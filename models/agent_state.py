"""LangGraph Agent状态模型"""
from typing import List, Dict, Any, Optional
from typing_extensions import TypedDict
from models.user import UserProfile, RiskPreference, ExistingProduct
from models.product import Product, RecommendationResult, CoverageGap
from models.conversation import Message, IntentType
from models.compliance import ComplianceCheck, DisclosureItem


class AgentState(TypedDict, total=False):
    """
    LangGraph Agent状态模型
    
    这是LangGraph状态图中所有Agent共享的状态对象。
    每个Agent读取State中的相关字段，更新自己负责的字段。
    
    使用TypedDict而非Pydantic BaseModel，因为LangGraph要求使用TypedDict。
    total=False表示所有字段都是可选的。
    """
    
    # ==================== 对话管理 ====================
    session_id: str  # 会话ID
    user_id: Optional[str]  # 用户ID
    messages: List[Message]  # 对话消息列表
    turn_count: int  # 对话轮数
    
    # ==================== 用户画像 ====================
    profile: Optional[UserProfile]  # 用户画像
    profile_complete: bool  # 用户画像是否收集完整
    risk_preference: Optional[RiskPreference]  # 风险偏好
    risk_score: Optional[float]  # 风险评分
    existing_coverage: List[ExistingProduct]  # 已有保障
    
    # ==================== 推荐相关 ====================
    recommendation_candidates: List[Product]  # 候选推荐产品
    recommendation_results: List[RecommendationResult]  # 推荐结果
    recommendation_generated: bool  # 是否已生成推荐
    coverage_gap: Optional[CoverageGap]  # 保障缺口分析
    
    # ==================== 合规相关 ====================
    compliance_checks: List[ComplianceCheck]  # 合规检查列表
    compliance_passed: bool  # 是否通过合规检查
    disclosure_info: List[DisclosureItem]  # 信息披露
    
    # ==================== 意图和槽位 ====================
    current_intent: Optional[IntentType]  # 当前用户意图
    slots: Dict[str, Any]  # 槽位字典（提取的结构化信息）
    missing_slots: List[str]  # 缺失的必填槽位
    
    # ==================== 上下文管理 ====================
    full_context_prompt: Optional[str]  # 完整上下文提示（压缩历史 + 热数据）
    compressed_history: Optional[str]  # 压缩的历史对话
    user_preferences: Optional[Dict[str, Any]]  # 用户偏好（从历史学习）
    
    # ==================== 控制流 ====================
    next_agent: Optional[str]  # 下一个要执行的Agent
    current_agent: Optional[str]  # 当前正在执行的Agent
    error: Optional[str]  # 错误信息
    status: str  # 会话状态（active, completed, error）
    
    # ==================== 会话管理 ====================
    background_mode: bool  # 是否后台运行
    saved_progress: Optional[Dict[str, Any]]  # 保存的进度（用于会话切换）
    
    # ==================== 反馈和质量 ====================
    user_feedback: Optional[str]  # 用户反馈（positive, negative, neutral）
    feedback_reason: Optional[str]  # 反馈原因
    quality_score: Optional[float]  # 质量评分
    
    # ==================== 元数据 ====================
    profile_change_history: List[Dict[str, Any]]  # 用户画像变更历史
    recommendation_constraints: Optional[Dict[str, Any]]  # 推荐约束条件
    excluded_products: List[str]  # 排除的产品ID列表


# 为了方便类型检查和IDE提示，提供一个辅助函数
def create_initial_state(session_id: str, user_id: Optional[str] = None) -> AgentState:
    """
    创建初始Agent状态
    
    Args:
        session_id: 会话ID
        user_id: 用户ID（可选）
    
    Returns:
        初始化的AgentState
    """
    return AgentState(
        # 对话管理
        session_id=session_id,
        user_id=user_id,
        messages=[],
        turn_count=0,
        
        # 用户画像
        profile=None,
        profile_complete=False,
        risk_preference=None,
        risk_score=None,
        existing_coverage=[],
        
        # 推荐相关
        recommendation_candidates=[],
        recommendation_results=[],
        recommendation_generated=False,
        coverage_gap=None,
        
        # 合规相关
        compliance_checks=[],
        compliance_passed=False,
        disclosure_info=[],
        
        # 意图和槽位
        current_intent=None,
        slots={},
        missing_slots=[],
        
        # 上下文管理
        full_context_prompt=None,
        compressed_history=None,
        user_preferences=None,
        
        # 控制流
        next_agent=None,
        current_agent=None,
        error=None,
        status="active",
        
        # 会话管理
        background_mode=False,
        saved_progress=None,
        
        # 反馈和质量
        user_feedback=None,
        feedback_reason=None,
        quality_score=None,
        
        # 元数据
        profile_change_history=[],
        recommendation_constraints=None,
        excluded_products=[]
    )


# 槽位定义（用于Profile Collection Agent）
REQUIRED_SLOTS = [
    "age",
    "occupation",
    "marital_status",
    "income_range",
]

OPTIONAL_SLOTS = [
    "has_children",
    "children_count",
    "has_dependents",
    "dependents_count",
    "family_size",
    "annual_income",
    "health_status",
    "has_medical_history",
    "medical_conditions",
    "city",
    "province",
]

ALL_SLOTS = REQUIRED_SLOTS + OPTIONAL_SLOTS
