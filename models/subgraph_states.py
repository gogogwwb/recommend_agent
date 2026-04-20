"""LangGraph 1.0.0 子图State模型

本模块定义了LangGraph子图架构的State模型，用于实现Agent隔离。
每个子图拥有独立的State Schema，通过结构化隔离替代运行时过滤。

架构设计：
- ProfileState: 画像收集子图状态（需要对话历史）
- RecommendationState: 推荐子图状态（只需要结构化数据）
- ComplianceState: 合规子图状态（只需要验证数据）
- MainState: 主图状态（包含所有数据）

关键特性：
- 类型安全：编译时检查，IDE支持
- 清晰的数据流：State定义即文档
- 无运行时开销：结构上隔离
- 易于测试：每个子图可独立测试
"""
from typing import Annotated, Any, Dict, List, Optional
from typing_extensions import TypedDict

from langgraph.graph.message import add_messages

from models.user import UserProfile
from models.product import RecommendationResult
from models.compliance import ComplianceCheck, DisclosureInfo
from models.conversation import Message


# ==================== Profile Subgraph State ====================

class ProfileState(TypedDict, total=False):
    """Profile Collection子图状态
    
    职责：
    - 引导用户提供个人信息（家庭结构、年龄、职业、收入）
    - 评估用户风险偏好
    - 收集已有保障信息
    - 识别用户意图和提取槽位信息
    - 管理多轮对话流程
    - 将提取的槽位存储到Store API
    
    输入：用户消息、当前对话上下文
    输出：结构化的用户画像、风险偏好评估、已有保障分析
    
    注意：ProfileState需要对话历史（messages字段）来理解用户意图
    """
    
    # ==================== 对话管理 ====================
    messages: Annotated[List[Message], add_messages]  # 对话历史（LangGraph自动管理）
    user_id: str  # 用户ID
    session_id: str  # 会话ID
    
    # ==================== 用户画像（输出） ====================
    user_profile: Optional[UserProfile]  # 结构化用户画像
    
    # ==================== 槽位提取 ====================
    slots: Dict[str, Any]  # 提取的槽位（从对话中提取的结构化信息）
    missing_slots: List[str]  # 缺失的必填槽位
    
    # ==================== 风险偏好 ====================
    risk_preference: Optional[str]  # 风险偏好（conservative, balanced, aggressive）
    risk_score: Optional[float]  # 风险评分
    
    # ==================== 已有保障 ====================
    existing_coverage: List[Dict[str, Any]]  # 已有保障产品列表
    
    # ==================== 意图识别 ====================
    current_intent: Optional[str]  # 当前用户意图
    question_type: Optional[str]  # 问题类型（terminology, comparison, claim, general, non_insurance）
    extracted_entities: Dict[str, Any]  # 从问题中提取的实体（如术语、产品类型）
    
    # ==================== 控制流 ====================
    profile_complete: bool  # 用户画像是否收集完整
    error: Optional[str]  # 错误信息


# ==================== Recommendation Subgraph State ====================

class RecommendationState(TypedDict, total=False):
    """Recommendation子图状态
    
    职责：
    - 从Store API读取用户画像（不需要对话历史）
    - 基于用户画像匹配保险产品
    - 生成个性化推荐列表（3-5个产品）
    - 为每个推荐生成可解释的理由
    - 分析保障缺口
    - 提供产品对比功能
    - 确保推荐多样性
    
    输入：完整的用户画像（从Store API）、风险偏好、已有保障
    输出：推荐产品列表、推荐理由、保障缺口分析
    
    注意：RecommendationState不需要对话历史（无messages字段）
          只需要结构化的用户画像数据
    """
    
    # ==================== 基本信息 ====================
    user_id: str  # 用户ID
    session_id: str  # 会话ID
    
    # ==================== 用户画像（输入） ====================
    user_profile: UserProfile  # 从Store API读取的用户画像
    
    # ==================== 风险偏好 ====================
    risk_preference: Optional[str]  # 风险偏好
    risk_score: Optional[float]  # 风险评分
    
    # ==================== 已有保障 ====================
    existing_coverage: List[Dict[str, Any]]  # 已有保障产品列表
    
    # ==================== 推荐结果（输出） ====================
    recommendations: List[RecommendationResult]  # 推荐产品列表（3-5个）
    explanations: List[str]  # 推荐理由列表
    
    # ==================== 保障缺口分析 ====================
    coverage_gap: Optional[Dict[str, Any]]  # 保障缺口分析结果
    
    # ==================== 推荐约束 ====================
    recommendation_constraints: Optional[Dict[str, Any]]  # 推荐约束条件
    excluded_products: List[str]  # 排除的产品ID列表
    
    # ==================== 控制流 ====================
    recommendation_generated: bool  # 是否已生成推荐
    error: Optional[str]  # 错误信息


# ==================== Compliance Subgraph State ====================

class ComplianceState(TypedDict, total=False):
    """Compliance子图状态
    
    职责：
    - 验证用户是否符合产品投保条件
    - 检查年龄、健康状况、职业限制
    - 生成必要的信息披露内容
    - 记录合规检查结果
    - 过滤不可用产品
    
    输入：用户画像、候选推荐产品
    输出：合规检查结果、披露信息、过滤后的推荐列表
    
    注意：ComplianceState只需要验证数据（无messages字段）
          不需要对话历史
    """
    
    # ==================== 基本信息 ====================
    user_id: str  # 用户ID
    session_id: str  # 会话ID
    
    # ==================== 用户画像（输入） ====================
    user_profile: UserProfile  # 用户画像
    
    # ==================== 推荐产品（输入） ====================
    recommendations: List[RecommendationResult]  # 候选推荐产品列表
    
    # ==================== 合规检查（输出） ====================
    compliance_checks: List[ComplianceCheck]  # 合规检查列表
    compliance_passed: bool  # 是否通过合规检查
    
    # ==================== 信息披露（输出） ====================
    disclosure_info: List[DisclosureInfo]  # 信息披露内容
    
    # ==================== 过滤后的推荐 ====================
    filtered_recommendations: List[RecommendationResult]  # 过滤后的推荐列表
    
    # ==================== 控制流 ====================
    error: Optional[str]  # 错误信息


# ==================== Main Graph State ====================

class MainState(TypedDict, total=False):
    """Main Graph状态 - 包含所有数据
    
    主图作为Orchestrator，负责：
    - 接收用户输入并路由到合适的子Agent
    - 维护全局对话状态和流程控制
    - 监控子Agent执行状态和性能
    - 处理子Agent之间的冲突
    - 决策下一步执行哪个Agent或结束对话
    
    主图State包含所有子图数据，通过State转换函数与子图交互：
    - MainState → ProfileState（profile_node）
    - MainState → RecommendationState（recommendation_node）
    - MainState → ComplianceState（compliance_node）
    
    注意：MainState包含messages字段，用于维护全局对话历史
          PostgresSaver会自动管理messages的持久化
    """
    
    # ==================== 对话管理 ====================
    messages: Annotated[List[Message], add_messages]  # 对话历史（LangGraph自动管理）
    user_id: str  # 用户ID
    session_id: str  # 会话ID
    
    # ==================== 用户画像 ====================
    user_profile: Optional[UserProfile]  # 用户画像
    profile_complete: bool  # 用户画像是否收集完整
    
    # ==================== 风险偏好 ====================
    risk_preference: Optional[str]  # 风险偏好
    risk_score: Optional[float]  # 风险评分
    
    # ==================== 已有保障 ====================
    existing_coverage: List[Dict[str, Any]]  # 已有保障产品列表
    
    # ==================== 推荐相关 ====================
    recommendations: List[RecommendationResult]  # 推荐产品列表
    recommendation_generated: bool  # 是否已生成推荐
    coverage_gap: Optional[Dict[str, Any]]  # 保障缺口分析
    
    # ==================== 合规相关 ====================
    compliance_checks: List[ComplianceCheck]  # 合规检查列表
    compliance_passed: bool  # 是否通过合规检查
    disclosure_info: List[DisclosureInfo]  # 信息披露
    
    # ==================== 意图和槽位 ====================
    current_intent: Optional[str]  # 当前用户意图
    slots: Dict[str, Any]  # 槽位字典
    missing_slots: List[str]  # 缺失的必填槽位
    
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
    
    # ==================== 元数据 ====================
    profile_change_history: List[Dict[str, Any]]  # 用户画像变更历史
    recommendation_constraints: Optional[Dict[str, Any]]  # 推荐约束条件
    excluded_products: List[str]  # 排除的产品ID列表


# ==================== 辅助函数 ====================

def create_initial_main_state(session_id: str, user_id: Optional[str] = None) -> MainState:
    """
    创建初始Main Graph状态
    
    Args:
        session_id: 会话ID
        user_id: 用户ID（可选）
    
    Returns:
        初始化的MainState
    """
    return MainState(
        # 对话管理
        messages=[],
        user_id=user_id or "",
        session_id=session_id,
        
        # 用户画像
        user_profile=None,
        profile_complete=False,
        
        # 风险偏好
        risk_preference=None,
        risk_score=None,
        
        # 已有保障
        existing_coverage=[],
        
        # 推荐相关
        recommendations=[],
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
        
        # 元数据
        profile_change_history=[],
        recommendation_constraints=None,
        excluded_products=[]
    )


def create_initial_profile_state(session_id: str, user_id: str) -> ProfileState:
    """
    创建初始Profile Subgraph状态
    
    Args:
        session_id: 会话ID
        user_id: 用户ID
    
    Returns:
        初始化的ProfileState
    """
    return ProfileState(
        messages=[],
        user_id=user_id,
        session_id=session_id,
        user_profile=None,
        slots={},
        missing_slots=[],
        risk_preference=None,
        risk_score=None,
        existing_coverage=[],
        current_intent=None,
        question_type=None,
        extracted_entities={},
        profile_complete=False,
        error=None
    )


def create_initial_recommendation_state(
    session_id: str, 
    user_id: str,
    user_profile: UserProfile
) -> RecommendationState:
    """
    创建初始Recommendation Subgraph状态
    
    Args:
        session_id: 会话ID
        user_id: 用户ID
        user_profile: 用户画像
    
    Returns:
        初始化的RecommendationState
    """
    return RecommendationState(
        user_id=user_id,
        session_id=session_id,
        user_profile=user_profile,
        risk_preference=None,
        risk_score=None,
        existing_coverage=[],
        recommendations=[],
        explanations=[],
        coverage_gap=None,
        recommendation_constraints=None,
        excluded_products=[],
        recommendation_generated=False,
        error=None
    )


def create_initial_compliance_state(
    session_id: str,
    user_id: str,
    user_profile: UserProfile,
    recommendations: List[RecommendationResult]
) -> ComplianceState:
    """
    创建初始Compliance Subgraph状态
    
    Args:
        session_id: 会话ID
        user_id: 用户ID
        user_profile: 用户画像
        recommendations: 候选推荐产品列表
    
    Returns:
        初始化的ComplianceState
    """
    return ComplianceState(
        user_id=user_id,
        session_id=session_id,
        user_profile=user_profile,
        recommendations=recommendations,
        compliance_checks=[],
        compliance_passed=False,
        disclosure_info=[],
        filtered_recommendations=[],
        error=None
    )
