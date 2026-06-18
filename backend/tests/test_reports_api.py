"""Comprehensive tests for app.api.reports module.

Targets uncovered code paths to increase coverage.
"""

import pytest
from httpx import AsyncClient
from unittest.mock import patch, AsyncMock, MagicMock

from app.models.audit_task import AuditTask, TaskStatus, TaskType
from app.models.finding import Finding, FindingType, SeverityLevel
from app.models.report import Report, ReportType


@pytest.mark.asyncio
class TestReportsList:
    """Tests for GET /reports/ endpoint."""

    async def test_list_reports_empty(self, client: AsyncClient):
        """GET /reports/ with no reports returns empty list."""
        resp = await client.get("/api/reports/")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, dict)
        assert "items" in data
        assert data["items"] == []
        assert data["total"] == 0

    async def test_list_reports_with_data(self, client: AsyncClient, db_session):
        """GET /reports/ returns reports from DB."""
        task = AuditTask(
            task_name="Report Task",
            task_type=TaskType.DEVIATION_ANALYSIS,
            status=TaskStatus.COMPLETED,
        )
        db_session.add(task)
        await db_session.commit()
        await db_session.refresh(task)

        report = Report(
            task_id=task.id,
            report_type=ReportType.FULL_REPORT,
            title="Test Report",
            content="# Report content",
        )
        db_session.add(report)
        await db_session.commit()

        resp = await client.get("/api/reports/")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["items"]) == 1
        assert data["items"][0]["title"] == "Test Report"

    async def test_list_reports_with_pagination(self, client: AsyncClient, db_session):
        """GET /reports/ supports pagination."""
        task = AuditTask(
            task_name="Pagination Task",
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
        assert len(data["items"]) == 2
        assert data["total"] == 5

    async def test_list_reports_filter_by_task(self, client: AsyncClient, db_session):
        """GET /reports/?task_id=X filters by task."""
        task1 = AuditTask(task_name="Task 1", task_type=TaskType.DEVIATION_ANALYSIS, status=TaskStatus.COMPLETED)
        task2 = AuditTask(task_name="Task 2", task_type=TaskType.SOP_COMPLIANCE, status=TaskStatus.COMPLETED)
        db_session.add_all([task1, task2])
        await db_session.commit()
        await db_session.refresh(task1)
        await db_session.refresh(task2)

        report1 = Report(task_id=task1.id, report_type=ReportType.FULL_REPORT, title="Report 1", content="C1")
        report2 = Report(task_id=task2.id, report_type=ReportType.FULL_REPORT, title="Report 2", content="C2")
        db_session.add_all([report1, report2])
        await db_session.commit()

        resp = await client.get("/api/reports/", params={"task_id": task1.id})
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["items"]) == 1
        assert data["items"][0]["title"] == "Report 1"


@pytest.mark.asyncio
class TestReportDetail:
    """Tests for GET /reports/{report_id} endpoint."""

    async def test_get_report(self, client: AsyncClient, db_session):
        """GET /reports/{id} returns report detail."""
        task = AuditTask(task_name="Detail Task", task_type=TaskType.DEVIATION_ANALYSIS, status=TaskStatus.COMPLETED)
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
        assert data["report_type"] == "full_report"

    async def test_get_report_not_found(self, client: AsyncClient):
        """GET /reports/{id} returns 404 for unknown report."""
        resp = await client.get("/api/reports/99999")
        assert resp.status_code == 404


@pytest.mark.asyncio
class TestReportGenerate:
    """Tests for POST /reports/generate/{task_id} endpoint."""

    async def test_generate_report_task_not_found(self, client: AsyncClient):
        """POST /reports/generate/{task_id} returns 404 for unknown task."""
        resp = await client.post("/api/reports/generate/99999")
        assert resp.status_code == 404

    async def test_generate_report_no_findings(self, client: AsyncClient, db_session):
        """POST /reports/generate/{task_id} returns 400 when no findings."""
        task = AuditTask(task_name="No Findings", task_type=TaskType.DEVIATION_ANALYSIS, status=TaskStatus.COMPLETED)
        db_session.add(task)
        await db_session.commit()
        await db_session.refresh(task)

        resp = await client.post(f"/api/reports/generate/{task.id}")
        assert resp.status_code == 400

    async def test_generate_report_success(self, client: AsyncClient, db_session):
        """POST /reports/generate/{task_id} generates report with LLM."""
        task = AuditTask(task_name="Generate Task", task_type=TaskType.DEVIATION_ANALYSIS, status=TaskStatus.COMPLETED)
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

        with patch("app.api.reports.get_llm_engine") as mock_engine:
            mock_llm = AsyncMock()
            mock_llm.generate_report = AsyncMock(return_value="# Generated Report")
            mock_engine.return_value = mock_llm

            resp = await client.post(f"/api/reports/generate/{task.id}")
            assert resp.status_code == 200
            data = resp.json()
            assert data["title"] == "Audit Report - Generate Task"
            assert data["content"] == "# Generated Report"


@pytest.mark.asyncio
class TestReportExport:
    """Tests for report export endpoints."""

    async def test_export_html(self, client: AsyncClient, db_session):
        """GET /reports/{id}/export/html returns HTML."""
        task = AuditTask(task_name="HTML Task", task_type=TaskType.DEVIATION_ANALYSIS, status=TaskStatus.COMPLETED)
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
        assert "HTML Report" in resp.text

    async def test_export_html_not_found(self, client: AsyncClient):
        """GET /reports/{id}/export/html returns 404 for unknown report."""
        resp = await client.get("/api/reports/99999/export/html")
        assert resp.status_code == 404

    async def test_export_pdf(self, client: AsyncClient, db_session):
        """GET /reports/{id}/export/pdf returns PDF."""
        task = AuditTask(task_name="PDF Task", task_type=TaskType.DEVIATION_ANALYSIS, status=TaskStatus.COMPLETED)
        db_session.add(task)
        await db_session.commit()
        await db_session.refresh(task)

        report = Report(
            task_id=task.id,
            report_type=ReportType.FULL_REPORT,
            title="PDF Report",
            content="# Report Content",
        )
        db_session.add(report)
        await db_session.commit()
        await db_session.refresh(report)

        resp = await client.get(f"/api/reports/{report.id}/export/pdf")
        assert resp.status_code == 200
        assert resp.headers["content-type"] == "application/pdf"

    async def test_export_pdf_not_found(self, client: AsyncClient):
        """GET /reports/{id}/export/pdf returns 404 for unknown report."""
        resp = await client.get("/api/reports/99999/export/pdf")
        assert resp.status_code == 404


class TestSanitizeHtml:
    """Tests for _sanitize_html helper."""

    def test_sanitize_allows_safe_tags(self):
        from app.api.reports import _sanitize_html
        html = "<h1>Title</h1><p>Content</p><strong>Bold</strong>"
        result = _sanitize_html(html)
        assert "<h1>" in result
        assert "<p>" in result
        assert "<strong>" in result

    def test_sanitize_strips_script_tags(self):
        from app.api.reports import _sanitize_html
        html = '<p>Safe</p><script>alert("xss")</script>'
        result = _sanitize_html(html)
        assert "<script>" not in result
        assert "Safe" in result

    def test_sanitize_strips_iframe_tags(self):
        from app.api.reports import _sanitize_html
        html = '<p>Content</p><iframe src="evil.com"></iframe>'
        result = _sanitize_html(html)
        assert "<iframe>" not in result
        assert "Content" in result
