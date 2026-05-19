"""LLM configuration for the agent system.

Uses langchain_openai.ChatOpenAI with OpenAI-compatible endpoints.
Supports: DeepSeek, Qwen, GLM, SiliconFlow, OpenRouter, Mimo, OpenAI.
Anthropic uses langchain_anthropic.ChatAnthropic.
"""

import asyncio
import os
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

from dotenv import load_dotenv

# Load .env from project config directory
_project_root = Path(__file__).parent.parent
load_dotenv(_project_root / "config" / ".env")

# All providers with OpenAI-compatible endpoints
MODEL_ENDPOINTS = {
    "deepseek": {
        "base_url": "https://api.deepseek.com/v1",
        "default_model": "deepseek-chat",
    },
    "qwen": {
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "default_model": "qwen-plus",
    },
    "glm": {
        "base_url": "https://open.bigmodel.cn/api/paas/v4",
        "default_model": "glm-4-flash",
    },
    "siliconflow": {
        "base_url": "https://api.siliconflow.cn/v1",
        "default_model": "deepseek-ai/DeepSeek-V3.2",
    },
    "openai": {
        "base_url": "https://api.openai.com/v1",
        "default_model": "gpt-4o",
    },
    "openrouter": {
        "base_url": "https://openrouter.ai/api/v1",
        "default_model": "deepseek/deepseek-chat",
    },
    "mimo": {
        "base_url": "https://api.xiaomimimo.com/v1",
        "default_model": "mimo-v2.5-pro",
    },
}

# Default provider - can be overridden via env var AGENT_LLM_PROVIDER
DEFAULT_PROVIDER = os.getenv("AGENT_LLM_PROVIDER", "mimo")


def get_default_provider() -> str:
    """Get the default LLM provider name."""
    return DEFAULT_PROVIDER


def get_llm_config(provider: Optional[str] = None) -> dict:
    """Get raw LLM config dict (base_url, api_key, model) for direct HTTP calls."""
    if provider is None:
        provider = DEFAULT_PROVIDER
    endpoint = MODEL_ENDPOINTS.get(provider, {})
    api_key_env = f"{provider.upper()}_API_KEY"
    base_url_env = f"{provider.upper()}_BASE_URL"
    model_env = f"{provider.upper()}_MODEL"
    return {
        "base_url": os.getenv(base_url_env, endpoint.get("base_url", "")),
        "api_key": os.getenv(api_key_env, ""),
        "model": os.getenv(model_env, endpoint.get("default_model", "")),
    }


def get_llm(
    provider: Optional[str] = None,
    model: Optional[str] = None,
    temperature: float = 0.3,
    max_tokens: int = 4000,
):
    """Create an LLM instance for the given provider.

    For OpenAI-compatible providers, uses ChatOpenAI.
    For Anthropic, uses ChatAnthropic.

    Args:
        provider: Provider name. Uses default if None.
        model: Model name override. Uses provider default if None.
        temperature: Sampling temperature
        max_tokens: Max output tokens
    """
    if provider is None:
        provider = DEFAULT_PROVIDER

    # Anthropic uses a different API format
    if provider == "anthropic":
        return _get_anthropic_llm(model, temperature, max_tokens)

    endpoint = MODEL_ENDPOINTS.get(provider)
    if not endpoint:
        raise ValueError(f"Unknown provider: {provider}. Choose from {list(MODEL_ENDPOINTS.keys())}")

    # API key env var: PROVIDER_API_KEY (e.g. DEEPSEEK_API_KEY, SILICONFLOW_API_KEY)
    api_key_env = f"{provider.upper()}_API_KEY"
    api_key = os.getenv(api_key_env, "")
    if not api_key:
        raise ValueError(f"Missing API key. Set {api_key_env} in config/.env")

    # Allow base_url override from env
    base_url_env = f"{provider.upper()}_BASE_URL"
    base_url = os.getenv(base_url_env, endpoint["base_url"])

    from langchain_openai import ChatOpenAI
    return ChatOpenAI(
        model=model or endpoint["default_model"],
        base_url=base_url,
        api_key=api_key,
        temperature=temperature,
        max_tokens=max_tokens,
    )


def _get_anthropic_llm(model: Optional[str], temperature: float, max_tokens: int):
    """Create Anthropic ChatAnthropic instance."""
    api_key = os.getenv("ANTHROPIC_API_KEY", "")
    if not api_key:
        raise ValueError("Missing API key. Set ANTHROPIC_API_KEY in config/.env")

    try:
        from langchain_anthropic import ChatAnthropic
    except ImportError:
        raise ImportError("langchain-anthropic is required for Anthropic provider. Install with: pip install langchain-anthropic")

    return ChatAnthropic(
        model=model or "claude-sonnet-4-20250514",
        api_key=api_key,
        temperature=temperature,
        max_tokens=max_tokens,
    )


def _is_retryable_error(exc: Exception) -> bool:
    """Check if an LLM error is retryable (rate limit, server error, timeout)."""
    error_str = str(exc).lower()
    # Non-retryable: auth errors, bad request
    if any(kw in error_str for kw in ("401", "403", "invalid api key", "invalid_key", "unauthorized")):
        return False
    if any(kw in error_str for kw in ("400", "bad request", "invalid_request")):
        return False
    # Retryable: rate limit, server error, timeout, network
    if any(kw in error_str for kw in ("429", "500", "502", "503", "504", "rate limit", "timeout", "connection", "overloaded")):
        return True
    # Default: retry on unknown errors (might be transient)
    return True


async def call_llm_with_retry(llm, prompt: str, max_retries: int = 3, retry_delay: float = 2.0):
    """Call LLM with retry for transient failures.

    Distinguishes retryable errors (429, 5xx, timeout) from
    non-retryable errors (401, 400) using exponential backoff.

    Args:
        llm: LangChain LLM instance with .ainvoke()
        prompt: The prompt string
        max_retries: Number of retries on retryable failures (default 3)
        retry_delay: Base delay in seconds, doubled each retry (default 2.0)

    Returns:
        LLM response object

    Raises:
        Exception: The last exception if all retries fail or error is non-retryable
    """
    for attempt in range(max_retries + 1):
        try:
            return await llm.ainvoke(prompt)
        except Exception as e:
            if not _is_retryable_error(e):
                logger.error("LLM call failed (non-retryable): %s", e)
                raise
            if attempt < max_retries:
                delay = retry_delay * (2 ** attempt)
                logger.warning("LLM call failed (attempt %d/%d): %s, retrying in %.1fs",
                               attempt + 1, max_retries + 1, e, delay)
                await asyncio.sleep(delay)
            else:
                logger.error("LLM call failed after %d attempts: %s", max_retries + 1, e)
                raise
