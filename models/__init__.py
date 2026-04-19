"""
Models模块 - 数据模型定义（Pydantic和SQLAlchemy）
"""

# 用户相关模型
from models.user import (
    MaritalStatus,
    IncomeRange,
    RiskPreference,
    HealthStatus,
    UserProfile,
    ExistingProduct,
)

# 产品相关模型
from models.product import (
    PremiumRange,
    AgeRange,
    Product,
    CoverageGap,
    RecommendationResult,
)

# 对话相关模型
from models.conversation import (
    MessageRole,
    IntentType,
    Message,
    SessionStatus,
    SessionContext,
)

# 合规相关模型
from models.compliance import (
    ComplianceCheckType,
    CheckResult,
    ComplianceCheck,
    ComplianceResult,
    DisclosureItem,
    DisclosureInfo,
)

# Agent状态模型
from models.agent_state import (
    AgentState,
    create_initial_state,
    REQUIRED_SLOTS,
    OPTIONAL_SLOTS,
    ALL_SLOTS,
)

# 子图State模型（LangGraph 1.0.0）
from models.subgraph_states import (
    ProfileState,
    RecommendationState,
    ComplianceState,
    MainState,
    create_initial_main_state,
    create_initial_profile_state,
    create_initial_recommendation_state,
    create_initial_compliance_state,
)

# SQLAlchemy ORM模型
from models.db_models import (
    Base,
    User,
    UserProfile as UserProfileORM,
    ExistingCoverage,
    ConversationSession,
    ConversationMessage,
    InsuranceProduct,
    Recommendation,
    UserFeedback,
    ComplianceLog,
    QualityMetric,
    ArchivedSession,
)

__all__ = [
    # 用户相关
    "MaritalStatus",
    "IncomeRange",
    "RiskPreference",
    "HealthStatus",
    "UserProfile",
    "ExistingProduct",
    # 产品相关
    "PremiumRange",
    "AgeRange",
    "Product",
    "CoverageGap",
    "RecommendationResult",
    # 对话相关
    "MessageRole",
    "IntentType",
    "Message",
    "SessionStatus",
    "SessionContext",
    # 合规相关
    "ComplianceCheckType",
    "CheckResult",
    "ComplianceCheck",
    "ComplianceResult",
    "DisclosureItem",
    "DisclosureInfo",
    # Agent状态
    "AgentState",
    "create_initial_state",
    "REQUIRED_SLOTS",
    "OPTIONAL_SLOTS",
    "ALL_SLOTS",
    # 子图State模型
    "ProfileState",
    "RecommendationState",
    "ComplianceState",
    "MainState",
    "create_initial_main_state",
    "create_initial_profile_state",
    "create_initial_recommendation_state",
    "create_initial_compliance_state",
    # SQLAlchemy ORM模型
    "Base",
    "User",
    "UserProfileORM",
    "ExistingCoverage",
    "ConversationSession",
    "ConversationMessage",
    "InsuranceProduct",
    "Recommendation",
    "UserFeedback",
    "ComplianceLog",
    "QualityMetric",
    "ArchivedSession",
]

