"""Comprehensive tests for audit API to cover uncovered code paths.

Targets specific uncovered lines in audit.py to increase coverage from 35% to 80%.
"""

from unittest.mock import patch

import pytest
from httpx import AsyncClient

from app.models.audit_task import AuditTask, TaskStatus, TaskType
from app.models.document import Document, DocumentStatus
from app.models.finding import Finding, FindingType, SeverityLevel


@pytest.mark.asyncio
class TestAuditTaskCreate:
    """Test POST /audit/tasks endpoint."""

    async def test_create_task_success(self, client: AsyncClient, db_session):
        """Create task with valid data."""
        doc = Document(
            filename="test.pdf",
            file_path="/tmp/test.pdf",
            file_type="pdf",
            file_size=100,
            process_status=DocumentStatus.PROCESSED,
        )
        db_session.add(doc)
        await db_session.commit()
        await db_session.refresh(doc)

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
        assert "id" in data

    async def test_create_task_invalid_type(self, client: AsyncClient):
        """Create task with invalid type."""
        resp = await client.post(
            "/api/audit/tasks",
            json={
                "task_name": "Bad Task",
                "task_type": "invalid_type",
                "document_ids": [],
            },
        )
        assert resp.status_code in (400, 422)


@pytest.mark.asyncio
class TestAuditTaskList:
    """Test GET /audit/tasks endpoint."""

    async def test_list_empty(self, client: AsyncClient):
        """List tasks when empty."""
        resp = await client.get("/api/audit/tasks")
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert "total" in data
        assert "page" in data
        assert "page_size" in data

    async def test_list_with_tasks(self, client: AsyncClient, db_session):
        """List tasks with data."""
        task = AuditTask(
            task_name="List Task",
            task_type=TaskType.DEVIATION_ANALYSIS,
            status=TaskStatus.PENDING,
        )
        db_session.add(task)
        await db_session.commit()

        resp = await client.get("/api/audit/tasks")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1
        assert len(data["items"]) >= 1

    async def test_list_with_pagination(self, client: AsyncClient, db_session):
        """List tasks with pagination."""
        for i in range(5):
            task = AuditTask(
                task_name=f"Pagination Task {i}",
                task_type=TaskType.DEVIATION_ANALYSIS,
                status=TaskStatus.PENDING,
            )
            db_session.add(task)
        await db_session.commit()

        resp = await client.get("/api/audit/tasks", params={"page": 1, "page_size": 2})
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["items"]) <= 2
        assert data["total"] >= 5

    async def test_list_filter_by_status(self, client: AsyncClient, db_session):
        """List tasks filtered by status."""
        task1 = AuditTask(task_name="Pending", task_type=TaskType.DEVIATION_ANALYSIS, status=TaskStatus.PENDING)
        task2 = AuditTask(task_name="Running", task_type=TaskType.DEVIATION_ANALYSIS, status=TaskStatus.RUNNING)
        db_session.add_all([task1, task2])
        await db_session.commit()

        resp = await client.get("/api/audit/tasks", params={"status": "pending"})
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["status"] == "pending"


@pytest.mark.asyncio
class TestAuditTaskDetail:
    """Test GET /audit/tasks/{task_id} endpoint."""

    async def test_get_task(self, client: AsyncClient, db_session):
        """Get task by ID."""
        task = AuditTask(
            task_name="Detail Task",
            task_type=TaskType.SOP_COMPLIANCE,
            status=TaskStatus.COMPLETED,
        )
        db_session.add(task)
        await db_session.commit()
        await db_session.refresh(task)

        resp = await client.get(f"/api/audit/tasks/{task.id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["task_name"] == "Detail Task"
        assert data["status"] == "completed"
        assert "document_ids" in data

    async def test_get_nonexistent_task(self, client: AsyncClient):
        """Get nonexistent task."""
        resp = await client.get("/api/audit/tasks/99999")
        assert resp.status_code == 404


@pytest.mark.asyncio
class TestAuditTaskRun:
    """Test POST /audit/tasks/{task_id}/run endpoint."""

    async def test_run_task_agent_unavailable(self, client: AsyncClient, db_session):
        """Run task when agent is unavailable."""
        task = AuditTask(
            task_name="Run Task",
            task_type=TaskType.DEVIATION_ANALYSIS,
            status=TaskStatus.PENDING,
        )
        db_session.add(task)
        await db_session.commit()
        await db_session.refresh(task)

        with patch("app.api.audit.is_agent_available", return_value=False):
            resp = await client.post(f"/api/audit/tasks/{task.id}/run")
            assert resp.status_code == 503

    async def test_run_task_not_found(self, client: AsyncClient):
        """Run nonexistent task."""
        with patch("app.api.audit.is_agent_available", return_value=False):
            resp = await client.post("/api/audit/tasks/99999/run")
            assert resp.status_code == 503


@pytest.mark.asyncio
class TestAuditTaskCancel:
    """Test POST /audit/tasks/{task_id}/cancel endpoint."""

    async def test_cancel_task_not_found(self, client: AsyncClient):
        """Cancel nonexistent task."""
        resp = await client.post("/api/audit/tasks/99999/cancel")
        assert resp.status_code == 404

    async def test_cancel_task_not_running(self, client: AsyncClient, db_session):
        """Cancel task that's not running."""
        task = AuditTask(
            task_name="Cancel Task",
            task_type=TaskType.DEVIATION_ANALYSIS,
            status=TaskStatus.PENDING,
        )
        db_session.add(task)
        await db_session.commit()
        await db_session.refresh(task)

        resp = await client.post(f"/api/audit/tasks/{task.id}/cancel")
        assert resp.status_code == 400


@pytest.mark.asyncio
class TestAuditTaskApproveReject:
    """Test POST /audit/tasks/{task_id}/approve and /reject endpoints."""

    async def test_approve_task_not_found(self, client: AsyncClient):
        """Approve nonexistent task."""
        resp = await client.post("/api/audit/tasks/99999/approve", json={"comment": "ok"})
        assert resp.status_code == 404

    async def test_approve_task_not_in_review(self, client: AsyncClient, db_session):
        """Approve task not in review state."""
        task = AuditTask(
            task_name="Approve Task",
            task_type=TaskType.DEVIATION_ANALYSIS,
            status=TaskStatus.PENDING,
        )
        db_session.add(task)
        await db_session.commit()
        await db_session.refresh(task)

        resp = await client.post(f"/api/audit/tasks/{task.id}/approve", json={"comment": "ok"})
        assert resp.status_code == 400

    async def test_approve_task_success(self, client: AsyncClient, db_session):
        """Approve task in AWAITING_REVIEW status."""
        task = AuditTask(
            task_name="Review Task",
            task_type=TaskType.DEVIATION_ANALYSIS,
            status=TaskStatus.AWAITING_REVIEW,
        )
        db_session.add(task)
        await db_session.commit()
        await db_session.refresh(task)

        resp = await client.post(f"/api/audit/tasks/{task.id}/approve", json={"comment": "Looks good"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "approved"
        assert data["task_id"] == task.id

    async def test_reject_task_not_found(self, client: AsyncClient):
        """Reject nonexistent task."""
        resp = await client.post("/api/audit/tasks/99999/reject", json={"comment": "bad"})
        assert resp.status_code == 404

    async def test_reject_task_not_in_review(self, client: AsyncClient, db_session):
        """Reject task not in review state."""
        task = AuditTask(
            task_name="Reject Task",
            task_type=TaskType.DEVIATION_ANALYSIS,
            status=TaskStatus.PENDING,
        )
        db_session.add(task)
        await db_session.commit()
        await db_session.refresh(task)

        resp = await client.post(f"/api/audit/tasks/{task.id}/reject", json={"comment": "bad"})
        assert resp.status_code == 400

    async def test_reject_task_success(self, client: AsyncClient, db_session):
        """Reject task in AWAITING_REVIEW status."""
        task = AuditTask(
            task_name="Reject Review",
            task_type=TaskType.DEVIATION_ANALYSIS,
            status=TaskStatus.AWAITING_REVIEW,
        )
        db_session.add(task)
        await db_session.commit()
        await db_session.refresh(task)

        resp = await client.post(f"/api/audit/tasks/{task.id}/reject", json={"comment": "Needs work"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "rejected"


@pytest.mark.asyncio
class TestAuditTaskFindings:
    """Test GET /audit/tasks/{task_id}/findings endpoint."""

    async def test_get_findings_empty(self, client: AsyncClient, db_session):
        """Get findings for task with no findings."""
        task = AuditTask(
            task_name="No Findings",
            task_type=TaskType.DEVIATION_ANALYSIS,
            status=TaskStatus.COMPLETED,
        )
        db_session.add(task)
        await db_session.commit()
        await db_session.refresh(task)

        resp = await client.get(f"/api/audit/tasks/{task.id}/findings")
        assert resp.status_code == 200
        assert resp.json() == []

    async def test_get_findings_with_data(self, client: AsyncClient, db_session):
        """Get findings for task with findings."""
        task = AuditTask(
            task_name="With Findings",
            task_type=TaskType.DEVIATION_ANALYSIS,
            status=TaskStatus.COMPLETED,
        )
        db_session.add(task)
        await db_session.commit()
        await db_session.refresh(task)

        finding = Finding(
            task_id=task.id,
            finding_type=FindingType.COMPLIANCE_RISK,
            severity=SeverityLevel.HIGH,
            title="Missing SOP",
            description="SOP not found",
        )
        db_session.add(finding)
        await db_session.commit()

        resp = await client.get(f"/api/audit/tasks/{task.id}/findings")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["title"] == "Missing SOP"
        assert data[0]["severity"] == "high"


@pytest.mark.asyncio
class TestFindingApproveReject:
    """Test POST /audit/findings/{finding_id}/approve and /reject endpoints."""

    async def test_approve_finding_not_found(self, client: AsyncClient):
        """Approve nonexistent finding."""
        resp = await client.post("/api/audit/findings/99999/approve", json={"comment": "ok"})
        assert resp.status_code == 404

    async def test_approve_finding_success(self, client: AsyncClient, db_session):
        """Approve finding."""
        task = AuditTask(
            task_name="Finding Task",
            task_type=TaskType.DEVIATION_ANALYSIS,
            status=TaskStatus.COMPLETED,
        )
        db_session.add(task)
        await db_session.commit()
        await db_session.refresh(task)

        finding = Finding(
            task_id=task.id,
            finding_type=FindingType.COMPLIANCE_RISK,
            severity=SeverityLevel.HIGH,
            title="Test Finding",
            description="Test description",
        )
        db_session.add(finding)
        await db_session.commit()
        await db_session.refresh(finding)

        resp = await client.post(f"/api/audit/findings/{finding.id}/approve", json={"comment": "approved"})
        assert resp.status_code == 200
        assert resp.json()["status"] == "approved"

    async def test_reject_finding_not_found(self, client: AsyncClient):
        """Reject nonexistent finding."""
        resp = await client.post("/api/audit/findings/99999/reject", json={"comment": "bad"})
        assert resp.status_code == 404

    async def test_reject_finding_success(self, client: AsyncClient, db_session):
        """Reject finding."""
        task = AuditTask(
            task_name="Finding Reject",
            task_type=TaskType.DEVIATION_ANALYSIS,
            status=TaskStatus.COMPLETED,
        )
        db_session.add(task)
        await db_session.commit()
        await db_session.refresh(task)

        finding = Finding(
            task_id=task.id,
            finding_type=FindingType.COMPLIANCE_RISK,
            severity=SeverityLevel.MEDIUM,
            title="Test Finding",
            description="Test description",
        )
        db_session.add(finding)
        await db_session.commit()
        await db_session.refresh(finding)

        resp = await client.post(f"/api/audit/findings/{finding.id}/reject", json={"comment": "rejected"})
        assert resp.status_code == 200
        assert resp.json()["status"] == "rejected"


@pytest.mark.asyncio
class TestAuditTaskRisk:
    """Test GET /audit/tasks/{task_id}/risk endpoint."""

    async def test_get_risk_assessment(self, client: AsyncClient, db_session):
        """Get risk assessment for task."""
        task = AuditTask(
            task_name="Risk Task",
            task_type=TaskType.DEVIATION_ANALYSIS,
            status=TaskStatus.COMPLETED,
        )
        db_session.add(task)
        await db_session.commit()
        await db_session.refresh(task)

        resp = await client.get(f"/api/audit/tasks/{task.id}/risk")
        assert resp.status_code == 200
        data = resp.json()
        assert "risk_level" in data
        assert "total_findings" in data
        assert "high_risk" in data
        assert "medium_risk" in data
        assert "low_risk" in data
        assert "score" in data


@pytest.mark.asyncio
class TestDashboard:
    """Test GET /audit/dashboard endpoint."""

    async def test_dashboard_stats(self, client: AsyncClient, db_session):
        """Get dashboard statistics."""
        task1 = AuditTask(task_name="Task 1", task_type=TaskType.DEVIATION_ANALYSIS, status=TaskStatus.COMPLETED)
        task2 = AuditTask(task_name="Task 2", task_type=TaskType.SOP_COMPLIANCE, status=TaskStatus.PENDING)
        db_session.add_all([task1, task2])
        await db_session.commit()

        resp = await client.get("/api/audit/dashboard")
        assert resp.status_code == 200
        data = resp.json()
        assert "task_counts" in data
        assert "severity_counts" in data
        assert "total_tasks" in data
        assert "total_findings" in data
        assert data["total_tasks"] >= 2


@pytest.mark.asyncio
class TestAuditMemory:
    """Test GET /audit/memory endpoint."""

    async def test_get_memory(self, client: AsyncClient):
        """Get audit memory."""
        resp = await client.get("/api/audit/memory")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    async def test_get_memory_with_limit(self, client: AsyncClient):
        """Get audit memory with limit."""
        resp = await client.get("/api/audit/memory", params={"limit": 10})
        assert resp.status_code == 200
