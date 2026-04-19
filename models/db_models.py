"""
SQLAlchemy数据库模型

定义PostgreSQL数据库表结构，对应Pydantic模型
"""
from datetime import datetime
from typing import Optional, List, Dict, Any
from sqlalchemy import (
    Column, String, Integer, Float, Boolean, DateTime, Text, JSON, 
    ForeignKey, Index, Enum as SQLEnum, ARRAY
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
import enum

# Import Pydantic models for conversion
from models.user import (
    UserProfile as UserProfilePydantic,
    ExistingProduct,
    MaritalStatus,
    IncomeRange,
    RiskPreference,
    HealthStatus,
)
from models.product import (
    Product as ProductPydantic,
    PremiumRange,
    AgeRange,
    CoverageGap,
    RecommendationResult,
)
from models.conversation import (
    Message as MessagePydantic,
    MessageRole,
    IntentType,
    SessionStatus,
    SessionContext,
)
from models.compliance import (
    ComplianceCheck as ComplianceCheckPydantic,
    ComplianceResult as ComplianceResultPydantic,
    DisclosureInfo as DisclosureInfoPydantic,
    DisclosureItem,
    CheckResult,
    ComplianceCheckType,
)

Base = declarative_base()


# ==================== 枚举类型 ====================

class MaritalStatusEnum(str, enum.Enum):
    """婚姻状况枚举"""
    SINGLE = "single"
    MARRIED = "married"
    DIVORCED = "divorced"
    WIDOWED = "widowed"


class IncomeRangeEnum(str, enum.Enum):
    """收入区间枚举"""
    LOW = "low"
    MEDIUM_LOW = "medium_low"
    MEDIUM = "medium"
    MEDIUM_HIGH = "medium_high"
    HIGH = "high"


class RiskPreferenceEnum(str, enum.Enum):
    """风险偏好枚举"""
    CONSERVATIVE = "conservative"
    BALANCED = "balanced"
    AGGRESSIVE = "aggressive"


class HealthStatusEnum(str, enum.Enum):
    """健康状况枚举"""
    EXCELLENT = "excellent"
    GOOD = "good"
    FAIR = "fair"
    POOR = "poor"


class SessionStatusEnum(str, enum.Enum):
    """会话状态枚举"""
    ACTIVE = "active"
    BACKGROUND = "background"
    COMPLETED = "completed"
    ABANDONED = "abandoned"
    ARCHIVED = "archived"


class MessageRoleEnum(str, enum.Enum):
    """消息角色枚举"""
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


class CheckResultEnum(str, enum.Enum):
    """检查结果枚举"""
    PASSED = "passed"
    FAILED = "failed"
    WARNING = "warning"
    MANUAL_REVIEW = "manual_review"


# ==================== 用户相关表 ====================

class User(Base):
    """用户表"""
    __tablename__ = "users"
    
    user_id = Column(String(50), primary_key=True, comment="用户ID")
    username = Column(String(100), nullable=True, comment="用户名")
    email = Column(String(255), nullable=True, unique=True, comment="邮箱")
    phone = Column(String(20), nullable=True, comment="手机号")
    
    # 时间戳
    created_at = Column(DateTime, default=datetime.now, nullable=False, comment="创建时间")
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now, nullable=False, comment="更新时间")
    last_login_at = Column(DateTime, nullable=True, comment="最后登录时间")
    
    # 关系
    profiles = relationship("UserProfile", back_populates="user", cascade="all, delete-orphan")
    sessions = relationship("ConversationSession", back_populates="user", cascade="all, delete-orphan")
    
    # 索引
    __table_args__ = (
        Index('idx_users_email', 'email'),
        Index('idx_users_phone', 'phone'),
    )
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "user_id": self.user_id,
            "username": self.username,
            "email": self.email,
            "phone": self.phone,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "last_login_at": self.last_login_at,
        }


class UserProfile(Base):
    """用户画像表"""
    __tablename__ = "user_profiles"
    
    profile_id = Column(String(50), primary_key=True, comment="画像ID")
    user_id = Column(String(50), ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False, comment="用户ID")
    
    # 基本信息
    age = Column(Integer, nullable=False, comment="年龄")
    occupation = Column(String(100), nullable=False, comment="职业")
    marital_status = Column(SQLEnum(MaritalStatusEnum), nullable=False, comment="婚姻状况")
    
    # 家庭结构
    has_children = Column(Boolean, default=False, nullable=False, comment="是否有子女")
    children_count = Column(Integer, default=0, nullable=False, comment="子女数量")
    has_dependents = Column(Boolean, default=False, nullable=False, comment="是否有被抚养人")
    dependents_count = Column(Integer, default=0, nullable=False, comment="被抚养人数量")
    family_size = Column(Integer, default=1, nullable=False, comment="家庭人数")
    
    # 经济状况
    income_range = Column(SQLEnum(IncomeRangeEnum), nullable=False, comment="收入区间")
    annual_income = Column(Float, nullable=True, comment="年收入（具体金额）")
    
    # 风险偏好
    risk_preference = Column(SQLEnum(RiskPreferenceEnum), nullable=True, comment="风险偏好")
    risk_score = Column(Float, nullable=True, comment="风险评分")
    
    # 健康状况
    health_status = Column(SQLEnum(HealthStatusEnum), nullable=True, comment="健康状况")
    has_medical_history = Column(Boolean, default=False, nullable=False, comment="是否有病史")
    medical_conditions = Column(ARRAY(String), default=[], nullable=False, comment="已有疾病")
    
    # 地理位置
    city = Column(String(50), nullable=True, comment="所在城市")
    province = Column(String(50), nullable=True, comment="所在省份")
    
    # 时间戳
    created_at = Column(DateTime, default=datetime.now, nullable=False, comment="创建时间")
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now, nullable=False, comment="更新时间")
    
    # 关系
    user = relationship("User", back_populates="profiles")
    existing_coverages = relationship("ExistingCoverage", back_populates="profile", cascade="all, delete-orphan")
    
    # 索引
    __table_args__ = (
        Index('idx_user_profiles_user_id', 'user_id'),
        Index('idx_user_profiles_age', 'age'),
        Index('idx_user_profiles_income_range', 'income_range'),
    )
    
    @classmethod
    def from_pydantic(cls, profile: UserProfilePydantic, user_id: str, profile_id: str) -> "UserProfile":
        """从Pydantic模型创建ORM模型"""
        return cls(
            profile_id=profile_id,
            user_id=user_id,
            age=profile.age,
            occupation=profile.occupation,
            marital_status=MaritalStatusEnum(profile.marital_status.value),
            has_children=profile.has_children,
            children_count=profile.children_count,
            has_dependents=profile.has_dependents,
            dependents_count=profile.dependents_count,
            family_size=profile.family_size,
            income_range=IncomeRangeEnum(profile.income_range.value),
            annual_income=profile.annual_income,
            risk_preference=RiskPreferenceEnum(profile.risk_preference.value) if profile.risk_preference else None,
            risk_score=profile.risk_score,
            health_status=HealthStatusEnum(profile.health_status.value) if profile.health_status else None,
            has_medical_history=profile.has_medical_history,
            medical_conditions=profile.medical_conditions,
            city=profile.city,
            province=profile.province,
            created_at=profile.created_at,
            updated_at=profile.updated_at,
        )
    
    def to_pydantic(self) -> UserProfilePydantic:
        """转换为Pydantic模型"""
        return UserProfilePydantic(
            age=self.age,
            occupation=self.occupation,
            marital_status=MaritalStatus(self.marital_status.value),
            has_children=self.has_children,
            children_count=self.children_count,
            has_dependents=self.has_dependents,
            dependents_count=self.dependents_count,
            family_size=self.family_size,
            income_range=IncomeRange(self.income_range.value),
            annual_income=self.annual_income,
            risk_preference=RiskPreference(self.risk_preference.value) if self.risk_preference else None,
            risk_score=self.risk_score,
            health_status=HealthStatus(self.health_status.value) if self.health_status else None,
            has_medical_history=self.has_medical_history,
            medical_conditions=self.medical_conditions or [],
            city=self.city,
            province=self.province,
            created_at=self.created_at,
            updated_at=self.updated_at,
        )
    
    def update_from_pydantic(self, profile: UserProfilePydantic) -> None:
        """从Pydantic模型更新字段"""
        self.age = profile.age
        self.occupation = profile.occupation
        self.marital_status = MaritalStatusEnum(profile.marital_status.value)
        self.has_children = profile.has_children
        self.children_count = profile.children_count
        self.has_dependents = profile.has_dependents
        self.dependents_count = profile.dependents_count
        self.family_size = profile.family_size
        self.income_range = IncomeRangeEnum(profile.income_range.value)
        self.annual_income = profile.annual_income
        self.risk_preference = RiskPreferenceEnum(profile.risk_preference.value) if profile.risk_preference else None
        self.risk_score = profile.risk_score
        self.health_status = HealthStatusEnum(profile.health_status.value) if profile.health_status else None
        self.has_medical_history = profile.has_medical_history
        self.medical_conditions = profile.medical_conditions
        self.city = profile.city
        self.province = profile.province
        self.updated_at = datetime.now()


class ExistingCoverage(Base):
    """已有保障表"""
    __tablename__ = "existing_coverage"
    
    coverage_id = Column(String(50), primary_key=True, comment="保障ID")
    profile_id = Column(String(50), ForeignKey("user_profiles.profile_id", ondelete="CASCADE"), nullable=False, comment="画像ID")
    
    # 产品信息
    product_id = Column(String(50), nullable=False, comment="产品ID")
    product_name = Column(String(200), nullable=False, comment="产品名称")
    product_type = Column(String(50), nullable=False, comment="产品类型")
    
    # 保障信息
    coverage_amount = Column(Float, nullable=False, comment="保额")
    premium = Column(Float, nullable=False, comment="保费")
    coverage_scope = Column(ARRAY(String), default=[], nullable=False, comment="保障范围")
    
    # 时间信息
    purchase_date = Column(DateTime, nullable=True, comment="购买日期")
    coverage_start_date = Column(DateTime, nullable=True, comment="保障开始日期")
    coverage_end_date = Column(DateTime, nullable=True, comment="保障结束日期")
    
    # 状态
    is_active = Column(Boolean, default=True, nullable=False, comment="是否有效")
    
    # 时间戳
    created_at = Column(DateTime, default=datetime.now, nullable=False, comment="创建时间")
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now, nullable=False, comment="更新时间")
    
    # 关系
    profile = relationship("UserProfile", back_populates="existing_coverages")
    
    # 索引
    __table_args__ = (
        Index('idx_existing_coverage_profile_id', 'profile_id'),
        Index('idx_existing_coverage_product_type', 'product_type'),
        Index('idx_existing_coverage_is_active', 'is_active'),
    )
    
    @classmethod
    def from_pydantic(cls, product: ExistingProduct, profile_id: str, coverage_id: str) -> "ExistingCoverage":
        """从Pydantic模型创建ORM模型"""
        return cls(
            coverage_id=coverage_id,
            profile_id=profile_id,
            product_id=product.product_id,
            product_name=product.product_name,
            product_type=product.product_type,
            coverage_amount=product.coverage_amount,
            premium=product.premium,
            coverage_scope=product.coverage_scope,
            purchase_date=product.purchase_date,
            coverage_start_date=product.coverage_start_date,
            coverage_end_date=product.coverage_end_date,
            is_active=product.is_active,
        )
    
    def to_pydantic(self) -> ExistingProduct:
        """转换为Pydantic模型"""
        return ExistingProduct(
            product_id=self.product_id,
            product_name=self.product_name,
            product_type=self.product_type,
            coverage_amount=self.coverage_amount,
            premium=self.premium,
            coverage_scope=self.coverage_scope or [],
            purchase_date=self.purchase_date,
            coverage_start_date=self.coverage_start_date,
            coverage_end_date=self.coverage_end_date,
            is_active=self.is_active,
        )
    
    def update_from_pydantic(self, product: ExistingProduct) -> None:
        """从Pydantic模型更新字段"""
        self.product_id = product.product_id
        self.product_name = product.product_name
        self.product_type = product.product_type
        self.coverage_amount = product.coverage_amount
        self.premium = product.premium
        self.coverage_scope = product.coverage_scope
        self.purchase_date = product.purchase_date
        self.coverage_start_date = product.coverage_start_date
        self.coverage_end_date = product.coverage_end_date
        self.is_active = product.is_active
        self.updated_at = datetime.now()


# ==================== 对话相关表 ====================

class ConversationSession(Base):
    """对话会话表"""
    __tablename__ = "conversation_sessions"
    
    session_id = Column(String(50), primary_key=True, comment="会话ID")
    user_id = Column(String(50), ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False, comment="用户ID")
    
    # 会话状态
    status = Column(SQLEnum(SessionStatusEnum), default=SessionStatusEnum.ACTIVE, nullable=False, comment="会话状态")
    background_mode = Column(Boolean, default=False, nullable=False, comment="是否后台运行")
    
    # 时间信息
    created_at = Column(DateTime, default=datetime.now, nullable=False, comment="创建时间")
    last_activity_at = Column(DateTime, default=datetime.now, onupdate=datetime.now, nullable=False, comment="最后活跃时间")
    completed_at = Column(DateTime, nullable=True, comment="完成时间")
    
    # 会话统计
    turn_count = Column(Integer, default=0, nullable=False, comment="对话轮数")
    total_messages = Column(Integer, default=0, nullable=False, comment="总消息数")
    
    # 会话数据（JSON存储）
    slots = Column(JSON, default={}, nullable=False, comment="槽位数据")
    user_preferences = Column(JSON, default={}, nullable=True, comment="用户偏好")
    
    # 温数据层字段（Warm Data Layer）
    warm_messages = Column(JSON, default=[], nullable=False, comment="温数据层未压缩消息")
    compressed_history = Column(Text, default="", nullable=False, comment="压缩的历史对话摘要")
    compression_count = Column(Integer, default=0, nullable=False, comment="压缩批次计数")
    
    # 关系
    user = relationship("User", back_populates="sessions")
    messages = relationship("ConversationMessage", back_populates="session", cascade="all, delete-orphan")
    recommendations = relationship("Recommendation", back_populates="session", cascade="all, delete-orphan")
    
    # 索引
    __table_args__ = (
        Index('idx_conversation_sessions_user_id', 'user_id'),
        Index('idx_conversation_sessions_status', 'status'),
        Index('idx_conversation_sessions_created_at', 'created_at'),
        Index('idx_conversation_sessions_last_activity', 'last_activity_at'),
        Index('idx_sessions_compression_count', 'compression_count'),
    )
    
    @classmethod
    def from_pydantic(cls, context: SessionContext) -> "ConversationSession":
        """从Pydantic模型创建ORM模型"""
        return cls(
            session_id=context.session_id,
            user_id=context.user_id,
            status=SessionStatusEnum(context.status.value),
            background_mode=context.background_mode,
            created_at=context.created_at,
            last_activity_at=context.last_activity_at,
            completed_at=context.completed_at,
            turn_count=context.turn_count,
            total_messages=context.total_messages,
        )
    
    def to_pydantic(self) -> SessionContext:
        """转换为Pydantic模型"""
        return SessionContext(
            session_id=self.session_id,
            user_id=self.user_id,
            status=SessionStatus(self.status.value),
            background_mode=self.background_mode,
            created_at=self.created_at,
            last_activity_at=self.last_activity_at,
            completed_at=self.completed_at,
            turn_count=self.turn_count,
            total_messages=self.total_messages,
        )
    
    def update_from_pydantic(self, context: SessionContext) -> None:
        """从Pydantic模型更新字段"""
        self.status = SessionStatusEnum(context.status.value)
        self.background_mode = context.background_mode
        self.last_activity_at = context.last_activity_at
        self.completed_at = context.completed_at
        self.turn_count = context.turn_count
        self.total_messages = context.total_messages


class ConversationMessage(Base):
    """对话消息表"""
    __tablename__ = "conversation_messages"
    
    message_id = Column(String(50), primary_key=True, comment="消息ID")
    session_id = Column(String(50), ForeignKey("conversation_sessions.session_id", ondelete="CASCADE"), nullable=False, comment="会话ID")
    
    # 消息内容
    role = Column(SQLEnum(MessageRoleEnum), nullable=False, comment="消息角色")
    content = Column(Text, nullable=False, comment="消息内容")
    
    # 意图和槽位（用户消息）
    intent = Column(String(50), nullable=True, comment="用户意图")
    extracted_slots = Column(JSON, default={}, nullable=True, comment="提取的槽位")
    
    # Agent信息（助手消息）
    agent_name = Column(String(50), nullable=True, comment="生成消息的Agent名称")
    thinking_process = Column(Text, nullable=True, comment="思考过程")
    
    # 时间戳
    timestamp = Column(DateTime, default=datetime.now, nullable=False, comment="时间戳")
    
    # 关系
    session = relationship("ConversationSession", back_populates="messages")
    
    # 索引
    __table_args__ = (
        Index('idx_conversation_messages_session_id', 'session_id'),
        Index('idx_conversation_messages_timestamp', 'timestamp'),
        Index('idx_conversation_messages_role', 'role'),
    )
    
    @classmethod
    def from_pydantic(cls, message: MessagePydantic, session_id: str, message_id: str) -> "ConversationMessage":
        """从Pydantic模型创建ORM模型"""
        return cls(
            message_id=message_id,
            session_id=session_id,
            role=MessageRoleEnum(message.role.value),
            content=message.content,
            intent=message.intent.value if message.intent else None,
            extracted_slots=message.extracted_slots,
            agent_name=message.agent_name,
            thinking_process=message.thinking_process,
            timestamp=message.timestamp,
        )
    
    def to_pydantic(self) -> MessagePydantic:
        """转换为Pydantic模型"""
        return MessagePydantic(
            role=MessageRole(self.role.value),
            content=self.content,
            timestamp=self.timestamp,
            message_id=self.message_id,
            intent=IntentType(self.intent) if self.intent else None,
            extracted_slots=self.extracted_slots or {},
            agent_name=self.agent_name,
            thinking_process=self.thinking_process,
        )
    
    def update_from_pydantic(self, message: MessagePydantic) -> None:
        """从Pydantic模型更新字段"""
        self.role = MessageRoleEnum(message.role.value)
        self.content = message.content
        self.intent = message.intent.value if message.intent else None
        self.extracted_slots = message.extracted_slots
        self.agent_name = message.agent_name
        self.thinking_process = message.thinking_process
        self.timestamp = message.timestamp


# ==================== 产品相关表 ====================

class InsuranceProduct(Base):
    """保险产品表"""
    __tablename__ = "insurance_products"
    
    product_id = Column(String(50), primary_key=True, comment="产品ID")
    
    # 基本信息
    product_name = Column(String(200), nullable=False, comment="产品名称")
    product_type = Column(String(50), nullable=False, comment="产品类型")
    provider = Column(String(100), nullable=False, comment="保险公司")
    
    # 保障信息
    coverage_scope = Column(ARRAY(String), default=[], nullable=False, comment="保障范围")
    coverage_amount_min = Column(Float, nullable=True, comment="最小保额")
    coverage_amount_max = Column(Float, nullable=True, comment="最大保额")
    exclusions = Column(ARRAY(String), default=[], nullable=False, comment="责任免除")
    
    # 费率信息
    premium_min = Column(Float, nullable=False, comment="最低保费")
    premium_max = Column(Float, nullable=False, comment="最高保费")
    payment_period = Column(ARRAY(String), default=[], nullable=False, comment="缴费期限选项")
    coverage_period = Column(ARRAY(String), default=[], nullable=False, comment="保障期限选项")
    
    # 投保规则
    age_min = Column(Integer, nullable=False, comment="最小投保年龄")
    age_max = Column(Integer, nullable=False, comment="最大投保年龄")
    occupation_restrictions = Column(ARRAY(String), default=[], nullable=False, comment="职业限制")
    health_requirements = Column(ARRAY(String), default=[], nullable=False, comment="健康要求")
    region_restrictions = Column(ARRAY(String), default=[], nullable=False, comment="地域限制")
    
    # 产品特点
    features = Column(ARRAY(String), default=[], nullable=False, comment="产品特点")
    advantages = Column(ARRAY(String), default=[], nullable=False, comment="产品优势")
    suitable_for = Column(ARRAY(String), default=[], nullable=False, comment="适用人群")
    
    # 理赔信息
    claim_process = Column(Text, nullable=True, comment="理赔流程")
    waiting_period_days = Column(Integer, default=0, nullable=False, comment="等待期（天）")
    deductible = Column(Float, default=0, nullable=False, comment="免赔额")
    
    # 状态
    is_available = Column(Boolean, default=True, nullable=False, comment="是否可售")
    is_featured = Column(Boolean, default=False, nullable=False, comment="是否推荐产品")
    
    # 向量化特征（用于RAG检索）
    embedding = Column(ARRAY(Float), nullable=True, comment="产品特征向量")
    
    # 时间戳
    created_at = Column(DateTime, default=datetime.now, nullable=False, comment="创建时间")
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now, nullable=False, comment="更新时间")
    version = Column(Integer, default=1, nullable=False, comment="版本号")
    
    # 关系
    recommendations = relationship("Recommendation", back_populates="product")
    
    # 索引
    __table_args__ = (
        Index('idx_insurance_products_product_type', 'product_type'),
        Index('idx_insurance_products_provider', 'provider'),
        Index('idx_insurance_products_is_available', 'is_available'),
        Index('idx_insurance_products_age_range', 'age_min', 'age_max'),
        Index('idx_insurance_products_premium_range', 'premium_min', 'premium_max'),
    )
    
    @classmethod
    def from_pydantic(cls, product: ProductPydantic) -> "InsuranceProduct":
        """从Pydantic模型创建ORM模型"""
        return cls(
            product_id=product.product_id,
            product_name=product.product_name,
            product_type=product.product_type,
            provider=product.provider,
            coverage_scope=product.coverage_scope,
            coverage_amount_min=product.coverage_amount_range.get("min") if product.coverage_amount_range else None,
            coverage_amount_max=product.coverage_amount_range.get("max") if product.coverage_amount_range else None,
            exclusions=product.exclusions,
            premium_min=product.premium_range.min_premium,
            premium_max=product.premium_range.max_premium,
            payment_period=product.payment_period,
            coverage_period=product.coverage_period,
            age_min=product.age_range.min_age,
            age_max=product.age_range.max_age,
            occupation_restrictions=product.occupation_restrictions,
            health_requirements=product.health_requirements,
            region_restrictions=product.region_restrictions,
            features=product.features,
            advantages=product.advantages,
            suitable_for=product.suitable_for,
            claim_process=product.claim_process,
            waiting_period_days=product.waiting_period_days,
            deductible=product.deductible,
            is_available=product.is_available,
            is_featured=product.is_featured,
            embedding=product.embedding,
            created_at=product.created_at,
            updated_at=product.updated_at,
            version=product.version,
        )
    
    def to_pydantic(self) -> ProductPydantic:
        """转换为Pydantic模型"""
        return ProductPydantic(
            product_id=self.product_id,
            product_name=self.product_name,
            product_type=self.product_type,
            provider=self.provider,
            coverage_scope=self.coverage_scope or [],
            coverage_amount_range={
                "min": self.coverage_amount_min,
                "max": self.coverage_amount_max
            } if self.coverage_amount_min and self.coverage_amount_max else None,
            exclusions=self.exclusions or [],
            premium_range=PremiumRange(
                min_premium=self.premium_min,
                max_premium=self.premium_max
            ),
            payment_period=self.payment_period or [],
            coverage_period=self.coverage_period or [],
            age_range=AgeRange(
                min_age=self.age_min,
                max_age=self.age_max
            ),
            occupation_restrictions=self.occupation_restrictions or [],
            health_requirements=self.health_requirements or [],
            region_restrictions=self.region_restrictions or [],
            features=self.features or [],
            advantages=self.advantages or [],
            suitable_for=self.suitable_for or [],
            claim_process=self.claim_process,
            waiting_period_days=self.waiting_period_days,
            deductible=self.deductible,
            is_available=self.is_available,
            is_featured=self.is_featured,
            embedding=self.embedding,
            created_at=self.created_at,
            updated_at=self.updated_at,
            version=self.version,
        )
    
    def update_from_pydantic(self, product: ProductPydantic) -> None:
        """从Pydantic模型更新字段"""
        self.product_name = product.product_name
        self.product_type = product.product_type
        self.provider = product.provider
        self.coverage_scope = product.coverage_scope
        self.coverage_amount_min = product.coverage_amount_range.get("min") if product.coverage_amount_range else None
        self.coverage_amount_max = product.coverage_amount_range.get("max") if product.coverage_amount_range else None
        self.exclusions = product.exclusions
        self.premium_min = product.premium_range.min_premium
        self.premium_max = product.premium_range.max_premium
        self.payment_period = product.payment_period
        self.coverage_period = product.coverage_period
        self.age_min = product.age_range.min_age
        self.age_max = product.age_range.max_age
        self.occupation_restrictions = product.occupation_restrictions
        self.health_requirements = product.health_requirements
        self.region_restrictions = product.region_restrictions
        self.features = product.features
        self.advantages = product.advantages
        self.suitable_for = product.suitable_for
        self.claim_process = product.claim_process
        self.waiting_period_days = product.waiting_period_days
        self.deductible = product.deductible
        self.is_available = product.is_available
        self.is_featured = product.is_featured
        self.embedding = product.embedding
        self.updated_at = datetime.now()
        self.version = self.version + 1


# ==================== 推荐相关表 ====================

class Recommendation(Base):
    """推荐记录表"""
    __tablename__ = "recommendations"
    
    recommendation_id = Column(String(50), primary_key=True, comment="推荐ID")
    session_id = Column(String(50), ForeignKey("conversation_sessions.session_id", ondelete="CASCADE"), nullable=False, comment="会话ID")
    product_id = Column(String(50), ForeignKey("insurance_products.product_id", ondelete="CASCADE"), nullable=False, comment="产品ID")
    
    # 推荐评分
    rank = Column(Integer, nullable=False, comment="推荐排名")
    match_score = Column(Float, nullable=False, comment="匹配分数")
    confidence_score = Column(Float, nullable=False, comment="推荐置信度")
    
    # 推荐理由
    explanation = Column(Text, nullable=False, comment="推荐理由")
    match_dimensions = Column(JSON, default={}, nullable=False, comment="各维度匹配分数")
    why_suitable = Column(ARRAY(String), default=[], nullable=False, comment="为什么适合用户")
    key_benefits = Column(ARRAY(String), default=[], nullable=False, comment="关键收益")
    
    # 合规状态
    compliance_passed = Column(Boolean, default=False, nullable=False, comment="是否通过合规检查")
    compliance_issues = Column(ARRAY(String), default=[], nullable=False, comment="合规问题")
    
    # 时间戳
    recommended_at = Column(DateTime, default=datetime.now, nullable=False, comment="推荐时间")
    
    # 关系
    session = relationship("ConversationSession", back_populates="recommendations")
    product = relationship("InsuranceProduct", back_populates="recommendations")
    feedbacks = relationship("UserFeedback", back_populates="recommendation", cascade="all, delete-orphan")
    
    # 索引
    __table_args__ = (
        Index('idx_recommendations_session_id', 'session_id'),
        Index('idx_recommendations_product_id', 'product_id'),
        Index('idx_recommendations_recommended_at', 'recommended_at'),
        Index('idx_recommendations_match_score', 'match_score'),
    )
    
    @classmethod
    def from_pydantic(
        cls, 
        result: RecommendationResult, 
        session_id: str, 
        recommendation_id: str
    ) -> "Recommendation":
        """从Pydantic模型创建ORM模型"""
        return cls(
            recommendation_id=recommendation_id,
            session_id=session_id,
            product_id=result.product.product_id,
            rank=result.rank,
            match_score=result.match_score,
            confidence_score=result.confidence_score,
            explanation=result.explanation,
            match_dimensions=result.match_dimensions,
            why_suitable=result.why_suitable,
            key_benefits=result.key_benefits,
            compliance_passed=result.compliance_passed,
            compliance_issues=result.compliance_issues,
            recommended_at=result.recommended_at,
        )
    
    def to_pydantic(self) -> RecommendationResult:
        """转换为Pydantic模型"""
        return RecommendationResult(
            product=self.product.to_pydantic() if self.product else None,
            rank=self.rank,
            match_score=self.match_score,
            confidence_score=self.confidence_score,
            explanation=self.explanation,
            match_dimensions=self.match_dimensions or {},
            why_suitable=self.why_suitable or [],
            key_benefits=self.key_benefits or [],
            compliance_passed=self.compliance_passed,
            compliance_issues=self.compliance_issues or [],
            recommended_at=self.recommended_at,
        )
    
    def update_from_pydantic(self, result: RecommendationResult) -> None:
        """从Pydantic模型更新字段"""
        self.rank = result.rank
        self.match_score = result.match_score
        self.confidence_score = result.confidence_score
        self.explanation = result.explanation
        self.match_dimensions = result.match_dimensions
        self.why_suitable = result.why_suitable
        self.key_benefits = result.key_benefits
        self.compliance_passed = result.compliance_passed
        self.compliance_issues = result.compliance_issues


# ==================== 反馈相关表 ====================

class UserFeedback(Base):
    """用户反馈表"""
    __tablename__ = "user_feedback"
    
    feedback_id = Column(String(50), primary_key=True, comment="反馈ID")
    recommendation_id = Column(String(50), ForeignKey("recommendations.recommendation_id", ondelete="CASCADE"), nullable=False, comment="推荐ID")
    
    # 反馈内容
    satisfaction = Column(String(20), nullable=False, comment="满意度（positive/negative/neutral）")
    reason = Column(Text, nullable=True, comment="反馈原因")
    rating = Column(Integer, nullable=True, comment="评分（1-5）")
    
    # 详细反馈
    helpful = Column(Boolean, nullable=True, comment="是否有帮助")
    meets_needs = Column(Boolean, nullable=True, comment="是否符合需求")
    comments = Column(Text, nullable=True, comment="其他评论")
    
    # 时间戳
    created_at = Column(DateTime, default=datetime.now, nullable=False, comment="创建时间")
    
    # 关系
    recommendation = relationship("Recommendation", back_populates="feedbacks")
    
    # 索引
    __table_args__ = (
        Index('idx_user_feedback_recommendation_id', 'recommendation_id'),
        Index('idx_user_feedback_satisfaction', 'satisfaction'),
        Index('idx_user_feedback_created_at', 'created_at'),
    )


# ==================== 合规相关表 ====================

class ComplianceLog(Base):
    """合规日志表"""
    __tablename__ = "compliance_logs"
    
    log_id = Column(String(50), primary_key=True, comment="日志ID")
    session_id = Column(String(50), nullable=False, comment="会话ID")
    product_id = Column(String(50), nullable=False, comment="产品ID")
    user_id = Column(String(50), nullable=False, comment="用户ID")
    
    # 检查结果
    check_type = Column(String(50), nullable=False, comment="检查类型")
    check_result = Column(SQLEnum(CheckResultEnum), nullable=False, comment="检查结果")
    eligible = Column(Boolean, nullable=False, comment="是否符合投保条件")
    
    # 检查详情
    check_description = Column(Text, nullable=False, comment="检查描述")
    reason = Column(Text, nullable=True, comment="未通过原因")
    checked_value = Column(String(200), nullable=True, comment="被检查的值")
    expected_value = Column(String(200), nullable=True, comment="期望的值")
    
    # 详细检查数据（JSON）
    checks_detail = Column(JSON, default=[], nullable=False, comment="详细检查列表")
    failed_checks = Column(ARRAY(String), default=[], nullable=False, comment="未通过的检查")
    recommendations = Column(ARRAY(String), default=[], nullable=False, comment="改进建议")
    
    # 时间戳
    checked_at = Column(DateTime, default=datetime.now, nullable=False, comment="检查时间")
    
    # 索引
    __table_args__ = (
        Index('idx_compliance_logs_session_id', 'session_id'),
        Index('idx_compliance_logs_product_id', 'product_id'),
        Index('idx_compliance_logs_user_id', 'user_id'),
        Index('idx_compliance_logs_check_result', 'check_result'),
        Index('idx_compliance_logs_checked_at', 'checked_at'),
    )
    
    @classmethod
    def from_pydantic(
        cls, 
        result: ComplianceResultPydantic, 
        log_id: str,
        session_id: str,
        user_id: str
    ) -> "ComplianceLog":
        """从Pydantic模型创建ORM模型"""
        return cls(
            log_id=log_id,
            session_id=session_id,
            product_id=result.product_id,
            user_id=user_id,
            check_type="comprehensive",  # 综合检查
            check_result=CheckResultEnum(result.overall_result.value),
            eligible=result.eligible,
            check_description="综合合规检查",
            reason="; ".join(result.reasons) if result.reasons else None,
            checks_detail=[check.model_dump() for check in result.checks],
            failed_checks=result.failed_checks,
            recommendations=result.recommendations,
            checked_at=result.checked_at,
        )
    
    def to_pydantic(self) -> ComplianceResultPydantic:
        """转换为Pydantic模型"""
        checks = []
        if self.checks_detail:
            for check_data in self.checks_detail:
                checks.append(ComplianceCheckPydantic(**check_data))
        
        return ComplianceResultPydantic(
            product_id=self.product_id,
            user_id=self.user_id,
            eligible=self.eligible,
            overall_result=CheckResult(self.check_result.value),
            checks=checks,
            failed_checks=self.failed_checks or [],
            reasons=[self.reason] if self.reason else [],
            recommendations=self.recommendations or [],
            checked_at=self.checked_at,
        )


# ==================== 质量监控表 ====================

class QualityMetric(Base):
    """质量指标表"""
    __tablename__ = "quality_metrics"
    
    metric_id = Column(String(50), primary_key=True, comment="指标ID")
    session_id = Column(String(50), nullable=False, comment="会话ID")
    
    # 对话质量指标
    intent_recognition_accuracy = Column(Float, nullable=True, comment="意图识别准确率")
    slot_fill_rate = Column(Float, nullable=True, comment="槽位填充率")
    conversation_completion_rate = Column(Float, nullable=True, comment="对话完成率")
    
    # 推荐质量指标
    recommendation_confidence = Column(Float, nullable=True, comment="推荐置信度")
    recommendation_diversity = Column(Float, nullable=True, comment="推荐多样性")
    compliance_pass_rate = Column(Float, nullable=True, comment="合规通过率")
    
    # 性能指标
    total_turns = Column(Integer, nullable=False, comment="总对话轮数")
    total_tokens = Column(Integer, nullable=True, comment="总Token数")
    response_time_ms = Column(Integer, nullable=True, comment="响应时间（毫秒）")
    
    # 用户满意度
    user_satisfaction = Column(String(20), nullable=True, comment="用户满意度")
    quality_score = Column(Float, nullable=True, comment="质量评分")
    
    # 时间戳
    created_at = Column(DateTime, default=datetime.now, nullable=False, comment="创建时间")
    
    # 索引
    __table_args__ = (
        Index('idx_quality_metrics_session_id', 'session_id'),
        Index('idx_quality_metrics_created_at', 'created_at'),
        Index('idx_quality_metrics_quality_score', 'quality_score'),
    )


# ==================== 归档会话表 ====================

class ArchivedSession(Base):
    """归档会话表"""
    __tablename__ = "archived_sessions"
    
    archive_id = Column(String(50), primary_key=True, comment="归档ID")
    session_id = Column(String(50), nullable=False, comment="原会话ID")
    user_id = Column(String(50), nullable=False, comment="用户ID")
    
    # 会话摘要
    session_summary = Column(Text, nullable=True, comment="会话摘要")
    key_intents = Column(ARRAY(String), default=[], nullable=False, comment="关键意图")
    extracted_profile = Column(JSON, nullable=True, comment="提取的用户画像")
    
    # 推荐结果
    recommended_products = Column(ARRAY(String), default=[], nullable=False, comment="推荐的产品ID列表")
    user_feedback_summary = Column(Text, nullable=True, comment="用户反馈摘要")
    
    # 完整会话数据（JSON）
    full_conversation = Column(JSON, nullable=True, comment="完整对话数据")
    final_state = Column(JSON, nullable=True, comment="最终状态")
    
    # 向量化（用于相似会话检索）
    session_embedding = Column(ARRAY(Float), nullable=True, comment="会话特征向量")
    
    # 时间信息
    session_created_at = Column(DateTime, nullable=False, comment="会话创建时间")
    session_completed_at = Column(DateTime, nullable=False, comment="会话完成时间")
    archived_at = Column(DateTime, default=datetime.now, nullable=False, comment="归档时间")
    
    # 索引
    __table_args__ = (
        Index('idx_archived_sessions_session_id', 'session_id'),
        Index('idx_archived_sessions_user_id', 'user_id'),
        Index('idx_archived_sessions_archived_at', 'archived_at'),
    )
