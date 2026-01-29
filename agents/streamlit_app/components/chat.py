"""
对话组件
处理聊天消息的显示
"""

import streamlit as st
from typing import List, Dict, Any, Optional


def render_message(
    role: str,
    content: str,
    tool_calls: Optional[List[Dict]] = None,
    retrieved_docs: Optional[List[str]] = None,
    image_base64: Optional[str] = None
):
    """
    渲染单条消息
    
    Args:
        role: 角色 (user/assistant)
        content: 消息内容
        tool_calls: 工具调用记录
        retrieved_docs: 检索到的文档
        image_base64: 附带的图片
    """
    if role == "user":
        with st.chat_message("user", avatar="🧑"):
            # 显示图片（如果有）
            if image_base64:
                st.image(
                    f"data:image/jpeg;base64,{image_base64}",
                    caption="上传的图片",
                    width=300
                )
            st.markdown(content)
    else:
        with st.chat_message("assistant", avatar="🤖"):
            st.markdown(content)
            
            # 显示工具调用信息
            if tool_calls and len(tool_calls) > 0:
                with st.expander("🔧 工具调用详情", expanded=False):
                    for i, tc in enumerate(tool_calls):
                        st.markdown(f"**{i+1}. {tc.get('tool_name', 'Unknown')}**")
                        st.code(f"输入: {tc.get('tool_input', {})}", language="json")
                        st.text(f"输出: {tc.get('tool_output', '')[:200]}...")
                        st.divider()
            
            # 显示检索到的文档
            if retrieved_docs and len(retrieved_docs) > 0:
                with st.expander("📚 参考资料", expanded=False):
                    for i, doc in enumerate(retrieved_docs):
                        st.markdown(f"**文档 {i+1}:**")
                        st.text(doc[:300] + "..." if len(doc) > 300 else doc)
                        st.divider()


def render_chat_history(messages: List[Dict[str, Any]]):
    """
    渲染完整的对话历史
    
    Args:
        messages: 消息列表
    """
    for msg in messages:
        render_message(
            role=msg.get("role", "user"),
            content=msg.get("content", ""),
            tool_calls=msg.get("tool_calls"),
            retrieved_docs=msg.get("retrieved_docs"),
            image_base64=msg.get("image_base64")
        )


def create_chat_input() -> tuple:
    """
    创建聊天输入区域
    
    Returns:
        (用户输入, 提交按钮状态)
    """
    user_input = st.chat_input("请输入您的问题...")
    return user_input


def show_thinking_indicator():
    """显示思考中指示器"""
    with st.chat_message("assistant", avatar="🤖"):
        with st.spinner("正在思考中..."):
            st.empty()
