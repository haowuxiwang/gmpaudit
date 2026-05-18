"""Integration tests for agent audit API endpoints."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.document import Document, DocumentStatus
from app.models.audit_task import AuditTask, TaskStatus, TaskType


@pytest.mark.asyncio
class TestAgentAuditIntegration:
    """Test agent audit workflow through API."""

    async def test_run_agent_audit_starts_task(self, client: AsyncClient, db_session: AsyncSession):
        """Run agent audit creates a task and returns task_id."""
        # Create a processed document
        doc = Document(
            filename="test.txt",
            file_path="/tmp/test.txt",
            file_type="txt",
            file_size=100,
            process_status=DocumentStatus.PROCESSED,
            content_text="Test document content about GMP deviation handling.",
        )
        db_session.add(doc)
        await db_session.commit()
        await db_session.refresh(doc)

        # Mock AGENT_AVAILABLE to True
        with patch("app.api.agent_audit.AGENT_AVAILABLE", True):
            response = await client.post(
                "/api/agent-audit/run",
                json={"document_id": doc.id, "audit_type": "deviation"},
            )

            # Should return 200 with task_id
            assert response.status_code == 200
            data = response.json()
            assert "task_id" in data
            assert data["status"] == "pending"

    async def test_run_agent_audit_document_not_found(self, client: AsyncClient):
        """Run audit on non-existent document returns 404."""
        response = await client.post(
            "/api/agent-audit/run",
            json={"document_id": 99999, "audit_type": "deviation"},
        )

        assert response.status_code == 404

    async def test_run_agent_audit_document_not_processed(self, client: AsyncClient, db_session: AsyncSession):
        """Run audit on unprocessed document returns 400."""
        doc = Document(
            filename="test.txt",
            file_path="/tmp/test.txt",
            file_type="txt",
            file_size=100,
            process_status=DocumentStatus.UPLOADED,
            content_text="",
        )
        db_session.add(doc)
        await db_session.commit()
        await db_session.refresh(doc)

        response = await client.post(
            "/api/agent-audit/run",
            json={"document_id": doc.id, "audit_type": "deviation"},
        )

        assert response.status_code == 400

    async def test_get_agent_audit_status(self, client: AsyncClient, db_session: AsyncSession):
        """Get audit task status."""
        task = AuditTask(
            task_name="Test Audit",
            task_type=TaskType.DEVIATION_ANALYSIS,
            status=TaskStatus.RUNNING,
            progress=50,
            document_ids=[1],
        )
        db_session.add(task)
        await db_session.commit()
        await db_session.refresh(task)

        response = await client.get(f"/api/agent-audit/status/{task.id}")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] in ("pending", "running")
        assert data["progress"] == 50

    async def test_get_agent_audit_status_not_found(self, client: AsyncClient):
        """Get status of non-existent task returns 404."""
        response = await client.get("/api/agent-audit/status/99999")

        assert response.status_code == 404

    async def test_run_agent_audit_agent_unavailable(self, client: AsyncClient, db_session: AsyncSession):
        """Run audit when agent is unavailable returns 503."""
        doc = Document(
            filename="test.txt",
            file_path="/tmp/test.txt",
            file_type="txt",
            file_size=100,
            process_status=DocumentStatus.PROCESSED,
            content_text="Test content",
        )
        db_session.add(doc)
        await db_session.commit()
        await db_session.refresh(doc)

        # Mock AGENT_AVAILABLE to False
        with patch("app.api.agent_audit.AGENT_AVAILABLE", False):
            response = await client.post(
                "/api/agent-audit/run",
                json={"document_id": doc.id, "audit_type": "deviation"},
            )

            assert response.status_code == 503


@pytest.mark.asyncio
class TestAuditTaskAPI:
    """Test audit task CRUD operations."""

    async def test_create_task(self, client: AsyncClient, db_session: AsyncSession):
        """Create an audit task."""
        doc = Document(
            filename="test.txt",
            file_path="/tmp/test.txt",
            file_type="txt",
            file_size=100,
            process_status=DocumentStatus.PROCESSED,
            content_text="Test content",
        )
        db_session.add(doc)
        await db_session.commit()
        await db_session.refresh(doc)

        response = await client.post(
            "/api/audit/tasks",
            json={
                "task_name": "Test Task",
                "task_type": "deviation_analysis",
                "document_ids": [doc.id],
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["task_name"] == "Test Task"
        assert data["status"] == "pending"

    async def test_list_tasks(self, client: AsyncClient, db_session: AsyncSession):
        """List audit tasks."""
        task = AuditTask(
            task_name="Test Task",
            task_type=TaskType.DEVIATION_ANALYSIS,
            status=TaskStatus.PENDING,
            document_ids=[],
        )
        db_session.add(task)
        await db_session.commit()

        response = await client.get("/api/audit/tasks")

        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert len(data["items"]) > 0

    async def test_get_task_by_id(self, client: AsyncClient, db_session: AsyncSession):
        """Get a specific task by ID."""
        task = AuditTask(
            task_name="Test Task",
            task_type=TaskType.DEVIATION_ANALYSIS,
            status=TaskStatus.COMPLETED,
            progress=100,
            document_ids=[],
        )
        db_session.add(task)
        await db_session.commit()
        await db_session.refresh(task)

        response = await client.get(f"/api/audit/tasks/{task.id}")

        assert response.status_code == 200
        data = response.json()
        assert data["task_name"] == "Test Task"
        assert data["status"] == "completed"
