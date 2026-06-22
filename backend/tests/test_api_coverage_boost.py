"""Comprehensive API coverage boost tests for backend.

Targets all uncovered code paths across:
- app/api/audit.py
- app/api/agent_audit.py
- app/api/reports.py
- app/api/alerts.py
- app/api/documents.py
"""

import asyncio
import json
import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit_task import AuditTask, TaskStatus, TaskType
from app.models.configuration import Configuration
from app.models.document import Document, DocumentStatus
from app.models.finding import Finding, FindingStatus, FindingType, SeverityLevel
from app.models.report import Report, ReportType
from app.models.risk_alert import AlertLevel, AlertStatus, RiskAlert

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _create_task(db: AsyncSession, **kwargs) -> AuditTask:
    defaults = {
        "task_name": "Test Task",
        "task_type": TaskType.DEVIATION_ANALYSIS,
        "status": TaskStatus.PENDING,
    }
    defaults.update(kwargs)
    task = AuditTask(**defaults)
    db.add(task)
    await db.commit()
    await db.refresh(task)
    return task


async def _create_doc(db: AsyncSession, **kwargs) -> Document:
    defaults = {
        "filename": "test.pdf",
        "file_path": "/tmp/test.pdf",
        "file_type": "pdf",
        "file_size": 100,
        "process_status": DocumentStatus.UPLOADED,
    }
    defaults.update(kwargs)
    doc = Document(**defaults)
    db.add(doc)
    await db.commit()
    await db.refresh(doc)
    return doc


async def _create_finding(db: AsyncSession, task_id: int, **kwargs) -> Finding:
    defaults = {
        "task_id": task_id,
        "finding_type": FindingType.COMPLIANCE_RISK,
        "severity": SeverityLevel.HIGH,
        "title": "Test Finding",
        "description": "Test description",
    }
    defaults.update(kwargs)
    finding = Finding(**defaults)
    db.add(finding)
    await db.commit()
    await db.refresh(finding)
    return finding


async def _create_alert(db: AsyncSession, finding_id: int, **kwargs) -> RiskAlert:
    defaults = {
        "finding_id": finding_id,
        "alert_level": AlertLevel.CRITICAL,
        "status": AlertStatus.ACTIVE,
    }
    defaults.update(kwargs)
    alert = RiskAlert(**defaults)
    db.add(alert)
    await db.commit()
    await db.refresh(alert)
    return alert


# ===========================================================================
# api/audit.py - Create Task
# ===========================================================================


@pytest.mark.asyncio
class TestAuditCreateTask:
    async def test_create_task_success(self, client: AsyncClient, db_session):
        doc = await _create_doc(db_session, process_status=DocumentStatus.PROCESSED)
        resp = await client.post(
            "/api/audit/tasks",
            json={
                "task_name": "New Task",
                "task_type": "deviation_analysis",
                "document_ids": [doc.id],
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["task_name"] == "New Task"
        assert data["status"] == "pending"

    async def test_create_task_invalid_type(self, client: AsyncClient):
        resp = await client.post(
            "/api/audit/tasks",
            json={
                "task_name": "Bad Task",
                "task_type": "invalid_type",
                "document_ids": [],
            },
        )
        assert resp.status_code == 422

    async def test_create_task_with_sop_type(self, client: AsyncClient, db_session):
        doc = await _create_doc(db_session, process_status=DocumentStatus.PROCESSED)
        resp = await client.post(
            "/api/audit/tasks",
            json={
                "task_name": "SOP Task",
                "task_type": "sop_compliance",
                "document_ids": [doc.id],
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["task_name"] == "SOP Task"

    async def test_create_task_empty_documents(self, client: AsyncClient):
        resp = await client.post(
            "/api/audit/tasks",
            json={
                "task_name": "Empty Doc Task",
                "task_type": "deviation_analysis",
                "document_ids": [],
            },
        )
        assert resp.status_code == 200


# ===========================================================================
# api/audit.py - List Tasks (with batch findings/reports loading)
# ===========================================================================


@pytest.mark.asyncio
class TestAuditListTasks:
    async def test_list_empty(self, client: AsyncClient):
        resp = await client.get("/api/audit/tasks")
        assert resp.status_code == 200
        data = resp.json()
        assert data["items"] == []
        assert data["total"] == 0

    async def test_list_with_pagination(self, client: AsyncClient, db_session):
        for i in range(5):
            await _create_task(db_session, task_name=f"Task {i}")
        resp = await client.get("/api/audit/tasks", params={"page": 1, "page_size": 2})
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["items"]) <= 2
        assert data["total"] == 5

    async def test_list_filter_by_status(self, client: AsyncClient, db_session):
        await _create_task(db_session, task_name="Pending", status=TaskStatus.PENDING)
        await _create_task(db_session, task_name="Running", status=TaskStatus.RUNNING)
        resp = await client.get("/api/audit/tasks", params={"status": "running"})
        assert resp.status_code == 200
        items = resp.json()["items"]
        assert all(t["status"] == "running" for t in items)

    async def test_list_with_findings_and_reports(self, client: AsyncClient, db_session):
        """Cover the batch-loading of findings count and report IDs."""
        task = await _create_task(db_session, status=TaskStatus.COMPLETED)
        await _create_finding(db_session, task.id, severity=SeverityLevel.HIGH)
        await _create_finding(db_session, task.id, severity=SeverityLevel.MEDIUM)
        report = Report(
            task_id=task.id,
            report_type=ReportType.FULL_REPORT,
            title="Report",
            content="Content",
        )
        db_session.add(report)
        await db_session.commit()

        resp = await client.get("/api/audit/tasks")
        assert resp.status_code == 200
        items = resp.json()["items"]
        assert len(items) >= 1
        # The item should include findings count and report info
        task_item = [t for t in items if t["id"] == task.id][0]
        assert task_item["findings_count"] == 2
        assert task_item["report_id"] is not None

    async def test_list_tasks_no_findings_no_reports(self, client: AsyncClient, db_session):
        """Tasks with no findings or reports should still list correctly."""
        await _create_task(db_session)
        resp = await client.get("/api/audit/tasks")
        assert resp.status_code == 200
        items = resp.json()["items"]
        assert len(items) == 1
        assert items[0]["findings_count"] == 0


# ===========================================================================
# api/audit.py - Get Task
# ===========================================================================


@pytest.mark.asyncio
class TestAuditGetTask:
    async def test_get_task_success(self, client: AsyncClient, db_session):
        doc = await _create_doc(db_session, process_status=DocumentStatus.PROCESSED)
        task = await _create_task(db_session, document_ids=[doc.id])
        resp = await client.get(f"/api/audit/tasks/{task.id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["task_name"] == "Test Task"
        assert data["document_ids"] == [doc.id]

    async def test_get_task_not_found(self, client: AsyncClient):
        resp = await client.get("/api/audit/tasks/99999")
        assert resp.status_code == 404

    async def test_get_task_no_documents(self, client: AsyncClient, db_session):
        task = await _create_task(db_session, document_ids=None)
        resp = await client.get(f"/api/audit/tasks/{task.id}")
        assert resp.status_code == 200
        assert resp.json()["document_ids"] == []


# ===========================================================================
# api/audit.py - Run Task
# ===========================================================================


@pytest.mark.asyncio
class TestAuditRunTask:
    async def test_run_task_not_found(self, client: AsyncClient):
        resp = await client.post("/api/audit/tasks/99999/run")
        assert resp.status_code in (400, 404)

    async def test_run_task_agent_unavailable(self, client: AsyncClient, db_session):
        task = await _create_task(db_session)
        with patch("app.api.audit.is_agent_available", return_value=False):
            resp = await client.post(f"/api/audit/tasks/{task.id}/run")
            assert resp.status_code == 503

    async def test_run_task_no_llm_configured(self, client: AsyncClient, db_session):
        task = await _create_task(db_session)
        with patch("app.api.audit.is_agent_available", return_value=True):
            mock_engine = MagicMock()
            mock_engine.adapters = {}
            with patch("app.services.llm_engine.get_llm_engine", return_value=mock_engine):
                resp = await client.post(f"/api/audit/tasks/{task.id}/run")
                assert resp.status_code == 400
                assert "LLM" in resp.json()["detail"] or "llm" in resp.json()["detail"].lower()

    async def test_run_task_already_running(self, client: AsyncClient, db_session):
        task = await _create_task(db_session, status=TaskStatus.RUNNING)
        with patch("app.api.audit.is_agent_available", return_value=True):
            mock_engine = MagicMock()
            mock_engine.adapters = {"test": MagicMock()}
            with patch("app.services.llm_engine.get_llm_engine", return_value=mock_engine):
                resp = await client.post(f"/api/audit/tasks/{task.id}/run")
                assert resp.status_code == 400
                assert "运行中" in resp.json()["detail"]

    async def test_run_task_document_not_found(self, client: AsyncClient, db_session):
        task = await _create_task(db_session, document_ids=[99999])
        with patch("app.api.audit.is_agent_available", return_value=True):
            mock_engine = MagicMock()
            mock_engine.adapters = {"test": MagicMock()}
            with patch("app.services.llm_engine.get_llm_engine", return_value=mock_engine):
                resp = await client.post(f"/api/audit/tasks/{task.id}/run")
                assert resp.status_code == 400
                assert "文档 99999 不存在" in resp.json()["detail"]

    async def test_run_task_document_not_processed(self, client: AsyncClient, db_session):
        doc = await _create_doc(db_session, process_status=DocumentStatus.UPLOADED)
        task = await _create_task(db_session, document_ids=[doc.id])
        with patch("app.api.audit.is_agent_available", return_value=True):
            mock_engine = MagicMock()
            mock_engine.adapters = {"test": MagicMock()}
            with patch("app.services.llm_engine.get_llm_engine", return_value=mock_engine):
                resp = await client.post(f"/api/audit/tasks/{task.id}/run")
                assert resp.status_code == 400
                assert "未处理" in resp.json()["detail"]

    async def test_run_task_success(self, client: AsyncClient, db_session):
        doc = await _create_doc(db_session, process_status=DocumentStatus.PROCESSED)
        task = await _create_task(db_session, document_ids=[doc.id])

        mock_runner = MagicMock()
        mock_factory = MagicMock(return_value=mock_runner)

        from app.main import app as fastapi_app

        original_factory = fastapi_app.state.task_runner_factory
        fastapi_app.state.task_runner_factory = mock_factory
        try:
            with patch("app.api.audit.is_agent_available", return_value=True):
                mock_engine = MagicMock()
                mock_engine.adapters = {"test": MagicMock()}
                with patch("app.services.llm_engine.get_llm_engine", return_value=mock_engine):
                    resp = await client.post(f"/api/audit/tasks/{task.id}/run")
            assert resp.status_code == 200
            data = resp.json()
            assert data["status"] == "pending"
            assert data["task_id"] == task.id
            mock_runner.enqueue.assert_called_once_with(task.id)
        finally:
            fastapi_app.state.task_runner_factory = original_factory

    async def test_run_task_enqueue_runtime_error(self, client: AsyncClient, db_session):
        doc = await _create_doc(db_session, process_status=DocumentStatus.PROCESSED)
        task = await _create_task(db_session, document_ids=[doc.id])

        mock_runner = MagicMock()
        mock_runner.enqueue.side_effect = RuntimeError("Runner is shut down")
        mock_factory = MagicMock(return_value=mock_runner)

        from app.main import app as fastapi_app

        original_factory = fastapi_app.state.task_runner_factory
        fastapi_app.state.task_runner_factory = mock_factory
        try:
            mock_engine = MagicMock()
            mock_engine.adapters = {"test": MagicMock()}
            with (
                patch("app.api.audit.is_agent_available", return_value=True),
                patch("app.services.llm_engine.get_llm_engine", return_value=mock_engine),
            ):
                resp = await client.post(f"/api/audit/tasks/{task.id}/run")
            assert resp.status_code == 503
        finally:
            fastapi_app.state.task_runner_factory = original_factory


# ===========================================================================
# api/audit.py - Cancel Task
# ===========================================================================


@pytest.mark.asyncio
class TestAuditCancelTask:
    async def test_cancel_task_not_found(self, client: AsyncClient):
        resp = await client.post("/api/audit/tasks/99999/cancel")
        assert resp.status_code == 404

    async def test_cancel_task_not_running(self, client: AsyncClient, db_session):
        task = await _create_task(db_session, status=TaskStatus.PENDING)
        resp = await client.post(f"/api/audit/tasks/{task.id}/cancel")
        assert resp.status_code == 400
        assert "not running" in resp.json()["detail"].lower()

    async def test_cancel_task_success(self, client: AsyncClient, db_session):
        task = await _create_task(db_session, status=TaskStatus.RUNNING)

        mock_runner = MagicMock()
        mock_runner.cancel = AsyncMock(return_value=True)
        mock_factory = MagicMock(return_value=mock_runner)

        from app.main import app as fastapi_app

        original_factory = fastapi_app.state.task_runner_factory
        fastapi_app.state.task_runner_factory = mock_factory
        try:
            resp = await client.post(f"/api/audit/tasks/{task.id}/cancel")
            assert resp.status_code == 200
            assert resp.json()["status"] == "cancelled"
        finally:
            fastapi_app.state.task_runner_factory = original_factory

    async def test_cancel_task_could_not_cancel(self, client: AsyncClient, db_session):
        task = await _create_task(db_session, status=TaskStatus.RUNNING)

        mock_runner = MagicMock()
        mock_runner.cancel = AsyncMock(return_value=False)
        mock_factory = MagicMock(return_value=mock_runner)

        from app.main import app as fastapi_app

        original_factory = fastapi_app.state.task_runner_factory
        fastapi_app.state.task_runner_factory = mock_factory
        try:
            resp = await client.post(f"/api/audit/tasks/{task.id}/cancel")
            assert resp.status_code == 400
            assert "could not be cancelled" in resp.json()["detail"].lower()
        finally:
            fastapi_app.state.task_runner_factory = original_factory


# ===========================================================================
# api/audit.py - Approve Task
# ===========================================================================


@pytest.mark.asyncio
class TestAuditApproveTask:
    async def test_approve_task_not_found(self, client: AsyncClient):
        resp = await client.post("/api/audit/tasks/99999/approve", json={"comment": "ok"})
        assert resp.status_code == 404

    async def test_approve_task_not_in_review(self, client: AsyncClient, db_session):
        task = await _create_task(db_session, status=TaskStatus.PENDING)
        resp = await client.post(f"/api/audit/tasks/{task.id}/approve", json={"comment": "ok"})
        assert resp.status_code == 400

    async def test_approve_task_success(self, client: AsyncClient, db_session):
        task = await _create_task(db_session, status=TaskStatus.AWAITING_REVIEW)
        resp = await client.post(f"/api/audit/tasks/{task.id}/approve", json={"comment": "Looks good"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "approved"
        assert data["task_id"] == task.id

    async def test_approve_task_with_event_bus(self, client: AsyncClient, db_session):
        """Test approve with EventBus notification."""
        task = await _create_task(db_session, status=TaskStatus.AWAITING_REVIEW)

        mock_event_bus = MagicMock()
        mock_event_bus.publish = AsyncMock()
        mock_event_bus.publish_done = AsyncMock()

        from app.main import app as fastapi_app

        original_bus = getattr(fastapi_app.state, "event_bus", None)
        fastapi_app.state.event_bus = mock_event_bus
        try:
            resp = await client.post(
                f"/api/audit/tasks/{task.id}/approve",
                json={"comment": "Approved with event bus"},
            )
            assert resp.status_code == 200
        finally:
            if original_bus:
                fastapi_app.state.event_bus = original_bus

    async def test_approve_task_with_feishu_notification(self, client: AsyncClient, db_session):
        """Test approve with Feishu notification configured."""
        task = await _create_task(db_session, status=TaskStatus.AWAITING_REVIEW)
        await _create_finding(db_session, task.id, severity=SeverityLevel.HIGH)

        with (
            patch("app.services.notification.is_feishu_configured", return_value=True),
            patch("app.services.notification.notify_audit_complete", new_callable=AsyncMock) as mock_notify,
        ):
            resp = await client.post(
                f"/api/audit/tasks/{task.id}/approve",
                json={"comment": "Approved with Feishu"},
            )
            assert resp.status_code == 200
            mock_notify.assert_called_once()

    async def test_approve_task_feishu_notification_failure(self, client: AsyncClient, db_session):
        """Feishu notification failure should not break the approve flow."""
        task = await _create_task(db_session, status=TaskStatus.AWAITING_REVIEW)

        with (
            patch("app.services.notification.is_feishu_configured", return_value=True),
            patch(
                "app.services.notification.notify_audit_complete",
                new_callable=AsyncMock,
                side_effect=Exception("Network error"),
            ),
        ):
            resp = await client.post(
                f"/api/audit/tasks/{task.id}/approve",
                json={"comment": "Approved despite Feishu error"},
            )
            assert resp.status_code == 200


# ===========================================================================
# api/audit.py - Reject Task
# ===========================================================================


@pytest.mark.asyncio
class TestAuditRejectTask:
    async def test_reject_task_not_found(self, client: AsyncClient):
        resp = await client.post("/api/audit/tasks/99999/reject", json={"comment": "bad"})
        assert resp.status_code == 404

    async def test_reject_task_not_in_review(self, client: AsyncClient, db_session):
        task = await _create_task(db_session, status=TaskStatus.PENDING)
        resp = await client.post(f"/api/audit/tasks/{task.id}/reject", json={"comment": "bad"})
        assert resp.status_code == 400

    async def test_reject_task_success(self, client: AsyncClient, db_session):
        task = await _create_task(db_session, status=TaskStatus.AWAITING_REVIEW)
        resp = await client.post(f"/api/audit/tasks/{task.id}/reject", json={"comment": "Needs work"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "rejected"
        assert data["task_id"] == task.id


# ===========================================================================
# api/audit.py - Findings
# ===========================================================================


@pytest.mark.asyncio
class TestAuditFindings:
    async def test_get_findings_empty(self, client: AsyncClient, db_session):
        task = await _create_task(db_session, status=TaskStatus.COMPLETED)
        resp = await client.get(f"/api/audit/tasks/{task.id}/findings")
        assert resp.status_code == 200
        assert resp.json() == []

    async def test_get_findings_with_data(self, client: AsyncClient, db_session):
        task = await _create_task(db_session, status=TaskStatus.COMPLETED)
        await _create_finding(
            db_session,
            task.id,
            evidence="Evidence text",
            suggestion="Fix suggestion",
            location="Section 3.1",
            regulation_ref="GMP 2010 §42",
        )
        resp = await client.get(f"/api/audit/tasks/{task.id}/findings")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["title"] == "Test Finding"
        assert data[0]["evidence"] == "Evidence text"
        assert data[0]["suggestion"] == "Fix suggestion"
        assert data[0]["location"] == "Section 3.1"
        assert data[0]["regulation_ref"] == "GMP 2010 §42"
        assert data[0]["status"] == "pending"
        assert data[0]["reviewer_comment"] is None
        assert data[0]["reviewed_at"] is None

    async def test_get_findings_with_review_info(self, client: AsyncClient, db_session):
        task = await _create_task(db_session, status=TaskStatus.COMPLETED)
        finding = await _create_finding(db_session, task.id)
        # Simulate a reviewed finding
        from datetime import UTC, datetime

        finding.status = FindingStatus.APPROVED
        finding.reviewer_comment = "Looks correct"
        finding.reviewed_at = datetime.now(UTC)
        await db_session.commit()

        resp = await client.get(f"/api/audit/tasks/{task.id}/findings")
        assert resp.status_code == 200
        data = resp.json()
        assert data[0]["status"] == "approved"
        assert data[0]["reviewer_comment"] == "Looks correct"
        assert data[0]["reviewed_at"] is not None


# ===========================================================================
# api/audit.py - Approve/Reject Finding
# ===========================================================================


@pytest.mark.asyncio
class TestFindingApproval:
    async def test_approve_finding_not_found(self, client: AsyncClient):
        resp = await client.post("/api/audit/findings/99999/approve", json={"comment": "ok"})
        assert resp.status_code == 404

    async def test_reject_finding_not_found(self, client: AsyncClient):
        resp = await client.post("/api/audit/findings/99999/reject", json={"comment": "bad"})
        assert resp.status_code == 404

    async def test_approve_finding_success(self, client: AsyncClient, db_session):
        task = await _create_task(db_session)
        finding = await _create_finding(db_session, task.id)
        resp = await client.post(
            f"/api/audit/findings/{finding.id}/approve",
            json={"comment": "approved"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "approved"

    async def test_approve_finding_no_body(self, client: AsyncClient, db_session):
        """Approve finding without body should work."""
        task = await _create_task(db_session)
        finding = await _create_finding(db_session, task.id)
        resp = await client.post(f"/api/audit/findings/{finding.id}/approve")
        assert resp.status_code == 200
        assert resp.json()["status"] == "approved"

    async def test_reject_finding_success(self, client: AsyncClient, db_session):
        task = await _create_task(db_session)
        finding = await _create_finding(db_session, task.id)
        resp = await client.post(
            f"/api/audit/findings/{finding.id}/reject",
            json={"comment": "rejected"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "rejected"

    async def test_reject_finding_no_body(self, client: AsyncClient, db_session):
        """Reject finding without body should work."""
        task = await _create_task(db_session)
        finding = await _create_finding(db_session, task.id)
        resp = await client.post(f"/api/audit/findings/{finding.id}/reject")
        assert resp.status_code == 200
        assert resp.json()["status"] == "rejected"


# ===========================================================================
# api/audit.py - Risk Assessment
# ===========================================================================


@pytest.mark.asyncio
class TestAuditRiskAssessment:
    async def test_get_risk_no_findings(self, client: AsyncClient, db_session):
        task = await _create_task(db_session, status=TaskStatus.COMPLETED)
        resp = await client.get(f"/api/audit/tasks/{task.id}/risk")
        assert resp.status_code == 200
        data = resp.json()
        assert "risk_level" in data
        assert data["total_findings"] == 0

    async def test_get_risk_with_findings(self, client: AsyncClient, db_session):
        task = await _create_task(db_session, status=TaskStatus.COMPLETED)
        await _create_finding(db_session, task.id, severity=SeverityLevel.HIGH)
        await _create_finding(db_session, task.id, severity=SeverityLevel.MEDIUM)
        await _create_finding(db_session, task.id, severity=SeverityLevel.LOW)
        resp = await client.get(f"/api/audit/tasks/{task.id}/risk")
        assert resp.status_code == 200
        data = resp.json()
        assert data["risk_level"] == "high"
        assert data["total_findings"] == 3

    async def test_get_risk_only_medium(self, client: AsyncClient, db_session):
        task = await _create_task(db_session, status=TaskStatus.COMPLETED)
        await _create_finding(db_session, task.id, severity=SeverityLevel.MEDIUM)
        resp = await client.get(f"/api/audit/tasks/{task.id}/risk")
        assert resp.status_code == 200
        assert resp.json()["risk_level"] == "medium"


# ===========================================================================
# api/audit.py - Dashboard
# ===========================================================================


@pytest.mark.asyncio
class TestAuditDashboard:
    async def test_dashboard_empty(self, client: AsyncClient):
        resp = await client.get("/api/audit/dashboard")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_tasks"] == 0
        assert data["total_findings"] == 0
        assert "task_counts" in data
        assert "severity_counts" in data

    async def test_dashboard_with_data(self, client: AsyncClient, db_session):
        task1 = await _create_task(db_session, task_name="T1", status=TaskStatus.COMPLETED)
        await _create_task(db_session, task_name="T2", status=TaskStatus.PENDING)
        await _create_finding(db_session, task1.id, severity=SeverityLevel.HIGH)
        await _create_finding(db_session, task1.id, severity=SeverityLevel.MEDIUM)

        resp = await client.get("/api/audit/dashboard")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_tasks"] == 2
        assert data["total_findings"] == 2
        assert data["task_counts"]["completed"] == 1
        assert data["task_counts"]["pending"] == 1
        assert data["severity_counts"]["high"] == 1
        assert data["severity_counts"]["medium"] == 1


# ===========================================================================
# api/audit.py - SSE Streams
# ===========================================================================


@pytest.mark.asyncio
class TestAuditStreams:
    async def test_stream_task_not_found(self, client: AsyncClient, db_session):
        resp = await client.get("/api/audit/tasks/99999/stream")
        assert resp.status_code == 404

    async def test_stream_task_terminal_status(self, client: AsyncClient, db_session):
        """Stream for a completed task should send done immediately."""
        task = await _create_task(db_session, status=TaskStatus.COMPLETED)
        resp = await client.get(f"/api/audit/tasks/{task.id}/stream")
        assert resp.status_code == 200
        assert "text/event-stream" in resp.headers["content-type"]

    async def test_stream_task_awaiting_review(self, client: AsyncClient, db_session):
        """Stream for an awaiting_review task should send done immediately."""
        task = await _create_task(db_session, status=TaskStatus.AWAITING_REVIEW)
        resp = await client.get(f"/api/audit/tasks/{task.id}/stream")
        assert resp.status_code == 200
        assert "text/event-stream" in resp.headers["content-type"]

    async def test_stream_task_failed(self, client: AsyncClient, db_session):
        """Stream for a failed task should send done immediately."""
        task = await _create_task(db_session, status=TaskStatus.FAILED)
        resp = await client.get(f"/api/audit/tasks/{task.id}/stream")
        assert resp.status_code == 200
        assert "text/event-stream" in resp.headers["content-type"]

    async def test_stream_task_rejected(self, client: AsyncClient, db_session):
        """Stream for a rejected task should send done immediately."""
        task = await _create_task(db_session, status=TaskStatus.REJECTED)
        resp = await client.get(f"/api/audit/tasks/{task.id}/stream")
        assert resp.status_code == 200
        assert "text/event-stream" in resp.headers["content-type"]

    async def test_stream_task_with_history(self, client: AsyncClient, db_session):
        """Stream should replay historical events from task config."""
        task = await _create_task(db_session, status=TaskStatus.COMPLETED)
        task.config = {
            "execution": {
                "events": [
                    {"time": "2025-01-01T00:00:00", "stage": "queued", "level": "info", "message": "Task queued"},
                ],
                "thinking_events": [
                    {"agent": "regulation_expert", "thinking": "Analyzing..."},
                ],
            }
        }
        await db_session.commit()

        resp = await client.get(f"/api/audit/tasks/{task.id}/stream")
        assert resp.status_code == 200
        body = resp.text
        assert "event" in body

    async def test_stream_task_with_empty_history(self, client: AsyncClient, db_session):
        """Stream with empty config history should still work."""
        task = await _create_task(db_session, status=TaskStatus.COMPLETED)
        task.config = {"execution": {}}
        await db_session.commit()

        resp = await client.get(f"/api/audit/tasks/{task.id}/stream")
        assert resp.status_code == 200

    async def test_stream_task_with_none_config(self, client: AsyncClient, db_session):
        """Stream with None config should still work."""
        task = await _create_task(db_session, status=TaskStatus.COMPLETED)
        # config is already None by default
        resp = await client.get(f"/api/audit/tasks/{task.id}/stream")
        assert resp.status_code == 200

    async def test_stream_all_tasks_endpoint_exists(self, client: AsyncClient, db_session):
        """Test the global task stream endpoint structure.

        Note: stream_all_tasks uses get_db_session() (not dependency-injected get_db)
        and runs an infinite poll loop, so full integration testing is impractical.
        """
        pass


# ===========================================================================
# api/audit.py - Memory
# ===========================================================================


@pytest.mark.asyncio
class TestAuditMemory:
    async def test_get_memory(self, client: AsyncClient):
        with patch("app.services.memory.load_memory", return_value=[]):
            resp = await client.get("/api/audit/memory")
            assert resp.status_code == 200
            assert isinstance(resp.json(), list)

    async def test_get_memory_with_limit(self, client: AsyncClient):
        with patch("app.services.memory.load_memory", return_value=[{"task": 1}]):
            resp = await client.get("/api/audit/memory", params={"limit": 10})
            assert resp.status_code == 200

    async def test_get_memory_with_data(self, client: AsyncClient):
        mock_data = [
            {"task_name": "Old Task", "findings_count": 3, "risk_level": "high"},
            {"task_name": "New Task", "findings_count": 1, "risk_level": "low"},
        ]
        with patch("app.services.memory.load_memory", return_value=mock_data):
            resp = await client.get("/api/audit/memory")
            assert resp.status_code == 200
            assert len(resp.json()) == 2


# ===========================================================================
# api/audit.py - Estimate
# ===========================================================================


@pytest.mark.asyncio
class TestAuditEstimate:
    async def test_estimate_no_documents(self, client: AsyncClient):
        resp = await client.post("/api/audit/estimate", json={"document_ids": []})
        assert resp.status_code == 404
        assert "No documents found" in resp.json()["detail"]

    async def test_estimate_small_document(self, client: AsyncClient, db_session):
        doc = await _create_doc(db_session, content_text="A" * 1000, process_status=DocumentStatus.PROCESSED)
        resp = await client.post("/api/audit/estimate", json={"document_ids": [doc.id]})
        assert resp.status_code == 200
        data = resp.json()
        assert data["document_count"] == 1
        assert data["estimated_llm_calls"] > 0
        assert data["estimated_input_tokens"] > 0
        assert data["estimated_output_tokens"] > 0
        assert data["estimated_duration_seconds"] > 0

    async def test_estimate_large_document(self, client: AsyncClient, db_session):
        """Document exceeding STUFF_LIMIT triggers map-reduce."""
        large_content = "A" * 70000  # > STUFF_LIMIT (60000)
        doc = await _create_doc(db_session, content_text=large_content, process_status=DocumentStatus.PROCESSED)
        resp = await client.post("/api/audit/estimate", json={"document_ids": [doc.id]})
        assert resp.status_code == 200
        data = resp.json()
        # For large doc: reg_calls=2, risk_calls=ceil(70000/8000)=9, report_calls=1 = 12
        assert data["estimated_llm_calls"] == 12

    async def test_estimate_multiple_documents(self, client: AsyncClient, db_session):
        doc1 = await _create_doc(
            db_session, filename="d1.pdf", content_text="A" * 500, process_status=DocumentStatus.PROCESSED
        )
        doc2 = await _create_doc(
            db_session, filename="d2.pdf", content_text="B" * 500, process_status=DocumentStatus.PROCESSED
        )
        resp = await client.post("/api/audit/estimate", json={"document_ids": [doc1.id, doc2.id]})
        assert resp.status_code == 200
        data = resp.json()
        assert data["document_count"] == 2

    async def test_estimate_nonexistent_documents(self, client: AsyncClient):
        resp = await client.post("/api/audit/estimate", json={"document_ids": [99999]})
        assert resp.status_code == 404

    async def test_estimate_document_no_content(self, client: AsyncClient, db_session):
        """Document with no content_text should still work."""
        doc = await _create_doc(db_session, content_text=None, process_status=DocumentStatus.PROCESSED)
        resp = await client.post("/api/audit/estimate", json={"document_ids": [doc.id]})
        assert resp.status_code == 200
        data = resp.json()
        assert data["document_count"] == 1


# ===========================================================================
# api/agent_audit.py
# ===========================================================================


@pytest.mark.asyncio
class TestAgentAudit:
    async def test_run_agent_audit_not_found(self, client: AsyncClient):
        resp = await client.post("/api/agent-audit/run", json={"document_id": 999, "audit_type": "deviation"})
        assert resp.status_code == 404

    async def test_run_agent_audit_not_processed(self, client: AsyncClient, db_session):
        doc = await _create_doc(db_session, process_status=DocumentStatus.UPLOADED)
        resp = await client.post(
            "/api/agent-audit/run",
            json={"document_id": doc.id, "audit_type": "deviation"},
        )
        assert resp.status_code == 400
        assert "未处理" in resp.json()["detail"]

    async def test_run_agent_audit_unavailable(self, client: AsyncClient, db_session):
        doc = await _create_doc(db_session, process_status=DocumentStatus.PROCESSED)
        with patch("app.api.agent_audit.is_agent_available", return_value=False):
            resp = await client.post(
                "/api/agent-audit/run",
                json={"document_id": doc.id, "audit_type": "deviation"},
            )
            assert resp.status_code == 503

    async def test_run_agent_audit_invalid_type(self, client: AsyncClient, db_session):
        doc = await _create_doc(db_session, process_status=DocumentStatus.PROCESSED)
        resp = await client.post(
            "/api/agent-audit/run",
            json={"document_id": doc.id, "audit_type": "invalid_type"},
        )
        assert resp.status_code == 400
        assert "无效" in resp.json()["detail"]

    async def test_run_agent_audit_deviation_success(self, client: AsyncClient, db_session):
        doc = await _create_doc(db_session, process_status=DocumentStatus.PROCESSED)
        mock_runner = MagicMock()
        mock_factory = MagicMock(return_value=mock_runner)

        from app.main import app as fastapi_app

        orig_factory = fastapi_app.state.task_runner_factory
        fastapi_app.state.task_runner_factory = mock_factory
        try:
            with patch("app.api.agent_audit.is_agent_available", return_value=True):
                resp = await client.post(
                    "/api/agent-audit/run",
                    json={"document_id": doc.id, "audit_type": "deviation"},
                )
            assert resp.status_code == 200
            data = resp.json()
            assert data["status"] == "pending"
            assert "task_id" in data
            mock_runner.enqueue.assert_called_once()
        finally:
            fastapi_app.state.task_runner_factory = orig_factory

    async def test_run_agent_audit_sop_success(self, client: AsyncClient, db_session):
        doc = await _create_doc(db_session, process_status=DocumentStatus.PROCESSED)
        mock_runner = MagicMock()
        mock_factory = MagicMock(return_value=mock_runner)

        from app.main import app as fastapi_app

        orig_factory = fastapi_app.state.task_runner_factory
        fastapi_app.state.task_runner_factory = mock_factory
        try:
            with patch("app.api.agent_audit.is_agent_available", return_value=True):
                resp = await client.post(
                    "/api/agent-audit/run",
                    json={"document_id": doc.id, "audit_type": "sop"},
                )
            assert resp.status_code == 200
        finally:
            fastapi_app.state.task_runner_factory = orig_factory

    async def test_run_agent_audit_change_control_success(self, client: AsyncClient, db_session):
        doc = await _create_doc(db_session, process_status=DocumentStatus.PROCESSED)
        mock_runner = MagicMock()
        mock_factory = MagicMock(return_value=mock_runner)

        from app.main import app as fastapi_app

        orig_factory = fastapi_app.state.task_runner_factory
        fastapi_app.state.task_runner_factory = mock_factory
        try:
            with patch("app.api.agent_audit.is_agent_available", return_value=True):
                resp = await client.post(
                    "/api/agent-audit/run",
                    json={"document_id": doc.id, "audit_type": "change_control"},
                )
            assert resp.status_code == 200
        finally:
            fastapi_app.state.task_runner_factory = orig_factory

    async def test_run_agent_audit_with_focus(self, client: AsyncClient, db_session):
        doc = await _create_doc(db_session, process_status=DocumentStatus.PROCESSED)
        mock_runner = MagicMock()
        mock_factory = MagicMock(return_value=mock_runner)

        from app.main import app as fastapi_app

        orig_factory = fastapi_app.state.task_runner_factory
        fastapi_app.state.task_runner_factory = mock_factory
        try:
            with patch("app.api.agent_audit.is_agent_available", return_value=True):
                resp = await client.post(
                    "/api/agent-audit/run",
                    json={"document_id": doc.id, "audit_type": "deviation", "focus": "数据完整性"},
                )
            assert resp.status_code == 200
        finally:
            fastapi_app.state.task_runner_factory = orig_factory

    async def test_run_agent_audit_enqueue_error(self, client: AsyncClient, db_session):
        doc = await _create_doc(db_session, process_status=DocumentStatus.PROCESSED)
        mock_runner = MagicMock()
        mock_runner.enqueue.side_effect = RuntimeError("Runner shut down")
        mock_factory = MagicMock(return_value=mock_runner)

        from app.main import app as fastapi_app

        orig_factory = fastapi_app.state.task_runner_factory
        fastapi_app.state.task_runner_factory = mock_factory
        try:
            with patch("app.api.agent_audit.is_agent_available", return_value=True):
                resp = await client.post(
                    "/api/agent-audit/run",
                    json={"document_id": doc.id, "audit_type": "deviation"},
                )
            assert resp.status_code == 503
        finally:
            fastapi_app.state.task_runner_factory = orig_factory

    async def test_get_agent_audit_status_not_found(self, client: AsyncClient):
        resp = await client.get("/api/agent-audit/status/999")
        assert resp.status_code == 404

    async def test_get_agent_audit_status(self, client: AsyncClient, db_session):
        task = await _create_task(db_session, status=TaskStatus.RUNNING, progress=50)
        resp = await client.get(f"/api/agent-audit/status/{task.id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["task_name"] == "Test Task"
        assert data["status"] == "running"
        assert data["progress"] == 50

    async def test_get_agent_audit_status_completed(self, client: AsyncClient, db_session):
        task = await _create_task(db_session, status=TaskStatus.COMPLETED, progress=100)
        resp = await client.get(f"/api/agent-audit/status/{task.id}")
        assert resp.status_code == 200
        assert resp.json()["status"] == "completed"


# ===========================================================================
# api/reports.py - List Reports
# ===========================================================================


@pytest.mark.asyncio
class TestReportsList:
    async def test_list_reports_empty(self, client: AsyncClient):
        resp = await client.get("/api/reports/")
        assert resp.status_code == 200
        data = resp.json()
        assert data["items"] == []
        assert data["total"] == 0

    async def test_list_reports_with_data(self, client: AsyncClient, db_session):
        task = await _create_task(db_session, status=TaskStatus.COMPLETED)
        report = Report(
            task_id=task.id,
            report_type=ReportType.FULL_REPORT,
            title="Test Report",
            content="Content",
            report_metadata={"report_source": "agent_report_writer"},
        )
        db_session.add(report)
        await db_session.commit()

        resp = await client.get("/api/reports/")
        assert resp.status_code == 200
        items = resp.json()["items"]
        assert len(items) == 1
        assert items[0]["title"] == "Test Report"
        assert items[0]["report_type"] == "full_report"
        assert items[0]["report_metadata"]["report_source"] == "agent_report_writer"

    async def test_list_reports_with_task_filter(self, client: AsyncClient, db_session):
        t1 = await _create_task(db_session, task_name="T1", status=TaskStatus.COMPLETED)
        t2 = await _create_task(db_session, task_name="T2", status=TaskStatus.COMPLETED)
        db_session.add(Report(task_id=t1.id, report_type=ReportType.FULL_REPORT, title="R1", content="C1"))
        db_session.add(Report(task_id=t2.id, report_type=ReportType.FULL_REPORT, title="R2", content="C2"))
        await db_session.commit()

        resp = await client.get(f"/api/reports/?task_id={t1.id}")
        assert resp.status_code == 200
        items = resp.json()["items"]
        assert len(items) == 1
        assert items[0]["task_id"] == t1.id

    async def test_list_reports_pagination(self, client: AsyncClient, db_session):
        task = await _create_task(db_session, status=TaskStatus.COMPLETED)
        for i in range(5):
            db_session.add(
                Report(
                    task_id=task.id,
                    report_type=ReportType.FULL_REPORT,
                    title=f"R{i}",
                    content=f"C{i}",
                )
            )
        await db_session.commit()

        resp = await client.get("/api/reports/", params={"page": 1, "page_size": 2})
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["items"]) == 2
        assert data["total"] == 5
        assert data["page"] == 1
        assert data["page_size"] == 2

    async def test_list_reports_created_at_format(self, client: AsyncClient, db_session):
        """Verify created_at is ISO formatted."""
        task = await _create_task(db_session, status=TaskStatus.COMPLETED)
        db_session.add(Report(task_id=task.id, report_type=ReportType.FULL_REPORT, title="R", content="C"))
        await db_session.commit()

        resp = await client.get("/api/reports/")
        items = resp.json()["items"]
        assert len(items) == 1
        assert items[0]["created_at"] is not None
        # Should be ISO format
        assert "T" in items[0]["created_at"]


# ===========================================================================
# api/reports.py - Get Report
# ===========================================================================


@pytest.mark.asyncio
class TestReportGet:
    async def test_get_report_not_found(self, client: AsyncClient):
        resp = await client.get("/api/reports/999")
        assert resp.status_code == 404

    async def test_get_report_detail(self, client: AsyncClient, db_session):
        report = Report(
            task_id=1,
            report_type=ReportType.FULL_REPORT,
            title="Detail Report",
            content="Detailed content",
            report_metadata={"report_mode": "single_document"},
        )
        db_session.add(report)
        await db_session.commit()
        await db_session.refresh(report)

        resp = await client.get(f"/api/reports/{report.id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["title"] == "Detail Report"
        assert data["content"] == "Detailed content"
        assert data["report_type"] == "full_report"
        assert data["report_metadata"]["report_mode"] == "single_document"
        assert data["created_at"] is not None

    async def test_get_report_empty_content(self, client: AsyncClient, db_session):
        report = Report(
            task_id=1,
            report_type=ReportType.FULL_REPORT,
            title="Empty",
            content="",
        )
        db_session.add(report)
        await db_session.commit()
        await db_session.refresh(report)

        resp = await client.get(f"/api/reports/{report.id}")
        assert resp.status_code == 200
        assert resp.json()["content"] == ""


# ===========================================================================
# api/reports.py - Generate Report
# ===========================================================================


@pytest.mark.asyncio
class TestReportGenerate:
    async def test_generate_report_task_not_found(self, client: AsyncClient):
        resp = await client.post("/api/reports/generate/999")
        assert resp.status_code == 404

    async def test_generate_report_no_findings(self, client: AsyncClient, db_session):
        task = await _create_task(db_session, status=TaskStatus.COMPLETED)
        resp = await client.post(f"/api/reports/generate/{task.id}")
        assert resp.status_code == 400
        assert "暂无审计发现" in resp.json()["detail"]

    async def test_generate_report_success(self, client: AsyncClient, db_session):
        task = await _create_task(db_session, status=TaskStatus.COMPLETED)
        await _create_finding(db_session, task.id)

        mock_engine = MagicMock()
        mock_engine.generate_report = AsyncMock(return_value="# Audit Report\nFindings here")

        with patch("app.api.reports.get_llm_engine", return_value=mock_engine):
            resp = await client.post(f"/api/reports/generate/{task.id}")

        assert resp.status_code == 200
        data = resp.json()
        assert "id" in data
        assert data["content"] == "# Audit Report\nFindings here"
        assert data["report_metadata"]["report_source"] == "backend_llm_generate"
        assert data["report_metadata"]["findings_count"] == 1

    async def test_generate_report_llm_timeout(self, client: AsyncClient, db_session):
        task = await _create_task(db_session, status=TaskStatus.COMPLETED)
        await _create_finding(db_session, task.id)

        mock_engine = MagicMock()
        mock_engine.generate_report = AsyncMock(side_effect=asyncio.TimeoutError)

        with patch("app.api.reports.get_llm_engine", return_value=mock_engine):
            resp = await client.post(f"/api/reports/generate/{task.id}")

        assert resp.status_code == 504
        assert "超时" in resp.json()["detail"]

    async def test_generate_report_llm_value_error(self, client: AsyncClient, db_session):
        task = await _create_task(db_session, status=TaskStatus.COMPLETED)
        await _create_finding(db_session, task.id)

        mock_engine = MagicMock()
        mock_engine.generate_report = AsyncMock(side_effect=ValueError("No adapter"))

        with patch("app.api.reports.get_llm_engine", return_value=mock_engine):
            resp = await client.post(f"/api/reports/generate/{task.id}")

        assert resp.status_code == 503
        assert "不可用" in resp.json()["detail"]

    async def test_generate_report_llm_generic_error(self, client: AsyncClient, db_session):
        task = await _create_task(db_session, status=TaskStatus.COMPLETED)
        await _create_finding(db_session, task.id)

        mock_engine = MagicMock()
        mock_engine.generate_report = AsyncMock(side_effect=RuntimeError("Network error"))

        with patch("app.api.reports.get_llm_engine", return_value=mock_engine):
            resp = await client.post(f"/api/reports/generate/{task.id}")

        assert resp.status_code == 502
        assert "LLM" in resp.json()["detail"]

    async def test_generate_report_with_multiple_findings(self, client: AsyncClient, db_session):
        task = await _create_task(db_session, status=TaskStatus.COMPLETED)
        for sev in [SeverityLevel.HIGH, SeverityLevel.MEDIUM, SeverityLevel.LOW]:
            await _create_finding(db_session, task.id, severity=sev, title=f"Finding {sev.value}")

        mock_engine = MagicMock()
        mock_engine.generate_report = AsyncMock(return_value="# Multi-finding report")

        with patch("app.api.reports.get_llm_engine", return_value=mock_engine):
            resp = await client.post(f"/api/reports/generate/{task.id}")

        assert resp.status_code == 200
        data = resp.json()
        assert data["report_metadata"]["findings_count"] == 3
        assert data["report_metadata"]["task_type"] == "deviation_analysis"


# ===========================================================================
# api/reports.py - Export HTML
# ===========================================================================


@pytest.mark.asyncio
class TestReportExportHTML:
    async def test_export_html_not_found(self, client: AsyncClient):
        resp = await client.get("/api/reports/99999/export/html")
        assert resp.status_code == 404

    async def test_export_html_success(self, client: AsyncClient, db_session):
        report = Report(
            task_id=1,
            report_type=ReportType.FULL_REPORT,
            title="HTML Export",
            content="# Test\n\n**Bold** text.",
        )
        db_session.add(report)
        await db_session.commit()
        await db_session.refresh(report)

        resp = await client.get(f"/api/reports/{report.id}/export/html")
        assert resp.status_code == 200
        assert "text/html" in resp.headers["content-type"]
        assert "HTML Export" in resp.text
        assert "<strong>Bold</strong>" in resp.text

    async def test_export_html_with_table(self, client: AsyncClient, db_session):
        report = Report(
            task_id=1,
            report_type=ReportType.FULL_REPORT,
            title="Table Report",
            content="| A | B |\n|---|---|\n| 1 | 2 |",
        )
        db_session.add(report)
        await db_session.commit()
        await db_session.refresh(report)

        resp = await client.get(f"/api/reports/{report.id}/export/html")
        assert resp.status_code == 200
        assert "<table>" in resp.text

    async def test_export_html_empty_content(self, client: AsyncClient, db_session):
        report = Report(
            task_id=1,
            report_type=ReportType.FULL_REPORT,
            title="Empty",
            content="",
        )
        db_session.add(report)
        await db_session.commit()
        await db_session.refresh(report)

        resp = await client.get(f"/api/reports/{report.id}/export/html")
        assert resp.status_code == 200

    async def test_export_html_empty_title(self, client: AsyncClient, db_session):
        report = Report(
            task_id=1,
            report_type=ReportType.FULL_REPORT,
            title="",
            content="Some content",
        )
        db_session.add(report)
        await db_session.commit()
        await db_session.refresh(report)

        resp = await client.get(f"/api/reports/{report.id}/export/html")
        assert resp.status_code == 200
        assert "Untitled" in resp.text

    async def test_export_html_sanitizes_script(self, client: AsyncClient, db_session):
        report = Report(
            task_id=1,
            report_type=ReportType.FULL_REPORT,
            title="XSS",
            content='<script>alert("xss")</script>Safe content',
        )
        db_session.add(report)
        await db_session.commit()
        await db_session.refresh(report)

        resp = await client.get(f"/api/reports/{report.id}/export/html")
        assert resp.status_code == 200
        assert "<script>" not in resp.text
        assert "Safe content" in resp.text

    async def test_export_html_sanitizes_iframe(self, client: AsyncClient, db_session):
        report = Report(
            task_id=1,
            report_type=ReportType.FULL_REPORT,
            title="Iframe",
            content='<iframe src="evil.com"></iframe>Good',
        )
        db_session.add(report)
        await db_session.commit()
        await db_session.refresh(report)

        resp = await client.get(f"/api/reports/{report.id}/export/html")
        assert resp.status_code == 200
        assert "<iframe>" not in resp.text
        assert "Good" in resp.text

    async def test_export_html_with_code_block(self, client: AsyncClient, db_session):
        report = Report(
            task_id=1,
            report_type=ReportType.FULL_REPORT,
            title="Code",
            content="```python\nprint('hello')\n```",
        )
        db_session.add(report)
        await db_session.commit()
        await db_session.refresh(report)

        resp = await client.get(f"/api/reports/{report.id}/export/html")
        assert resp.status_code == 200
        assert "<code>" in resp.text or "print" in resp.text

    async def test_export_html_with_links(self, client: AsyncClient, db_session):
        report = Report(
            task_id=1,
            report_type=ReportType.FULL_REPORT,
            title="Links",
            content='[Example](https://example.com "Title")',
        )
        db_session.add(report)
        await db_session.commit()
        await db_session.refresh(report)

        resp = await client.get(f"/api/reports/{report.id}/export/html")
        assert resp.status_code == 200
        assert "https://example.com" in resp.text


# ===========================================================================
# api/reports.py - Export PDF
# ===========================================================================


@pytest.mark.asyncio
class TestReportExportPDF:
    async def test_export_pdf_not_found(self, client: AsyncClient):
        resp = await client.get("/api/reports/99999/export/pdf")
        assert resp.status_code == 404

    async def test_export_pdf_success(self, client: AsyncClient, db_session):
        report = Report(
            task_id=1,
            report_type=ReportType.FULL_REPORT,
            title="PDF Report",
            content="# PDF Content",
        )
        db_session.add(report)
        await db_session.commit()
        await db_session.refresh(report)

        def fake_create_pdf(html, dest, encoding="utf-8"):
            dest.write(b"%PDF-1.4 fake pdf content")
            return MagicMock(err=False)

        parent = MagicMock()
        parent.pisa = MagicMock()
        parent.pisa.CreatePDF = MagicMock(side_effect=fake_create_pdf)

        with patch.dict("sys.modules", {"xhtml2pdf": parent, "xhtml2pdf.pisa": parent.pisa}):
            resp = await client.get(f"/api/reports/{report.id}/export/pdf")

        assert resp.status_code == 200
        assert resp.headers["content-type"] == "application/pdf"
        assert "attachment" in resp.headers.get("content-disposition", "")
        assert resp.content == b"%PDF-1.4 fake pdf content"

    async def test_export_pdf_generation_error(self, client: AsyncClient, db_session):
        report = Report(
            task_id=1,
            report_type=ReportType.FULL_REPORT,
            title="Bad PDF",
            content="# Content",
        )
        db_session.add(report)
        await db_session.commit()
        await db_session.refresh(report)

        parent = MagicMock()
        parent.pisa = MagicMock()
        parent.pisa.CreatePDF = MagicMock(return_value=MagicMock(err=True))

        with patch.dict("sys.modules", {"xhtml2pdf": parent, "xhtml2pdf.pisa": parent.pisa}):
            resp = await client.get(f"/api/reports/{report.id}/export/pdf")

        assert resp.status_code == 500
        assert "PDF" in resp.json()["detail"]

    async def test_export_pdf_exception(self, client: AsyncClient, db_session):
        report = Report(
            task_id=1,
            report_type=ReportType.FULL_REPORT,
            title="Exception PDF",
            content="# Content",
        )
        db_session.add(report)
        await db_session.commit()
        await db_session.refresh(report)

        parent = MagicMock()
        parent.pisa = MagicMock()
        parent.pisa.CreatePDF = MagicMock(side_effect=ImportError("No module"))

        with patch.dict("sys.modules", {"xhtml2pdf": parent, "xhtml2pdf.pisa": parent.pisa}):
            resp = await client.get(f"/api/reports/{report.id}/export/pdf")

        assert resp.status_code == 500

    async def test_export_pdf_content_disposition(self, client: AsyncClient, db_session):
        report = Report(
            task_id=1,
            report_type=ReportType.FULL_REPORT,
            title="Filename Test",
            content="Content",
        )
        db_session.add(report)
        await db_session.commit()
        await db_session.refresh(report)

        def fake_create_pdf(html, dest, encoding="utf-8"):
            dest.write(b"%PDF")
            return MagicMock(err=False)

        parent = MagicMock()
        parent.pisa = MagicMock()
        parent.pisa.CreatePDF = MagicMock(side_effect=fake_create_pdf)

        with patch.dict("sys.modules", {"xhtml2pdf": parent, "xhtml2pdf.pisa": parent.pisa}):
            resp = await client.get(f"/api/reports/{report.id}/export/pdf")

        disposition = resp.headers.get("content-disposition", "")
        assert "Filename_Test.pdf" in disposition

    async def test_export_pdf_empty_title(self, client: AsyncClient, db_session):
        report = Report(
            task_id=1,
            report_type=ReportType.FULL_REPORT,
            title="",
            content="Content",
        )
        db_session.add(report)
        await db_session.commit()
        await db_session.refresh(report)

        def fake_create_pdf(html, dest, encoding="utf-8"):
            dest.write(b"%PDF")
            return MagicMock(err=False)

        parent = MagicMock()
        parent.pisa = MagicMock()
        parent.pisa.CreatePDF = MagicMock(side_effect=fake_create_pdf)

        with patch.dict("sys.modules", {"xhtml2pdf": parent, "xhtml2pdf.pisa": parent.pisa}):
            resp = await client.get(f"/api/reports/{report.id}/export/pdf")

        assert resp.status_code == 200
        disposition = resp.headers.get("content-disposition", "")
        assert "report.pdf" in disposition

    async def test_export_pdf_with_table(self, client: AsyncClient, db_session):
        report = Report(
            task_id=1,
            report_type=ReportType.FULL_REPORT,
            title="Table PDF",
            content="| A | B |\n|---|---|\n| 1 | 2 |",
        )
        db_session.add(report)
        await db_session.commit()
        await db_session.refresh(report)

        def fake_create_pdf(html, dest, encoding="utf-8"):
            dest.write(b"%PDF")
            return MagicMock(err=False)

        parent = MagicMock()
        parent.pisa = MagicMock()
        parent.pisa.CreatePDF = MagicMock(side_effect=fake_create_pdf)

        with patch.dict("sys.modules", {"xhtml2pdf": parent, "xhtml2pdf.pisa": parent.pisa}):
            resp = await client.get(f"/api/reports/{report.id}/export/pdf")

        assert resp.status_code == 200

    async def test_export_pdf_special_chars_in_title(self, client: AsyncClient, db_session):
        report = Report(
            task_id=1,
            report_type=ReportType.FULL_REPORT,
            title="Report/with\\special:chars*?<>|",
            content="Content",
        )
        db_session.add(report)
        await db_session.commit()
        await db_session.refresh(report)

        def fake_create_pdf(html, dest, encoding="utf-8"):
            dest.write(b"%PDF")
            return MagicMock(err=False)

        parent = MagicMock()
        parent.pisa = MagicMock()
        parent.pisa.CreatePDF = MagicMock(side_effect=fake_create_pdf)

        with patch.dict("sys.modules", {"xhtml2pdf": parent, "xhtml2pdf.pisa": parent.pisa}):
            resp = await client.get(f"/api/reports/{report.id}/export/pdf")

        assert resp.status_code == 200
        disposition = resp.headers.get("content-disposition", "")
        # Special chars should be replaced with underscores
        assert "/" not in disposition
        assert "\\" not in disposition


# ===========================================================================
# api/alerts.py - List Alerts
# ===========================================================================


@pytest.mark.asyncio
class TestAlertsList:
    async def test_list_alerts_empty(self, client: AsyncClient):
        resp = await client.get("/api/alerts/")
        assert resp.status_code == 200
        data = resp.json()
        assert data["items"] == []
        assert data["total"] == 0

    async def test_list_alerts_with_data(self, client: AsyncClient, db_session):
        task = await _create_task(db_session)
        finding = await _create_finding(db_session, task.id)
        alert = await _create_alert(db_session, finding.id)

        resp = await client.get("/api/alerts/")
        assert resp.status_code == 200
        items = resp.json()["items"]
        assert len(items) >= 1
        a = items[0]
        assert a["id"] == alert.id
        assert a["finding_id"] == finding.id
        assert a["alert_level"] == "critical"
        assert a["status"] == "active"
        assert a["finding_title"] == "Test Finding"
        assert a["finding_severity"] == "high"
        assert a["task_id"] == task.id

    async def test_list_alerts_filter_by_status(self, client: AsyncClient, db_session):
        task = await _create_task(db_session)
        finding = await _create_finding(db_session, task.id)
        await _create_alert(db_session, finding.id, status=AlertStatus.ACTIVE)
        await _create_alert(db_session, finding.id, status=AlertStatus.RESOLVED)

        resp = await client.get("/api/alerts/", params={"status": "resolved"})
        assert resp.status_code == 200
        items = resp.json()["items"]
        assert all(a["status"] == "resolved" for a in items)

    async def test_list_alerts_filter_acknowledged(self, client: AsyncClient, db_session):
        task = await _create_task(db_session)
        finding = await _create_finding(db_session, task.id)
        await _create_alert(db_session, finding.id, status=AlertStatus.ACKNOWLEDGED)

        resp = await client.get("/api/alerts/", params={"status": "acknowledged"})
        assert resp.status_code == 200
        items = resp.json()["items"]
        assert all(a["status"] == "acknowledged" for a in items)

    async def test_list_alerts_invalid_status(self, client: AsyncClient):
        resp = await client.get("/api/alerts/", params={"status": "bogus"})
        assert resp.status_code == 422
        assert "无效" in resp.json()["detail"]

    async def test_list_alerts_pagination(self, client: AsyncClient, db_session):
        task = await _create_task(db_session)
        for sev in [SeverityLevel.HIGH, SeverityLevel.MEDIUM, SeverityLevel.LOW]:
            finding = await _create_finding(db_session, task.id, severity=sev)
            await _create_alert(db_session, finding.id)

        resp = await client.get("/api/alerts/", params={"page": 1, "page_size": 2})
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["items"]) == 2
        assert data["total"] == 3

    async def test_list_alerts_resolved_at_field(self, client: AsyncClient, db_session):
        from datetime import UTC, datetime

        task = await _create_task(db_session)
        finding = await _create_finding(db_session, task.id)
        alert = await _create_alert(db_session, finding.id, status=AlertStatus.RESOLVED)
        # Set resolved_at explicitly (it's not auto-set by creation)
        alert.resolved_at = datetime.now(UTC)
        await db_session.commit()

        resp = await client.get("/api/alerts/")
        items = resp.json()["items"]
        a = [x for x in items if x["id"] == alert.id][0]
        assert a["resolved_at"] is not None


# ===========================================================================
# api/alerts.py - Acknowledge Alert
# ===========================================================================


@pytest.mark.asyncio
class TestAlertAcknowledge:
    async def test_acknowledge_alert_success(self, client: AsyncClient, db_session):
        task = await _create_task(db_session)
        finding = await _create_finding(db_session, task.id)
        alert = await _create_alert(db_session, finding.id, status=AlertStatus.ACTIVE)

        resp = await client.put(f"/api/alerts/{alert.id}/acknowledge")
        assert resp.status_code == 200
        assert resp.json()["status"] == "success"

    async def test_acknowledge_nonexistent(self, client: AsyncClient):
        resp = await client.put("/api/alerts/999/acknowledge")
        assert resp.status_code == 404

    async def test_acknowledge_already_resolved(self, client: AsyncClient, db_session):
        task = await _create_task(db_session)
        finding = await _create_finding(db_session, task.id)
        alert = await _create_alert(db_session, finding.id, status=AlertStatus.RESOLVED)

        resp = await client.put(f"/api/alerts/{alert.id}/acknowledge")
        assert resp.status_code == 400
        assert "解决" in resp.json()["detail"]

    async def test_acknowledge_already_acknowledged(self, client: AsyncClient, db_session):
        task = await _create_task(db_session)
        finding = await _create_finding(db_session, task.id)
        alert = await _create_alert(db_session, finding.id, status=AlertStatus.ACKNOWLEDGED)

        resp = await client.put(f"/api/alerts/{alert.id}/acknowledge")
        assert resp.status_code == 200


# ===========================================================================
# api/alerts.py - Resolve Alert
# ===========================================================================


@pytest.mark.asyncio
class TestAlertResolve:
    async def test_resolve_alert_success(self, client: AsyncClient, db_session):
        task = await _create_task(db_session)
        finding = await _create_finding(db_session, task.id)
        alert = await _create_alert(db_session, finding.id, status=AlertStatus.ACTIVE)

        resp = await client.put(f"/api/alerts/{alert.id}/resolve")
        assert resp.status_code == 200
        assert resp.json()["status"] == "success"

    async def test_resolve_from_acknowledged(self, client: AsyncClient, db_session):
        task = await _create_task(db_session)
        finding = await _create_finding(db_session, task.id)
        alert = await _create_alert(db_session, finding.id, status=AlertStatus.ACKNOWLEDGED)

        resp = await client.put(f"/api/alerts/{alert.id}/resolve")
        assert resp.status_code == 200

    async def test_resolve_nonexistent(self, client: AsyncClient):
        resp = await client.put("/api/alerts/999/resolve")
        assert resp.status_code == 404

    async def test_resolve_already_resolved(self, client: AsyncClient, db_session):
        task = await _create_task(db_session)
        finding = await _create_finding(db_session, task.id)
        alert = await _create_alert(db_session, finding.id, status=AlertStatus.RESOLVED)

        resp = await client.put(f"/api/alerts/{alert.id}/resolve")
        assert resp.status_code == 400
        assert "已经是解决状态" in resp.json()["detail"]


# ===========================================================================
# api/documents.py - Upload
# ===========================================================================


@pytest.mark.asyncio
class TestDocumentUpload:
    async def test_upload_unsupported_type(self, client: AsyncClient):
        files = {"file": ("test.xyz", b"content", "application/octet-stream")}
        resp = await client.post("/api/documents/upload", files=files)
        assert resp.status_code == 400
        assert "不支持" in resp.json()["detail"]

    async def test_upload_pdf(self, client: AsyncClient):
        files = {"file": ("test.pdf", b"%PDF-1.4 fake", "application/pdf")}
        resp = await client.post("/api/documents/upload", files=files)
        assert resp.status_code == 200
        data = resp.json()
        assert data["filename"] == "test.pdf"
        assert data["status"] == "uploaded"

    async def test_upload_docx(self, client: AsyncClient):
        files = {
            "file": (
                "test.docx",
                b"PK fake docx",
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )
        }
        resp = await client.post("/api/documents/upload", files=files)
        assert resp.status_code == 200

    async def test_upload_txt(self, client: AsyncClient):
        files = {"file": ("test.txt", b"text content", "text/plain")}
        resp = await client.post("/api/documents/upload", files=files)
        assert resp.status_code == 200

    async def test_upload_image(self, client: AsyncClient):
        files = {"file": ("test.jpg", b"\xff\xd8\xff\xe0fake jpg", "image/jpeg")}
        resp = await client.post("/api/documents/upload", files=files)
        assert resp.status_code == 200

    async def test_upload_too_large(self, client: AsyncClient):
        # Create a file that exceeds MAX_UPLOAD_SIZE (50MB)
        large_content = b"x" * (50 * 1024 * 1024 + 1)
        files = {"file": ("large.pdf", large_content, "application/pdf")}
        resp = await client.post("/api/documents/upload", files=files)
        assert resp.status_code == 413
        assert "大小" in resp.json()["detail"] or "限制" in resp.json()["detail"]


# ===========================================================================
# api/documents.py - Batch Upload
# ===========================================================================


@pytest.mark.asyncio
class TestDocumentBatchUpload:
    async def test_batch_upload_success(self, client: AsyncClient):
        files = [
            ("files", ("a.pdf", b"%PDF-1.4 fake", "application/pdf")),
            ("files", ("b.txt", b"text", "text/plain")),
        ]
        resp = await client.post("/api/documents/upload/batch", files=files)
        assert resp.status_code == 200
        results = resp.json()
        assert len(results) == 2

    async def test_batch_upload_mixed_types(self, client: AsyncClient):
        files = [
            ("files", ("a.pdf", b"%PDF-1.4 fake", "application/pdf")),
            ("files", ("b.xyz", b"bad", "application/octet-stream")),
        ]
        resp = await client.post("/api/documents/upload/batch", files=files)
        assert resp.status_code == 200
        results = resp.json()
        assert len(results) == 1  # b.xyz rejected


# ===========================================================================
# api/documents.py - List Documents
# ===========================================================================


@pytest.mark.asyncio
class TestDocumentsList:
    async def test_list_documents_empty(self, client: AsyncClient):
        resp = await client.get("/api/documents/")
        assert resp.status_code == 200
        data = resp.json()
        assert data["items"] == []
        assert data["total"] == 0

    async def test_list_documents_with_pagination(self, client: AsyncClient, db_session):
        for i in range(5):
            await _create_doc(db_session, filename=f"doc_{i}.pdf", file_size=100 * (i + 1))
        resp = await client.get("/api/documents/", params={"page": 1, "page_size": 2})
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["items"]) <= 2
        assert data["total"] == 5

    async def test_list_documents_metadata(self, client: AsyncClient, db_session):
        await _create_doc(db_session, doc_metadata=json.dumps({"source": "test"}))
        resp = await client.get("/api/documents/")
        assert resp.status_code == 200
        items = resp.json()["items"]
        assert len(items) == 1
        assert items[0]["doc_metadata"] == {"source": "test"}

    async def test_list_documents_metadata_dict(self, client: AsyncClient, db_session):
        """Test when doc_metadata is a valid JSON string."""
        await _create_doc(db_session, doc_metadata='{"source": "dict"}')
        resp = await client.get("/api/documents/")
        assert resp.status_code == 200
        items = resp.json()["items"]
        assert items[0]["doc_metadata"] == {"source": "dict"}

    async def test_list_documents_metadata_invalid_json(self, client: AsyncClient, db_session):
        """Test when doc_metadata is invalid JSON."""
        await _create_doc(db_session, doc_metadata="not json{{{")
        resp = await client.get("/api/documents/")
        assert resp.status_code == 200
        items = resp.json()["items"]
        assert items[0]["doc_metadata"] is None

    async def test_list_documents_created_at_format(self, client: AsyncClient, db_session):
        await _create_doc(db_session)
        resp = await client.get("/api/documents/")
        items = resp.json()["items"]
        assert len(items) == 1
        assert items[0]["upload_time"] is not None
        assert items[0]["created_at"] is not None


# ===========================================================================
# api/documents.py - Get Document
# ===========================================================================


@pytest.mark.asyncio
class TestDocumentGet:
    async def test_get_document_not_found(self, client: AsyncClient):
        resp = await client.get("/api/documents/99999")
        assert resp.status_code == 404

    async def test_get_document_success(self, client: AsyncClient, db_session):
        doc = await _create_doc(
            db_session,
            process_status=DocumentStatus.PROCESSED,
            content_text="Test content",
        )
        resp = await client.get(f"/api/documents/{doc.id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["filename"] == "test.pdf"
        assert data["file_type"] == "pdf"
        assert data["process_status"] == "processed"
        assert data["content_text"] == "Test content"

    async def test_get_document_with_metadata(self, client: AsyncClient, db_session):
        doc = await _create_doc(db_session, doc_metadata=json.dumps({"pages": 10}))
        resp = await client.get(f"/api/documents/{doc.id}")
        assert resp.status_code == 200
        assert resp.json()["doc_metadata"] == {"pages": 10}


# ===========================================================================
# api/documents.py - Process Document
# ===========================================================================


@pytest.mark.asyncio
class TestDocumentProcess:
    async def test_process_document_not_found(self, client: AsyncClient):
        resp = await client.post("/api/documents/99999/process")
        assert resp.status_code == 404

    async def test_process_document_already_processing(self, client: AsyncClient, db_session):
        doc = await _create_doc(db_session, process_status=DocumentStatus.PROCESSING)
        resp = await client.post(f"/api/documents/{doc.id}/process")
        assert resp.status_code == 409
        assert "处理中" in resp.json()["detail"]

    async def test_process_document_success(self, client: AsyncClient, db_session):
        doc = await _create_doc(db_session, process_status=DocumentStatus.UPLOADED)

        import app.services.document_processor as dp_module

        mock_processor = MagicMock()
        mock_processor.process_document = AsyncMock(
            return_value={
                "content": "Processed content",
                "chunks": ["chunk1"],
                "chunk_count": 1,
                "char_count": 16,
            }
        )
        original = dp_module.document_processor
        dp_module.document_processor = mock_processor
        try:
            resp = await client.post(f"/api/documents/{doc.id}/process")
            assert resp.status_code == 200
            data = resp.json()
            assert data["status"] == "success"
            assert data["char_count"] == 16
            assert data["chunk_count"] == 1
        finally:
            dp_module.document_processor = original

    async def test_process_document_failure(self, client: AsyncClient, db_session):
        doc = await _create_doc(db_session, process_status=DocumentStatus.UPLOADED)

        import app.services.document_processor as dp_module

        mock_processor = MagicMock()
        mock_processor.process_document = AsyncMock(side_effect=Exception("Processing error"))
        original = dp_module.document_processor
        dp_module.document_processor = mock_processor
        try:
            resp = await client.post(f"/api/documents/{doc.id}/process")
            assert resp.status_code == 500
            assert "处理失败" in resp.json()["detail"]
        finally:
            dp_module.document_processor = original


# ===========================================================================
# api/documents.py - Delete Document
# ===========================================================================


@pytest.mark.asyncio
class TestDocumentDelete:
    async def test_delete_document_not_found(self, client: AsyncClient):
        resp = await client.delete("/api/documents/999")
        assert resp.status_code == 404

    async def test_delete_document_success(self, client: AsyncClient, db_session):
        from app.core.config import settings

        upload_dir = settings.UPLOAD_DIR
        os.makedirs(upload_dir, exist_ok=True)
        test_file = os.path.join(upload_dir, "test_delete_success.txt")
        with open(test_file, "w", encoding="utf-8") as f:
            f.write("test content")

        doc = await _create_doc(db_session, file_path=test_file, file_type="txt", file_size=12)
        resp = await client.delete(f"/api/documents/{doc.id}")
        assert resp.status_code == 200
        assert resp.json()["status"] == "success"
        assert not os.path.exists(test_file)

    async def test_delete_document_with_findings(self, client: AsyncClient, db_session):
        """Document with related findings cannot be deleted."""
        from app.core.config import settings

        upload_dir = settings.UPLOAD_DIR
        os.makedirs(upload_dir, exist_ok=True)
        test_file = os.path.join(upload_dir, "test_delete_with_findings.txt")
        with open(test_file, "w", encoding="utf-8") as f:
            f.write("content")

        doc = await _create_doc(db_session, file_path=test_file, file_type="txt", file_size=7)
        task = await _create_task(db_session)
        await _create_finding(db_session, task.id, document_id=doc.id)

        resp = await client.delete(f"/api/documents/{doc.id}")
        assert resp.status_code == 400
        assert "引用" in resp.json()["detail"]
        # File should still exist
        assert os.path.exists(test_file)
        # Cleanup
        os.remove(test_file)

    async def test_delete_document_path_outside_upload_dir(self, client: AsyncClient, db_session):
        """Document with file path outside upload dir should be rejected."""
        doc = await _create_doc(db_session, file_path="/etc/passwd", file_type="txt")
        resp = await client.delete(f"/api/documents/{doc.id}")
        assert resp.status_code == 400
        assert "路径异常" in resp.json()["detail"]

    async def test_delete_document_file_already_deleted(self, client: AsyncClient, db_session):
        """Delete document when file was already removed from disk."""
        from app.core.config import settings

        upload_dir = settings.UPLOAD_DIR
        os.makedirs(upload_dir, exist_ok=True)
        test_file = os.path.join(upload_dir, "test_already_deleted.txt")
        with open(test_file, "w", encoding="utf-8") as f:
            f.write("content")
        file_path = test_file
        # Delete the file first
        os.remove(test_file)

        doc = await _create_doc(db_session, file_path=file_path, file_type="txt", file_size=0)
        resp = await client.delete(f"/api/documents/{doc.id}")
        assert resp.status_code == 200


# ===========================================================================
# Health API
# ===========================================================================


@pytest.mark.asyncio
class TestHealthAPI:
    async def test_health_check(self, client: AsyncClient):
        resp = await client.get("/api/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"

    async def test_db_health(self, client: AsyncClient):
        resp = await client.get("/api/health/db")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert "journal_mode" in data


# ===========================================================================
# Config API
# ===========================================================================


@pytest.mark.asyncio
class TestConfigAPI:
    async def test_get_config(self, client: AsyncClient, db_session):
        config = Configuration(
            config_key="TEST_KEY",
            config_value="TEST_VALUE",
            config_type="string",
        )
        db_session.add(config)
        await db_session.commit()

        resp = await client.get("/api/config/")
        assert resp.status_code == 200

    async def test_get_config_by_key(self, client: AsyncClient, db_session):
        config = Configuration(
            config_key="LOG_LEVEL",
            config_value="DEBUG",
            config_type="string",
        )
        db_session.add(config)
        await db_session.commit()

        resp = await client.get("/api/config/LOG_LEVEL")
        assert resp.status_code == 200
        data = resp.json()
        assert data["key"] == "LOG_LEVEL"
        assert data["value"] == "DEBUG"

    async def test_get_config_by_key_not_found(self, client: AsyncClient):
        resp = await client.get("/api/config/NONEXISTENT")
        assert resp.status_code in (200, 404)

    async def test_update_config(self, client: AsyncClient, db_session):
        config = Configuration(
            config_key="LOG_LEVEL",
            config_value="INFO",
            config_type="string",
        )
        db_session.add(config)
        await db_session.commit()

        resp = await client.put("/api/config/LOG_LEVEL", json={"value": "DEBUG"})
        assert resp.status_code == 200
        assert resp.json()["status"] == "success"

    async def test_update_config_not_found(self, client: AsyncClient):
        resp = await client.put("/api/config/NONEXISTENT", json={"value": "test"})
        assert resp.status_code in (400, 404)
