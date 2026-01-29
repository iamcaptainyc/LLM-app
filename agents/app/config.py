"""
配置管理模块
使用 Pydantic Settings 管理环境变量
"""

import os
from functools import lru_cache
from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    """应用配置"""
    
    # DashScope API
    dashscope_api_key: str = Field(default="", env="DASHSCOPE_API_KEY")
    
    # 模型配置
    qwen_vl_model: str = Field(default="qwen-vl-max", env="QWEN_VL_MODEL")
    embedding_model: str = Field(default="text-embedding-v2", env="EMBEDDING_MODEL")
    
    # 服务器配置
    api_host: str = Field(default="0.0.0.0", env="API_HOST")
    api_port: int = Field(default=8000, env="API_PORT")
    streamlit_port: int = Field(default=8501, env="STREAMLIT_PORT")
    
    # 向量数据库
    chroma_persist_dir: str = Field(default="./data/chroma", env="CHROMA_PERSIST_DIR")
    
    # 知识库目录
    knowledge_dir: str = Field(default="./data/knowledge", env="KNOWLEDGE_DIR")
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


@lru_cache()
def get_settings() -> Settings:
    """获取配置单例"""
    return Settings()


# 便捷访问
settings = get_settings()
