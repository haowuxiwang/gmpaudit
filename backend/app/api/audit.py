from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.audit_task import AuditTask, TaskStatus, TaskType
from app.models.document import Document, DocumentStatus
from app.models.finding import Finding
from app.services.audit_engine import get_audit_engine
from app.services.task_runner import append_event, build_task_payload, set_stage
from app.utils.agent_helpers import AGENT_AVAILABLE

router = APIRouter()


class AuditTaskCreate(BaseModel):
    task_name: str
    task_type: TaskType
    document_ids: list[int]


@router.post("/tasks")
async def create_audit_task(
    task_data: AuditTaskCreate,
    db: AsyncSession = Depends(get_db),
):
    task = AuditTask(
        task_name=task_data.task_name,
        task_type=task_data.task_type,
        document_ids=task_data.document_ids,
        status=TaskStatus.PENDING,
        progress=0,
        config={},
    )
    set_stage(task, "pending")
    append_event(task, "Task created", stage="pending")
    db.add(task)
    await db.commit()
    await db.refresh(task)
    return {"id": task.id, "task_name": task.task_name, "status": task.status.value}


@router.get("/tasks")
async def list_audit_tasks(
    status: TaskStatus | None = None,
    page: int = 1,
    page_size: int = 20,
    db: AsyncSession = Depends(get_db),
):
    query = select(AuditTask)
    count_q = select(func.count()).select_from(AuditTask)
    if status:
        query = query.where(AuditTask.status == status)
        count_q = count_q.where(AuditTask.status == status)

    total = (await db.execute(count_q)).scalar()
    query = query.order_by(AuditTask.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    tasks = (await db.execute(query)).scalars().all()

    items = []
    for task in tasks:
        payload = await build_task_payload(db, task)
        items.append(payload)

    return {"items": items, "total": total, "page": page, "page_size": page_size}


@router.get("/tasks/{task_id}")
async def get_audit_task(
    task_id: int,
    db: AsyncSession = Depends(get_db),
):
    task = (await db.execute(select(AuditTask).where(AuditTask.id == task_id))).scalar_one_or_none()
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    payload = await build_task_payload(db, task)
    payload["document_ids"] = task.document_ids or []
    return payload


@router.post("/tasks/{task_id}/run")
async def run_audit_task(
    task_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    task = (await db.execute(select(AuditTask).where(AuditTask.id == task_id))).scalar_one_or_none()
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    if task.status == TaskStatus.RUNNING:
        raise HTTPException(status_code=400, detail="Task is already running")
    if not AGENT_AVAILABLE:
        raise HTTPException(status_code=503, detail="Agent audit system is unavailable")

    for doc_id in task.document_ids or []:
        document = (await db.execute(select(Document).where(Document.id == doc_id))).scalar_one_or_none()
        if document is None:
            raise HTTPException(status_code=400, detail=f"Document {doc_id} not found")
        if document.process_status != DocumentStatus.PROCESSED:
            raise HTTPException(status_code=400, detail=f"Document is not processed: {document.filename}")

    task.status = TaskStatus.PENDING
    task.progress = 0
    task.error_message = None
    set_stage(task, "queued")
    append_event(task, "Task queued for execution", stage="queued")
    await db.commit()

    runner = request.app.state.task_runner_factory()
    runner.enqueue(task.id)

    return {"status": "pending", "task_id": task_id}


@router.get("/tasks/{task_id}/findings")
async def get_task_findings(
    task_id: int,
    db: AsyncSession = Depends(get_db),
):
    findings = (await db.execute(select(Finding).where(Finding.task_id == task_id))).scalars().all()
    return [
        {
            "id": finding.id,
            "finding_type": finding.finding_type.value,
            "severity": finding.severity.value,
            "title": finding.title,
            "description": finding.description,
            "evidence": finding.evidence,
            "suggestion": finding.suggestion,
            "location": finding.location,
            "regulation_ref": finding.regulation_ref,
            "document_id": finding.document_id,
            "created_at": finding.created_at,
        }
        for finding in findings
    ]


@router.get("/tasks/{task_id}/risk")
async def get_task_risk_assessment(
    task_id: int,
    db: AsyncSession = Depends(get_db),
):
    findings = (await db.execute(select(Finding).where(Finding.task_id == task_id))).scalars().all()
    return await get_audit_engine().assess_risk([{"severity": finding.severity.value} for finding in findings])


@router.get("/dashboard")
async def get_dashboard_stats(
    db: AsyncSession = Depends(get_db),
):
    task_counts = {}
    for status in TaskStatus:
        result = await db.execute(select(func.count()).select_from(AuditTask).where(AuditTask.status == status))
        task_counts[status.value] = result.scalar()

    from app.models.finding import SeverityLevel

    severity_counts = {}
    for level in SeverityLevel:
        result = await db.execute(select(func.count()).select_from(Finding).where(Finding.severity == level))
        severity_counts[level.value] = result.scalar()

    return {
        "task_counts": task_counts,
        "severity_counts": severity_counts,
        "total_tasks": sum(task_counts.values()),
        "total_findings": sum(severity_counts.values()),
    }
