"""Comprehensive tests for app.api.config module.

Targets uncovered code paths to increase coverage from 61% to 80%.
"""

import pytest
from httpx import AsyncClient
from unittest.mock import patch, AsyncMock, MagicMock

from app.models.configuration import Configuration


@pytest.mark.asyncio
class TestConfigAPI:
    """Tests for config API endpoints."""

    async def test_get_config_empty(self, client: AsyncClient):
        """GET /config/ with no configs returns empty dict."""
        resp = await client.get("/api/config/")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, dict)

    async def test_get_config_with_data(self, client: AsyncClient, db_session):
        """GET /config/ returns configs from DB."""
        config = Configuration(
            config_key="LOG_LEVEL",
            config_value="INFO",
            config_type="string",
            description="Log level",
        )
        db_session.add(config)
        await db_session.commit()

        resp = await client.get("/api/config/")
        assert resp.status_code == 200
        data = resp.json()
        assert "LOG_LEVEL" in data
        assert data["LOG_LEVEL"]["value"] == "INFO"

    async def test_get_config_masks_api_key(self, client: AsyncClient, db_session):
        """GET /config/ masks API key values."""
        config = Configuration(
            config_key="DEEPSEEK_API_KEY",
            config_value="sk-1234567890abcdef",
            config_type="string",
        )
        db_session.add(config)
        await db_session.commit()

        resp = await client.get("/api/config/")
        assert resp.status_code == 200
        data = resp.json()
        # Should be masked
        assert "****" in data["DEEPSEEK_API_KEY"]["value"]
        assert data["DEEPSEEK_API_KEY"]["value"] != "sk-1234567890abcdef"

    async def test_get_config_by_key(self, client: AsyncClient, db_session):
        """GET /config/{key} returns specific config."""
        config = Configuration(
            config_key="LOG_LEVEL",
            config_value="DEBUG",
            config_type="string",
        )
        db_session.add(config)
        await db_session.commit()

        resp = await client.get("/api/config/LOG_LEVEL")
        assert resp.status_code == 200
        data = resp.json()
        assert data["key"] == "LOG_LEVEL"
        assert data["value"] == "DEBUG"

    async def test_get_config_by_key_not_found(self, client: AsyncClient):
        """GET /config/{key} returns 404 for unknown key."""
        resp = await client.get("/api/config/UNKNOWN_KEY")
        assert resp.status_code == 404

    async def test_update_config(self, client: AsyncClient, db_session):
        """PUT /config/{key} updates existing config."""
        config = Configuration(
            config_key="LOG_LEVEL",
            config_value="INFO",
            config_type="string",
        )
        db_session.add(config)
        await db_session.commit()

        resp = await client.put("/api/config/LOG_LEVEL", json={"value": "DEBUG"})
        assert resp.status_code == 200
        assert resp.json()["status"] == "success"

    async def test_update_config_unknown_key(self, client: AsyncClient):
        """PUT /config/{key} rejects unknown key."""
        resp = await client.put("/api/config/UNKNOWN_KEY", json={"value": "test"})
        assert resp.status_code == 400

    async def test_update_config_placeholder_rejected(self, client: AsyncClient):
        """PUT /config/{key} rejects placeholder values."""
        resp = await client.put("/api/config/DEEPSEEK_API_KEY", json={"value": "your_api_key_here"})
        assert resp.status_code == 422

    async def test_batch_update_config(self, client: AsyncClient, db_session):
        """POST /config/batch updates multiple configs."""
        resp = await client.post("/api/config/batch", json={
            "configs": {
                "LOG_LEVEL": "DEBUG",
                "MAX_CONCURRENT_TASKS": "5",
            }
        })
        assert resp.status_code == 200
        assert resp.json()["status"] == "success"

    async def test_test_webhook_no_url(self, client: AsyncClient):
        """POST /config/test-webhook returns error when no URL configured."""
        with patch("app.core.config.settings") as mock_settings:
            mock_settings.FEISHU_WEBHOOK_URL = ""
            resp = await client.post("/api/config/test-webhook")
            assert resp.status_code == 200
            data = resp.json()
            assert data["success"] is False

    async def test_get_available_models(self, client: AsyncClient):
        """GET /config/llm/models returns available models."""
        resp = await client.get("/api/config/llm/models")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)


@pytest.mark.asyncio
class TestConfigMaskValue:
    """Tests for _mask_value helper."""

    def test_mask_short_key(self):
        from app.api.config import _mask_value
        assert _mask_value("API_KEY", "short") == "****"

    def test_mask_long_key(self):
        from app.api.config import _mask_value
        result = _mask_value("API_KEY", "sk-1234567890abcdef")
        assert result.startswith("sk-1")
        assert result.endswith("cdef")
        assert "****" in result

    def test_mask_non_key_field(self):
        from app.api.config import _mask_value
        assert _mask_value("LOG_LEVEL", "INFO") == "INFO"

    def test_mask_empty_value(self):
        from app.api.config import _mask_value
        assert _mask_value("API_KEY", "") == ""

    def test_mask_placeholder(self):
        from app.api.config import _mask_value
        assert _mask_value("API_KEY", "your_api_key") == ""
