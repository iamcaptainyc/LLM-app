"""
Pydantic 数据模型定义
定义 API 请求/响应的数据结构
"""

from typing import Optional, List, Literal, Any
from pydantic import BaseModel, Field
from datetime import datetime


class MultimodalContent(BaseModel):
    """多模态内容"""
    type: Literal["text", "image"] = "text"
    text: Optional[str] = None
    image_base64: Optional[str] = None  # Base64 编码的图片
    image_url: Optional[str] = None


class ChatMessage(BaseModel):
    """聊天消息"""
    role: Literal["user", "assistant", "system"] = "user"
    content: str | List[MultimodalContent]
    timestamp: Optional[datetime] = Field(default_factory=datetime.now)


class ChatRequest(BaseModel):
    """聊天请求"""
    messages: List[ChatMessage]
    image_base64: Optional[str] = None  # 可选的附加图片
    session_id: Optional[str] = None    # 会话ID
    use_tools: bool = Field(default=True, description="是否启用工具调用")
    use_rag: bool = Field(default=True, description="是否启用知识检索")
    stream: bool = Field(default=False, description="是否流式输出")
    
    class Config:
        json_schema_extra = {
            "example": {
                "messages": [
                    {"role": "user", "content": "这张图片里有什么?"}
                ],
                "image_base64": "iVBORw0KGgo...",
                "use_tools": True,
                "use_rag": True
            }
        }


class ToolCall(BaseModel):
    """工具调用记录"""
    tool_name: str
    tool_input: dict
    tool_output: Any
    

class ChatResponse(BaseModel):
    """聊天响应"""
    response: str
    tool_calls: Optional[List[ToolCall]] = None
    retrieved_docs: Optional[List[str]] = None
    model: str = "qwen-vl-max"
    usage: Optional[dict] = None
    
    class Config:
        json_schema_extra = {
            "example": {
                "response": "这张图片展示了一只可爱的猫咪...",
                "tool_calls": [],
                "retrieved_docs": [],
                "model": "qwen-vl-max"
            }
        }


class HealthResponse(BaseModel):
    """健康检查响应"""
    status: str = "healthy"
    version: str
    model: str
