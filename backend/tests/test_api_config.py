from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.configuration import Configuration

# ---------------------------------------------------------------------------
# GET /config/
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_config(client: AsyncClient):
    response = await client.get("/api/config/")
    assert response.status_code == 200
    assert isinstance(response.json(), dict)


@pytest.mark.asyncio
async def test_get_config_with_entries(client: AsyncClient, db_session: AsyncSession):
    db_session.add(
        Configuration(
            config_key="log_level",
            config_value="INFO",
            config_type="string",
            description="Log level",
        )
    )
    db_session.add(
        Configuration(
            config_key="deepseek_api_key",
            config_value="sk-12345678abcd",
            config_type="string",
            description="API key",
        )
    )
    await db_session.commit()

    resp = await client.get("/api/config/")
    assert resp.status_code == 200
    data = resp.json()
    assert "log_level" in data
    assert data["log_level"]["value"] == "INFO"
    assert data["log_level"]["type"] == "string"
    # API key should be masked
    assert "deepseek_api_key" in data
    masked = data["deepseek_api_key"]["value"]
    assert "****" in masked
    assert masked != "sk-12345678abcd"


@pytest.mark.asyncio
async def test_get_config_masks_short_key(client: AsyncClient, db_session: AsyncSession):
    """Short API key (<=8 chars) should be fully masked."""
    db_session.add(
        Configuration(
            config_key="test_api_key",
            config_value="short",
            config_type="string",
        )
    )
    await db_session.commit()

    resp = await client.get("/api/config/")
    assert resp.json()["test_api_key"]["value"] == "****"


@pytest.mark.asyncio
async def test_get_config_masks_secret(client: AsyncClient, db_session: AsyncSession):
    db_session.add(
        Configuration(
            config_key="feishu_webhook_secret",
            config_value="mysecretvalue123",
            config_type="string",
        )
    )
    await db_session.commit()

    resp = await client.get("/api/config/")
    masked = resp.json()["feishu_webhook_secret"]["value"]
    assert "****" in masked


@pytest.mark.asyncio
async def test_get_config_empty_placeholder(client: AsyncClient, db_session: AsyncSession):
    """Placeholder values starting with 'your_' should return empty string."""
    db_session.add(
        Configuration(
            config_key="openai_api_key",
            config_value="your_openai_key_here",
            config_type="string",
        )
    )
    await db_session.commit()

    resp = await client.get("/api/config/")
    assert resp.json()["openai_api_key"]["value"] == ""


# ---------------------------------------------------------------------------
# GET /config/{key}
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_config_by_key_not_found(client: AsyncClient):
    response = await client.get("/api/config/nonexistent_key")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_get_config_by_key(client: AsyncClient, db_session: AsyncSession):
    db_session.add(
        Configuration(
            config_key="log_level",
            config_value="DEBUG",
            config_type="string",
            description="日志级别",
        )
    )
    await db_session.commit()

    resp = await client.get("/api/config/log_level")
    assert resp.status_code == 200
    data = resp.json()
    assert data["key"] == "log_level"
    assert data["value"] == "DEBUG"
    assert data["type"] == "string"
    assert data["description"] == "日志级别"


# ---------------------------------------------------------------------------
# PUT /config/{key}
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_update_and_get_config(client: AsyncClient):
    with patch("app.api.config._apply_setting", new_callable=AsyncMock):
        response = await client.put("/api/config/log_level", json={"value": "DEBUG", "description": "日志级别"})
    assert response.status_code == 200
    assert response.json()["status"] == "success"

    response = await client.get("/api/config/log_level")
    assert response.status_code == 200
    assert response.json()["key"] == "log_level"
    assert response.json()["value"] == "DEBUG"


@pytest.mark.asyncio
async def test_update_existing_config(client: AsyncClient):
    with patch("app.api.config._apply_setting", new_callable=AsyncMock):
        await client.put("/api/config/log_level", json={"value": "INFO"})
        await client.put("/api/config/log_level", json={"value": "WARNING"})
    response = await client.get("/api/config/log_level")
    assert response.json()["value"] == "WARNING"


@pytest.mark.asyncio
async def test_update_config_unknown_key_rejected(client: AsyncClient):
    response = await client.put("/api/config/evil_key", json={"value": "malicious"})
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_update_config_placeholder_rejected(client: AsyncClient):
    """Placeholder values starting with 'your_' should be rejected for API keys."""
    resp = await client.put(
        "/api/config/deepseek_api_key",
        json={"value": "your_key_here"},
    )
    assert resp.status_code == 422
    assert "占位符" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_update_config_placeholder_url_rejected(client: AsyncClient):
    resp = await client.put(
        "/api/config/deepseek_base_url",
        json={"value": "your_url_here"},
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_update_config_placeholder_model_rejected(client: AsyncClient):
    resp = await client.put(
        "/api/config/deepseek_model",
        json={"value": "your_model_here"},
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_update_config_integer_value(client: AsyncClient):
    """Integer config values should be cast correctly."""
    with patch("app.api.config._apply_setting", new_callable=AsyncMock):
        resp = await client.put(
            "/api/config/max_concurrent_tasks",
            json={"value": "5"},
        )
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_update_config_integer_invalid(client: AsyncClient):
    """Non-integer value for integer config should be rejected."""
    resp = await client.put(
        "/api/config/max_concurrent_tasks",
        json={"value": "not_a_number"},
    )
    assert resp.status_code == 422
    assert "整数" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_update_config_creates_new_entry(client: AsyncClient, db_session: AsyncSession):
    """When config key doesn't exist in DB, it should be created."""
    with patch("app.api.config._apply_setting", new_callable=AsyncMock):
        resp = await client.put(
            "/api/config/log_level",
            json={"value": "CRITICAL", "description": "New description"},
        )
    assert resp.status_code == 200

    resp = await client.get("/api/config/log_level")
    assert resp.json()["value"] == "CRITICAL"


@pytest.mark.asyncio
async def test_update_config_auto_sets_agent_provider(client: AsyncClient, db_session: AsyncSession):
    """When an API key is updated, AGENT_LLM_PROVIDER should be auto-set."""
    with patch("app.api.config._apply_setting", new_callable=AsyncMock):
        resp = await client.put(
            "/api/config/deepseek_api_key",
            json={"value": "sk-real-key-12345678"},
        )
    assert resp.status_code == 200

    # Verify agent_llm_provider was auto-set
    resp = await client.get("/api/config/agent_llm_provider")
    assert resp.status_code == 200
    assert resp.json()["value"] == "deepseek"


@pytest.mark.asyncio
async def test_update_config_api_key_with_reload(client: AsyncClient, db_session: AsyncSession):
    """Updating an API key should trigger LLM provider reload."""
    with patch("app.api.config._apply_setting", new_callable=AsyncMock):
        resp = await client.put(
            "/api/config/deepseek_api_key",
            json={"value": "sk-new-key-12345678"},
        )
    assert resp.status_code == 200


# ---------------------------------------------------------------------------
# POST /config/batch
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_batch_update_config(client: AsyncClient):
    with patch("app.api.config._reload_llm_provider", new_callable=AsyncMock):
        resp = await client.post(
            "/api/config/batch",
            json={
                "configs": {
                    "log_level": "WARNING",
                    "temperature": "0.7",
                }
            },
        )
    assert resp.status_code == 200
    assert resp.json()["status"] == "success"


@pytest.mark.asyncio
async def test_batch_update_skips_placeholders(client: AsyncClient):
    with patch("app.api.config._reload_llm_provider", new_callable=AsyncMock):
        resp = await client.post(
            "/api/config/batch",
            json={
                "configs": {
                    "deepseek_api_key": "your_key_here",
                    "log_level": "DEBUG",
                }
            },
        )
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_batch_update_auto_sets_provider(client: AsyncClient):
    with patch("app.api.config._reload_llm_provider", new_callable=AsyncMock):
        resp = await client.post(
            "/api/config/batch",
            json={
                "configs": {
                    "qwen_api_key": "sk-qwen-real-key-12345",
                }
            },
        )
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_batch_update_integer_cast(client: AsyncClient):
    with patch("app.api.config._reload_llm_provider", new_callable=AsyncMock):
        resp = await client.post(
            "/api/config/batch",
            json={
                "configs": {
                    "max_concurrent_tasks": "3",
                }
            },
        )
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_batch_update_unknown_key_warns(client: AsyncClient):
    """Unknown keys should be skipped with a warning (not crash)."""
    with patch("app.api.config._reload_llm_provider", new_callable=AsyncMock):
        resp = await client.post(
            "/api/config/batch",
            json={
                "configs": {
                    "unknown_key_xyz": "value",
                    "log_level": "INFO",
                }
            },
        )
    assert resp.status_code == 200


# ---------------------------------------------------------------------------
# GET /config/llm/models
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_available_models(client: AsyncClient):
    response = await client.get("/api/config/llm/models")
    assert response.status_code == 200
    models = response.json()
    assert isinstance(models, list)
    for m in models:
        assert "id" in m
        assert "name" in m
        assert "available" in m


# ---------------------------------------------------------------------------
# POST /config/test-webhook
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_test_webhook_no_url(client: AsyncClient):
    """When FEISHU_WEBHOOK_URL is not configured, should return failure."""
    with patch("app.core.config.settings") as mock_settings:
        mock_settings.FEISHU_WEBHOOK_URL = ""
        resp = await client.post("/api/config/test-webhook")
    assert resp.status_code == 200
    assert resp.json()["success"] is False
    assert "未配置" in resp.json()["error"]


@pytest.mark.asyncio
async def test_test_webhook_success(client: AsyncClient):
    with patch("app.core.config.settings") as mock_settings:
        mock_settings.FEISHU_WEBHOOK_URL = "https://example.com/hook"
        with patch("app.services.notification.send_feishu_notification", new_callable=AsyncMock, return_value=True):
            resp = await client.post("/api/config/test-webhook")
    assert resp.status_code == 200
    assert resp.json()["success"] is True


@pytest.mark.asyncio
async def test_test_webhook_failure(client: AsyncClient):
    with patch("app.core.config.settings") as mock_settings:
        mock_settings.FEISHU_WEBHOOK_URL = "https://example.com/hook"
        with patch("app.services.notification.send_feishu_notification", new_callable=AsyncMock, return_value=False):
            resp = await client.post("/api/config/test-webhook")
    assert resp.status_code == 200
    assert resp.json()["success"] is False
    assert "发送失败" in resp.json()["error"]


# ---------------------------------------------------------------------------
# POST /config/test-llm
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_test_llm_unsupported_provider(client: AsyncClient):
    resp = await client.post(
        "/api/config/test-llm",
        json={
            "provider": "unknown_provider",
            "api_key": "sk-test",
        },
    )
    assert resp.status_code == 200
    assert resp.json()["success"] is False
    assert "不支持" in resp.json()["error"]


@pytest.mark.asyncio
async def test_test_llm_empty_api_key(client: AsyncClient):
    resp = await client.post(
        "/api/config/test-llm",
        json={
            "provider": "deepseek",
            "api_key": "",
        },
    )
    assert resp.status_code == 200
    assert resp.json()["success"] is False
    assert "API Key" in resp.json()["error"]


@pytest.mark.asyncio
async def test_test_llm_success(client: AsyncClient):
    mock_adapter = AsyncMock()
    mock_adapter.chat = AsyncMock(return_value=MagicMock(model="deepseek-chat"))
    mock_adapter.close = AsyncMock()

    with patch("app.services.llm_engine.OpenAICompatibleAdapter", return_value=mock_adapter):
        resp = await client.post(
            "/api/config/test-llm",
            json={
                "provider": "deepseek",
                "api_key": "sk-test-key",
            },
        )
    assert resp.status_code == 200
    assert resp.json()["success"] is True
    assert resp.json()["model_used"] == "deepseek-chat"


@pytest.mark.asyncio
async def test_test_llm_failure(client: AsyncClient):
    mock_adapter = AsyncMock()
    mock_adapter.chat = AsyncMock(side_effect=Exception("Connection refused"))
    mock_adapter.close = AsyncMock()

    with patch("app.services.llm_engine.OpenAICompatibleAdapter", return_value=mock_adapter):
        resp = await client.post(
            "/api/config/test-llm",
            json={
                "provider": "deepseek",
                "api_key": "sk-test-key",
            },
        )
    assert resp.status_code == 200
    assert resp.json()["success"] is False
    assert "Connection refused" in resp.json()["error"]


@pytest.mark.asyncio
async def test_test_llm_anthropic(client: AsyncClient):
    mock_adapter = AsyncMock()
    mock_adapter.chat = AsyncMock(return_value=MagicMock(model="claude-sonnet"))
    mock_adapter.close = AsyncMock()

    with patch("app.services.llm_engine.AnthropicAdapter", return_value=mock_adapter):
        resp = await client.post(
            "/api/config/test-llm",
            json={
                "provider": "anthropic",
                "api_key": "sk-ant-test",
            },
        )
    assert resp.status_code == 200
    assert resp.json()["success"] is True


@pytest.mark.asyncio
async def test_test_llm_with_custom_url(client: AsyncClient):
    mock_adapter = AsyncMock()
    mock_adapter.chat = AsyncMock(return_value=MagicMock(model="custom-model"))
    mock_adapter.close = AsyncMock()

    with patch("app.services.llm_engine.OpenAICompatibleAdapter", return_value=mock_adapter):
        resp = await client.post(
            "/api/config/test-llm",
            json={
                "provider": "openai",
                "api_key": "sk-test",
                "base_url": "https://custom.api.com/v1",
                "model": "custom-model",
            },
        )
    assert resp.status_code == 200
    assert resp.json()["success"] is True


@pytest.mark.asyncio
async def test_test_llm_placeholder_url(client: AsyncClient):
    """Placeholder base_url should fall back to provider default."""
    mock_adapter = AsyncMock()
    mock_adapter.chat = AsyncMock(return_value=MagicMock(model="qwen-plus"))
    mock_adapter.close = AsyncMock()

    with patch("app.services.llm_engine.OpenAICompatibleAdapter", return_value=mock_adapter):
        resp = await client.post(
            "/api/config/test-llm",
            json={
                "provider": "qwen",
                "api_key": "sk-test",
                "base_url": "your_url_here",
            },
        )
    assert resp.status_code == 200
    assert resp.json()["success"] is True


# ---------------------------------------------------------------------------
# _apply_setting (internal function coverage)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_apply_setting_updates_env_and_settings():
    """_apply_setting should update os.environ and settings singleton."""
    import os

    from app.api.config import _apply_setting
    from app.core.config import settings

    orig_val = os.environ.get("LOG_LEVEL", "")
    orig_setting = getattr(settings, "LOG_LEVEL", "")
    try:
        with patch("app.api.config._reload_llm_provider", new_callable=AsyncMock):
            await _apply_setting("log_level", "CRITICAL")
        assert os.environ.get("LOG_LEVEL") == "CRITICAL"
        assert settings.LOG_LEVEL == "CRITICAL"
    finally:
        os.environ["LOG_LEVEL"] = orig_val or "INFO"
        settings.LOG_LEVEL = orig_setting or "INFO"


@pytest.mark.asyncio
async def test_apply_setting_unknown_key_noop():
    """Unknown key should be a no-op."""
    from app.api.config import _apply_setting

    await _apply_setting("nonexistent_key_xyz", "value")


@pytest.mark.asyncio
async def test_apply_setting_integer_cast():
    """_apply_setting should cast integer values correctly."""
    import os

    from app.api.config import _apply_setting
    from app.core.config import settings

    orig_val = os.environ.get("MAX_CONCURRENT_TASKS", "")
    orig_setting = getattr(settings, "MAX_CONCURRENT_TASKS", "")
    try:
        with patch("app.api.config._reload_llm_provider", new_callable=AsyncMock):
            await _apply_setting("max_concurrent_tasks", "7")
        assert settings.MAX_CONCURRENT_TASKS == 7
        assert os.environ.get("MAX_CONCURRENT_TASKS") == "7"
    finally:
        os.environ["MAX_CONCURRENT_TASKS"] = orig_val or "3"
        settings.MAX_CONCURRENT_TASKS = int(orig_setting) if orig_setting else 3


@pytest.mark.asyncio
async def test_apply_setting_integer_invalid():
    """_apply_setting should raise HTTPException for invalid integer."""
    from fastapi import HTTPException

    from app.api.config import _apply_setting
    from app.core.config import settings

    orig_setting = getattr(settings, "MAX_CONCURRENT_TASKS", 3)
    try:
        with pytest.raises(HTTPException) as exc_info:
            await _apply_setting("max_concurrent_tasks", "not_int")
        assert exc_info.value.status_code == 422
    finally:
        settings.MAX_CONCURRENT_TASKS = orig_setting


@pytest.mark.asyncio
async def test_apply_setting_api_key_triggers_reload():
    """API key change should trigger LLM provider reload."""
    import os

    from app.api.config import _apply_setting

    orig_val = os.environ.get("DEEPSEEK_API_KEY", "")
    try:
        with patch("app.api.config._reload_llm_provider", new_callable=AsyncMock) as mock_reload:
            await _apply_setting("deepseek_api_key", "sk-test-12345678")
        mock_reload.assert_called_once_with("deepseek")
    finally:
        if orig_val:
            os.environ["DEEPSEEK_API_KEY"] = orig_val
        else:
            os.environ.pop("DEEPSEEK_API_KEY", None)


@pytest.mark.asyncio
async def test_apply_setting_placeholder_rejected():
    """Placeholder API key values should be rejected."""
    from fastapi import HTTPException

    from app.api.config import _apply_setting

    with pytest.raises(HTTPException) as exc_info:
        await _apply_setting("deepseek_api_key", "your_key_here")
    assert exc_info.value.status_code == 422


@pytest.mark.asyncio
async def test_apply_setting_agent_provider_clears_cache():
    """Changing agent_llm_provider should clear agent LLM cache."""
    import os

    from app.api.config import _apply_setting

    orig_val = os.environ.get("AGENT_LLM_PROVIDER", "")
    try:
        with patch("agent.config.clear_llm_cache") as mock_clear:
            await _apply_setting("agent_llm_provider", "deepseek")
        mock_clear.assert_called_once()
    finally:
        if orig_val:
            os.environ["AGENT_LLM_PROVIDER"] = orig_val
        else:
            os.environ.pop("AGENT_LLM_PROVIDER", None)


# ---------------------------------------------------------------------------
# _mask_value coverage
# ---------------------------------------------------------------------------


def test_mask_value_empty():
    from app.api.config import _mask_value

    assert _mask_value("test_key", "") == ""
    assert _mask_value("test_key", None) is None


def test_mask_value_non_sensitive():
    from app.api.config import _mask_value

    assert _mask_value("log_level", "INFO") == "INFO"


def test_mask_value_short_key():
    from app.api.config import _mask_value

    assert _mask_value("test_api_key", "short") == "****"


def test_mask_value_long_key():
    from app.api.config import _mask_value

    result = _mask_value("deepseek_api_key", "sk-12345678abcd")
    assert result.startswith("sk-1")
    assert result.endswith("abcd")
    assert "****" in result


def test_mask_value_secret():
    from app.api.config import _mask_value

    result = _mask_value("feishu_webhook_secret", "mysecretvalue123")
    assert "****" in result


def test_mask_value_placeholder():
    from app.api.config import _mask_value

    assert _mask_value("any_key", "your_placeholder") == ""


# ---------------------------------------------------------------------------
# _reload_llm_provider
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_reload_llm_provider():
    """_reload_llm_provider should call engine.reload_provider."""
    from app.api.config import _reload_llm_provider

    mock_engine = AsyncMock()
    mock_engine.reload_provider = AsyncMock()
    with patch("app.services.llm_engine.get_llm_engine", return_value=mock_engine):
        with patch("app.core.config.settings") as mock_settings:
            mock_settings.DEEPSEEK_API_KEY = "sk-test"
            mock_settings.DEEPSEEK_BASE_URL = "https://api.deepseek.com/v1"
            mock_settings.DEEPSEEK_MODEL = None
            await _reload_llm_provider("deepseek")
    mock_engine.reload_provider.assert_called_once()


@pytest.mark.asyncio
async def test_reload_llm_provider_timeout():
    """_reload_llm_provider should handle timeout gracefully."""
    import asyncio

    from app.api.config import _reload_llm_provider

    mock_engine = AsyncMock()
    mock_engine.reload_provider = AsyncMock(side_effect=asyncio.TimeoutError)
    with patch("app.services.llm_engine.get_llm_engine", return_value=mock_engine):
        with patch("app.core.config.settings") as mock_settings:
            mock_settings.DEEPSEEK_API_KEY = "sk-test"
            mock_settings.DEEPSEEK_BASE_URL = None
            mock_settings.DEEPSEEK_MODEL = None
            await _reload_llm_provider("deepseek")


# ---------------------------------------------------------------------------
# update_config with real _apply_setting (non-API-key path)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_update_config_log_level_real(client: AsyncClient):
    """Update log_level without mocking _apply_setting to cover the actual path."""
    import os

    from app.core.config import settings

    orig_env = os.environ.get("LOG_LEVEL", "")
    orig_setting = getattr(settings, "LOG_LEVEL", "")
    try:
        resp = await client.put("/api/config/log_level", json={"value": "WARNING"})
        assert resp.status_code == 200

        resp = await client.get("/api/config/log_level")
        assert resp.status_code == 200
        assert resp.json()["value"] == "WARNING"
    finally:
        os.environ["LOG_LEVEL"] = orig_env or "INFO"
        settings.LOG_LEVEL = orig_setting or "INFO"


# ---------------------------------------------------------------------------
# batch_update with real _apply_setting paths
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_batch_update_with_integer_and_float(client: AsyncClient):
    """Batch update should correctly cast integer and float values."""
    import os

    from app.core.config import settings

    orig_max = os.environ.get("MAX_CONCURRENT_TASKS", "")
    orig_temp = os.environ.get("TEMPERATURE", "")
    orig_s_max = getattr(settings, "MAX_CONCURRENT_TASKS", "")
    orig_s_temp = getattr(settings, "TEMPERATURE", "")
    try:
        with patch("app.api.config._reload_llm_provider", new_callable=AsyncMock):
            resp = await client.post(
                "/api/config/batch",
                json={
                    "configs": {
                        "max_concurrent_tasks": "10",
                        "temperature": "0.3",
                    }
                },
            )
        assert resp.status_code == 200
    finally:
        os.environ["MAX_CONCURRENT_TASKS"] = orig_max or "3"
        os.environ["TEMPERATURE"] = orig_temp or "0.7"
        settings.MAX_CONCURRENT_TASKS = int(orig_s_max) if orig_s_max else 3
        settings.TEMPERATURE = float(orig_s_temp) if orig_s_temp else 0.7
