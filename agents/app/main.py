"""
FastAPI 作为后端服务
"""

import os
from contextlib import asynccontextmanager
from typing import Optional, List, Dict

from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Depends, BackgroundTasks
from fastapi.responses import StreamingResponse
from fastapi.concurrency import run_in_threadpool
from fastapi.middleware.cors import CORSMiddleware
import json
from dotenv import load_dotenv

from app.services.agent_service import get_agent_service
from app.services.qwen_service import get_qwen_service
from app.services.vector_service import get_vector_service
from app.services.document_service import get_document_service

from app.models.schemas import ChatRequest, ChatResponse, HealthResponse, ToolCall

# 加载环境变量
load_dotenv()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    生命周期管理器
    """
    # 启动时执行
    print("Application startup")
    
    # 确保单例服务被初始化
    get_agent_service()
    get_qwen_service()
    get_vector_service()
    
    yield
    
    # 关闭时执行
    print("Application shutdown")


app = FastAPI(
    title="Multimodal Agent API",
    description="Backend API for Multimodal Intelligent Agent",
    version="1.0.0",
    lifespan=lifespan
)

# 配置 CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 上传状态跟踪 (filename -> status)
_upload_status: Dict[str, str] = {}


@app.get("/health", response_model=HealthResponse, tags=["Health"])
async def health_check():
    """健康检查接口"""
    return HealthResponse(
        status="healthy",
        version="1.0.0",
        model="qwen-vl-max"
    )


@app.post("/chat", response_model=ChatResponse, tags=["Chat"])
async def chat_endpoint(request: ChatRequest):
    """
    智能对话接口
    """
    try:
        agent_service = get_agent_service()
        
        # 提取最后一条用户消息的文本内容
        user_message_content = ""
        user_messages = [m for m in request.messages if m.role == "user"]
        if user_messages:
            last_message = user_messages[-1]
            if isinstance(last_message.content, str):
                user_message_content = last_message.content
            else:
                user_message_content = " ".join([
                    c.text for c in last_message.content 
                    if c.type == "text" and c.text
                ])

        result = agent_service.chat(
            user_input=user_message_content,
            image_base64=request.image_base64,
            use_rag=request.use_rag,
            session_id=request.session_id,
            use_tools=request.use_tools
        )
        
        if result["success"]:
            return ChatResponse(
                response=result["response"],
                tool_calls=[ToolCall(**t) for t in result["tool_calls"]],
                retrieved_docs=result["retrieved_docs"],
                model="qwen-plus"
            )
        else:
            raise HTTPException(status_code=500, detail=result["response"])
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/chat/stream", tags=["Chat"])
async def chat_stream_endpoint(request: ChatRequest):
    """
    流式对话接口 (SSE)
    """
    try:
        agent_service = get_agent_service()
        
        # 提取最后一条用户消息的文本内容
        user_message_content = ""
        user_messages = [m for m in request.messages if m.role == "user"]
        if user_messages:
            last_message = user_messages[-1]
            if isinstance(last_message.content, str):
                user_message_content = last_message.content
            else:
                user_message_content = " ".join([
                    c.text for c in last_message.content 
                    if c.type == "text" and c.text
                ])

        async def event_generator():
            try:
                async for chunk in agent_service.chat_stream(
                    user_input=user_message_content,
                    image_base64=request.image_base64,
                    use_rag=request.use_rag,
                    session_id=request.session_id,
                    use_tools=request.use_tools
                ):
                    yield f"data: {chunk}\n\n"
            except Exception as e:
                error_json = json.dumps({"type": "error", "message": str(e)})
                yield f"data: {error_json}\n\n"

        return StreamingResponse(event_generator(), media_type="text/event-stream")
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/chat/multimodal", tags=["Chat"])
async def chat_multimodal_endpoint(
    message: str = Form(...),
    image: Optional[UploadFile] = File(None),
    use_tools: bool = Form(True),
    use_rag: bool = Form(True),
    session_id: Optional[str] = Form(None)
):
    """
    多模态对话接口 (支持文件上传)
    """
    try:
        image_base64 = None
        if image:
            contents = await image.read()
            import base64
            image_base64 = base64.b64encode(contents).decode("utf-8")
        
        agent_service = get_agent_service()
        result = agent_service.chat(
            user_input=message,
            image_base64=image_base64,
            use_rag=use_rag,
            session_id=session_id
        )
        
        if result["success"]:
            return {
                "response": result["response"],
                "tool_calls": result["tool_calls"],
                "retrieved_docs": result["retrieved_docs"]
            }
        else:
            raise HTTPException(status_code=500, detail=result["response"])
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# --- 会话管理接口 ---

@app.get("/sessions", tags=["Session"])
async def list_sessions():
    """获取会话列表"""
    try:
        agent_service = get_agent_service()
        return agent_service.list_sessions()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/sessions", tags=["Session"])
async def create_session(name: str = Form(None)):
    """创建新会话"""
    try:
        agent_service = get_agent_service()
        session = agent_service.create_session(name)
        return {"id": session.session_id, "name": session.name}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/sessions/{session_id}", tags=["Session"])
async def delete_session(session_id: str):
    """删除会话"""
    try:
        agent_service = get_agent_service()
        success = agent_service.delete_session(session_id)
        if success:
            return {"status": "success"}
        else:
            raise HTTPException(status_code=404, detail="Session not found")
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/sessions/{session_id}/history", tags=["Session"])
async def get_session_history(session_id: str):
    """获取特定会话历史"""
    try:
        agent_service = get_agent_service()
        return {"history": agent_service.get_history(session_id)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


async def process_document(
    content: bytes, 
    filename: str, 
    session_id: Optional[str],
    save_to_global: bool = False
) -> dict:
    """处理上传文档 (同步)
    
    Args:
        content: 文件内容
        filename: 文件名
        session_id: 会话ID
        save_to_global: 是否保存到全局知识库（默认False，仅保存到会话级知识库）
        
    Returns:
        处理结果字典
    """
    try:
        print(f"[Upload] Processing {filename}, session={session_id}, global={save_to_global}")
        
        # 处理文档
        doc_service = get_document_service()
        chunks, metadata = await run_in_threadpool(doc_service.process_file, content, filename)
        print(f"[Upload] Parsed {filename}: {len(chunks)} chunks")
        
        # 为每个chunk创建metadata
        metadatas = [{"filename": filename, **metadata} for _ in chunks]
        
        # 存入向量库
        vector_service = get_vector_service()
        
        success = False
        message = ""
        
        if save_to_global:
            # 保存到全局知识库
            success = await run_in_threadpool(vector_service.add_documents_to_global, chunks, metadatas)
            scope = "全局知识库"
        elif session_id:
            # 保存到会话级知识库
            success = await run_in_threadpool(vector_service.add_documents_to_session, session_id, chunks, metadatas)
            scope = "会话知识库"
        else:
            # 无 session_id 且不保存全局，默认保存到全局
            success = await run_in_threadpool(vector_service.add_documents_to_global, chunks, metadatas)
            scope = "全局知识库 (默认)"
        
        if success:
            if session_id:
                # 添加到会话的上传文档列表
                agent_service = get_agent_service()
                agent_service.add_uploaded_document(filename, session_id)
            
            print(f"[Upload] Processing success: {filename} -> {scope}")
            return {
                "status": "completed",
                "filename": filename,
                "scope": scope,
                "chunks": len(chunks),
                "message": "文档处理完成"
            }
        else:
            print(f"[Upload] Vector service returned failure for {filename}. Check vector_service logs.")
            raise Exception("向量库处理失败 - vector_service returned False")
            
    except Exception as e:
        print(f"[Upload] Processing failed for {filename}: {e}")
        import traceback
        traceback.print_exc()
        raise Exception(f"处理失败: {str(e)}")


@app.post("/knowledge/upload", tags=["Knowledge"])
async def upload_document(
    file: UploadFile = File(...),
    source: str = Form("uploaded_file"),
    session_id: Optional[str] = Form(None),
    save_to_global: bool = Form(False)
):
    """
    上传文档到知识库 (同步处理)
    支持: PDF, TXT, MD
    
    Args:
        file: 上传的文件
        source: 来源标识
        session_id: 会话ID（用于会话级知识库）
        save_to_global: 是否保存到全局知识库（可跨会话访问）
    """
    try:
        # 验证文件类型
        filename = file.filename or "unknown"
        suffix = filename.lower().split(".")[-1] if "." in filename else ""
        
        if suffix not in ["pdf", "txt", "md", "text"]:
            raise HTTPException(status_code=400, detail="不支持的文件类型")
        
        # 读取文件
        content = await file.read()
        
        # 同步处理
        result = await process_document(
            content, 
            filename, 
            session_id,
            save_to_global
        )
        
        return result
            
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/knowledge/add", tags=["Knowledge"])
async def add_knowledge(content: str = Form(...), source: str = Form("manual")):
    """手动添加知识到向量库"""
    try:
        vector_service = get_vector_service()
        # 分块处理
        chunks = []
        chunk_size = 500
        for i in range(0, len(content), chunk_size):
            chunks.append(content[i:i + chunk_size])
        
        metadatas = [{"source": source, "chunk_index": i} for i in range(len(chunks))]
        success = vector_service.add_documents(chunks, metadatas)
        
        if success:
            return {"status": "success", "chunks": len(chunks), "source": source}
        else:
            raise HTTPException(status_code=500, detail="添加失败")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/knowledge/search", tags=["Knowledge"])
async def search_knowledge(query: str = Form(...), n_results: int = Form(3)):
    """搜索知识库"""
    try:
        vector_service = get_vector_service()
        results = vector_service.search(query, n_results=n_results)
        return {
            "query": query,
            "results": [
                {"document": r["content"], "metadata": r.get("metadata", {}), "distance": r.get("distance", 0)}
                for r in results
            ]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/knowledge/stats", tags=["Knowledge"])
async def get_knowledge_stats():
    """获取知识库统计"""
    try:
        vector_service = get_vector_service()
        return vector_service.get_stats()
    except Exception as e:
        return {"error": str(e)}


@app.get("/knowledge/upload/status/{filename}", tags=["Knowledge"])
async def get_upload_status(filename: str):
    """查询文档上传处理状态"""
    status = _upload_status.get(filename, "unknown")
    return {"filename": filename, "status": status}


@app.get("/sessions/{session_id}/documents", tags=["Session"])
async def get_session_documents(session_id: str):
    """获取会话的已上传文档列表"""
    try:
        agent_service = get_agent_service()
        documents = agent_service.get_uploaded_documents(session_id)
        return {"session_id": session_id, "documents": documents}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/agent/clear", tags=["Agent"])
async def clear_agent_history(session_id: Optional[str] = Form(None)):
    """清空 Agent 对话历史"""
    try:
        agent_service = get_agent_service()
        agent_service.clear_history(session_id)
        return {"message": "对话历史已清空"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
