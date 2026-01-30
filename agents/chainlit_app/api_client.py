import os
import httpx
import json
from typing import AsyncGenerator, Dict, Any, List, Optional

class APIClient:
    """Async API Client for interacting with the backend agent service"""
    
    def __init__(self, base_url: str = "http://localhost:8000"):
        # Load from env if available
        self.base_url = os.getenv("API_URL", base_url)
        self.timeout = 600.0  # Long timeout for LLM generation
    
    async def chat_stream(
        self, 
        messages: List[Dict[str, str]], 
        image_base64: Optional[str] = None,
        use_tools: bool = True,
        use_rag: bool = True,
        session_id: str = None
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Stream chat completions from backend"""
        
        url = f"{self.base_url}/chat/stream"
        
        payload = {
            "messages": messages,
            "use_tools": use_tools,
            "use_rag": use_rag
        }
        
        if image_base64:
            payload["image_base64"] = image_base64
            
        if session_id:
            payload["session_id"] = session_id

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                # Use JSON payload for Pydantic model validation on backend
                async with client.stream("POST", url, json=payload) as response:
                    if response.status_code != 200:
                        error_text = await response.read()
                        yield {"type": "error", "message": f"API Error {response.status_code}: {error_text.decode()}"}
                        return

                    async for line in response.aiter_lines():
                        if not line.strip():
                            continue
                            
                        if line.startswith("data: "):
                            data = line[6:]
                            if data == "[DONE]":
                                break
                            
                            try:
                                chunk = json.loads(data)
                                yield chunk
                            except json.JSONDecodeError:
                                # Sometimes plain text or keep-alive might be sent
                                continue
            except Exception as e:
                yield {"type": "error", "message": f"Connection error: {str(e)}"}

    async def upload_document(
        self, 
        file_bytes: bytes, 
        filename: str, 
        session_id: str = None,
        save_to_global: bool = False
    ) -> Dict[str, Any]:
        """Upload a document to the backend knowledge base"""
        url = f"{self.base_url}/knowledge/upload"
        
        files = {"file": (filename, file_bytes)}
        data = {
            "source": "chainlit_upload",
            "save_to_global": str(save_to_global).lower(),
            "session_id": session_id or ""
        }
        
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                response = await client.post(url, files=files, data=data)
                if response.status_code == 200:
                    return response.json()
                else:
                    return {"status": "error", "message": f"Status {response.status_code}: {response.text}"}
            except Exception as e:
                return {"status": "error", "message": str(e)}

    async def list_sessions(self) -> List[Dict[str, Any]]:
        """List available sessions from backend"""
        url = f"{self.base_url}/sessions"
        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                response = await client.get(url)
                if response.status_code == 200:
                    data = response.json()
                    # Backend returns list directly or {"sessions": [...]}?
                    # Based on code `return agent_service.list_sessions()`, likely a list of dicts.
                    if isinstance(data, list):
                        return data
                    return data.get("sessions", [])
                return []
            except:
                return []

    async def get_session_history(self, session_id: str) -> List[Dict[str, Any]]:
        """Get history for a specific session"""
        url = f"{self.base_url}/sessions/{session_id}/history"
        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                response = await client.get(url)
                if response.status_code == 200:
                    return response.json().get("history", [])
                return []
            except:
                return []

    async def delete_session(self, session_id: str) -> bool:
        """Delete a session from backend"""
        url = f"{self.base_url}/sessions/{session_id}"
        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                response = await client.delete(url)
                return response.status_code == 200
            except:
                return False
