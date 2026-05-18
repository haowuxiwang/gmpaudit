from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit_task import AuditTask, TaskStatus, TaskType
from app.models.finding import Finding, FindingType, SeverityLevel
from app.models.report import Report, ReportType


@pytest.mark.asyncio
async def test_list_reports_empty(client: AsyncClient):
    response = await client.get("/api/reports/")
    assert response.status_code == 200
    data = response.json()
    assert data["items"] == []
    assert data["total"] == 0


@pytest.mark.asyncio
async def test_get_report_not_found(client: AsyncClient):
    response = await client.get("/api/reports/999")
    assert response.status_code == 404
    assert response.json()["detail"] == "Report not found"


@pytest.mark.asyncio
async def test_generate_report_no_task(client: AsyncClient):
    response = await client.post("/api/reports/generate/999")
    assert response.status_code == 404
    assert response.json()["detail"] == "Task not found"


@pytest.mark.asyncio
async def test_generate_report_no_findings(client: AsyncClient):
    task_resp = await client.post(
        "/api/audit/tasks",
        json={
            "task_name": "Test task",
            "task_type": "deviation_analysis",
            "document_ids": [],
        },
    )
    task_id = task_resp.json()["id"]

    response = await client.post(f"/api/reports/generate/{task_id}")
    assert response.status_code == 400
    assert "No findings available" in response.json()["detail"]


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


@pytest.mark.asyncio
async def test_list_reports_with_filter(client: AsyncClient, db_session: AsyncSession):
    task = AuditTask(
        task_name="Filter Task",
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

    response = await client.get(f"/api/reports/?task_id={task.id}")
    assert response.status_code == 200
    reports = response.json()["items"]
    assert len(reports) == 1
    assert reports[0]["report_metadata"]["report_source"] == "agent_report_writer"


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
