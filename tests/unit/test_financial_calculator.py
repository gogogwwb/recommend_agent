"""
金融计算工具单元测试
"""
import pytest
from tools.financial_calculator import FinancialCalculatorTool
from models.user import (
    UserProfile,
    MaritalStatus,
    IncomeRange,
    RiskPreference,
    HealthStatus
)


class TestFinancialCalculatorTool:
    """金融计算工具测试类"""
    
    @pytest.fixture
    def calculator(self):
        """创建计算器实例"""
        return FinancialCalculatorTool()
    
    @pytest.fixture
    def sample_profile(self):
        """创建示例用户画像"""
        return UserProfile(
            age=30,
            occupation="软件工程师",
            marital_status=MaritalStatus.MARRIED,
            has_children=True,
            children_count=1,
            has_dependents=True,
            dependents_count=1,
            family_size=3,
            income_range=IncomeRange.MEDIUM_HIGH,
            annual_income=300000,
            risk_preference=RiskPreference.BALANCED,
            health_status=HealthStatus.GOOD
        )
    
    # ========== calculate_affordable_premium 测试 ==========
    
    def test_calculate_affordable_premium_basic(self, calculator):
        """测试基本保费计算"""
        # 年收入10万，家庭1人
        premium = calculator.calculate_affordable_premium(100000, 1)
        # 基础比例10%
        assert premium == 10000.0
    
    def test_calculate_affordable_premium_family_adjustment(self, calculator):
        """测试家庭人数调整"""
        # 年收入10万，家庭3人
        premium = calculator.calculate_affordable_premium(100000, 3)
        # 基础比例10% - 调整4% = 6%
        assert pytest.approx(premium, rel=1e-9) == 6000.0
    
    def test_calculate_affordable_premium_min_ratio(self, calculator):
        """测试最低比例限制"""
        # 年收入10万，家庭10人（会触发最低比例5%）
        premium = calculator.calculate_affordable_premium(100000, 10)
        # 最低比例5%
        assert premium == 5000.0
    
    def test_calculate_affordable_premium_zero_income(self, calculator):
        """测试零收入"""
        premium = calculator.calculate_affordable_premium(0, 1)
        assert premium == 0.0
    
    def test_calculate_affordable_premium_negative_income(self, calculator):
        """测试负收入应抛出异常"""
        with pytest.raises(ValueError, match="年收入不能为负数"):
            calculator.calculate_affordable_premium(-100000, 1)
    
    def test_calculate_affordable_premium_invalid_family_size(self, calculator):
        """测试无效家庭人数应抛出异常"""
        with pytest.raises(ValueError, match="家庭人数必须大于等于1"):
            calculator.calculate_affordable_premium(100000, 0)
    
    # ========== calculate_coverage_need 测试 ==========
    
    def test_calculate_coverage_need_with_dependents(self, calculator, sample_profile):
        """测试有被抚养人的保障需求计算"""
        needs = calculator.calculate_coverage_need(sample_profile)
        
        # 年收入30万
        # 重疾险：5倍 = 150万
        assert needs["critical_illness"] == 1500000.0
        # 医疗险：固定50万
        assert needs["medical"] == 500000.0
        # 意外险：10倍 = 300万
        assert needs["accident"] == 3000000.0
        # 寿险：有被抚养人，10倍 = 300万
        assert needs["life"] == 3000000.0
    
    def test_calculate_coverage_need_without_dependents(self, calculator):
        """测试无被抚养人的保障需求计算"""
        profile = UserProfile(
            age=30,
            occupation="软件工程师",
            marital_status=MaritalStatus.SINGLE,
            has_children=False,
            children_count=0,
            has_dependents=False,
            dependents_count=0,
            family_size=1,
            income_range=IncomeRange.MEDIUM,
            annual_income=200000
        )
        
        needs = calculator.calculate_coverage_need(profile)
        
        # 年收入20万
        # 重疾险：5倍 = 100万
        assert needs["critical_illness"] == 1000000.0
        # 医疗险：固定50万
        assert needs["medical"] == 500000.0
        # 意外险：10倍 = 200万
        assert needs["accident"] == 2000000.0
        # 寿险：无被抚养人，0
        assert needs["life"] == 0.0
    
    def test_calculate_coverage_need_default_income(self, calculator):
        """测试未提供年收入时使用默认值"""
        profile = UserProfile(
            age=30,
            occupation="自由职业",
            marital_status=MaritalStatus.SINGLE,
            has_children=False,
            children_count=0,
            has_dependents=False,
            dependents_count=0,
            family_size=1,
            income_range=IncomeRange.MEDIUM
        )
        
        needs = calculator.calculate_coverage_need(profile)
        
        # 默认年收入10万
        # 重疾险：5倍 = 50万
        assert needs["critical_illness"] == 500000.0
        # 医疗险：固定50万
        assert needs["medical"] == 500000.0
        # 意外险：10倍 = 100万
        assert needs["accident"] == 1000000.0
    
    # ========== calculate_premium_to_income_ratio 测试 ==========
    
    def test_calculate_premium_to_income_ratio_basic(self, calculator):
        """测试基本保费收入比计算"""
        ratio = calculator.calculate_premium_to_income_ratio(10000, 100000)
        assert ratio == 0.1
    
    def test_calculate_premium_to_income_ratio_zero_premium(self, calculator):
        """测试零保费"""
        ratio = calculator.calculate_premium_to_income_ratio(0, 100000)
        assert ratio == 0.0
    
    def test_calculate_premium_to_income_ratio_zero_income(self, calculator):
        """测试零收入应抛出异常"""
        with pytest.raises(ValueError, match="年收入必须大于0"):
            calculator.calculate_premium_to_income_ratio(10000, 0)
    
    def test_calculate_premium_to_income_ratio_negative_income(self, calculator):
        """测试负收入应抛出异常"""
        with pytest.raises(ValueError, match="年收入必须大于0"):
            calculator.calculate_premium_to_income_ratio(10000, -100000)
    
    def test_calculate_premium_to_income_ratio_negative_premium(self, calculator):
        """测试负保费应抛出异常"""
        with pytest.raises(ValueError, match="保费不能为负数"):
            calculator.calculate_premium_to_income_ratio(-10000, 100000)
    
    # ========== evaluate_premium_affordability 测试 ==========
    
    def test_evaluate_premium_affordability_affordable(self, calculator):
        """测试可承受保费评估"""
        result = calculator.evaluate_premium_affordability(8000, 100000, 1)
        
        assert result["is_affordable"] is True
        assert result["ratio"] == 0.08
        assert result["affordable_premium"] == 10000.0
        assert result["gap"] == -2000.0  # 在预算内
    
    def test_evaluate_premium_affordability_not_affordable(self, calculator):
        """测试不可承受保费评估"""
        result = calculator.evaluate_premium_affordability(20000, 100000, 1)
        
        assert result["is_affordable"] is False
        assert result["ratio"] == 0.2
        assert result["gap"] == 10000.0  # 超出预算
    
    def test_evaluate_premium_affordability_low_ratio(self, calculator):
        """测试低保费收入比的建议"""
        result = calculator.evaluate_premium_affordability(3000, 100000, 1)
        
        assert result["is_affordable"] is True
        assert "保费负担较轻" in result["recommendation"]
    
    def test_evaluate_premium_affordability_high_ratio(self, calculator):
        """测试高保费收入比的建议"""
        result = calculator.evaluate_premium_affordability(20000, 100000, 1)
        
        assert result["is_affordable"] is False
        assert "保费负担过重" in result["recommendation"]
    
    # ========== calculate_coverage_gap 测试 ==========
    
    def test_calculate_coverage_gap_full_gap(self, calculator, sample_profile):
        """测试完全无保障的缺口计算"""
        existing_coverage = {
            "critical_illness": 0.0,
            "medical": 0.0,
            "accident": 0.0,
            "life": 0.0
        }
        
        gap = calculator.calculate_coverage_gap(sample_profile, existing_coverage)
        
        # 年收入30万，有被抚养人
        assert gap["critical_illness_gap"] == 1500000.0
        assert gap["medical_gap"] == 500000.0
        assert gap["accident_gap"] == 3000000.0
        assert gap["life_gap"] == 3000000.0
        assert gap["total_gap"] == 8000000.0
    
    def test_calculate_coverage_gap_partial_gap(self, calculator, sample_profile):
        """测试部分保障的缺口计算"""
        existing_coverage = {
            "critical_illness": 500000.0,  # 已有50万
            "medical": 300000.0,  # 已有30万
            "accident": 1000000.0,  # 已有100万
            "life": 0.0
        }
        
        gap = calculator.calculate_coverage_gap(sample_profile, existing_coverage)
        
        # 重疾险缺口：150万 - 50万 = 100万
        assert gap["critical_illness_gap"] == 1000000.0
        # 医疗险缺口：50万 - 30万 = 20万
        assert gap["medical_gap"] == 200000.0
        # 意外险缺口：300万 - 100万 = 200万
        assert gap["accident_gap"] == 2000000.0
        # 寿险缺口：300万
        assert gap["life_gap"] == 3000000.0
    
    def test_calculate_coverage_gap_no_gap(self, calculator, sample_profile):
        """测试保障充足无缺口"""
        existing_coverage = {
            "critical_illness": 2000000.0,  # 超过推荐
            "medical": 600000.0,
            "accident": 4000000.0,
            "life": 4000000.0
        }
        
        gap = calculator.calculate_coverage_gap(sample_profile, existing_coverage)
        
        # 所有缺口应为0
        assert gap["critical_illness_gap"] == 0.0
        assert gap["medical_gap"] == 0.0
        assert gap["accident_gap"] == 0.0
        assert gap["life_gap"] == 0.0
        assert gap["total_gap"] == 0.0
        assert gap["priority_order"] == []
    
    def test_calculate_coverage_gap_priority_order(self, calculator, sample_profile):
        """测试优先配置顺序"""
        existing_coverage = {
            "critical_illness": 1000000.0,  # 缺口50万
            "medical": 0.0,  # 缺口50万
            "accident": 0.0,  # 缺口300万（最大）
            "life": 2000000.0  # 缺口100万
        }
        
        gap = calculator.calculate_coverage_gap(sample_profile, existing_coverage)
        
        # 优先顺序应按缺口大小降序：意外险 > 寿险 > 重疾险 > 医疗险
        assert gap["priority_order"] == ["accident", "life", "critical_illness", "medical"]
    
    # ========== 自定义配置测试 ==========
    
    def test_custom_config(self):
        """测试自定义配置"""
        custom_config = {
            "base_premium_ratio": 0.15,
            "critical_illness_multiplier": 3,
            "medical_fixed_coverage": 300000,
        }
        
        calculator = FinancialCalculatorTool(config=custom_config)
        
        # 测试自定义保费比例
        premium = calculator.calculate_affordable_premium(100000, 1)
        assert premium == 15000.0  # 15%
        
        # 测试自定义保障需求
        profile = UserProfile(
            age=30,
            occupation="测试",
            marital_status=MaritalStatus.SINGLE,
            has_children=False,
            children_count=0,
            has_dependents=False,
            dependents_count=0,
            family_size=1,
            income_range=IncomeRange.MEDIUM,
            annual_income=100000
        )
        
        needs = calculator.calculate_coverage_need(profile)
        assert needs["critical_illness"] == 300000.0  # 3倍
        assert needs["medical"] == 300000.0  # 固定30万
