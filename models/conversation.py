"""对话相关数据模型"""
from datetime import datetime
from enum import Enum
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


class MessageRole(str, Enum):
    """消息角色"""
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


class IntentType(str, Enum):
    """意图类型"""
    CONSULT_COVERAGE = "consult_coverage"  # 咨询保障
    COMPARE_PRODUCTS = "compare_products"  # 比较产品
    MODIFY_INFO = "modify_info"  # 修改信息
    CONFIRM_RECOMMENDATION = "confirm_recommendation"  # 确认推荐
    ASK_QUESTION = "ask_question"  # 提问
    PROVIDE_INFO = "provide_info"  # 提供信息
    CHITCHAT = "chitchat"  # 闲聊
    REQUEST_EXPLANATION = "request_explanation"  # 请求解释
    OTHER = "other"  # 其他


class Message(BaseModel):
    """消息模型"""
    role: MessageRole = Field(..., description="消息角色")
    content: str = Field(..., min_length=1, description="消息内容")
    
    # 元数据
    timestamp: datetime = Field(default_factory=datetime.now, description="时间戳")
    message_id: Optional[str] = Field(None, description="消息ID")
    
    # 意图和槽位（仅用户消息）
    intent: Optional[IntentType] = Field(None, description="用户意图")
    extracted_slots: Dict[str, Any] = Field(default_factory=dict, description="提取的槽位")
    
    # Agent信息（仅助手消息）
    agent_name: Optional[str] = Field(None, description="生成消息的Agent名称")
    thinking_process: Optional[str] = Field(None, description="思考过程")
    
    class Config:
        json_schema_extra = {
            "example": {
                "role": "user",
                "content": "我今年30岁，想了解重疾险",
                "intent": "consult_coverage",
                "extracted_slots": {
                    "age": 30,
                    "interested_product_type": "critical_illness"
                }
            }
        }


class SessionStatus(str, Enum):
    """会话状态"""
    ACTIVE = "active"  # 活跃
    BACKGROUND = "background"  # 后台运行
    COMPLETED = "completed"  # 已完成
    ABANDONED = "abandoned"  # 已放弃
    ARCHIVED = "archived"  # 已归档


class SessionContext(BaseModel):
    """会话上下文模型"""
    session_id: str = Field(..., description="会话ID")
    user_id: str = Field(..., description="用户ID")
    
    # 会话状态
    status: SessionStatus = Field(default=SessionStatus.ACTIVE, description="会话状态")
    background_mode: bool = Field(default=False, description="是否后台运行")
    
    # 时间信息
    created_at: datetime = Field(default_factory=datetime.now, description="创建时间")
    last_activity_at: datetime = Field(default_factory=datetime.now, description="最后活跃时间")
    completed_at: Optional[datetime] = Field(None, description="完成时间")
    
    # 会话统计
    turn_count: int = Field(default=0, ge=0, description="对话轮数")
    total_messages: int = Field(default=0, ge=0, description="总消息数")
    
    class Config:
        json_schema_extra = {
            "example": {
                "session_id": "sess-001",
                "user_id": "user-001",
                "status": "active",
                "turn_count": 5,
                "total_messages": 10
            }
        }
