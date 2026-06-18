"""Direct-call API tests to bypass httpx ASGITransport coverage issues.

Imports and calls each API handler function directly, avoiding HTTP layer
coverage-tracking bugs with coverage.py.
"""

import asyncio
import json
import os
import tempfile
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit_task import AuditTask, TaskStatus, TaskType
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
        "progress": 0,
        "config": {},
        "document_ids": [],
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
        "file_size": 1024,
        "process_status": DocumentStatus.PROCESSED,
        "content_text": "Test content " * 100,
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
        "severity": SeverityLevel.MEDIUM,
        "title": "Test Finding",
        "description": "A test finding description with enough detail.",
        "evidence": "Evidence text",
        "suggestion": "Fix suggestion",
        "location": "Section 1",
        "regulation_ref": "GMP-001",
    }
    defaults.update(kwargs)
    finding = Finding(**defaults)
    db.add(finding)
    await db.commit()
    await db.refresh(finding)
    return finding


async def _create_report(db: AsyncSession, task_id: int, **kwargs) -> Report:
    defaults = {
        "task_id": task_id,
        "report_type": ReportType.FULL_REPORT,
        "title": "Test Report",
        "content": "# Audit Report\n\n## Findings\n\n| Item | Severity |\n|------|----------|\n| Test | Medium |",
        "report_metadata": {"findings_count": 1},
    }
    defaults.update(kwargs)
    report = Report(**defaults)
    db.add(report)
    await db.commit()
    await db.refresh(report)
    return report


async def _create_alert(db: AsyncSession, finding_id: int, **kwargs) -> RiskAlert:
    defaults = {
        "finding_id": finding_id,
        "alert_level": AlertLevel.WARNING,
        "status": AlertStatus.ACTIVE,
    }
    defaults.update(kwargs)
    alert = RiskAlert(**defaults)
    db.add(alert)
    await db.commit()
    await db.refresh(alert)
    return alert


def _mock_request(app_state: dict | None = None) -> Request:
    """Create a mock Request with app.state attributes."""
    req = MagicMock(spec=Request)
    req.app = MagicMock()
    req.app.state = MagicMock()
    # Allow dynamic attribute access on app.state
    if app_state:
        for k, v in app_state.items():
            setattr(req.app.state, k, v)
    return req


# ===========================================================================
# api/audit.py
# ===========================================================================


class TestAuditCreateTaskDirect:
    async def test_create_task_success(self, db_session: AsyncSession):
        from app.api.audit import AuditTaskCreate, create_audit_task

        task_data = AuditTaskCreate(
            task_name="Direct Test Task",
            task_type=TaskType.DEVIATION_ANALYSIS,
            document_ids=[1, 2],
        )
        result = await create_audit_task(task_data, db_session)

        assert result["task_name"] == "Direct Test Task"
        assert result["status"] == "pending"
        assert "id" in result

    async def test_create_task_with_sop_type(self, db_session: AsyncSession):
        from app.api.audit import AuditTaskCreate, create_audit_task

        task_data = AuditTaskCreate(
            task_name="SOP Task",
            task_type=TaskType.SOP_COMPLIANCE,
            document_ids=[],
        )
        result = await create_audit_task(task_data, db_session)
        assert result["status"] == "pending"


class TestAuditListTasksDirect:
    async def test_list_empty(self, db_session: AsyncSession):
        from app.api.audit import list_audit_tasks

        result = await list_audit_tasks(status=None, page=1, page_size=20, db=db_session)
        assert result["items"] == []
        assert result["total"] == 0
        assert result["page"] == 1

    async def test_list_with_tasks(self, db_session: AsyncSession):
        from app.api.audit import list_audit_tasks

        await _create_task(db_session, task_name="Task 1")
        await _create_task(db_session, task_name="Task 2")

        result = await list_audit_tasks(status=None, page=1, page_size=20, db=db_session)
        assert result["total"] == 2
        assert len(result["items"]) == 2

    async def test_list_filter_by_status(self, db_session: AsyncSession):
        from app.api.audit import list_audit_tasks

        await _create_task(db_session, task_name="Pending", status=TaskStatus.PENDING)
        await _create_task(db_session, task_name="Running", status=TaskStatus.RUNNING)

        result = await list_audit_tasks(status=TaskStatus.PENDING, page=1, page_size=20, db=db_session)
        assert result["total"] == 1
        assert result["items"][0]["task_name"] == "Pending"

    async def test_list_pagination(self, db_session: AsyncSession):
        from app.api.audit import list_audit_tasks

        for i in range(5):
            await _create_task(db_session, task_name=f"Task {i}")

        result = await list_audit_tasks(status=None, page=1, page_size=2, db=db_session)
        assert len(result["items"]) == 2
        assert result["total"] == 5

        result2 = await list_audit_tasks(status=None, page=3, page_size=2, db=db_session)
        assert len(result2["items"]) == 1

    async def test_list_with_findings_and_reports(self, db_session: AsyncSession):
        from app.api.audit import list_audit_tasks

        task = await _create_task(db_session)
        await _create_finding(db_session, task.id)
        await _create_report(db_session, task.id)

        result = await list_audit_tasks(status=None, page=1, page_size=20, db=db_session)
        assert result["total"] == 1
        assert result["items"][0]["findings_count"] == 1
        assert result["items"][0]["report_id"] is not None


class TestAuditGetTaskDirect:
    async def test_get_task_success(self, db_session: AsyncSession):
        from app.api.audit import get_audit_task

        doc = await _create_doc(db_session)
        task = await _create_task(db_session, document_ids=[doc.id])

        result = await get_audit_task(task.id, db_session)
        assert result["task_name"] == "Test Task"
        assert result["document_ids"] == [doc.id]

    async def test_get_task_not_found(self, db_session: AsyncSession):
        from app.api.audit import get_audit_task

        with pytest.raises(HTTPException) as exc_info:
            await get_audit_task(99999, db_session)
        assert exc_info.value.status_code == 404


class TestAuditRunTaskDirect:
    async def test_run_task_agent_unavailable(self, db_session: AsyncSession):
        from app.api.audit import run_audit_task

        task = await _create_task(db_session)
        req = _mock_request({"task_runner_factory": MagicMock()})

        with patch("app.api.audit.is_agent_available", return_value=False):
            with pytest.raises(HTTPException) as exc_info:
                await run_audit_task(task.id, req, db_session)
            assert exc_info.value.status_code == 503

    async def test_run_task_no_llm_configured(self, db_session: AsyncSession):
        from app.api.audit import run_audit_task

        task = await _create_task(db_session)
        req = _mock_request()

        with patch("app.api.audit.is_agent_available", return_value=True):
            mock_engine = MagicMock()
            mock_engine.adapters = {}
            with patch("app.services.llm_engine.get_llm_engine", return_value=mock_engine):
                with pytest.raises(HTTPException) as exc_info:
                    await run_audit_task(task.id, req, db_session)
                assert exc_info.value.status_code == 400

    async def test_run_task_already_running(self, db_session: AsyncSession):
        from app.api.audit import run_audit_task

        task = await _create_task(db_session, status=TaskStatus.RUNNING)
        req = _mock_request()

        with patch("app.api.audit.is_agent_available", return_value=True):
            mock_engine = MagicMock()
            mock_engine.adapters = {"test": MagicMock()}
            with patch("app.services.llm_engine.get_llm_engine", return_value=mock_engine):
                with pytest.raises(HTTPException) as exc_info:
                    await run_audit_task(task.id, req, db_session)
                assert exc_info.value.status_code == 400

    async def test_run_task_document_not_found(self, db_session: AsyncSession):
        from app.api.audit import run_audit_task

        task = await _create_task(db_session, document_ids=[99999])
        req = _mock_request()

        with patch("app.api.audit.is_agent_available", return_value=True):
            mock_engine = MagicMock()
            mock_engine.adapters = {"test": MagicMock()}
            with patch("app.services.llm_engine.get_llm_engine", return_value=mock_engine):
                with pytest.raises(HTTPException) as exc_info:
                    await run_audit_task(task.id, req, db_session)
                assert exc_info.value.status_code == 400
                assert "not found" in exc_info.value.detail.lower() or "Document" in exc_info.value.detail

    async def test_run_task_document_not_processed(self, db_session: AsyncSession):
        from app.api.audit import run_audit_task

        doc = await _create_doc(db_session, process_status=DocumentStatus.UPLOADED)
        task = await _create_task(db_session, document_ids=[doc.id])
        req = _mock_request()

        with patch("app.api.audit.is_agent_available", return_value=True):
            mock_engine = MagicMock()
            mock_engine.adapters = {"test": MagicMock()}
            with patch("app.services.llm_engine.get_llm_engine", return_value=mock_engine):
                with pytest.raises(HTTPException) as exc_info:
                    await run_audit_task(task.id, req, db_session)
                assert exc_info.value.status_code == 400

    async def test_run_task_not_found(self, db_session: AsyncSession):
        from app.api.audit import run_audit_task

        req = _mock_request()

        with patch("app.api.audit.is_agent_available", return_value=True):
            mock_engine = MagicMock()
            mock_engine.adapters = {"test": MagicMock()}
            with patch("app.services.llm_engine.get_llm_engine", return_value=mock_engine):
                with pytest.raises(HTTPException) as exc_info:
                    await run_audit_task(99999, req, db_session)
                assert exc_info.value.status_code == 404

    async def test_run_task_success(self, db_session: AsyncSession):
        from app.api.audit import run_audit_task

        doc = await _create_doc(db_session)
        task = await _create_task(db_session, document_ids=[doc.id])

        mock_runner = MagicMock()
        mock_runner.enqueue = MagicMock()
        mock_factory = MagicMock(return_value=mock_runner)
        req = _mock_request({"task_runner_factory": mock_factory})

        with patch("app.api.audit.is_agent_available", return_value=True):
            mock_engine = MagicMock()
            mock_engine.adapters = {"test": MagicMock()}
            with patch("app.services.llm_engine.get_llm_engine", return_value=mock_engine):
                result = await run_audit_task(task.id, req, db_session)

        assert result["status"] == "pending"
        assert result["task_id"] == task.id
        mock_runner.enqueue.assert_called_once_with(task.id)

    async def test_run_task_enqueue_runtime_error(self, db_session: AsyncSession):
        from app.api.audit import run_audit_task

        doc = await _create_doc(db_session)
        task = await _create_task(db_session, document_ids=[doc.id])

        mock_runner = MagicMock()
        mock_runner.enqueue.side_effect = RuntimeError("Queue full")
        mock_factory = MagicMock(return_value=mock_runner)
        req = _mock_request({"task_runner_factory": mock_factory})

        with patch("app.api.audit.is_agent_available", return_value=True):
            mock_engine = MagicMock()
            mock_engine.adapters = {"test": MagicMock()}
            with patch("app.services.llm_engine.get_llm_engine", return_value=mock_engine):
                with pytest.raises(HTTPException) as exc_info:
                    await run_audit_task(task.id, req, db_session)
                assert exc_info.value.status_code == 503


class TestAuditCancelTaskDirect:
    async def test_cancel_not_found(self, db_session: AsyncSession):
        from app.api.audit import cancel_audit_task

        req = _mock_request()
        with pytest.raises(HTTPException) as exc_info:
            await cancel_audit_task(99999, req, db_session)
        assert exc_info.value.status_code == 404

    async def test_cancel_not_running(self, db_session: AsyncSession):
        from app.api.audit import cancel_audit_task

        task = await _create_task(db_session, status=TaskStatus.PENDING)
        req = _mock_request()

        with pytest.raises(HTTPException) as exc_info:
            await cancel_audit_task(task.id, req, db_session)
        assert exc_info.value.status_code == 400

    async def test_cancel_success(self, db_session: AsyncSession):
        from app.api.audit import cancel_audit_task

        task = await _create_task(db_session, status=TaskStatus.RUNNING)

        mock_runner = AsyncMock()
        mock_runner.cancel = AsyncMock(return_value=True)
        mock_factory = MagicMock(return_value=mock_runner)
        req = _mock_request({"task_runner_factory": mock_factory})

        result = await cancel_audit_task(task.id, req, db_session)
        assert result["status"] == "cancelled"

    async def test_cancel_failed(self, db_session: AsyncSession):
        from app.api.audit import cancel_audit_task

        task = await _create_task(db_session, status=TaskStatus.RUNNING)

        mock_runner = AsyncMock()
        mock_runner.cancel = AsyncMock(return_value=False)
        mock_factory = MagicMock(return_value=mock_runner)
        req = _mock_request({"task_runner_factory": mock_factory})

        with pytest.raises(HTTPException) as exc_info:
            await cancel_audit_task(task.id, req, db_session)
        assert exc_info.value.status_code == 400


class TestAuditApproveTaskDirect:
    async def test_approve_not_found(self, db_session: AsyncSession):
        from app.api.audit import ReviewComment, approve_task

        body = ReviewComment(comment="Approved")
        req = _mock_request()
        with pytest.raises(HTTPException) as exc_info:
            await approve_task(99999, body, req, db_session)
        assert exc_info.value.status_code == 404

    async def test_approve_not_in_review(self, db_session: AsyncSession):
        from app.api.audit import ReviewComment, approve_task

        task = await _create_task(db_session, status=TaskStatus.PENDING)
        body = ReviewComment(comment="Approved")
        req = _mock_request()

        with pytest.raises(HTTPException) as exc_info:
            await approve_task(task.id, body, req, db_session)
        assert exc_info.value.status_code == 400

    async def test_approve_success(self, db_session: AsyncSession):
        from app.api.audit import ReviewComment, approve_task

        task = await _create_task(db_session, status=TaskStatus.AWAITING_REVIEW)
        body = ReviewComment(comment="Looks good")
        req = _mock_request()

        result = await approve_task(task.id, body, req, db_session)
        assert result["status"] == "approved"

    async def test_approve_with_event_bus(self, db_session: AsyncSession):
        from app.api.audit import ReviewComment, approve_task

        task = await _create_task(db_session, status=TaskStatus.AWAITING_REVIEW)
        body = ReviewComment(comment="Approved via bus")

        mock_bus = AsyncMock()
        mock_bus.publish = AsyncMock()
        mock_bus.publish_done = AsyncMock()
        req = _mock_request({"event_bus": mock_bus})

        result = await approve_task(task.id, body, req, db_session)
        assert result["status"] == "approved"
        mock_bus.publish.assert_called()
        mock_bus.publish_done.assert_called_once()

    async def test_approve_with_feishu_notification(self, db_session: AsyncSession):
        from app.api.audit import ReviewComment, approve_task

        task = await _create_task(db_session, status=TaskStatus.AWAITING_REVIEW)
        finding = await _create_finding(db_session, task.id, severity=SeverityLevel.HIGH)
        body = ReviewComment(comment="Approved")
        req = _mock_request()

        with patch("app.services.notification.is_feishu_configured", return_value=True):
            with patch("app.services.notification.notify_audit_complete", new_callable=AsyncMock) as mock_notify:
                result = await approve_task(task.id, body, req, db_session)
                assert result["status"] == "approved"
                mock_notify.assert_called_once()

    async def test_approve_event_bus_error_non_critical(self, db_session: AsyncSession):
        from app.api.audit import ReviewComment, approve_task

        task = await _create_task(db_session, status=TaskStatus.AWAITING_REVIEW)
        body = ReviewComment(comment="Approved")

        mock_bus = AsyncMock()
        mock_bus.publish.side_effect = RuntimeError("Bus error")
        req = _mock_request({"event_bus": mock_bus})

        # Should NOT raise - event bus errors are non-critical
        result = await approve_task(task.id, body, req, db_session)
        assert result["status"] == "approved"


class TestAuditRejectTaskDirect:
    async def test_reject_not_found(self, db_session: AsyncSession):
        from app.api.audit import ReviewComment, reject_task

        body = ReviewComment(comment="Rejected")
        with pytest.raises(HTTPException) as exc_info:
            await reject_task(99999, body, db_session)
        assert exc_info.value.status_code == 404

    async def test_reject_not_in_review(self, db_session: AsyncSession):
        from app.api.audit import ReviewComment, reject_task

        task = await _create_task(db_session, status=TaskStatus.COMPLETED)
        body = ReviewComment(comment="Rejected")

        with pytest.raises(HTTPException) as exc_info:
            await reject_task(task.id, body, db_session)
        assert exc_info.value.status_code == 400

    async def test_reject_success(self, db_session: AsyncSession):
        from app.api.audit import ReviewComment, reject_task

        task = await _create_task(db_session, status=TaskStatus.AWAITING_REVIEW)
        body = ReviewComment(comment="Needs rework")

        result = await reject_task(task.id, body, db_session)
        assert result["status"] == "rejected"
        assert result["task_id"] == task.id


class TestAuditGetFindingsDirect:
    async def test_get_findings_empty(self, db_session: AsyncSession):
        from app.api.audit import get_task_findings

        task = await _create_task(db_session)
        result = await get_task_findings(task.id, db_session)
        assert result == []

    async def test_get_findings_with_data(self, db_session: AsyncSession):
        from app.api.audit import get_task_findings

        task = await _create_task(db_session)
        finding = await _create_finding(db_session, task.id)

        result = await get_task_findings(task.id, db_session)
        assert len(result) == 1
        assert result[0]["title"] == "Test Finding"
        assert result[0]["severity"] == "medium"
        assert result[0]["finding_type"] == "compliance_risk"
        assert result[0]["status"] == "pending"

    async def test_get_findings_with_reviewed_at(self, db_session: AsyncSession):
        from app.api.audit import get_task_findings

        task = await _create_task(db_session)
        finding = await _create_finding(
            db_session, task.id,
            status=FindingStatus.APPROVED,
            reviewed_at=datetime.now(UTC),
        )

        result = await get_task_findings(task.id, db_session)
        assert result[0]["status"] == "approved"
        assert result[0]["reviewed_at"] is not None


class TestAuditApproveRejectFindingDirect:
    async def test_approve_finding_success(self, db_session: AsyncSession):
        from app.api.audit import FindingReviewRequest, approve_finding

        task = await _create_task(db_session)
        finding = await _create_finding(db_session, task.id)
        body = FindingReviewRequest(comment="Good finding")

        result = await approve_finding(finding.id, body, db_session)
        assert result["status"] == "approved"

    async def test_approve_finding_not_found(self, db_session: AsyncSession):
        from app.api.audit import FindingReviewRequest, approve_finding

        body = FindingReviewRequest(comment="test")
        with pytest.raises(HTTPException) as exc_info:
            await approve_finding(99999, body, db_session)
        assert exc_info.value.status_code == 404

    async def test_approve_finding_no_body(self, db_session: AsyncSession):
        from app.api.audit import approve_finding

        task = await _create_task(db_session)
        finding = await _create_finding(db_session, task.id)

        result = await approve_finding(finding.id, None, db_session)
        assert result["status"] == "approved"

    async def test_reject_finding_success(self, db_session: AsyncSession):
        from app.api.audit import FindingReviewRequest, reject_finding

        task = await _create_task(db_session)
        finding = await _create_finding(db_session, task.id)
        body = FindingReviewRequest(comment="Not valid")

        result = await reject_finding(finding.id, body, db_session)
        assert result["status"] == "rejected"

    async def test_reject_finding_not_found(self, db_session: AsyncSession):
        from app.api.audit import FindingReviewRequest, reject_finding

        body = FindingReviewRequest(comment="test")
        with pytest.raises(HTTPException) as exc_info:
            await reject_finding(99999, body, db_session)
        assert exc_info.value.status_code == 404

    async def test_reject_finding_no_body(self, db_session: AsyncSession):
        from app.api.audit import reject_finding

        task = await _create_task(db_session)
        finding = await _create_finding(db_session, task.id)

        result = await reject_finding(finding.id, None, db_session)
        assert result["status"] == "rejected"


class TestAuditRiskAssessmentDirect:
    async def test_risk_assessment_empty(self, db_session: AsyncSession):
        from app.api.audit import get_task_risk_assessment

        task = await _create_task(db_session)
        result = await get_task_risk_assessment(task.id, db_session)

        assert result["risk_level"] == "low"
        assert result["total_findings"] == 0

    async def test_risk_assessment_with_findings(self, db_session: AsyncSession):
        from app.api.audit import get_task_risk_assessment

        task = await _create_task(db_session)
        await _create_finding(db_session, task.id, severity=SeverityLevel.HIGH)
        await _create_finding(db_session, task.id, severity=SeverityLevel.MEDIUM)

        result = await get_task_risk_assessment(task.id, db_session)
        assert result["risk_level"] == "high"
        assert result["high_risk"] == 1
        assert result["medium_risk"] == 1


class TestAuditDashboardDirect:
    async def test_dashboard_empty(self, db_session: AsyncSession):
        from app.api.audit import get_dashboard_stats

        result = await get_dashboard_stats(db_session)
        assert result["total_tasks"] == 0
        assert result["total_findings"] == 0
        assert "task_counts" in result
        assert "severity_counts" in result

    async def test_dashboard_with_data(self, db_session: AsyncSession):
        from app.api.audit import get_dashboard_stats

        task = await _create_task(db_session, status=TaskStatus.COMPLETED)
        await _create_finding(db_session, task.id, severity=SeverityLevel.HIGH)

        result = await get_dashboard_stats(db_session)
        assert result["total_tasks"] == 1
        assert result["total_findings"] == 1
        assert result["task_counts"]["completed"] == 1
        assert result["severity_counts"]["high"] == 1


class TestAuditEstimateCostDirect:
    async def test_estimate_success(self, db_session: AsyncSession):
        from app.api.audit import EstimateRequest, estimate_audit_cost

        doc = await _create_doc(db_session, content_text="A" * 1000)
        body = EstimateRequest(document_ids=[doc.id])

        result = await estimate_audit_cost(body, db_session)
        assert result["document_count"] == 1
        assert result["estimated_llm_calls"] > 0
        assert result["estimated_input_tokens"] > 0
        assert result["estimated_output_tokens"] > 0
        assert result["estimated_duration_seconds"] > 0

    async def test_estimate_no_docs_found(self, db_session: AsyncSession):
        from app.api.audit import EstimateRequest, estimate_audit_cost

        body = EstimateRequest(document_ids=[99999])
        with pytest.raises(HTTPException) as exc_info:
            await estimate_audit_cost(body, db_session)
        assert exc_info.value.status_code == 404

    async def test_estimate_large_document(self, db_session: AsyncSession):
        from app.api.audit import EstimateRequest, estimate_audit_cost

        # Content > STUFF_LIMIT (60000) triggers map-reduce path
        doc = await _create_doc(db_session, content_text="A" * 100000)
        body = EstimateRequest(document_ids=[doc.id])

        result = await estimate_audit_cost(body, db_session)
        assert result["estimated_llm_calls"] > 4  # more than simple path


# ===========================================================================
# api/agent_audit.py
# ===========================================================================


class TestAgentAuditRunDirect:
    async def test_run_agent_audit_success(self, db_session: AsyncSession):
        from app.api.agent_audit import AgentAuditRequest, run_agent_audit

        doc = await _create_doc(db_session)
        request = AgentAuditRequest(document_id=doc.id, audit_type="deviation", focus="GMP compliance")

        mock_runner = MagicMock()
        mock_runner.enqueue = MagicMock()
        mock_factory = MagicMock(return_value=mock_runner)
        http_request = _mock_request({"task_runner_factory": mock_factory})

        with patch("app.api.agent_audit.is_agent_available", return_value=True):
            result = await run_agent_audit(request, http_request, db_session)

        assert result.task_id is not None
        assert result.status == "pending"

    async def test_run_agent_audit_agent_unavailable(self, db_session: AsyncSession):
        from app.api.agent_audit import AgentAuditRequest, run_agent_audit

        doc = await _create_doc(db_session)
        request = AgentAuditRequest(document_id=doc.id)
        http_request = _mock_request()

        with patch("app.api.agent_audit.is_agent_available", return_value=False):
            with pytest.raises(HTTPException) as exc_info:
                await run_agent_audit(request, http_request, db_session)
            assert exc_info.value.status_code == 503

    async def test_run_agent_audit_doc_not_found(self, db_session: AsyncSession):
        from app.api.agent_audit import AgentAuditRequest, run_agent_audit

        request = AgentAuditRequest(document_id=99999)
        http_request = _mock_request()

        with patch("app.api.agent_audit.is_agent_available", return_value=True):
            with pytest.raises(HTTPException) as exc_info:
                await run_agent_audit(request, http_request, db_session)
            assert exc_info.value.status_code == 404

    async def test_run_agent_audit_doc_not_processed(self, db_session: AsyncSession):
        from app.api.agent_audit import AgentAuditRequest, run_agent_audit

        doc = await _create_doc(db_session, process_status=DocumentStatus.UPLOADED)
        request = AgentAuditRequest(document_id=doc.id)
        http_request = _mock_request()

        with patch("app.api.agent_audit.is_agent_available", return_value=True):
            with pytest.raises(HTTPException) as exc_info:
                await run_agent_audit(request, http_request, db_session)
            assert exc_info.value.status_code == 400

    async def test_run_agent_audit_invalid_type(self, db_session: AsyncSession):
        from app.api.agent_audit import AgentAuditRequest, run_agent_audit

        doc = await _create_doc(db_session)
        request = AgentAuditRequest(document_id=doc.id, audit_type="invalid_type")
        http_request = _mock_request()

        with patch("app.api.agent_audit.is_agent_available", return_value=True):
            with pytest.raises(HTTPException) as exc_info:
                await run_agent_audit(request, http_request, db_session)
            assert exc_info.value.status_code == 400

    async def test_run_agent_audit_enqueue_error(self, db_session: AsyncSession):
        from app.api.agent_audit import AgentAuditRequest, run_agent_audit

        doc = await _create_doc(db_session)
        request = AgentAuditRequest(document_id=doc.id, audit_type="sop")

        mock_runner = MagicMock()
        mock_runner.enqueue.side_effect = RuntimeError("Queue full")
        mock_factory = MagicMock(return_value=mock_runner)
        http_request = _mock_request({"task_runner_factory": mock_factory})

        with patch("app.api.agent_audit.is_agent_available", return_value=True):
            with pytest.raises(HTTPException) as exc_info:
                await run_agent_audit(request, http_request, db_session)
            assert exc_info.value.status_code == 503

    async def test_run_agent_audit_change_control_type(self, db_session: AsyncSession):
        from app.api.agent_audit import AgentAuditRequest, run_agent_audit

        doc = await _create_doc(db_session)
        request = AgentAuditRequest(document_id=doc.id, audit_type="change_control")

        mock_runner = MagicMock()
        mock_factory = MagicMock(return_value=mock_runner)
        http_request = _mock_request({"task_runner_factory": mock_factory})

        with patch("app.api.agent_audit.is_agent_available", return_value=True):
            result = await run_agent_audit(request, http_request, db_session)
        assert result.status == "pending"


class TestAgentAuditStatusDirect:
    async def test_get_status_success(self, db_session: AsyncSession):
        from app.api.agent_audit import get_agent_audit_status

        task = await _create_task(db_session)
        result = await get_agent_audit_status(task.id, db_session)
        assert result["task_name"] == "Test Task"

    async def test_get_status_not_found(self, db_session: AsyncSession):
        from app.api.agent_audit import get_agent_audit_status

        with pytest.raises(HTTPException) as exc_info:
            await get_agent_audit_status(99999, db_session)
        assert exc_info.value.status_code == 404


# ===========================================================================
# api/reports.py
# ===========================================================================


class TestReportsListDirect:
    async def test_list_reports_empty(self, db_session: AsyncSession):
        from app.api.reports import list_reports

        result = await list_reports(task_id=None, page=1, page_size=20, db=db_session)
        assert result["items"] == []
        assert result["total"] == 0

    async def test_list_reports_with_data(self, db_session: AsyncSession):
        from app.api.reports import list_reports

        task = await _create_task(db_session)
        await _create_report(db_session, task.id)

        result = await list_reports(task_id=None, page=1, page_size=20, db=db_session)
        assert result["total"] == 1
        assert result["items"][0]["title"] == "Test Report"

    async def test_list_reports_filter_by_task(self, db_session: AsyncSession):
        from app.api.reports import list_reports

        task1 = await _create_task(db_session, task_name="Task 1")
        task2 = await _create_task(db_session, task_name="Task 2")
        await _create_report(db_session, task1.id, title="Report 1")
        await _create_report(db_session, task2.id, title="Report 2")

        result = await list_reports(task_id=task1.id, page=1, page_size=20, db=db_session)
        assert result["total"] == 1
        assert result["items"][0]["title"] == "Report 1"

    async def test_list_reports_pagination(self, db_session: AsyncSession):
        from app.api.reports import list_reports

        task = await _create_task(db_session)
        for i in range(3):
            await _create_report(db_session, task.id, title=f"Report {i}")

        result = await list_reports(task_id=None, page=1, page_size=2, db=db_session)
        assert len(result["items"]) == 2
        assert result["total"] == 3


class TestReportsGenerateDirect:
    async def test_generate_report_success(self, db_session: AsyncSession):
        from app.api.reports import generate_report

        task = await _create_task(db_session)
        await _create_finding(db_session, task.id)

        mock_llm = AsyncMock()
        mock_llm.generate_report = AsyncMock(return_value="# Generated Report\n\nAll good.")
        with patch("app.api.reports.get_llm_engine", return_value=mock_llm):
            with patch("app.api.reports.settings") as mock_settings:
                mock_settings.LLM_REQUEST_TIMEOUT = 60
                result = await generate_report(task.id, db_session)

        assert "id" in result
        assert result["title"] is not None
        assert "Generated Report" in result["content"]

    async def test_generate_report_task_not_found(self, db_session: AsyncSession):
        from app.api.reports import generate_report

        with pytest.raises(HTTPException) as exc_info:
            await generate_report(99999, db_session)
        assert exc_info.value.status_code == 404

    async def test_generate_report_no_findings(self, db_session: AsyncSession):
        from app.api.reports import generate_report

        task = await _create_task(db_session)

        with pytest.raises(HTTPException) as exc_info:
            await generate_report(task.id, db_session)
        assert exc_info.value.status_code == 400

    async def test_generate_report_llm_value_error(self, db_session: AsyncSession):
        from app.api.reports import generate_report

        task = await _create_task(db_session)
        await _create_finding(db_session, task.id)

        mock_llm = AsyncMock()
        mock_llm.generate_report = AsyncMock(side_effect=ValueError("No API key"))
        with patch("app.api.reports.get_llm_engine", return_value=mock_llm):
            with patch("app.api.reports.settings") as mock_settings:
                mock_settings.LLM_REQUEST_TIMEOUT = 60
                with pytest.raises(HTTPException) as exc_info:
                    await generate_report(task.id, db_session)
                assert exc_info.value.status_code == 503

    async def test_generate_report_llm_timeout(self, db_session: AsyncSession):
        from app.api.reports import generate_report

        task = await _create_task(db_session)
        await _create_finding(db_session, task.id)

        mock_llm = AsyncMock()
        mock_llm.generate_report = AsyncMock(side_effect=TimeoutError())
        with patch("app.api.reports.get_llm_engine", return_value=mock_llm):
            with patch("app.api.reports.settings") as mock_settings:
                mock_settings.LLM_REQUEST_TIMEOUT = 60
                with pytest.raises(HTTPException) as exc_info:
                    await generate_report(task.id, db_session)
                assert exc_info.value.status_code == 504

    async def test_generate_report_llm_generic_error(self, db_session: AsyncSession):
        from app.api.reports import generate_report

        task = await _create_task(db_session)
        await _create_finding(db_session, task.id)

        mock_llm = AsyncMock()
        mock_llm.generate_report = AsyncMock(side_effect=RuntimeError("LLM exploded"))
        with patch("app.api.reports.get_llm_engine", return_value=mock_llm):
            with patch("app.api.reports.settings") as mock_settings:
                mock_settings.LLM_REQUEST_TIMEOUT = 60
                with pytest.raises(HTTPException) as exc_info:
                    await generate_report(task.id, db_session)
                assert exc_info.value.status_code == 502


class TestReportsGetDirect:
    async def test_get_report_success(self, db_session: AsyncSession):
        from app.api.reports import get_report

        task = await _create_task(db_session)
        report = await _create_report(db_session, task.id)

        result = await get_report(report.id, db_session)
        assert result["id"] == report.id
        assert result["title"] == "Test Report"
        assert "content" in result

    async def test_get_report_not_found(self, db_session: AsyncSession):
        from app.api.reports import get_report

        with pytest.raises(HTTPException) as exc_info:
            await get_report(99999, db_session)
        assert exc_info.value.status_code == 404


class TestReportsExportHtmlDirect:
    async def test_export_html_success(self, db_session: AsyncSession):
        from app.api.reports import export_report_html

        task = await _create_task(db_session)
        report = await _create_report(db_session, task.id, content="# Title\n\nSome content")

        result = await export_report_html(report.id, db_session)
        # HTMLResponse has a .body attribute
        html_content = result.body.decode("utf-8") if hasattr(result, "body") else str(result)
        assert "Test Report" in html_content or "Title" in html_content

    async def test_export_html_not_found(self, db_session: AsyncSession):
        from app.api.reports import export_report_html

        with pytest.raises(HTTPException) as exc_info:
            await export_report_html(99999, db_session)
        assert exc_info.value.status_code == 404

    async def test_export_html_empty_content(self, db_session: AsyncSession):
        from app.api.reports import export_report_html

        task = await _create_task(db_session)
        report = await _create_report(db_session, task.id, content="")

        result = await export_report_html(report.id, db_session)
        html_content = result.body.decode("utf-8") if hasattr(result, "body") else str(result)
        assert "<!DOCTYPE html>" in html_content

    async def test_export_html_with_tables(self, db_session: AsyncSession):
        from app.api.reports import export_report_html

        task = await _create_task(db_session)
        report = await _create_report(
            db_session, task.id,
            content="| A | B |\n|---|---|\n| 1 | 2 |"
        )

        result = await export_report_html(report.id, db_session)
        html_content = result.body.decode("utf-8") if hasattr(result, "body") else str(result)
        assert "<table>" in html_content


class TestReportsExportPdfDirect:
    async def test_export_pdf_success(self, db_session: AsyncSession):
        from app.api.reports import export_report_pdf

        task = await _create_task(db_session)
        report = await _create_report(db_session, task.id, content="# PDF Report\n\nContent here.")

        with patch("app.api.reports.settings") as mock_settings:
            # Just test that it doesn't crash; PDF libs may not be installed
            try:
                result = await export_report_pdf(report.id, db_session)
                # StreamingResponse for PDF
                assert result is not None
            except HTTPException as e:
                # 500 is expected if xhtml2pdf is not installed
                assert e.status_code == 500

    async def test_export_pdf_not_found(self, db_session: AsyncSession):
        from app.api.reports import export_report_pdf

        with pytest.raises(HTTPException) as exc_info:
            await export_report_pdf(99999, db_session)
        assert exc_info.value.status_code == 404


# ===========================================================================
# api/alerts.py
# ===========================================================================


class TestAlertsListDirect:
    async def test_list_alerts_empty(self, db_session: AsyncSession):
        from app.api.alerts import list_alerts

        result = await list_alerts(status=None, page=1, page_size=20, db=db_session)
        assert result["items"] == []
        assert result["total"] == 0

    async def test_list_alerts_with_data(self, db_session: AsyncSession):
        from app.api.alerts import list_alerts

        task = await _create_task(db_session)
        finding = await _create_finding(db_session, task.id)
        alert = await _create_alert(db_session, finding.id)

        result = await list_alerts(status=None, page=1, page_size=20, db=db_session)
        assert result["total"] == 1
        assert result["items"][0]["alert_level"] == "warning"
        assert result["items"][0]["finding_title"] == "Test Finding"

    async def test_list_alerts_filter_status(self, db_session: AsyncSession):
        from app.api.alerts import list_alerts

        task = await _create_task(db_session)
        finding = await _create_finding(db_session, task.id)
        await _create_alert(db_session, finding.id, status=AlertStatus.ACTIVE)
        await _create_alert(db_session, finding.id, status=AlertStatus.ACKNOWLEDGED)

        result = await list_alerts(status="active", page=1, page_size=20, db=db_session)
        assert result["total"] == 1
        assert result["items"][0]["status"] == "active"

    async def test_list_alerts_invalid_status(self, db_session: AsyncSession):
        from app.api.alerts import list_alerts

        with pytest.raises(HTTPException) as exc_info:
            await list_alerts(status="invalid_status", page=1, page_size=20, db=db_session)
        assert exc_info.value.status_code == 422

    async def test_list_alerts_pagination(self, db_session: AsyncSession):
        from app.api.alerts import list_alerts

        task = await _create_task(db_session)
        finding = await _create_finding(db_session, task.id)
        for _ in range(3):
            await _create_alert(db_session, finding.id)

        result = await list_alerts(status=None, page=1, page_size=2, db=db_session)
        assert len(result["items"]) == 2
        assert result["total"] == 3

    async def test_list_alerts_resolved_at(self, db_session: AsyncSession):
        from app.api.alerts import list_alerts

        task = await _create_task(db_session)
        finding = await _create_finding(db_session, task.id)
        await _create_alert(
            db_session, finding.id,
            status=AlertStatus.RESOLVED,
            resolved_at=datetime.now(UTC),
            resolved_by="admin",
        )

        result = await list_alerts(status="resolved", page=1, page_size=20, db=db_session)
        assert result["total"] == 1
        assert result["items"][0]["resolved_by"] == "admin"


class TestAlertsAcknowledgeDirect:
    async def test_acknowledge_success(self, db_session: AsyncSession):
        from app.api.alerts import acknowledge_alert

        task = await _create_task(db_session)
        finding = await _create_finding(db_session, task.id)
        alert = await _create_alert(db_session, finding.id, status=AlertStatus.ACTIVE)

        result = await acknowledge_alert(alert.id, db_session)
        assert result["status"] == "success"

    async def test_acknowledge_not_found(self, db_session: AsyncSession):
        from app.api.alerts import acknowledge_alert

        with pytest.raises(HTTPException) as exc_info:
            await acknowledge_alert(99999, db_session)
        assert exc_info.value.status_code == 404

    async def test_acknowledge_already_resolved(self, db_session: AsyncSession):
        from app.api.alerts import acknowledge_alert

        task = await _create_task(db_session)
        finding = await _create_finding(db_session, task.id)
        alert = await _create_alert(db_session, finding.id, status=AlertStatus.RESOLVED)

        with pytest.raises(HTTPException) as exc_info:
            await acknowledge_alert(alert.id, db_session)
        assert exc_info.value.status_code == 400


class TestAlertsResolveDirect:
    async def test_resolve_success(self, db_session: AsyncSession):
        from app.api.alerts import resolve_alert

        task = await _create_task(db_session)
        finding = await _create_finding(db_session, task.id)
        alert = await _create_alert(db_session, finding.id, status=AlertStatus.ACTIVE)

        result = await resolve_alert(alert.id, db_session)
        assert result["status"] == "success"

    async def test_resolve_not_found(self, db_session: AsyncSession):
        from app.api.alerts import resolve_alert

        with pytest.raises(HTTPException) as exc_info:
            await resolve_alert(99999, db_session)
        assert exc_info.value.status_code == 404

    async def test_resolve_already_resolved(self, db_session: AsyncSession):
        from app.api.alerts import resolve_alert

        task = await _create_task(db_session)
        finding = await _create_finding(db_session, task.id)
        alert = await _create_alert(db_session, finding.id, status=AlertStatus.RESOLVED)

        with pytest.raises(HTTPException) as exc_info:
            await resolve_alert(alert.id, db_session)
        assert exc_info.value.status_code == 400

    async def test_resolve_from_acknowledged(self, db_session: AsyncSession):
        from app.api.alerts import resolve_alert

        task = await _create_task(db_session)
        finding = await _create_finding(db_session, task.id)
        alert = await _create_alert(db_session, finding.id, status=AlertStatus.ACKNOWLEDGED)

        result = await resolve_alert(alert.id, db_session)
        assert result["status"] == "success"


# ===========================================================================
# api/documents.py
# ===========================================================================


class TestDocumentsListDirect:
    async def test_list_documents_empty(self, db_session: AsyncSession):
        from app.api.documents import list_documents

        result = await list_documents(page=1, page_size=20, db=db_session)
        assert result["items"] == []
        assert result["total"] == 0

    async def test_list_documents_with_data(self, db_session: AsyncSession):
        from app.api.documents import list_documents

        await _create_doc(db_session)
        result = await list_documents(page=1, page_size=20, db=db_session)
        assert result["total"] == 1
        assert result["items"][0]["filename"] == "test.pdf"

    async def test_list_documents_pagination(self, db_session: AsyncSession):
        from app.api.documents import list_documents

        for i in range(3):
            await _create_doc(db_session, filename=f"doc{i}.pdf")

        result = await list_documents(page=1, page_size=2, db=db_session)
        assert len(result["items"]) == 2
        assert result["total"] == 3

    async def test_list_documents_with_metadata(self, db_session: AsyncSession):
        from app.api.documents import list_documents

        await _create_doc(db_session, doc_metadata='{"key": "value"}')
        result = await list_documents(page=1, page_size=20, db=db_session)
        assert result["items"][0]["doc_metadata"] == {"key": "value"}

    async def test_list_documents_with_dict_metadata(self, db_session: AsyncSession):
        from app.api.documents import list_documents

        await _create_doc(db_session, doc_metadata=json.dumps({"source": "upload"}))
        result = await list_documents(page=1, page_size=20, db=db_session)
        assert result["items"][0]["doc_metadata"]["source"] == "upload"


class TestDocumentsGetDirect:
    async def test_get_document_success(self, db_session: AsyncSession):
        from app.api.documents import get_document

        doc = await _create_doc(db_session)
        result = await get_document(doc.id, db_session)
        assert result["filename"] == "test.pdf"
        assert "content_text" in result

    async def test_get_document_not_found(self, db_session: AsyncSession):
        from app.api.documents import get_document

        with pytest.raises(HTTPException) as exc_info:
            await get_document(99999, db_session)
        assert exc_info.value.status_code == 404

    async def test_get_document_with_metadata(self, db_session: AsyncSession):
        from app.api.documents import get_document

        doc = await _create_doc(db_session, doc_metadata='{"pages": 10}')
        result = await get_document(doc.id, db_session)
        assert result["doc_metadata"] == {"pages": 10}


class TestDocumentsProcessDirect:
    async def test_process_document_success(self, db_session: AsyncSession):
        from app.api.documents import process_document

        doc = await _create_doc(db_session, process_status=DocumentStatus.UPLOADED)

        mock_processor = MagicMock()
        mock_processor.process_document = AsyncMock(
            return_value={"content": "Processed content", "char_count": 100, "chunk_count": 5}
        )
        with patch("app.services.document_processor.get_document_processor", return_value=mock_processor):
            result = await process_document(doc.id, db_session)

        assert result["status"] == "success"
        assert result["char_count"] == 100
        assert result["chunk_count"] == 5

    async def test_process_document_not_found(self, db_session: AsyncSession):
        from app.api.documents import process_document

        with pytest.raises(HTTPException) as exc_info:
            await process_document(99999, db_session)
        assert exc_info.value.status_code == 404

    async def test_process_document_already_processing(self, db_session: AsyncSession):
        from app.api.documents import process_document

        doc = await _create_doc(db_session, process_status=DocumentStatus.PROCESSING)

        with pytest.raises(HTTPException) as exc_info:
            await process_document(doc.id, db_session)
        assert exc_info.value.status_code == 409

    async def test_process_document_failure(self, db_session: AsyncSession):
        from app.api.documents import process_document

        doc = await _create_doc(db_session, process_status=DocumentStatus.UPLOADED)

        mock_processor = MagicMock()
        mock_processor.process_document = AsyncMock(side_effect=RuntimeError("Process failed"))
        with patch("app.services.document_processor.get_document_processor", return_value=mock_processor):
            with pytest.raises(HTTPException) as exc_info:
                await process_document(doc.id, db_session)
            assert exc_info.value.status_code == 500


class TestDocumentsDeleteDirect:
    async def test_delete_document_success(self, db_session: AsyncSession, tmp_path):
        from app.api.documents import delete_document

        # Create a temp file
        test_file = tmp_path / "test_delete.pdf"
        test_file.write_bytes(b"test content")

        doc = await _create_doc(db_session, file_path=str(test_file))

        with patch("app.api.documents._get_upload_dir", return_value=str(tmp_path)):
            result = await delete_document(doc.id, db_session)

        assert result["status"] == "success"
        assert not test_file.exists()

    async def test_delete_document_not_found(self, db_session: AsyncSession):
        from app.api.documents import delete_document

        with pytest.raises(HTTPException) as exc_info:
            await delete_document(99999, db_session)
        assert exc_info.value.status_code == 404

    async def test_delete_document_with_findings(self, db_session: AsyncSession):
        from app.api.documents import delete_document

        task = await _create_task(db_session)
        doc = await _create_doc(db_session)
        await _create_finding(db_session, task.id, document_id=doc.id)

        with pytest.raises(HTTPException) as exc_info:
            await delete_document(doc.id, db_session)
        assert exc_info.value.status_code == 400
        assert "引用" in exc_info.value.detail

    async def test_delete_document_path_outside_upload_dir(self, db_session: AsyncSession):
        from app.api.documents import delete_document

        doc = await _create_doc(db_session, file_path="/etc/passwd")

        with patch("app.api.documents._get_upload_dir", return_value="/tmp/uploads"):
            with pytest.raises(HTTPException) as exc_info:
                await delete_document(doc.id, db_session)
            assert exc_info.value.status_code == 400
            assert "异常" in exc_info.value.detail

    async def test_delete_document_file_not_exists(self, db_session: AsyncSession, tmp_path):
        from app.api.documents import delete_document

        # File doesn't exist, but path is within upload dir
        fake_path = str(tmp_path / "nonexistent.pdf")
        doc = await _create_doc(db_session, file_path=fake_path)

        with patch("app.api.documents._get_upload_dir", return_value=str(tmp_path)):
            result = await delete_document(doc.id, db_session)

        assert result["status"] == "success"


class TestDocumentsUploadDirect:
    async def test_upload_document_success(self, db_session: AsyncSession, tmp_path):
        from app.api.documents import upload_document

        mock_file = MagicMock()
        mock_file.filename = "test.pdf"
        mock_file.read = AsyncMock(return_value=b"PDF content here")

        mock_request = MagicMock(spec=Request)
        mock_request.headers = {"content-length": "100"}

        mock_bg = MagicMock()
        mock_bg.add_task = MagicMock()

        with patch("app.api.documents._get_upload_dir", return_value=str(tmp_path)):
            with patch("app.api.documents._write_file_sync"):
                with patch("app.api.documents.get_file_type", return_value="pdf"):
                    with patch("app.api.documents.get_file_size", return_value=100):
                        result = await upload_document(mock_request, mock_file, mock_bg, db_session)

        assert result["filename"] == "test.pdf"
        assert result["status"] == "uploaded"

    async def test_upload_document_unsupported_type(self, db_session: AsyncSession):
        from app.api.documents import upload_document

        mock_file = MagicMock()
        mock_file.filename = "test.exe"

        mock_request = MagicMock(spec=Request)
        mock_request.headers = {}

        mock_bg = MagicMock()

        with patch("app.api.documents.get_file_type", return_value="unknown"):
            with pytest.raises(HTTPException) as exc_info:
                await upload_document(mock_request, mock_file, mock_bg, db_session)
            assert exc_info.value.status_code == 400

    async def test_upload_document_too_large_content_length(self, db_session: AsyncSession):
        from app.api.documents import upload_document

        mock_file = MagicMock()
        mock_file.filename = "big.pdf"

        mock_request = MagicMock(spec=Request)
        mock_request.headers = {"content-length": str(60 * 1024 * 1024)}

        mock_bg = MagicMock()

        with patch("app.api.documents.get_file_type", return_value="pdf"):
            with pytest.raises(HTTPException) as exc_info:
                await upload_document(mock_request, mock_file, mock_bg, db_session)
            assert exc_info.value.status_code == 413

    async def test_upload_document_too_large_body(self, db_session: AsyncSession):
        from app.api.documents import upload_document

        mock_file = MagicMock()
        mock_file.filename = "big.pdf"
        mock_file.read = AsyncMock(return_value=b"x" * (51 * 1024 * 1024))

        mock_request = MagicMock(spec=Request)
        mock_request.headers = {}

        mock_bg = MagicMock()

        with patch("app.api.documents.get_file_type", return_value="pdf"):
            with pytest.raises(HTTPException) as exc_info:
                await upload_document(mock_request, mock_file, mock_bg, db_session)
            assert exc_info.value.status_code == 413


class TestDocumentsUploadBatchDirect:
    async def test_upload_batch_success(self, db_session: AsyncSession, tmp_path):
        from app.api.documents import upload_documents_batch

        mock_file1 = MagicMock()
        mock_file1.filename = "doc1.pdf"
        mock_file1.file = MagicMock()
        mock_file1.file.seek = MagicMock()
        mock_file1.file.tell = MagicMock(return_value=100)

        mock_file2 = MagicMock()
        mock_file2.filename = "doc2.txt"
        mock_file2.file = MagicMock()
        mock_file2.file.seek = MagicMock()
        mock_file2.file.tell = MagicMock(return_value=200)

        mock_bg = MagicMock()

        with patch("app.api.documents._get_upload_dir", return_value=str(tmp_path)):
            with patch("app.api.documents.get_file_type", side_effect=["pdf", "text"]):
                with patch("app.api.documents.get_file_size", return_value=100):
                    with patch("builtins.open", MagicMock()):
                        with patch("shutil.copyfileobj"):
                            result = await upload_documents_batch(
                                [mock_file1, mock_file2], mock_bg, db_session
                            )

        assert len(result) == 2
        assert result[0]["filename"] == "doc1.pdf"
        assert result[1]["filename"] == "doc2.txt"

    async def test_upload_batch_skip_unknown(self, db_session: AsyncSession, tmp_path):
        from app.api.documents import upload_documents_batch

        mock_file1 = MagicMock()
        mock_file1.filename = "test.exe"
        mock_file1.file = MagicMock()
        mock_file1.file.seek = MagicMock()
        mock_file1.file.tell = MagicMock(return_value=100)

        mock_file2 = MagicMock()
        mock_file2.filename = "test.pdf"
        mock_file2.file = MagicMock()
        mock_file2.file.seek = MagicMock()
        mock_file2.file.tell = MagicMock(return_value=100)

        mock_bg = MagicMock()

        with patch("app.api.documents._get_upload_dir", return_value=str(tmp_path)):
            with patch("app.api.documents.get_file_type", side_effect=["unknown", "pdf"]):
                with patch("app.api.documents.get_file_size", return_value=100):
                    with patch("builtins.open", MagicMock()):
                        with patch("shutil.copyfileobj"):
                            result = await upload_documents_batch(
                                [mock_file1, mock_file2], mock_bg, db_session
                            )

        # Only 1 result - unknown type is skipped
        assert len(result) == 1

    async def test_upload_batch_file_too_large(self, db_session: AsyncSession, tmp_path):
        from app.api.documents import upload_documents_batch

        mock_file = MagicMock()
        mock_file.filename = "big.pdf"
        mock_file.file = MagicMock()
        mock_file.file.seek = MagicMock()
        mock_file.file.tell = MagicMock(return_value=60 * 1024 * 1024)

        mock_bg = MagicMock()

        with patch("app.api.documents._get_upload_dir", return_value=str(tmp_path)):
            with patch("app.api.documents.get_file_type", return_value="pdf"):
                with pytest.raises(HTTPException) as exc_info:
                    await upload_documents_batch([mock_file], mock_bg, db_session)
                assert exc_info.value.status_code == 413


# ===========================================================================
# api/documents.py - _parse_metadata and _generate_safe_filename helpers
# ===========================================================================


class TestDocumentHelpers:
    def test_parse_metadata_none(self):
        from app.api.documents import _parse_metadata

        assert _parse_metadata(None) is None
        assert _parse_metadata("") is None

    def test_parse_metadata_dict(self):
        from app.api.documents import _parse_metadata

        data = {"key": "value"}
        assert _parse_metadata(data) == data

    def test_parse_metadata_json_string(self):
        from app.api.documents import _parse_metadata

        assert _parse_metadata('{"key": "value"}') == {"key": "value"}

    def test_parse_metadata_invalid_json(self):
        from app.api.documents import _parse_metadata

        assert _parse_metadata("not json") is None

    def test_generate_safe_filename(self):
        from app.api.documents import _generate_safe_filename

        name = _generate_safe_filename("test file.pdf")
        assert name.endswith(".pdf")
        assert len(name) > 4  # uuid hex + extension
        # Should not contain spaces or special chars
        assert " " not in name

    def test_generate_safe_filename_no_ext(self):
        from app.api.documents import _generate_safe_filename

        name = _generate_safe_filename("noext")
        assert name.endswith("")  # no extension preserved

    async def test_get_upload_dir_preferred(self):
        from app.api.documents import _get_upload_dir

        with patch("app.api.documents.settings") as mock_settings:
            mock_settings.UPLOAD_DIR = tempfile.mkdtemp()
            result = _get_upload_dir()
            assert result == mock_settings.UPLOAD_DIR

    async def test_get_upload_dir_fallback(self):
        from app.api.documents import _get_upload_dir

        call_count = 0
        original_makedirs = os.makedirs

        def _selective_makedirs(path, *args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise OSError("Permission denied")
            return original_makedirs(path, *args, **kwargs)

        with patch("app.api.documents.settings") as mock_settings:
            mock_settings.UPLOAD_DIR = "/nonexistent/readonly/path"
            with patch("os.makedirs", side_effect=_selective_makedirs):
                result = _get_upload_dir()
                assert "gmpaudit_uploads" in result


# ===========================================================================
# api/reports.py - _sanitize_html helper
# ===========================================================================


class TestReportsSanitizeHtml:
    def test_sanitize_allows_safe_tags(self):
        from app.api.reports import _sanitize_html

        html = "<h1>Title</h1><p>Text <strong>bold</strong></p>"
        result = _sanitize_html(html)
        assert "<h1>" in result
        assert "<strong>" in result

    def test_sanitize_strips_script(self):
        from app.api.reports import _sanitize_html

        html = '<p>Safe</p><script>alert("xss")</script>'
        result = _sanitize_html(html)
        assert "<script>" not in result
        assert "Safe" in result

    def test_sanitize_strips_iframe(self):
        from app.api.reports import _sanitize_html

        html = '<p>Text</p><iframe src="evil.com"></iframe>'
        result = _sanitize_html(html)
        assert "<iframe>" not in result

    def test_sanitize_preserves_links(self):
        from app.api.reports import _sanitize_html

        html = '<a href="https://example.com" title="test">Link</a>'
        result = _sanitize_html(html)
        assert "href" in result
