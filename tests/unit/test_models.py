"""测试数据模型的基本功能"""
import pytest
from datetime import datetime
from models import (
    UserProfile,
    MaritalStatus,
    IncomeRange,
    RiskPreference,
    HealthStatus,
    ExistingProduct,
    Product,
    PremiumRange,
    AgeRange,
    CoverageGap,
    RecommendationResult,
    Message,
    MessageRole,
    IntentType,
    SessionContext,
    SessionStatus,
    ComplianceCheck,
    ComplianceCheckType,
    CheckResult,
    ComplianceResult,
    DisclosureInfo,
    DisclosureItem,
    AgentState,
    create_initial_state,
)


class TestUserProfile:
    """测试UserProfile模型"""
    
    def test_create_valid_profile(self):
        """测试创建有效的用户画像"""
        profile = UserProfile(
            age=30,
            occupation="软件工程师",
            marital_status=MaritalStatus.MARRIED,
            has_children=True,
            children_count=1,
            has_dependents=False,
            dependents_count=0,
            family_size=3,
            income_range=IncomeRange.MEDIUM_HIGH,
            annual_income=300000,
            risk_preference=RiskPreference.BALANCED,
            health_status=HealthStatus.GOOD
        )
        
        assert profile.age == 30
        assert profile.occupation == "软件工程师"
        assert profile.marital_status == MaritalStatus.MARRIED
        assert profile.has_children is True
        assert profile.children_count == 1
    
    def test_profile_validation_children_count(self):
        """测试子女数量验证"""
        # has_children=True但children_count=0应该失败
        with pytest.raises(ValueError):
            UserProfile(
                age=30,
                occupation="工程师",
                marital_status=MaritalStatus.MARRIED,
                has_children=True,
                children_count=0,
                income_range=IncomeRange.MEDIUM
            )
    
    def test_profile_serialization(self):
        """测试序列化和反序列化"""
        profile = UserProfile(
            age=30,
            occupation="工程师",
            marital_status=MaritalStatus.SINGLE,
            income_range=IncomeRange.MEDIUM
        )
        
        # 序列化
        json_data = profile.model_dump_json()
        
        # 反序列化
        restored_profile = UserProfile.model_validate_json(json_data)
        
        assert restored_profile.age == profile.age
        assert restored_profile.occupation == profile.occupation


class TestProduct:
    """测试Product模型"""
    
    def test_create_valid_product(self):
        """测试创建有效的产品"""
        product = Product(
            product_id="prod-001",
            product_name="康健一生重疾险",
            product_type="critical_illness",
            provider="平安保险",
            premium_range=PremiumRange(min_premium=5000, max_premium=15000),
            age_range=AgeRange(min_age=18, max_age=60)
        )
        
        assert product.product_id == "prod-001"
        assert product.product_type == "critical_illness"
        assert product.premium_range.min_premium == 5000
        assert product.age_range.min_age == 18


class TestMessage:
    """测试Message模型"""
    
    def test_create_user_message(self):
        """测试创建用户消息"""
        message = Message(
            role=MessageRole.USER,
            content="我想了解重疾险",
            intent=IntentType.CONSULT_COVERAGE,
            extracted_slots={"interested_product_type": "critical_illness"}
        )
        
        assert message.role == MessageRole.USER
        assert message.content == "我想了解重疾险"
        assert message.intent == IntentType.CONSULT_COVERAGE
    
    def test_create_assistant_message(self):
        """测试创建助手消息"""
        message = Message(
            role=MessageRole.ASSISTANT,
            content="我可以为您推荐几款重疾险产品",
            agent_name="RecommendationAgent"
        )
        
        assert message.role == MessageRole.ASSISTANT
        assert message.agent_name == "RecommendationAgent"


class TestComplianceModels:
    """测试合规相关模型"""
    
    def test_compliance_check(self):
        """测试合规检查"""
        check = ComplianceCheck(
            check_type=ComplianceCheckType.AGE_CHECK,
            check_result=CheckResult.PASSED,
            check_description="年龄在投保范围内",
            checked_value="30",
            expected_value="18-60"
        )
        
        assert check.check_type == ComplianceCheckType.AGE_CHECK
        assert check.check_result == CheckResult.PASSED
    
    def test_compliance_result(self):
        """测试合规结果"""
        result = ComplianceResult(
            product_id="prod-001",
            user_id="user-001",
            eligible=True,
            overall_result=CheckResult.PASSED,
            checks=[
                ComplianceCheck(
                    check_type=ComplianceCheckType.AGE_CHECK,
                    check_result=CheckResult.PASSED,
                    check_description="年龄检查通过"
                )
            ]
        )
        
        assert result.eligible is True
        assert len(result.checks) == 1


class TestAgentState:
    """测试AgentState模型"""
    
    def test_create_initial_state(self):
        """测试创建初始状态"""
        state = create_initial_state(
            session_id="sess-001",
            user_id="user-001"
        )
        
        assert state["session_id"] == "sess-001"
        assert state["user_id"] == "user-001"
        assert state["turn_count"] == 0
        assert state["messages"] == []
        assert state["profile_complete"] is False
        assert state["recommendation_generated"] is False
    
    def test_state_update(self):
        """测试状态更新"""
        state = create_initial_state("sess-001")
        
        # 更新状态
        state["turn_count"] = 1
        state["profile_complete"] = True
        state["current_intent"] = IntentType.CONSULT_COVERAGE
        
        assert state["turn_count"] == 1
        assert state["profile_complete"] is True
        assert state["current_intent"] == IntentType.CONSULT_COVERAGE


class TestRecommendationResult:
    """测试推荐结果模型"""
    
    def test_create_recommendation(self):
        """测试创建推荐结果"""
        product = Product(
            product_id="prod-001",
            product_name="康健一生",
            product_type="critical_illness",
            provider="平安",
            premium_range=PremiumRange(min_premium=5000, max_premium=10000),
            age_range=AgeRange(min_age=18, max_age=60)
        )
        
        recommendation = RecommendationResult(
            product=product,
            rank=1,
            match_score=85.5,
            confidence_score=0.92,
            explanation="该产品非常适合您",
            match_dimensions={
                "age_match": 95,
                "income_match": 88
            },
            compliance_passed=True
        )
        
        assert recommendation.rank == 1
        assert recommendation.match_score == 85.5
        assert recommendation.compliance_passed is True


class TestCoverageGap:
    """测试保障缺口模型"""
    
    def test_create_coverage_gap(self):
        """测试创建保障缺口"""
        gap = CoverageGap(
            critical_illness_gap=300000,
            medical_gap=500000,
            current_critical_illness_coverage=200000,
            recommended_critical_illness=500000,
            gap_analysis="您的重疾险保额偏低",
            priority_recommendations=["critical_illness", "medical"]
        )
        
        assert gap.critical_illness_gap == 300000
        assert gap.medical_gap == 500000
        assert len(gap.priority_recommendations) == 2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
