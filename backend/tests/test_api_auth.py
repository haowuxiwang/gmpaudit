import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_get_me(client: AsyncClient):
    response = await client.get("/api/auth/me")
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Test User"
    assert data["email"] == "test@example.com"


@pytest.mark.asyncio
async def test_feishu_login_returns_url(client: AsyncClient):
    # This endpoint doesn't require auth (in PUBLIC_PATHS via middleware)
    # But our test client overrides get_current_user, so it should work
    response = await client.get("/api/auth/feishu/login")
    assert response.status_code == 200
    data = response.json()
    assert "url" in data
    assert "feishu.cn" in data["url"]
