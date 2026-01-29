"""
Qwen 2.5-VL 多模态模型服务
通过 DashScope API 调用 Qwen 视觉语言模型
"""

import base64
from typing import List, Optional, Generator, Any
import dashscope
from dashscope import MultiModalConversation
from http import HTTPStatus

from app.config import settings


class QwenVLService:
    """Qwen 2.5-VL 多模态服务"""
    
    def __init__(self):
        """初始化服务"""
        dashscope.api_key = settings.dashscope_api_key
        self.model = settings.qwen_vl_model
    
    def _build_messages(
        self,
        text: str,
        image_base64: Optional[str] = None,
        history: Optional[List[dict]] = None,
        system_prompt: Optional[str] = None
    ) -> List[dict]:
        """
        构建消息列表
        
        Args:
            text: 用户输入的文本
            image_base64: Base64编码的图片
            history: 历史对话记录
            system_prompt: 系统提示词
            
        Returns:
            格式化的消息列表
        """
        messages = []
        
        # 添加系统提示
        if system_prompt:
            messages.append({
                "role": "system",
                "content": [{"text": system_prompt}]
            })
        
        # 添加历史记录
        if history:
            for msg in history:
                messages.append(msg)
        
        # 构建当前用户消息
        user_content = []
        
        # 添加图片
        if image_base64:
            # 确保 base64 格式正确
            if not image_base64.startswith("data:"):
                image_base64 = f"data:image/jpeg;base64,{image_base64}"
            user_content.append({"image": image_base64})
        
        # 添加文本
        user_content.append({"text": text})
        
        messages.append({
            "role": "user",
            "content": user_content
        })
        
        return messages
    
    def chat(
        self,
        text: str,
        image_base64: Optional[str] = None,
        history: Optional[List[dict]] = None,
        system_prompt: Optional[str] = None
    ) -> dict:
        """
        同步对话
        
        Args:
            text: 用户输入
            image_base64: 可选的图片
            history: 对话历史
            system_prompt: 系统提示
            
        Returns:
            响应字典，包含 content, usage 等
        """
        messages = self._build_messages(text, image_base64, history, system_prompt)
        
        try:
            response = MultiModalConversation.call(
                model=self.model,
                messages=messages
            )
            
            if response.status_code == HTTPStatus.OK:
                return {
                    "success": True,
                    "content": response.output.choices[0].message.content[0]["text"],
                    "usage": {
                        "input_tokens": response.usage.input_tokens,
                        "output_tokens": response.usage.output_tokens
                    },
                    "model": self.model
                }
            else:
                return {
                    "success": False,
                    "error": f"API Error: {response.code} - {response.message}",
                    "model": self.model
                }
                
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "model": self.model
            }
    
    def chat_stream(
        self,
        text: str,
        image_base64: Optional[str] = None,
        history: Optional[List[dict]] = None,
        system_prompt: Optional[str] = None
    ) -> Generator[str, None, None]:
        """
        流式对话
        
        Args:
            text: 用户输入
            image_base64: 可选的图片
            history: 对话历史
            system_prompt: 系统提示
            
        Yields:
            响应文本片段
        """
        messages = self._build_messages(text, image_base64, history, system_prompt)
        
        try:
            responses = MultiModalConversation.call(
                model=self.model,
                messages=messages,
                stream=True,
                incremental_output=True
            )
            
            for response in responses:
                if response.status_code == HTTPStatus.OK:
                    if response.output.choices:
                        content = response.output.choices[0].message.content
                        if content and len(content) > 0:
                            yield content[0].get("text", "")
                else:
                    yield f"[Error: {response.code}]"
                    
        except Exception as e:
            yield f"[Error: {str(e)}]"
    
    def analyze_image(
        self,
        image_base64: str,
        question: str = "请详细描述这张图片的内容"
    ) -> dict:
        """
        图像分析
        
        Args:
            image_base64: Base64编码的图片
            question: 关于图片的问题
            
        Returns:
            分析结果
        """
        return self.chat(
            text=question,
            image_base64=image_base64,
            system_prompt="你是一个专业的图像分析助手，请仔细观察图片并给出详细、准确的描述。"
        )


# 单例
_qwen_service: Optional[QwenVLService] = None


def get_qwen_service() -> QwenVLService:
    """获取 Qwen VL 服务单例"""
    global _qwen_service
    if _qwen_service is None:
        _qwen_service = QwenVLService()
    return _qwen_service
