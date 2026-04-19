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

Architecture:
- Uses ProfileState (TypedDict) for state management
- Integrates with Store API for cross-session data persistence
- Follows LangGraph 1.0.0 subgraph pattern with StateGraph

Requirements: 1.1, 1.2, 1.4, 4.1, 5.1
"""
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime

from langgraph.graph import StateGraph, START, END
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langchain_openai import ChatOpenAI

from models.subgraph_states import ProfileState
from models.user import UserProfile, RiskPreference, MaritalStatus, IncomeRange, HealthStatus
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


# ==================== Node Functions ====================

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


# ==================== Routing Functions ====================

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

def create_profile_subgraph(store=None) -> StateGraph:
    """
    Create the Profile Collection Subgraph
    
    The subgraph follows this flow:
    START → extract_slots → validate_profile → store_slots → END
                                        ↓
                                    (if incomplete)
                                        ↓
                                    extract_slots (loop)
    
    Args:
        store: Optional PostgresStore instance (for dependency injection)
        
    Returns:
        Compiled StateGraph for Profile Subgraph
    """
    logger.info("Creating Profile Collection Subgraph")
    
    # Create the graph with ProfileState
    builder = StateGraph(ProfileState)
    
    # Add nodes
    builder.add_node("extract_slots", extract_slots_node)
    builder.add_node("validate_profile", validate_profile_node)
    builder.add_node("store_slots", store_slots_node)
    
    # Add edges
    builder.add_edge(START, "extract_slots")
    builder.add_edge("extract_slots", "validate_profile")
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
    store=None
) -> ProfileState:
    """
    Convenience function to run the Profile Subgraph
    
    Args:
        session_id: Session identifier
        user_id: User identifier
        messages: List of conversation messages
        existing_slots: Existing slots from previous turns (optional)
        store: PostgresStore instance (optional)
        
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
    
    # Create and run subgraph
    subgraph = create_profile_subgraph(store)
    result = await subgraph.ainvoke(initial_state)
    
    return result


# ==================== Module Exports ====================

__all__ = [
    "create_profile_subgraph",
    "run_profile_subgraph",
    "extract_slots_node",
    "validate_profile_node",
    "store_slots_node",
    "REQUIRED_SLOTS",
    "OPTIONAL_SLOTS",
    "INTENT_TYPES",
]
