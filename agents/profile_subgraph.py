"""
Profile Collection Subgraph - LangGraph 1.0.0 Implementation

This module implements the Profile Collection Subgraph for the insurance recommendation system.
The subgraph is responsible for collecting user profile information through natural conversation.

Key Features:
- Extract slots from conversation using LLM
- Validate profile completeness
- Store extracted slots to Store API for cross-session persistence
- Handle multi-turn dialogue flow
- Detect and handle chitchat/off-topic conversations
- Detect user intent (ask_question vs provide_info) and route accordingly

Architecture:
- Uses ProfileState (TypedDict) for state management
- Integrates with Store API for cross-session data persistence
- Follows LangGraph 1.0.0 subgraph pattern with StateGraph

Requirements: 1.1, 1.2, 1.4, 4.1, 5.1, 6.1, 6.2, 6.3, 6.4, 6.5
"""
import logging
import re
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime

from langgraph.graph import StateGraph, START, END
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langchain_openai import ChatOpenAI

from models.subgraph_states import ProfileState
from models.user import UserProfile, RiskPreference, MaritalStatus, IncomeRange, HealthStatus
from models.intent import QuestionType, QUESTION_PATTERNS, PRODUCT_TYPE_NAMES
from utils.store_manager import get_store_manager, StoreError

logger = logging.getLogger(__name__)


# ==================== Constants ====================

# Required slots for a complete user profile
REQUIRED_SLOTS = [
    "age",
    "occupation",
    "marital_status",
    "income_range",
]

# Optional slots that enhance recommendations
OPTIONAL_SLOTS = [
    "has_children",
    "children_count",
    "has_dependents",
    "dependents_count",
    "family_size",
    "risk_preference",
    "health_status",
    "city",
    "province",
]

# Intent types the Profile Subgraph can recognize
INTENT_TYPES = [
    "provide_info",       # User providing personal information
    "ask_question",       # User asking about insurance concepts
    "modify_info",        # User correcting previous information
    "confirm_info",       # User confirming their information
    "chitchat",           # Off-topic conversation
    "greeting",           # Greeting message
    "request_recommendation",  # User asking for recommendations
    "unknown",            # Unclear intent
]

# Question indicators - words that suggest user is asking a question
QUESTION_INDICATORS = [
    "什么是", "是什么", "怎么", "如何", "为什么", "区别", "对比", "比较",
    "解释", "意思", "理赔", "流程", "步骤", "哪个", "好不好"
]

# System prompt for slot extraction
SLOT_EXTRACTION_PROMPT = """你是一个保险推荐系统的用户画像收集助手。你的任务是从用户的对话中提取结构化信息。

当前已收集的信息：
{current_slots}

缺失的必填信息：
{missing_slots}

请分析用户的最新消息，提取以下信息（如果用户提供）：
- age: 年龄（整数）
- occupation: 职业（字符串）
- marital_status: 婚姻状况（single/married/divorced/widowed）
- income_range: 收入区间（low/medium_low/medium/medium_high/high）
- has_children: 是否有子女（true/false）
- children_count: 子女数量（整数）
- has_dependents: 是否有被抚养人（true/false）
- dependents_count: 被抚养人数量（整数）
- family_size: 家庭人数（整数）
- risk_preference: 风险偏好（conservative/balanced/aggressive）
- health_status: 健康状况（excellent/good/fair/poor）
- city: 所在城市
- province: 所在省份

请以JSON格式返回提取的信息，格式如下：
{{
  "intent": "意图类型",
  "slots": {{
    "字段名": "值",
    ...
  }},
  "response": "对用户的回复（如果需要澄清或引导）"
}}

如果用户没有提供新的信息，slots可以为空。
如果用户的问题与保险无关，intent设为"chitchat"。
"""

# System prompt for profile validation
PROFILE_VALIDATION_PROMPT = """你是一个保险推荐系统的用户画像验证助手。

当前用户画像：
{user_profile}

请验证以下必填字段是否完整且合理：
- age: 年龄（0-120之间的整数）
- occupation: 职业（非空字符串）
- marital_status: 婚姻状况（single/married/divorced/widowed）
- income_range: 收入区间（low/medium_low/medium/medium_high/high）

请以JSON格式返回验证结果：
{{
  "is_complete": true/false,
  "missing_fields": ["字段1", "字段2"],
  "invalid_fields": ["字段1", ...],
  "validation_messages": ["问题1", "问题2"],
  "next_question": "下一个要问用户的问题（如果不完整）"
}}
"""


# ==================== Helper Functions ====================

def _get_llm():
    """Get LLM instance for slot extraction and validation"""
    from config import get_settings
    settings = get_settings()
    
    return ChatOpenAI(
        model=settings.LLM_MODEL,
        temperature=settings.LLM_TEMPERATURE,
        max_tokens=settings.LLM_MAX_TOKENS,
        api_key=settings.OPENAI_API_KEY,
        base_url=settings.OPENAI_API_BASE,
    )


def _format_slots_for_prompt(slots: Dict[str, Any]) -> str:
    """Format slots dictionary for prompt display"""
    if not slots:
        return "暂无"
    
    formatted = []
    for key, value in slots.items():
        formatted.append(f"- {key}: {value}")
    return "\n".join(formatted)


def _parse_llm_json_response(response: str) -> Dict[str, Any]:
    """Parse JSON response from LLM"""
    import json
    
    # Try to extract JSON from response
    try:
        # Remove markdown code blocks if present
        if "```json" in response:
            response = response.split("```json")[1].split("```")[0]
        elif "```" in response:
            response = response.split("```")[1].split("```")[0]
        
        return json.loads(response.strip())
    except Exception as e:
        logger.warning(f"Failed to parse LLM JSON response: {e}")
        return {}


def _detect_question_type(message: str) -> Tuple[str, Dict[str, Any]]:
    """
    Detect question type using pattern matching and extract entities.
    
    This function uses regex patterns to identify question types:
    - terminology: Questions about insurance terms (e.g., "什么是重疾险？")
    - comparison: Questions comparing products (e.g., "重疾险和医疗险有什么区别？")
    - claim: Questions about claim process (e.g., "怎么理赔？")
    
    Args:
        message: User message text
        
    Returns:
        Tuple of (question_type, extracted_entities)
        question_type: One of "terminology", "comparison", "claim", "general", "non_insurance"
        extracted_entities: Dict with extracted entities like {"term": "重疾险"} or 
                           {"product_types": ["critical_illness", "medical"]}
    """
    # Check each question type pattern
    for question_type, patterns in QUESTION_PATTERNS.items():
        for pattern in patterns:
            match = re.search(pattern, message)
            if match:
                entities = {}
                
                if question_type == "terminology":
                    # Extract the term being asked about
                    term = match.group(1).strip() if match.groups() else ""
                    if term:
                        entities["term"] = term
                        logger.debug(f"Detected terminology question about: {term}")
                
                elif question_type == "comparison":
                    # Extract the two product types being compared
                    if len(match.groups()) >= 2:
                        product1 = match.group(1).strip()
                        product2 = match.group(2).strip()
                        
                        # Convert Chinese names to English identifiers
                        product1_en = PRODUCT_TYPE_NAMES.get(product1, product1)
                        product2_en = PRODUCT_TYPE_NAMES.get(product2, product2)
                        
                        entities["product_types"] = [product1_en, product2_en]
                        entities["product_types_cn"] = [product1, product2]
                        logger.debug(f"Detected comparison question: {product1} vs {product2}")
                
                elif question_type == "claim":
                    # Extract product type for claim process question
                    # Claim questions might not always specify a product type
                    entities["product_type"] = None
                    
                    # Try to find product type in the message
                    for cn_name, en_name in PRODUCT_TYPE_NAMES.items():
                        if cn_name in message:
                            entities["product_type"] = en_name
                            entities["product_type_cn"] = cn_name
                            break
                    
                    logger.debug(f"Detected claim process question for: {entities.get('product_type', 'general')}")
                
                return question_type, entities
    
    # Check if message contains question indicators but didn't match patterns
    has_question_indicator = any(indicator in message for indicator in QUESTION_INDICATORS)
    
    if has_question_indicator:
        # It's a question but doesn't match our patterns
        return "general", {}
    
    # Not a question
    return "non_insurance", {}


def _is_question_message(message: str) -> bool:
    """
    Determine if a message is a question based on patterns and indicators.
    
    Args:
        message: User message text
        
    Returns:
        True if the message appears to be a question, False otherwise
    """
    # Check for question marks
    if "？" in message or "?" in message:
        return True
    
    # Check for question indicators
    for indicator in QUESTION_INDICATORS:
        if indicator in message:
            return True
    
    return False


# ==================== Node Functions ====================

async def detect_intent_node(state: ProfileState) -> Dict[str, Any]:
    """
    Detect user intent from the latest message.
    
    This node:
    1. Analyzes the latest user message
    2. Determines if user is asking a question or providing information
    3. If asking a question, identifies the question type (terminology, comparison, claim)
    4. Extracts relevant entities from the question
    5. Updates ProfileState with detected intent and entities
    
    The intent detection uses pattern matching with regex to identify:
    - Terminology questions: "什么是重疾险？"
    - Comparison questions: "重疾险和医疗险有什么区别？"
    - Claim process questions: "怎么理赔？"
    
    Args:
        state: Current ProfileState
        
    Returns:
        Dict with current_intent, question_type, extracted_entities, and error fields
        
    Requirements: 6.1, 6.2, 6.3, 6.4, 6.5
    """
    logger.info(f"Detecting intent for session {state.get('session_id')}")
    
    try:
        # Get the latest user message
        messages = state.get("messages", [])
        if not messages:
            logger.warning("No messages in state")
            return {
                "current_intent": "unknown",
                "question_type": None,
                "extracted_entities": {},
                "error": None
            }
        
        # Get the last user message
        last_message = messages[-1] if messages else None
        user_message = ""
        if isinstance(last_message, HumanMessage):
            user_message = last_message.content
        elif isinstance(last_message, dict):
            user_message = last_message.get("content", "")
        
        logger.debug(f"Analyzing message: {user_message[:100]}...")
        
        # Check if the message is a question
        is_question = _is_question_message(user_message)
        
        if is_question:
            # Detect question type and extract entities
            question_type, entities = _detect_question_type(user_message)
            
            logger.info(f"Detected question - type: {question_type}, entities: {entities}")
            
            return {
                "current_intent": "ask_question",
                "question_type": question_type,
                "extracted_entities": entities,
                "error": None
            }
        else:
            # Not a question - user is providing information or other intent
            # The extract_slots_node will handle slot extraction
            logger.debug("Message is not a question, will proceed to slot extraction")
            
            return {
                "current_intent": "provide_info",
                "question_type": None,
                "extracted_entities": {},
                "error": None
            }
    
    except Exception as e:
        logger.error(f"Error in detect_intent_node: {e}", exc_info=True)
        return {
            "current_intent": "unknown",
            "question_type": None,
            "extracted_entities": {},
            "error": f"意图检测失败: {str(e)}"
        }


async def extract_slots_node(state: ProfileState) -> Dict[str, Any]:
    """
    Extract slots from conversation using LLM
    
    This node:
    1. Analyzes the latest user message
    2. Identifies user intent
    3. Extracts structured information (slots)
    4. Returns extracted slots and intent
    
    Args:
        state: Current ProfileState
        
    Returns:
        Dict with updated slots, intent, and other fields
    """
    logger.info(f"Extracting slots for session {state.get('session_id')}")
    
    try:
        # Get LLM instance
        llm = _get_llm()
        
        # Get current slots and missing slots
        current_slots = state.get("slots", {})
        missing_slots = state.get("missing_slots", REQUIRED_SLOTS.copy())
        
        # Get the latest user message
        messages = state.get("messages", [])
        if not messages:
            logger.warning("No messages in state")
            return {
                "current_intent": "unknown",
                "error": None
            }
        
        # Get the last user message
        last_message = messages[-1] if messages else None
        user_message = ""
        if isinstance(last_message, HumanMessage):
            user_message = last_message.content
        elif isinstance(last_message, dict):
            user_message = last_message.get("content", "")
        
        # Prepare prompt
        prompt = SLOT_EXTRACTION_PROMPT.format(
            current_slots=_format_slots_for_prompt(current_slots),
            missing_slots=", ".join(missing_slots) if missing_slots else "无"
        )
        
        # Call LLM
        messages_for_llm = [
            SystemMessage(content=prompt),
            HumanMessage(content=user_message)
        ]
        
        response = await llm.ainvoke(messages_for_llm)
        response_text = response.content
        
        # Parse response
        parsed = _parse_llm_json_response(response_text)
        
        intent = parsed.get("intent", "unknown")
        new_slots = parsed.get("slots", {})
        ai_response = parsed.get("response", "")
        
        # Merge new slots with existing slots
        updated_slots = {**current_slots, **new_slots}
        
        # Update missing slots
        updated_missing = [
            slot for slot in missing_slots 
            if slot not in updated_slots or updated_slots[slot] is None
        ]
        
        logger.info(f"Extracted intent: {intent}, new slots: {list(new_slots.keys())}")
        
        return {
            "slots": updated_slots,
            "missing_slots": updated_missing,
            "current_intent": intent,
            "error": None
        }
        
    except Exception as e:
        logger.error(f"Error in extract_slots_node: {e}")
        return {
            "current_intent": "unknown",
            "error": f"槽位提取失败: {str(e)}"
        }


async def validate_profile_node(state: ProfileState) -> Dict[str, Any]:
    """
    Validate profile completeness and correctness
    
    This node:
    1. Checks if all required slots are filled
    2. Validates slot values (e.g., age range, valid enum values)
    3. Determines if profile is complete
    4. Generates next question if incomplete
    
    Args:
        state: Current ProfileState
        
    Returns:
        Dict with profile_complete, user_profile, and other fields
    """
    logger.info(f"Validating profile for session {state.get('session_id')}")
    
    try:
        slots = state.get("slots", {})
        missing_slots = state.get("missing_slots", [])
        
        # Check if all required slots are present
        is_complete = len(missing_slots) == 0
        
        # Validate slot values
        validation_errors = []
        
        # Validate age
        if "age" in slots:
            try:
                age = int(slots["age"])
                if not (0 <= age <= 120):
                    validation_errors.append("年龄必须在0-120之间")
            except (ValueError, TypeError):
                validation_errors.append("年龄必须是整数")
        
        # Validate marital_status
        if "marital_status" in slots:
            valid_statuses = ["single", "married", "divorced", "widowed"]
            if slots["marital_status"] not in valid_statuses:
                validation_errors.append(f"婚姻状况必须是: {', '.join(valid_statuses)}")
        
        # Validate income_range
        if "income_range" in slots:
            valid_ranges = ["low", "medium_low", "medium", "medium_high", "high"]
            if slots["income_range"] not in valid_ranges:
                validation_errors.append(f"收入区间必须是: {', '.join(valid_ranges)}")
        
        # Validate risk_preference if present
        if "risk_preference" in slots and slots["risk_preference"]:
            valid_preferences = ["conservative", "balanced", "aggressive"]
            if slots["risk_preference"] not in valid_preferences:
                validation_errors.append(f"风险偏好必须是: {', '.join(valid_preferences)}")
        
        # Validate health_status if present
        if "health_status" in slots and slots["health_status"]:
            valid_statuses = ["excellent", "good", "fair", "poor"]
            if slots["health_status"] not in valid_statuses:
                validation_errors.append(f"健康状况必须是: {', '.join(valid_statuses)}")
        
        # If there are validation errors, profile is not complete
        if validation_errors:
            is_complete = False
            logger.warning(f"Validation errors: {validation_errors}")
        
        # Create UserProfile if complete
        user_profile = None
        if is_complete and not validation_errors:
            try:
                user_profile = UserProfile(
                    age=int(slots.get("age", 0)),
                    occupation=slots.get("occupation", ""),
                    marital_status=MaritalStatus(slots.get("marital_status", "single")),
                    has_children=slots.get("has_children", False),
                    children_count=slots.get("children_count", 0),
                    has_dependents=slots.get("has_dependents", False),
                    dependents_count=slots.get("dependents_count", 0),
                    family_size=slots.get("family_size", 1),
                    income_range=IncomeRange(slots.get("income_range", "medium")),
                    risk_preference=RiskPreference(slots.get("risk_preference")) if slots.get("risk_preference") else None,
                    health_status=HealthStatus(slots.get("health_status")) if slots.get("health_status") else None,
                    city=slots.get("city"),
                    province=slots.get("province"),
                )
                logger.info(f"Created UserProfile for user {state.get('user_id')}")
            except Exception as e:
                logger.error(f"Failed to create UserProfile: {e}")
                is_complete = False
                validation_errors.append(f"用户画像创建失败: {str(e)}")
        
        return {
            "profile_complete": is_complete,
            "user_profile": user_profile,
            "error": "; ".join(validation_errors) if validation_errors else None
        }
        
    except Exception as e:
        logger.error(f"Error in validate_profile_node: {e}")
        return {
            "profile_complete": False,
            "error": f"画像验证失败: {str(e)}"
        }


async def store_slots_node(state: ProfileState) -> Dict[str, Any]:
    """
    Store extracted slots to Store API
    
    This node:
    1. Stores/updates slots in Store API (namespace: users/{user_id})
    2. Enables cross-session persistence of user profile
    3. Handles Store API errors gracefully
    
    Args:
        state: Current ProfileState
        
    Returns:
        Dict with error field (None if successful)
    """
    logger.info(f"Storing slots to Store API for user {state.get('user_id')}")
    
    try:
        user_id = state.get("user_id")
        slots = state.get("slots", {})
        
        if not user_id:
            logger.warning("No user_id in state, skipping store")
            return {"error": None}
        
        if not slots:
            logger.debug("No slots to store")
            return {"error": None}
        
        # Get store manager
        store_manager = get_store_manager()
        
        # Update user profile in Store API
        # This merges with existing profile data
        store_manager.update_user_profile(
            user_id=user_id,
            updates=slots
        )
        
        logger.info(f"Successfully stored {len(slots)} slots for user {user_id}")
        
        return {"error": None}
        
    except StoreError as e:
        logger.error(f"Store API error: {e}")
        # Don't fail the entire flow if Store API fails
        # The profile can still be used in the current session
        return {"error": f"存储失败（将使用会话内数据）: {str(e)}"}
        
    except Exception as e:
        logger.error(f"Error in store_slots_node: {e}")
        return {"error": f"存储失败: {str(e)}"}


# ==================== Question Handling Node ====================

def _format_comparison_result(result: Dict[str, Any]) -> str:
    """
    Format comparison result for user display.
    
    Args:
        result: Comparison result from InsuranceDomainSkill.compare_products()
        
    Returns:
        Formatted text for user display
    """
    parts = []
    
    # Product names
    product1_name = result.get("product1", {}).get("name", "产品1")
    product2_name = result.get("product2", {}).get("name", "产品2")
    parts.append(f"**{product1_name} vs {product2_name}**\n")
    
    # Comparison dimensions
    comparison = result.get("comparison", [])
    if comparison:
        parts.append("**对比维度：**\n")
        for dim in comparison:
            dim_name = dim.get("name", "")
            val1 = dim.get(result.get("product1", {}).get("type", "product1"), "")
            val2 = dim.get(result.get("product2", {}).get("type", "product2"), "")
            parts.append(f"- **{dim_name}**:")
            parts.append(f"  - {product1_name}: {val1}")
            parts.append(f"  - {product2_name}: {val2}")
    
    # Recommendation
    recommendation = result.get("recommendation")
    if recommendation:
        parts.append(f"\n**建议：** {recommendation}")
    
    return "\n".join(parts)


async def handle_question_node(
    state: ProfileState,
    insurance_skill: "InsuranceDomainSkill"
) -> Dict[str, Any]:
    """
    Handle user questions using InsuranceDomainSkill with graceful degradation.
    
    This node:
    1. Routes questions to appropriate InsuranceDomainSkill methods based on question_type
    2. Wraps all skill calls in try-except blocks for error handling
    3. Returns fallback messages when skill fails
    4. Logs errors for debugging without exposing to users
    5. Preserves missing_slots state to continue profile collection
    
    Args:
        state: Current ProfileState
        insurance_skill: InsuranceDomainSkill instance (injected via closure)
        
    Returns:
        Dict with response, error, and preserved state fields
        
    Requirements: 1.1, 1.2, 1.3, 4.1, 4.2, 4.3, 4.6
    """
    logger.info(f"Handling question for session {state.get('session_id')}")
    
    question_type = state.get("question_type")
    entities = state.get("extracted_entities", {})
    missing_slots = state.get("missing_slots", [])
    
    try:
        # Handle terminology questions
        if question_type == "terminology":
            term = entities.get("term", "")
            
            if not term:
                logger.warning("Terminology question but no term extracted")
                return {
                    "response": "请提供要查询的术语名称。您可以问我关于重疾险、医疗险、意外险、寿险等保险术语。",
                    "error": None,
                    "missing_slots": missing_slots  # Preserve for continued collection
                }
            
            try:
                logger.debug(f"Explaining term: {term}")
                explanation = insurance_skill.explain_term(term)
                
                return {
                    "response": explanation,
                    "error": None,
                    "missing_slots": missing_slots
                }
            except Exception as e:
                logger.error(f"Failed to explain term '{term}': {e}", exc_info=True)
                # Return fallback message without exposing error details
                return {
                    "response": f"抱歉，查询术语'{term}'时出现错误。您可以尝试查询其他保险术语，如：重疾险、医疗险、意外险、寿险、等待期、犹豫期等。或咨询专业保险顾问。",
                    "error": f"术语解释失败: {str(e)}",
                    "missing_slots": missing_slots
                }
        
        # Handle comparison questions
        elif question_type == "comparison":
            product_types = entities.get("product_types", [])
            product_types_cn = entities.get("product_types_cn", [])
            
            if len(product_types) < 2:
                logger.warning("Comparison question but insufficient product types extracted")
                return {
                    "response": "请提供要对比的两种产品类型。例如：'重疾险和医疗险有什么区别？'",
                    "error": None,
                    "missing_slots": missing_slots
                }
            
            try:
                logger.debug(f"Comparing products: {product_types[0]} vs {product_types[1]}")
                result = insurance_skill.compare_products(product_types[0], product_types[1])
                
                # Check if skill returned an error
                if "error" in result:
                    available_types = result.get("available_types", [])
                    available_names = ["重疾险", "医疗险", "意外险", "寿险"]
                    
                    return {
                        "response": f"{result['error']}\n\n可用产品类型：{', '.join(available_names)}",
                        "error": None,
                        "missing_slots": missing_slots
                    }
                
                # Format comparison result for user
                formatted_response = _format_comparison_result(result)
                
                return {
                    "response": formatted_response,
                    "error": None,
                    "missing_slots": missing_slots
                }
            except Exception as e:
                logger.error(f"Failed to compare products: {e}", exc_info=True)
                return {
                    "response": "抱歉，产品对比时出现错误。您可以尝试对比其他产品类型，如：重疾险、医疗险、意外险、寿险。或咨询专业保险顾问获取详细对比。",
                    "error": f"产品对比失败: {str(e)}",
                    "missing_slots": missing_slots
                }
        
        # Handle claim process questions
        elif question_type == "claim":
            product_type = entities.get("product_type")
            product_type_cn = entities.get("product_type_cn", "")
            
            if not product_type:
                # No specific product type mentioned - provide general claim info
                logger.debug("Claim question without specific product type")
                return {
                    "response": "**理赔流程概述**\n\n一般理赔流程包括以下步骤：\n1. 及时报案：发生保险事故后，请及时拨打保险公司客服电话报案\n2. 准备材料：根据理赔类型准备相关证明材料\n3. 提交申请：通过线上或线下渠道提交理赔申请\n4. 审核处理：保险公司审核材料并进行理赔调查\n5. 赔付结案：审核通过后，赔款将打入指定账户\n\n如需了解具体产品的理赔流程，请告诉我产品类型（如重疾险、医疗险、意外险、寿险）。",
                    "error": None,
                    "missing_slots": missing_slots
                }
            
            try:
                logger.debug(f"Explaining claim process for: {product_type}")
                steps = insurance_skill.explain_claim_process(product_type)
                
                # Format steps for display
                response = "\n".join(steps)
                
                return {
                    "response": response,
                    "error": None,
                    "missing_slots": missing_slots
                }
            except Exception as e:
                logger.error(f"Failed to explain claim process: {e}", exc_info=True)
                return {
                    "response": f"抱歉，查询{product_type_cn or product_type}理赔流程时出现错误。一般理赔流程包括：报案、准备材料、提交申请、审核处理、赔付结案。建议咨询专业保险顾问或拨打保险公司客服获取详细信息。",
                    "error": f"理赔流程查询失败: {str(e)}",
                    "missing_slots": missing_slots
                }
        
        # Handle general insurance questions
        elif question_type == "general":
            logger.debug("General insurance question - providing guidance")
            return {
                "response": "我可以帮您解答以下类型的保险问题：\n\n1. **术语解释**：如'什么是重疾险？'、'等待期是什么意思？'\n2. **产品对比**：如'重疾险和医疗险有什么区别？'\n3. **理赔流程**：如'重疾险怎么理赔？'\n\n请告诉我您想了解哪方面的内容？",
                "error": None,
                "missing_slots": missing_slots
            }
        
        # Handle non-insurance questions
        elif question_type == "non_insurance":
            logger.debug("Non-insurance question - providing polite guidance")
            return {
                "response": "我是保险推荐助手，主要帮助您了解保险知识和推荐合适的保险产品。如果您有保险相关的问题，我很乐意为您解答。您也可以继续提供您的个人信息，以便我为您推荐合适的保险产品。",
                "error": None,
                "missing_slots": missing_slots
            }
        
        # Unknown question type
        else:
            logger.warning(f"Unknown question type: {question_type}")
            return {
                "response": "抱歉，我暂时无法回答这类问题。您可以问我关于保险术语、产品对比或理赔流程的问题，或者继续提供您的个人信息。",
                "error": None,
                "missing_slots": missing_slots
            }
    
    except Exception as e:
        # Catch-all for any unexpected errors
        logger.error(f"Unexpected error in handle_question_node: {e}", exc_info=True)
        return {
            "response": "抱歉，处理您的问题时出现错误。请稍后再试或咨询专业保险顾问。",
            "error": f"问题处理失败: {str(e)}",
            "missing_slots": missing_slots
        }


# ==================== Routing Functions ====================

def route_after_intent_detection(state: ProfileState) -> str:
    """
    Route after intent detection based on the detected intent.
    
    Routes based on:
    - current_intent: If "ask_question", route to handle_question
    - current_intent: If "provide_info", route to extract_slots
    
    Args:
        state: Current ProfileState
        
    Returns:
        Next node name
    """
    intent = state.get("current_intent", "unknown")
    
    if intent == "ask_question":
        logger.debug("Routing to handle_question node")
        return "handle_question"
    else:
        # For provide_info, modify_info, or other intents, extract slots
        logger.debug("Routing to extract_slots node")
        return "extract_slots"


def should_continue(state: ProfileState) -> str:
    """
    Determine if profile collection should continue or end
    
    Routes based on:
    - profile_complete: If True, go to END
    - current_intent: Handle special intents (chitchat, etc.)
    - missing_slots: If there are missing slots, continue extraction
    
    Args:
        state: Current ProfileState
        
    Returns:
        Next node name or END
    """
    # If profile is complete, we're done
    if state.get("profile_complete"):
        logger.info("Profile complete, ending subgraph")
        return END
    
    # Check intent for special handling
    intent = state.get("current_intent", "unknown")
    
    # For chitchat or greetings, we might want to respond but continue
    if intent in ["chitchat", "greeting"]:
        logger.debug(f"Handling {intent} intent, continuing collection")
        return "extract_slots"
    
    # If there are missing slots, continue extraction
    missing_slots = state.get("missing_slots", [])
    if missing_slots:
        logger.debug(f"Missing slots: {missing_slots}, continuing collection")
        return "extract_slots"
    
    # Default: end
    return END


# ==================== Subgraph Builder ====================

def create_profile_subgraph(
    store=None,
    insurance_skill: Optional["InsuranceDomainSkill"] = None
) -> StateGraph:
    """
    Create the Profile Collection Subgraph
    
    The subgraph follows this flow:
    START → detect_intent → [ask_question?] → handle_question → validate_profile → store_slots → END
                          ↓                                          ↑
                          ↓ (provide_info)                           |
                          → extract_slots → validate_profile ────────┘
                                        ↓
                                    (if incomplete)
                                        ↓
                                    extract_slots (loop)
    
    Args:
        store: Optional PostgresStore instance (for dependency injection)
        insurance_skill: Optional InsuranceDomainSkill instance (for dependency injection).
                        If not provided, a default instance will be created.
        
    Returns:
        Compiled StateGraph for Profile Subgraph
        
    Requirements: 5.1, 5.3, 5.6
    """
    logger.info("Creating Profile Collection Subgraph")
    
    # Use provided skill or create default instance
    if insurance_skill is None:
        from skills.insurance_domain import InsuranceDomainSkill
        insurance_skill = InsuranceDomainSkill()
        logger.debug("Created default InsuranceDomainSkill instance")
    else:
        logger.debug("Using injected InsuranceDomainSkill instance")
    
    # Create node functions with skill captured in closure
    async def handle_question_with_skill(state: ProfileState) -> Dict[str, Any]:
        """Wrapper that passes insurance_skill to handle_question_node"""
        return await handle_question_node(state, insurance_skill)
    
    # Create the graph with ProfileState
    builder = StateGraph(ProfileState)
    
    # Add nodes
    builder.add_node("detect_intent", detect_intent_node)
    builder.add_node("handle_question", handle_question_with_skill)
    builder.add_node("extract_slots", extract_slots_node)
    builder.add_node("validate_profile", validate_profile_node)
    builder.add_node("store_slots", store_slots_node)
    
    # Add edges
    # START → detect_intent
    builder.add_edge(START, "detect_intent")
    
    # detect_intent → conditional routing
    builder.add_conditional_edges(
        "detect_intent",
        route_after_intent_detection,
        {
            "handle_question": "handle_question",
            "extract_slots": "extract_slots"
        }
    )
    
    # handle_question → validate_profile (continue collection after answering)
    builder.add_edge("handle_question", "validate_profile")
    
    # extract_slots → validate_profile
    builder.add_edge("extract_slots", "validate_profile")
    
    # validate_profile → store_slots
    builder.add_edge("validate_profile", "store_slots")
    
    # Add conditional edge from store_slots
    builder.add_conditional_edges(
        "store_slots",
        should_continue,
        {
            "extract_slots": "extract_slots",
            END: END
        }
    )
    
    # Compile the graph
    graph = builder.compile()
    
    logger.info("Profile Collection Subgraph created successfully")
    
    return graph


# ==================== Convenience Functions ====================

async def run_profile_subgraph(
    session_id: str,
    user_id: str,
    messages: List[Any],
    existing_slots: Optional[Dict[str, Any]] = None,
    store=None,
    insurance_skill: Optional["InsuranceDomainSkill"] = None
) -> ProfileState:
    """
    Convenience function to run the Profile Subgraph
    
    Args:
        session_id: Session identifier
        user_id: User identifier
        messages: List of conversation messages
        existing_slots: Existing slots from previous turns (optional)
        store: PostgresStore instance (optional)
        insurance_skill: InsuranceDomainSkill instance (optional)
        
    Returns:
        Final ProfileState after subgraph execution
    """
    # Create initial state
    initial_state = ProfileState(
        messages=messages,
        user_id=user_id,
        session_id=session_id,
        user_profile=None,
        slots=existing_slots or {},
        missing_slots=REQUIRED_SLOTS.copy(),
        risk_preference=None,
        risk_score=None,
        existing_coverage=[],
        current_intent=None,
        profile_complete=False,
        error=None
    )
    
    # Create and run subgraph with injected skill
    subgraph = create_profile_subgraph(store, insurance_skill)
    result = await subgraph.ainvoke(initial_state)
    
    return result


# ==================== Module Exports ====================

__all__ = [
    "create_profile_subgraph",
    "run_profile_subgraph",
    "detect_intent_node",
    "handle_question_node",
    "extract_slots_node",
    "validate_profile_node",
    "store_slots_node",
    "REQUIRED_SLOTS",
    "OPTIONAL_SLOTS",
    "INTENT_TYPES",
    "QUESTION_INDICATORS",
]
