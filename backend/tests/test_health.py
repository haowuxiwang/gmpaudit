import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_health_check(client: AsyncClient):
    response = await client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["service"] == "AuditBee"


@pytest.mark.asyncio
async def test_db_health(client: AsyncClient):
    response = await client.get("/api/health/db")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"


@pytest.mark.asyncio
async def test_full_health_check(client: AsyncClient):
    response = await client.get("/api/health/full")
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert "checks" in data
    assert "database" in data["checks"]
    assert "disk" in data["checks"]
    assert "llm" in data["checks"]
    assert data["service"] == "AuditBee"
    assert data["version"] == "1.1.0"
