import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit_task import AuditTask, TaskStatus, TaskType
from app.models.finding import Finding, FindingType, SeverityLevel
from app.models.report import Report, ReportType

# ---------------------------------------------------------------------------
# List reports
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_reports_empty(client: AsyncClient):
    response = await client.get("/api/reports/")
    assert response.status_code == 200
    data = response.json()
    assert data["items"] == []
    assert data["total"] == 0
    assert data["page"] == 1
    assert data["page_size"] == 20


@pytest.mark.asyncio
async def test_list_reports_with_data(client: AsyncClient, db_session: AsyncSession):
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
        content="Report content",
        report_metadata={"report_source": "agent_report_writer"},
    )
    db_session.add(report)
    await db_session.commit()

    response = await client.get("/api/reports/")
    assert response.status_code == 200
    items = response.json()["items"]
    assert len(items) == 1
    assert items[0]["title"] == "Test Report"
    assert items[0]["report_type"] == "full_report"


@pytest.mark.asyncio
async def test_list_reports_with_task_filter(client: AsyncClient, db_session: AsyncSession):
    t1 = AuditTask(task_name="T1", task_type=TaskType.DEVIATION_ANALYSIS, status=TaskStatus.COMPLETED)
    t2 = AuditTask(task_name="T2", task_type=TaskType.SOP_COMPLIANCE, status=TaskStatus.COMPLETED)
    db_session.add_all([t1, t2])
    await db_session.commit()
    await db_session.refresh(t1)
    await db_session.refresh(t2)

    db_session.add(Report(task_id=t1.id, report_type=ReportType.FULL_REPORT, title="R1", content="C1"))
    db_session.add(Report(task_id=t2.id, report_type=ReportType.FULL_REPORT, title="R2", content="C2"))
    await db_session.commit()

    response = await client.get(f"/api/reports/?task_id={t1.id}")
    assert response.status_code == 200
    reports = response.json()["items"]
    assert len(reports) == 1
    assert reports[0]["task_id"] == t1.id


@pytest.mark.asyncio
async def test_list_reports_pagination(client: AsyncClient, db_session: AsyncSession):
    task = AuditTask(task_name="P", task_type=TaskType.DEVIATION_ANALYSIS, status=TaskStatus.COMPLETED)
    db_session.add(task)
    await db_session.commit()
    await db_session.refresh(task)

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
    assert len(resp.json()["items"]) == 2
    assert resp.json()["total"] == 5


# ---------------------------------------------------------------------------
# Get report
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_report_not_found(client: AsyncClient):
    response = await client.get("/api/reports/999")
    assert response.status_code == 404
    assert response.json()["detail"] == "报告不存在"


@pytest.mark.asyncio
async def test_get_report_detail(client: AsyncClient, db_session: AsyncSession):
    report = Report(
        task_id=1,
        report_type=ReportType.FULL_REPORT,
        title="Detail Report",
        content="Detailed content here",
        report_metadata={"report_mode": "single_document"},
    )
    db_session.add(report)
    await db_session.commit()
    await db_session.refresh(report)

    response = await client.get(f"/api/reports/{report.id}")
    assert response.status_code == 200
    data = response.json()
    assert data["title"] == "Detail Report"
    assert data["content"] == "Detailed content here"
    assert data["report_metadata"]["report_mode"] == "single_document"
    assert data["report_type"] == "full_report"
    assert "created_at" in data


# ---------------------------------------------------------------------------
# Generate report
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_generate_report_no_task(client: AsyncClient):
    response = await client.post("/api/reports/generate/999")
    assert response.status_code == 404
    assert response.json()["detail"] == "任务不存在"


@pytest.mark.asyncio
async def test_generate_report_no_findings(client: AsyncClient):
    task_resp = await client.post(
        "/api/audit/tasks",
        json={"task_name": "Test task", "task_type": "deviation_analysis", "document_ids": []},
    )
    task_id = task_resp.json()["id"]

    response = await client.post(f"/api/reports/generate/{task_id}")
    assert response.status_code == 400
    assert "暂无审计发现" in response.json()["detail"]


@pytest.mark.asyncio
async def test_generate_report_success(client: AsyncClient, db_session: AsyncSession):
    task = AuditTask(
        task_name="Report Task",
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
        title="High Finding",
        description="Critical issue found",
    )
    db_session.add(finding)
    await db_session.commit()

    mock_engine = MagicMock()
    mock_engine.generate_report = AsyncMock(return_value="# Audit Report\nFindings here")

    with patch("app.api.reports.get_llm_engine", return_value=mock_engine):
        response = await client.post(f"/api/reports/generate/{task.id}")

    assert response.status_code == 200
    data = response.json()
    assert "id" in data
    assert "content" in data
    assert data["report_metadata"]["report_source"] == "backend_llm_generate"
    assert data["report_metadata"]["findings_count"] == 1


@pytest.mark.asyncio
async def test_generate_report_llm_timeout(client: AsyncClient, db_session: AsyncSession):
    task = AuditTask(
        task_name="Timeout Task",
        task_type=TaskType.DEVIATION_ANALYSIS,
        status=TaskStatus.COMPLETED,
    )
    db_session.add(task)
    await db_session.commit()
    await db_session.refresh(task)

    db_session.add(
        Finding(
            task_id=task.id,
            finding_type=FindingType.COMPLIANCE_RISK,
            severity=SeverityLevel.HIGH,
            title="F",
            description="D",
        )
    )
    await db_session.commit()

    mock_engine = MagicMock()
    mock_engine.generate_report = AsyncMock(side_effect=asyncio.TimeoutError)

    with patch("app.api.reports.get_llm_engine", return_value=mock_engine):
        resp = await client.post(f"/api/reports/generate/{task.id}")

    assert resp.status_code == 504
    assert "超时" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_generate_report_llm_value_error(client: AsyncClient, db_session: AsyncSession):
    task = AuditTask(
        task_name="ValErr Task",
        task_type=TaskType.DEVIATION_ANALYSIS,
        status=TaskStatus.COMPLETED,
    )
    db_session.add(task)
    await db_session.commit()
    await db_session.refresh(task)

    db_session.add(
        Finding(
            task_id=task.id,
            finding_type=FindingType.COMPLIANCE_RISK,
            severity=SeverityLevel.HIGH,
            title="F",
            description="D",
        )
    )
    await db_session.commit()

    mock_engine = MagicMock()
    mock_engine.generate_report = AsyncMock(side_effect=ValueError("No adapter"))

    with patch("app.api.reports.get_llm_engine", return_value=mock_engine):
        resp = await client.post(f"/api/reports/generate/{task.id}")

    assert resp.status_code == 503
    assert "不可用" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_generate_report_llm_generic_error(client: AsyncClient, db_session: AsyncSession):
    task = AuditTask(
        task_name="Err Task",
        task_type=TaskType.DEVIATION_ANALYSIS,
        status=TaskStatus.COMPLETED,
    )
    db_session.add(task)
    await db_session.commit()
    await db_session.refresh(task)

    db_session.add(
        Finding(
            task_id=task.id,
            finding_type=FindingType.COMPLIANCE_RISK,
            severity=SeverityLevel.HIGH,
            title="F",
            description="D",
        )
    )
    await db_session.commit()

    mock_engine = MagicMock()
    mock_engine.generate_report = AsyncMock(side_effect=RuntimeError("Network error"))

    with patch("app.api.reports.get_llm_engine", return_value=mock_engine):
        resp = await client.post(f"/api/reports/generate/{task.id}")

    assert resp.status_code == 502
    assert "LLM" in resp.json()["detail"]


# ---------------------------------------------------------------------------
# Export HTML
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_export_html_success(client: AsyncClient, db_session: AsyncSession):
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


@pytest.mark.asyncio
async def test_export_html_not_found(client: AsyncClient):
    resp = await client.get("/api/reports/99999/export/html")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_export_html_with_table(client: AsyncClient, db_session: AsyncSession):
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


@pytest.mark.asyncio
async def test_export_html_empty_content(client: AsyncClient, db_session: AsyncSession):
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


@pytest.mark.asyncio
async def test_export_html_empty_title(client: AsyncClient, db_session: AsyncSession):
    """Empty title should be handled gracefully."""
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


@pytest.mark.asyncio
async def test_export_html_sanitizes_script(client: AsyncClient, db_session: AsyncSession):
    """Script tags should be stripped from HTML output."""
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


# ---------------------------------------------------------------------------
# Export PDF
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_export_pdf_not_found(client: AsyncClient):
    resp = await client.get("/api/reports/99999/export/pdf")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_export_pdf_success(client: AsyncClient, db_session: AsyncSession):
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


@pytest.mark.asyncio
async def test_export_pdf_generation_error(client: AsyncClient, db_session: AsyncSession):
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


@pytest.mark.asyncio
async def test_export_pdf_content_disposition(client: AsyncClient, db_session: AsyncSession):
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


@pytest.mark.asyncio
async def test_export_pdf_empty_title(client: AsyncClient, db_session: AsyncSession):
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
