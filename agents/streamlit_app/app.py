"""
多模态智能 Agent - Streamlit 前端
支持文本和图片输入的智能对话界面
"""

import streamlit as st
import base64
import time
from typing import Optional, List

# 添加项目路径
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from streamlit_app.utils.api_client import APIClient
from streamlit_app.components.chat import render_message
from streamlit_app.components.upload import create_image_uploader, show_image_preview
from streamlit_app.components.document_upload import create_document_uploader, show_upload_result


# 页面配置
st.set_page_config(
    page_title="多模态智能 Agent",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 自定义样式
st.markdown("""
<style>
    .main-title {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        font-size: 2.5rem;
        font-weight: bold;
        text-align: center;
        margin-bottom: 1rem;
    }
    .status-online { background-color: #28a745; }
    .status-offline { background-color: #dc3545; }
</style>
""", unsafe_allow_html=True)


# --- 缓存函数 (避免重复请求) ---

@st.cache_data(ttl=10)  # 缓存10秒
def cached_list_sessions(_api_client):
    """缓存的会话列表"""
    return _api_client.list_sessions()

@st.cache_data(ttl=30)  # 缓存30秒
def cached_health_check(_api_client):
    """缓存的健康检查"""
    return _api_client.check_health()

@st.cache_data(ttl=60)  # 缓存60秒
def cached_knowledge_stats(_api_client):
    """缓存的知识库统计"""
    return _api_client.get_knowledge_stats()


def init_session_state():
    """初始化会话状态 (仅在首次运行时执行API调用)"""
    if "api_client" not in st.session_state:
        st.session_state.api_client = APIClient()

    if "current_session_id" not in st.session_state:
        # 仅在初始化时调用一次
        sessions = st.session_state.api_client.list_sessions()
        if sessions:
            st.session_state.current_session_id = sessions[0]["id"]
            st.session_state.sessions_cache = sessions
        else:
            new_session = st.session_state.api_client.create_session()
            st.session_state.current_session_id = new_session.get("id")
            st.session_state.sessions_cache = [{"id": new_session.get("id"), "name": new_session.get("name")}]
    
    if "sessions_cache" not in st.session_state:
        st.session_state.sessions_cache = []

    if "messages" not in st.session_state:
        st.session_state.messages = []
        if st.session_state.current_session_id:
            load_history(st.session_state.current_session_id)
    
    if "current_image" not in st.session_state:
        st.session_state.current_image = None
    
    if "current_image_base64" not in st.session_state:
        st.session_state.current_image_base64 = None
    
    if "use_tools" not in st.session_state:
        st.session_state.use_tools = True
        
    if "uploaded_documents" not in st.session_state:
        st.session_state.uploaded_documents = []
        # 从服务器加载已上传文档列表
        if st.session_state.current_session_id:
            st.session_state.uploaded_documents = st.session_state.api_client.get_session_documents(
                st.session_state.current_session_id
            )
    
    if "pending_upload" not in st.session_state:
        st.session_state.pending_upload = None  # 正在处理的文件名
    
    if "use_rag" not in st.session_state:
        st.session_state.use_rag = True


def load_history(session_id: str):
    """加载会话历史"""
    history = st.session_state.api_client.get_session_history(session_id)
    st.session_state.messages = []
    for msg in history:
        st.session_state.messages.append({
            "role": msg["role"],
            "content": msg["content"]
        })


def refresh_sessions_cache():
    """刷新会话缓存 (仅在新建/删除时调用)"""
    st.session_state.sessions_cache = st.session_state.api_client.list_sessions()
    # 同时清除缓存以便下次获取新数据
    cached_list_sessions.clear()


def render_sidebar():
    """渲染侧边栏"""
    with st.sidebar:
        st.markdown("### 🗂️ 会话管理")
        
        # 使用缓存的会话列表
        sessions = st.session_state.sessions_cache
        if not isinstance(sessions, list):
            sessions = []
        
        # 构建有效的会话选项（严格过滤无效数据）
        valid_sessions = []
        for s in sessions:
            if isinstance(s, dict):
                sid = s.get("id")
                sname = s.get("name")
                # 只接受 id 不为 None 的会话
                if sid is not None:
                    display_name = sname if sname else f"Session {str(sid)[:8]}"
                    valid_sessions.append({"id": sid, "name": display_name})
        
        if valid_sessions:
            # 构建选项
            options_ids = [s["id"] for s in valid_sessions]
            options_names = {s["id"]: s["name"] for s in valid_sessions}
            
            # 确定当前索引
            current_index = 0
            if st.session_state.current_session_id in options_ids:
                current_index = options_ids.index(st.session_state.current_session_id)
            
            selected_session_id = st.selectbox(
                "选择会话",
                options=options_ids,
                format_func=lambda x: options_names.get(x, "Unknown"),
                index=current_index,
                key="session_selector",
                label_visibility="collapsed"
            )
            
            if selected_session_id != st.session_state.current_session_id:
                st.session_state.current_session_id = selected_session_id
                st.session_state.uploaded_documents = st.session_state.api_client.get_session_documents(
                    selected_session_id
                )
                st.session_state.pending_upload = None
                load_history(selected_session_id)
                st.rerun()
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button("➕ 新建", use_container_width=True):
                new_session = st.session_state.api_client.create_session()
                st.session_state.current_session_id = new_session.get("id")
                st.session_state.messages = []
                st.session_state.uploaded_documents = []
                st.session_state.pending_upload = None
                refresh_sessions_cache()
                st.rerun()
        
        with col2:
            if st.button("🗑️ 删除", use_container_width=True, type="secondary"):
                if st.session_state.current_session_id and len(valid_sessions) > 1:
                    st.session_state.api_client.delete_session(st.session_state.current_session_id)
                    refresh_sessions_cache()
                    # 安全获取第一个有效会话
                    new_sessions = st.session_state.sessions_cache
                    if new_sessions and isinstance(new_sessions, list) and len(new_sessions) > 0:
                        first_session = new_sessions[0]
                        if isinstance(first_session, dict) and first_session.get("id"):
                            st.session_state.current_session_id = first_session["id"]
                            load_history(st.session_state.current_session_id)
                    st.rerun()

        st.divider()

        # 功能开关 (无API调用，非常快)
        st.markdown("### ⚙️ 功能配置")
        
        st.session_state.use_tools = st.toggle(
            "🔧 启用工具调用",
            value=st.session_state.use_tools,
            help="启用后可使用计算器等工具"
        )
        
        st.session_state.use_rag = st.toggle(
            "📚 启用知识检索",
            value=st.session_state.use_rag,
            help="启用后会从知识库检索信息"
        )
        
        st.divider()
        
        # 图片上传
        st.markdown("### 📷 图片上传")
        
        image_bytes, image_base64 = create_image_uploader()
        
        if image_bytes:
            st.session_state.current_image = image_bytes
            st.session_state.current_image_base64 = image_base64
            show_image_preview(image_bytes, "当前图片")
            
            if st.button("🗑️ 清除图片", use_container_width=True):
                st.session_state.current_image = None
                st.session_state.current_image_base64 = None
                st.rerun()
        
        st.divider()
        
        # 文档上传
        st.markdown("### 📄 文档上传")
        st.caption("上传PDF或TXT文件")
        
        # 全局知识库选项
        save_to_global_kb = st.checkbox(
            "💾 保存到全局知识库",
            value=False,
            help="勾选后文档将永久保存，可在其他会话中访问；不勾选则仅在当前会话可用"
        )
        
        # 检查是否有正在处理的上传
        if st.session_state.pending_upload:
            status_result = st.session_state.api_client.get_upload_status(st.session_state.pending_upload)
            upload_status = status_result.get("status", "unknown")
            
            if upload_status == "completed":
                # 上传完成，更新本地文档列表
                if st.session_state.pending_upload not in st.session_state.uploaded_documents:
                    st.session_state.uploaded_documents.append(st.session_state.pending_upload)
                st.success(f"✅ {st.session_state.pending_upload} 处理完成!")
                st.session_state.pending_upload = None
            elif upload_status == "processing":
                st.info(f"⏳ {st.session_state.pending_upload} 正在后台处理中...")
            elif upload_status == "failed":
                st.error(f"❌ {st.session_state.pending_upload} 处理失败")
                st.session_state.pending_upload = None
        
        doc_bytes, doc_filename = create_document_uploader()
        
        if doc_bytes and doc_filename:
            # 检查是否已上传过
            if doc_filename not in st.session_state.uploaded_documents and doc_filename != st.session_state.pending_upload:
                with st.spinner(f"正在上传 {doc_filename}..."):
                    result = st.session_state.api_client.upload_document(
                        file_bytes=doc_bytes,
                        filename=doc_filename,
                        session_id=st.session_state.current_session_id,
                        save_to_global=save_to_global_kb
                    )
                    
                    status = result.get("status")
                    if status == "processing":
                        st.session_state.pending_upload = doc_filename
                        scope_msg = "全局知识库" if save_to_global_kb else "会话知识库"
                        st.info(f"📤 {doc_filename} 已提交到{scope_msg}，正在后台处理...")
                    elif status == "success":
                        if doc_filename not in st.session_state.uploaded_documents:
                            st.session_state.uploaded_documents.append(doc_filename)
                        show_upload_result(result)
                    else:
                        st.error(f"上传失败: {result.get('message', '未知错误')}")
        
        # 显示已上传的文档列表
        if st.session_state.uploaded_documents:
            st.markdown("**已上传文档:**")
            for doc in st.session_state.uploaded_documents:
                st.markdown(f"• 📄 {doc}")
        
        st.divider()
        
        # 知识库统计 (使用expander延迟显示，减少视觉干扰)
        with st.expander("📊 知识库状态"):
            if st.button("刷新", key="refresh_stats"):
                cached_knowledge_stats.clear()
            stats = cached_knowledge_stats(st.session_state.api_client)
            if "error" not in stats:
                st.metric("已索引文档", stats.get('document_count', 0))
        
        st.divider()
        
        if st.button("🧹 清空当前对话", use_container_width=True):
            st.session_state.messages = []
            st.session_state.uploaded_documents = []
            st.session_state.pending_upload = None
            st.session_state.api_client.clear_history(st.session_state.current_session_id)
            st.rerun()


def render_main_chat():
    """渲染主聊天区域"""
    st.markdown('<h1 class="main-title">🤖 多模态智能 Agent</h1>', unsafe_allow_html=True)
    
    # 显示当前会话名称
    current_session_name = "New Chat"
    for s in st.session_state.sessions_cache:
        if s["id"] == st.session_state.current_session_id:
            current_session_name = s["name"]
            break
            
    st.markdown(
        f'<p style="text-align: center; color: #666;">当前会话: {current_session_name}</p>',
        unsafe_allow_html=True
    )
    
    st.divider()
    
    # 显示对话历史
    for msg in st.session_state.messages:
        render_message(
            role=msg["role"],
            content=msg["content"],
            tool_calls=msg.get("tool_calls"),
            retrieved_docs=msg.get("retrieved_docs"),
            image_base64=msg.get("image_base64")
        )
    
    # 聊天输入
    chat_disabled = st.session_state.pending_upload is not None
    chat_placeholder = "正在处理文档，请稍候..." if chat_disabled else "请输入您的问题..."
    
    if user_input := st.chat_input(chat_placeholder, disabled=chat_disabled):
        user_message = {
            "role": "user",
            "content": user_input,
            "image_base64": st.session_state.current_image_base64
        }
        st.session_state.messages.append(user_message)
        
        render_message(
            role="user",
            content=user_input,
            image_base64=st.session_state.current_image_base64
        )
        
        with st.chat_message("assistant", avatar="🤖"):
            # 占位容器
            retrieved_docs_container = st.container()
            tool_calls_container = st.container()
            
            # 准备请求参数
            messages_payload = [{"role": "user", "content": user_input}]
            
            # 使用流式 API
            stream = st.session_state.api_client.chat_stream(
                messages=messages_payload,
                image_base64=st.session_state.current_image_base64,
                use_tools=st.session_state.use_tools,
                use_rag=st.session_state.use_rag,
                session_id=st.session_state.current_session_id
            )
            
            retrieved_docs = []
            tool_calls = []
            
            def stream_generator():
                nonlocal retrieved_docs
                for chunk in stream:
                    if chunk["type"] == "meta":
                        retrieved_docs = chunk.get("retrieved_docs", [])
                        # 实时显示检索结果
                        if retrieved_docs:
                            with retrieved_docs_container.expander("📚 参考资料", expanded=False):
                                for i, doc in enumerate(retrieved_docs):
                                    st.markdown(f"**文档 {i+1}:**")
                                    st.text(doc[:300] + "..." if len(doc) > 300 else doc)
                                    
                    elif chunk["type"] == "content":
                        yield chunk["content"]
                    
                    elif chunk["type"] == "error":
                        st.error(chunk["message"])
            
            # 实时渲染
            ai_content = st.write_stream(stream_generator())
            
            # 保存 AI 消息
            if ai_content:
                st.session_state.messages.append({
                    "role": "assistant",
                    "content": ai_content,
                    "tool_calls": tool_calls,
                    "retrieved_docs": retrieved_docs
                })
        
        # 清除已使用的图片
        st.session_state.current_image = None
        st.session_state.current_image_base64 = None


def main():
    """主函数"""
    init_session_state()
    render_sidebar()
    render_main_chat()


if __name__ == "__main__":
    main()
