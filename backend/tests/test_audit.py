import pytest
from httpx import AsyncClient

@pytest.mark.asyncio
async def test_create_audit_task(client: AsyncClient):
    task_data = {
        "task_name": "测试审计任务",
        "task_type": "deviation_analysis",
        "document_ids": []
    }
    response = await client.post("/api/audit/tasks", json=task_data)
    assert response.status_code == 200
    data = response.json()
    assert "id" in data
    assert data["task_name"] == "测试审计任务"
    assert data["status"] == "pending"

@pytest.mark.asyncio
async def test_list_audit_tasks(client: AsyncClient):
    response = await client.get("/api/audit/tasks")
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert isinstance(data["items"], list)

@pytest.mark.asyncio
async def test_get_audit_task(client: AsyncClient):
    # 先创建任务
    task_data = {
        "task_name": "测试审计任务",
        "task_type": "deviation_analysis",
        "document_ids": []
    }
    create_response = await client.post("/api/audit/tasks", json=task_data)
    task_id = create_response.json()["id"]

    # 获取任务
    response = await client.get(f"/api/audit/tasks/{task_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == task_id
    assert data["task_name"] == "测试审计任务"

@pytest.mark.asyncio
async def test_get_nonexistent_task(client: AsyncClient):
    response = await client.get("/api/audit/tasks/999")
    assert response.status_code == 404
