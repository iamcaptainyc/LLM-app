"""
Chroma 向量数据库服务
实现文档存储、向量化和相似度检索
"""

import os
from typing import List, Optional
from pathlib import Path

import chromadb
from chromadb.config import Settings as ChromaSettings
import dashscope
from dashscope import TextEmbedding

from app.config import settings


class VectorService:
    """向量检索服务"""
    
    def __init__(self):
        """初始化向量服务"""
        dashscope.api_key = settings.dashscope_api_key
        self.embedding_model = settings.embedding_model
        
        # 确保目录存在
        persist_dir = Path(settings.chroma_persist_dir)
        persist_dir.mkdir(parents=True, exist_ok=True)
        
        # 初始化 Chroma 客户端
        self.client = chromadb.PersistentClient(
            path=str(persist_dir),
            settings=ChromaSettings(anonymized_telemetry=False)
        )
        
        # 获取或创建集合
        self.collection = self.client.get_or_create_collection(
            name="knowledge_base",
            metadata={"description": "多模态Agent知识库"}
        )
    
    def _get_embedding(self, text: str) -> List[float]:
        """
        获取文本嵌入向量
        
        Args:
            text: 输入文本
            
        Returns:
            嵌入向量
        """
        try:
            response = TextEmbedding.call(
                model=self.embedding_model,
                input=text
            )
            
            if response.status_code == 200:
                return response.output["embeddings"][0]["embedding"]
            else:
                raise Exception(f"Embedding error: {response.code}")
                
        except Exception as e:
            print(f"Embedding error: {e}")
            # 返回零向量作为fallback
            return [0.0] * 1536
    
    def _get_embeddings_batch(self, texts: List[str]) -> List[List[float]]:
        """
        批量获取文本嵌入向量 (并发分批处理)
        """
        import concurrent.futures
        
        # DashScope 限制通常为 25
        BATCH_SIZE = 25
        batches = []
        for i in range(0, len(texts), BATCH_SIZE):
            batches.append((i, texts[i : i + BATCH_SIZE]))
            
        embeddings_map = {}
        
        def process_batch(batch_info):
            start_idx, batch_texts = batch_info
            try:
                response = TextEmbedding.call(
                    model=self.embedding_model,
                    input=batch_texts
                )
                    
                if response.status_code == 200:
                    return start_idx, [item["embedding"] for item in response.output["embeddings"]]
                else:
                    return start_idx, [[0.0] * 1536 for _ in batch_texts]
            except Exception as e:
                print(f"Batch embedding exception: {e}")
                return start_idx, [[0.0] * 1536 for _ in batch_texts]

        # 使用线程池并发请求
        # 限制最大工作线程，避免触发 API 限制
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            results = list(executor.map(process_batch, batches))
            
        # 整理结果
        for start_idx, batch_embeddings in results:
            for i, emb in enumerate(batch_embeddings):
                embeddings_map[start_idx + i] = emb
                
        # 按顺序重组
        return [embeddings_map[i] for i in range(len(texts))]
    
    def add_documents(
        self,
        documents: List[str],
        metadatas: Optional[List[dict]] = None,
        ids: Optional[List[str]] = None
    ) -> bool:
        """
        添加文档到向量库
        """
        import time
        try:
            # 生成ID
            if ids is None:
                existing_count = self.collection.count()
                ids = [f"doc_{existing_count + i}" for i in range(len(documents))]
            
            # 生成嵌入
            t0 = time.time()
            embeddings = self._get_embeddings_batch(documents)
            t1 = time.time()
            print(f"DEBUG: _get_embeddings_batch took {t1 - t0:.2f}s for {len(documents)} docs")
            
            # 添加到集合
            t2 = time.time()
            self.collection.add(
                documents=documents,
                embeddings=embeddings,
                metadatas=metadatas or [{}] * len(documents),
                ids=ids
            )
            t3 = time.time()
            print(f"DEBUG: collection.add took {t3 - t2:.2f}s")
            
            return True
            
        except Exception as e:
            print(f"Add documents error: {e}")
            return False
    
    def search(
        self,
        query: str,
        n_results: int = 3,
        filter: Optional[dict] = None
    ) -> List[dict]:
        """
        相似度检索
        
        Args:
            query: 查询文本
            n_results: 返回结果数量
            filter: 元数据过滤条件 (e.g. {"filename": "doc.pdf"})
            
        Returns:
            检索结果列表
        """
        try:
            # 获取查询向量
            query_embedding = self._get_embedding(query)
            
            # 准备查询参数
            query_params = {
                "query_embeddings": [query_embedding],
                "n_results": n_results,
                "include": ["documents", "metadatas", "distances"]
            }
            
            # 添加过滤条件
            if filter:
                query_params["where"] = filter
            
            # 执行检索
            results = self.collection.query(**query_params)
            
            # 格式化结果
            formatted_results = []
            if results["documents"] and results["documents"][0]:
                for i, doc in enumerate(results["documents"][0]):
                    formatted_results.append({
                        "content": doc,
                        "metadata": results["metadatas"][0][i] if results["metadatas"] else {},
                        "distance": results["distances"][0][i] if results["distances"] else 0,
                        "id": results["ids"][0][i] if results["ids"] else ""
                    })
            
            return formatted_results
            
        except Exception as e:
            print(f"Search error: {e}")
            return []
    
    def load_knowledge_directory(self, directory: Optional[str] = None) -> int:
        """
        从目录加载知识文档
        
        Args:
            directory: 知识库目录路径
            
        Returns:
            加载的文档数量
        """
        knowledge_dir = Path(directory or settings.knowledge_dir)
        
        if not knowledge_dir.exists():
            knowledge_dir.mkdir(parents=True, exist_ok=True)
            return 0
        
        documents = []
        metadatas = []
        
        # 支持的文件类型
        supported_extensions = {".txt", ".md", ".json"}
        
        for file_path in knowledge_dir.rglob("*"):
            if file_path.suffix.lower() in supported_extensions:
                try:
                    content = file_path.read_text(encoding="utf-8")
                    
                    # 分块处理长文档
                    chunks = self._chunk_text(content, chunk_size=500)
                    
                    for i, chunk in enumerate(chunks):
                        documents.append(chunk)
                        metadatas.append({
                            "source": str(file_path),
                            "chunk_index": i,
                            "file_type": file_path.suffix
                        })
                        
                except Exception as e:
                    print(f"Error loading {file_path}: {e}")
        
        if documents:
            self.add_documents(documents, metadatas)
        
        return len(documents)
    
    def _chunk_text(self, text: str, chunk_size: int = 500, overlap: int = 50) -> List[str]:
        """
        文本分块
        
        Args:
            text: 原始文本
            chunk_size: 块大小
            overlap: 重叠大小
            
        Returns:
            文本块列表
        """
        if len(text) <= chunk_size:
            return [text]
        
        chunks = []
        start = 0
        
        while start < len(text):
            end = start + chunk_size
            chunk = text[start:end]
            chunks.append(chunk)
            start = end - overlap
        
        return chunks
    
    def get_stats(self) -> dict:
        """获取向量库统计信息"""
        return {
            "collection_name": self.collection.name,
            "document_count": self.collection.count(),
            "embedding_model": self.embedding_model
        }
    
    def clear(self) -> bool:
        """清空全局向量库"""
        try:
            self.client.delete_collection("knowledge_base")
            self.collection = self.client.get_or_create_collection(
                name="knowledge_base",
                metadata={"description": "多模态Agent知识库"}
            )
            return True
        except Exception as e:
            print(f"Clear error: {e}")
            return False

    # =========================
    # 会话级知识库方法
    # =========================
    
    def get_session_collection(self, session_id: str):
        """获取或创建会话级 collection"""
        collection_name = f"session_{session_id[:8]}"  # 使用 session_id 前8位作为名称
        return self.client.get_or_create_collection(
            name=collection_name,
            metadata={"description": f"会话 {session_id} 的临时知识库", "session_id": session_id}
        )
    
    def add_documents_to_session(
        self,
        session_id: str,
        documents: List[str],
        metadatas: Optional[List[dict]] = None,
        ids: Optional[List[str]] = None
    ) -> bool:
        """添加文档到会话级知识库"""
        import time
        try:
            collection = self.get_session_collection(session_id)
            
            # 生成ID
            if ids is None:
                existing_count = collection.count()
                ids = [f"sdoc_{existing_count + i}" for i in range(len(documents))]
            
            # 生成嵌入
            t0 = time.time()
            embeddings = self._get_embeddings_batch(documents)
            t1 = time.time()
            print(f"DEBUG: Session embedding took {t1 - t0:.2f}s for {len(documents)} docs")
            
            # 添加到集合
            collection.add(
                documents=documents,
                embeddings=embeddings,
                metadatas=metadatas or [{}] * len(documents),
                ids=ids
            )
            
            return True
            
        except Exception as e:
            print(f"Add session documents error: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def add_documents_to_global(
        self,
        documents: List[str],
        metadatas: Optional[List[dict]] = None,
        ids: Optional[List[str]] = None
    ) -> bool:
        """添加文档到全局知识库（等同于 add_documents）"""
        return self.add_documents(documents, metadatas, ids)
    
    def search_session(
        self,
        session_id: str,
        query: str,
        n_results: int = 5,
        filter: Optional[dict] = None
    ) -> List[dict]:
        """从会话级知识库检索"""
        try:
            collection = self.get_session_collection(session_id)
            
            # 检查 collection 是否为空
            if collection.count() == 0:
                return []
            
            query_embedding = self._get_embedding(query)
            
            query_params = {
                "query_embeddings": [query_embedding],
                "n_results": n_results,
                "include": ["documents", "metadatas", "distances"]
            }
            
            if filter:
                query_params["where"] = filter
            
            results = collection.query(**query_params)
            
            formatted_results = []
            if results["documents"] and results["documents"][0]:
                for i, doc in enumerate(results["documents"][0]):
                    formatted_results.append({
                        "content": doc,
                        "metadata": results["metadatas"][0][i] if results["metadatas"] else {},
                        "distance": results["distances"][0][i] if results["distances"] else 0,
                        "id": results["ids"][0][i] if results["ids"] else "",
                        "source": "session"
                    })
            
            return formatted_results
            
        except Exception as e:
            print(f"Session search error: {e}")
            return []
    
    def search_global(
        self,
        query: str,
        n_results: int = 3,
        filter: Optional[dict] = None
    ) -> List[dict]:
        """从全局知识库检索"""
        results = self.search(query, n_results, filter)
        for r in results:
            r["source"] = "global"
        return results
    
    def clear_session_collection(self, session_id: str) -> bool:
        """清除会话级知识库"""
        try:
            collection_name = f"session_{session_id[:8]}"
            # 检查 collection 是否存在
            existing_collections = [c.name for c in self.client.list_collections()]
            if collection_name in existing_collections:
                self.client.delete_collection(collection_name)
                print(f"[VectorService] Cleared session collection: {collection_name}")
            return True
        except Exception as e:
            print(f"Clear session collection error: {e}")
            return False
    
    def get_session_stats(self, session_id: str) -> dict:
        """获取会话级知识库统计"""
        try:
            collection = self.get_session_collection(session_id)
            return {
                "collection_name": collection.name,
                "document_count": collection.count(),
                "session_id": session_id
            }
        except Exception as e:
            return {"error": str(e)}


# 单例
_vector_service: Optional[VectorService] = None


def get_vector_service() -> VectorService:
    """获取向量服务单例"""
    global _vector_service
    if _vector_service is None:
        _vector_service = VectorService()
    return _vector_service
