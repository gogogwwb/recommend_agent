"""用户相关数据模型"""
from datetime import datetime
from enum import Enum
from typing import Optional, List
from pydantic import BaseModel, Field, field_validator


class MaritalStatus(str, Enum):
    """婚姻状况"""
    SINGLE = "single"
    MARRIED = "married"
    DIVORCED = "divorced"
    WIDOWED = "widowed"


class IncomeRange(str, Enum):
    """收入区间"""
    LOW = "low"  # <5万
    MEDIUM_LOW = "medium_low"  # 5-10万
    MEDIUM = "medium"  # 10-20万
    MEDIUM_HIGH = "medium_high"  # 20-50万
    HIGH = "high"  # >50万


class RiskPreference(str, Enum):
    """风险偏好"""
    CONSERVATIVE = "conservative"  # 保守型
    BALANCED = "balanced"  # 稳健型
    AGGRESSIVE = "aggressive"  # 进取型


class HealthStatus(str, Enum):
    """健康状况"""
    EXCELLENT = "excellent"  # 优秀
    GOOD = "good"  # 良好
    FAIR = "fair"  # 一般
    POOR = "poor"  # 较差


class UserProfile(BaseModel):
    """用户画像模型"""
    # 基本信息
    age: int = Field(..., ge=0, le=120, description="年龄")
    occupation: str = Field(..., min_length=1, description="职业")
    marital_status: MaritalStatus = Field(..., description="婚姻状况")
    
    # 家庭结构
    has_children: bool = Field(default=False, description="是否有子女")
    children_count: int = Field(default=0, ge=0, description="子女数量")
    has_dependents: bool = Field(default=False, description="是否有被抚养人")
    dependents_count: int = Field(default=0, ge=0, description="被抚养人数量")
    family_size: int = Field(default=1, ge=1, description="家庭人数")
    
    # 经济状况
    income_range: IncomeRange = Field(..., description="收入区间")
    annual_income: Optional[float] = Field(None, ge=0, description="年收入（具体金额）")
    
    # 风险偏好
    risk_preference: Optional[RiskPreference] = Field(None, description="风险偏好")
    risk_score: Optional[float] = Field(None, ge=0, le=100, description="风险评分")
    
    # 健康状况
    health_status: Optional[HealthStatus] = Field(None, description="健康状况")
    has_medical_history: bool = Field(default=False, description="是否有病史")
    medical_conditions: List[str] = Field(default_factory=list, description="已有疾病")
    
    # 地理位置
    city: Optional[str] = Field(None, description="所在城市")
    province: Optional[str] = Field(None, description="所在省份")
    
    # 元数据
    created_at: datetime = Field(default_factory=datetime.now, description="创建时间")
    updated_at: datetime = Field(default_factory=datetime.now, description="更新时间")
    
    @field_validator('children_count')
    @classmethod
    def validate_children_count(cls, v, info):
        """验证子女数量与has_children一致"""
        if info.data.get('has_children') and v == 0:
            raise ValueError("has_children为True时，children_count必须大于0")
        if not info.data.get('has_children') and v > 0:
            raise ValueError("has_children为False时，children_count必须为0")
        return v
    
    @field_validator('dependents_count')
    @classmethod
    def validate_dependents_count(cls, v, info):
        """验证被抚养人数量与has_dependents一致"""
        if info.data.get('has_dependents') and v == 0:
            raise ValueError("has_dependents为True时，dependents_count必须大于0")
        if not info.data.get('has_dependents') and v > 0:
            raise ValueError("has_dependents为False时，dependents_count必须为0")
        return v
    
    class Config:
        json_schema_extra = {
            "example": {
                "age": 30,
                "occupation": "软件工程师",
                "marital_status": "married",
                "has_children": True,
                "children_count": 1,
                "has_dependents": False,
                "dependents_count": 0,
                "family_size": 3,
                "income_range": "medium_high",
                "annual_income": 300000,
                "risk_preference": "balanced",
                "health_status": "good"
            }
        }


class ExistingProduct(BaseModel):
    """已有保障产品模型"""
    product_id: str = Field(..., description="产品ID")
    product_name: str = Field(..., description="产品名称")
    product_type: str = Field(..., description="产品类型（重疾险、医疗险、意外险、寿险）")
    
    # 保障信息
    coverage_amount: float = Field(..., ge=0, description="保额")
    premium: float = Field(..., ge=0, description="保费")
    coverage_scope: List[str] = Field(default_factory=list, description="保障范围")
    
    # 时间信息
    purchase_date: Optional[datetime] = Field(None, description="购买日期")
    coverage_start_date: Optional[datetime] = Field(None, description="保障开始日期")
    coverage_end_date: Optional[datetime] = Field(None, description="保障结束日期")
    
    # 状态
    is_active: bool = Field(default=True, description="是否有效")
    
    class Config:
        json_schema_extra = {
            "example": {
                "product_id": "prod-001",
                "product_name": "平安福重疾险",
                "product_type": "critical_illness",
                "coverage_amount": 500000,
                "premium": 8000,
                "coverage_scope": ["重大疾病", "轻症", "中症"],
                "is_active": True
            }
        }
