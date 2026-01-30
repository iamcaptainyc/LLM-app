"""
文档解析服务
使用 LangChain Loaders 支持多种格式 (PDF, DOCX, TXT, etc.)
"""

import os
import tempfile
from typing import List, Tuple, Optional
from pathlib import Path

# LangChain Loaders
from langchain_community.document_loaders import (
    PyPDFLoader,
    Docx2txtLoader,
    TextLoader,
    UnstructuredFileLoader
)
from langchain_text_splitters import RecursiveCharacterTextSplitter


class DocumentService:
    """文档解析服务 (LangChain版)"""
    
    def __init__(self, chunk_size: int = 500, chunk_overlap: int = 50):
        """
        初始化文档服务
        
        Args:
            chunk_size: 文本分块大小
            chunk_overlap: 分块重叠大小
        """
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        
        # 初始化通用的文本分割器
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            separators=["\n\n", "\n", "。", "！", "？", ". ", "! ", "? ", " ", ""]
        )
    
    def _get_loader(self, file_path: str):
        """
        根据文件扩展名获取合适的 Loader
        """
        ext = Path(file_path).suffix.lower()
        
        if ext == ".pdf":
            return PyPDFLoader(file_path)
        elif ext == ".docx":
            return Docx2txtLoader(file_path)
        elif ext in [".txt", ".md", ".py", ".json", ".csv"]:
            # 尝试使用 TextLoader，即使失败也可以回退
            return TextLoader(file_path, autodetect_encoding=True)
        else:
            # 对于 .doc 或其他未知类型，尝试使用 Unstructured
            # 注意: 需要安装 unstructured 和 python-magic (Windows上是 python-magic-bin)
            return UnstructuredFileLoader(file_path)

    def process_file(self, file_bytes: bytes, filename: str) -> Tuple[List[str], dict]:
        """
        处理文件：解析并分块
        
        Args:
            file_bytes: 文件字节数据
            filename: 文件名
            
        Returns:
            (文本块列表, 元数据)
        """
        # 创建临时文件
        suffix = Path(filename).suffix
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
        temp_path = temp_file.name
        
        try:
            # 写入临时文件
            temp_file.write(file_bytes)
            temp_file.close()
            
            # 获取 Loader
            try:
                loader = self._get_loader(temp_path)
                docs = loader.load()
            except Exception as e:
                # 如果 TextLoader 失败，尝试 Unstructured
                print(f"Primary loader failed for {filename}: {e}, retrying with Unstructured...")
                try:
                    loader = UnstructuredFileLoader(temp_path)
                    docs = loader.load()
                except Exception as e2:
                    raise ValueError(f"无法解析文件 {filename}: {str(e)} | Retry: {str(e2)}")
            
            if not docs:
                return [], {"filename": filename, "chunk_count": 0, "total_chars": 0}
            
            # 分割文本
            chunks = self.text_splitter.split_documents(docs)
            
            # 提取文本内容和基本统计
            chunk_texts = [chunk.page_content for chunk in chunks]
            total_chars = sum(len(c) for c in chunk_texts)
            
            # 提取元数据 (取第一个文档的 metadata 作为基础，加上自定义字段)
            base_metadata = docs[0].metadata if docs else {}
            metadata = {
                "filename": filename,
                "file_type": suffix.lstrip("."),
                "chunk_count": len(chunks),
                "total_chars": total_chars,
                # 保留 loader 提取的其他有用元数据 (如 source)
                "source": base_metadata.get("source", filename) 
            }
            
            return chunk_texts, metadata
            
        except Exception as e:
            raise ValueError(f"文件处理失败: {str(e)}")
            
        finally:
            # 清理临时文件
            if os.path.exists(temp_path):
                try:
                    os.unlink(temp_path)
                except Exception as e:
                    print(f"Error removing temp file {temp_path}: {e}")


# 单例
_document_service: Optional[DocumentService] = None


def get_document_service() -> DocumentService:
    """获取文档服务单例"""
    global _document_service
    if _document_service is None:
        _document_service = DocumentService()
    return _document_service
