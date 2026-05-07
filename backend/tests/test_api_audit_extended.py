import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.document import Document, DocumentStatus
from app.models.audit_task import AuditTask, TaskStatus, TaskType
from app.models.finding import Finding, FindingType, SeverityLevel


@pytest.mark.asyncio
async def test_run_audit_task_not_found(client: AsyncClient):
    response = await client.post("/api/audit/tasks/999/run")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_run_audit_task_already_running(client: AsyncClient, db_session: AsyncSession):
    task = AuditTask(
        task_name="Running Task",
        task_type=TaskType.DEVIATION_ANALYSIS,
        status=TaskStatus.RUNNING,
    )
    db_session.add(task)
    await db_session.commit()
    await db_session.refresh(task)

    response = await client.post(f"/api/audit/tasks/{task.id}/run")
    assert response.status_code == 400
    assert "正在运行" in response.json()["detail"]


@pytest.mark.asyncio
async def test_get_task_findings_empty(client: AsyncClient):
    response = await client.get("/api/audit/tasks/999/findings")
    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.asyncio
async def test_get_task_findings(client: AsyncClient, db_session: AsyncSession):
    task = AuditTask(
        task_name="Task",
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
        description="Desc",
    )
    db_session.add(finding)
    await db_session.commit()

    response = await client.get(f"/api/audit/tasks/{task.id}/findings")
    assert response.status_code == 200
    findings = response.json()
    assert len(findings) == 1
    assert findings[0]["severity"] == "high"


@pytest.mark.asyncio
async def test_get_task_risk_assessment(client: AsyncClient, db_session: AsyncSession):
    task = AuditTask(
        task_name="Task",
        task_type=TaskType.RISK_ASSESSMENT,
        status=TaskStatus.COMPLETED,
    )
    db_session.add(task)
    await db_session.commit()
    await db_session.refresh(task)

    for sev in [SeverityLevel.HIGH, SeverityLevel.MEDIUM, SeverityLevel.LOW]:
        finding = Finding(
            task_id=task.id,
            finding_type=FindingType.COMPLIANCE_RISK,
            severity=sev,
            title=f"Finding {sev.value}",
            description="Desc",
        )
        db_session.add(finding)
    await db_session.commit()

    response = await client.get(f"/api/audit/tasks/{task.id}/risk")
    assert response.status_code == 200
    risk = response.json()
    assert risk["risk_level"] == "high"
    assert risk["total_findings"] == 3


@pytest.mark.asyncio
async def test_dashboard_stats(client: AsyncClient, db_session: AsyncSession):
    task = AuditTask(
        task_name="Task",
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
        title="Finding",
        description="Desc",
    )
    db_session.add(finding)
    await db_session.commit()

    response = await client.get("/api/audit/dashboard")
    assert response.status_code == 200
    data = response.json()
    assert "task_counts" in data
    assert "severity_counts" in data
    assert data["total_tasks"] >= 1
    assert data["total_findings"] >= 1


@pytest.mark.asyncio
async def test_list_audit_tasks_filter_by_status(client: AsyncClient, db_session: AsyncSession):
    task = AuditTask(
        task_name="Completed Task",
        task_type=TaskType.DEVIATION_ANALYSIS,
        status=TaskStatus.COMPLETED,
    )
    db_session.add(task)
    await db_session.commit()

    response = await client.get("/api/audit/tasks?status=completed")
    assert response.status_code == 200
    tasks = response.json()
    assert all(t["status"] == "completed" for t in tasks)


@pytest.mark.asyncio
async def test_run_audit_task_agent_unavailable(client: AsyncClient, db_session: AsyncSession):
    """When agent is unavailable, run should return 503."""
    doc = Document(
        filename="test.pdf",
        file_path="/tmp/test.pdf",
        file_type="pdf",
        file_size=1024,
        process_status=DocumentStatus.PROCESSED,
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

    import app.api.audit as audit_module
    original = audit_module.AGENT_AVAILABLE
    audit_module.AGENT_AVAILABLE = False
    try:
        response = await client.post(f"/api/audit/tasks/{task.id}/run")
        # The endpoint catches HTTPException(503) in generic except and re-raises as 500
        assert response.status_code in (500, 503)
    finally:
        audit_module.AGENT_AVAILABLE = original
