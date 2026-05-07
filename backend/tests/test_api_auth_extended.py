import os
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_feishu_callback_missing_code(client: AsyncClient):
    response = await client.get("/api/auth/feishu/callback")
    assert response.status_code == 422  # Missing required query param


@pytest.mark.asyncio
async def test_feishu_callback_missing_csrf_state(client: AsyncClient):
    """Callback without CSRF cookie should fail."""
    response = await client.get("/api/auth/feishu/callback?code=test_code&state=test_state")
    assert response.status_code == 400
    assert "CSRF" in response.json()["detail"]


@pytest.mark.asyncio
async def test_root_endpoint(client: AsyncClient):
    response = await client.get("/")
    assert response.status_code == 200
    assert "GMP" in response.json()["message"]


@pytest.mark.asyncio
async def test_startup_event():
    """Test that the startup event runs without errors."""
    from app.main import startup
    # Should not raise — JWT_SECRET_KEY is set in conftest
    await startup()


@pytest.mark.asyncio
async def test_startup_rejects_default_jwt_key():
    """Startup should fail with default JWT key."""
    import app.core.config as config_module
    original_key = config_module.settings.JWT_SECRET_KEY
    config_module.settings.JWT_SECRET_KEY = "gmp-audit-secret-key-change-in-production"
    try:
        from app.main import startup
        with pytest.raises(RuntimeError, match="JWT_SECRET_KEY"):
            await startup()
    finally:
        config_module.settings.JWT_SECRET_KEY = original_key
