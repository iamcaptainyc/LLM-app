"""
自定义 Chainlit 数据层
使用本地 JSON 文件进行会话持久化，独立于后端 API
"""

import uuid
import json
import os
from datetime import datetime
from typing import Dict, List, Optional, Any, TYPE_CHECKING, Union
from pathlib import Path

from chainlit.data.base import BaseDataLayer
from chainlit.types import (
    Feedback,
    PaginatedResponse,
    Pagination,
    ThreadDict,
    ThreadFilter,
    PageInfo,
)
from chainlit.user import PersistedUser, User
from chainlit.logger import logger
from chainlit_app.api_client import APIClient

if TYPE_CHECKING:
    from chainlit.element import Element, ElementDict
    from chainlit.step import StepDict


class CustomDataLayer(BaseDataLayer):
    """
    自定义数据层，使用本地文件存储 (JSON)
    这允许 Chainlit 的历史记录侧边栏正常工作，而不依赖后端的会话列表
    """
    
    
    def __init__(self, storage_path: str = "./data/chainlit_storage"):
        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(parents=True, exist_ok=True)
        self.api_client = APIClient()
        
        # 内存缓存
        self._users: Dict[str, PersistedUser] = {}
        self._threads: Dict[str, ThreadDict] = {}
        self._steps: Dict[str, "StepDict"] = {}
        self._elements: Dict[str, "ElementDict"] = {}
        self._feedbacks: Dict[str, Feedback] = {}
        
        # 加载已有数据
        self._load_data()
        
        logger.info(f"CustomDataLayer (Local) 初始化完成，存储路径: {self.storage_path}")
    
    def _load_data(self):
        """从文件加载数据"""
        try:
            users_file = self.storage_path / "users.json"
            if users_file.exists():
                with open(users_file, "r", encoding="utf-8") as f:
                    users_data = json.load(f)
                    for uid, udata in users_data.items():
                        self._users[uid] = PersistedUser(**udata)
            
            threads_file = self.storage_path / "threads.json"
            if threads_file.exists():
                with open(threads_file, "r", encoding="utf-8") as f:
                    try:
                        self._threads = json.load(f)
                    except json.JSONDecodeError:
                        self._threads = {}
                    
        except Exception as e:
            logger.warning(f"加载数据失败: {e}")
    
    def _save_data(self):
        """保存数据到文件"""
        try:
            users_file = self.storage_path / "users.json"
            with open(users_file, "w", encoding="utf-8") as f:
                users_data = {
                    uid: {
                        "id": u.id,
                        "identifier": u.identifier,
                        "createdAt": u.createdAt,
                        "metadata": u.metadata
                    }
                    for uid, u in self._users.items()
                }
                json.dump(users_data, f, ensure_ascii=False, indent=2)
            
            threads_file = self.storage_path / "threads.json"
            with open(threads_file, "w", encoding="utf-8") as f:
                json.dump(self._threads, f, ensure_ascii=False, indent=2)
                
        except Exception as e:
            logger.warning(f"保存数据失败: {e}")
            
    # ========== User 相关 ==========
    
    async def get_user(self, identifier: str) -> Optional[PersistedUser]:
        """获取用户"""
        for user in self._users.values():
            if user.identifier == identifier:
                return user
        return None
    
    async def create_user(self, user: User) -> Optional[PersistedUser]:
        """创建用户"""
        existing = await self.get_user(user.identifier)
        if existing:
            return existing
        
        persisted = PersistedUser(
            id=str(uuid.uuid4()),
            identifier=user.identifier,
            createdAt=datetime.now().isoformat(),
            metadata=user.metadata or {}
        )
        self._users[persisted.id] = persisted
        self._save_data()
        return persisted
    
    # ========== Feedback 相关 ==========
    
    async def delete_feedback(self, feedback_id: str) -> bool:
        """删除反馈"""
        if feedback_id in self._feedbacks:
            del self._feedbacks[feedback_id]
            return True
        return False
    
    async def upsert_feedback(self, feedback: Feedback) -> str:
        """创建或更新反馈"""
        feedback_id = feedback.id or str(uuid.uuid4())
        self._feedbacks[feedback_id] = feedback
        return feedback_id
    
    # ========== Element 相关 ==========
    
    async def create_element(self, element: "Element"):
        """创建元素"""
        element_dict = element.to_dict()
        self._elements[element.id] = element_dict
    
    async def get_element(
        self, thread_id: str, element_id: str
    ) -> Optional["ElementDict"]:
        """获取元素"""
        return self._elements.get(element_id)
    
    async def delete_element(self, element_id: str, thread_id: Optional[str] = None):
        """删除元素"""
        if element_id in self._elements:
            del self._elements[element_id]
    
    # ========== Step 相关 ==========
    
    async def create_step(self, step_dict: "StepDict"):
        """创建步骤 (保存消息)"""
        step_id = step_dict.get("id")
        if step_id:
            self._steps[step_id] = step_dict
            
            # 将步骤添加到对应的 thread
            thread_id = step_dict.get("threadId")
            if thread_id:
                if thread_id not in self._threads:
                    # 如果线程不存在（极少情况），先创建线程占位
                    self._threads[thread_id] = {
                        "id": thread_id,
                        "createdAt": step_dict.get("createdAt") or datetime.now().isoformat(),
                        "steps": []
                    }
                
                if "steps" not in self._threads[thread_id]:
                    self._threads[thread_id]["steps"] = []
                    
                self._threads[thread_id]["steps"].append(step_dict)
                self._save_data()
    
    async def update_step(self, step_dict: "StepDict"):
        """更新步骤"""
        step_id = step_dict.get("id")
        if step_id and step_id in self._steps:
            self._steps[step_id].update(step_dict)
            # 同时也需要更新 threads 里的 step 副本，比较麻烦
            # 简单起见，我们假设 Chainlit 是读写分离的或者仅仅是追加。
            # 为了严谨，我们应该遍历更新，但考虑到性能，这里仅更新 _steps 字典。
            # 实际持久化时，threads.json 包含了 steps。所以我们需要更新 _threads 里的 step。
            
            thread_id = step_dict.get("threadId")
            if thread_id and thread_id in self._threads:
                # 找到并更新
                steps = self._threads[thread_id].get("steps", [])
                for i, s in enumerate(steps):
                    if s["id"] == step_id:
                        steps[i].update(step_dict)
                        break
                self._save_data()
    
    async def delete_step(self, step_id: str):
        """删除步骤"""
        if step_id in self._steps:
            del self._steps[step_id]
            # 同样需要从 threads 中删除
            # 略...
    
    # ========== Thread 相关 ==========
    
    async def get_thread_author(self, thread_id: str) -> str:
        """获取线程作者"""
        thread = self._threads.get(thread_id)
        if thread:
            return thread.get("userIdentifier", "")
        return ""
    
    async def delete_thread(self, thread_id: str):
        """删除线程"""
        if thread_id in self._threads:
            del self._threads[thread_id]
            self._save_data()
            
        # 同步删除后端会话
        try:
            await self.api_client.delete_session(thread_id)
        except Exception:
            pass
    
    async def list_threads(
        self, pagination: Pagination, filters: ThreadFilter
    ) -> PaginatedResponse[ThreadDict]:
        """列出线程"""
        # 过滤用户的线程
        user_threads = []
        
        # 安全获取 filtering 属性
        filter_user_id = filters.userId if hasattr(filters, "userId") else None
        
        for thread in self._threads.values():
            if filter_user_id and thread.get("userId") != filter_user_id:
                continue
            user_threads.append(thread)
        
        # 按创建时间倒序排序
        user_threads.sort(key=lambda x: x.get("createdAt", ""), reverse=True)
        
        # 分页
        first = pagination.first or 20
        cursor = pagination.cursor
        
        start_idx = 0
        if cursor:
            for i, t in enumerate(user_threads):
                if t.get("id") == cursor:
                    start_idx = i + 1
                    break
        
        end_idx = start_idx + first
        page_threads = user_threads[start_idx:end_idx]
        
        has_next = end_idx < len(user_threads)
        
        # 安全获取 cursor
        end_cursor = page_threads[-1].get("id") if page_threads else None
        start_cursor = page_threads[0].get("id") if page_threads else None
        has_previous = start_idx > 0
        
        return PaginatedResponse(
            data=page_threads,
            pageInfo=PageInfo(
                hasNextPage=has_next,
                endCursor=end_cursor,
                startCursor=start_cursor,
                hasPreviousPage=has_previous
            )
        )
    
    async def get_thread(self, thread_id: str) -> Optional[ThreadDict]:
        """获取线程"""
        return self._threads.get(thread_id)
    
    async def update_thread(
        self,
        thread_id: str,
        name: Optional[str] = None,
        user_id: Optional[str] = None,
        metadata: Optional[Dict] = None,
        tags: Optional[List[str]] = None,
    ):
        """更新线程"""
        if thread_id not in self._threads:
            # 创建新线程
            self._threads[thread_id] = {
                "id": thread_id,
                "createdAt": datetime.now().isoformat(),
                "steps": []
            }
        
        thread = self._threads[thread_id]
        
        if name is not None:
            thread["name"] = name
        if user_id is not None:
            thread["userId"] = user_id
            # 查找用户标识符
            user = self._users.get(user_id)
            if user:
                thread["userIdentifier"] = user.identifier
        if metadata is not None:
            thread["metadata"] = metadata
        if tags is not None:
            thread["tags"] = tags
        
        self._save_data()
    
    # ========== 其他方法 ==========
    
    async def build_debug_url(self) -> str:
        """构建调试URL"""
        return ""
    
    async def close(self) -> None:
        """关闭数据层"""
        self._save_data()
    
    async def get_favorite_steps(self, user_id: str) -> List["StepDict"]:
        """获取收藏的步骤"""
        return []
