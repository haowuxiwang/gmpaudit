"""Tests for the authentication middleware protecting sensitive endpoints.

The middleware requires a valid Bearer token for sensitive mutation endpoints
(config changes, audit actions) even in dev (non-frozen) mode.
"""

import sys
from unittest.mock import patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.fixture
async def auth_client():
    """Client with api_token set (simulates a session with auth enabled)."""
    from app.services.event_bus import EventBus

    app.state.api_token = "test-token-12345"
    app.state.event_bus = EventBus()

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        yield ac

    # Cleanup
    if hasattr(app.state, "api_token"):
        del app.state.api_token


# ---------------------------------------------------------------------------
# Config mutation endpoints require auth
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_put_config_requires_auth(auth_client: AsyncClient):
    """PUT /api/config/{key} should return 401 without valid token."""
    resp = await auth_client.put(
        "/api/config/log_level",
        json={"value": "DEBUG"},
        headers={"Authorization": "Bearer wrong-token"},
    )
    assert resp.status_code == 401
    assert "未授权" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_put_config_with_valid_token(auth_client: AsyncClient):
    """PUT /api/config/{key} should succeed with valid token."""
    from unittest.mock import AsyncMock

    with patch("app.api.config._apply_setting", new_callable=AsyncMock):
        resp = await auth_client.put(
            "/api/config/log_level",
            json={"value": "DEBUG"},
            headers={"Authorization": "Bearer test-token-12345"},
        )
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_put_config_no_header_returns_401(auth_client: AsyncClient):
    """PUT /api/config/{key} without Authorization header should return 401."""
    resp = await auth_client.put(
        "/api/config/log_level",
        json={"value": "DEBUG"},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_batch_config_requires_auth(auth_client: AsyncClient):
    """POST /api/config/batch should return 401 without valid token."""
    resp = await auth_client.post(
        "/api/config/batch",
        json={"configs": {"log_level": "DEBUG"}},
        headers={"Authorization": "Bearer wrong-token"},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_test_llm_requires_auth(auth_client: AsyncClient):
    """POST /api/config/test-llm should return 401 without valid token."""
    resp = await auth_client.post(
        "/api/config/test-llm",
        json={"provider": "deepseek", "api_key": "sk-test"},
        headers={"Authorization": "Bearer wrong-token"},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_test_webhook_requires_auth(auth_client: AsyncClient):
    """POST /api/config/test-webhook should return 401 without valid token."""
    resp = await auth_client.post(
        "/api/config/test-webhook",
        headers={"Authorization": "Bearer wrong-token"},
    )
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Audit action endpoints require auth
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_audit_run_requires_auth(auth_client: AsyncClient):
    """POST /api/audit/tasks/{id}/run should return 401 without valid token."""
    resp = await auth_client.post(
        "/api/audit/tasks/1/run",
        headers={"Authorization": "Bearer wrong-token"},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_audit_cancel_requires_auth(auth_client: AsyncClient):
    """POST /api/audit/tasks/{id}/cancel should return 401 without valid token."""
    resp = await auth_client.post(
        "/api/audit/tasks/1/cancel",
        headers={"Authorization": "Bearer wrong-token"},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_audit_approve_requires_auth(auth_client: AsyncClient):
    """POST /api/audit/tasks/{id}/approve should return 401 without valid token."""
    resp = await auth_client.post(
        "/api/audit/tasks/1/approve",
        headers={"Authorization": "Bearer wrong-token"},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_audit_reject_requires_auth(auth_client: AsyncClient):
    """POST /api/audit/tasks/{id}/reject should return 401 without valid token."""
    resp = await auth_client.post(
        "/api/audit/tasks/1/reject",
        headers={"Authorization": "Bearer wrong-token"},
    )
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Read-only endpoints do NOT require auth in dev mode
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_config_no_auth_needed(auth_client: AsyncClient):
    """GET /api/config/ should work without auth in dev mode."""
    resp = await auth_client.get("/api/config/")
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_get_config_by_key_no_auth_needed(auth_client: AsyncClient):
    """GET /api/config/{key} should work without auth in dev mode."""
    resp = await auth_client.get("/api/config/log_level")
    # May be 404 if key doesn't exist, but should NOT be 401
    assert resp.status_code != 401


@pytest.mark.asyncio
async def test_health_no_auth_needed(auth_client: AsyncClient):
    """GET /api/health should work without auth."""
    resp = await auth_client.get("/api/health")
    assert resp.status_code == 200


# ---------------------------------------------------------------------------
# No api_token set = auth is skipped (backward compatibility)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_no_token_set_skips_auth():
    """When api_token is not set on app.state, auth should be skipped entirely."""
    from app.services.event_bus import EventBus

    if hasattr(app.state, "api_token"):
        del app.state.api_token
    app.state.event_bus = EventBus()

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        from unittest.mock import AsyncMock

        with patch("app.api.config._apply_setting", new_callable=AsyncMock):
            resp = await ac.put(
                "/api/config/log_level",
                json={"value": "DEBUG"},
            )
    # No token set -> auth skipped -> should NOT be 401
    assert resp.status_code != 401
