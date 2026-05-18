from pydantic_settings import BaseSettings
from pydantic import ConfigDict
from typing import Optional
import os

# 项目根目录: backend/ 的上级目录
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))

class Settings(BaseSettings):
    # 数据库配置
    DATABASE_URL: str = f"sqlite+aiosqlite:///{os.path.join(PROJECT_ROOT, 'data', 'database', 'gmp_audit.db').replace(os.sep, '/')}"

    # 文件存储配置
    UPLOAD_DIR: str = os.path.join(PROJECT_ROOT, "data", "documents")
    PROCESSED_DIR: str = os.path.join(PROJECT_ROOT, "data", "processed")
    REPORTS_DIR: str = os.path.join(PROJECT_ROOT, "data", "reports")

    # LLM配置 - 所有 OpenAI 兼容提供商使用统一的 base_url 格式（含 /v1）
    DEEPSEEK_API_KEY: Optional[str] = None
    DEEPSEEK_BASE_URL: str = "https://api.deepseek.com/v1"
    DEEPSEEK_MODEL: str = "deepseek-chat"
    QWEN_API_KEY: Optional[str] = None
    QWEN_BASE_URL: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    QWEN_MODEL: str = "qwen-plus"
    GLM_API_KEY: Optional[str] = None
    GLM_BASE_URL: str = "https://open.bigmodel.cn/api/paas/v4"
    GLM_MODEL: str = "glm-4-flash"
    OPENAI_API_KEY: Optional[str] = None
    OPENAI_BASE_URL: str = "https://api.openai.com/v1"
    OPENAI_MODEL: str = "gpt-4o"
    ANTHROPIC_API_KEY: Optional[str] = None
    ANTHROPIC_BASE_URL: str = "https://api.anthropic.com"
    ANTHROPIC_MODEL: str = "claude-sonnet-4-20250514"
    SILICONFLOW_API_KEY: Optional[str] = None
    SILICONFLOW_BASE_URL: str = "https://api.siliconflow.cn/v1"
    SILICONFLOW_MODEL: str = "deepseek-ai/DeepSeek-V3.2"
    OPENROUTER_API_KEY: Optional[str] = None
    OPENROUTER_BASE_URL: str = "https://openrouter.ai/api/v1"
    OPENROUTER_MODEL: str = "deepseek/deepseek-chat"
    MIMO_API_KEY: Optional[str] = None
    MIMO_BASE_URL: str = "https://api.xiaomimimo.com/v1"
    MIMO_MODEL: str = "mimo-v2.5-pro"

    # 飞书配置
    FEISHU_WEBHOOK_URL: Optional[str] = None
    FEISHU_WEBHOOK_SECRET: Optional[str] = None

    # Agent 配置
    AGENT_LLM_PROVIDER: str = "mimo"

    # 应用配置
    TEMPERATURE: float = 0.7
    LOG_LEVEL: str = "INFO"
    MAX_CONCURRENT_TASKS: int = 5
    DOCUMENT_PROCESS_TIMEOUT: int = 300
    LLM_REQUEST_TIMEOUT: int = 120

    model_config = ConfigDict(
        env_file=os.path.join(PROJECT_ROOT, "config", ".env"),
        env_file_encoding="utf-8",
        frozen=False,
        extra="ignore",
    )


settings = Settings()
