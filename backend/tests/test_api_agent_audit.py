import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.document import Document, DocumentStatus


@pytest.mark.asyncio
async def test_agent_audit_document_not_found(client: AsyncClient):
    response = await client.post(
        "/api/agent-audit/run",
        json={"document_id": 999, "audit_type": "deviation"},
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_agent_audit_document_not_processed(client: AsyncClient, db_session: AsyncSession):
    doc = Document(
        filename="test.pdf",
        file_path="/tmp/test.pdf",
        file_type="pdf",
        file_size=1024,
        process_status=DocumentStatus.UPLOADED,
    )
    db_session.add(doc)
    await db_session.commit()
    await db_session.refresh(doc)

    response = await client.post(
        "/api/agent-audit/run",
        json={"document_id": doc.id, "audit_type": "deviation"},
    )
    assert response.status_code == 400
    assert "not processed" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_get_agent_audit_status_not_found(client: AsyncClient):
    response = await client.get("/api/agent-audit/status/999")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_agent_audit_unavailable(client: AsyncClient, db_session: AsyncSession):
    """When agent system is not available, should return 503."""
    doc = Document(
        filename="test.pdf",
        file_path="/tmp/test.pdf",
        file_type="pdf",
        file_size=1024,
        process_status=DocumentStatus.PROCESSED,
    )
    db_session.add(doc)
    await db_session.commit()
    await db_session.refresh(doc)

    # Patch AGENT_AVAILABLE to False
    import app.api.agent_audit as agent_module
    original = agent_module.AGENT_AVAILABLE
    agent_module.AGENT_AVAILABLE = False

    try:
        response = await client.post(
            "/api/agent-audit/run",
            json={"document_id": doc.id, "audit_type": "deviation"},
        )
        assert response.status_code == 503
    finally:
        agent_module.AGENT_AVAILABLE = original
