from pydantic_settings import BaseSettings
from typing import Optional
import os

# 项目根目录: backend/ 的上级目录
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))

# 默认 JWT 密钥（用于检测是否已配置）
_DEFAULT_JWT_KEY = "gmp-audit-secret-key-change-in-production"


class Settings(BaseSettings):
    # 数据库配置
    DATABASE_URL: str = f"sqlite+aiosqlite:///{os.path.join(PROJECT_ROOT, 'data', 'database', 'gmp_audit.db')}"

    # 文件存储配置
    UPLOAD_DIR: str = os.path.join(PROJECT_ROOT, "data", "documents")
    PROCESSED_DIR: str = os.path.join(PROJECT_ROOT, "data", "processed")
    REPORTS_DIR: str = os.path.join(PROJECT_ROOT, "data", "reports")

    # LLM配置 - 所有 OpenAI 兼容提供商使用统一的 base_url 格式（含 /v1）
    DEEPSEEK_API_KEY: Optional[str] = None
    DEEPSEEK_BASE_URL: str = "https://api.deepseek.com/v1"
    QWEN_API_KEY: Optional[str] = None
    QWEN_BASE_URL: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    GLM_API_KEY: Optional[str] = None
    GLM_BASE_URL: str = "https://open.bigmodel.cn/api/paas/v4"
    OPENAI_API_KEY: Optional[str] = None
    OPENAI_BASE_URL: str = "https://api.openai.com/v1"
    ANTHROPIC_API_KEY: Optional[str] = None
    ANTHROPIC_BASE_URL: str = "https://api.anthropic.com"
    SILICONFLOW_API_KEY: Optional[str] = None
    SILICONFLOW_BASE_URL: str = "https://api.siliconflow.cn/v1"
    OPENROUTER_API_KEY: Optional[str] = None
    OPENROUTER_BASE_URL: str = "https://openrouter.ai/api/v1"
    MIMO_API_KEY: Optional[str] = None
    MIMO_BASE_URL: str = "https://api.minimax.chat/v1"

    # 飞书配置
    FEISHU_APP_ID: Optional[str] = None
    FEISHU_APP_SECRET: Optional[str] = None
    FEISHU_REDIRECT_URI: str = "http://localhost:8000/api/auth/feishu/callback"
    FEISHU_WEBHOOK_URL: Optional[str] = None

    # JWT配置
    JWT_SECRET_KEY: str = _DEFAULT_JWT_KEY

    # 应用配置
    LOG_LEVEL: str = "INFO"
    MAX_CONCURRENT_TASKS: int = 5
    DOCUMENT_PROCESS_TIMEOUT: int = 300
    LLM_REQUEST_TIMEOUT: int = 120

    class Config:
        env_file = os.path.join(PROJECT_ROOT, "config", ".env")
        env_file_encoding = "utf-8"


settings = Settings()

# 确保目录存在
os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
os.makedirs(settings.PROCESSED_DIR, exist_ok=True)
os.makedirs(settings.REPORTS_DIR, exist_ok=True)
os.makedirs(os.path.join(PROJECT_ROOT, "data", "database"), exist_ok=True)
