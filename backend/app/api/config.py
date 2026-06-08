import asyncio
import logging
import os
import re
import sys
from pathlib import Path
from typing import Dict

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_db
from app.models.configuration import Configuration

logger = logging.getLogger(__name__)

router = APIRouter()


def _mask_value(key: str, value: str) -> str:
    """Mask sensitive config values (keys containing 'key' or 'secret')."""
    if not value:
        return value
    # Return empty for placeholder values so frontend knows the key is not configured
    if value.lower().startswith("your_"):
        return ""
    lower_key = key.lower()
    if "key" not in lower_key and "secret" not in lower_key:
        return value
    if len(value) <= 8:
        return "****"
    return value[:4] + "****" + value[-4:]

# Mapping from config key to (settings_attr, provider_name)
_LLM_KEY_MAP = {
    "deepseek_api_key": ("DEEPSEEK_API_KEY", "deepseek"),
    "deepseek_base_url": ("DEEPSEEK_BASE_URL", "deepseek"),
    "qwen_api_key": ("QWEN_API_KEY", "qwen"),
    "qwen_base_url": ("QWEN_BASE_URL", "qwen"),
    "glm_api_key": ("GLM_API_KEY", "glm"),
    "glm_base_url": ("GLM_BASE_URL", "glm"),
    "openai_api_key": ("OPENAI_API_KEY", "openai"),
    "openai_base_url": ("OPENAI_BASE_URL", "openai"),
    "anthropic_api_key": ("ANTHROPIC_API_KEY", "anthropic"),
    "anthropic_base_url": ("ANTHROPIC_BASE_URL", "anthropic"),
    "siliconflow_api_key": ("SILICONFLOW_API_KEY", "siliconflow"),
    "siliconflow_base_url": ("SILICONFLOW_BASE_URL", "siliconflow"),
    "openrouter_api_key": ("OPENROUTER_API_KEY", "openrouter"),
    "openrouter_base_url": ("OPENROUTER_BASE_URL", "openrouter"),
    "mimo_api_key": ("MIMO_API_KEY", "mimo"),
    "mimo_base_url": ("MIMO_BASE_URL", "mimo"),
    "deepseek_model": ("DEEPSEEK_MODEL", "deepseek"),
    "qwen_model": ("QWEN_MODEL", "qwen"),
    "glm_model": ("GLM_MODEL", "glm"),
    "openai_model": ("OPENAI_MODEL", "openai"),
    "anthropic_model": ("ANTHROPIC_MODEL", "anthropic"),
    "siliconflow_model": ("SILICONFLOW_MODEL", "siliconflow"),
    "openrouter_model": ("OPENROUTER_MODEL", "openrouter"),
    "mimo_model": ("MIMO_MODEL", "mimo"),
    "agent_llm_provider": ("AGENT_LLM_PROVIDER", None),
    "feishu_webhook_url": ("FEISHU_WEBHOOK_URL", None),
    "feishu_webhook_secret": ("FEISHU_WEBHOOK_SECRET", None),
    "temperature": ("TEMPERATURE", None),
    "log_level": ("LOG_LEVEL", None),
    "max_concurrent_tasks": ("MAX_CONCURRENT_TASKS", None),
    "agent_task_timeout": ("AGENT_TASK_TIMEOUT", None),
}


async def _apply_setting(key: str, value: str):
    """Update the settings singleton, sync to os.environ, persist to .env, and reload LLM adapter."""
    from app.core.config import settings

    mapping = _LLM_KEY_MAP.get(key.lower())
    if not mapping:
        return
    attr, provider = mapping

    # Validate: reject placeholder and masked API keys, URLs, and model names
    if ("api_key" in attr.lower() or "base_url" in attr.lower() or "model" in attr.lower()) and isinstance(value, str) and re.match(r'^your_', value, re.IGNORECASE):
        raise HTTPException(status_code=422, detail=f"{key} 为占位符值，请填写真实配置")

    # Update settings singleton
    # Cast to correct type
    current = getattr(settings, attr, None)
    if isinstance(current, int):
        try:
            value = int(value)
        except ValueError:
            raise HTTPException(status_code=422, detail=f"配置项 {key} 需要整数值，收到: {value}")
    elif isinstance(current, float):
        try:
            value = float(value)
        except ValueError:
            raise HTTPException(status_code=422, detail=f"配置项 {key} 需要小数值，收到: {value}")
    setattr(settings, attr, value)
    logger.info("Config updated: %s", attr)

    # Sync to os.environ so agent/config.py's os.getenv() picks up the change
    os.environ[attr] = str(value)

    # Persist to .env file for restart survival
    _update_env_file(attr, str(value))

    # Reload LLM adapter if API key, base URL, or model changed
    if provider and ("api_key" in key.lower() or "base_url" in key.lower() or "model" in key.lower()):
        await _reload_llm_provider(provider)

    # Clear agent LLM cache when provider selection changes
    if key.lower() == "agent_llm_provider":
        try:
            from agent.config import clear_llm_cache
            clear_llm_cache()
            logger.info("Agent LLM cache cleared due to provider change to %s", value)
        except ImportError:
            pass


def _atomic_write_text(path, content: str, encoding: str = "utf-8"):
    """Atomically write text to a file using write-to-temp-then-rename."""
    import tempfile
    tmp_fd, tmp_path = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
    try:
        with os.fdopen(tmp_fd, "w", encoding=encoding) as f:
            f.write(content)
        # On Windows, rename fails if target exists; remove first
        if sys.platform == "win32" and path.exists():
            path.unlink()
        os.rename(tmp_path, path)
    except Exception:
        # Clean up temp file on failure
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


def _update_env_file(attr: str, value: str):
    """Update a single key in config/.env file."""
    from app.core.paths import ENV_FILE
    env_path = ENV_FILE
    if not env_path.exists():
        return
    try:
        lines = env_path.read_text(encoding="utf-8").splitlines()
        updated = False
        for i, line in enumerate(lines):
            stripped = line.strip()
            if stripped.startswith(f"{attr}=") or stripped.startswith(f"{attr} ="):
                lines[i] = f"{attr}={value}"
                updated = True
                break
        if not updated:
            lines.append(f"{attr}={value}")
        _atomic_write_text(env_path, "\n".join(lines) + "\n")
    except Exception as e:
        logger.warning("Failed to persist %s to .env: %s", attr, e)


def _batch_update_env_file(updates: dict[str, str]):
    """Batch update multiple keys in config/.env file in a single read/write."""
    from app.core.paths import ENV_FILE
    env_path = ENV_FILE
    if not env_path.exists():
        return
    try:
        lines = env_path.read_text(encoding="utf-8").splitlines()
        updated_keys: set[str] = set()
        for i, line in enumerate(lines):
            stripped = line.strip()
            if stripped and not stripped.startswith("#") and "=" in stripped:
                key = stripped.split("=", 1)[0].strip()
                if key in updates:
                    lines[i] = f"{key}={updates[key]}"
                    updated_keys.add(key)
        for key, value in updates.items():
            if key not in updated_keys:
                lines.append(f"{key}={value}")
        _atomic_write_text(env_path, "\n".join(lines) + "\n")
    except Exception as e:
        logger.warning("Failed to batch persist to .env: %s", e)


async def _reload_llm_provider(provider: str):
    """Reload a single LLM provider adapter and clear agent-side cache."""
    from app.core.config import settings
    from app.services.llm_engine import get_llm_engine

    engine = get_llm_engine()
    key_attr = f"{provider.upper()}_API_KEY"
    url_attr = f"{provider.upper()}_BASE_URL"
    api_key = getattr(settings, key_attr, None)
    base_url = getattr(settings, url_attr, None)
    model_attr = f"{provider.upper()}_MODEL"
    model = getattr(settings, model_attr, None)
    try:
        await asyncio.wait_for(
            engine.reload_provider(provider, api_key=api_key or "", base_url=base_url, model=model),
            timeout=10,
        )
    except asyncio.TimeoutError:
        logger.warning("LLM provider reload timed out for %s", provider)
        return
    logger.info("Reloaded LLM provider: %s", provider)

    # Clear agent-side LangChain LLM cache so next audit uses the new provider
    try:
        from agent.config import clear_llm_cache
        clear_llm_cache(provider)
    except ImportError:
        pass

@router.get("/")
async def get_config(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Configuration))
    configs = result.scalars().all()
    return {c.config_key: {"value": _mask_value(c.config_key, c.config_value), "type": c.config_type, "description": c.description} for c in configs}

@router.get("/llm/models")
async def get_available_models():
    from app.services.llm_engine import get_llm_engine
    from app.core.providers import get_provider_names, PROVIDER_REGISTRY
    engine = get_llm_engine()
    providers = engine.get_available_providers()
    names = get_provider_names()

    return [
        {
            "id": p["name"],
            "name": names.get(p["name"], p["name"]),
            "model": p["model"],
            "available": p["available"],
            "base_url": PROVIDER_REGISTRY.get(p["name"], {}).get("base_url", ""),
            "default_model": PROVIDER_REGISTRY.get(p["name"], {}).get("default_model", ""),
            "available_models": PROVIDER_REGISTRY.get(p["name"], {}).get("available_models", []),
        }
        for p in providers
    ]


@router.get("/{key}")
async def get_config_by_key(key: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Configuration).where(Configuration.config_key == key))
    config = result.scalar_one_or_none()
    if not config:
        raise HTTPException(status_code=404, detail="配置不存在")
    return {"key": config.config_key, "value": _mask_value(config.config_key, config.config_value), "type": config.config_type, "description": config.description}


class ConfigUpdateRequest(BaseModel):
    value: str
    description: str | None = None


@router.put("/{key}")
async def update_config(key: str, req: ConfigUpdateRequest, db: AsyncSession = Depends(get_db)):
    value = req.value
    description = req.description

    # Validate placeholder before DB write
    lower_key = key.lower()
    if ("api_key" in lower_key or "base_url" in lower_key or "model" in lower_key) and isinstance(value, str) and re.match(r'^your_', value, re.IGNORECASE):
        raise HTTPException(status_code=422, detail=f"{key} 为占位符值，请填写真实配置")

    result = await db.execute(select(Configuration).where(Configuration.config_key == key))
    config = result.scalar_one_or_none()

    if config:
        config.config_value = value
        if description:
            config.description = description
    else:
        config = Configuration(config_key=key, config_value=value, config_type="string", description=description)
        db.add(config)

    await db.commit()
    await _apply_setting(key, value)

    # Auto-set AGENT_LLM_PROVIDER if an API key was configured
    if "api_key" in lower_key and value and lower_key in _LLM_KEY_MAP:
        _, provider = _LLM_KEY_MAP[lower_key]
        if provider:
            await _apply_setting("agent_llm_provider", provider)
            result2 = await db.execute(select(Configuration).where(Configuration.config_key == "agent_llm_provider"))
            cfg2 = result2.scalar_one_or_none()
            if cfg2:
                cfg2.config_value = provider
            else:
                db.add(Configuration(config_key="agent_llm_provider", config_value=provider, config_type="string"))
            await db.commit()
            logger.info("Auto-set AGENT_LLM_PROVIDER to %s", provider)

    return {"status": "success"}


class BatchConfigRequest(BaseModel):
    configs: Dict[str, str]


@router.post("/batch")
async def batch_update_config(request: BatchConfigRequest, db: AsyncSession = Depends(get_db)):
    from app.core.config import settings

    # Pre-filter: skip placeholder/masked API key values
    _placeholder_re = re.compile(r'^your_', re.IGNORECASE)
    filtered_configs = {}
    auto_provider = None
    for key, value in request.configs.items():
        lower_key = key.lower()
        if ("api_key" in lower_key or "base_url" in lower_key or "model" in lower_key) and isinstance(value, str) and _placeholder_re.match(value):
            logger.info("Skipping placeholder/masked config: %s", key)
            continue
        filtered_configs[key] = value
        # Auto-detect provider from API key for AGENT_LLM_PROVIDER
        if "api_key" in lower_key and value and lower_key in _LLM_KEY_MAP:
            _, provider = _LLM_KEY_MAP[lower_key]
            if provider:
                auto_provider = provider

    # Auto-set AGENT_LLM_PROVIDER if an API key was configured
    if auto_provider and "AGENT_LLM_PROVIDER" not in filtered_configs and "agent_llm_provider" not in filtered_configs:
        filtered_configs["AGENT_LLM_PROVIDER"] = auto_provider
        logger.info("Auto-setting AGENT_LLM_PROVIDER to %s", auto_provider)

    # 1. Batch update DB
    for key, value in filtered_configs.items():
        result = await db.execute(select(Configuration).where(Configuration.config_key == key))
        config = result.scalar_one_or_none()
        if config:
            config.config_value = value
        else:
            db.add(Configuration(config_key=key, config_value=value, config_type="string"))
    await db.commit()

    # 2. Batch update os.environ + collect env file updates
    env_updates = {}
    providers_to_reload = set()
    for key, value in filtered_configs.items():
        if key.lower() not in _LLM_KEY_MAP:
            logger.warning("Skipping unknown config key: %s", key)
            continue
        attr, provider = _LLM_KEY_MAP[key.lower()]
        old_val = getattr(settings, attr, None)
        if old_val is not None and str(old_val) == str(value):
            continue
        # Cast to correct type (mirrors _apply_setting logic)
        if isinstance(old_val, int):
            try:
                value = int(value)
            except ValueError:
                logger.warning("Skipping %s: expected int, got %s", key, value)
                continue
        elif isinstance(old_val, float):
            try:
                value = float(value)
            except ValueError:
                logger.warning("Skipping %s: expected float, got %s", key, value)
                continue
        setattr(settings, attr, value)
        os.environ[attr] = str(value)
        env_updates[attr] = str(value)
        if provider and ("api_key" in key.lower() or "base_url" in key.lower() or "model" in key.lower()):
            providers_to_reload.add(provider)

    # 3. Single .env file write
    if env_updates:
        _batch_update_env_file(env_updates)

    # 4. Reload LLM adapters (still sequential - needs to close old connections)
    for provider in providers_to_reload:
        await _reload_llm_provider(provider)

    # 5. Clear agent LLM cache if provider changed
    if auto_provider:
        try:
            from agent.config import clear_llm_cache
            clear_llm_cache()
            logger.info("Agent LLM cache cleared due to provider auto-set to %s", auto_provider)
        except ImportError:
            pass

    return {"status": "success", "updated": len(filtered_configs)}


@router.post("/test-webhook")
async def test_webhook():
    from app.core.config import settings
    if not settings.FEISHU_WEBHOOK_URL:
        return {"success": False, "error": "未配置 Webhook URL"}
    from app.services.notification import send_feishu_notification
    success = await send_feishu_notification("测试通知", "这是一条来自 AuditBee 的测试消息", "info")
    return {"success": success, "error": None if success else "发送失败，请检查 Webhook URL 和网络"}


class TestLLMRequest(BaseModel):
    provider: str
    api_key: str
    base_url: str | None = None
    model: str | None = None


@router.post("/test-llm")
async def test_llm_connection(request: TestLLMRequest):
    """Test LLM provider connectivity with a lightweight request."""
    import time as _time
    from app.services.llm_engine import OpenAICompatibleAdapter, AnthropicAdapter

    provider = request.provider.lower()
    api_key = request.api_key
    base_url = request.base_url or ""
    model = request.model or ""

    # Provider-specific defaults
    defaults = {
        "deepseek": ("https://api.deepseek.com/v1", "deepseek-chat"),
        "qwen": ("https://dashscope.aliyuncs.com/compatible-mode/v1", "qwen-plus"),
        "glm": ("https://open.bigmodel.cn/api/paas/v4", "glm-4-flash"),
        "openai": ("https://api.openai.com/v1", "gpt-4o"),
        "anthropic": ("https://api.anthropic.com", "claude-sonnet-4-20250514"),
        "siliconflow": ("https://api.siliconflow.cn/v1", "deepseek-ai/DeepSeek-V3.2"),
        "openrouter": ("https://openrouter.ai/api/v1", "deepseek/deepseek-chat"),
        "mimo": ("https://api.xiaomimimo.com/v1", "mimo-v2.5-pro"),
    }

    if provider not in defaults:
        return {"success": False, "error": f"不支持的 provider: {provider}", "latency_ms": 0}

    default_url, default_model = defaults[provider]
    base_url = (base_url if base_url and not base_url.lower().startswith("your_") else None) or default_url
    model = (model if model and not model.lower().startswith("your_") else None) or default_model

    logger.info("Testing LLM connection: provider=%s, model=%s, base_url=%s", provider, model, base_url)

    if not api_key:
        return {"success": False, "error": "API Key 不能为空", "latency_ms": 0}

    adapter = None
    try:
        if provider == "anthropic":
            adapter = AnthropicAdapter(api_key=api_key, base_url=base_url, model=model)
        else:
            adapter = OpenAICompatibleAdapter(api_key=api_key, base_url=base_url, model=model, name=provider)

        start = _time.monotonic()
        response = await adapter.chat(
            [{"role": "user", "content": "hi"}],
            max_tokens=5,
            timeout=15,
        )
        latency_ms = int((_time.monotonic() - start) * 1000)

        return {"success": True, "model_used": response.model, "latency_ms": latency_ms, "error": None}
    except Exception as exc:
        return {"success": False, "error": str(exc)[:200], "latency_ms": 0}
    finally:
        if adapter:
            await adapter.close()
