"""LLM configuration for the agent system.

Uses langchain_openai.ChatOpenAI with OpenAI-compatible endpoints
for domestic LLM providers (Qwen, DeepSeek, GLM).
"""

import os
from pathlib import Path

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI

# Load .env from project config directory
_project_root = Path(__file__).parent.parent
load_dotenv(_project_root / "config" / ".env")

# Domestic model OpenAI-compatible endpoints
MODEL_ENDPOINTS = {
    "qwen": {
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "default_model": "qwen-plus",
    },
    "deepseek": {
        "base_url": "https://api.deepseek.com",
        "default_model": "deepseek-chat",
    },
    "glm": {
        "base_url": "https://open.bigmodel.cn/api/paas/v4",
        "default_model": "glm-4-flash",
    },
    "siliconflow": {
        "base_url": "https://api.siliconflow.cn/v1",
        "default_model": "deepseek-ai/DeepSeek-V3.2",
    },
}


def get_llm(
    provider: str = "qwen",
    model: str | None = None,
    temperature: float = 0.3,
    max_tokens: int = 4000,
) -> ChatOpenAI:
    """Create a ChatOpenAI instance configured for a domestic LLM provider.

    Args:
        provider: One of "qwen", "deepseek", "glm"
        model: Model name override (uses provider default if None)
        temperature: Sampling temperature
        max_tokens: Max output tokens
    """
    endpoint = MODEL_ENDPOINTS.get(provider)
    if not endpoint:
        raise ValueError(f"Unknown provider: {provider}. Choose from {list(MODEL_ENDPOINTS.keys())}")

    # API key env var names: QWEN_API_KEY, DEEPSEEK_API_KEY, GLM_API_KEY
    api_key_env = f"{provider.upper()}_API_KEY"
    api_key = os.getenv(api_key_env, "")
    if not api_key:
        raise ValueError(f"Missing API key. Set {api_key_env} in config/.env")

    return ChatOpenAI(
        model=model or endpoint["default_model"],
        base_url=endpoint["base_url"],
        api_key=api_key,
        temperature=temperature,
        max_tokens=max_tokens,
    )
