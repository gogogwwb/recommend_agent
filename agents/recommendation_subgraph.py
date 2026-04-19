"""
Recommendation Subgraph - LangGraph 1.0.0 Implementation

This module implements the Recommendation Subgraph for the insurance recommendation system.
The subgraph is responsible for generating personalized insurance product recommendations
based on user profile data.

Key Features:
- Load user profile from Store API (cross-session persistence)
- Match products using FAISS vector similarity search
- Generate personalized recommendations (3-5 products)
- Create explainable recommendation reasons
- Analyze coverage gaps
- Ensure recommendation diversity

Architecture:
- Uses RecommendationState (TypedDict) for state management
- Integrates with Store API for user profile retrieval
- Uses FAISS for vector-based product retrieval
- Follows LangGraph 1.0.0 subgraph pattern with StateGraph

Requirements: 7.1, 7.2, 7.3, 7.4, 8.1, 18.1
"""
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime

from langgraph.graph import StateGraph, START, END
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langchain_openai import ChatOpenAI
import numpy as np

from models.subgraph_states import RecommendationState
from models.user import UserProfile, RiskPreference, IncomeRange
from models.product import Product, RecommendationResult, CoverageGap, PremiumRange, AgeRange
from utils.store_manager import get_store_manager, StoreError
from utils.faiss_index import get_faiss_index_manager, FAISSIndexError

logger = logging.getLogger(__name__)


# ==================== Constants ====================

# Number of recommendations to generate
MIN_RECOMMENDATIONS = 3
MAX_RECOMMENDATIONS = 5

# Product types
PRODUCT_TYPES = [
    "critical_illness",  # 重疾险
    "medical",           # 医疗险
    "accident",          # 意外险
    "life",              # 寿险
]

# Product type priorities based on user profile
PRODUCT_TYPE_PRIORITIES = {
    "young_single": ["medical", "accident", "critical_illness"],
    "young_married": ["critical_illness", "medical", "life", "accident"],
    "middle_aged_parent": ["critical_illness", "life", "medical", "accident"],
    "senior": ["medical", "critical_illness", "accident"],
}

# Match score weights for different dimensions
MATCH_WEIGHTS = {
    "age_match": 0.25,
    "income_match": 0.25,
    "risk_match": 0.20,
    "family_match": 0.15,
    "coverage_match": 0.15,
}

# System prompt for explanation generation
EXPLANATION_GENERATION_PROMPT = """你是一个保险推荐系统的推荐解释生成助手。

用户画像：
{user_profile}

推荐产品：
{product_info}

请为这个推荐生成一个简洁、易懂的推荐理由（不超过100字），说明：
1. 为什么这个产品适合用户
2. 产品的主要优势
3. 如何满足用户的需求

请用自然、友好的语言，避免专业术语堆砌。
"""


# ==================== Helper Functions ====================

def _get_llm():
    """Get LLM instance for explanation generation"""
    from config import get_settings
    settings = get_settings()
    
    return ChatOpenAI(
        model=settings.LLM_MODEL,
        temperature=settings.LLM_TEMPERATURE,
        max_tokens=settings.LLM_MAX_TOKENS,
        api_key=settings.OPENAI_API_KEY,
        base_url=settings.OPENAI_API_BASE,
    )


def _infer_product_types(profile: UserProfile) -> List[str]:
    """
    Infer product types based on user profile
    
    Args:
        profile: User profile
        
    Returns:
        List of product types in priority order
    """
    age = profile.age
    marital_status = profile.marital_status.value
    has_children = profile.has_children
    
    # Determine life stage
    if age < 30:
        if marital_status == "single":
            stage = "young_single"
        else:
            stage = "young_married"
    elif age < 50:
        if has_children:
            stage = "middle_aged_parent"
        else:
            stage = "young_married"
    else:
        stage = "senior"
    
    return PRODUCT_TYPE_PRIORITIES.get(stage, PRODUCT_TYPES)


def _calculate_affordable_premium_range(income_range: IncomeRange) -> Dict[str, float]:
    """
    Calculate affordable premium range based on income
    
    Args:
        income_range: User's income range
        
    Returns:
        Dict with min and max affordable premium
    """
    # Premium should be 5-15% of annual income
    income_ranges = {
        "low": (30000, 50000),           # 3-5万
        "medium_low": (50000, 100000),   # 5-10万
        "medium": (100000, 200000),      # 10-20万
        "medium_high": (200000, 500000), # 20-50万
        "high": (500000, 1000000),       # 50-100万
    }
    
    min_income, max_income = income_ranges.get(income_range.value, (50000, 100000))
    
    # 5-15% of income for insurance
    min_premium = min_income * 0.05
    max_premium = max_income * 0.15
    
    return {
        "min_premium": min_premium,
        "max_premium": max_premium
    }


def _calculate_age_match_score(user_age: int, product_min_age: int, product_max_age: int) -> float:
    """Calculate age match score (0-100)"""
    if product_min_age <= user_age <= product_max_age:
        # Perfect match
        return 100.0
    elif user_age < product_min_age:
        # Too young
        gap = product_min_age - user_age
        return max(0, 100 - gap * 10)
    else:
        # Too old
        gap = user_age - product_max_age
        return max(0, 100 - gap * 10)


def _calculate_income_match_score(
    user_income_range: IncomeRange,
    product_min_premium: float,
    product_max_premium: float
) -> float:
    """Calculate income match score (0-100)"""
    affordable = _calculate_affordable_premium_range(user_income_range)
    
    # Check if product premium is within affordable range
    if product_min_premium <= affordable["max_premium"] and product_max_premium >= affordable["min_premium"]:
        # Good match
        overlap_min = max(product_min_premium, affordable["min_premium"])
        overlap_max = min(product_max_premium, affordable["max_premium"])
        overlap_ratio = (overlap_max - overlap_min) / (product_max_premium - product_min_premium)
        return 80 + overlap_ratio * 20
    elif product_max_premium < affordable["min_premium"]:
        # Product too cheap (might not provide enough coverage)
        return 60.0
    else:
        # Product too expensive
        return 40.0


def _calculate_risk_match_score(user_risk: Optional[RiskPreference], product_type: str) -> float:
    """Calculate risk preference match score (0-100)"""
    if not user_risk:
        return 70.0  # Default score if no risk preference
    
    # Risk preference to product type mapping
    risk_product_match = {
        "conservative": {
            "medical": 95,
            "critical_illness": 90,
            "accident": 85,
            "life": 80,
        },
        "balanced": {
            "critical_illness": 95,
            "medical": 90,
            "life": 85,
            "accident": 80,
        },
        "aggressive": {
            "life": 95,
            "critical_illness": 85,
            "accident": 75,
            "medical": 70,
        },
    }
    
    return risk_product_match.get(user_risk.value, {}).get(product_type, 70.0)


def _calculate_family_match_score(profile: UserProfile, product_type: str) -> float:
    """Calculate family structure match score (0-100)"""
    score = 70.0  # Base score
    
    # Has dependents - life insurance becomes more important
    if profile.has_dependents or profile.has_children:
        if product_type == "life":
            score = 95.0
        elif product_type == "critical_illness":
            score = 90.0
        elif product_type == "medical":
            score = 85.0
    
    # Married - family protection products
    if profile.marital_status.value == "married":
        if product_type in ["critical_illness", "life"]:
            score = max(score, 90.0)
    
    # Single - personal protection
    if profile.marital_status.value == "single":
        if product_type in ["medical", "accident"]:
            score = max(score, 85.0)
    
    return score


def _calculate_coverage_match_score(
    existing_coverage: List[Dict[str, Any]],
    product_type: str
) -> float:
    """Calculate coverage gap match score (0-100)"""
    # Check if user already has this type of coverage
    has_coverage = any(
        cov.get("product_type") == product_type and cov.get("is_active", True)
        for cov in existing_coverage
    )
    
    if has_coverage:
        # Already has this type - lower priority
        return 50.0
    else:
        # Doesn't have this type - higher priority
        return 95.0


def _calculate_overall_match_score(
    profile: UserProfile,
    product: Product,
    existing_coverage: List[Dict[str, Any]]
) -> Dict[str, float]:
    """
    Calculate overall match score and dimension scores
    
    Args:
        profile: User profile
        product: Product to match
        existing_coverage: User's existing coverage
        
    Returns:
        Dict with overall score and dimension scores
    """
    # Calculate dimension scores
    age_score = _calculate_age_match_score(
        profile.age,
        product.age_range.min_age,
        product.age_range.max_age
    )
    
    income_score = _calculate_income_match_score(
        profile.income_range,
        product.premium_range.min_premium,
        product.premium_range.max_premium
    )
    
    risk_score = _calculate_risk_match_score(
        profile.risk_preference,
        product.product_type
    )
    
    family_score = _calculate_family_match_score(
        profile,
        product.product_type
    )
    
    coverage_score = _calculate_coverage_match_score(
        existing_coverage,
        product.product_type
    )
    
    # Calculate weighted overall score
    overall_score = (
        age_score * MATCH_WEIGHTS["age_match"] +
        income_score * MATCH_WEIGHTS["income_match"] +
        risk_score * MATCH_WEIGHTS["risk_match"] +
        family_score * MATCH_WEIGHTS["family_match"] +
        coverage_score * MATCH_WEIGHTS["coverage_match"]
    )
    
    return {
        "overall": overall_score,
        "age_match": age_score,
        "income_match": income_score,
        "risk_match": risk_score,
        "family_match": family_score,
        "coverage_match": coverage_score,
    }


def _ensure_diversity(
    recommendations: List[RecommendationResult],
    max_recommendations: int = MAX_RECOMMENDATIONS
) -> List[RecommendationResult]:
    """
    Ensure recommendation diversity by product type
    
    Args:
        recommendations: List of recommendations
        max_recommendations: Maximum number of recommendations
        
    Returns:
        Diversified list of recommendations
    """
    if len(recommendations) <= max_recommendations:
        return recommendations
    
    # Group by product type
    by_type: Dict[str, List[RecommendationResult]] = {}
    for rec in recommendations:
        ptype = rec.product.product_type
        if ptype not in by_type:
            by_type[ptype] = []
        by_type[ptype].append(rec)
    
    # Select top recommendations ensuring diversity
    diversified = []
    type_indices = {ptype: 0 for ptype in by_type}
    
    # Round-robin selection from each type
    while len(diversified) < max_recommendations:
        added = False
        for ptype in PRODUCT_TYPES:
            if ptype in by_type and type_indices[ptype] < len(by_type[ptype]):
                diversified.append(by_type[ptype][type_indices[ptype]])
                type_indices[ptype] += 1
                added = True
                if len(diversified) >= max_recommendations:
                    break
        
        if not added:
            # No more products to add
            break
    
    # Sort by match score
    diversified.sort(key=lambda x: x.match_score, reverse=True)
    
    return diversified


# ==================== Node Functions ====================

async def load_profile_node(state: RecommendationState) -> Dict[str, Any]:
    """
    Load user profile from Store API
    
    This node:
    1. Retrieves user profile from Store API (namespace: users/{user_id})
    2. Validates profile completeness
    3. Returns profile data for recommendation generation
    
    Args:
        state: Current RecommendationState
        
    Returns:
        Dict with user_profile and other fields
    """
    logger.info(f"Loading profile for user {state.get('user_id')}")
    
    try:
        user_id = state.get("user_id")
        
        if not user_id:
            logger.error("No user_id in state")
            return {
                "error": "缺少用户ID",
                "recommendation_generated": False
            }
        
        # Check if profile is already in state
        if state.get("user_profile"):
            logger.debug("Profile already in state, using existing profile")
            return {"error": None}
        
        # Get store manager
        store_manager = get_store_manager()
        
        # Load profile from Store API
        profile_data = store_manager.get_user_profile(user_id)
        
        if not profile_data:
            logger.error(f"No profile found for user {user_id}")
            return {
                "error": "未找到用户画像，请先完成信息收集",
                "recommendation_generated": False
            }
        
        # Convert to UserProfile model
        try:
            user_profile = UserProfile(**profile_data)
            logger.info(f"Successfully loaded profile for user {user_id}")
            
            return {
                "user_profile": user_profile,
                "error": None
            }
            
        except Exception as e:
            logger.error(f"Failed to parse profile data: {e}")
            return {
                "error": f"用户画像数据格式错误: {str(e)}",
                "recommendation_generated": False
            }
    
    except StoreError as e:
        logger.error(f"Store API error: {e}")
        return {
            "error": f"加载用户画像失败: {str(e)}",
            "recommendation_generated": False
        }
    
    except Exception as e:
        logger.error(f"Error in load_profile_node: {e}")
        return {
            "error": f"加载用户画像失败: {str(e)}",
            "recommendation_generated": False
        }


async def match_products_node(state: RecommendationState) -> Dict[str, Any]:
    """
    Match products based on user profile
    
    This node:
    1. Uses FAISS to retrieve candidate products
    2. Calculates match scores for each product
    3. Ranks and filters products
    4. Ensures recommendation diversity
    
    Args:
        state: Current RecommendationState
        
    Returns:
        Dict with recommendations and coverage_gap
    """
    logger.info(f"Matching products for user {state.get('user_id')}")
    
    try:
        user_profile = state.get("user_profile")
        existing_coverage = state.get("existing_coverage", [])
        excluded_products = state.get("excluded_products", [])
        
        if not user_profile:
            logger.error("No user_profile in state")
            return {
                "error": "缺少用户画像",
                "recommendation_generated": False
            }
        
        # Get FAISS index manager
        faiss_manager = get_faiss_index_manager()
        
        # Check if index has products
        if faiss_manager.get_total_products() == 0:
            logger.warning("FAISS index is empty, no products to recommend")
            return {
                "error": "产品库为空，无法生成推荐",
                "recommendation_generated": False
            }
        
        # Infer product types based on profile
        product_types = _infer_product_types(user_profile)
        logger.debug(f"Inferred product types: {product_types}")
        
        # Calculate affordable premium range
        affordable_range = _calculate_affordable_premium_range(user_profile.income_range)
        
        # TODO: In a real implementation, we would:
        # 1. Query database for products matching criteria
        # 2. Use FAISS for vector similarity search
        # 3. Combine both results
        
        # For now, we'll create placeholder products for demonstration
        # In production, this would query the database
        candidate_products = _get_sample_products()
        
        # Filter by excluded products
        candidate_products = [
            p for p in candidate_products
            if p.product_id not in excluded_products
        ]
        
        # Calculate match scores for each product
        scored_products = []
        for product in candidate_products:
            scores = _calculate_overall_match_score(
                user_profile,
                product,
                existing_coverage
            )
            
            # Only include products with reasonable match score
            if scores["overall"] >= 50.0:
                scored_products.append((product, scores))
        
        # Sort by overall score
        scored_products.sort(key=lambda x: x[1]["overall"], reverse=True)
        
        # Create recommendation results
        recommendations = []
        for rank, (product, scores) in enumerate(scored_products[:MAX_RECOMMENDATIONS * 2], start=1):
            rec = RecommendationResult(
                product=product,
                rank=rank,
                match_score=scores["overall"],
                confidence_score=min(scores["overall"] / 100.0, 1.0),
                explanation="",  # Will be generated in next node
                match_dimensions={
                    k: v for k, v in scores.items()
                    if k != "overall"
                },
                why_suitable=[],
                key_benefits=product.advantages[:3] if product.advantages else [],
                compliance_passed=False,  # Will be checked by Compliance Subgraph
                compliance_issues=[],
            )
            recommendations.append(rec)
        
        # Ensure diversity
        recommendations = _ensure_diversity(recommendations, MAX_RECOMMENDATIONS)
        
        # Re-rank after diversity adjustment
        for i, rec in enumerate(recommendations, start=1):
            rec.rank = i
        
        # Analyze coverage gap
        coverage_gap = _analyze_coverage_gap(user_profile, existing_coverage)
        
        logger.info(
            f"Generated {len(recommendations)} recommendations for user {state.get('user_id')}"
        )
        
        return {
            "recommendations": recommendations,
            "coverage_gap": coverage_gap,
            "error": None
        }
    
    except FAISSIndexError as e:
        logger.error(f"FAISS index error: {e}")
        return {
            "error": f"产品检索失败: {str(e)}",
            "recommendation_generated": False
        }
    
    except Exception as e:
        logger.error(f"Error in match_products_node: {e}")
        return {
            "error": f"产品匹配失败: {str(e)}",
            "recommendation_generated": False
        }


async def generate_explanations_node(state: RecommendationState) -> Dict[str, Any]:
    """
    Generate explanations for recommendations
    
    This node:
    1. Uses LLM to generate personalized explanations
    2. Creates why_suitable and key_benefits for each recommendation
    3. Ensures explanations are user-friendly
    
    Args:
        state: Current RecommendationState
        
    Returns:
        Dict with updated recommendations and explanations list
    """
    logger.info(f"Generating explanations for user {state.get('user_id')}")
    
    try:
        user_profile = state.get("user_profile")
        recommendations = state.get("recommendations", [])
        
        if not recommendations:
            logger.warning("No recommendations to explain")
            return {
                "explanations": [],
                "recommendation_generated": True,
                "error": None
            }
        
        # Get LLM instance
        llm = _get_llm()
        
        # Generate explanation for each recommendation
        explanations = []
        for rec in recommendations:
            try:
                # Prepare prompt
                prompt = EXPLANATION_GENERATION_PROMPT.format(
                    user_profile=user_profile.model_dump_json(indent=2),
                    product_info=rec.product.model_dump_json(indent=2)
                )
                
                # Call LLM
                messages = [
                    SystemMessage(content=prompt),
                    HumanMessage(content="请生成推荐理由")
                ]
                
                response = await llm.ainvoke(messages)
                explanation = response.content.strip()
                
                # Update recommendation
                rec.explanation = explanation
                
                # Generate why_suitable based on match dimensions
                why_suitable = _generate_why_suitable(rec.match_dimensions, rec.product)
                rec.why_suitable = why_suitable
                
                explanations.append(explanation)
                
                logger.debug(f"Generated explanation for product {rec.product.product_id}")
                
            except Exception as e:
                logger.warning(f"Failed to generate explanation for product {rec.product.product_id}: {e}")
                # Use fallback explanation
                fallback = _generate_fallback_explanation(rec)
                rec.explanation = fallback
                explanations.append(fallback)
        
        logger.info(f"Generated {len(explanations)} explanations")
        
        return {
            "recommendations": recommendations,
            "explanations": explanations,
            "recommendation_generated": True,
            "error": None
        }
    
    except Exception as e:
        logger.error(f"Error in generate_explanations_node: {e}")
        return {
            "error": f"推荐解释生成失败: {str(e)}",
            "recommendation_generated": False
        }


# ==================== Helper Functions for Explanations ====================

def _generate_why_suitable(match_dimensions: Dict[str, float], product: Product) -> List[str]:
    """Generate why_suitable list based on match dimensions"""
    reasons = []
    
    if match_dimensions.get("age_match", 0) >= 80:
        reasons.append(f"适合{product.age_range.min_age}-{product.age_range.max_age}岁人群投保")
    
    if match_dimensions.get("income_match", 0) >= 80:
        reasons.append("保费在您的预算范围内")
    
    if match_dimensions.get("risk_match", 0) >= 80:
        reasons.append("符合您的风险偏好")
    
    if match_dimensions.get("family_match", 0) >= 80:
        reasons.append("适合您的家庭结构")
    
    if match_dimensions.get("coverage_match", 0) >= 80:
        reasons.append("填补您的保障缺口")
    
    # Add product features if available
    if product.features:
        reasons.extend(product.features[:2])
    
    return reasons[:5]  # Limit to 5 reasons


def _generate_fallback_explanation(rec: RecommendationResult) -> str:
    """Generate fallback explanation without LLM"""
    product = rec.product
    score = rec.match_score
    
    if score >= 85:
        quality = "非常适合"
    elif score >= 70:
        quality = "比较适合"
    else:
        quality = "可以考虑"
    
    return f"{product.product_name}{quality}您的需求，匹配度{score:.0f}分。{product.provider}出品，保障范围全面。"


def _analyze_coverage_gap(
    profile: UserProfile,
    existing_coverage: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """
    Analyze coverage gap based on user profile and existing coverage
    
    Args:
        profile: User profile
        existing_coverage: User's existing coverage
        
    Returns:
        Coverage gap analysis dict
    """
    # Calculate current coverage by type
    current_coverage = {
        "critical_illness": 0.0,
        "medical": 0.0,
        "accident": 0.0,
        "life": 0.0,
    }
    
    for cov in existing_coverage:
        ptype = cov.get("product_type")
        amount = cov.get("coverage_amount", 0)
        if ptype in current_coverage and cov.get("is_active", True):
            current_coverage[ptype] += amount
    
    # Calculate recommended coverage based on profile
    # These are simplified rules - real implementation would be more sophisticated
    annual_income = profile.annual_income or 100000  # Default if not specified
    
    recommended = {
        "critical_illness": annual_income * 5,  # 5x annual income
        "medical": 500000,  # 500k medical coverage
        "accident": annual_income * 10,  # 10x annual income
        "life": annual_income * 10 if (profile.has_dependents or profile.has_children) else 0,
    }
    
    # Calculate gaps
    gaps = {
        ptype: max(0, recommended[ptype] - current_coverage[ptype])
        for ptype in PRODUCT_TYPES
    }
    
    # Determine priority recommendations
    priority = sorted(
        [ptype for ptype in PRODUCT_TYPES if gaps[ptype] > 0],
        key=lambda x: gaps[x],
        reverse=True
    )
    
    return {
        "current_coverage": current_coverage,
        "recommended_coverage": recommended,
        "gaps": gaps,
        "priority_recommendations": priority[:2],
        "analysis": _generate_gap_analysis_text(gaps, profile),
    }


def _generate_gap_analysis_text(gaps: Dict[str, float], profile: UserProfile) -> str:
    """Generate gap analysis text"""
    texts = []
    
    if gaps["critical_illness"] > 0:
        texts.append(f"重疾险保障缺口{gaps['critical_illness']/10000:.0f}万元")
    
    if gaps["medical"] > 0:
        texts.append(f"医疗险保障缺口{gaps['medical']/10000:.0f}万元")
    
    if gaps["accident"] > 0:
        texts.append(f"意外险保障缺口{gaps['accident']/10000:.0f}万元")
    
    if gaps["life"] > 0 and (profile.has_dependents or profile.has_children):
        texts.append(f"寿险保障缺口{gaps['life']/10000:.0f}万元")
    
    if texts:
        return "您当前的保障情况：" + "，".join(texts) + "。建议优先补充缺口较大的保障类型。"
    else:
        return "您当前的保障较为完善，建议根据实际情况优化保障组合。"


def _get_sample_products() -> List[Product]:
    """
    Get sample products for demonstration
    
    In production, this would query the database
    """
    return [
        Product(
            product_id="prod-ci-001",
            product_name="康健一生重大疾病保险",
            product_type="critical_illness",
            provider="平安保险",
            coverage_scope=["重大疾病", "轻症", "中症", "身故"],
            premium_range=PremiumRange(min_premium=5000, max_premium=15000),
            age_range=AgeRange(min_age=18, max_age=60),
            payment_period=["20年", "30年"],
            coverage_period=["终身"],
            features=["120种重疾保障", "轻症中症多次赔付", "身故保障"],
            advantages=["保障全面", "性价比高", "品牌信誉好"],
            suitable_for=["家庭支柱", "有家庭责任的人群"],
            is_available=True,
        ),
        Product(
            product_id="prod-med-001",
            product_name="百万医疗险",
            product_type="medical",
            provider="中国人寿",
            coverage_scope=["住院医疗", "门诊手术", "特殊门诊"],
            premium_range=PremiumRange(min_premium=500, max_premium=2000),
            age_range=AgeRange(min_age=0, max_age=65),
            payment_period=["1年"],
            coverage_period=["1年"],
            features=["最高600万保额", "0免赔", "质子重离子治疗"],
            advantages=["保额高", "覆盖广", "理赔快"],
            suitable_for=["所有人群"],
            is_available=True,
        ),
        Product(
            product_id="prod-acc-001",
            product_name="综合意外险",
            product_type="accident",
            provider="太平洋保险",
            coverage_scope=["意外身故", "意外伤残", "意外医疗"],
            premium_range=PremiumRange(min_premium=100, max_premium=500),
            age_range=AgeRange(min_age=18, max_age=65),
            payment_period=["1年"],
            coverage_period=["1年"],
            features=["100万意外身故", "10万意外医疗", "猝死保障"],
            advantages=["保费低", "保障高", "投保简便"],
            suitable_for=["上班族", "经常出行人群"],
            is_available=True,
        ),
        Product(
            product_id="prod-life-001",
            product_name="定期寿险",
            product_type="life",
            provider="泰康保险",
            coverage_scope=["身故", "全残"],
            premium_range=PremiumRange(min_premium=1000, max_premium=5000),
            age_range=AgeRange(min_age=18, max_age=60),
            payment_period=["20年", "30年"],
            coverage_period=["至70岁", "终身"],
            features=["高额身故保障", "全残保障", "免体检"],
            advantages=["保费便宜", "保障期限灵活", "健康告知宽松"],
            suitable_for=["家庭经济支柱", "有房贷车贷人群"],
            is_available=True,
        ),
    ]


# ==================== Routing Functions ====================

def should_generate_explanations(state: RecommendationState) -> str:
    """
    Determine if we should generate explanations or end
    
    Args:
        state: Current RecommendationState
        
    Returns:
        Next node name or END
    """
    # Check for errors
    if state.get("error"):
        logger.warning(f"Error in state: {state.get('error')}")
        return END
    
    # Check if we have recommendations
    recommendations = state.get("recommendations", [])
    if not recommendations:
        logger.warning("No recommendations generated")
        return END
    
    # Proceed to generate explanations
    return "generate_explanations"


# ==================== Subgraph Builder ====================

def create_recommendation_subgraph(store=None) -> StateGraph:
    """
    Create the Recommendation Subgraph
    
    The subgraph follows this flow:
    START → load_profile → match_products → generate_explanations → END
    
    Args:
        store: Optional PostgresStore instance (for dependency injection)
        
    Returns:
        Compiled StateGraph for Recommendation Subgraph
    """
    logger.info("Creating Recommendation Subgraph")
    
    # Create the graph with RecommendationState
    builder = StateGraph(RecommendationState)
    
    # Add nodes
    builder.add_node("load_profile", load_profile_node)
    builder.add_node("match_products", match_products_node)
    builder.add_node("generate_explanations", generate_explanations_node)
    
    # Add edges
    builder.add_edge(START, "load_profile")
    builder.add_edge("load_profile", "match_products")
    
    # Add conditional edge from match_products
    builder.add_conditional_edges(
        "match_products",
        should_generate_explanations,
        {
            "generate_explanations": "generate_explanations",
            END: END
        }
    )
    
    builder.add_edge("generate_explanations", END)
    
    # Compile the graph
    graph = builder.compile()
    
    logger.info("Recommendation Subgraph created successfully")
    
    return graph


# ==================== Convenience Functions ====================

async def run_recommendation_subgraph(
    session_id: str,
    user_id: str,
    user_profile: Optional[UserProfile] = None,
    existing_coverage: Optional[List[Dict[str, Any]]] = None,
    excluded_products: Optional[List[str]] = None,
    store=None
) -> RecommendationState:
    """
    Convenience function to run the Recommendation Subgraph
    
    Args:
        session_id: Session identifier
        user_id: User identifier
        user_profile: User profile (optional, will load from Store API if not provided)
        existing_coverage: User's existing coverage (optional)
        excluded_products: Product IDs to exclude (optional)
        store: PostgresStore instance (optional)
        
    Returns:
        Final RecommendationState after subgraph execution
    """
    # Create initial state
    initial_state = RecommendationState(
        user_id=user_id,
        session_id=session_id,
        user_profile=user_profile,
        risk_preference=user_profile.risk_preference.value if user_profile and user_profile.risk_preference else None,
        risk_score=user_profile.risk_score if user_profile else None,
        existing_coverage=existing_coverage or [],
        recommendations=[],
        explanations=[],
        coverage_gap=None,
        recommendation_constraints=None,
        excluded_products=excluded_products or [],
        recommendation_generated=False,
        error=None
    )
    
    # Create and run subgraph
    subgraph = create_recommendation_subgraph(store)
    result = await subgraph.ainvoke(initial_state)
    
    return result


# ==================== Module Exports ====================

__all__ = [
    "create_recommendation_subgraph",
    "run_recommendation_subgraph",
    "load_profile_node",
    "match_products_node",
    "generate_explanations_node",
    "MIN_RECOMMENDATIONS",
    "MAX_RECOMMENDATIONS",
    "PRODUCT_TYPES",
]
