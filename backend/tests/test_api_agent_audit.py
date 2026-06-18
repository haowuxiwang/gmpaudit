from unittest.mock import MagicMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit_task import AuditTask, TaskStatus, TaskType
from app.models.document import Document, DocumentStatus

# ---------------------------------------------------------------------------
# Run agent audit
# ---------------------------------------------------------------------------


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
    assert "未处理" in response.json()["detail"]


@pytest.mark.asyncio
async def test_agent_audit_unavailable(client: AsyncClient, db_session: AsyncSession):
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

    with patch("app.api.agent_audit.is_agent_available", return_value=False):
        response = await client.post(
            "/api/agent-audit/run",
            json={"document_id": doc.id, "audit_type": "deviation"},
        )
        assert response.status_code == 503


@pytest.mark.asyncio
async def test_agent_audit_invalid_type(client: AsyncClient, db_session: AsyncSession):
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

    resp = await client.post(
        "/api/agent-audit/run",
        json={"document_id": doc.id, "audit_type": "invalid_type"},
    )
    assert resp.status_code == 400
    assert "无效" in resp.json()["detail"] or "invalid" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_agent_audit_deviation_success(client: AsyncClient, db_session: AsyncSession):
    doc = Document(
        filename="dev.pdf",
        file_path="/tmp/dev.pdf",
        file_type="pdf",
        file_size=1024,
        process_status=DocumentStatus.PROCESSED,
    )
    db_session.add(doc)
    await db_session.commit()
    await db_session.refresh(doc)

    mock_runner = MagicMock()
    mock_factory = MagicMock(return_value=mock_runner)

    from unittest.mock import patch as _patch

    from app.main import app

    orig_factory = app.state.task_runner_factory
    app.state.task_runner_factory = mock_factory
    try:
        with _patch("app.api.agent_audit.is_agent_available", return_value=True):
            resp = await client.post(
                "/api/agent-audit/run",
                json={"document_id": doc.id, "audit_type": "deviation"},
            )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "pending"
        assert "task_id" in data
    finally:
        app.state.task_runner_factory = orig_factory


@pytest.mark.asyncio
async def test_agent_audit_sop_success(client: AsyncClient, db_session: AsyncSession):
    doc = Document(
        filename="sop.pdf",
        file_path="/tmp/sop.pdf",
        file_type="pdf",
        file_size=1024,
        process_status=DocumentStatus.PROCESSED,
    )
    db_session.add(doc)
    await db_session.commit()
    await db_session.refresh(doc)

    mock_runner = MagicMock()
    mock_factory = MagicMock(return_value=mock_runner)

    from unittest.mock import patch as _patch

    from app.main import app

    orig_factory = app.state.task_runner_factory
    app.state.task_runner_factory = mock_factory
    try:
        with _patch("app.api.agent_audit.is_agent_available", return_value=True):
            resp = await client.post(
                "/api/agent-audit/run",
                json={"document_id": doc.id, "audit_type": "sop"},
            )
        assert resp.status_code == 200
    finally:
        app.state.task_runner_factory = orig_factory


@pytest.mark.asyncio
async def test_agent_audit_change_control_success(client: AsyncClient, db_session: AsyncSession):
    doc = Document(
        filename="cc.pdf",
        file_path="/tmp/cc.pdf",
        file_type="pdf",
        file_size=1024,
        process_status=DocumentStatus.PROCESSED,
    )
    db_session.add(doc)
    await db_session.commit()
    await db_session.refresh(doc)

    mock_runner = MagicMock()
    mock_factory = MagicMock(return_value=mock_runner)

    from unittest.mock import patch as _patch

    from app.main import app

    orig_factory = app.state.task_runner_factory
    app.state.task_runner_factory = mock_factory
    try:
        with _patch("app.api.agent_audit.is_agent_available", return_value=True):
            resp = await client.post(
                "/api/agent-audit/run",
                json={"document_id": doc.id, "audit_type": "change_control"},
            )
        assert resp.status_code == 200
    finally:
        app.state.task_runner_factory = orig_factory


@pytest.mark.asyncio
async def test_agent_audit_with_focus(client: AsyncClient, db_session: AsyncSession):
    doc = Document(
        filename="focus.pdf",
        file_path="/tmp/focus.pdf",
        file_type="pdf",
        file_size=1024,
        process_status=DocumentStatus.PROCESSED,
    )
    db_session.add(doc)
    await db_session.commit()
    await db_session.refresh(doc)

    mock_runner = MagicMock()
    mock_factory = MagicMock(return_value=mock_runner)

    from unittest.mock import patch as _patch

    from app.main import app

    orig_factory = app.state.task_runner_factory
    app.state.task_runner_factory = mock_factory
    try:
        with _patch("app.api.agent_audit.is_agent_available", return_value=True):
            resp = await client.post(
                "/api/agent-audit/run",
                json={"document_id": doc.id, "audit_type": "deviation", "focus": "数据完整性"},
            )
        assert resp.status_code == 200
    finally:
        app.state.task_runner_factory = orig_factory


@pytest.mark.asyncio
async def test_agent_audit_default_focus(client: AsyncClient, db_session: AsyncSession):
    """When focus is not provided, it should default to empty string."""
    doc = Document(
        filename="nf.pdf",
        file_path="/tmp/nf.pdf",
        file_type="pdf",
        file_size=1024,
        process_status=DocumentStatus.PROCESSED,
    )
    db_session.add(doc)
    await db_session.commit()
    await db_session.refresh(doc)

    mock_runner = MagicMock()
    mock_factory = MagicMock(return_value=mock_runner)

    from unittest.mock import patch as _patch

    from app.main import app

    orig_factory = app.state.task_runner_factory
    app.state.task_runner_factory = mock_factory
    try:
        with _patch("app.api.agent_audit.is_agent_available", return_value=True):
            resp = await client.post(
                "/api/agent-audit/run",
                json={"document_id": doc.id, "audit_type": "deviation"},
            )
        assert resp.status_code == 200
    finally:
        app.state.task_runner_factory = orig_factory


# ---------------------------------------------------------------------------
# Get agent audit status
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_agent_audit_status_not_found(client: AsyncClient):
    response = await client.get("/api/agent-audit/status/999")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_get_agent_audit_status(client: AsyncClient, db_session: AsyncSession):
    task = AuditTask(
        task_name="Agent Task",
        task_type=TaskType.DEVIATION_ANALYSIS,
        status=TaskStatus.RUNNING,
        progress=50,
    )
    db_session.add(task)
    await db_session.commit()
    await db_session.refresh(task)

    resp = await client.get(f"/api/agent-audit/status/{task.id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["task_name"] == "Agent Task"
    assert data["status"] == "running"
    assert data["progress"] == 50


@pytest.mark.asyncio
async def test_get_agent_audit_status_completed(client: AsyncClient, db_session: AsyncSession):
    task = AuditTask(
        task_name="Done Task",
        task_type=TaskType.SOP_COMPLIANCE,
        status=TaskStatus.COMPLETED,
        progress=100,
    )
    db_session.add(task)
    await db_session.commit()
    await db_session.refresh(task)

    resp = await client.get(f"/api/agent-audit/status/{task.id}")
    assert resp.status_code == 200
    assert resp.json()["status"] == "completed"
