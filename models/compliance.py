"""合规相关数据模型"""
from datetime import datetime
from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field


class ComplianceCheckType(str, Enum):
    """合规检查类型"""
    AGE_CHECK = "age_check"  # 年龄检查
    OCCUPATION_CHECK = "occupation_check"  # 职业检查
    HEALTH_CHECK = "health_check"  # 健康检查
    REGION_CHECK = "region_check"  # 地域检查
    INCOME_CHECK = "income_check"  # 收入检查


class CheckResult(str, Enum):
    """检查结果"""
    PASSED = "passed"  # 通过
    FAILED = "failed"  # 未通过
    WARNING = "warning"  # 警告
    MANUAL_REVIEW = "manual_review"  # 需人工审核


class ComplianceCheck(BaseModel):
    """合规检查模型"""
    check_type: ComplianceCheckType = Field(..., description="检查类型")
    check_result: CheckResult = Field(..., description="检查结果")
    
    # 检查详情
    check_description: str = Field(..., description="检查描述")
    reason: Optional[str] = Field(None, description="未通过原因")
    recommendation: Optional[str] = Field(None, description="建议")
    
    # 检查数据
    checked_value: Optional[str] = Field(None, description="被检查的值")
    expected_value: Optional[str] = Field(None, description="期望的值")
    
    # 元数据
    checked_at: datetime = Field(default_factory=datetime.now, description="检查时间")
    
    class Config:
        json_schema_extra = {
            "example": {
                "check_type": "age_check",
                "check_result": "passed",
                "check_description": "年龄在投保范围内",
                "checked_value": "30",
                "expected_value": "18-60"
            }
        }


class ComplianceResult(BaseModel):
    """合规检查结果汇总"""
    product_id: str = Field(..., description="产品ID")
    user_id: str = Field(..., description="用户ID")
    
    # 总体结果
    eligible: bool = Field(..., description="是否符合投保条件")
    overall_result: CheckResult = Field(..., description="总体检查结果")
    
    # 详细检查
    checks: List[ComplianceCheck] = Field(default_factory=list, description="详细检查列表")
    
    # 不通过原因
    failed_checks: List[str] = Field(default_factory=list, description="未通过的检查")
    reasons: List[str] = Field(default_factory=list, description="不符合原因")
    
    # 建议
    recommendations: List[str] = Field(default_factory=list, description="改进建议")
    
    # 元数据
    checked_at: datetime = Field(default_factory=datetime.now, description="检查时间")
    
    class Config:
        json_schema_extra = {
            "example": {
                "product_id": "prod-ci-001",
                "user_id": "user-001",
                "eligible": True,
                "overall_result": "passed",
                "checks": [
                    {
                        "check_type": "age_check",
                        "check_result": "passed",
                        "check_description": "年龄在投保范围内"
                    }
                ],
                "failed_checks": [],
                "reasons": []
            }
        }


class DisclosureItem(BaseModel):
    """信息披露项"""
    title: str = Field(..., description="披露项标题")
    content: str = Field(..., description="披露内容")
    is_mandatory: bool = Field(default=True, description="是否必须披露")
    category: str = Field(..., description="披露类别")
    
    class Config:
        json_schema_extra = {
            "example": {
                "title": "保险责任",
                "content": "本产品保障120种重大疾病...",
                "is_mandatory": True,
                "category": "insurance_liability"
            }
        }


class DisclosureInfo(BaseModel):
    """信息披露模型"""
    product_id: str = Field(..., description="产品ID")
    
    # 披露内容
    insurance_liability: str = Field(..., description="保险责任")
    liability_exclusions: str = Field(..., description="责任免除")
    cooling_off_period: str = Field(default="15天犹豫期", description="犹豫期")
    fee_description: str = Field(..., description="费用说明")
    
    # 详细披露项
    disclosure_items: List[DisclosureItem] = Field(default_factory=list, description="详细披露项")
    
    # 用户确认
    user_acknowledged: bool = Field(default=False, description="用户是否已确认")
    acknowledged_at: Optional[datetime] = Field(None, description="确认时间")
    
    # 元数据
    generated_at: datetime = Field(default_factory=datetime.now, description="生成时间")
    version: str = Field(default="1.0", description="版本号")
    
    class Config:
        json_schema_extra = {
            "example": {
                "product_id": "prod-ci-001",
                "insurance_liability": "保障120种重大疾病，包括恶性肿瘤、急性心肌梗塞等",
                "liability_exclusions": "投保前已患疾病、故意犯罪、酒驾等情况不予赔付",
                "cooling_off_period": "15天犹豫期",
                "fee_description": "保费按年缴纳，不含额外管理费",
                "user_acknowledged": False
            }
        }
