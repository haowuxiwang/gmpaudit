"""Single source of truth for LLM provider configuration.

This is a pure data module with NO imports from app.* so that
tkinter_launcher.py (which avoids app.* imports) can safely use it.
"""

from typing import Dict, List

# Provider registry: provider_key -> {name, base_url, default_model, available_models}
PROVIDER_REGISTRY: Dict[str, Dict[str, object]] = {
    "deepseek": {
        "name": "DeepSeek",
        "base_url": "https://api.deepseek.com/v1",
        "default_model": "deepseek-chat",
        "available_models": ["deepseek-chat", "deepseek-reasoner"],
    },
    "qwen": {
        "name": "通义千问 (Qwen)",
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "default_model": "qwen-plus",
        "available_models": ["qwen-plus", "qwen-turbo", "qwen-max", "qwen-long"],
    },
    "glm": {
        "name": "智谱 (GLM)",
        "base_url": "https://open.bigmodel.cn/api/paas/v4",
        "default_model": "glm-4-flash",
        "available_models": ["glm-4-flash", "glm-4-plus", "glm-4-long"],
    },
    "openai": {
        "name": "OpenAI",
        "base_url": "https://api.openai.com/v1",
        "default_model": "gpt-4o",
        "available_models": ["gpt-4o", "gpt-4o-mini", "gpt-4-turbo", "o1-mini"],
    },
    "anthropic": {
        "name": "Anthropic (Claude)",
        "base_url": "https://api.anthropic.com",
        "default_model": "claude-sonnet-4-20250514",
        "available_models": ["claude-sonnet-4-20250514", "claude-haiku-4-5-20251001", "claude-opus-4-20250514"],
    },
    "siliconflow": {
        "name": "SiliconFlow",
        "base_url": "https://api.siliconflow.cn/v1",
        "default_model": "deepseek-ai/DeepSeek-V3.2",
        "available_models": ["deepseek-ai/DeepSeek-V3.2", "Qwen/Qwen2.5-72B-Instruct", "meta-llama/Meta-Llama-3.1-70B-Instruct"],
    },
    "openrouter": {
        "name": "OpenRouter",
        "base_url": "https://openrouter.ai/api/v1",
        "default_model": "deepseek/deepseek-chat",
        "available_models": ["deepseek/deepseek-chat", "anthropic/claude-sonnet-4", "openai/gpt-4o"],
    },
    "mimo": {
        "name": "Mimo (推荐)",
        "base_url": "https://api.xiaomimimo.com/v1",
        "default_model": "mimo-v2.5-pro",
        "available_models": ["mimo-v2.5-pro"],
    },
}


def get_provider_defaults(provider: str) -> dict:
    """Get default config for a provider. Returns {} if unknown."""
    return PROVIDER_REGISTRY.get(provider, {})


def get_provider_names() -> Dict[str, str]:
    """Returns {provider_key: display_name} mapping."""
    return {k: v["name"] for k, v in PROVIDER_REGISTRY.items()}


def get_provider_list() -> list[dict]:
    """Returns list of provider dicts for API responses."""
    return [
        {"id": k, "name": v["name"], "model": v["default_model"]}
        for k, v in PROVIDER_REGISTRY.items()
    ]
