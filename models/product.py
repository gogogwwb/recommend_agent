"""保险产品相关数据模型"""
from datetime import datetime
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class PremiumRange(BaseModel):
    """保费区间"""
    min_premium: float = Field(..., ge=0, description="最低保费")
    max_premium: float = Field(..., ge=0, description="最高保费")
    
    class Config:
        json_schema_extra = {
            "example": {
                "min_premium": 5000,
                "max_premium": 15000
            }
        }


class AgeRange(BaseModel):
    """年龄区间"""
    min_age: int = Field(..., ge=0, le=120, description="最小年龄")
    max_age: int = Field(..., ge=0, le=120, description="最大年龄")
    
    class Config:
        json_schema_extra = {
            "example": {
                "min_age": 18,
                "max_age": 60
            }
        }


class Product(BaseModel):
    """保险产品模型"""
    # 基本信息
    product_id: str = Field(..., description="产品ID")
    product_name: str = Field(..., description="产品名称")
    product_type: str = Field(..., description="产品类型（critical_illness, medical, accident, life）")
    provider: str = Field(..., description="保险公司")
    
    # 保障信息
    coverage_scope: List[str] = Field(default_factory=list, description="保障范围")
    coverage_amount_range: Optional[Dict[str, float]] = Field(None, description="保额范围")
    exclusions: List[str] = Field(default_factory=list, description="责任免除")
    
    # 费率信息
    premium_range: PremiumRange = Field(..., description="保费区间")
    payment_period: List[str] = Field(default_factory=list, description="缴费期限选项")
    coverage_period: List[str] = Field(default_factory=list, description="保障期限选项")
    
    # 投保规则
    age_range: AgeRange = Field(..., description="投保年龄范围")
    occupation_restrictions: List[str] = Field(default_factory=list, description="职业限制")
    health_requirements: List[str] = Field(default_factory=list, description="健康要求")
    region_restrictions: List[str] = Field(default_factory=list, description="地域限制")
    
    # 产品特点
    features: List[str] = Field(default_factory=list, description="产品特点")
    advantages: List[str] = Field(default_factory=list, description="产品优势")
    suitable_for: List[str] = Field(default_factory=list, description="适用人群")
    
    # 理赔信息
    claim_process: Optional[str] = Field(None, description="理赔流程")
    waiting_period_days: int = Field(default=0, ge=0, description="等待期（天）")
    deductible: float = Field(default=0, ge=0, description="免赔额")
    
    # 状态
    is_available: bool = Field(default=True, description="是否可售")
    is_featured: bool = Field(default=False, description="是否推荐产品")
    
    # 元数据
    created_at: datetime = Field(default_factory=datetime.now, description="创建时间")
    updated_at: datetime = Field(default_factory=datetime.now, description="更新时间")
    version: int = Field(default=1, description="版本号")
    
    # 向量化特征（用于RAG检索）
    embedding: Optional[List[float]] = Field(None, description="产品特征向量")
    
    class Config:
        json_schema_extra = {
            "example": {
                "product_id": "prod-ci-001",
                "product_name": "康健一生重大疾病保险",
                "product_type": "critical_illness",
                "provider": "平安保险",
                "coverage_scope": ["重大疾病", "轻症", "中症", "身故"],
                "premium_range": {
                    "min_premium": 5000,
                    "max_premium": 15000
                },
                "age_range": {
                    "min_age": 18,
                    "max_age": 60
                },
                "is_available": True
            }
        }


class CoverageGap(BaseModel):
    """保障缺口分析模型"""
    # 各维度保障缺口
    critical_illness_gap: float = Field(default=0, ge=0, description="重疾险保障缺口")
    medical_gap: float = Field(default=0, ge=0, description="医疗险保障缺口")
    accident_gap: float = Field(default=0, ge=0, description="意外险保障缺口")
    life_insurance_gap: float = Field(default=0, ge=0, description="寿险保障缺口")
    
    # 当前保障情况
    current_critical_illness_coverage: float = Field(default=0, ge=0, description="当前重疾险保额")
    current_medical_coverage: float = Field(default=0, ge=0, description="当前医疗险保额")
    current_accident_coverage: float = Field(default=0, ge=0, description="当前意外险保额")
    current_life_coverage: float = Field(default=0, ge=0, description="当前寿险保额")
    
    # 推荐保障
    recommended_critical_illness: float = Field(default=0, ge=0, description="推荐重疾险保额")
    recommended_medical: float = Field(default=0, ge=0, description="推荐医疗险保额")
    recommended_accident: float = Field(default=0, ge=0, description="推荐意外险保额")
    recommended_life: float = Field(default=0, ge=0, description="推荐寿险保额")
    
    # 分析说明
    gap_analysis: str = Field(default="", description="保障缺口分析说明")
    priority_recommendations: List[str] = Field(default_factory=list, description="优先推荐的保障类型")
    
    class Config:
        json_schema_extra = {
            "example": {
                "critical_illness_gap": 300000,
                "medical_gap": 500000,
                "accident_gap": 1000000,
                "life_insurance_gap": 0,
                "current_critical_illness_coverage": 200000,
                "recommended_critical_illness": 500000,
                "gap_analysis": "您当前的重疾险保额偏低，建议增加至年收入的5倍",
                "priority_recommendations": ["critical_illness", "medical"]
            }
        }


class RecommendationResult(BaseModel):
    """推荐结果模型"""
    # 推荐产品
    product: Product = Field(..., description="推荐的产品")
    
    # 推荐评分
    rank: int = Field(..., ge=1, description="推荐排名")
    match_score: float = Field(..., ge=0, le=100, description="匹配分数")
    confidence_score: float = Field(..., ge=0, le=1, description="推荐置信度")
    
    # 推荐理由
    explanation: str = Field(..., description="推荐理由")
    match_dimensions: Dict[str, float] = Field(default_factory=dict, description="各维度匹配分数")
    
    # 产品优势
    why_suitable: List[str] = Field(default_factory=list, description="为什么适合用户")
    key_benefits: List[str] = Field(default_factory=list, description="关键收益")
    
    # 合规状态
    compliance_passed: bool = Field(default=False, description="是否通过合规检查")
    compliance_issues: List[str] = Field(default_factory=list, description="合规问题")
    
    # 元数据
    recommended_at: datetime = Field(default_factory=datetime.now, description="推荐时间")
    
    class Config:
        json_schema_extra = {
            "example": {
                "product": {
                    "product_id": "prod-ci-001",
                    "product_name": "康健一生重大疾病保险",
                    "product_type": "critical_illness"
                },
                "rank": 1,
                "match_score": 85.5,
                "confidence_score": 0.92,
                "explanation": "该产品保障范围全面，保费适中，非常适合您的家庭情况",
                "match_dimensions": {
                    "age_match": 95,
                    "income_match": 88,
                    "risk_match": 82,
                    "coverage_match": 90
                },
                "why_suitable": [
                    "保障范围覆盖120种重疾",
                    "保费在您的预算范围内",
                    "适合有家庭责任的人群"
                ],
                "compliance_passed": True
            }
        }
