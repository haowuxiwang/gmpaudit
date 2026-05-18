import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_get_config(client: AsyncClient):
    response = await client.get("/api/config/")
    assert response.status_code == 200
    assert isinstance(response.json(), dict)


@pytest.mark.asyncio
async def test_get_config_by_key_not_found(client: AsyncClient):
    response = await client.get("/api/config/nonexistent_key")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_update_and_get_config(client: AsyncClient):
    # Update a config
    response = await client.put("/api/config/test_key?value=test_value&description=测试配置")
    assert response.status_code == 200
    assert response.json()["status"] == "success"

    # Get it back
    response = await client.get("/api/config/test_key")
    assert response.status_code == 200
    assert response.json()["key"] == "test_key"
    # Value is masked because key contains "key"
    assert response.json()["value"] == "test****alue"


@pytest.mark.asyncio
async def test_update_existing_config(client: AsyncClient):
    # Create
    await client.put("/api/config/my_key?value=v1")
    # Update
    await client.put("/api/config/my_key?value=v2")
    # Verify
    response = await client.get("/api/config/my_key")
    # Value is masked because key contains "key" and value is short
    assert response.json()["value"] == "****"


@pytest.mark.asyncio
async def test_get_available_models(client: AsyncClient):
    response = await client.get("/api/config/llm/models")
    assert response.status_code == 200
    models = response.json()
    assert isinstance(models, list)
