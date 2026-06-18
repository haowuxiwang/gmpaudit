"""Tests for agent_audit API to cover uncovered code paths.

Targets specific uncovered lines in agent_audit.py to increase coverage.
"""

from unittest.mock import patch

import pytest
from httpx import AsyncClient

from app.models.audit_task import AuditTask, TaskStatus, TaskType
from app.models.document import Document, DocumentStatus


@pytest.mark.asyncio
class TestAgentAuditRun:
    """Test POST /agent-audit/run endpoint."""

    async def test_run_agent_audit_agent_unavailable(self, client: AsyncClient):
        """Run audit when agent is unavailable."""
        with patch("app.api.agent_audit.is_agent_available", return_value=False):
            resp = await client.post(
                "/api/agent-audit/run",
                json={
                    "document_id": 1,
                    "audit_type": "deviation",
                },
            )
            assert resp.status_code == 503

    async def test_run_agent_audit_document_not_found(self, client: AsyncClient):
        """Run audit with nonexistent document."""
        with patch("app.api.agent_audit.is_agent_available", return_value=True):
            resp = await client.post(
                "/api/agent-audit/run",
                json={
                    "document_id": 99999,
                    "audit_type": "deviation",
                },
            )
            assert resp.status_code == 404

    async def test_run_agent_audit_document_not_processed(self, client: AsyncClient, db_session):
        """Run audit with unprocessed document."""
        doc = Document(
            filename="unprocessed.txt",
            file_path="/tmp/unprocessed.txt",
            file_type="txt",
            file_size=100,
            process_status=DocumentStatus.UPLOADED,
        )
        db_session.add(doc)
        await db_session.commit()
        await db_session.refresh(doc)

        with patch("app.api.agent_audit.is_agent_available", return_value=True):
            resp = await client.post(
                "/api/agent-audit/run",
                json={
                    "document_id": doc.id,
                    "audit_type": "deviation",
                },
            )
            assert resp.status_code == 400

    async def test_run_agent_audit_invalid_type(self, client: AsyncClient, db_session):
        """Run audit with invalid audit type."""
        doc = Document(
            filename="processed.txt",
            file_path="/tmp/processed.txt",
            file_type="txt",
            file_size=100,
            process_status=DocumentStatus.PROCESSED,
        )
        db_session.add(doc)
        await db_session.commit()
        await db_session.refresh(doc)

        with patch("app.api.agent_audit.is_agent_available", return_value=True):
            resp = await client.post(
                "/api/agent-audit/run",
                json={
                    "document_id": doc.id,
                    "audit_type": "invalid_type",
                },
            )
            assert resp.status_code == 400

    async def test_run_agent_audit_success(self, client: AsyncClient, db_session):
        """Run audit successfully."""
        doc = Document(
            filename="success.txt",
            file_path="/tmp/success.txt",
            file_type="txt",
            file_size=100,
            process_status=DocumentStatus.PROCESSED,
        )
        db_session.add(doc)
        await db_session.commit()
        await db_session.refresh(doc)

        with patch("app.api.agent_audit.is_agent_available", return_value=True):
            resp = await client.post(
                "/api/agent-audit/run",
                json={
                    "document_id": doc.id,
                    "audit_type": "deviation",
                    "focus": "GMP compliance",
                },
            )
            assert resp.status_code == 200
            data = resp.json()
            assert "task_id" in data
            assert data["status"] == "pending"

    async def test_run_agent_audit_sop_type(self, client: AsyncClient, db_session):
        """Run audit with SOP type."""
        doc = Document(
            filename="sop.txt",
            file_path="/tmp/sop.txt",
            file_type="txt",
            file_size=100,
            process_status=DocumentStatus.PROCESSED,
        )
        db_session.add(doc)
        await db_session.commit()
        await db_session.refresh(doc)

        with patch("app.api.agent_audit.is_agent_available", return_value=True):
            resp = await client.post(
                "/api/agent-audit/run",
                json={
                    "document_id": doc.id,
                    "audit_type": "sop",
                },
            )
            assert resp.status_code == 200

    async def test_run_agent_audit_change_control_type(self, client: AsyncClient, db_session):
        """Run audit with change_control type."""
        doc = Document(
            filename="change.txt",
            file_path="/tmp/change.txt",
            file_type="txt",
            file_size=100,
            process_status=DocumentStatus.PROCESSED,
        )
        db_session.add(doc)
        await db_session.commit()
        await db_session.refresh(doc)

        with patch("app.api.agent_audit.is_agent_available", return_value=True):
            resp = await client.post(
                "/api/agent-audit/run",
                json={
                    "document_id": doc.id,
                    "audit_type": "change_control",
                },
            )
            assert resp.status_code == 200


@pytest.mark.asyncio
class TestAgentAuditStatus:
    """Test GET /agent-audit/status/{task_id} endpoint."""

    async def test_get_status_not_found(self, client: AsyncClient):
        """Get status for nonexistent task."""
        resp = await client.get("/api/agent-audit/status/99999")
        assert resp.status_code == 404

    async def test_get_status_success(self, client: AsyncClient, db_session):
        """Get status for existing task."""
        task = AuditTask(
            task_name="Status Task",
            task_type=TaskType.DEVIATION_ANALYSIS,
            status=TaskStatus.PENDING,
        )
        db_session.add(task)
        await db_session.commit()
        await db_session.refresh(task)

        resp = await client.get(f"/api/agent-audit/status/{task.id}")
        assert resp.status_code == 200
        data = resp.json()
        assert "task_id" in data
        assert "status" in data
