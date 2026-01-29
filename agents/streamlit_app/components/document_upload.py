"""
文档上传组件
支持PDF和TXT文件上传
"""

import streamlit as st
from typing import Optional, Tuple


def create_document_uploader() -> Tuple[Optional[bytes], Optional[str]]:
    """
    创建文档上传组件
    
    Returns:
        (文件字节数据, 文件名) 或 (None, None)
    """
    uploaded_file = st.file_uploader(
        "选择文件",
        type=["pdf", "txt", "md"],
        help="支持 PDF、TXT、MD 文件",
        key="document_uploader"
    )
    
    if uploaded_file is not None:
        file_bytes = uploaded_file.getvalue()
        filename = uploaded_file.name
        return file_bytes, filename
    
    return None, None


def show_upload_result(result: dict):
    """
    显示上传结果
    
    Args:
        result: API返回的结果
    """
    if result.get("status") == "success":
        st.success(f"✅ {result.get('message', '上传成功')}")
        
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("文件名", result.get("filename", "-"))
        with col2:
            st.metric("文本块", result.get("chunks", 0))
        with col3:
            st.metric("字符数", result.get("total_chars", 0))
    else:
        st.error(f"❌ {result.get('message', '上传失败')}")


def show_uploaded_documents(documents: list):
    """
    显示已上传的文档列表
    
    Args:
        documents: 文档列表
    """
    if not documents:
        st.info("📭 暂无上传的文档")
        return
    
    for doc in documents:
        with st.container():
            st.markdown(f"📄 **{doc.get('filename', '未知')}**")
            st.caption(f"共 {doc.get('chunks', 0)} 个文本块")
