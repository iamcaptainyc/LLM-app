"""
文档解析服务
支持PDF和TXT文件的解析与索引
"""

import io
from typing import List, Tuple, Optional
from pathlib import Path

from pypdf import PdfReader


class DocumentService:
    """文档解析服务"""
    
    def __init__(self, chunk_size: int = 500, chunk_overlap: int = 50):
        """
        初始化文档服务
        
        Args:
            chunk_size: 文本分块大小
            chunk_overlap: 分块重叠大小
        """
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
    
    def parse_pdf(self, file_bytes: bytes) -> Tuple[str, dict]:
        """
        解析PDF文件
        
        Args:
            file_bytes: PDF文件字节数据
            
        Returns:
            (提取的文本, 元数据)
        """
        try:
            reader = PdfReader(io.BytesIO(file_bytes))
            
            # 提取所有页面文本
            text_parts = []
            for page_num, page in enumerate(reader.pages):
                page_text = page.extract_text()
                if page_text:
                    text_parts.append(page_text)
            
            full_text = "\n\n".join(text_parts)
            
            # 提取元数据
            metadata = {
                "page_count": len(reader.pages),
                "file_type": "pdf",
            }
            
            # 尝试获取PDF元数据
            if reader.metadata:
                if reader.metadata.title:
                    metadata["title"] = reader.metadata.title
                if reader.metadata.author:
                    metadata["author"] = reader.metadata.author
            
            return full_text, metadata
            
        except Exception as e:
            raise ValueError(f"PDF解析失败: {str(e)}")
    
    def parse_txt(self, file_bytes: bytes, encoding: str = "utf-8") -> Tuple[str, dict]:
        """
        解析TXT文件
        
        Args:
            file_bytes: TXT文件字节数据
            encoding: 文件编码
            
        Returns:
            (文本内容, 元数据)
        """
        try:
            # 尝试多种编码
            encodings = [encoding, "utf-8", "gbk", "gb2312", "latin-1"]
            
            for enc in encodings:
                try:
                    text = file_bytes.decode(enc)
                    return text, {"file_type": "txt", "encoding": enc}
                except UnicodeDecodeError:
                    continue
            
            # 最后使用errors='replace'
            text = file_bytes.decode("utf-8", errors="replace")
            return text, {"file_type": "txt", "encoding": "utf-8-replace"}
            
        except Exception as e:
            raise ValueError(f"TXT解析失败: {str(e)}")
    
    def parse_file(self, file_bytes: bytes, filename: str) -> Tuple[str, dict]:
        """
        根据文件名自动解析文件
        
        Args:
            file_bytes: 文件字节数据
            filename: 文件名
            
        Returns:
            (文本内容, 元数据)
        """
        suffix = Path(filename).suffix.lower()
        
        if suffix == ".pdf":
            text, metadata = self.parse_pdf(file_bytes)
        elif suffix in [".txt", ".md", ".text"]:
            text, metadata = self.parse_txt(file_bytes)
        else:
            raise ValueError(f"不支持的文件类型: {suffix}")
        
        metadata["filename"] = filename
        return text, metadata
    
    def chunk_text(self, text: str) -> List[str]:
        """
        将文本分块
        
        Args:
            text: 原始文本
            
        Returns:
            文本块列表
        """
        if len(text) <= self.chunk_size:
            return [text.strip()] if text.strip() else []
        
        chunks = []
        
        # 按段落分割
        paragraphs = text.split("\n\n")
        current_chunk = ""
        
        for para in paragraphs:
            para = para.strip()
            if not para:
                continue
            
            # 如果当前段落加上现有内容不超过限制
            if len(current_chunk) + len(para) + 2 <= self.chunk_size:
                current_chunk += ("\n\n" if current_chunk else "") + para
            else:
                # 保存当前块
                if current_chunk:
                    chunks.append(current_chunk)
                
                # 如果段落本身太长，需要进一步分割
                if len(para) > self.chunk_size:
                    sub_chunks = self._split_long_paragraph(para)
                    chunks.extend(sub_chunks[:-1])
                    current_chunk = sub_chunks[-1] if sub_chunks else ""
                else:
                    current_chunk = para
        
        # 添加最后一块
        if current_chunk:
            chunks.append(current_chunk)
        
        return chunks
    
    def _split_long_paragraph(self, text: str) -> List[str]:
        """分割长段落"""
        chunks = []
        start = 0
        
        while start < len(text):
            end = start + self.chunk_size
            
            # 尝试在句子边界分割
            if end < len(text):
                # 寻找句号、问号、感叹号
                for sep in ["。", "！", "？", ". ", "! ", "? "]:
                    pos = text.rfind(sep, start, end)
                    if pos > start:
                        end = pos + len(sep)
                        break
            
            chunk = text[start:end].strip()
            if chunk:
                chunks.append(chunk)
            
            start = end - self.chunk_overlap
            if start < 0:
                start = 0
        
        return chunks
    
    def process_file(self, file_bytes: bytes, filename: str) -> Tuple[List[str], dict]:
        """
        处理文件：解析并分块
        
        Args:
            file_bytes: 文件字节数据
            filename: 文件名
            
        Returns:
            (文本块列表, 元数据)
        """
        # 解析文件
        text, metadata = self.parse_file(file_bytes, filename)
        
        # 分块
        chunks = self.chunk_text(text)
        
        metadata["chunk_count"] = len(chunks)
        metadata["total_chars"] = len(text)
        
        return chunks, metadata


# 单例
_document_service: Optional[DocumentService] = None


def get_document_service() -> DocumentService:
    """获取文档服务单例"""
    global _document_service
    if _document_service is None:
        _document_service = DocumentService()
    return _document_service
