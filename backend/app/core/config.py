from pydantic_settings import BaseSettings
from typing import Optional
import os

class Settings(BaseSettings):
    # 数据库配置
    DATABASE_URL: str = "sqlite+aiosqlite:///./data/database/gmp_audit.db"

    # 文件存储配置
    UPLOAD_DIR: str = "./data/documents"
    PROCESSED_DIR: str = "./data/processed"
    REPORTS_DIR: str = "./data/reports"

    # LLM配置
    DEEPSEEK_API_KEY: Optional[str] = None
    DEEPSEEK_BASE_URL: str = "https://api.deepseek.com"
    QWEN_API_KEY: Optional[str] = None
    GLM_API_KEY: Optional[str] = None

    # OCR配置
    PADDLEOCR_LANG: str = "ch"

    # ChromaDB配置
    CHROMA_PERSIST_DIR: str = "./data/database/chroma"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

settings = Settings()

# 确保目录存在
os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
os.makedirs(settings.PROCESSED_DIR, exist_ok=True)
os.makedirs(settings.REPORTS_DIR, exist_ok=True)
