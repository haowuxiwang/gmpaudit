import asyncio
import json
from datetime import timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.responses import StreamingResponse

from app.core.database import get_db
from app.models.audit_task import AuditTask, TaskStatus, TaskType
from app.models.document import Document, DocumentStatus
from app.models.finding import Finding
from app.services.audit_engine import get_audit_engine
from app.services.task_runner import append_event, build_task_payload, set_stage
from app.utils.agent_helpers import AGENT_AVAILABLE

router = APIRouter()


def get_db_session():
    from app.core.database import async_session
    return async_session()


class AuditTaskCreate(BaseModel):
    task_name: str
    task_type: TaskType
    document_ids: list[int]


class ReviewComment(BaseModel):
    comment: str = ""


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


@router.post("/tasks/{task_id}/cancel")
async def cancel_audit_task(
    task_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    task = (await db.execute(select(AuditTask).where(AuditTask.id == task_id))).scalar_one_or_none()
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    if task.status != TaskStatus.RUNNING:
        raise HTTPException(status_code=400, detail="Task is not running")
    runner = request.app.state.task_runner_factory()
    cancelled = await runner.cancel(task_id)
    if not cancelled:
        raise HTTPException(status_code=400, detail="Task could not be cancelled")
    return {"status": "cancelled", "task_id": task_id}


@router.post("/tasks/{task_id}/approve")
async def approve_task(
    task_id: int,
    body: ReviewComment,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    task = (await db.execute(select(AuditTask).where(AuditTask.id == task_id))).scalar_one_or_none()
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    if task.status != TaskStatus.AWAITING_REVIEW:
        raise HTTPException(status_code=400, detail="Task not in review state")

    from datetime import datetime, timezone
    task.status = TaskStatus.PENDING
    task.review_comment = body.comment
    task.reviewed_at = datetime.now(timezone.utc)
    task.auto_approve = True
    task.progress = 0
    task.error_message = None
    set_stage(task, "queued")
    append_event(task, f"Task approved: {body.comment}", stage="queued")
    await db.commit()

    runner = request.app.state.task_runner_factory()
    runner.enqueue(task.id)

    return {"status": "approved", "task_id": task_id}


@router.post("/tasks/{task_id}/reject")
async def reject_task(
    task_id: int,
    body: ReviewComment,
    db: AsyncSession = Depends(get_db),
):
    task = (await db.execute(select(AuditTask).where(AuditTask.id == task_id))).scalar_one_or_none()
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    if task.status != TaskStatus.AWAITING_REVIEW:
        raise HTTPException(status_code=400, detail="Task not in review state")

    from datetime import datetime, timezone
    task.status = TaskStatus.REJECTED
    task.review_comment = body.comment
    task.reviewed_at = datetime.now(timezone.utc)
    task.completed_at = datetime.now(timezone.utc)
    set_stage(task, "rejected")
    append_event(task, f"Task rejected: {body.comment}", stage="rejected", level="warning")
    await db.commit()

    return {"status": "rejected", "task_id": task_id}


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
            "created_at": finding.created_at.replace(tzinfo=timezone.utc).isoformat() if finding.created_at else None,
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


@router.get("/tasks/{task_id}/stream")
async def stream_task_events(task_id: int, request: Request, db: AsyncSession = Depends(get_db)):
    task = (await db.execute(select(AuditTask).where(AuditTask.id == task_id))).scalar_one_or_none()
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")

    event_bus = request.app.state.event_bus

    async def event_generator():
        # Send historical events snapshot for reconnecting clients
        meta = task.config or {}
        execution = meta.get("execution", {})
        for event in execution.get("events", []):
            yield f"data: {json.dumps({'type': 'event', 'data': event})}\n\n"

        # If task already finished, send done and close
        if task.status in (TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.REJECTED, TaskStatus.AWAITING_REVIEW):
            yield f"data: {json.dumps({'type': 'done', 'status': task.status.value})}\n\n"
            return

        # Subscribe to live events
        queue = await event_bus.subscribe(task_id)
        try:
            while True:
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=30.0)
                except asyncio.TimeoutError:
                    yield ": keepalive\n\n"
                    continue

                if event is event_bus.DONE_SENTINEL:
                    break

                yield f"data: {json.dumps(event)}\n\n"
        finally:
            await event_bus.unsubscribe(task_id, queue)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/tasks/stream")
async def stream_all_tasks(request: Request):
    async def event_generator():
        last_statuses = {}
        while True:
            if await request.is_disconnected():
                break

            async with get_db_session() as session:
                result = await session.execute(select(AuditTask))
                tasks = result.scalars().all()
                current_statuses = {t.id: t.status.value for t in tasks}

                changed = []
                for task_id, status in current_statuses.items():
                    if last_statuses.get(task_id) != status:
                        changed.append({"task_id": task_id, "status": status})

                if changed:
                    yield f"data: {json.dumps({'type': 'status_change', 'tasks': changed})}\n\n"

                last_statuses = current_statuses
            await asyncio.sleep(2)

    return StreamingResponse(event_generator(), media_type="text/event-stream")
