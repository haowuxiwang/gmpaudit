"""LLM configuration for the agent system.

Uses langchain_openai.ChatOpenAI with OpenAI-compatible endpoints.
Supports: DeepSeek, Qwen, GLM, SiliconFlow, OpenRouter, Mimo, OpenAI.
Anthropic uses langchain_anthropic.ChatAnthropic.
"""

import asyncio
import logging
import os
import re

logger = logging.getLogger(__name__)


class LLMAuthError(Exception):
    """Raised when LLM API returns 401/403 (invalid or missing API key).

    Attributes:
        provider: The LLM provider name (e.g. 'deepseek', 'mimo')
        user_message: A user-friendly Chinese error message
    """

    def __init__(self, provider: str, original_error: str = ""):
        self.provider = provider
        self.original_error = original_error
        self.user_message = f"API Key 无效或已过期（{provider}），请在「设置」页面重新配置"
        super().__init__(self.user_message)


# LLM client cache: key=(provider, model, temperature, max_tokens) -> LLM instance
_llm_cache: dict[tuple, object] = {}

# .env is loaded by pydantic-settings in backend/app/core/config.py.
# When running standalone (agent CLI), load_dotenv is called in main.py.


def clear_llm_cache(provider: str | None = None):
    """Clear cached LLM instances.

    Args:
        provider: If given, only clear entries for this provider.
                  If None, clear all cached instances.
    """
    global _llm_cache
    if provider:
        # Cache keys are tuples (provider, model, temperature, max_tokens)
        # Handle legacy string keys defensively
        _llm_cache = {
            k: v
            for k, v in _llm_cache.items()
            if (isinstance(k, tuple) and k[0] != provider) or (isinstance(k, str) and not k.startswith(provider))
        }
    else:
        _llm_cache.clear()
    logger.info("LLM cache cleared for %s", provider or "all providers")


# All providers with OpenAI-compatible endpoints
# Canonical source: backend/app/core/providers.py (keep in sync)
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

# Anthropic uses Messages API (not OpenAI-compatible), tracked separately
ANTHROPIC_DEFAULT_MODEL = "claude-sonnet-4-20250514"

# Document content truncation limit (chars) for LLM analysis.
# Override via MAX_DOCUMENT_CHARS env var for longer documents.
MAX_DOCUMENT_CHARS = int(os.getenv("MAX_DOCUMENT_CHARS", "3000"))

# LLM per-call timeout (seconds). Reasoning models get 2x this value.
# Override via LLM_REQUEST_TIMEOUT env var.
_LLM_REQUEST_TIMEOUT = int(os.getenv("LLM_REQUEST_TIMEOUT", "180"))

# Max chars per chunk for structure-aware chunking (default ~8000 Chinese chars)
CHUNK_MAX_CHARS = int(os.getenv("CHUNK_MAX_CHARS", "16000"))

# Documents ≤ this size use "stuff" strategy (single LLM call, no chunking).
# 40000 chars ≈ 20000 Chinese chars ≈ 15-20 pages, fits in 128K context models.
# Above this, map_reduce avoids sending full doc to LLM twice.
STUFF_LIMIT = int(os.getenv("STUFF_LIMIT", "40000"))


def get_default_provider() -> str:
    """Get the default LLM provider name.

    Reads from env var AGENT_LLM_PROVIDER each call so that values
    loaded by load_dotenv() at startup are always picked up.
    """
    return os.getenv("AGENT_LLM_PROVIDER", "mimo")


def get_llm_config(provider: str | None = None) -> dict:
    """Get raw LLM config dict (base_url, api_key, model) for direct HTTP calls."""
    if provider is None:
        provider = get_default_provider()
    endpoint = MODEL_ENDPOINTS.get(provider, {})
    api_key_env = f"{provider.upper()}_API_KEY"
    base_url_env = f"{provider.upper()}_BASE_URL"
    model_env = f"{provider.upper()}_MODEL"
    model = os.getenv(model_env, "") or endpoint.get("default_model", "")
    return {
        "base_url": os.getenv(base_url_env, endpoint.get("base_url", "")),
        "api_key": os.getenv(api_key_env, ""),
        "model": model,
    }


def _validate_model_name(provider: str, model_name: str) -> None:
    """Warn if model name format doesn't match provider conventions.

    SiliconFlow and OpenRouter use 'org/model' format (e.g. 'deepseek-ai/DeepSeek-V3.2').
    Other providers use simple names (e.g. 'deepseek-chat', 'gpt-4o').
    """
    has_slash = "/" in model_name
    slash_providers = {"siliconflow", "openrouter"}
    if has_slash and provider not in slash_providers:
        logger.warning(
            "Model '%s' contains '/' but provider '%s' may not support org/model format. Expected format for %s: '%s'",
            model_name,
            provider,
            provider,
            MODEL_ENDPOINTS.get(provider, {}).get("default_model", "simple-name"),
        )
    elif not has_slash and provider in slash_providers:
        logger.warning(
            "Model '%s' has no '/' but provider '%s' typically uses 'org/model' format "
            "(e.g. '%s'). Verify the model name is correct.",
            model_name,
            provider,
            MODEL_ENDPOINTS.get(provider, {}).get("default_model", "org/model"),
        )


# Reasoning model name patterns (DeepSeek-R1, o1, o3, etc.)
# These models output reasoning in a separate field and need higher max_tokens.
_REASONING_PATTERNS = ("-r1", "reason", "thinking", "o1-", "o3-", "nex-n2")


def _is_reasoning_model(model_name: str) -> bool:
    """Detect if a model is a reasoning/thinking model by its name."""
    if not isinstance(model_name, str):
        return False
    name = model_name.lower()
    return any(p in name for p in _REASONING_PATTERNS)


# Reasoning models consume tokens for internal reasoning before producing output.
# Default max_tokens (4000) is often insufficient; boost to this value.
_REASONING_MAX_TOKENS = 16000


def get_llm(
    provider: str | None = None,
    model: str | None = None,
    temperature: float = 0.3,
    max_tokens: int = 4000,
):
    """Get or create a cached LLM instance for the given provider.

    Reuses existing instances to avoid repeated TCP/TLS handshake overhead.

    Args:
        provider: Provider name. Uses default if None.
        model: Model name override. Uses provider default if None.
        temperature: Sampling temperature
        max_tokens: Max output tokens
    """
    if provider is None:
        provider = get_default_provider()

    # Anthropic uses a different API format
    if provider == "anthropic":
        return _get_anthropic_llm(model, temperature, max_tokens)

    endpoint = MODEL_ENDPOINTS.get(provider)
    if not endpoint:
        raise ValueError(f"Unknown provider: {provider}. Choose from {list(MODEL_ENDPOINTS.keys())}")

    model_env = f"{provider.upper()}_MODEL"
    resolved_model = model or os.getenv(model_env)
    if not resolved_model or resolved_model.startswith("your_"):
        if resolved_model and resolved_model.startswith("your_"):
            logger.warning(
                "Model '%s' is a placeholder, using default '%s' for %s",
                resolved_model,
                endpoint["default_model"],
                provider,
            )
        resolved_model = endpoint["default_model"]
    _validate_model_name(provider, resolved_model)

    # Auto-boost max_tokens for reasoning models
    if _is_reasoning_model(resolved_model) and max_tokens < _REASONING_MAX_TOKENS:
        logger.info(
            "Reasoning model detected (%s), boosting max_tokens %d -> %d",
            resolved_model, max_tokens, _REASONING_MAX_TOKENS,
        )
        max_tokens = _REASONING_MAX_TOKENS

    cache_key = (provider, resolved_model, temperature, max_tokens)

    if cache_key in _llm_cache:
        return _llm_cache[cache_key]

    # API key env var: PROVIDER_API_KEY (e.g. DEEPSEEK_API_KEY, SILICONFLOW_API_KEY)
    api_key_env = f"{provider.upper()}_API_KEY"
    api_key = os.getenv(api_key_env, "")
    if not api_key or api_key.startswith("your_"):
        raise ValueError(f"Missing or placeholder API key. Set {api_key_env} in config/.env")

    # Allow base_url override from env
    base_url_env = f"{provider.upper()}_BASE_URL"
    base_url = os.getenv(base_url_env, endpoint["base_url"])
    if base_url.startswith("your_"):
        logger.warning("Base URL '%s' is a placeholder, using default for %s", base_url, provider)
        base_url = endpoint["base_url"]

    from langchain_openai import ChatOpenAI

    llm = ChatOpenAI(
        model=resolved_model,
        base_url=base_url,
        api_key=api_key,
        temperature=temperature,
        max_tokens=max_tokens,
    )
    llm._provider = provider
    llm._model = resolved_model
    # Evict oldest entry if cache is full
    if len(_llm_cache) >= 50:
        _llm_cache.pop(next(iter(_llm_cache)))
    _llm_cache[cache_key] = llm
    return llm


def get_llm_with_fallback(
    model: str | None = None,
    temperature: float = 0.3,
    max_tokens: int = 4000,
):
    """Try default provider first, fallback to any available provider with a valid API key.

    Returns the first LLM instance that can be created successfully.
    Raises ValueError if no provider has a valid API key.
    """
    default = get_default_provider()
    all_providers = list(MODEL_ENDPOINTS.keys()) + ["anthropic"]
    providers = [default] + [p for p in all_providers if p != default]
    last_error = None
    for provider in providers:
        try:
            return get_llm(provider, model, temperature, max_tokens)
        except (ValueError, ImportError, ConnectionError, RuntimeError) as e:
            last_error = e
            logger.warning("Provider %s unavailable: %s", provider, e)
            continue
    raise ValueError(f"No provider with valid API key available. Last error: {last_error}")


def _get_anthropic_llm(model: str | None, temperature: float, max_tokens: int):
    """Create Anthropic ChatAnthropic instance (cached)."""
    resolved_model = model or os.getenv("ANTHROPIC_MODEL")
    if not resolved_model or resolved_model.startswith("your_"):
        resolved_model = ANTHROPIC_DEFAULT_MODEL
    cache_key = ("anthropic", resolved_model, temperature, max_tokens)
    if cache_key in _llm_cache:
        return _llm_cache[cache_key]

    api_key = os.getenv("ANTHROPIC_API_KEY", "")
    if not api_key or api_key.startswith("your_"):
        raise ValueError("Missing or placeholder API key. Set ANTHROPIC_API_KEY in config/.env")

    try:
        from langchain_anthropic import ChatAnthropic
    except ImportError:
        raise ImportError(
            "langchain-anthropic is required for Anthropic provider. Install with: pip install langchain-anthropic"
        ) from None

    llm = ChatAnthropic(
        model=resolved_model,
        api_key=api_key,
        temperature=temperature,
        max_tokens=max_tokens,
    )
    llm._provider = "anthropic"
    llm._model = resolved_model
    # Evict oldest entry if cache is full
    if len(_llm_cache) >= 50:
        _llm_cache.pop(next(iter(_llm_cache)))
    _llm_cache[cache_key] = llm
    return llm


def _is_retryable_error(exc: Exception) -> bool:
    """Check if an LLM error is retryable (rate limit, server error, timeout)."""
    # asyncio.TimeoutError and httpx timeout errors are always retryable
    if isinstance(exc, asyncio.TimeoutError):
        return True
    try:
        import httpx
        if isinstance(exc, (httpx.TimeoutException, httpx.ConnectTimeout, httpx.ReadTimeout, httpx.WriteTimeout)):
            return True
    except ImportError:
        pass
    error_str = str(exc).lower()
    # Non-retryable: auth errors (use regex to avoid false positives on model names)
    if re.search(r"\b40[13]\b", error_str) or any(
        kw in error_str for kw in ("invalid api key", "invalid_key", "unauthorized")
    ):
        return False
    if re.search(r"\b400\b", error_str) or any(kw in error_str for kw in ("bad request", "invalid_request")):
        return False
    # Retryable: rate limit, server error, timeout, network
    return any(
        kw in error_str
        for kw in ("429", "500", "502", "503", "504", "rate limit", "timeout", "connection", "overloaded")
    )


def _is_auth_error(exc: Exception) -> bool:
    """Check if an LLM error is an authentication error (401/403)."""
    error_str = str(exc).lower()
    # Check for explicit auth keywords first (most reliable)
    if any(kw in error_str for kw in ("invalid api key", "invalid_key", "unauthorized")):
        return True
    # Check for status code patterns (not substrings like model names)
    if re.search(r"(?:error code|status.?code|http)[:\s]*40[13]\b", error_str):
        return True
    return bool(re.search(r"\b40[13]\b.*(?:api.?key|auth|token)", error_str))


async def call_llm_with_retry(llm, prompt: str, node: str = "unknown", max_retries: int = 3, retry_delay: float = 1.0):
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
    from agent.trace import LLMTraceEvent, get_current_trace, now_ms

    trace = get_current_trace()
    provider = getattr(llm, "_provider", "unknown")
    model = getattr(llm, "_model", "unknown")
    # node is now passed explicitly to avoid race conditions on shared cached LLM instances
    total_retries = 0

    # Reasoning models need more time per call due to internal reasoning
    call_timeout = (_LLM_REQUEST_TIMEOUT * 2) if _is_reasoning_model(model) else _LLM_REQUEST_TIMEOUT

    for attempt in range(max_retries + 1):
        try:
            t0 = now_ms()
            response = await asyncio.wait_for(llm.ainvoke(prompt), timeout=call_timeout)
            latency = now_ms() - t0

            # Normalize reasoning model response:
            # Reasoning models (DeepSeek-R1, Nex-N2-Pro, o1, etc.) put output
            # in reasoning_content, leaving content empty. Swap so all downstream
            # code works transparently.
            if not response.content and hasattr(response, "additional_kwargs"):
                reasoning = response.additional_kwargs.get("reasoning_content", "")
                if reasoning:
                    response.content = reasoning
                    logger.info(
                        "Recovered %d chars from reasoning_content (provider=%s, model=%s, node=%s)",
                        len(reasoning), provider, model, node,
                    )

            # Empty content is a failure — raise to trigger retry
            if not response.content or not response.content.strip():
                raise ValueError(f"LLM returned empty content (provider={provider}, model={model})")

            if trace:
                content = response.content if hasattr(response, "content") else str(response)
                trace.llm_events.append(
                    LLMTraceEvent(
                        provider=provider,
                        model=model,
                        node=node,
                        prompt_length=len(prompt),
                        prompt_preview=prompt[:200],
                        response_length=len(content),
                        latency_ms=round(latency, 1),
                        success=True,
                        retry_count=total_retries,
                    )
                )
            return response
        except Exception as e:
            total_retries = attempt
            if not _is_retryable_error(e):
                if trace:
                    trace.llm_events.append(
                        LLMTraceEvent(
                            provider=provider,
                            model=model,
                            node=node,
                            prompt_length=len(prompt),
                            prompt_preview=prompt[:200],
                            response_length=0,
                            latency_ms=0,
                            success=False,
                            error=str(e)[:500],
                            retry_count=total_retries,
                        )
                    )
                # Wrap auth errors with user-friendly message
                if _is_auth_error(e):
                    logger.error("LLM auth error (provider=%s): %s", provider, e)
                    raise LLMAuthError(provider, str(e)) from e
                logger.error("LLM call failed (non-retryable): [%s] %s", type(e).__name__, e or "(empty)")
                raise
            if attempt < max_retries:
                import random
                base_delay = retry_delay * (2**attempt)
                delay = base_delay + random.uniform(0, base_delay * 0.5)  # add 0-50% jitter
                logger.warning(
                    "LLM call failed (attempt %d/%d): [%s] %s, retrying in %.1fs",
                    attempt + 1, max_retries + 1, type(e).__name__, e or "(empty)", delay,
                )
                await asyncio.sleep(delay)
            else:
                if trace:
                    trace.llm_events.append(
                        LLMTraceEvent(
                            provider=provider,
                            model=model,
                            node=node,
                            prompt_length=len(prompt),
                            prompt_preview=prompt[:200],
                            response_length=0,
                            latency_ms=0,
                            success=False,
                            error=str(e)[:500],
                            retry_count=total_retries,
                        )
                    )
                logger.error("LLM call failed after %d attempts: [%s] %s", max_retries + 1, type(e).__name__, e or "(empty)")
                raise
