import json
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit_task import AuditTask, TaskStatus, TaskType
from app.models.document import Document, DocumentStatus
from app.models.finding import Finding, FindingStatus, FindingType, SeverityLevel
from app.models.report import Report, ReportType
from app.models.risk_alert import AlertLevel, AlertStatus, RiskAlert


# ---------------------------------------------------------------------------
# Basic CRUD
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_create_audit_task(client: AsyncClient):
    task_data = {"task_name": "测试审计任务", "task_type": "deviation_analysis", "document_ids": []}
    response = await client.post("/api/audit/tasks", json=task_data)
    assert response.status_code == 200
    data = response.json()
    assert "id" in data
    assert data["task_name"] == "测试审计任务"
    assert data["status"] == "pending"


@pytest.mark.asyncio
async def test_create_audit_task_with_doc_ids(client: AsyncClient, db_session: AsyncSession):
    task_data = {
        "task_name": "带文档任务",
        "task_type": "sop_compliance",
        "document_ids": [1, 2, 3],
    }
    response = await client.post("/api/audit/tasks", json=task_data)
    assert response.status_code == 200
    data = response.json()
    assert data["task_name"] == "带文档任务"


@pytest.mark.asyncio
async def test_create_audit_task_consistency_check(client: AsyncClient):
    task_data = {
        "task_name": "一致性检查",
        "task_type": "consistency_check",
        "document_ids": [],
    }
    response = await client.post("/api/audit/tasks", json=task_data)
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_list_audit_tasks(client: AsyncClient):
    response = await client.get("/api/audit/tasks")
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert isinstance(data["items"], list)
    assert "total" in data
    assert "page" in data
    assert "page_size" in data


@pytest.mark.asyncio
async def test_get_audit_task(client: AsyncClient):
    task_data = {"task_name": "测试审计任务", "task_type": "deviation_analysis", "document_ids": []}
    create_response = await client.post("/api/audit/tasks", json=task_data)
    task_id = create_response.json()["id"]

    response = await client.get(f"/api/audit/tasks/{task_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == task_id
    assert data["task_name"] == "测试审计任务"
    assert "document_ids" in data


@pytest.mark.asyncio
async def test_get_nonexistent_task(client: AsyncClient):
    response = await client.get("/api/audit/tasks/999")
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# List tasks with findings_counts and report_ids (N+1 avoidance path)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_list_tasks_with_findings_and_reports(client: AsyncClient, db_session: AsyncSession):
    """Ensure the batch-load path (findings_counts, report_ids) is exercised."""
    task = AuditTask(
        task_name="Full Task",
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
        title="Finding 1",
        description="Desc",
    )
    db_session.add(finding)

    report = Report(
        task_id=task.id,
        report_type=ReportType.FULL_REPORT,
        title="Report 1",
        content="Content",
    )
    db_session.add(report)
    await db_session.commit()

    response = await client.get("/api/audit/tasks")
    assert response.status_code == 200
    items = response.json()["items"]
    assert len(items) >= 1
    matching = [i for i in items if i["id"] == task.id]
    assert len(matching) == 1
    assert matching[0]["findings_count"] == 1
    assert matching[0]["report_id"] == report.id


@pytest.mark.asyncio
async def test_list_tasks_pagination(client: AsyncClient, db_session: AsyncSession):
    for i in range(5):
        db_session.add(AuditTask(
            task_name=f"Task {i}",
            task_type=TaskType.DEVIATION_ANALYSIS,
            status=TaskStatus.PENDING,
        ))
    await db_session.commit()

    resp = await client.get("/api/audit/tasks", params={"page": 1, "page_size": 2})
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["items"]) == 2
    assert data["total"] == 5
    assert data["page"] == 1
    assert data["page_size"] == 2


@pytest.mark.asyncio
async def test_list_tasks_filter_by_status(client: AsyncClient, db_session: AsyncSession):
    t1 = AuditTask(task_name="P", task_type=TaskType.DEVIATION_ANALYSIS, status=TaskStatus.PENDING)
    t2 = AuditTask(task_name="C", task_type=TaskType.DEVIATION_ANALYSIS, status=TaskStatus.COMPLETED)
    db_session.add_all([t1, t2])
    await db_session.commit()

    resp = await client.get("/api/audit/tasks", params={"status": "completed"})
    assert resp.status_code == 200
    for item in resp.json()["items"]:
        assert item["status"] == "completed"


# ---------------------------------------------------------------------------
# Get task detail with document_ids
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_task_returns_document_ids(client: AsyncClient, db_session: AsyncSession):
    task = AuditTask(
        task_name="Doc IDs Task",
        task_type=TaskType.DEVIATION_ANALYSIS,
        status=TaskStatus.PENDING,
        document_ids=[10, 20],
    )
    db_session.add(task)
    await db_session.commit()
    await db_session.refresh(task)

    resp = await client.get(f"/api/audit/tasks/{task.id}")
    assert resp.status_code == 200
    assert resp.json()["document_ids"] == [10, 20]


# ---------------------------------------------------------------------------
# Run task
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_run_task_not_found(client: AsyncClient):
    response = await client.post("/api/audit/tasks/999/run")
    # 400 if LLM not configured, or 404 if LLM configured but task missing
    assert response.status_code in (400, 404, 503)


@pytest.mark.asyncio
async def test_run_task_agent_unavailable(client: AsyncClient, db_session: AsyncSession):
    doc = Document(
        filename="test.pdf", file_path="/tmp/test.pdf", file_type="pdf",
        file_size=1024, process_status=DocumentStatus.PROCESSED,
    )
    db_session.add(doc)
    await db_session.commit()
    await db_session.refresh(doc)

    task = AuditTask(
        task_name="Test", task_type=TaskType.DEVIATION_ANALYSIS,
        status=TaskStatus.PENDING, document_ids=[doc.id],
    )
    db_session.add(task)
    await db_session.commit()
    await db_session.refresh(task)

    with patch("app.api.audit.is_agent_available", return_value=False):
        resp = await client.post(f"/api/audit/tasks/{task.id}/run")
        assert resp.status_code == 503


@pytest.mark.asyncio
async def test_run_task_llm_not_configured(client: AsyncClient, db_session: AsyncSession):
    """When agent is available but no LLM adapters configured, should return 400."""
    task = AuditTask(
        task_name="No LLM", task_type=TaskType.DEVIATION_ANALYSIS, status=TaskStatus.PENDING,
    )
    db_session.add(task)
    await db_session.commit()
    await db_session.refresh(task)

    mock_engine = MagicMock()
    mock_engine.adapters = {}
    with (
        patch("app.api.audit.is_agent_available", return_value=True),
        patch("app.services.llm_engine.get_llm_engine", return_value=mock_engine),
    ):
        resp = await client.post(f"/api/audit/tasks/{task.id}/run")
    assert resp.status_code == 400
    assert "LLM" in resp.json()["detail"] or "Key" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_run_task_already_running(client: AsyncClient, db_session: AsyncSession):
    task = AuditTask(
        task_name="Running", task_type=TaskType.DEVIATION_ANALYSIS, status=TaskStatus.RUNNING,
    )
    db_session.add(task)
    await db_session.commit()
    await db_session.refresh(task)

    mock_engine = MagicMock()
    mock_engine.adapters = {"deepseek": True}
    with (
        patch("app.api.audit.is_agent_available", return_value=True),
        patch("app.services.llm_engine.get_llm_engine", return_value=mock_engine),
    ):
        resp = await client.post(f"/api/audit/tasks/{task.id}/run")
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_run_task_document_not_found(client: AsyncClient, db_session: AsyncSession):
    """When task references a non-existent document, run should fail."""
    task = AuditTask(
        task_name="Bad Doc", task_type=TaskType.DEVIATION_ANALYSIS,
        status=TaskStatus.PENDING, document_ids=[99999],
    )
    db_session.add(task)
    await db_session.commit()
    await db_session.refresh(task)

    mock_engine = MagicMock()
    mock_engine.adapters = {"deepseek": True}
    with (
        patch("app.api.audit.is_agent_available", return_value=True),
        patch("app.services.llm_engine.get_llm_engine", return_value=mock_engine),
    ):
        resp = await client.post(f"/api/audit/tasks/{task.id}/run")
    assert resp.status_code == 400
    assert "99999" in resp.json()["detail"] or "not found" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_run_task_document_not_processed(client: AsyncClient, db_session: AsyncSession):
    """When task references an unprocessed document, run should fail."""
    doc = Document(
        filename="raw.pdf", file_path="/tmp/raw.pdf", file_type="pdf",
        file_size=100, process_status=DocumentStatus.UPLOADED,
    )
    db_session.add(doc)
    await db_session.commit()
    await db_session.refresh(doc)

    task = AuditTask(
        task_name="Unproc", task_type=TaskType.DEVIATION_ANALYSIS,
        status=TaskStatus.PENDING, document_ids=[doc.id],
    )
    db_session.add(task)
    await db_session.commit()
    await db_session.refresh(task)

    mock_engine = MagicMock()
    mock_engine.adapters = {"deepseek": True}
    with (
        patch("app.api.audit.is_agent_available", return_value=True),
        patch("app.services.llm_engine.get_llm_engine", return_value=mock_engine),
    ):
        resp = await client.post(f"/api/audit/tasks/{task.id}/run")
    assert resp.status_code == 400
    assert "not processed" in resp.json()["detail"].lower() or "未处理" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_run_task_success(client: AsyncClient, db_session: AsyncSession):
    """Successful task run with agent available and LLM configured."""
    doc = Document(
        filename="ready.pdf", file_path="/tmp/ready.pdf", file_type="pdf",
        file_size=100, process_status=DocumentStatus.PROCESSED,
    )
    db_session.add(doc)
    await db_session.commit()
    await db_session.refresh(doc)

    task = AuditTask(
        task_name="Ready", task_type=TaskType.DEVIATION_ANALYSIS,
        status=TaskStatus.PENDING, document_ids=[doc.id],
    )
    db_session.add(task)
    await db_session.commit()
    await db_session.refresh(task)

    mock_engine = MagicMock()
    mock_engine.adapters = {"deepseek": True}
    mock_runner = MagicMock()
    mock_factory = MagicMock(return_value=mock_runner)

    from app.main import app
    original_factory = getattr(app.state, "task_runner_factory", None)
    app.state.task_runner_factory = mock_factory
    try:
        with (
            patch("app.api.audit.is_agent_available", return_value=True),
            patch("app.services.llm_engine.get_llm_engine", return_value=mock_engine),
        ):
            resp = await client.post(f"/api/audit/tasks/{task.id}/run")

        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "pending"
        assert data["task_id"] == task.id
    finally:
        if original_factory is not None:
            app.state.task_runner_factory = original_factory


# ---------------------------------------------------------------------------
# Cancel task
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_cancel_task_not_found(client: AsyncClient):
    resp = await client.post("/api/audit/tasks/999/cancel")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_cancel_task_not_running(client: AsyncClient, db_session: AsyncSession):
    task = AuditTask(
        task_name="Pending", task_type=TaskType.DEVIATION_ANALYSIS, status=TaskStatus.PENDING,
    )
    db_session.add(task)
    await db_session.commit()
    await db_session.refresh(task)

    resp = await client.post(f"/api/audit/tasks/{task.id}/cancel")
    assert resp.status_code == 400
    assert "not running" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_cancel_task_success(client: AsyncClient, db_session: AsyncSession):
    task = AuditTask(
        task_name="To Cancel", task_type=TaskType.DEVIATION_ANALYSIS, status=TaskStatus.RUNNING,
    )
    db_session.add(task)
    await db_session.commit()
    await db_session.refresh(task)

    mock_runner = AsyncMock()
    mock_runner.cancel = AsyncMock(return_value=True)
    mock_factory = MagicMock(return_value=mock_runner)

    from app.main import app
    original_factory = app.state.task_runner_factory
    app.state.task_runner_factory = mock_factory
    try:
        resp = await client.post(f"/api/audit/tasks/{task.id}/cancel")
        assert resp.status_code == 200
        assert resp.json()["status"] == "cancelled"
    finally:
        app.state.task_runner_factory = original_factory


@pytest.mark.asyncio
async def test_cancel_task_could_not_cancel(client: AsyncClient, db_session: AsyncSession):
    task = AuditTask(
        task_name="No Cancel", task_type=TaskType.DEVIATION_ANALYSIS, status=TaskStatus.RUNNING,
    )
    db_session.add(task)
    await db_session.commit()
    await db_session.refresh(task)

    mock_runner = AsyncMock()
    mock_runner.cancel = AsyncMock(return_value=False)
    mock_factory = MagicMock(return_value=mock_runner)

    from app.main import app
    original_factory = app.state.task_runner_factory
    app.state.task_runner_factory = mock_factory
    try:
        resp = await client.post(f"/api/audit/tasks/{task.id}/cancel")
        assert resp.status_code == 400
    finally:
        app.state.task_runner_factory = original_factory


# ---------------------------------------------------------------------------
# Approve / Reject task
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_approve_task_not_found(client: AsyncClient):
    resp = await client.post("/api/audit/tasks/999/approve", json={"comment": "ok"})
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_approve_task_not_in_review(client: AsyncClient, db_session: AsyncSession):
    task = AuditTask(
        task_name="Pending", task_type=TaskType.DEVIATION_ANALYSIS, status=TaskStatus.PENDING,
    )
    db_session.add(task)
    await db_session.commit()
    await db_session.refresh(task)

    resp = await client.post(f"/api/audit/tasks/{task.id}/approve", json={"comment": "ok"})
    assert resp.status_code == 400
    assert "review" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_approve_task_success(client: AsyncClient, db_session: AsyncSession):
    task = AuditTask(
        task_name="Review Me", task_type=TaskType.DEVIATION_ANALYSIS, status=TaskStatus.AWAITING_REVIEW,
    )
    db_session.add(task)
    await db_session.commit()
    await db_session.refresh(task)

    # Mock event_bus and feishu to avoid logger NameError in approve endpoint
    from app.main import app
    mock_bus = MagicMock()
    mock_bus.publish = AsyncMock()
    mock_bus.publish_done = AsyncMock()
    orig_bus = getattr(app.state, "event_bus", None)
    app.state.event_bus = mock_bus
    try:
        with (
            patch("app.services.notification.is_feishu_configured", return_value=False),
            patch("app.services.notification.notify_audit_complete", new_callable=AsyncMock),
        ):
            resp = await client.post(f"/api/audit/tasks/{task.id}/approve", json={"comment": "LGTM"})
        assert resp.status_code == 200
        assert resp.json()["status"] == "approved"
        assert resp.json()["task_id"] == task.id
    finally:
        app.state.event_bus = orig_bus


@pytest.mark.asyncio
async def test_approve_task_with_findings_and_feishu(client: AsyncClient, db_session: AsyncSession):
    """Approve a task that has findings — covers the Feishu notification path."""
    task = AuditTask(
        task_name="With Findings", task_type=TaskType.DEVIATION_ANALYSIS, status=TaskStatus.AWAITING_REVIEW,
    )
    db_session.add(task)
    await db_session.commit()
    await db_session.refresh(task)

    for sev in [SeverityLevel.HIGH, SeverityLevel.MEDIUM]:
        db_session.add(Finding(
            task_id=task.id, finding_type=FindingType.COMPLIANCE_RISK,
            severity=sev, title=f"Finding {sev.value}", description="Desc",
        ))
    await db_session.commit()

    from app.main import app
    mock_bus = MagicMock()
    mock_bus.publish = AsyncMock()
    mock_bus.publish_done = AsyncMock()
    orig_bus = getattr(app.state, "event_bus", None)
    app.state.event_bus = mock_bus
    try:
        with (
            patch("app.services.notification.is_feishu_configured", return_value=True),
            patch("app.services.notification.notify_audit_complete", new_callable=AsyncMock),
        ):
            resp = await client.post(f"/api/audit/tasks/{task.id}/approve", json={"comment": "ok"})
        assert resp.status_code == 200
        assert resp.json()["status"] == "approved"
    finally:
        app.state.event_bus = orig_bus


@pytest.mark.asyncio
async def test_reject_task_not_found(client: AsyncClient):
    resp = await client.post("/api/audit/tasks/999/reject", json={"comment": "bad"})
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_reject_task_not_in_review(client: AsyncClient, db_session: AsyncSession):
    task = AuditTask(
        task_name="Pending", task_type=TaskType.DEVIATION_ANALYSIS, status=TaskStatus.PENDING,
    )
    db_session.add(task)
    await db_session.commit()
    await db_session.refresh(task)

    resp = await client.post(f"/api/audit/tasks/{task.id}/reject", json={"comment": "bad"})
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_reject_task_success(client: AsyncClient, db_session: AsyncSession):
    task = AuditTask(
        task_name="Reject Me", task_type=TaskType.DEVIATION_ANALYSIS, status=TaskStatus.AWAITING_REVIEW,
    )
    db_session.add(task)
    await db_session.commit()
    await db_session.refresh(task)

    resp = await client.post(f"/api/audit/tasks/{task.id}/reject", json={"comment": "Needs work"})
    assert resp.status_code == 200
    assert resp.json()["status"] == "rejected"
    assert resp.json()["task_id"] == task.id


# ---------------------------------------------------------------------------
# Findings
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_task_findings_empty(client: AsyncClient):
    response = await client.get("/api/audit/tasks/999/findings")
    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.asyncio
async def test_get_task_findings_with_all_fields(client: AsyncClient, db_session: AsyncSession):
    """Ensure all finding fields are serialized correctly."""
    task = AuditTask(
        task_name="Full Finding", task_type=TaskType.DEVIATION_ANALYSIS, status=TaskStatus.COMPLETED,
    )
    db_session.add(task)
    await db_session.commit()
    await db_session.refresh(task)

    finding = Finding(
        task_id=task.id,
        document_id=1,
        finding_type=FindingType.COMPLIANCE_RISK,
        severity=SeverityLevel.HIGH,
        title="Missing SOP",
        description="SOP not found",
        evidence="Checked records",
        suggestion="Add SOP",
        location="Section 3",
        regulation_ref="EU-GMP Annex 15",
        status=FindingStatus.PENDING,
    )
    db_session.add(finding)
    await db_session.commit()
    await db_session.refresh(finding)

    resp = await client.get(f"/api/audit/tasks/{task.id}/findings")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    f = data[0]
    assert f["id"] == finding.id
    assert f["finding_type"] == "compliance_risk"
    assert f["severity"] == "high"
    assert f["title"] == "Missing SOP"
    assert f["evidence"] == "Checked records"
    assert f["suggestion"] == "Add SOP"
    assert f["location"] == "Section 3"
    assert f["regulation_ref"] == "EU-GMP Annex 15"
    assert f["document_id"] == 1
    assert f["status"] == "pending"


@pytest.mark.asyncio
async def test_get_task_findings_with_reviewed_at(client: AsyncClient, db_session: AsyncSession):
    task = AuditTask(
        task_name="Reviewed", task_type=TaskType.DEVIATION_ANALYSIS, status=TaskStatus.COMPLETED,
    )
    db_session.add(task)
    await db_session.commit()
    await db_session.refresh(task)

    finding = Finding(
        task_id=task.id, finding_type=FindingType.COMPLIANCE_RISK,
        severity=SeverityLevel.LOW, title="Minor", description="Desc",
        status=FindingStatus.APPROVED, reviewer_comment="OK",
        reviewed_at=datetime.now(UTC),
    )
    db_session.add(finding)
    await db_session.commit()

    resp = await client.get(f"/api/audit/tasks/{task.id}/findings")
    assert resp.status_code == 200
    data = resp.json()[0]
    assert data["reviewer_comment"] == "OK"
    assert data["reviewed_at"] is not None


# ---------------------------------------------------------------------------
# Approve / Reject finding
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_approve_finding_not_found(client: AsyncClient):
    resp = await client.post("/api/audit/findings/999/approve", json={"comment": "ok"})
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_approve_finding_no_body(client: AsyncClient, db_session: AsyncSession):
    task = AuditTask(task_name="T", task_type=TaskType.DEVIATION_ANALYSIS, status=TaskStatus.COMPLETED)
    db_session.add(task)
    await db_session.commit()
    await db_session.refresh(task)

    finding = Finding(
        task_id=task.id, finding_type=FindingType.COMPLIANCE_RISK,
        severity=SeverityLevel.HIGH, title="F", description="D",
    )
    db_session.add(finding)
    await db_session.commit()
    await db_session.refresh(finding)

    resp = await client.post(f"/api/audit/findings/{finding.id}/approve")
    assert resp.status_code == 200
    assert resp.json()["status"] == "approved"


@pytest.mark.asyncio
async def test_approve_finding_with_comment(client: AsyncClient, db_session: AsyncSession):
    task = AuditTask(task_name="T2", task_type=TaskType.DEVIATION_ANALYSIS, status=TaskStatus.COMPLETED)
    db_session.add(task)
    await db_session.commit()
    await db_session.refresh(task)

    finding = Finding(
        task_id=task.id, finding_type=FindingType.INCONSISTENCY,
        severity=SeverityLevel.MEDIUM, title="Inconsistency", description="D",
    )
    db_session.add(finding)
    await db_session.commit()
    await db_session.refresh(finding)

    resp = await client.post(
        f"/api/audit/findings/{finding.id}/approve",
        json={"comment": "Confirmed by reviewer"},
    )
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_reject_finding_not_found(client: AsyncClient):
    resp = await client.post("/api/audit/findings/999/reject", json={"comment": "bad"})
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_reject_finding_no_body(client: AsyncClient, db_session: AsyncSession):
    task = AuditTask(task_name="T3", task_type=TaskType.DEVIATION_ANALYSIS, status=TaskStatus.COMPLETED)
    db_session.add(task)
    await db_session.commit()
    await db_session.refresh(task)

    finding = Finding(
        task_id=task.id, finding_type=FindingType.BEST_PRACTICE,
        severity=SeverityLevel.INFO, title="BP", description="D",
    )
    db_session.add(finding)
    await db_session.commit()
    await db_session.refresh(finding)

    resp = await client.post(f"/api/audit/findings/{finding.id}/reject")
    assert resp.status_code == 200
    assert resp.json()["status"] == "rejected"


@pytest.mark.asyncio
async def test_reject_finding_with_comment(client: AsyncClient, db_session: AsyncSession):
    task = AuditTask(task_name="T4", task_type=TaskType.DEVIATION_ANALYSIS, status=TaskStatus.COMPLETED)
    db_session.add(task)
    await db_session.commit()
    await db_session.refresh(task)

    finding = Finding(
        task_id=task.id, finding_type=FindingType.MISSING_INFO,
        severity=SeverityLevel.LOW, title="Missing", description="D",
    )
    db_session.add(finding)
    await db_session.commit()
    await db_session.refresh(finding)

    resp = await client.post(
        f"/api/audit/findings/{finding.id}/reject",
        json={"comment": "Not valid"},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "rejected"


# ---------------------------------------------------------------------------
# Risk assessment
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_task_risk_assessment_empty(client: AsyncClient, db_session: AsyncSession):
    task = AuditTask(task_name="No Risk", task_type=TaskType.DEVIATION_ANALYSIS, status=TaskStatus.COMPLETED)
    db_session.add(task)
    await db_session.commit()
    await db_session.refresh(task)

    resp = await client.get(f"/api/audit/tasks/{task.id}/risk")
    assert resp.status_code == 200
    data = resp.json()
    assert data["risk_level"] == "low"
    assert data["total_findings"] == 0


@pytest.mark.asyncio
async def test_get_task_risk_assessment_medium(client: AsyncClient, db_session: AsyncSession):
    """Medium risk: high medium count ratio."""
    task = AuditTask(task_name="Med Risk", task_type=TaskType.DEVIATION_ANALYSIS, status=TaskStatus.COMPLETED)
    db_session.add(task)
    await db_session.commit()
    await db_session.refresh(task)

    for _ in range(5):
        db_session.add(Finding(
            task_id=task.id, finding_type=FindingType.COMPLIANCE_RISK,
            severity=SeverityLevel.MEDIUM, title="M", description="D",
        ))
    await db_session.commit()

    resp = await client.get(f"/api/audit/tasks/{task.id}/risk")
    assert resp.status_code == 200
    assert resp.json()["risk_level"] == "medium"


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_dashboard_stats_empty(client: AsyncClient):
    resp = await client.get("/api/audit/dashboard")
    assert resp.status_code == 200
    data = resp.json()
    assert "task_counts" in data
    assert "severity_counts" in data
    assert "total_tasks" in data
    assert "total_findings" in data


@pytest.mark.asyncio
async def test_dashboard_stats_with_data(client: AsyncClient, db_session: AsyncSession):
    task = AuditTask(task_name="D", task_type=TaskType.DEVIATION_ANALYSIS, status=TaskStatus.COMPLETED)
    db_session.add(task)
    await db_session.commit()
    await db_session.refresh(task)

    db_session.add(Finding(
        task_id=task.id, finding_type=FindingType.COMPLIANCE_RISK,
        severity=SeverityLevel.HIGH, title="H", description="D",
    ))
    db_session.add(Finding(
        task_id=task.id, finding_type=FindingType.COMPLIANCE_RISK,
        severity=SeverityLevel.LOW, title="L", description="D",
    ))
    await db_session.commit()

    resp = await client.get("/api/audit/dashboard")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_tasks"] >= 1
    assert data["total_findings"] >= 2


# ---------------------------------------------------------------------------
# Estimate
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_estimate_no_documents(client: AsyncClient):
    resp = await client.post("/api/audit/estimate", json={"document_ids": [99999]})
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_estimate_small_document(client: AsyncClient, db_session: AsyncSession):
    doc = Document(
        filename="small.pdf", file_path="/tmp/small.pdf", file_type="pdf",
        file_size=100, process_status=DocumentStatus.PROCESSED,
        content_text="A" * 1000,
    )
    db_session.add(doc)
    await db_session.commit()
    await db_session.refresh(doc)

    resp = await client.post("/api/audit/estimate", json={"document_ids": [doc.id]})
    assert resp.status_code == 200
    data = resp.json()
    assert data["document_count"] == 1
    assert data["estimated_llm_calls"] >= 4  # 2 reg + 1 risk + 1 report
    assert data["estimated_input_tokens"] > 0
    assert data["estimated_output_tokens"] > 0
    assert data["estimated_duration_seconds"] > 0


@pytest.mark.asyncio
async def test_estimate_large_document(client: AsyncClient, db_session: AsyncSession):
    """Document exceeding STUFF_LIMIT triggers map-reduce (more risk calls)."""
    doc = Document(
        filename="large.pdf", file_path="/tmp/large.pdf", file_type="pdf",
        file_size=100000, process_status=DocumentStatus.PROCESSED,
        content_text="A" * 70000,  # > 60000 STUFF_LIMIT
    )
    db_session.add(doc)
    await db_session.commit()
    await db_session.refresh(doc)

    resp = await client.post("/api/audit/estimate", json={"document_ids": [doc.id]})
    assert resp.status_code == 200
    data = resp.json()
    # 70000 / 8000 = 9 chunks for risk
    assert data["estimated_llm_calls"] >= 11  # 2 + 9 + 1


@pytest.mark.asyncio
async def test_estimate_multiple_documents(client: AsyncClient, db_session: AsyncSession):
    docs = []
    for i in range(3):
        doc = Document(
            filename=f"est_{i}.pdf", file_path=f"/tmp/est_{i}.pdf", file_type="pdf",
            file_size=100, process_status=DocumentStatus.PROCESSED,
            content_text="X" * 500,
        )
        db_session.add(doc)
        docs.append(doc)
    await db_session.commit()
    for d in docs:
        await db_session.refresh(d)

    resp = await client.post(
        "/api/audit/estimate",
        json={"document_ids": [d.id for d in docs]},
    )
    assert resp.status_code == 200
    assert resp.json()["document_count"] == 3


# ---------------------------------------------------------------------------
# Memory
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_memory(client: AsyncClient):
    resp = await client.get("/api/audit/memory")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


@pytest.mark.asyncio
async def test_get_memory_with_limit(client: AsyncClient):
    resp = await client.get("/api/audit/memory", params={"limit": 5})
    assert resp.status_code == 200


# ---------------------------------------------------------------------------
# SSE streaming
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_stream_task_not_found(client: AsyncClient):
    resp = await client.get("/api/audit/tasks/999/stream")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_stream_task_completed(client: AsyncClient, db_session: AsyncSession):
    """Streaming a completed task should send historical events then done."""
    task = AuditTask(
        task_name="Done", task_type=TaskType.DEVIATION_ANALYSIS,
        status=TaskStatus.COMPLETED,
        config={"execution": {"events": [{"time": "2026-01-01", "stage": "completed", "level": "info", "message": "done"}], "thinking_events": []}},
    )
    db_session.add(task)
    await db_session.commit()
    await db_session.refresh(task)

    from app.main import app
    from app.services.event_bus import EventBus
    if not hasattr(app.state, "event_bus") or app.state.event_bus is None:
        app.state.event_bus = EventBus()

    resp = await client.get(f"/api/audit/tasks/{task.id}/stream")
    assert resp.status_code == 200
    assert "text/event-stream" in resp.headers["content-type"]
    body = resp.text
    assert "done" in body


@pytest.mark.asyncio
async def test_stream_task_awaiting_review(client: AsyncClient, db_session: AsyncSession):
    """Terminal status: AWAITING_REVIEW should close stream quickly."""
    task = AuditTask(
        task_name="Review", task_type=TaskType.DEVIATION_ANALYSIS,
        status=TaskStatus.AWAITING_REVIEW,
    )
    db_session.add(task)
    await db_session.commit()
    await db_session.refresh(task)

    from app.main import app
    from app.services.event_bus import EventBus
    if not hasattr(app.state, "event_bus") or app.state.event_bus is None:
        app.state.event_bus = EventBus()

    resp = await client.get(f"/api/audit/tasks/{task.id}/stream")
    assert resp.status_code == 200
    assert "done" in resp.text


@pytest.mark.asyncio
async def test_stream_task_failed(client: AsyncClient, db_session: AsyncSession):
    task = AuditTask(
        task_name="Failed", task_type=TaskType.DEVIATION_ANALYSIS,
        status=TaskStatus.FAILED,
    )
    db_session.add(task)
    await db_session.commit()
    await db_session.refresh(task)

    from app.main import app
    from app.services.event_bus import EventBus
    if not hasattr(app.state, "event_bus") or app.state.event_bus is None:
        app.state.event_bus = EventBus()

    resp = await client.get(f"/api/audit/tasks/{task.id}/stream")
    assert resp.status_code == 200
    assert "done" in resp.text


@pytest.mark.asyncio
async def test_stream_task_with_thinking_events(client: AsyncClient, db_session: AsyncSession):
    """Covers the thinking_events replay path."""
    task = AuditTask(
        task_name="Thinking", task_type=TaskType.DEVIATION_ANALYSIS,
        status=TaskStatus.COMPLETED,
        config={
            "execution": {
                "events": [],
                "thinking_events": [
                    {"agent": "regulation_expert", "thought": "Analyzing..."},
                ],
            }
        },
    )
    db_session.add(task)
    await db_session.commit()
    await db_session.refresh(task)

    from app.main import app
    from app.services.event_bus import EventBus
    if not hasattr(app.state, "event_bus") or app.state.event_bus is None:
        app.state.event_bus = EventBus()

    resp = await client.get(f"/api/audit/tasks/{task.id}/stream")
    assert resp.status_code == 200
    assert "agent_thinking" in resp.text


@pytest.mark.asyncio
async def test_stream_task_rejected(client: AsyncClient, db_session: AsyncSession):
    task = AuditTask(
        task_name="Rejected", task_type=TaskType.DEVIATION_ANALYSIS,
        status=TaskStatus.REJECTED,
    )
    db_session.add(task)
    await db_session.commit()
    await db_session.refresh(task)

    from app.main import app
    from app.services.event_bus import EventBus
    if not hasattr(app.state, "event_bus") or app.state.event_bus is None:
        app.state.event_bus = EventBus()

    resp = await client.get(f"/api/audit/tasks/{task.id}/stream")
    assert resp.status_code == 200
    assert "done" in resp.text
