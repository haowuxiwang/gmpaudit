import pytest
from httpx import AsyncClient

@pytest.mark.asyncio
async def test_upload_document(client: AsyncClient):
    # 创建测试文件（使用支持的PDF格式）
    files = {"file": ("test.pdf", b"test content", "application/pdf")}
    response = await client.post("/api/documents/upload", files=files)
    assert response.status_code == 200
    data = response.json()
    assert "id" in data
    assert data["filename"] == "test.pdf"
    assert data["status"] == "uploaded"

@pytest.mark.asyncio
async def test_list_documents(client: AsyncClient):
    response = await client.get("/api/documents/")
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert "total" in data
    assert isinstance(data["items"], list)

@pytest.mark.asyncio
async def test_get_document(client: AsyncClient):
    # 先上传文档
    files = {"file": ("test.pdf", b"test content", "application/pdf")}
    upload_response = await client.post("/api/documents/upload", files=files)
    doc_id = upload_response.json()["id"]

    # 获取文档
    response = await client.get(f"/api/documents/{doc_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == doc_id
    assert data["filename"] == "test.pdf"

@pytest.mark.asyncio
async def test_get_nonexistent_document(client: AsyncClient):
    response = await client.get("/api/documents/999")
    assert response.status_code == 404

@pytest.mark.asyncio
async def test_delete_document(client: AsyncClient):
    # 先上传文档
    files = {"file": ("test.pdf", b"test content", "application/pdf")}
    upload_response = await client.post("/api/documents/upload", files=files)
    doc_id = upload_response.json()["id"]

    # 删除文档
    response = await client.delete(f"/api/documents/{doc_id}")
    assert response.status_code == 200
    assert response.json()["status"] == "success"

    # 验证文档已删除
    get_response = await client.get(f"/api/documents/{doc_id}")
    assert get_response.status_code == 404
