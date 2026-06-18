import asyncio
import json
import logging
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.responses import StreamingResponse

logger = logging.getLogger(__name__)

from app.core.database import get_db
from app.models.audit_task import AuditTask, TaskStatus, TaskType
from app.models.document import Document, DocumentStatus
from app.models.finding import Finding
from app.services.audit_engine import get_audit_engine
from app.services.task_runner import append_event, build_task_payload, set_stage
from app.utils.agent_helpers import is_agent_available

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
    page: int = Query(1, ge=1, le=10000),
    page_size: int = Query(20, ge=1, le=100),
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

    # Batch-load findings count and latest report for all tasks (avoids N+1)
    task_ids = [t.id for t in tasks]
    findings_counts: dict[int, int] = {}
    report_ids: dict[int, int] = {}
    if task_ids:
        from app.models.finding import Finding
        from app.models.report import Report

        rows = (
            await db.execute(
                select(Finding.task_id, func.count()).where(Finding.task_id.in_(task_ids)).group_by(Finding.task_id)
            )
        ).all()
        findings_counts = {tid: cnt for tid, cnt in rows}

        # Latest report per task
        from sqlalchemy import func as sqlfunc

        subq = (
            select(Report.task_id, sqlfunc.max(Report.id).label("max_id"))
            .where(Report.task_id.in_(task_ids))
            .group_by(Report.task_id)
            .subquery()
        )
        report_rows = (await db.execute(select(subq.c.task_id, subq.c.max_id))).all()
        report_ids = {tid: rid for tid, rid in report_rows}

    items = []
    for task in tasks:
        payload = await build_task_payload(
            db, task,
            _findings_count=findings_counts.get(task.id, 0),
            _report_id=report_ids.get(task.id),
        )
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
    if not is_agent_available():
        raise HTTPException(status_code=503, detail="Agent audit system is unavailable")

    # Check if LLM is configured
    from app.services.llm_engine import get_llm_engine
    engine = get_llm_engine()
    if not engine.adapters:
        raise HTTPException(
            status_code=400,
            detail="未配置 LLM API Key，请在「设置」页面配置后再运行审计任务"
        )

    # Atomic check-and-set to prevent TOCTOU race condition
    from sqlalchemy import update as sa_update

    result = await db.execute(
        sa_update(AuditTask)
        .where(AuditTask.id == task_id, AuditTask.status != TaskStatus.RUNNING)
        .values(status=TaskStatus.PENDING, progress=0, error_message=None)
    )
    if result.rowcount == 0:
        # Use select() instead of db.get() to bypass identity map cache
        task = (await db.execute(select(AuditTask).where(AuditTask.id == task_id))).scalar_one_or_none()
        if task is None:
            raise HTTPException(status_code=404, detail="Task not found")
        raise HTTPException(status_code=400, detail="Task is already running")

    task = (await db.execute(select(AuditTask).where(AuditTask.id == task_id))).scalar_one()

    for doc_id in task.document_ids or []:
        document = (await db.execute(select(Document).where(Document.id == doc_id))).scalar_one_or_none()
        if document is None:
            raise HTTPException(status_code=400, detail=f"Document {doc_id} not found")
        if document.process_status != DocumentStatus.PROCESSED:
            raise HTTPException(status_code=400, detail=f"Document is not processed: {document.filename}")

    set_stage(task, "queued")
    append_event(task, "Task queued for execution", stage="queued")
    await db.commit()

    runner = request.app.state.task_runner_factory()
    try:
        runner.enqueue(task.id)
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e)) from e

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

    from datetime import datetime

    # Report and findings are already in DB from the initial run.
    # No need to re-run the entire pipeline — just mark as completed.
    task.status = TaskStatus.COMPLETED
    task.progress = 100
    task.review_comment = body.comment
    task.reviewed_at = datetime.now(UTC)
    task.auto_approve = True
    task.completed_at = datetime.now(UTC)
    task.error_message = None
    set_stage(task, "completed")
    append_event(task, f"Task approved: {body.comment}", stage="completed")
    await db.commit()

    # Notify via EventBus
    try:
        event_bus = getattr(request.app.state, "event_bus", None)
        if event_bus:
            await event_bus.publish(
                task_id,
                {
                    "type": "event",
                    "data": {
                        "time": datetime.now(UTC).isoformat(),
                        "stage": "completed",
                        "level": "info",
                        "message": f"Task approved: {body.comment}",
                    },
                },
            )
            await event_bus.publish_done(task_id, "completed")
    except Exception:
        logger.debug("Non-critical error in task notification", exc_info=True)

    # Send Feishu notification
    try:
        from app.services.notification import is_feishu_configured, notify_audit_complete

        if is_feishu_configured():
            from sqlalchemy import select as sa_select

            from app.models.finding import Finding, SeverityLevel

            findings = (await db.execute(sa_select(Finding).where(Finding.task_id == task.id))).scalars().all()
            high_count = sum(1 for f in findings if f.severity == SeverityLevel.HIGH)
            medium_count = sum(1 for f in findings if f.severity == SeverityLevel.MEDIUM)
            top_findings = [
                {"title": f.title, "severity": f.severity.value} for f in findings if f.severity == SeverityLevel.HIGH
            ][:3]
            await notify_audit_complete(
                task.task_name, len(findings), high_count, medium_count, top_findings, task_id=task.id
            )
    except Exception:
        logger.debug("Non-critical error in task notification", exc_info=True)

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

    from datetime import datetime

    task.status = TaskStatus.REJECTED
    task.review_comment = body.comment
    task.reviewed_at = datetime.now(UTC)
    task.completed_at = datetime.now(UTC)
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
            "status": finding.status.value if finding.status else "pending",
            "reviewer_comment": finding.reviewer_comment,
            "reviewed_at": finding.reviewed_at.replace(tzinfo=UTC).isoformat() if finding.reviewed_at else None,
            "created_at": finding.created_at.replace(tzinfo=UTC).isoformat() if finding.created_at else None,
        }
        for finding in findings
    ]


class FindingReviewRequest(BaseModel):
    comment: str | None = None


@router.post("/findings/{finding_id}/approve")
async def approve_finding(
    finding_id: int,
    body: FindingReviewRequest | None = None,
    db: AsyncSession = Depends(get_db),
):
    finding = (await db.execute(select(Finding).where(Finding.id == finding_id))).scalars().first()
    if not finding:
        raise HTTPException(status_code=404, detail="Finding not found")
    from app.models.finding import FindingStatus

    finding.status = FindingStatus.APPROVED
    finding.reviewer_comment = body.comment if body else None
    finding.reviewed_at = datetime.now(UTC)
    await db.commit()
    return {"status": "approved", "finding_id": finding_id}


@router.post("/findings/{finding_id}/reject")
async def reject_finding(
    finding_id: int,
    body: FindingReviewRequest | None = None,
    db: AsyncSession = Depends(get_db),
):
    finding = (await db.execute(select(Finding).where(Finding.id == finding_id))).scalars().first()
    if not finding:
        raise HTTPException(status_code=404, detail="Finding not found")
    from app.models.finding import FindingStatus

    finding.status = FindingStatus.REJECTED
    finding.reviewer_comment = body.comment if body else None
    finding.reviewed_at = datetime.now(UTC)
    await db.commit()
    return {"status": "rejected", "finding_id": finding_id}


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
    # Single query: GROUP BY task status
    status_result = await db.execute(
        select(AuditTask.status, func.count(AuditTask.id))
        .group_by(AuditTask.status)
    )
    task_counts = {
        row[0].value if hasattr(row[0], "value") else row[0]: row[1]
        for row in status_result.all()
    }

    # Single query: GROUP BY finding severity
    severity_result = await db.execute(
        select(Finding.severity, func.count(Finding.id))
        .group_by(Finding.severity)
    )
    severity_counts = {
        row[0].value if hasattr(row[0], "value") else row[0]: row[1]
        for row in severity_result.all()
    }

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
    terminal_statuses = (TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.REJECTED, TaskStatus.AWAITING_REVIEW)

    async def event_generator():
        # Subscribe BEFORE checking status to avoid race condition
        queue = await event_bus.subscribe(task_id)
        try:
            # Re-check status after subscribing to catch transitions that happened between request and subscribe
            # Use a fresh session (not the dependency-injected one) to avoid session lifecycle issues
            async with get_db_session() as db_session:
                refreshed = (
                    await db_session.execute(select(AuditTask).where(AuditTask.id == task_id))
                ).scalar_one_or_none()
            if refreshed is None:
                yield f"event: done\ndata: {json.dumps({'type': 'done', 'status': 'failed'})}\n\n"
                return

            # Send historical events snapshot for reconnecting clients
            meta = refreshed.config or {}
            execution = meta.get("execution", {})
            for event in execution.get("events", []):
                yield f"event: event\ndata: {json.dumps({'type': 'event', 'data': event})}\n\n"
            # Replay persisted agent_thinking events
            for event in execution.get("thinking_events", []):
                yield f"event: agent_thinking\ndata: {json.dumps({'type': 'agent_thinking', 'data': event})}\n\n"

            # If task already finished, send done and close
            if refreshed.status in terminal_statuses:
                yield f"event: done\ndata: {json.dumps({'type': 'done', 'status': refreshed.status.value})}\n\n"
                return

            # Live event loop
            while True:
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=30.0)
                except TimeoutError:
                    yield ": keepalive\n\n"
                    continue

                if event is event_bus.DONE_SENTINEL:
                    break

                # Use the event's type field as the SSE event name
                event_type = event.get("type", "event")
                yield f"event: {event_type}\ndata: {json.dumps(event)}\n\n"
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

            try:
                async with get_db_session() as session:
                    result = await session.execute(
                        select(AuditTask.id, AuditTask.status, AuditTask.progress, AuditTask.task_name)
                        .order_by(AuditTask.created_at.desc())
                    )
                    current_statuses = {row.id: row.status.value for row in result.all()}

                    changed = []
                    for task_id, status in current_statuses.items():
                        if last_statuses.get(task_id) != status:
                            changed.append({"task_id": task_id, "status": status})

                    if changed:
                        yield f"data: {json.dumps({'type': 'status_change', 'tasks': changed})}\n\n"

                    last_statuses = current_statuses
            except Exception:
                logger.warning("stream_all_tasks poll error", exc_info=True)

            await asyncio.sleep(5)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/memory")
async def get_audit_memory(limit: int = Query(default=50, ge=1, le=500)):
    """Return recent audit memory entries (JSONL-based cross-audit history)."""
    from app.services.memory import load_memory

    return await load_memory(limit=limit)


class EstimateRequest(BaseModel):
    document_ids: list[int]


@router.post("/estimate")
async def estimate_audit_cost(
    body: EstimateRequest,
    db: AsyncSession = Depends(get_db),
):
    """Estimate LLM calls, tokens, and duration for an audit task."""
    import math

    CHUNK_MAX_CHARS = 8000
    STUFF_LIMIT = 60000
    AVG_COMPLETION_TOKENS = 1500

    docs = (await db.execute(select(Document).where(Document.id.in_(body.document_ids)))).scalars().all()
    if not docs:
        raise HTTPException(status_code=404, detail="No documents found")

    total_llm_calls = 0
    total_input_tokens = 0
    for doc in docs:
        content_len = len(doc.content_text or "")
        # regulation_expert: 1 rewrite + 1 analysis = 2 calls
        reg_calls = 2
        # risk_assessor: 1 call (stuff) or N calls (map-reduce)
        if content_len > STUFF_LIMIT:
            chunks = math.ceil(content_len / CHUNK_MAX_CHARS)
            risk_calls = chunks
        else:
            risk_calls = 1
        # report_writer: 1 call
        report_calls = 1
        doc_calls = reg_calls + risk_calls + report_calls
        total_llm_calls += doc_calls
        # Estimate input tokens: ~1.5 chars per Chinese token + prompt overhead
        total_input_tokens += int(content_len / 1.5) + 500 * doc_calls

    total_output_tokens = total_llm_calls * AVG_COMPLETION_TOKENS
    estimated_seconds = total_llm_calls * 10  # ~10s per LLM call

    return {
        "document_count": len(docs),
        "estimated_llm_calls": total_llm_calls,
        "estimated_input_tokens": total_input_tokens,
        "estimated_output_tokens": total_output_tokens,
        "estimated_duration_seconds": estimated_seconds,
    }
