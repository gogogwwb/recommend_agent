"""
测试SQLAlchemy ORM模型与Pydantic模型的转换方法
"""
import pytest
from datetime import datetime
from models import (
    UserProfile,
    UserProfileORM,
    ExistingProduct,
    ExistingCoverage,
    Product,
    InsuranceProduct,
    Message,
    ConversationMessage,
    SessionContext,
    ConversationSession,
    RecommendationResult,
    Recommendation,
    MaritalStatus,
    IncomeRange,
    RiskPreference,
    HealthStatus,
    MessageRole,
    IntentType,
    SessionStatus,
    PremiumRange,
    AgeRange,
)


class TestUserProfileConversion:
    """测试UserProfile ORM与Pydantic转换"""
    
    def test_user_profile_to_pydantic(self):
        """测试ORM转Pydantic"""
        # 导入ORM枚举类型
        from models.db_models import MaritalStatusEnum, IncomeRangeEnum, RiskPreferenceEnum, HealthStatusEnum
        
        # 创建ORM模型
        orm_profile = UserProfileORM(
            profile_id="profile-001",
            user_id="user-001",
            age=30,
            occupation="软件工程师",
            marital_status=MaritalStatusEnum.MARRIED,
            has_children=True,
            children_count=1,
            has_dependents=False,
            dependents_count=0,
            family_size=3,
            income_range=IncomeRangeEnum.MEDIUM_HIGH,
            annual_income=300000.0,
            risk_preference=RiskPreferenceEnum.BALANCED,
            risk_score=65.0,
            health_status=HealthStatusEnum.GOOD,
            has_medical_history=False,
            medical_conditions=[],
            city="北京",
            province="北京",
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )
        
        # 转换为Pydantic
        pydantic_profile = orm_profile.to_pydantic()
        
        # 验证转换结果
        assert pydantic_profile.age == 30
        assert pydantic_profile.occupation == "软件工程师"
        assert pydantic_profile.marital_status == MaritalStatus.MARRIED
        assert pydantic_profile.has_children is True
        assert pydantic_profile.children_count == 1
        assert pydantic_profile.income_range == IncomeRange.MEDIUM_HIGH
        assert pydantic_profile.annual_income == 300000.0
        assert pydantic_profile.risk_preference == RiskPreference.BALANCED
        assert pydantic_profile.health_status == HealthStatus.GOOD
    
    def test_user_profile_from_pydantic(self):
        """测试Pydantic转ORM"""
        # 创建Pydantic模型
        pydantic_profile = UserProfile(
            age=35,
            occupation="产品经理",
            marital_status=MaritalStatus.SINGLE,
            has_children=False,
            children_count=0,
            has_dependents=False,
            dependents_count=0,
            family_size=1,
            income_range=IncomeRange.HIGH,
            annual_income=500000.0,
            risk_preference=RiskPreference.AGGRESSIVE,
            health_status=HealthStatus.EXCELLENT,
        )
        
        # 转换为ORM
        orm_profile = UserProfileORM.from_pydantic(
            pydantic_profile, 
            user_id="user-002",
            profile_id="profile-002"
        )
        
        # 验证转换结果
        assert orm_profile.profile_id == "profile-002"
        assert orm_profile.user_id == "user-002"
        assert orm_profile.age == 35
        assert orm_profile.occupation == "产品经理"
        assert orm_profile.marital_status.value == "single"
        assert orm_profile.has_children is False
        assert orm_profile.income_range.value == "high"
        assert orm_profile.annual_income == 500000.0


class TestInsuranceProductConversion:
    """测试InsuranceProduct ORM与Pydantic转换"""
    
    def test_product_to_pydantic(self):
        """测试ORM转Pydantic"""
        # 创建ORM模型
        orm_product = InsuranceProduct(
            product_id="prod-001",
            product_name="康健一生重大疾病保险",
            product_type="critical_illness",
            provider="平安保险",
            coverage_scope=["重大疾病", "轻症", "中症"],
            coverage_amount_min=100000.0,
            coverage_amount_max=1000000.0,
            exclusions=["投保前已患疾病"],
            premium_min=5000.0,
            premium_max=15000.0,
            payment_period=["20年", "30年"],
            coverage_period=["终身"],
            age_min=18,
            age_max=60,
            occupation_restrictions=[],
            health_requirements=[],
            region_restrictions=[],
            features=["保障全面"],
            advantages=["性价比高"],
            suitable_for=["家庭支柱"],
            waiting_period_days=90,
            deductible=0.0,
            is_available=True,
            is_featured=True,
            created_at=datetime.now(),
            updated_at=datetime.now(),
            version=1,
        )
        
        # 转换为Pydantic
        pydantic_product = orm_product.to_pydantic()
        
        # 验证转换结果
        assert pydantic_product.product_id == "prod-001"
        assert pydantic_product.product_name == "康健一生重大疾病保险"
        assert pydantic_product.product_type == "critical_illness"
        assert pydantic_product.provider == "平安保险"
        assert "重大疾病" in pydantic_product.coverage_scope
        assert pydantic_product.premium_range.min_premium == 5000.0
        assert pydantic_product.premium_range.max_premium == 15000.0
        assert pydantic_product.age_range.min_age == 18
        assert pydantic_product.age_range.max_age == 60
        assert pydantic_product.is_available is True
    
    def test_product_from_pydantic(self):
        """测试Pydantic转ORM"""
        # 创建Pydantic模型
        pydantic_product = Product(
            product_id="prod-002",
            product_name="百万医疗险",
            product_type="medical",
            provider="中国人寿",
            coverage_scope=["住院医疗", "门诊"],
            exclusions=["既往症"],
            premium_range=PremiumRange(min_premium=500.0, max_premium=2000.0),
            payment_period=["1年"],
            coverage_period=["1年"],
            age_range=AgeRange(min_age=0, max_age=65),
            occupation_restrictions=[],
            health_requirements=[],
            region_restrictions=[],
            features=["保额高"],
            advantages=["保费低"],
            suitable_for=["所有人"],
            waiting_period_days=30,
            deductible=10000.0,
            is_available=True,
        )
        
        # 转换为ORM
        orm_product = InsuranceProduct.from_pydantic(pydantic_product)
        
        # 验证转换结果
        assert orm_product.product_id == "prod-002"
        assert orm_product.product_name == "百万医疗险"
        assert orm_product.product_type == "medical"
        assert orm_product.premium_min == 500.0
        assert orm_product.premium_max == 2000.0
        assert orm_product.age_min == 0
        assert orm_product.age_max == 65


class TestConversationMessageConversion:
    """测试ConversationMessage ORM与Pydantic转换"""
    
    def test_message_to_pydantic(self):
        """测试ORM转Pydantic"""
        # 导入ORM枚举类型
        from models.db_models import MessageRoleEnum
        
        # 创建ORM模型
        orm_message = ConversationMessage(
            message_id="msg-001",
            session_id="session-001",
            role=MessageRoleEnum.USER,
            content="我想了解重疾险",
            intent="consult_coverage",
            extracted_slots={"age": 30, "product_type": "critical_illness"},
            timestamp=datetime.now(),
        )
        
        # 转换为Pydantic
        pydantic_message = orm_message.to_pydantic()
        
        # 验证转换结果
        assert pydantic_message.role == MessageRole.USER
        assert pydantic_message.content == "我想了解重疾险"
        assert pydantic_message.intent == IntentType.CONSULT_COVERAGE
        assert pydantic_message.extracted_slots.get("age") == 30
    
    def test_message_from_pydantic(self):
        """测试Pydantic转ORM"""
        # 创建Pydantic模型
        pydantic_message = Message(
            role=MessageRole.ASSISTANT,
            content="好的，我来为您介绍重疾险",
            agent_name="ProfileCollectionAgent",
        )
        
        # 转换为ORM
        orm_message = ConversationMessage.from_pydantic(
            pydantic_message,
            session_id="session-001",
            message_id="msg-002"
        )
        
        # 验证转换结果
        assert orm_message.message_id == "msg-002"
        assert orm_message.session_id == "session-001"
        assert orm_message.role.value == "assistant"
        assert orm_message.content == "好的，我来为您介绍重疾险"
        assert orm_message.agent_name == "ProfileCollectionAgent"


class TestConversationSessionConversion:
    """测试ConversationSession ORM与Pydantic转换"""
    
    def test_session_to_pydantic(self):
        """测试ORM转Pydantic"""
        # 导入ORM枚举类型
        from models.db_models import SessionStatusEnum
        
        # 创建ORM模型
        orm_session = ConversationSession(
            session_id="session-001",
            user_id="user-001",
            status=SessionStatusEnum.ACTIVE,
            background_mode=False,
            turn_count=5,
            total_messages=10,
            created_at=datetime.now(),
            last_activity_at=datetime.now(),
        )
        
        # 转换为Pydantic
        pydantic_session = orm_session.to_pydantic()
        
        # 验证转换结果
        assert pydantic_session.session_id == "session-001"
        assert pydantic_session.user_id == "user-001"
        assert pydantic_session.status == SessionStatus.ACTIVE
        assert pydantic_session.background_mode is False
        assert pydantic_session.turn_count == 5
        assert pydantic_session.total_messages == 10
    
    def test_session_from_pydantic(self):
        """测试Pydantic转ORM"""
        # 创建Pydantic模型
        pydantic_session = SessionContext(
            session_id="session-002",
            user_id="user-002",
            status=SessionStatus.COMPLETED,
            turn_count=8,
            total_messages=16,
        )
        
        # 转换为ORM
        orm_session = ConversationSession.from_pydantic(pydantic_session)
        
        # 验证转换结果
        assert orm_session.session_id == "session-002"
        assert orm_session.user_id == "user-002"
        assert orm_session.status.value == "completed"
        assert orm_session.turn_count == 8
        assert orm_session.total_messages == 16


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
