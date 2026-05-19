import logging
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
}


async def _apply_setting(key: str, value: str):
    """Update the settings singleton, sync to os.environ, persist to .env, and reload LLM adapter."""
    import os
    from pathlib import Path
    from app.core.config import settings

    mapping = _LLM_KEY_MAP.get(key)
    if not mapping:
        return
    attr, provider = mapping

    # Update settings singleton
    old_val = getattr(settings, attr, None)
    # Cast to correct type
    if isinstance(getattr(settings, attr, None), int):
        try:
            value = int(value)
        except ValueError:
            raise HTTPException(status_code=422, detail=f"配置项 {key} 需要整数值，收到: {value}")
    setattr(settings, attr, value)
    logger.info("Config updated: %s (was=%s)", attr, old_val)

    # Sync to os.environ so agent/config.py's os.getenv() picks up the change
    os.environ[attr] = str(value)

    # Persist to .env file for restart survival
    _update_env_file(attr, str(value))

    # Reload LLM adapter if API key, base URL, or model changed
    if provider and ("api_key" in key or "base_url" in key or "model" in key):
        await _reload_llm_provider(provider)


def _update_env_file(attr: str, value: str):
    """Update a single key in config/.env file."""
    env_path = Path(__file__).parent.parent.parent.parent / "config" / ".env"
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
        env_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    except Exception as e:
        logger.warning("Failed to persist %s to .env: %s", attr, e)


async def _reload_llm_provider(provider: str):
    """Reload a single LLM provider adapter."""
    from app.core.config import settings
    from app.services.llm_engine import get_llm_engine

    engine = get_llm_engine()
    key_attr = f"{provider.upper()}_API_KEY"
    url_attr = f"{provider.upper()}_BASE_URL"
    api_key = getattr(settings, key_attr, None)
    base_url = getattr(settings, url_attr, None)
    model_attr = f"{provider.upper()}_MODEL"
    model = getattr(settings, model_attr, None)
    await engine.reload_provider(provider, api_key=api_key or "", base_url=base_url, model=model)
    logger.info("Reloaded LLM provider: %s", provider)

@router.get("/")
async def get_config(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Configuration))
    configs = result.scalars().all()
    return {c.config_key: {"value": _mask_value(c.config_key, c.config_value), "type": c.config_type, "description": c.description} for c in configs}

@router.get("/llm/models")
async def get_available_models():
    from app.services.llm_engine import get_llm_engine
    engine = get_llm_engine()
    providers = engine.get_available_providers()

    # Provider display names
    names = {
        "deepseek": "DeepSeek",
        "qwen": "通义千问",
        "glm": "智谱GLM",
        "openai": "OpenAI",
        "anthropic": "Anthropic/Claude",
        "siliconflow": "SiliconFlow",
        "openrouter": "OpenRouter",
        "mimo": "Mimo/MiniMax",
    }

    return [
        {
            "id": p["name"],
            "name": names.get(p["name"], p["name"]),
            "model": p["model"],
            "available": p["available"],
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


@router.put("/{key}")
async def update_config(key: str, value: str, description: str = None, db: AsyncSession = Depends(get_db)):
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
    return {"status": "success"}


class BatchConfigRequest(BaseModel):
    configs: Dict[str, str]


@router.post("/batch")
async def batch_update_config(request: BatchConfigRequest, db: AsyncSession = Depends(get_db)):
    for key, value in request.configs.items():
        result = await db.execute(select(Configuration).where(Configuration.config_key == key))
        config = result.scalar_one_or_none()
        if config:
            config.config_value = value
        else:
            db.add(Configuration(config_key=key, config_value=value, config_type="string"))
    await db.commit()
    for key, value in request.configs.items():
        await _apply_setting(key, value)
    return {"status": "success", "updated": len(request.configs)}


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
    base_url = base_url or default_url
    model = model or default_model

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
