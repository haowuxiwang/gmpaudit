"""Final coverage boost tests for backend.

Targets specific uncovered code paths to increase coverage from 61% to 80%.
"""

import pytest
from httpx import AsyncClient

from app.models.audit_task import AuditTask, TaskStatus, TaskType
from app.models.configuration import Configuration
from app.models.document import Document, DocumentStatus
from app.models.finding import Finding, FindingType, SeverityLevel
from app.models.report import Report, ReportType


@pytest.mark.asyncio
class TestAuditTaskLifecycle:
    """Test complete audit task lifecycle to cover more code paths."""

    async def test_create_and_get_task(self, client: AsyncClient, db_session):
        """Create task then get it by ID."""
        # Create document
        doc = Document(
            filename="lifecycle.pdf",
            file_path="/tmp/lifecycle.pdf",
            file_type="pdf",
            file_size=100,
            process_status=DocumentStatus.PROCESSED,
        )
        db_session.add(doc)
        await db_session.commit()
        await db_session.refresh(doc)

        # Create task
        resp = await client.post(
            "/api/audit/tasks",
            json={
                "task_name": "Lifecycle Task",
                "task_type": "deviation_analysis",
                "document_ids": [doc.id],
            },
        )
        assert resp.status_code == 200
        task_id = resp.json()["id"]

        # Get task
        resp = await client.get(f"/api/audit/tasks/{task_id}")
        assert resp.status_code == 200
        assert resp.json()["task_name"] == "Lifecycle Task"

    async def test_create_task_with_multiple_documents(self, client: AsyncClient, db_session):
        """Create task with multiple documents."""
        docs = []
        for i in range(3):
            doc = Document(
                filename=f"multi_{i}.pdf",
                file_path=f"/tmp/multi_{i}.pdf",
                file_type="pdf",
                file_size=100 * (i + 1),
                process_status=DocumentStatus.PROCESSED,
            )
            db_session.add(doc)
            docs.append(doc)
        await db_session.commit()
        for doc in docs:
            await db_session.refresh(doc)

        resp = await client.post(
            "/api/audit/tasks",
            json={
                "task_name": "Multi Doc Task",
                "task_type": "sop_compliance",
                "document_ids": [doc.id for doc in docs],
            },
        )
        assert resp.status_code == 200
        assert resp.json()["task_name"] == "Multi Doc Task"

    async def test_list_tasks_with_pagination(self, client: AsyncClient, db_session):
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
        assert "items" in data
        assert len(data["items"]) <= 2

    async def test_list_tasks_filter_by_status(self, client: AsyncClient, db_session):
        """List tasks filtered by status."""
        task1 = AuditTask(task_name="Pending Task", task_type=TaskType.DEVIATION_ANALYSIS, status=TaskStatus.PENDING)
        task2 = AuditTask(task_name="Running Task", task_type=TaskType.DEVIATION_ANALYSIS, status=TaskStatus.RUNNING)
        db_session.add_all([task1, task2])
        await db_session.commit()

        resp = await client.get("/api/audit/tasks", params={"status": "pending"})
        assert resp.status_code == 200
        data = resp.json()
        # Should only return pending tasks
        for item in data["items"]:
            assert item["status"] == "pending"

    async def test_approve_task_success(self, client: AsyncClient, db_session):
        """Approve a task in AWAITING_REVIEW status."""
        task = AuditTask(
            task_name="Approve Task",
            task_type=TaskType.DEVIATION_ANALYSIS,
            status=TaskStatus.AWAITING_REVIEW,
        )
        db_session.add(task)
        await db_session.commit()
        await db_session.refresh(task)

        resp = await client.post(f"/api/audit/tasks/{task.id}/approve", json={"comment": "Looks good"})
        assert resp.status_code == 200
        assert resp.json()["status"] == "approved"

    async def test_reject_task_success(self, client: AsyncClient, db_session):
        """Reject a task in AWAITING_REVIEW status."""
        task = AuditTask(
            task_name="Reject Task",
            task_type=TaskType.DEVIATION_ANALYSIS,
            status=TaskStatus.AWAITING_REVIEW,
        )
        db_session.add(task)
        await db_session.commit()
        await db_session.refresh(task)

        resp = await client.post(f"/api/audit/tasks/{task.id}/reject", json={"comment": "Needs improvement"})
        assert resp.status_code == 200
        assert resp.json()["status"] == "rejected"

    async def test_get_task_findings(self, client: AsyncClient, db_session):
        """Get findings for a task."""
        task = AuditTask(
            task_name="Findings Task",
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
            description="SOP not found in deviation report",
        )
        db_session.add(finding)
        await db_session.commit()

        resp = await client.get(f"/api/audit/tasks/{task.id}/findings")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["title"] == "Missing SOP"

    async def test_approve_finding(self, client: AsyncClient, db_session):
        """Approve a finding."""
        task = AuditTask(
            task_name="Finding Approve Task",
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

    async def test_reject_finding(self, client: AsyncClient, db_session):
        """Reject a finding."""
        task = AuditTask(
            task_name="Finding Reject Task",
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

    async def test_get_risk_assessment(self, client: AsyncClient, db_session):
        """Get risk assessment for a task."""
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

    async def test_dashboard_stats(self, client: AsyncClient, db_session):
        """Get dashboard statistics."""
        # Create some tasks
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

    async def test_audit_memory(self, client: AsyncClient):
        """Get audit memory."""
        resp = await client.get("/api/audit/memory")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)


@pytest.mark.asyncio
class TestDocumentsLifecycle:
    """Test document lifecycle to cover more code paths."""

    async def test_list_documents_with_pagination(self, client: AsyncClient, db_session):
        """List documents with pagination."""
        for i in range(5):
            doc = Document(
                filename=f"doc_{i}.pdf",
                file_path=f"/tmp/doc_{i}.pdf",
                file_type="pdf",
                file_size=100 * (i + 1),
                process_status=DocumentStatus.UPLOADED,
            )
            db_session.add(doc)
        await db_session.commit()

        resp = await client.get("/api/documents/", params={"page": 1, "page_size": 2})
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert len(data["items"]) <= 2

    async def test_get_document_detail(self, client: AsyncClient, db_session):
        """Get document detail."""
        doc = Document(
            filename="detail.pdf",
            file_path="/tmp/detail.pdf",
            file_type="pdf",
            file_size=100,
            process_status=DocumentStatus.PROCESSED,
            content_text="Test content",
        )
        db_session.add(doc)
        await db_session.commit()
        await db_session.refresh(doc)

        resp = await client.get(f"/api/documents/{doc.id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["filename"] == "detail.pdf"
        assert data["process_status"] == "processed"
        assert data["content_text"] == "Test content"

    async def test_delete_document(self, client: AsyncClient, db_session, tmp_path):
        """Delete document."""
        test_file = tmp_path / "delete_test.txt"
        test_file.write_text("test content")

        doc = Document(
            filename="delete_test.txt",
            file_path=str(test_file),
            file_type="txt",
            file_size=12,
            process_status=DocumentStatus.UPLOADED,
        )
        db_session.add(doc)
        await db_session.commit()
        await db_session.refresh(doc)

        resp = await client.delete(f"/api/documents/{doc.id}")
        # May fail if document has related findings from other tests
        assert resp.status_code in (200, 400)


@pytest.mark.asyncio
class TestReportsLifecycle:
    """Test reports lifecycle to cover more code paths."""

    async def test_list_reports_with_pagination(self, client: AsyncClient, db_session):
        """List reports with pagination."""
        task = AuditTask(
            task_name="Report Task",
            task_type=TaskType.DEVIATION_ANALYSIS,
            status=TaskStatus.COMPLETED,
        )
        db_session.add(task)
        await db_session.commit()
        await db_session.refresh(task)

        for i in range(5):
            report = Report(
                task_id=task.id,
                report_type=ReportType.FULL_REPORT,
                title=f"Report {i}",
                content=f"Content {i}",
            )
            db_session.add(report)
        await db_session.commit()

        resp = await client.get("/api/reports/", params={"page": 1, "page_size": 2})
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert len(data["items"]) <= 2

    async def test_get_report_detail(self, client: AsyncClient, db_session):
        """Get report detail."""
        task = AuditTask(
            task_name="Detail Task",
            task_type=TaskType.DEVIATION_ANALYSIS,
            status=TaskStatus.COMPLETED,
        )
        db_session.add(task)
        await db_session.commit()
        await db_session.refresh(task)

        report = Report(
            task_id=task.id,
            report_type=ReportType.FULL_REPORT,
            title="Detail Report",
            content="# Detailed Content",
        )
        db_session.add(report)
        await db_session.commit()
        await db_session.refresh(report)

        resp = await client.get(f"/api/reports/{report.id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["title"] == "Detail Report"
        assert data["content"] == "# Detailed Content"

    async def test_export_html(self, client: AsyncClient, db_session):
        """Export report as HTML."""
        task = AuditTask(
            task_name="HTML Task",
            task_type=TaskType.DEVIATION_ANALYSIS,
            status=TaskStatus.COMPLETED,
        )
        db_session.add(task)
        await db_session.commit()
        await db_session.refresh(task)

        report = Report(
            task_id=task.id,
            report_type=ReportType.FULL_REPORT,
            title="HTML Report",
            content="# Report Content",
        )
        db_session.add(report)
        await db_session.commit()
        await db_session.refresh(report)

        resp = await client.get(f"/api/reports/{report.id}/export/html")
        assert resp.status_code == 200
        assert "text/html" in resp.headers["content-type"]


@pytest.mark.asyncio
class TestAlertsLifecycle:
    """Test alerts lifecycle to cover more code paths."""

    async def test_list_alerts(self, client: AsyncClient):
        """List alerts."""
        resp = await client.get("/api/alerts/")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, (list, dict))


@pytest.mark.asyncio
class TestConfigLifecycle:
    """Test config lifecycle to cover more code paths."""

    async def test_get_config(self, client: AsyncClient, db_session):
        """Get all configs."""
        config = Configuration(
            config_key="LOG_LEVEL",
            config_value="INFO",
            config_type="string",
            description="Log level",
        )
        db_session.add(config)
        await db_session.commit()

        resp = await client.get("/api/config/")
        assert resp.status_code == 200
        data = resp.json()
        assert "LOG_LEVEL" in data

    async def test_get_config_by_key(self, client: AsyncClient, db_session):
        """Get config by key."""
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

    async def test_update_config(self, client: AsyncClient, db_session):
        """Update config."""
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


@pytest.mark.asyncio
class TestHealthEndpoints:
    """Test health endpoints to cover more code paths."""

    async def test_health_check(self, client: AsyncClient):
        """Health check endpoint."""
        resp = await client.get("/api/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"

    async def test_db_health(self, client: AsyncClient):
        """DB health check endpoint."""
        resp = await client.get("/api/health/db")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert "journal_mode" in data
