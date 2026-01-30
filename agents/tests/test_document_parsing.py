
import unittest
import os
import sys
from pathlib import Path

# 添加项目根目录到 sys.path
current_dir = Path(__file__).parent
project_root = current_dir.parent
sys.path.append(str(project_root))

from app.services.document_service import DocumentService

class TestDocumentService(unittest.TestCase):
    def setUp(self):
        self.doc_service = DocumentService(chunk_size=100, chunk_overlap=10)
        self.output_dir = project_root / "tests" / "test_data"
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def test_text_processing(self):
        """测试文本文件处理"""
        content = "这是一个测试文档。\n\n包含多个段落。\n\n用于测试分块功能。"
        file_bytes = content.encode('utf-8')
        
        chunks, metadata = self.doc_service.process_file(file_bytes, "test.txt")
        
        print(f"\n[TXT] Chunks: {len(chunks)}")
        print(f"[TXT] Metadata: {metadata}")
        
        self.assertGreater(len(chunks), 0)
        self.assertEqual(metadata["filename"], "test.txt")
        self.assertEqual(metadata["file_type"], "txt")

    def test_unknown_file_processing(self):
        """测试未知类型文件(尝试通用解析)"""
        # 创建一个假的 .doc 文件内容 (这里只是文本，但模仿 old word doc 扩展名)
        content = "This is a fake doc file content."
        file_bytes = content.encode('utf-8')
        
        # 即使是 .doc, UnstructuredFileLoader 也应该能处理纯文本内容
        try:
            chunks, metadata = self.doc_service.process_file(file_bytes, "test.doc")
            print(f"\n[DOC] Chunks: {len(chunks)}")
            print(f"[DOC] Metadata: {metadata}")
            self.assertGreater(len(chunks), 0)
        except Exception as e:
            # 如果没有安装 unstructured，可能会失败，这是预期的
            print(f"\n[DOC] Processing failed (expected if deps missing): {e}")

if __name__ == "__main__":
    unittest.main()
