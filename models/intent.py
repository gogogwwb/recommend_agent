"""意图检测模型

本模块定义了Profile Subgraph中用于意图检测的数据模型。
支持检测用户是在提问还是提供画像信息，并识别问题类型。

关键特性：
- QuestionType枚举：定义可回答的问题类型
- DetectedIntent模型：存储检测到的意图和提取的实体
- QUESTION_PATTERNS：用于模式匹配的正则表达式
- PRODUCT_TYPE_NAMES：中文产品类型名称到英文的映射
"""
from enum import Enum
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field


class QuestionType(str, Enum):
    """Profile Subgraph可以回答的问题类型
    
    Attributes:
        TERMINOLOGY: 术语问题，如"什么是重疾险？"
        COMPARISON: 产品对比问题，如"重疾险和医疗险有什么区别？"
        CLAIM_PROCESS: 理赔流程问题，如"怎么理赔？"
        GENERAL: 通用保险问题
        NON_INSURANCE: 离题问题（与保险无关）
    """
    TERMINOLOGY = "terminology"  # "什么是重疾险？"
    COMPARISON = "comparison"    # "重疾险和医疗险有什么区别？"
    CLAIM_PROCESS = "claim"      # "怎么理赔？"
    GENERAL = "general"          # 通用保险问题
    NON_INSURANCE = "non_insurance"  # 离题


class DetectedIntent(BaseModel):
    """从消息中检测到的用户意图
    
    Attributes:
        intent_type: 意图类型（ask_question, provide_info, modify_info等）
        question_type: 问题类型（仅当intent_type为ask_question时有效）
        extracted_entities: 提取的实体（如术语、产品类型）
        confidence: 检测置信度（0-1）
    """
    intent_type: str = Field(
        ...,
        description="意图类型：ask_question, provide_info, modify_info等"
    )
    question_type: Optional[QuestionType] = Field(
        None,
        description="问题类型（仅当intent_type为ask_question时有效）"
    )
    extracted_entities: Dict[str, Any] = Field(
        default_factory=dict,
        description="提取的实体，如{'term': '重疾险'}, {'product_types': ['critical_illness', 'medical']}"
    )
    confidence: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="检测置信度（0-1）"
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "intent_type": "ask_question",
                "question_type": "terminology",
                "extracted_entities": {"term": "重疾险"},
                "confidence": 0.95
            }
        }


# 用于意图检测的问题模式
# 键为QuestionType枚举值，值为正则表达式列表
QUESTION_PATTERNS: Dict[str, List[str]] = {
    "terminology": [
        r"什么是(.+?)\？",
        r"(.+?)是什么",
        r"解释一下(.+?)",
        r"(.+?)的意思",
        r"请问(.+?)是什么",
        r"(.+?)是指什么",
        r"什么叫(.+?)",
    ],
    "comparison": [
        r"(.+?)和(.+?)有什么区别",
        r"(.+?)与(.+?)的区别",
        r"比较一下(.+?)和(.+?)",
        r"(.+?)好还是(.+?)好",
        r"(.+?)和(.+?)哪个好",
        r"(.+?)与(.+?)对比",
    ],
    "claim": [
        r"怎么理赔",
        r"理赔流程",
        r"如何申请理赔",
        r"理赔需要什么",
        r"怎么办理赔",
        r"理赔怎么操作",
        r"理赔步骤",
    ],
}


# 产品类型名称映射（中文到英文）
# 用于将用户输入的中文产品类型转换为系统内部使用的英文标识
PRODUCT_TYPE_NAMES: Dict[str, str] = {
    "重疾险": "critical_illness",
    "重大疾病保险": "critical_illness",
    "重疾": "critical_illness",
    "医疗险": "medical",
    "医疗保险": "medical",
    "医疗": "medical",
    "意外险": "accident",
    "意外伤害保险": "accident",
    "意外": "accident",
    "寿险": "life",
    "人寿保险": "life",
    "定期寿险": "life",
    "终身寿险": "life",
}


def get_product_type_name(chinese_name: str) -> Optional[str]:
    """将中文产品类型名称转换为英文标识
    
    Args:
        chinese_name: 中文产品类型名称
        
    Returns:
        英文产品类型标识，如果未找到则返回None
    """
    return PRODUCT_TYPE_NAMES.get(chinese_name)


def get_all_product_type_names() -> List[str]:
    """获取所有支持的中文产品类型名称
    
    Returns:
        中文产品类型名称列表
    """
    return list(PRODUCT_TYPE_NAMES.keys())
