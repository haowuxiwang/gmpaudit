from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.audit_task import AuditTask, TaskStatus, TaskType
from app.models.document import Document, DocumentStatus
from app.services.task_runner import append_event, build_task_payload, get_execution_meta, set_execution_meta, set_stage
from app.utils.agent_helpers import is_agent_available

router = APIRouter()

AUDIT_TYPE_TO_TASK_TYPE = {
    "deviation": TaskType.DEVIATION_ANALYSIS,
    "sop": TaskType.SOP_COMPLIANCE,
    "change_control": TaskType.CONSISTENCY_CHECK,
}


class AgentAuditRequest(BaseModel):
    document_id: int
    audit_type: str = "deviation"
    focus: str | None = None


class AgentAuditResponse(BaseModel):
    task_id: int
    status: str
    message: str


@router.post("/run", response_model=AgentAuditResponse)
async def run_agent_audit(
    request: AgentAuditRequest,
    http_request: Request,
    db: AsyncSession = Depends(get_db),
):
    if not is_agent_available():
        raise HTTPException(status_code=503, detail="Agent audit system is unavailable")

    document = (await db.execute(select(Document).where(Document.id == request.document_id))).scalar_one_or_none()
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found")
    if document.process_status != DocumentStatus.PROCESSED:
        raise HTTPException(status_code=400, detail="Document is not processed")

    if request.audit_type not in AUDIT_TYPE_TO_TASK_TYPE:
        raise HTTPException(
            status_code=400,
            detail=f"无效的审计类型: {request.audit_type}，可选: {list(AUDIT_TYPE_TO_TASK_TYPE.keys())}",
        )
    audit_type = request.audit_type
    task = AuditTask(
        task_name=f"Agent audit - {document.filename}",
        task_type=AUDIT_TYPE_TO_TASK_TYPE[audit_type],
        status=TaskStatus.PENDING,
        document_ids=[request.document_id],
        progress=0,
        config={},
    )
    set_stage(task, "queued")
    meta = get_execution_meta(task)
    meta["focus"] = request.focus or ""
    set_execution_meta(task, meta)
    append_event(task, "Agent audit queued", stage="queued")
    db.add(task)
    await db.commit()
    await db.refresh(task)

    try:
        http_request.app.state.task_runner_factory().enqueue(task.id)
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e)) from e

    return AgentAuditResponse(task_id=task.id, status="pending", message="Agent audit queued")


@router.get("/status/{task_id}")
async def get_agent_audit_status(
    task_id: int,
    db: AsyncSession = Depends(get_db),
):
    task = (await db.execute(select(AuditTask).where(AuditTask.id == task_id))).scalar_one_or_none()
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return await build_task_payload(db, task)
