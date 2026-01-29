import requests
import json
from typing import Optional, Dict, Any, List

class APIClient:
    """后端 API 客户端"""
    
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url.rstrip("/")
        
    def check_health(self) -> Dict[str, Any]:
        """检查 API 健康状态"""
        try:
            response = requests.get(f"{self.base_url}/health", timeout=5)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            return {"status": "error", "error": str(e)}

    # --- 会话管理 ---
    
    def list_sessions(self) -> List[Dict[str, Any]]:
        """获取所有会话"""
        try:
            response = requests.get(f"{self.base_url}/sessions", timeout=5)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"Error listing sessions: {e}")
            return []
            
    def create_session(self, name: Optional[str] = None) -> Dict[str, Any]:
        """创建新会话"""
        try:
            data = {"name": name} if name else {}
            response = requests.post(f"{self.base_url}/sessions", data=data, timeout=5)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"Error creating session: {e}")
            return {}
            
    def delete_session(self, session_id: str) -> bool:
        """删除会话"""
        try:
            response = requests.delete(f"{self.base_url}/sessions/{session_id}", timeout=5)
            response.raise_for_status()
            return True
        except Exception as e:
            print(f"Error deleting session: {e}")
            return False
            
    def get_session_history(self, session_id: str) -> List[Dict[str, Any]]:
        """获取会话记录"""
        try:
            response = requests.get(f"{self.base_url}/sessions/{session_id}/history", timeout=5)
            response.raise_for_status()
            return response.json().get("history", [])
        except Exception as e:
            print(f"Error getting history: {e}")
            return []

    # --- 核心功能 (支持 Session) ---

    def chat(
        self, 
        messages: List[Dict[str, str]], 
        image_base64: Optional[str] = None,
        use_tools: bool = True,
        use_rag: bool = True,
        stream: bool = False,
        session_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        发送聊天请求
        """
        endpoint = f"{self.base_url}/chat"
        
        payload = {
            "messages": messages,
            "image_base64": image_base64,
            "use_tools": use_tools,
            "use_rag": use_rag,
            "stream": stream,
            "session_id": session_id
        }
        
        try:
            # 设置较长的超时时间，因为涉及RAG和工具调用
            response = requests.post(endpoint, json=payload, timeout=60)
            response.raise_for_status()
            return response.json()
            
        except requests.exceptions.Timeout:
            return {
                "success": False, 
                "response": "请求超时，请稍后重试", 
                "tool_calls": []
            }
        except Exception as e:
            return {
                "success": False, 
                "response": f"API调用错误: {str(e)}", 
                "tool_calls": []
            }

    def chat_stream(
        self, 
        messages: List[Dict[str, str]], 
        image_base64: Optional[str] = None,
        use_tools: bool = True,
        use_rag: bool = True,
        session_id: Optional[str] = None
    ):
        """流式发送聊天请求 (Generator)"""
        endpoint = f"{self.base_url}/chat/stream"
        
        payload = {
            "messages": messages,
            "image_base64": image_base64,
            "use_tools": use_tools,
            "use_rag": use_rag,
            "stream": True,
            "session_id": session_id
        }
        
        try:
            with requests.post(endpoint, json=payload, stream=True, timeout=60) as response:
                response.raise_for_status()
                
                for line in response.iter_lines():
                    if line:
                        line = line.decode('utf-8')
                        if line.startswith("data: "):
                            data_str = line[6:]
                            try:
                                yield json.loads(data_str)
                            except json.JSONDecodeError:
                                print(f"Parse error: {data_str}")
                                
        except Exception as e:
            yield {"type": "error", "message": str(e)}

    def chat_multimodal(
        self,
        message: str,
        image_bytes: Optional[bytes] = None,
        use_tools: bool = True,
        use_rag: bool = True,
        session_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        多模态对话 (直接上传图片)
        """
        endpoint = f"{self.base_url}/chat/multimodal"
        
        files = {}
        if image_bytes:
            files["image"] = ("image.jpg", image_bytes, "image/jpeg")
            
        data = {
            "message": message,
            "use_tools": str(use_tools).lower(),
            "use_rag": str(use_rag).lower()
        }
        if session_id:
            data["session_id"] = session_id
        
        try:
            response = requests.post(
                endpoint, 
                data=data, 
                files=files if files else None,
                timeout=60
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            return {"response": f"API Error: {str(e)}"}

    def upload_document(
        self, 
        file_bytes: bytes, 
        filename: str, 
        session_id: Optional[str] = None,
        save_to_global: bool = False
    ) -> Dict[str, Any]:
        """上传文档到知识库
        
        Args:
            file_bytes: 文件内容
            filename: 文件名
            session_id: 会话ID
            save_to_global: 是否保存到全局知识库（默认为会话级）
        """
        endpoint = f"{self.base_url}/knowledge/upload"
        
        files = {
            "file": (filename, file_bytes, "application/pdf" if filename.endswith(".pdf") else "text/plain")
        }
        data = {
            "source": "uploaded_file",
            "save_to_global": str(save_to_global).lower()
        }
        if session_id:
            data["session_id"] = session_id
        
        try:
            # 上传文件可能需要较长时间
            response = requests.post(endpoint, files=files, data=data, timeout=30)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            return {"status": "error", "message": f"Upload failed: {str(e)}"}
            
    def get_knowledge_stats(self) -> Dict[str, Any]:
        """获取知识库统计"""
        try:
            response = requests.get(f"{self.base_url}/knowledge/stats", timeout=5)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            return {"error": str(e)}
    
    def get_upload_status(self, filename: str) -> Dict[str, Any]:
        """查询文档上传状态"""
        try:
            response = requests.get(f"{self.base_url}/knowledge/upload/status/{filename}", timeout=5)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            return {"status": "error", "error": str(e)}
    
    def get_session_documents(self, session_id: str) -> List[str]:
        """获取会话的已上传文档列表"""
        try:
            response = requests.get(f"{self.base_url}/sessions/{session_id}/documents", timeout=5)
            response.raise_for_status()
            return response.json().get("documents", [])
        except Exception as e:
            print(f"Error getting session documents: {e}")
            return []
            
    def clear_history(self, session_id: Optional[str] = None) -> Dict[str, Any]:
        """清空对话历史"""
        try:
            data = {}
            if session_id:
                data["session_id"] = session_id
                
            response = requests.post(f"{self.base_url}/agent/clear", data=data, timeout=5)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            return {"error": str(e)}
