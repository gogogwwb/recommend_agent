"""
Compliance Subgraph - LangGraph 1.0.0 Implementation

This module implements the Compliance Subgraph for the insurance recommendation system.
The subgraph is responsible for validating user eligibility for recommended products,
generating disclosure information, and logging compliance checks.

Key Features:
- Check user eligibility for each recommended product (age, occupation, health)
- Generate mandatory disclosure information for each product
- Log compliance check results for audit purposes
- Filter out products that don't pass compliance checks

Architecture:
- Uses ComplianceState (TypedDict) for state management
- Integrates with database for compliance logging
- Follows LangGraph 1.0.0 subgraph pattern with StateGraph

Requirements: 10.1, 10.2, 10.3, 10.4, 11.1
"""
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime

from langgraph.graph import StateGraph, START, END
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langchain_openai import ChatOpenAI
from sqlalchemy.orm import Session

from models.subgraph_states import ComplianceState
from models.user import UserProfile, HealthStatus
from models.product import RecommendationResult, Product
from models.compliance import (
    ComplianceCheck,
    ComplianceCheckType,
    CheckResult,
    DisclosureInfo,
    DisclosureItem,
)
from models.db_models import ComplianceLog, CheckResultEnum

logger = logging.getLogger(__name__)


# ==================== Constants ====================

# Compliance check types
COMPLIANCE_CHECK_TYPES = [
    ComplianceCheckType.AGE_CHECK,
    ComplianceCheckType.OCCUPATION_CHECK,
    ComplianceCheckType.HEALTH_CHECK,
    ComplianceCheckType.REGION_CHECK,
]

# High-risk occupations (simplified list)
HIGH_RISK_OCCUPATIONS = [
    "矿工",
    "高空作业人员",
    "消防员",
    "警察",
    "军人",
    "飞行员",
    "深海潜水员",
]

# Region restrictions (simplified)
RESTRICTED_REGIONS = [
    "高风险地区",  # Placeholder for actual restricted regions
]

# System prompt for disclosure generation
DISCLOSURE_GENERATION_PROMPT = """你是一个保险产品信息披露助手。

产品信息：
{product_info}

请生成简洁、易懂的信息披露内容，包括：
1. 保险责任（主要保障内容）
2. 责任免除（不赔付的情况）
3. 犹豫期说明
4. 费用说明

请用用户友好的语言，避免专业术语堆砌。
"""


# ==================== Helper Functions ====================

def _get_llm():
    """Get LLM instance for disclosure generation"""
    from config import get_settings
    settings = get_settings()
    
    return ChatOpenAI(
        model=settings.LLM_MODEL,
        temperature=settings.LLM_TEMPERATURE,
        max_tokens=settings.LLM_MAX_TOKENS,
        api_key=settings.OPENAI_API_KEY,
        base_url=settings.OPENAI_API_BASE,
    )


def _get_db_session() -> Session:
    """Get database session for compliance logging"""
    from utils.checkpointer import get_db_session
    return get_db_session()


def _check_age_eligibility(
    user_age: int,
    product_min_age: int,
    product_max_age: int
) -> ComplianceCheck:
    """
    Check if user's age is within product's acceptable range
    
    Args:
        user_age: User's age
        product_min_age: Product's minimum age requirement
        product_max_age: Product's maximum age requirement
        
    Returns:
        ComplianceCheck with result
    """
    is_eligible = product_min_age <= user_age <= product_max_age
    
    if is_eligible:
        return ComplianceCheck(
            check_type=ComplianceCheckType.AGE_CHECK,
            check_result=CheckResult.PASSED,
            check_description=f"年龄检查通过：{user_age}岁在投保范围内",
            checked_value=str(user_age),
            expected_value=f"{product_min_age}-{product_max_age}岁",
        )
    else:
        reason = ""
        if user_age < product_min_age:
            reason = f"年龄不足，需满{product_min_age}岁"
        else:
            reason = f"年龄超限，最高投保年龄{product_max_age}岁"
        
        return ComplianceCheck(
            check_type=ComplianceCheckType.AGE_CHECK,
            check_result=CheckResult.FAILED,
            check_description=f"年龄检查未通过：{user_age}岁",
            reason=reason,
            recommendation="请选择适合您年龄段的产品",
            checked_value=str(user_age),
            expected_value=f"{product_min_age}-{product_max_age}岁",
        )


def _check_occupation_eligibility(
    user_occupation: str,
    product_occupation_restrictions: List[str]
) -> ComplianceCheck:
    """
    Check if user's occupation is allowed for the product
    
    Args:
        user_occupation: User's occupation
        product_occupation_restrictions: List of restricted occupations
        
    Returns:
        ComplianceCheck with result
    """
    # Check if occupation is in restricted list
    is_restricted = any(
        restricted.lower() in user_occupation.lower()
        for restricted in product_occupation_restrictions
    )
    
    # Also check high-risk occupations
    is_high_risk = any(
        high_risk.lower() in user_occupation.lower()
        for high_risk in HIGH_RISK_OCCUPATIONS
    )
    
    if not is_restricted and not is_high_risk:
        return ComplianceCheck(
            check_type=ComplianceCheckType.OCCUPATION_CHECK,
            check_result=CheckResult.PASSED,
            check_description=f"职业检查通过：{user_occupation}",
            checked_value=user_occupation,
            expected_value="非限制职业",
        )
    elif is_high_risk and not is_restricted:
        return ComplianceCheck(
            check_type=ComplianceCheckType.OCCUPATION_CHECK,
            check_result=CheckResult.WARNING,
            check_description=f"职业检查警告：{user_occupation}属于高风险职业",
            reason="高风险职业可能影响保费或保障范围",
            recommendation="建议咨询客服了解详细投保条件",
            checked_value=user_occupation,
            expected_value="非限制职业",
        )
    else:
        return ComplianceCheck(
            check_type=ComplianceCheckType.OCCUPATION_CHECK,
            check_result=CheckResult.FAILED,
            check_description=f"职业检查未通过：{user_occupation}",
            reason="该职业属于限制投保职业",
            recommendation="请选择其他适合的产品或咨询客服",
            checked_value=user_occupation,
            expected_value="非限制职业",
        )


def _check_health_eligibility(
    user_health_status: Optional[HealthStatus],
    product_health_requirements: List[str]
) -> ComplianceCheck:
    """
    Check if user's health status meets product requirements
    
    Args:
        user_health_status: User's health status
        product_health_requirements: Product's health requirements
        
    Returns:
        ComplianceCheck with result
    """
    if not user_health_status:
        # No health status provided - require manual review
        return ComplianceCheck(
            check_type=ComplianceCheckType.HEALTH_CHECK,
            check_result=CheckResult.MANUAL_REVIEW,
            check_description="健康状况检查：需要人工审核",
            reason="未提供健康状况信息",
            recommendation="请提供健康状况信息以便完成审核",
            checked_value="unknown",
            expected_value="健康状况声明",
        )
    
    # Check health status against requirements
    health_status_value = user_health_status.value if isinstance(user_health_status, HealthStatus) else user_health_status
    
    # Simplified health check logic
    if health_status_value in ["excellent", "good"]:
        return ComplianceCheck(
            check_type=ComplianceCheckType.HEALTH_CHECK,
            check_result=CheckResult.PASSED,
            check_description=f"健康状况检查通过：{health_status_value}",
            checked_value=health_status_value,
            expected_value="良好或优秀",
        )
    elif health_status_value == "fair":
        return ComplianceCheck(
            check_type=ComplianceCheckType.HEALTH_CHECK,
            check_result=CheckResult.WARNING,
            check_description=f"健康状况检查警告：{health_status_value}",
            reason="健康状况一般，可能需要额外核保",
            recommendation="建议提供详细健康报告",
            checked_value=health_status_value,
            expected_value="良好或优秀",
        )
    else:  # poor
        return ComplianceCheck(
            check_type=ComplianceCheckType.HEALTH_CHECK,
            check_result=CheckResult.FAILED,
            check_description=f"健康状况检查未通过：{health_status_value}",
            reason="健康状况不符合投保要求",
            recommendation="请咨询客服了解可投保的产品",
            checked_value=health_status_value,
            expected_value="良好或优秀",
        )


def _check_region_eligibility(
    user_city: Optional[str],
    user_province: Optional[str],
    product_region_restrictions: List[str]
) -> ComplianceCheck:
    """
    Check if user's region is allowed for the product
    
    Args:
        user_city: User's city
        user_province: User's province
        product_region_restrictions: List of restricted regions
        
    Returns:
        ComplianceCheck with result
    """
    user_region = f"{user_province or ''}{user_city or ''}".strip()
    
    if not user_region:
        # No region info - pass with warning
        return ComplianceCheck(
            check_type=ComplianceCheckType.REGION_CHECK,
            check_result=CheckResult.WARNING,
            check_description="地区检查：未提供地区信息",
            reason="未提供地区信息，可能影响投保",
            recommendation="建议提供所在地区信息",
            checked_value="unknown",
            expected_value="中国大陆地区",
        )
    
    # Check if region is restricted
    is_restricted = any(
        restricted in user_region
        for restricted in product_region_restrictions
    )
    
    if not is_restricted:
        return ComplianceCheck(
            check_type=ComplianceCheckType.REGION_CHECK,
            check_result=CheckResult.PASSED,
            check_description=f"地区检查通过：{user_region}",
            checked_value=user_region,
            expected_value="中国大陆地区",
        )
    else:
        return ComplianceCheck(
            check_type=ComplianceCheckType.REGION_CHECK,
            check_result=CheckResult.FAILED,
            check_description=f"地区检查未通过：{user_region}",
            reason="该地区暂不支持投保",
            recommendation="请选择其他产品或联系客服",
            checked_value=user_region,
            expected_value="中国大陆地区",
        )


def _determine_overall_result(checks: List[ComplianceCheck]) -> CheckResult:
    """
    Determine overall compliance result from individual checks
    
    Args:
        checks: List of compliance checks
        
    Returns:
        Overall CheckResult
    """
    if not checks:
        return CheckResult.MANUAL_REVIEW
    
    # If any check failed, overall is failed
    if any(check.check_result == CheckResult.FAILED for check in checks):
        return CheckResult.FAILED
    
    # If any check requires manual review, overall is manual review
    if any(check.check_result == CheckResult.MANUAL_REVIEW for check in checks):
        return CheckResult.MANUAL_REVIEW
    
    # If any check has warning, overall is warning
    if any(check.check_result == CheckResult.WARNING for check in checks):
        return CheckResult.WARNING
    
    # All passed
    return CheckResult.PASSED


def _format_disclosure_content(product: Product) -> Dict[str, str]:
    """
    Format disclosure content from product information
    
    Args:
        product: Product to generate disclosure for
        
    Returns:
        Dict with disclosure content
    """
    # Format insurance liability
    liability = "、".join(product.coverage_scope) if product.coverage_scope else "详见条款"
    
    # Format exclusions (simplified)
    exclusions = "投保前已患疾病、故意犯罪、酒驾、吸毒、战争、核辐射等情况不予赔付"
    
    # Format fees
    fees = f"保费范围：{product.premium_range.min_premium}-{product.premium_range.max_premium}元/年"
    if product.payment_period:
        fees += f"，缴费期限：{'、'.join(product.payment_period)}"
    
    return {
        "insurance_liability": liability,
        "liability_exclusions": exclusions,
        "fee_description": fees,
    }


# ==================== Node Functions ====================

async def check_eligibility_node(state: ComplianceState) -> Dict[str, Any]:
    """
    Check user eligibility for each recommended product
    
    This node:
    1. Validates user's age, occupation, health status against product requirements
    2. Generates compliance checks for each product
    3. Determines overall eligibility
    
    Args:
        state: Current ComplianceState
        
    Returns:
        Dict with compliance_checks and compliance_passed
    """
    logger.info(f"Checking eligibility for user {state.get('user_id')}")
    
    try:
        user_profile = state.get("user_profile")
        recommendations = state.get("recommendations", [])
        
        if not user_profile:
            logger.error("No user_profile in state")
            return {
                "error": "缺少用户画像",
                "compliance_passed": False,
            }
        
        if not recommendations:
            logger.warning("No recommendations to check")
            return {
                "compliance_checks": [],
                "compliance_passed": True,
                "filtered_recommendations": [],
                "error": None,
            }
        
        all_compliance_checks = []
        
        # Check each recommendation
        for rec in recommendations:
            product = rec.product
            
            # Perform compliance checks
            checks = []
            
            # 1. Age check
            age_check = _check_age_eligibility(
                user_age=user_profile.age,
                product_min_age=product.age_range.min_age,
                product_max_age=product.age_range.max_age,
            )
            checks.append(age_check)
            
            # 2. Occupation check
            occupation_restrictions = getattr(product, 'occupation_restrictions', [])
            occupation_check = _check_occupation_eligibility(
                user_occupation=user_profile.occupation,
                product_occupation_restrictions=occupation_restrictions,
            )
            checks.append(occupation_check)
            
            # 3. Health check
            health_requirements = getattr(product, 'health_requirements', [])
            health_check = _check_health_eligibility(
                user_health_status=user_profile.health_status,
                product_health_requirements=health_requirements,
            )
            checks.append(health_check)
            
            # 4. Region check
            region_restrictions = getattr(product, 'region_restrictions', [])
            region_check = _check_region_eligibility(
                user_city=user_profile.city,
                user_province=user_profile.province,
                product_region_restrictions=region_restrictions,
            )
            checks.append(region_check)
            
            # Determine overall result for this product
            overall_result = _determine_overall_result(checks)
            
            # Update recommendation with compliance info
            rec.compliance_passed = overall_result in [CheckResult.PASSED, CheckResult.WARNING]
            rec.compliance_issues = [
                check.reason for check in checks
                if check.check_result in [CheckResult.FAILED, CheckResult.WARNING]
                if check.reason
            ]
            
            # Store checks
            all_compliance_checks.extend(checks)
            
            logger.debug(
                f"Product {product.product_id}: compliance_passed={rec.compliance_passed}, "
                f"overall_result={overall_result.value}"
            )
        
        # Determine overall compliance
        # If at least one product passes, we can proceed
        any_passed = any(rec.compliance_passed for rec in recommendations)
        
        logger.info(
            f"Eligibility check complete: {sum(1 for rec in recommendations if rec.compliance_passed)}/"
            f"{len(recommendations)} products passed"
        )
        
        return {
            "compliance_checks": all_compliance_checks,
            "compliance_passed": any_passed,
            "error": None,
        }
        
    except Exception as e:
        logger.error(f"Error in check_eligibility_node: {e}")
        return {
            "error": f"合规检查失败: {str(e)}",
            "compliance_passed": False,
        }


async def generate_disclosure_node(state: ComplianceState) -> Dict[str, Any]:
    """
    Generate disclosure information for each recommended product
    
    This node:
    1. Creates disclosure content for each product
    2. Formats disclosure in user-friendly language
    3. Prepares mandatory disclosure items
    
    Args:
        state: Current ComplianceState
        
    Returns:
        Dict with disclosure_info
    """
    logger.info(f"Generating disclosure for user {state.get('user_id')}")
    
    try:
        recommendations = state.get("recommendations", [])
        
        if not recommendations:
            logger.warning("No recommendations to generate disclosure for")
            return {
                "disclosure_info": [],
                "error": None,
            }
        
        # Get LLM for enhanced disclosure generation
        llm = _get_llm()
        
        disclosure_list = []
        
        for rec in recommendations:
            product = rec.product
            
            # Only generate disclosure for products that passed compliance
            if not rec.compliance_passed:
                continue
            
            try:
                # Format basic disclosure content
                basic_disclosure = _format_disclosure_content(product)
                
                # Use LLM to enhance disclosure language
                prompt = DISCLOSURE_GENERATION_PROMPT.format(
                    product_info=product.model_dump_json(indent=2)
                )
                
                messages = [
                    SystemMessage(content=prompt),
                    HumanMessage(content="请生成信息披露内容"),
                ]
                
                response = await llm.ainvoke(messages)
                enhanced_content = response.content.strip()
                
                # Create disclosure items
                disclosure_items = [
                    DisclosureItem(
                        title="保险责任",
                        content=basic_disclosure["insurance_liability"],
                        is_mandatory=True,
                        category="insurance_liability",
                    ),
                    DisclosureItem(
                        title="责任免除",
                        content=basic_disclosure["liability_exclusions"],
                        is_mandatory=True,
                        category="liability_exclusions",
                    ),
                    DisclosureItem(
                        title="犹豫期",
                        content="15天犹豫期，期间可无条件退保",
                        is_mandatory=True,
                        category="cooling_off_period",
                    ),
                    DisclosureItem(
                        title="费用说明",
                        content=basic_disclosure["fee_description"],
                        is_mandatory=True,
                        category="fee_description",
                    ),
                ]
                
                # Create disclosure info
                disclosure = DisclosureInfo(
                    product_id=product.product_id,
                    insurance_liability=basic_disclosure["insurance_liability"],
                    liability_exclusions=basic_disclosure["liability_exclusions"],
                    cooling_off_period="15天犹豫期",
                    fee_description=basic_disclosure["fee_description"],
                    disclosure_items=disclosure_items,
                    user_acknowledged=False,
                )
                
                disclosure_list.append(disclosure)
                
                logger.debug(f"Generated disclosure for product {product.product_id}")
                
            except Exception as e:
                logger.warning(
                    f"Failed to generate disclosure for product {product.product_id}: {e}"
                )
                # Create basic disclosure without LLM enhancement
                basic_disclosure = _format_disclosure_content(product)
                
                disclosure = DisclosureInfo(
                    product_id=product.product_id,
                    insurance_liability=basic_disclosure["insurance_liability"],
                    liability_exclusions=basic_disclosure["liability_exclusions"],
                    cooling_off_period="15天犹豫期",
                    fee_description=basic_disclosure["fee_description"],
                    user_acknowledged=False,
                )
                
                disclosure_list.append(disclosure)
        
        logger.info(f"Generated {len(disclosure_list)} disclosure documents")
        
        return {
            "disclosure_info": disclosure_list,
            "error": None,
        }
        
    except Exception as e:
        logger.error(f"Error in generate_disclosure_node: {e}")
        return {
            "error": f"信息披露生成失败: {str(e)}",
        }


async def log_compliance_node(state: ComplianceState) -> Dict[str, Any]:
    """
    Log compliance check results for audit purposes
    
    This node:
    1. Records compliance check results to database
    2. Filters out products that didn't pass compliance
    3. Prepares final filtered recommendations
    
    Args:
        state: Current ComplianceState
        
    Returns:
        Dict with filtered_recommendations
    """
    logger.info(f"Logging compliance for session {state.get('session_id')}")
    
    try:
        session_id = state.get("session_id")
        user_id = state.get("user_id")
        recommendations = state.get("recommendations", [])
        compliance_checks = state.get("compliance_checks", [])
        disclosure_info = state.get("disclosure_info", [])
        
        # Filter recommendations to only include those that passed compliance
        filtered_recommendations = [
            rec for rec in recommendations
            if rec.compliance_passed
        ]
        
        # Re-rank filtered recommendations
        for i, rec in enumerate(filtered_recommendations, start=1):
            rec.rank = i
        
        # Log compliance check results to database
        try:
            db_session = _get_db_session()
            
            # Create compliance log entry for each product
            import uuid
            for rec in recommendations:
                log_id = f"cl-{uuid.uuid4().hex[:12]}"
                
                # Determine overall check result for this product
                product_checks = [
                    check for check in compliance_checks
                    # We need to associate checks with products
                    # For now, we'll log a summary
                ]
                
                log_entry = ComplianceLog(
                    log_id=log_id,
                    session_id=session_id,
                    product_id=rec.product.product_id,
                    user_id=user_id,
                    check_type="comprehensive",
                    check_result=CheckResultEnum.PASSED if rec.compliance_passed else CheckResultEnum.FAILED,
                    eligible=rec.compliance_passed,
                    check_description=f"综合合规检查 - {rec.product.product_name}",
                    reason="; ".join(rec.compliance_issues) if rec.compliance_issues else None,
                    checks_detail=[
                        {
                            "check_type": check.check_type.value,
                            "check_result": check.check_result.value,
                            "check_description": check.check_description,
                            "reason": check.reason,
                        }
                        for check in compliance_checks
                    ],
                    failed_checks=rec.compliance_issues,
                    recommendations=[],
                    checked_at=datetime.now(),
                )
                
                db_session.add(log_entry)
            
            db_session.commit()
            
            logger.info(f"Logged compliance check results for session {session_id}")
            
        except Exception as e:
            logger.warning(f"Failed to log compliance to database: {e}")
            # Don't fail the entire flow if logging fails
            # Continue with filtered recommendations
        
        logger.info(
            f"Compliance processing complete: {len(filtered_recommendations)}/"
            f"{len(recommendations)} products passed compliance checks"
        )
        
        return {
            "filtered_recommendations": filtered_recommendations,
            "error": None,
        }
        
    except Exception as e:
        logger.error(f"Error in log_compliance_node: {e}")
        return {
            "error": f"合规日志记录失败: {str(e)}",
        }


# ==================== Routing Functions ====================

def should_generate_disclosure(state: ComplianceState) -> str:
    """
    Determine if we should generate disclosure or end
    
    Args:
        state: Current ComplianceState
        
    Returns:
        Next node name or END
    """
    # Check for errors
    if state.get("error"):
        logger.warning(f"Error in state: {state.get('error')}")
        return END
    
    # Check if any products passed compliance
    compliance_passed = state.get("compliance_passed", False)
    if not compliance_passed:
        logger.warning("No products passed compliance checks")
        return END
    
    # Proceed to generate disclosure
    return "generate_disclosure"


def should_log_compliance(state: ComplianceState) -> str:
    """
    Determine if we should log compliance or end
    
    Args:
        state: Current ComplianceState
        
    Returns:
        Next node name or END
    """
    # Check for errors
    if state.get("error"):
        logger.warning(f"Error in state: {state.get('error')}")
        return END
    
    # Always log compliance if we have checks
    compliance_checks = state.get("compliance_checks", [])
    if compliance_checks:
        return "log_compliance"
    
    return END


# ==================== Subgraph Builder ====================

def create_compliance_subgraph(store=None) -> StateGraph:
    """
    Create the Compliance Subgraph
    
    The subgraph follows this flow:
    START → check_eligibility → generate_disclosure → log_compliance → END
    
    Args:
        store: Optional PostgresStore instance (for dependency injection)
        
    Returns:
        Compiled StateGraph for Compliance Subgraph
    """
    logger.info("Creating Compliance Subgraph")
    
    # Create the graph with ComplianceState
    builder = StateGraph(ComplianceState)
    
    # Add nodes
    builder.add_node("check_eligibility", check_eligibility_node)
    builder.add_node("generate_disclosure", generate_disclosure_node)
    builder.add_node("log_compliance", log_compliance_node)
    
    # Add edges
    builder.add_edge(START, "check_eligibility")
    
    # Add conditional edge from check_eligibility
    builder.add_conditional_edges(
        "check_eligibility",
        should_generate_disclosure,
        {
            "generate_disclosure": "generate_disclosure",
            END: END,
        }
    )
    
    # Add conditional edge from generate_disclosure
    builder.add_conditional_edges(
        "generate_disclosure",
        should_log_compliance,
        {
            "log_compliance": "log_compliance",
            END: END,
        }
    )
    
    builder.add_edge("log_compliance", END)
    
    # Compile the graph
    graph = builder.compile()
    
    logger.info("Compliance Subgraph created successfully")
    
    return graph


# ==================== Convenience Functions ====================

async def run_compliance_subgraph(
    session_id: str,
    user_id: str,
    user_profile: UserProfile,
    recommendations: List[RecommendationResult],
    store=None
) -> ComplianceState:
    """
    Convenience function to run the Compliance Subgraph
    
    Args:
        session_id: Session identifier
        user_id: User identifier
        user_profile: User profile
        recommendations: List of recommendations to check
        store: PostgresStore instance (optional)
        
    Returns:
        Final ComplianceState after subgraph execution
    """
    # Create initial state
    initial_state = ComplianceState(
        user_id=user_id,
        session_id=session_id,
        user_profile=user_profile,
        recommendations=recommendations,
        compliance_checks=[],
        compliance_passed=False,
        disclosure_info=[],
        filtered_recommendations=[],
        error=None,
    )
    
    # Create and run subgraph
    subgraph = create_compliance_subgraph(store)
    result = await subgraph.ainvoke(initial_state)
    
    return result


# ==================== Module Exports ====================

__all__ = [
    "create_compliance_subgraph",
    "run_compliance_subgraph",
    "check_eligibility_node",
    "generate_disclosure_node",
    "log_compliance_node",
    "COMPLIANCE_CHECK_TYPES",
    "HIGH_RISK_OCCUPATIONS",
]
