"""Extended audit API tests for uncovered endpoints.

Covers:
- POST /tasks/{id}/cancel
- POST /tasks/{id}/approve
- POST /tasks/{id}/reject
- POST /estimate
- POST /findings/{id}/approve
- POST /findings/{id}/reject
- GET /dashboard with multiple statuses
- GET /tasks/{id}/findings with multiple findings
- GET /memory
- SSE stream endpoints (basic coverage)
- Additional edge cases for existing endpoints
"""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit_task import AuditTask, TaskStatus, TaskType
from app.models.document import Document, DocumentStatus
from app.models.finding import Finding, FindingStatus, FindingType, SeverityLevel
from app.models.report import Report, ReportType


# ---------------------------------------------------------------------------
# Helper: create task + document + findings
# ---------------------------------------------------------------------------


async def _create_task_with_doc(db: AsyncSession, status=TaskStatus.PENDING, doc_status=DocumentStatus.PROCESSED):
    doc = Document(
        filename="test.pdf",
        file_path="/tmp/test.pdf",
        file_type="pdf",
        file_size=1024,
        process_status=doc_status,
        content_text="Sample content",
    )
    db.add(doc)
    await db.commit()
    await db.refresh(doc)

    task = AuditTask(
        task_name="Test Audit",
        task_type=TaskType.DEVIATION_ANALYSIS,
        status=status,
        document_ids=[doc.id],
        config={},
    )
    db.add(task)
    await db.commit()
    await db.refresh(task)
    return task, doc


async def _create_finding(db: AsyncSession, task_id: int, severity=SeverityLevel.HIGH, document_id: int | None = None):
    finding = Finding(
        task_id=task_id,
        document_id=document_id,
        finding_type=FindingType.COMPLIANCE_RISK,
        severity=severity,
        title="Test Finding",
        description="A test finding description",
    )
    db.add(finding)
    await db.commit()
    await db.refresh(finding)
    return finding


# ---------------------------------------------------------------------------
# POST /tasks - create
# ---------------------------------------------------------------------------


class TestCreateAuditTask:
    @pytest.mark.asyncio
    async def test_create_task_returns_correct_fields(self, client: AsyncClient):
        resp = await client.post(
            "/api/audit/tasks",
            json={"task_name": "New Task", "task_type": "sop_compliance", "document_ids": []},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "id" in data
        assert data["task_name"] == "New Task"
        assert data["status"] == "pending"

    @pytest.mark.asyncio
    async def test_create_task_with_document_ids(self, client: AsyncClient, db_session: AsyncSession):
        doc = Document(
            filename="d.pdf", file_path="/tmp/d.pdf", file_type="pdf",
            file_size=100, process_status=DocumentStatus.PROCESSED,
        )
        db_session.add(doc)
        await db_session.commit()
        await db_session.refresh(doc)

        resp = await client.post(
            "/api/audit/tasks",
            json={"task_name": "Task With Doc", "task_type": "deviation_analysis", "document_ids": [doc.id]},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["task_name"] == "Task With Doc"


# ---------------------------------------------------------------------------
# GET /tasks - list with pagination
# ---------------------------------------------------------------------------


class TestListAuditTasks:
    @pytest.mark.asyncio
    async def test_list_empty(self, client: AsyncClient):
        resp = await client.get("/api/audit/tasks")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0
        assert data["items"] == []

    @pytest.mark.asyncio
    async def test_list_with_pagination(self, client: AsyncClient, db_session: AsyncSession):
        for i in range(5):
            db_session.add(AuditTask(
                task_name=f"Task {i}",
                task_type=TaskType.DEVIATION_ANALYSIS,
                status=TaskStatus.COMPLETED,
            ))
        await db_session.commit()

        resp = await client.get("/api/audit/tasks?page=1&page_size=2")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 5
        assert len(data["items"]) == 2
        assert data["page"] == 1
        assert data["page_size"] == 2

    @pytest.mark.asyncio
    async def test_list_with_findings_count(self, client: AsyncClient, db_session: AsyncSession):
        task = AuditTask(
            task_name="Task With Findings",
            task_type=TaskType.DEVIATION_ANALYSIS,
            status=TaskStatus.COMPLETED,
        )
        db_session.add(task)
        await db_session.commit()
        await db_session.refresh(task)

        for i in range(3):
            db_session.add(Finding(
                task_id=task.id,
                finding_type=FindingType.COMPLIANCE_RISK,
                severity=SeverityLevel.HIGH,
                title=f"Finding {i}",
                description="Desc",
            ))
        await db_session.commit()

        resp = await client.get("/api/audit/tasks")
        data = resp.json()
        items = data["items"]
        # Find our task
        found = [t for t in items if t["task_name"] == "Task With Findings"]
        assert len(found) == 1
        assert found[0]["findings_count"] == 3


# ---------------------------------------------------------------------------
# GET /tasks/{id}
# ---------------------------------------------------------------------------


class TestGetAuditTask:
    @pytest.mark.asyncio
    async def test_get_task_includes_document_ids(self, client: AsyncClient, db_session: AsyncSession):
        task, doc = await _create_task_with_doc(db_session)

        resp = await client.get(f"/api/audit/tasks/{task.id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["document_ids"] == [doc.id]

    @pytest.mark.asyncio
    async def test_get_nonexistent_returns_404(self, client: AsyncClient):
        resp = await client.get("/api/audit/tasks/99999")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# POST /tasks/{id}/cancel
# ---------------------------------------------------------------------------


class TestCancelAuditTask:
    @pytest.mark.asyncio
    async def test_cancel_not_found(self, client: AsyncClient):
        resp = await client.post("/api/audit/tasks/999/cancel")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_cancel_non_running_task(self, client: AsyncClient, db_session: AsyncSession):
        task = AuditTask(
            task_name="Pending Task",
            task_type=TaskType.DEVIATION_ANALYSIS,
            status=TaskStatus.PENDING,
        )
        db_session.add(task)
        await db_session.commit()
        await db_session.refresh(task)

        resp = await client.post(f"/api/audit/tasks/{task.id}/cancel")
        assert resp.status_code == 400
        assert "not running" in resp.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_cancel_running_task_success(self, client: AsyncClient, db_session: AsyncSession):
        task = AuditTask(
            task_name="Running Task",
            task_type=TaskType.DEVIATION_ANALYSIS,
            status=TaskStatus.RUNNING,
        )
        db_session.add(task)
        await db_session.commit()
        await db_session.refresh(task)

        # Mock the task_runner_factory to return a runner where cancel succeeds
        mock_runner = MagicMock()
        mock_runner.cancel = AsyncMock(return_value=True)

        original_factory = client._transport.app.state.task_runner_factory
        client._transport.app.state.task_runner_factory = lambda: mock_runner

        try:
            resp = await client.post(f"/api/audit/tasks/{task.id}/cancel")
            assert resp.status_code == 200
            data = resp.json()
            assert data["status"] == "cancelled"
            assert data["task_id"] == task.id
        finally:
            client._transport.app.state.task_runner_factory = original_factory

    @pytest.mark.asyncio
    async def test_cancel_returns_failure(self, client: AsyncClient, db_session: AsyncSession):
        task = AuditTask(
            task_name="Running Task",
            task_type=TaskType.DEVIATION_ANALYSIS,
            status=TaskStatus.RUNNING,
        )
        db_session.add(task)
        await db_session.commit()
        await db_session.refresh(task)

        mock_runner = MagicMock()
        mock_runner.cancel = AsyncMock(return_value=False)

        original_factory = client._transport.app.state.task_runner_factory
        client._transport.app.state.task_runner_factory = lambda: mock_runner

        try:
            resp = await client.post(f"/api/audit/tasks/{task.id}/cancel")
            assert resp.status_code == 400
            assert "could not be cancelled" in resp.json()["detail"].lower()
        finally:
            client._transport.app.state.task_runner_factory = original_factory


# ---------------------------------------------------------------------------
# POST /tasks/{id}/approve
# ---------------------------------------------------------------------------


class TestApproveTask:
    @pytest.mark.asyncio
    async def test_approve_not_found(self, client: AsyncClient):
        resp = await client.post("/api/audit/tasks/999/approve", json={"comment": "OK"})
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_approve_wrong_status(self, client: AsyncClient, db_session: AsyncSession):
        task = AuditTask(
            task_name="Pending Task",
            task_type=TaskType.DEVIATION_ANALYSIS,
            status=TaskStatus.PENDING,
        )
        db_session.add(task)
        await db_session.commit()
        await db_session.refresh(task)

        resp = await client.post(f"/api/audit/tasks/{task.id}/approve", json={"comment": "OK"})
        assert resp.status_code == 400
        assert "review" in resp.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_approve_awaiting_review_success(self, client: AsyncClient, db_session: AsyncSession):
        task = AuditTask(
            task_name="Review Task",
            task_type=TaskType.DEVIATION_ANALYSIS,
            status=TaskStatus.AWAITING_REVIEW,
        )
        db_session.add(task)
        await db_session.commit()
        await db_session.refresh(task)

        # Mock EventBus on app state
        mock_event_bus = AsyncMock()
        original_bus = getattr(client._transport.app.state, "event_bus", None)
        client._transport.app.state.event_bus = mock_event_bus

        try:
            with patch("app.services.notification.is_feishu_configured", return_value=False):
                resp = await client.post(
                    f"/api/audit/tasks/{task.id}/approve",
                    json={"comment": "Approved after review"},
                )
            assert resp.status_code == 200
            data = resp.json()
            assert data["status"] == "approved"
        finally:
            if original_bus:
                client._transport.app.state.event_bus = original_bus

    @pytest.mark.asyncio
    async def test_approve_with_empty_comment(self, client: AsyncClient, db_session: AsyncSession):
        task = AuditTask(
            task_name="Review Task",
            task_type=TaskType.DEVIATION_ANALYSIS,
            status=TaskStatus.AWAITING_REVIEW,
        )
        db_session.add(task)
        await db_session.commit()
        await db_session.refresh(task)

        mock_event_bus = AsyncMock()
        original_bus = getattr(client._transport.app.state, "event_bus", None)
        client._transport.app.state.event_bus = mock_event_bus

        try:
            with patch("app.services.notification.is_feishu_configured", return_value=False):
                resp = await client.post(
                    f"/api/audit/tasks/{task.id}/approve",
                    json={"comment": ""},
                )
            assert resp.status_code == 200
        finally:
            if original_bus:
                client._transport.app.state.event_bus = original_bus


# ---------------------------------------------------------------------------
# POST /tasks/{id}/reject
# ---------------------------------------------------------------------------


class TestRejectTask:
    @pytest.mark.asyncio
    async def test_reject_not_found(self, client: AsyncClient):
        resp = await client.post("/api/audit/tasks/999/reject", json={"comment": "Bad"})
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_reject_wrong_status(self, client: AsyncClient, db_session: AsyncSession):
        task = AuditTask(
            task_name="Completed Task",
            task_type=TaskType.DEVIATION_ANALYSIS,
            status=TaskStatus.COMPLETED,
        )
        db_session.add(task)
        await db_session.commit()
        await db_session.refresh(task)

        resp = await client.post(f"/api/audit/tasks/{task.id}/reject", json={"comment": "No"})
        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_reject_awaiting_review_success(self, client: AsyncClient, db_session: AsyncSession):
        task = AuditTask(
            task_name="Review Task",
            task_type=TaskType.DEVIATION_ANALYSIS,
            status=TaskStatus.AWAITING_REVIEW,
        )
        db_session.add(task)
        await db_session.commit()
        await db_session.refresh(task)

        resp = await client.post(
            f"/api/audit/tasks/{task.id}/reject",
            json={"comment": "Needs rework"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "rejected"


# ---------------------------------------------------------------------------
# POST /findings/{id}/approve
# ---------------------------------------------------------------------------


class TestApproveFinding:
    @pytest.mark.asyncio
    async def test_approve_finding_not_found(self, client: AsyncClient):
        resp = await client.post("/api/audit/findings/999/approve", json={"comment": "OK"})
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_approve_finding_success(self, client: AsyncClient, db_session: AsyncSession):
        task = AuditTask(
            task_name="T", task_type=TaskType.DEVIATION_ANALYSIS, status=TaskStatus.COMPLETED,
        )
        db_session.add(task)
        await db_session.commit()
        await db_session.refresh(task)

        finding = await _create_finding(db_session, task.id)

        resp = await client.post(
            f"/api/audit/findings/{finding.id}/approve",
            json={"comment": "Looks correct"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "approved"

    @pytest.mark.asyncio
    async def test_approve_finding_no_body(self, client: AsyncClient, db_session: AsyncSession):
        task = AuditTask(
            task_name="T", task_type=TaskType.DEVIATION_ANALYSIS, status=TaskStatus.COMPLETED,
        )
        db_session.add(task)
        await db_session.commit()
        await db_session.refresh(task)

        finding = await _create_finding(db_session, task.id)

        resp = await client.post(f"/api/audit/findings/{finding.id}/approve")
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# POST /findings/{id}/reject
# ---------------------------------------------------------------------------


class TestRejectFinding:
    @pytest.mark.asyncio
    async def test_reject_finding_not_found(self, client: AsyncClient):
        resp = await client.post("/api/audit/findings/999/reject", json={"comment": "Bad"})
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_reject_finding_success(self, client: AsyncClient, db_session: AsyncSession):
        task = AuditTask(
            task_name="T", task_type=TaskType.DEVIATION_ANALYSIS, status=TaskStatus.COMPLETED,
        )
        db_session.add(task)
        await db_session.commit()
        await db_session.refresh(task)

        finding = await _create_finding(db_session, task.id)

        resp = await client.post(
            f"/api/audit/findings/{finding.id}/reject",
            json={"comment": "Not valid"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "rejected"


# ---------------------------------------------------------------------------
# POST /estimate
# ---------------------------------------------------------------------------


class TestEstimateAuditCost:
    @pytest.mark.asyncio
    async def test_estimate_not_found(self, client: AsyncClient):
        resp = await client.post("/api/audit/estimate", json={"document_ids": [999]})
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_estimate_single_document(self, client: AsyncClient, db_session: AsyncSession):
        doc = Document(
            filename="short.pdf",
            file_path="/tmp/short.pdf",
            file_type="pdf",
            file_size=1024,
            content_text="Short content",
            process_status=DocumentStatus.PROCESSED,
        )
        db_session.add(doc)
        await db_session.commit()
        await db_session.refresh(doc)

        resp = await client.post("/api/audit/estimate", json={"document_ids": [doc.id]})
        assert resp.status_code == 200
        data = resp.json()
        assert data["document_count"] == 1
        assert data["estimated_llm_calls"] > 0
        assert data["estimated_input_tokens"] > 0
        assert data["estimated_output_tokens"] > 0
        assert data["estimated_duration_seconds"] > 0

    @pytest.mark.asyncio
    async def test_estimate_large_document_uses_map_reduce(self, client: AsyncClient, db_session: AsyncSession):
        # Content larger than STUFF_LIMIT (60000 chars) triggers map-reduce
        large_content = "x" * 70000
        doc = Document(
            filename="large.pdf",
            file_path="/tmp/large.pdf",
            file_type="pdf",
            file_size=70000,
            content_text=large_content,
            process_status=DocumentStatus.PROCESSED,
        )
        db_session.add(doc)
        await db_session.commit()
        await db_session.refresh(doc)

        resp = await client.post("/api/audit/estimate", json={"document_ids": [doc.id]})
        assert resp.status_code == 200
        data = resp.json()
        # Large doc should have more LLM calls (map-reduce)
        assert data["estimated_llm_calls"] > 4  # reg(2) + risk(chunks) + report(1)

    @pytest.mark.asyncio
    async def test_estimate_multiple_documents(self, client: AsyncClient, db_session: AsyncSession):
        docs = []
        for i in range(3):
            doc = Document(
                filename=f"doc{i}.pdf",
                file_path=f"/tmp/doc{i}.pdf",
                file_type="pdf",
                file_size=1024,
                content_text=f"Content {i}",
                process_status=DocumentStatus.PROCESSED,
            )
            db_session.add(doc)
            docs.append(doc)
        await db_session.commit()
        for doc in docs:
            await db_session.refresh(doc)

        doc_ids = [doc.id for doc in docs]
        resp = await client.post("/api/audit/estimate", json={"document_ids": doc_ids})
        assert resp.status_code == 200
        data = resp.json()
        assert data["document_count"] == 3
        # Each doc: 2 reg + 1 risk + 1 report = 4 calls, so 3 docs = 12
        assert data["estimated_llm_calls"] == 12


# ---------------------------------------------------------------------------
# GET /dashboard
# ---------------------------------------------------------------------------


class TestDashboard:
    @pytest.mark.asyncio
    async def test_dashboard_empty(self, client: AsyncClient):
        resp = await client.get("/api/audit/dashboard")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_tasks"] == 0
        assert data["total_findings"] == 0
        # All task statuses should be 0
        for status_val in ["pending", "running", "completed", "failed"]:
            assert data["task_counts"].get(status_val, 0) == 0

    @pytest.mark.asyncio
    async def test_dashboard_with_various_statuses(self, client: AsyncClient, db_session: AsyncSession):
        statuses = [TaskStatus.COMPLETED, TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.PENDING]
        for i, status in enumerate(statuses):
            db_session.add(AuditTask(
                task_name=f"Task {i}",
                task_type=TaskType.DEVIATION_ANALYSIS,
                status=status,
            ))
        await db_session.commit()

        resp = await client.get("/api/audit/dashboard")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_tasks"] == 4
        assert data["task_counts"]["completed"] == 2
        assert data["task_counts"]["failed"] == 1
        assert data["task_counts"]["pending"] == 1

    @pytest.mark.asyncio
    async def test_dashboard_with_severity_counts(self, client: AsyncClient, db_session: AsyncSession):
        task = AuditTask(
            task_name="T", task_type=TaskType.DEVIATION_ANALYSIS, status=TaskStatus.COMPLETED,
        )
        db_session.add(task)
        await db_session.commit()
        await db_session.refresh(task)

        for sev in [SeverityLevel.HIGH, SeverityLevel.HIGH, SeverityLevel.MEDIUM, SeverityLevel.LOW]:
            db_session.add(Finding(
                task_id=task.id,
                finding_type=FindingType.COMPLIANCE_RISK,
                severity=sev,
                title=f"Finding {sev.value}",
                description="Desc",
            ))
        await db_session.commit()

        resp = await client.get("/api/audit/dashboard")
        assert resp.status_code == 200
        data = resp.json()
        assert data["severity_counts"]["high"] == 2
        assert data["severity_counts"]["medium"] == 1
        assert data["severity_counts"]["low"] == 1
        assert data["total_findings"] == 4


# ---------------------------------------------------------------------------
# GET /tasks/{id}/findings
# ---------------------------------------------------------------------------


class TestGetTaskFindings:
    @pytest.mark.asyncio
    async def test_findings_with_all_fields(self, client: AsyncClient, db_session: AsyncSession):
        task = AuditTask(
            task_name="T", task_type=TaskType.DEVIATION_ANALYSIS, status=TaskStatus.COMPLETED,
        )
        db_session.add(task)
        await db_session.commit()
        await db_session.refresh(task)

        finding = Finding(
            task_id=task.id,
            document_id=None,
            finding_type=FindingType.COMPLIANCE_RISK,
            severity=SeverityLevel.HIGH,
            title="Complete Finding",
            description="Full description",
            evidence="Evidence text",
            suggestion="Fix suggestion",
            location="Section 4.2",
            regulation_ref="GMP Annex 11",
        )
        db_session.add(finding)
        await db_session.commit()

        resp = await client.get(f"/api/audit/tasks/{task.id}/findings")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        f = data[0]
        assert f["title"] == "Complete Finding"
        assert f["severity"] == "high"
        assert f["finding_type"] == "compliance_risk"
        assert f["evidence"] == "Evidence text"
        assert f["suggestion"] == "Fix suggestion"
        assert f["location"] == "Section 4.2"
        assert f["regulation_ref"] == "GMP Annex 11"
        assert f["status"] == "pending"

    @pytest.mark.asyncio
    async def test_findings_multiple(self, client: AsyncClient, db_session: AsyncSession):
        task = AuditTask(
            task_name="T", task_type=TaskType.DEVIATION_ANALYSIS, status=TaskStatus.COMPLETED,
        )
        db_session.add(task)
        await db_session.commit()
        await db_session.refresh(task)

        for sev in [SeverityLevel.HIGH, SeverityLevel.MEDIUM, SeverityLevel.LOW]:
            db_session.add(Finding(
                task_id=task.id,
                finding_type=FindingType.COMPLIANCE_RISK,
                severity=sev,
                title=f"{sev.value} Finding",
                description="Desc",
            ))
        await db_session.commit()

        resp = await client.get(f"/api/audit/tasks/{task.id}/findings")
        assert resp.status_code == 200
        assert len(resp.json()) == 3


# ---------------------------------------------------------------------------
# GET /tasks/{id}/risk
# ---------------------------------------------------------------------------


class TestGetTaskRisk:
    @pytest.mark.asyncio
    async def test_risk_no_findings(self, client: AsyncClient, db_session: AsyncSession):
        task = AuditTask(
            task_name="T", task_type=TaskType.DEVIATION_ANALYSIS, status=TaskStatus.COMPLETED,
        )
        db_session.add(task)
        await db_session.commit()
        await db_session.refresh(task)

        resp = await client.get(f"/api/audit/tasks/{task.id}/risk")
        assert resp.status_code == 200
        data = resp.json()
        assert data["risk_level"] == "low"
        assert data["total_findings"] == 0


# ---------------------------------------------------------------------------
# POST /tasks/{id}/run edge cases
# ---------------------------------------------------------------------------


class TestRunAuditTaskEdgeCases:
    @pytest.mark.asyncio
    async def test_run_unprocessed_document_rejected(self, client: AsyncClient, db_session: AsyncSession):
        """Run should reject if document is not PROCESSED."""
        doc = Document(
            filename="raw.pdf",
            file_path="/tmp/raw.pdf",
            file_type="pdf",
            file_size=100,
            process_status=DocumentStatus.UPLOADED,
        )
        db_session.add(doc)
        await db_session.commit()
        await db_session.refresh(doc)

        task = AuditTask(
            task_name="Test",
            task_type=TaskType.DEVIATION_ANALYSIS,
            status=TaskStatus.PENDING,
            document_ids=[doc.id],
        )
        db_session.add(task)
        await db_session.commit()
        await db_session.refresh(task)

        mock_engine = MagicMock()
        mock_engine.adapters = {"deepseek": MagicMock()}
        with (
            patch("app.api.audit.is_agent_available", return_value=True),
            patch("app.services.llm_engine.get_llm_engine", return_value=mock_engine),
        ):
            resp = await client.post(f"/api/audit/tasks/{task.id}/run")
        # Should be 400 (unprocessed) or 400 (LLM not configured) or 503
        assert resp.status_code in (400, 503)

    @pytest.mark.asyncio
    async def test_run_nonexistent_document_rejected(self, client: AsyncClient, db_session: AsyncSession):
        """Run should reject if document ID does not exist."""
        task = AuditTask(
            task_name="Test",
            task_type=TaskType.DEVIATION_ANALYSIS,
            status=TaskStatus.PENDING,
            document_ids=[99999],
        )
        db_session.add(task)
        await db_session.commit()
        await db_session.refresh(task)

        mock_engine = MagicMock()
        mock_engine.adapters = {"deepseek": MagicMock()}
        with (
            patch("app.api.audit.is_agent_available", return_value=True),
            patch("app.services.llm_engine.get_llm_engine", return_value=mock_engine),
        ):
            resp = await client.post(f"/api/audit/tasks/{task.id}/run")
        assert resp.status_code in (400, 404, 503)


# ---------------------------------------------------------------------------
# GET /memory
# ---------------------------------------------------------------------------


class TestGetAuditMemory:
    @pytest.mark.asyncio
    async def test_memory_endpoint(self, client: AsyncClient):
        with patch("app.services.memory.load_memory", return_value=[]):
            resp = await client.get("/api/audit/memory")
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_memory_with_limit(self, client: AsyncClient):
        with patch("app.services.memory.load_memory", return_value=[]):
            resp = await client.get("/api/audit/memory?limit=10")
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Additional config API tests
# ---------------------------------------------------------------------------


class TestConfigEndpointsAdditional:
    @pytest.mark.asyncio
    async def test_update_config_with_description(self, client: AsyncClient):
        resp = await client.put(
            "/api/config/log_level",
            json={"value": "WARNING", "description": "Log verbosity level"},
        )
        assert resp.status_code == 200

        resp = await client.get("/api/config/log_level")
        assert resp.status_code == 200
        data = resp.json()
        assert data["description"] == "Log verbosity level"

    @pytest.mark.asyncio
    async def test_batch_update_with_no_valid_keys(self, client: AsyncClient):
        """Batch with all unknown keys should still succeed (skipped keys)."""
        resp = await client.post(
            "/api/config/batch",
            json={"configs": {"unknown_key_abc": "value"}},
        )
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_update_config_agent_timeout(self, client: AsyncClient):
        resp = await client.put(
            "/api/config/agent_task_timeout",
            json={"value": "300"},
        )
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Additional LLM engine tests
# ---------------------------------------------------------------------------


class TestLLMEngineAdditional:
    @pytest.mark.asyncio
    async def test_engine_analyze_logs_latency(self):
        from app.services.llm_engine import LLMEngine, LLMResponse

        engine = LLMEngine()
        mock_adapter = AsyncMock()
        mock_adapter.chat = AsyncMock(return_value=LLMResponse(
            content="result", model="test", usage={"prompt_tokens": 10}, finish_reason="stop",
        ))
        engine.adapters["test"] = mock_adapter

        result = await engine.analyze("doc", "prompt", model="test")
        assert result.content == "result"

    @pytest.mark.asyncio
    async def test_engine_generate_report_logs_and_returns(self):
        from app.services.llm_engine import LLMEngine, LLMResponse

        engine = LLMEngine()
        mock_adapter = AsyncMock()
        mock_adapter.chat = AsyncMock(return_value=LLMResponse(
            content="# Report", model="test", usage={}, finish_reason="stop",
        ))
        engine.adapters["test"] = mock_adapter

        result = await engine.generate_report(
            [{"severity": "high", "title": "F", "description": "D"}],
            model="test",
        )
        assert result == "# Report"

    def test_get_provider_defaults(self):
        from app.core.providers import get_provider_defaults

        assert get_provider_defaults("deepseek")["base_url"].startswith("https://")
        assert get_provider_defaults("unknown") == {}

    def test_get_provider_names(self):
        from app.core.providers import get_provider_names

        names = get_provider_names()
        assert "deepseek" in names
        assert "anthropic" in names
        assert len(names) == 8

    def test_get_provider_list(self):
        from app.core.providers import get_provider_list

        plist = get_provider_list()
        assert len(plist) == 8
        for p in plist:
            assert "id" in p
            assert "name" in p
            assert "model" in p


# ---------------------------------------------------------------------------
# Audit engine tests
# ---------------------------------------------------------------------------


class TestAuditEngine:
    @pytest.mark.asyncio
    async def test_assess_risk_high(self):
        from app.services.audit_engine import AuditEngine

        engine = AuditEngine()
        findings = [{"severity": "high"}, {"severity": "medium"}, {"severity": "low"}]
        result = await engine.assess_risk(findings)
        assert result["risk_level"] == "high"
        assert result["total_findings"] == 3
        assert result["high_risk"] == 1
        assert result["medium_risk"] == 1
        assert result["low_risk"] == 1

    @pytest.mark.asyncio
    async def test_assess_risk_medium(self):
        from app.services.audit_engine import AuditEngine

        engine = AuditEngine()
        findings = [{"severity": "medium"} for _ in range(5)]
        result = await engine.assess_risk(findings)
        assert result["risk_level"] == "medium"

    @pytest.mark.asyncio
    async def test_assess_risk_low(self):
        from app.services.audit_engine import AuditEngine

        engine = AuditEngine()
        findings = [{"severity": "low"} for _ in range(10)]
        result = await engine.assess_risk(findings)
        assert result["risk_level"] == "low"
        assert result["score"] > 0

    @pytest.mark.asyncio
    async def test_assess_risk_empty(self):
        from app.services.audit_engine import AuditEngine

        engine = AuditEngine()
        result = await engine.assess_risk([])
        assert result["risk_level"] == "low"
        assert result["total_findings"] == 0
        assert result["score"] == 100

    def test_get_audit_engine_singleton(self):
        from app.services.audit_engine import get_audit_engine

        engine1 = get_audit_engine()
        engine2 = get_audit_engine()
        assert engine1 is engine2


# ---------------------------------------------------------------------------
# Agent helpers tests
# ---------------------------------------------------------------------------


class TestAgentHelpers:
    def test_build_initial_state(self):
        from app.utils.agent_helpers import build_initial_state

        state = build_initial_state(
            document_path="/tmp/test.pdf",
            document_type="deviation",
            focus="GMP compliance",
            document_content="Test content",
            document_name="test.pdf",
        )
        assert state["document_name"] == "test.pdf"
        assert state["document_type"] == "deviation"
        assert state["audit_focus"] == "GMP compliance"
        assert state["status"] == "running"
        assert state["findings"] == []

    def test_build_initial_state_defaults(self):
        from app.utils.agent_helpers import build_initial_state

        state = build_initial_state(
            document_path="/tmp/test.pdf",
            document_type="deviation",
        )
        assert state["document_name"] == "/tmp/test.pdf"
        assert state["audit_focus"] == ""

    def test_normalize_finding_high_severity(self):
        from app.utils.agent_helpers import normalize_finding

        finding = normalize_finding(
            {"title": "Issue", "description": "Desc", "severity": "critical", "type": "compliance"},
            task_id=1,
            document_id=2,
        )
        assert finding.severity == SeverityLevel.HIGH
        assert finding.finding_type == FindingType.COMPLIANCE_RISK
        assert finding.task_id == 1
        assert finding.document_id == 2

    def test_normalize_finding_medium_severity(self):
        from app.utils.agent_helpers import normalize_finding

        finding = normalize_finding(
            {"title": "Issue", "description": "Desc", "severity": "medium"},
            task_id=1,
        )
        assert finding.severity == SeverityLevel.MEDIUM

    def test_normalize_finding_low_severity(self):
        from app.utils.agent_helpers import normalize_finding

        finding = normalize_finding(
            {"title": "Issue", "description": "Desc", "severity": "info"},
            task_id=1,
        )
        assert finding.severity == SeverityLevel.LOW

    def test_normalize_finding_type_mapping(self):
        from app.utils.agent_helpers import normalize_finding

        for ftype, expected in [
            ("logic_flaw", FindingType.LOGIC_FLAW),
            ("inconsistency", FindingType.INCONSISTENCY),
            ("missing_info", FindingType.MISSING_INFO),
            ("best_practice", FindingType.BEST_PRACTICE),
            ("compliance_risk", FindingType.COMPLIANCE_RISK),
            ("unknown_type", FindingType.COMPLIANCE_RISK),  # default
        ]:
            finding = normalize_finding(
                {"title": "T", "description": "D", "type": ftype},
                task_id=1,
            )
            assert finding.finding_type == expected, f"type={ftype} should map to {expected}"

    def test_normalize_finding_location_from_source_section(self):
        from app.utils.agent_helpers import normalize_finding

        finding = normalize_finding(
            {"title": "T", "description": "D", "source_section": "4.2.1"},
            task_id=1,
        )
        assert finding.location == "4.2.1"
