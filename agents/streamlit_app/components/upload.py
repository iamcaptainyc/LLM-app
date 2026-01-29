"""
上传组件
处理图片上传和预览
"""

import streamlit as st
from typing import Optional, Tuple
import base64
from PIL import Image
import io


def create_image_uploader() -> Tuple[Optional[bytes], Optional[str]]:
    """
    创建图片上传器
    
    Returns:
        (图片字节数据, Base64编码)
    """
    uploaded_file = st.file_uploader(
        "📷 上传图片",
        type=["jpg", "jpeg", "png", "gif", "webp"],
        help="支持 JPG、PNG、GIF、WebP 格式",
        key="image_uploader"
    )
    
    if uploaded_file is not None:
        # 读取图片数据
        image_bytes = uploaded_file.read()
        
        # 转换为 Base64
        image_base64 = base64.b64encode(image_bytes).decode("utf-8")
        
        return image_bytes, image_base64
    
    return None, None


def show_image_preview(image_bytes: bytes, caption: str = "已上传的图片"):
    """
    显示图片预览
    
    Args:
        image_bytes: 图片字节数据
        caption: 图片标题
    """
    try:
        image = Image.open(io.BytesIO(image_bytes))
        
        # 限制预览尺寸
        max_size = (400, 400)
        image.thumbnail(max_size, Image.Resampling.LANCZOS)
        
        st.image(image, caption=caption, use_container_width=True)
        
        # 显示图片信息
        original_image = Image.open(io.BytesIO(image_bytes))
        st.caption(f"尺寸: {original_image.size[0]}x{original_image.size[1]} | 格式: {original_image.format}")
        
    except Exception as e:
        st.error(f"图片预览失败: {e}")


def clear_uploaded_image():
    """清除已上传的图片"""
    if "image_uploader" in st.session_state:
        del st.session_state["image_uploader"]


def create_camera_input() -> Tuple[Optional[bytes], Optional[str]]:
    """
    创建相机输入（如果设备支持）
    
    Returns:
        (图片字节数据, Base64编码)
    """
    camera_image = st.camera_input("📸 拍照", key="camera_input")
    
    if camera_image is not None:
        image_bytes = camera_image.read()
        image_base64 = base64.b64encode(image_bytes).decode("utf-8")
        return image_bytes, image_base64
    
    return None, None
