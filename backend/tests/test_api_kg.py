"""Tests for knowledge graph API endpoints."""

import os
from unittest.mock import AsyncMock, patch

import pytest

# Ensure test env
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-for-testing-only")


@pytest.mark.asyncio
async def test_get_status(client):
    resp = await client.get("/api/kg/status")
    assert resp.status_code == 200
    data = resp.json()
    assert "built" in data
    assert "input_file_count" in data
    assert "building" in data


@pytest.mark.asyncio
async def test_get_documents(client):
    resp = await client.get("/api/kg/documents")
    assert resp.status_code == 200
    data = resp.json()
    assert "documents" in data
    assert isinstance(data["documents"], list)


@pytest.mark.asyncio
async def test_get_build_status(client):
    resp = await client.get("/api/kg/build-status")
    assert resp.status_code == 200
    data = resp.json()
    assert "building" in data
    assert data["building"] is False


@pytest.mark.asyncio
async def test_query_without_index(client):
    """Query should fail gracefully when index is not built."""
    with patch("app.api.kg._get_index_info", return_value={"built": False, "file_count": 0, "last_modified": None}):
        resp = await client.post("/api/kg/query", json={"query": "test", "method": "local"})
        assert resp.status_code == 400
        assert "尚未构建" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_query_with_index(client):
    """Query should return results when index is built."""
    mock_results = [{"regulation": "test", "content": "test content", "title": "test"}]
    with patch("app.api.kg._get_index_info", return_value={"built": True, "file_count": 5, "last_modified": "2026-01-01T00:00:00"}), \
         patch("agent.tools.lightrag_tool.lightrag_search", new_callable=AsyncMock, return_value=mock_results):
        resp = await client.post("/api/kg/query", json={"query": "GMP 数据完整性", "method": "local"})
        assert resp.status_code == 200
        data = resp.json()
        assert "results" in data
        assert len(data["results"]) == 1


@pytest.mark.asyncio
async def test_build_without_input(client):
    """Build should fail when no input files exist."""
    with patch("app.api.kg.os.path.isdir", return_value=True), \
         patch("app.api.kg.os.listdir", return_value=[".gitkeep"]):
        resp = await client.post("/api/kg/build")
        assert resp.status_code == 400
        assert "没有输入文件" in resp.json()["detail"]
