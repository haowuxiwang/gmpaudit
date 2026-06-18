import os

from pydantic import ConfigDict
from pydantic_settings import BaseSettings

from app.core import paths as _paths


class Settings(BaseSettings):
    # 数据库配置
    DATABASE_URL: str = f"sqlite+aiosqlite:///{_paths.DB_DIR / 'gmp_audit.db'}".replace(os.sep, "/")

    # 文件存储配置
    UPLOAD_DIR: str = str(_paths.DOCS_DIR)
    PROCESSED_DIR: str = str(_paths.PROCESSED_DIR)
    REPORTS_DIR: str = str(_paths.REPORTS_DIR)

    # LLM配置 - 所有 OpenAI 兼容提供商使用统一的 base_url 格式（含 /v1）
    DEEPSEEK_API_KEY: str | None = None
    DEEPSEEK_BASE_URL: str = "https://api.deepseek.com/v1"
    DEEPSEEK_MODEL: str = "deepseek-chat"
    QWEN_API_KEY: str | None = None
    QWEN_BASE_URL: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    QWEN_MODEL: str = "qwen-plus"
    GLM_API_KEY: str | None = None
    GLM_BASE_URL: str = "https://open.bigmodel.cn/api/paas/v4"
    GLM_MODEL: str = "glm-4-flash"
    OPENAI_API_KEY: str | None = None
    OPENAI_BASE_URL: str = "https://api.openai.com/v1"
    OPENAI_MODEL: str = "gpt-4o"
    ANTHROPIC_API_KEY: str | None = None
    ANTHROPIC_BASE_URL: str = "https://api.anthropic.com"
    ANTHROPIC_MODEL: str = "claude-sonnet-4-20250514"
    SILICONFLOW_API_KEY: str | None = None
    SILICONFLOW_BASE_URL: str = "https://api.siliconflow.cn/v1"
    SILICONFLOW_MODEL: str = "deepseek-ai/DeepSeek-V3.2"
    OPENROUTER_API_KEY: str | None = None
    OPENROUTER_BASE_URL: str = "https://openrouter.ai/api/v1"
    OPENROUTER_MODEL: str = "deepseek/deepseek-chat"
    MIMO_API_KEY: str | None = None
    MIMO_BASE_URL: str = "https://api.xiaomimimo.com/v1"
    MIMO_MODEL: str = "mimo-v2.5-pro"

    # 飞书配置
    FEISHU_WEBHOOK_URL: str | None = None
    FEISHU_WEBHOOK_SECRET: str | None = None

    # Agent 配置
    AGENT_LLM_PROVIDER: str = "mimo"

    # 应用配置
    APP_BASE_URL: str = "http://localhost:8000"
    TEMPERATURE: float = 0.7
    LOG_LEVEL: str = "INFO"
    MAX_CONCURRENT_TASKS: int = 5
    MAX_CONCURRENT_LLM_CALLS: int = 3
    DOCUMENT_PROCESS_TIMEOUT: int = 300
    LLM_REQUEST_TIMEOUT: int = 120
    AGENT_TASK_TIMEOUT: int = 1200

    model_config = ConfigDict(
        env_file=str(_paths.ENV_FILE),
        env_file_encoding="utf-8",
        frozen=False,
        extra="ignore",
    )


settings = Settings()
