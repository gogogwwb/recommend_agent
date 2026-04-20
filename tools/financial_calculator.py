"""
金融计算工具

负责保险相关的金融计算，包括：
- 可承受保费计算
- 保障需求计算
- 保费收入比计算
"""
from typing import Dict, Any, Optional
from models.user import UserProfile


class FinancialCalculatorTool:
    """金融计算工具 - 内部模块
    
    提供保险相关的金融计算功能，帮助用户了解自己的保障需求和保费预算。
    
    计算规则：
    - 可承受保费：建议保费不超过年收入的10%-15%，根据家庭人数调整
    - 保障需求：基于年收入和家庭结构计算各类型保险的推荐保额
    """
    
    # 默认配置
    DEFAULT_CONFIG = {
        # 保费收入比基础比例
        "base_premium_ratio": 0.10,  # 10%
        # 家庭人数调整系数（每增加一人，比例降低）
        "family_size_adjustment": 0.02,
        # 最低保费收入比
        "min_premium_ratio": 0.05,  # 5%
        # 最高保费收入比
        "max_premium_ratio": 0.15,  # 15%
        # 重疾险保额倍数
        "critical_illness_multiplier": 5,
        # 医疗险固定保额
        "medical_fixed_coverage": 500000,
        # 意外险保额倍数
        "accident_multiplier": 10,
        # 寿险保额倍数（有被抚养人时）
        "life_multiplier": 10,
        # 默认年收入（当用户未提供时）
        "default_annual_income": 100000,
    }
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """初始化金融计算工具
        
        Args:
            config: 配置字典，可覆盖默认配置
        """
        self.config = {**self.DEFAULT_CONFIG, **(config or {})}
    
    def calculate_affordable_premium(
        self, 
        annual_income: float, 
        family_size: int
    ) -> float:
        """计算可承受保费
        
        规则：建议保费不超过年收入的10%-15%，根据家庭人数调整。
        家庭人数越多，可承受保费比例越低。
        
        Args:
            annual_income: 年收入（元）
            family_size: 家庭人数
            
        Returns:
            可承受保费（元/年）
            
        Raises:
            ValueError: 如果年收入为负数或家庭人数小于1
        """
        # 参数验证
        if annual_income < 0:
            raise ValueError("年收入不能为负数")
        if family_size < 1:
            raise ValueError("家庭人数必须大于等于1")
        
        # 基础比例
        base_ratio = self.config["base_premium_ratio"]
        
        # 家庭人数调整（人数越多，比例越低）
        family_adjustment = self.config["family_size_adjustment"] * (family_size - 1)
        adjusted_ratio = base_ratio - family_adjustment
        
        # 限制在合理范围内
        adjusted_ratio = max(
            self.config["min_premium_ratio"],
            min(self.config["max_premium_ratio"], adjusted_ratio)
        )
        
        return annual_income * adjusted_ratio
    
    def calculate_coverage_need(self, user_profile: UserProfile) -> Dict[str, float]:
        """计算保障需求
        
        根据用户画像计算各类型保险的推荐保额。
        
        计算规则：
        - 重疾险：5倍年收入（覆盖治疗费用和收入损失）
        - 医疗险：固定50万（覆盖大额医疗费用）
        - 意外险：10倍年收入（覆盖意外身故/伤残）
        - 寿险：有被抚养人时，10倍年收入；否则为0
        
        Args:
            user_profile: 用户画像
            
        Returns:
            各类型保险的推荐保额字典：
            {
                "critical_illness": 重疾险保额,
                "medical": 医疗险保额,
                "accident": 意外险保额,
                "life": 寿险保额
            }
        """
        # 获取年收入，如果未提供则使用默认值
        annual_income = user_profile.annual_income or self.config["default_annual_income"]
        
        # 重疾险：5倍年收入
        critical_illness = annual_income * self.config["critical_illness_multiplier"]
        
        # 医疗险：固定50万
        medical = float(self.config["medical_fixed_coverage"])
        
        # 意外险：10倍年收入
        accident = annual_income * self.config["accident_multiplier"]
        
        # 寿险：有被抚养人时，10倍年收入
        life = annual_income * self.config["life_multiplier"] if user_profile.has_dependents else 0.0
        
        return {
            "critical_illness": critical_illness,
            "medical": medical,
            "accident": accident,
            "life": life
        }
    
    def calculate_premium_to_income_ratio(
        self, 
        total_premium: float, 
        annual_income: float
    ) -> float:
        """计算保费收入比
        
        用于评估保费负担是否合理。
        
        Args:
            total_premium: 总保费（元/年）
            annual_income: 年收入（元）
            
        Returns:
            保费收入比（0-1之间）
            
        Raises:
            ValueError: 如果年收入为0或负数
        """
        if annual_income <= 0:
            raise ValueError("年收入必须大于0")
        
        if total_premium < 0:
            raise ValueError("保费不能为负数")
        
        return total_premium / annual_income
    
    def evaluate_premium_affordability(
        self, 
        total_premium: float, 
        annual_income: float,
        family_size: int = 1
    ) -> Dict[str, Any]:
        """评估保费可承受性
        
        综合评估保费是否在用户可承受范围内，并提供建议。
        
        Args:
            total_premium: 总保费（元/年）
            annual_income: 年收入（元）
            family_size: 家庭人数
            
        Returns:
            评估结果字典：
            {
                "is_affordable": 是否可承受,
                "ratio": 保费收入比,
                "affordable_premium": 可承受保费,
                "gap": 差额（正数表示超出预算，负数表示在预算内）,
                "recommendation": 建议
            }
        """
        # 计算可承受保费
        affordable_premium = self.calculate_affordable_premium(annual_income, family_size)
        
        # 计算保费收入比
        ratio = self.calculate_premium_to_income_ratio(total_premium, annual_income)
        
        # 判断是否可承受
        is_affordable = total_premium <= affordable_premium
        
        # 计算差额
        gap = total_premium - affordable_premium
        
        # 生成建议
        if is_affordable:
            if ratio <= self.config["min_premium_ratio"]:
                recommendation = "保费负担较轻，可考虑增加保障额度或配置更多险种。"
            else:
                recommendation = "保费在合理范围内，建议保持当前配置。"
        else:
            if ratio > self.config["max_premium_ratio"]:
                recommendation = "保费负担过重，建议减少保障额度或选择更经济的方案。"
            else:
                recommendation = "保费略高于建议预算，可适当调整或保持当前配置。"
        
        return {
            "is_affordable": is_affordable,
            "ratio": ratio,
            "affordable_premium": affordable_premium,
            "gap": gap,
            "recommendation": recommendation
        }
    
    def calculate_coverage_gap(
        self,
        user_profile: UserProfile,
        existing_coverage: Dict[str, float]
    ) -> Dict[str, Any]:
        """计算保障缺口
        
        对比推荐保额和已有保障，计算各类型保险的缺口。
        
        Args:
            user_profile: 用户画像
            existing_coverage: 已有保障字典，格式为：
                {
                    "critical_illness": 已有重疾险保额,
                    "medical": 已有医疗险保额,
                    "accident": 已有意外险保额,
                    "life": 已有寿险保额
                }
            
        Returns:
            保障缺口字典：
            {
                "critical_illness_gap": 重疾险缺口,
                "medical_gap": 医疗险缺口,
                "accident_gap": 意外险缺口,
                "life_gap": 寿险缺口,
                "total_gap": 总缺口,
                "priority_order": 优先配置顺序
            }
        """
        # 计算推荐保额
        recommended = self.calculate_coverage_need(user_profile)
        
        # 计算各类型缺口
        gaps = {}
        for coverage_type in ["critical_illness", "medical", "accident", "life"]:
            existing = existing_coverage.get(coverage_type, 0.0)
            recommended_amount = recommended[coverage_type]
            gap = max(0.0, recommended_amount - existing)
            gaps[f"{coverage_type}_gap"] = gap
        
        # 计算总缺口
        total_gap = sum(gaps.values())
        
        # 确定优先配置顺序（按缺口大小排序）
        gap_items = [
            ("critical_illness", gaps["critical_illness_gap"]),
            ("medical", gaps["medical_gap"]),
            ("accident", gaps["accident_gap"]),
            ("life", gaps["life_gap"]),
        ]
        # 过滤掉缺口为0的项，按缺口大小降序排序
        priority_order = [
            item[0] for item in sorted(
                [item for item in gap_items if item[1] > 0],
                key=lambda x: x[1],
                reverse=True
            )
        ]
        
        return {
            **gaps,
            "total_gap": total_gap,
            "priority_order": priority_order
        }
