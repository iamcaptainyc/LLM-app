"""
LangGraph ReAct Agent 服务
支持多会话管理与持久化
"""

import os
import json
import uuid
import shutil
from typing import List, Optional, Any, Dict, TypedDict
from pathlib import Path
from datetime import datetime

from langchain_core.messages import HumanMessage, AIMessage, SystemMessage, ToolMessage, BaseMessage, AIMessageChunk
from langchain_community.chat_models.tongyi import ChatTongyi
from langgraph.graph import StateGraph, END

from app.config import settings
from app.tools.custom_tools import get_all_tools, set_current_image
from app.services.vector_service import get_vector_service


# 系统提示词 - ReAct风格
SYSTEM_PROMPT = """你是一个智能多模态助手。

你的核心能力：
1. **知识问答**: 用户上传的PDF/TXT文档会被添加到知识库，你可以基于这些文档回答问题
2. **图像理解**: 分析用户上传的图片内容
3. **工具调用**: 使用计算器、日期时间等工具
4. **联合推理**: 结合图片和文档知识进行综合分析

重要规则：
- 当系统消息中包含"[知识库内容]"时，这些内容来自用户上传的文档，你必须基于这些内容回答
- 不要说"没有上传文档"或"没有看到PDF"，如果有知识库内容，就直接使用它们
- 回答时引用知识库内容，说明"根据您上传的文档..."
- 语言自然友好，回答准确有帮助
"""


class AgentState(TypedDict):
    """Agent状态定义"""
    messages: List[Any]
    retrieved_docs: List[str]
    tool_calls_log: List[dict]


class SessionData:
    """会话数据结构"""
    def __init__(self, session_id: str, history: List[BaseMessage] = None, uploaded_documents: List[str] = None, name: str = None):
        self.session_id = session_id
        self.history = history or []
        self.uploaded_documents = uploaded_documents or []  # 改为列表支持多文档
        self.name = name or f"New Chat {datetime.now().strftime('%H:%M')}"
        self.created_at = datetime.now().isoformat()
        
    def to_dict(self) -> dict:
        """序列化"""
        # 将 LangChain 消息转换为字典
        serialized_history = []
        for msg in self.history:
            if isinstance(msg, HumanMessage):
                serialized_history.append({"type": "human", "content": msg.content})
            elif isinstance(msg, AIMessage):
                serialized_history.append({"type": "ai", "content": msg.content})
            elif isinstance(msg, SystemMessage):
                serialized_history.append({"type": "system", "content": msg.content})
            # 暂时忽略其他类型消息以简化存储
            
        return {
            "session_id": self.session_id,
            "name": self.name,
            "uploaded_documents": self.uploaded_documents,
            "created_at": self.created_at,
            "history": serialized_history
        }

    @classmethod
    def from_dict(cls, data: dict):
        """反序列化"""
        history = []
        for msg_data in data.get("history", []):
            if msg_data["type"] == "human":
                history.append(HumanMessage(content=msg_data["content"]))
            elif msg_data["type"] == "ai":
                history.append(AIMessage(content=msg_data["content"]))
            elif msg_data["type"] == "system":
                history.append(SystemMessage(content=msg_data["content"]))
                
        # 兼容旧格式: latest_document -> uploaded_documents
        uploaded_docs = data.get("uploaded_documents", [])
        if not uploaded_docs and data.get("latest_document"):
            uploaded_docs = [data["latest_document"]]
                
        return cls(
            session_id=data["session_id"],
            history=history,
            uploaded_documents=uploaded_docs,
            name=data.get("name")
        )


class ReActAgentService:
    """LangGraph ReAct Agent 服务 (支持多会话)"""
    
    def __init__(self):
        """初始化 ReAct Agent"""
        # 初始化 LLM
        self.llm = ChatTongyi(
            model="qwen-plus",
            dashscope_api_key=settings.dashscope_api_key,
            streaming=True
        )
        
        # 获取工具
        self.tools = get_all_tools()
        self.llm_with_tools = self.llm.bind_tools(self.tools)
        
        # 构建两个工作流:一个支持工具调用,一个不支持
        self.graph_with_tools = self._build_graph(use_tools=True)
        self.graph_no_tools = self._build_graph(use_tools=False)
        
        # 会话存储路径
        self.storage_dir = Path("data/sessions")
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        
        # 内存缓存
        self.sessions: Dict[str, SessionData] = {}
        
        # 加载所有会话
        self._load_all_sessions()

    
    def _load_all_sessions(self):
        """从磁盘加载所有会话"""
        for file_path in self.storage_dir.glob("*.json"):
            try:
                data = json.loads(file_path.read_text(encoding="utf-8"))
                session = SessionData.from_dict(data)
                self.sessions[session.session_id] = session
            except Exception as e:
                print(f"Error loading session {file_path}: {e}")

    def _generate_title(self, user_input: str, ai_response: str) -> str:
        """根据用户输入生成标题 (截取前20字)"""
        return user_input[:20].strip()

    async def _agenerate_title(self, user_input: str, ai_response: str) -> str:
        """根据用户输入生成标题 (Async, 截取前20字)"""
        return user_input[:20].strip()

    def _save_session(self, session: SessionData):
        """保存会话到磁盘"""
        file_path = self.storage_dir / f"{session.session_id}.json"
        data = session.to_dict()
        file_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    def get_session(self, session_id: Optional[str] = None) -> SessionData:
        """获取或创建会话"""
        if not session_id:
            session_id = str(uuid.uuid4())
            
        if session_id not in self.sessions:
            self.sessions[session_id] = SessionData(session_id)
            self._save_session(self.sessions[session_id])
            
        return self.sessions[session_id]

    def create_session(self, name: Optional[str] = None) -> SessionData:
        """创建新会话"""
        session_id = str(uuid.uuid4())
        session = SessionData(session_id, name=name)
        self.sessions[session_id] = session
        self._save_session(session)
        return session

    def delete_session(self, session_id: str) -> bool:
        """删除会话 (Robust)"""
        try:
            file_path = self.storage_dir / f"{session_id}.json"
            exists_in_memory = session_id in self.sessions
            exists_on_disk = file_path.exists()

            if not exists_in_memory and not exists_on_disk:
                return False

            # 1. 清除向量库 (不阻断)
            try:
                from app.services.vector_service import get_vector_service
                vs = get_vector_service()
                vs.clear_session_collection(session_id)
            except Exception as e:
                print(f"[Warning] Failed to clear vector store for {session_id}: {e}")

            # 2. 从内存删除
            if exists_in_memory:
                del self.sessions[session_id]

            # 3. 从磁盘删除
            if exists_on_disk:
                try:
                    file_path.unlink()
                except PermissionError:
                    print(f"[Error] Permission denied deleting {file_path}. File might be in use.")
                except Exception as e:
                    print(f"[Error] Failed to delete file {file_path}: {e}")

            return True
        except Exception as e:
            print(f"[Fatal] delete_session error: {e}")
            return False
    
    def list_sessions(self) -> List[dict]:
        """列出所有会话"""
        sessions_list = []
        for s in self.sessions.values():
            sessions_list.append({
                "id": s.session_id,
                "name": s.name,
                "created_at": s.created_at,
                "msg_count": len(s.history) // 2  # 估算轮数
            })
        # 按创建时间倒序排序
        return sorted(sessions_list, key=lambda x: x["created_at"], reverse=True)

    def add_uploaded_document(self, filename: str, session_id: str):
        """添加上传文档到会话"""
        session = self.get_session(session_id)
        print(f"[DEBUG] add_uploaded_document: session={session_id}, filename={filename}")
        print(f"[DEBUG] Before: uploaded_documents={session.uploaded_documents}")
        if filename not in session.uploaded_documents:
            session.uploaded_documents.append(filename)
        print(f"[DEBUG] After: uploaded_documents={session.uploaded_documents}")
        self._save_session(session)

    def clear_uploaded_documents(self, session_id: str):
        """清除某个会话的上传文档列表"""
        session = self.get_session(session_id)
        session.uploaded_documents = []
        self._save_session(session)

    def get_uploaded_documents(self, session_id: str) -> List[str]:
        """获取会话的上传文档列表"""
        session = self.get_session(session_id)
        return session.uploaded_documents

    def _build_graph(self, use_tools: bool = True) -> StateGraph:
        """构建LangGraph工作流
        
        Args:
            use_tools: 是否启用工具调用
        """
        # 根据参数选择使用的 LLM
        llm = self.llm_with_tools if use_tools else self.llm
        
        def agent_node(state: AgentState) -> AgentState:
            messages = state["messages"]
            response = llm.invoke(messages)
            return {"messages": messages + [response]}
        
        def should_continue(state: AgentState) -> str:
            messages = state["messages"]
            last_message = messages[-1]
            if not hasattr(last_message, "tool_calls") or not last_message.tool_calls:
                return "end"
            return "continue"
        
        def tool_node(state: AgentState) -> AgentState:
            messages = state["messages"]
            last_message = messages[-1]
            tool_calls_log = state.get("tool_calls_log", [])
            new_messages = []
            
            for tool_call in last_message.tool_calls:
                tool_name = tool_call["name"]
                tool_args = tool_call["args"]
                
                result = None
                for tool in self.tools:
                    if tool.name == tool_name:
                        try:
                            result = tool.invoke(tool_args)
                        except Exception as e:
                            result = f"工具执行错误: {str(e)}"
                        break
                if result is None:
                    result = f"未找到工具: {tool_name}"
                
                tool_calls_log.append({
                    "tool_name": tool_name,
                    "tool_input": tool_args,
                    "tool_output": str(result)[:500]
                })
                new_messages.append(ToolMessage(content=str(result), tool_call_id=tool_call["id"]))
            
            return {
                "messages": messages + new_messages,
                "tool_calls_log": tool_calls_log
            }
        
        workflow = StateGraph(AgentState)
        workflow.add_node("agent", agent_node)
        workflow.add_node("tools", tool_node)
        workflow.set_entry_point("agent")
        workflow.add_conditional_edges("agent", should_continue, {"continue": "tools", "end": END})
        workflow.add_edge("tools", "agent")
        
        return workflow.compile()
    
    def chat(
        self,
        user_input: str,
        image_base64: Optional[str] = None,
        use_rag: bool = True,
        session_id: Optional[str] = None,
        use_tools: bool = True
    ) -> dict:
        """根据 session_id 处理用户输入"""
        try:
            # 获取会话上下文
            session = self.get_session(session_id)
            current_session_id = session.session_id
            
            # 设置当前图片（全局变量仍需设置，LangGraph内部工具会用）
            set_current_image(image_base64)
            
            # 构建消息
            messages = [SystemMessage(content=SYSTEM_PROMPT)]
            messages.extend(session.history)
            
            # RAG 检索
            retrieved_docs = []
            enhanced_input = user_input
            
            if use_rag:
                vector_service = get_vector_service()
                search_results = []
                source_context = ""
                
                # 策略1: 从会话级知识库检索（优先级最高）
                print(f"[RAG] Session {current_session_id}: 检索会话级知识库")
                session_results = vector_service.search_session(
                    current_session_id,
                    user_input,
                    n_results=5
                )
                if session_results:
                    search_results.extend(session_results)
                    print(f"[RAG] Found {len(session_results)} results from session KB")
                    source_context = "会话知识库"
                
                # 策略2: 定向检索全局知识库 (基于会话的上传文档列表)
                print(f"[DEBUG] RAG: session.uploaded_documents = {session.uploaded_documents}")
                if session.uploaded_documents and len(search_results) < 5:
                    doc_list = session.uploaded_documents
                    print(f"[RAG] Session {current_session_id}: 定向检索全局知识库 {doc_list}")
                    where_filter = {"filename": {"$in": doc_list}} if len(doc_list) > 1 else {"filename": doc_list[0]}
                    global_targeted = vector_service.search_global(
                        user_input, 
                        n_results=5 - len(search_results), 
                        filter=where_filter
                    )
                    if global_targeted:
                        search_results.extend(global_targeted)
                        source_context += "、全局知识库(指定文件)" if source_context else "全局知识库(指定文件)"
                
                # 策略3: 全局知识库检索（补充）
                if len(search_results) < 3:
                    print(f"[RAG] 执行全局知识库补充检索")
                    global_results = vector_service.search_global(user_input, n_results=3 - len(search_results))
                    if global_results:
                        search_results.extend(global_results)
                        source_context += "、全局知识库" if source_context else "全局知识库"
                
                if search_results:
                    retrieved_docs = [r["content"] for r in search_results]
                    filenames = set()
                    for r in search_results:
                        if r.get("metadata") and r["metadata"].get("filename"):
                            filenames.add(r["metadata"]["filename"])
                    source_info = f"(参考来源: {', '.join(filenames)})" if filenames else ""
                    context = "\n\n".join([f"--- 文档片段 {i+1} ---\n{doc}" for i, doc in enumerate(retrieved_docs)])
                    enhanced_input = f"""[知识库内容] {source_context} {source_info}
以下是从文档中检索到的相关内容:

{context}

--- 用户问题 ---
{user_input}

请根据上述文档内容回答用户的问题。"""
            
            # 添加会话上下文：告诉模型当前会话中有哪些已上传的文件
            if session.uploaded_documents:
                session_context = f"[会话上下文] 用户在当前对话中已上传以下文件: {', '.join(session.uploaded_documents)}\n\n"
                enhanced_input = session_context + enhanced_input

            # 图片提示 (根据是否启用工具调整提示)
            if image_base64:
                if use_tools:
                    enhanced_input = f"[用户上传了一张图片，请使用图像分析工具分析图片内容]\n\n{enhanced_input}"
                else:
                    enhanced_input = f"[用户上传了一张图片，但工具调用已禁用，无法进行图像分析]\n\n{enhanced_input}"
            
            messages.append(HumanMessage(content=enhanced_input))
            
            # 运行工作流
            initial_state = {
                "messages": messages,
                "retrieved_docs": retrieved_docs,
                "tool_calls_log": []
            }
            # 根据 use_tools 选择工作流
            graph = self.graph_with_tools if use_tools else self.graph_no_tools
            result = graph.invoke(initial_state)
            
            # 提取响应
            final_messages = result["messages"]
            final_response = ""
            for msg in reversed(final_messages):
                if isinstance(msg, AIMessage) and msg.content:
                    final_response = msg.content
                    break
            
            # 更新历史并保存
            session.history.append(HumanMessage(content=user_input))
            session.history.append(AIMessage(content=final_response))
            
            # 如果是第一轮对话，生成标题
            if len(session.history) <= 2:
                session.name = self._generate_title(user_input, final_response)

            # 限制历史长度
            if len(session.history) > 20:
                session.history = session.history[-20:]
            
            self._save_session(session)
            
            return {
                "success": True,
                "response": final_response,
                "tool_calls": result.get("tool_calls_log", []),
                "retrieved_docs": retrieved_docs,
                "session_id": current_session_id
            }
            
        except Exception as e:
            import traceback
            traceback.print_exc()
            return {
                "success": False,
                "response": f"Error: {str(e)}",
                "tool_calls": [],
                "retrieved_docs": []
            }

    async def chat_stream(
        self,
        user_input: str,
        image_base64: Optional[str] = None,
        use_rag: bool = True,
        session_id: Optional[str] = None,
        use_tools: bool = True
    ):
        """流式对话生成器 (Async)"""
        try:
            # 1. 准备上下文 (复用 chat 逻辑)
            session = self.get_session(session_id)
            current_session_id = session.session_id
            set_current_image(image_base64)
            
            messages = [SystemMessage(content=SYSTEM_PROMPT)]
            messages.extend(session.history)
            
            enhanced_input = user_input
            retrieved_docs = []
            
            if use_rag:
                vector_service = get_vector_service()
                search_results = []
                source_context = ""
                
                # 策略1: 从会话级知识库检索（优先级最高）
                session_results = vector_service.search_session(
                    current_session_id,
                    user_input,
                    n_results=5
                )
                if session_results:
                    search_results.extend(session_results)
                    source_context = "会话知识库"
                
                # 策略2: 定向检索全局知识库
                if session.uploaded_documents and len(search_results) < 5:
                    doc_list = session.uploaded_documents
                    where_filter = {"filename": {"$in": doc_list}} if len(doc_list) > 1 else {"filename": doc_list[0]}
                    global_targeted = vector_service.search_global(
                        user_input, 
                        n_results=5 - len(search_results), 
                        filter=where_filter
                    )
                    if global_targeted:
                        search_results.extend(global_targeted)
                        source_context += "、全局知识库" if source_context else "全局知识库"
                
                # 策略3: 全局检索补充
                if len(search_results) < 3:
                    global_results = vector_service.search_global(user_input, n_results=3 - len(search_results))
                    if global_results:
                        search_results.extend(global_results)
                        source_context += "、全局知识库" if source_context else "全局知识库"
                
                if search_results:
                    retrieved_docs = [r["content"] for r in search_results]
                    filenames = set()
                    for r in search_results:
                        if r.get("metadata") and r["metadata"].get("filename"):
                            filenames.add(r["metadata"]["filename"])
                    source_info = f"(参考来源: {', '.join(filenames)})" if filenames else ""
                    context = "\n\n".join([f"--- 文档片段 {i+1} ---\n{doc}" for i, doc in enumerate(retrieved_docs)])
                    enhanced_input = f"""[知识库内容] {source_context} {source_info}
以下是从文档中检索到的相关内容:

{context}

--- 用户问题 ---
{user_input}

请根据上述文档内容回答用户的问题。"""

            # 添加会话上下文：告诉模型当前会话中有哪些已上传的文件
            if session.uploaded_documents:
                session_context = f"[会话上下文] 用户在当前对话中已上传以下文件: {', '.join(session.uploaded_documents)}\n\n"
                enhanced_input = session_context + enhanced_input

            # 图片提示 (根据是否启用工具调整提示)
            if image_base64:
                if use_tools:
                    enhanced_input = f"[用户上传了一张图片，请使用图像分析工具分析图片内容]\n\n{enhanced_input}"
                else:
                    enhanced_input = f"[用户上传了一张图片，但工具调用已禁用，无法进行图像分析]\n\n{enhanced_input}"
            
            messages.append(HumanMessage(content=enhanced_input))
            
            initial_state = {
                "messages": messages,
                "retrieved_docs": retrieved_docs,
                "tool_calls_log": []
            }
            
            # 2. 发送元数据 (Session ID, Docs)
            yield json.dumps({
                "type": "meta", 
                "session_id": current_session_id,
                "retrieved_docs": retrieved_docs
            }) + "\n"
            
            # 3. 流式生成 - 根据 use_tools 选择工作流
            final_response = ""
            graph = self.graph_with_tools if use_tools else self.graph_no_tools
            
            # 使用 astream_events 获取详细事件流
            async for event in graph.astream_events(initial_state, version="v2"):
                kind = event["event"]
                
                # 监听 Chat Model 的流式输出
                if kind == "on_chat_model_stream":
                    chunk = event["data"]["chunk"]
                    if isinstance(chunk, AIMessageChunk) and chunk.content:
                        content = chunk.content
                        final_response += content
                        yield json.dumps({"type": "content", "content": content}) + "\n"
                        
            # 4. 更新历史并保存
            session.history.append(HumanMessage(content=user_input))
            session.history.append(AIMessage(content=final_response))
            
            # 如果是第一轮对话，生成标题 (Async)
            if len(session.history) <= 2:
                session.name = await self._agenerate_title(user_input, final_response)

            if len(session.history) > 20:
                session.history = session.history[-20:]
            self._save_session(session)
            
            # 5. 结束标志
            yield json.dumps({"type": "done"}) + "\n"

        except Exception as e:
            import traceback
            traceback.print_exc()
            yield json.dumps({"type": "error", "message": str(e)}) + "\n"


    def clear_history(self, session_id: str):
        """清空会话历史和会话级知识库"""
        if session_id in self.sessions:
            session = self.sessions[session_id]
            session.history = []
            session.uploaded_documents = []
            self._save_session(session)
            set_current_image(None)
            
            # 清除会话级知识库
            vector_service = get_vector_service()
            vector_service.clear_session_collection(session_id)
            print(f"[AgentService] Cleared session KB for {session_id}")

    def get_history(self, session_id: str) -> List[dict]:
        """获取会话历史"""
        session = self.get_session(session_id)
        history = []
        for msg in session.history:
            if isinstance(msg, HumanMessage):
                history.append({"role": "user", "content": msg.content})
            elif isinstance(msg, AIMessage):
                history.append({"role": "assistant", "content": msg.content})
        return history


# 单例
_agent_service: Optional[ReActAgentService] = None

def get_agent_service() -> ReActAgentService:
    global _agent_service
    if _agent_service is None:
        _agent_service = ReActAgentService()
    return _agent_service
