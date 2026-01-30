"""
多模态智能 Agent - Chainlit 前端
高性能聊天界面，支持文本、图片和文档输入

本实现使用自定义数据层启用原生历史记录侧边栏(左侧)，无需 PostgreSQL。
同时重构了信息展示，使用右侧边栏显示工具调用和参考来源，避免信息过载。
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# 强制加载项目根目录的 .env
env_path = Path(__file__).parent.parent / ".env"
load_dotenv(env_path)

# 确保 AUTH_SECRET 存在
if not os.getenv("CHAINLIT_AUTH_SECRET"):
    os.environ["CHAINLIT_AUTH_SECRET"] = "fixed-secret-key-for-dev-123"

import chainlit as cl
from chainlit.input_widget import Switch
import base64
import sys

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from chainlit_app.api_client import APIClient
# from chainlit_app.custom_data_layer import CustomDataLayer
from chainlit_app.custom_data_layer import CustomDataLayer


# 全局 API 客户端（复用连接）
api_client = APIClient()


# ============================================================================
# 数据层配置 - 使用自定义数据层启用历史记录侧边栏
# ============================================================================

@cl.data_layer
def get_data_layer():
    """
    返回自定义数据层实例
    数据将存储在 ./data/chainlit_storage 目录
    """
    storage_path = Path(__file__).parent.parent / "data" / "chainlit_storage"
    return CustomDataLayer(storage_path=str(storage_path))


# ============================================================================
# 认证配置 (必须启用认证才能有历史记录侧边栏)
# ============================================================================

@cl.password_auth_callback
def auth_callback(username: str, password: str):
    """
    简单的密码认证
    输入任意用户名即可登录，无需特定密码
    """
    return cl.User(identifier=username)


# ============================================================================
# Chat Profiles - 在顶部提供配置切换
# ============================================================================

@cl.set_chat_profiles
async def set_chat_profiles():
    """
    定义不同的聊天配置
    用户可以在顶部下拉菜单中切换
    """
    return [
        cl.ChatProfile(
            name="🤖 标准模式",
            markdown_description="启用所有功能：工具调用 + 知识检索",
            default=True,
        ),
        cl.ChatProfile(
            name="💬 纯对话模式",
            markdown_description="仅对话，不使用工具和知识库",
        ),
        cl.ChatProfile(
            name="🔧 工具模式",
            markdown_description="启用工具调用，关闭知识检索",
        ),
        cl.ChatProfile(
            name="📚 知识库模式",
            markdown_description="启用知识检索，关闭工具调用",
        ),
    ]


# ============================================================================
# Chainlit 生命周期钩子
# ============================================================================

@cl.on_chat_start
async def on_chat_start():
    """
    用户开始新对话时调用
    初始化会话状态和设置面板
    """
    # 获取当前配置
    chat_profile = cl.user_session.get("chat_profile")
    session_id = cl.user_session.get("id")
    user = cl.user_session.get("user")
    
    print(f"[Chainlit] 新会话开始: {session_id}")
    print(f"[Chainlit] 当前用户: {user.identifier if user else 'None'}")
    print(f"[Chainlit] 当前配置: {chat_profile}")
    
    # 根据配置设置默认值
    if chat_profile == "💬 纯对话模式":
        use_tools = False
        use_rag = False
    elif chat_profile == "🔧 工具模式":
        use_tools = True
        use_rag = False
    elif chat_profile == "📚 知识库模式":
        use_tools = False
        use_rag = True
    else:  # 标准模式
        use_tools = True
        use_rag = True
    
    # 初始化用户偏好设置
    cl.user_session.set("use_tools", use_tools)
    cl.user_session.set("use_rag", use_rag)
    cl.user_session.set("save_to_global", False)
    
    # 创建设置面板
    await cl.ChatSettings(
        [
            Switch(
                id="use_tools",
                label="🔧 启用工具调用",
                initial=use_tools,
                description="允许 Agent 使用计算器等工具"
            ),
            Switch(
                id="use_rag",
                label="📚 启用知识检索",
                initial=use_rag,
                description="从知识库检索相关信息"
            ),
            Switch(
                id="save_to_global",
                label="💾 文档保存到全局知识库",
                initial=False,
                description="上传的文档将永久保存，可在其他会话访问"
            ),
        ]
    ).send()
    
    # 指南内容已移除，不再发送欢迎消息以保持界面清爽


@cl.on_chat_resume
async def on_chat_resume(thread: dict):
    """
    用户恢复之前的对话时调用
    重新加载会话状态
    """
    thread_id = thread.get("id")
    print(f"[Chainlit] 恢复会话: {thread_id}")
    
    # 关键：将当前会话 ID 设置为恢复的线程 ID
    # 这样后续发给后端的请求就会带上这个 ID，后端就能恢复对应的上下文（如果有持久化）
    cl.user_session.set("id", thread_id)
    
    # 恢复默认设置
    cl.user_session.set("use_tools", True)
    cl.user_session.set("use_rag", True)
    cl.user_session.set("save_to_global", False)
    
    # 重新显示设置面板
    await cl.ChatSettings(
        [
            Switch(
                id="use_tools",
                label="🔧 启用工具调用",
                initial=True,
                description="允许 Agent 使用计算器等工具"
            ),
            Switch(
                id="use_rag",
                label="📚 启用知识检索",
                initial=True,
                description="从知识库检索相关信息"
            ),
            Switch(
                id="save_to_global",
                label="💾 文档保存到全局知识库",
                initial=False,
                description="上传的文档将永久保存，可在其他会话访问"
            ),
        ]
    ).send()
    
    pass
    # 消息已移除


@cl.on_chat_end
async def on_chat_end():
    """对话结束时清理资源"""
    print("[Chainlit] 对话结束")


@cl.on_stop
async def on_stop():
    """用户点击停止按钮时调用"""
    print("[Chainlit] 用户终止了生成")


# ============================================================================
# 设置更新处理
# ============================================================================

@cl.on_settings_update
async def on_settings_update(settings: dict):
    """用户更新设置时调用"""
    cl.user_session.set("use_tools", settings.get("use_tools", True))
    cl.user_session.set("use_rag", settings.get("use_rag", True))
    cl.user_session.set("save_to_global", settings.get("save_to_global", False))
    
    await cl.Message(
        content=f"⚙️ 设置已更新:\n"
                f"- 工具调用: {'✅' if settings.get('use_tools') else '❌'}\n"
                f"- 知识检索: {'✅' if settings.get('use_rag') else '❌'}\n"
                f"- 保存到全局知识库: {'✅' if settings.get('save_to_global') else '❌'}"
    ).send()


# ============================================================================
# 消息处理
# ============================================================================

@cl.on_message
async def on_message(message: cl.Message):
    """
    处理用户发送的消息
    支持纯文本、图片和文档
    """
    # 使用 Chainlit 的 thread_id 作为 session_id，确保后端 ID 与前端一致
    session_id = message.thread_id
    cl.user_session.set("id", session_id)
    
    use_tools = cl.user_session.get("use_tools", True)
    use_rag = cl.user_session.get("use_rag", True)
    
    # ---- 1. 处理上传的文件 ----
    image_base64 = None
    
    if message.elements:
        for element in message.elements:
            # 处理图片
            if element.mime and "image" in element.mime:
                image_base64 = await process_image(element)
                
            # 处理文档 (PDF, TXT, MD)
            elif element.name and any(element.name.lower().endswith(ext) for ext in [".pdf", ".txt", ".md"]):
                await process_document(element, session_id)
    
    # 如果只上传了文档没有文本，不需要调用聊天API
    if not message.content.strip() and not image_base64:
        return
    
    # ---- 2. 调用后端流式 API ----
    msg = cl.Message(content="")
    await msg.send()
    
    messages_payload = [{"role": "user", "content": message.content}]
    
    # 元数据收集
    tool_calls = []
    retrieved_docs = []
    
    try:
        async for chunk in api_client.chat_stream(
            messages=messages_payload,
            image_base64=image_base64,
            use_tools=use_tools,
            use_rag=use_rag,
            session_id=session_id
        ):
            if chunk["type"] == "meta":
                # 收集元数据（工具调用、检索结果）
                tool_calls = chunk.get("tool_calls", [])
                retrieved_docs = chunk.get("retrieved_docs", [])
                
            elif chunk["type"] == "content":
                # 流式输出内容
                await msg.stream_token(chunk["content"])
                
            elif chunk["type"] == "error":
                await msg.stream_token(f"\n\n❌ 错误: {chunk['message']}")
        
        # 完成主消息
        await msg.update()
        
        # ---- 3. 在侧边栏显示详细信息 (Refactored) ----
        # 遵循用户提供的最佳实践：使用 display="side" 而不是 inline steps
        
        side_elements = []
        
        if tool_calls:
            tool_info = ""
            for i, tool in enumerate(tool_calls):
                tool_name = tool.get("name", "未知工具")
                tool_input = tool.get("input", {})
                tool_output = str(tool.get("output", ""))
                # 截断过长的输出
                if len(tool_output) > 500:
                    tool_output = tool_output[:500] + "... (已截断)"
                
                tool_info += f"### {i+1}. {tool_name}\n"
                tool_info += f"**Input**: `{tool_input}`\n\n"
                tool_info += f"**Output**:\n```\n{tool_output}\n```\n\n---\n\n"
            
            side_elements.append(
                cl.Text(name="工具调用详情", content=tool_info, display="side")
            )
        
        if retrieved_docs:
            ref_info = ""
            for i, doc in enumerate(retrieved_docs):
                preview = doc[:500] + "..." if len(doc) > 500 else doc
                ref_info += f"### 来源 {i+1}\n{preview}\n\n---\n\n"
                
            side_elements.append(
                cl.Text(name="知识库来源", content=ref_info, display="side")
            )
            
        # 如果有侧边栏元素，更新消息以包含它们
        if side_elements:
            msg.elements = side_elements
            # 必须在内容中提及元素名称，才能触发侧边栏 (根据用户提供的图片指示)
            element_links = " ".join([f"[{e.name}]" for e in side_elements])
            msg.content += f"\n\n👉 查看详情: {element_links}"
            await msg.update()
        
    except Exception as e:
        await msg.stream_token(f"\n\n❌ 发生错误: {str(e)}")
        await msg.update()


# ============================================================================
# 辅助函数
# ============================================================================

async def process_image(element) -> str:
    """处理上传的图片，返回 base64 编码"""
    try:
        with open(element.path, "rb") as f:
            image_bytes = f.read()
        
        image_base64 = base64.b64encode(image_bytes).decode("utf-8")
        
        await cl.Message(
            content=f"🖼️ 已接收图片: **{element.name}**",
            elements=[
                cl.Image(name=element.name, path=element.path, display="inline")
            ]
        ).send()
        
        return image_base64
        
    except Exception as e:
        await cl.Message(content=f"❌ 图片处理失败: {str(e)}").send()
        return None


async def process_document(element, session_id: str):
    """处理上传的文档，添加到知识库"""
    save_to_global = cl.user_session.get("save_to_global", False)
    
    # 同样使用侧边栏显示处理结果
    try:
        with open(element.path, "rb") as f:
            file_bytes = f.read()
        
        result = await api_client.upload_document(
            file_bytes=file_bytes,
            filename=element.name,
            session_id=session_id,
            save_to_global=save_to_global
        )
        
        status = result.get("status")
        
        if status == "completed":
            scope = result.get("scope", "未知")
            chunks = result.get("chunks", 0)
            
            info_content = f"### 文档处理详情\n\n- **文件名**: {element.name}\n- **存储位置**: {scope}\n- **分块数量**: {chunks}\n- **状态**: ✅ 完成"
            
            info_element = cl.Text(name=f"{element.name}-详情", content=info_content, display="side")
            
            await cl.Message(
                content=f"✅ 文档 **{element.name}** 处理完成！可以查看 [{element.name}-详情]。",
                elements=[info_element]
            ).send()
            
        else:
            await cl.Message(
                content=f"❌ 文档处理失败: {result.get('message', '未知错误')}"
            ).send()
            
    except Exception as e:
        await cl.Message(content=f"❌ 文档上传错误: {str(e)}").send()


# ============================================================================
# 聊天启动器
# ============================================================================

@cl.set_starters
async def set_starters():
    """设置对话启动建议"""
    return [
        cl.Starter(
            label="💡 介绍一下你的功能",
            message="请详细介绍你可以做什么，有哪些功能？",
        ),
        cl.Starter(
            label="🧮 数学计算",
            message="请帮我计算：(123 + 456) * 789 / 2 的结果是多少？",
        ),
        cl.Starter(
            label="📖 知识问答",
            message="什么是机器学习？请用简单的语言解释。",
        ),
        cl.Starter(
            label="🔍 代码解释",
            message="请解释 Python 中的装饰器是什么，并给出一个例子。",
        ),
    ]
