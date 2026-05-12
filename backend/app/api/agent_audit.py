"""Agent-based audit API routes."""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_user
from app.core.config import settings
from app.core.database import async_session, get_db
from app.models.user import User
from app.models.audit_task import AuditTask, TaskStatus, TaskType
from app.models.document import Document, DocumentStatus
from app.models.finding import Finding, SeverityLevel
from app.models.risk_alert import RiskAlert, AlertLevel
from app.services.notification import notify_audit_complete, notify_high_risk_finding, notify_task_failed
from app.utils.agent_helpers import AGENT_AVAILABLE, build_audit_graph, build_initial_state, normalize_finding

logger = logging.getLogger(__name__)

router = APIRouter()

AUDIT_TYPE_TO_TASK_TYPE = {
    "deviation": TaskType.DEVIATION_ANALYSIS,
    "sop": TaskType.SOP_COMPLIANCE,
    "change_control": TaskType.CONSISTENCY_CHECK,
}


class AgentAuditRequest(BaseModel):
    document_id: int
    audit_type: str = "deviation"
    focus: Optional[str] = None


class AgentAuditResponse(BaseModel):
    task_id: int
    status: str
    message: str


async def _run_agent_audit(task_id: int, document_id: int, document_path: str, document_type: str, focus: str = ""):
    task = None
    timeout_seconds = settings.DOCUMENT_PROCESS_TIMEOUT or 300

    async with async_session() as db:
        try:
            if not AGENT_AVAILABLE:
                raise RuntimeError("Agent 审计系统不可用，请检查依赖安装")

            result = await db.execute(select(AuditTask).where(AuditTask.id == task_id))
            task = result.scalar_one_or_none()
            if not task:
                logger.error("Task %s not found", task_id)
                return

            graph = build_audit_graph()
            agent_result = await asyncio.wait_for(
                graph.ainvoke(build_initial_state(document_path, document_type, focus)),
                timeout=timeout_seconds,
            )

            for finding_data in agent_result.get("findings", []):
                db.add(normalize_finding(finding_data, task_id, document_id))

            report_md = agent_result.get("report_markdown")
            if report_md:
                from app.models.report import Report, ReportType
                db.add(Report(
                    task_id=task_id,
                    report_type=ReportType.FULL_REPORT,
                    title=f"Agent审计报告 - {document_type}",
                    content=report_md,
                ))

            task.status = TaskStatus.COMPLETED
            task.progress = 100
            task.completed_at = datetime.now(timezone.utc)
            await db.commit()
            logger.info("Agent audit completed for task %s", task_id)

            # Create RiskAlert records for high/critical findings
            result = await db.execute(select(Finding).where(Finding.task_id == task_id))
            saved_findings = result.scalars().all()
            for f in saved_findings:
                if f.severity == SeverityLevel.HIGH:
                    db.add(RiskAlert(finding_id=f.id, alert_level=AlertLevel.CRITICAL))
                elif f.severity == SeverityLevel.MEDIUM:
                    db.add(RiskAlert(finding_id=f.id, alert_level=AlertLevel.WARNING))
            await db.commit()

            # Send notifications
            findings = agent_result.get("findings", [])
            high_count = sum(1 for f in findings if f.get("severity", "").lower() in ("high", "critical"))
            medium_count = sum(1 for f in findings if f.get("severity", "").lower() == "medium")
            top_findings = [
                {"title": f.get("title", ""), "severity": f.get("severity", "")}
                for f in findings if f.get("severity", "").lower() in ("high", "critical")
            ][:3]
            await notify_audit_complete(task.task_name, len(findings), high_count, medium_count, top_findings)
            for f in findings:
                if f.get("severity", "").lower() in ("high", "critical"):
                    await notify_high_risk_finding(task.task_name, f.get("title", ""), f.get("severity", ""), f.get("description", ""))
        except asyncio.TimeoutError:
            logger.error("Agent audit timed out for task %s after %d seconds", task_id, timeout_seconds)
            error_msg = f"审计任务超时（超过 {timeout_seconds} 秒）"
            await notify_task_failed(task.task_name if task is not None else f"Task {task_id}", error_msg)
            try:
                result = await db.execute(select(AuditTask).where(AuditTask.id == task_id))
                task = result.scalar_one_or_none()
                if task:
                    task.status = TaskStatus.FAILED
                    task.error_message = error_msg
                    task.completed_at = datetime.now(timezone.utc)
                    await db.commit()
            except Exception:
                logger.exception("Failed to persist timeout state for task %s", task_id)
        except Exception as exc:
            logger.exception("Agent audit failed for task %s", task_id)
            await notify_task_failed(task.task_name if task is not None else f"Task {task_id}", str(exc))
            try:
                result = await db.execute(select(AuditTask).where(AuditTask.id == task_id))
                task = result.scalar_one_or_none()
                if task:
                    task.status = TaskStatus.FAILED
                    task.error_message = str(exc)
                    task.completed_at = datetime.now(timezone.utc)
                    await db.commit()
            except Exception:
                logger.exception("Failed to persist failure state for task %s", task_id)


@router.post("/run", response_model=AgentAuditResponse)
async def run_agent_audit(
    request: AgentAuditRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not AGENT_AVAILABLE:
        raise HTTPException(status_code=503, detail="Agent 审计系统不可用，请检查依赖安装")

    result = await db.execute(select(Document).where(Document.id == request.document_id))
    document = result.scalar_one_or_none()
    if not document:
        raise HTTPException(status_code=404, detail="文档不存在")
    if document.process_status != DocumentStatus.PROCESSED:
        raise HTTPException(status_code=400, detail="文档尚未处理完成")

    audit_type = request.audit_type if request.audit_type in AUDIT_TYPE_TO_TASK_TYPE else "deviation"
    task = AuditTask(
        task_name=f"Agent审计 - {document.filename}",
        task_type=AUDIT_TYPE_TO_TASK_TYPE[audit_type],
        status=TaskStatus.RUNNING,
        document_ids=[request.document_id],
        progress=0,
    )
    db.add(task)
    await db.commit()
    await db.refresh(task)

    background_tasks.add_task(
        _run_agent_audit,
        task.id,
        document.id,
        document.file_path,
        audit_type,
        request.focus or "",
    )

    return AgentAuditResponse(task_id=task.id, status="running", message="Agent审计已启动")


@router.get("/status/{task_id}")
async def get_agent_audit_status(task_id: int, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    result = await db.execute(select(AuditTask).where(AuditTask.id == task_id))
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")

    return {
        "task_id": task.id,
        "status": task.status.value,
        "progress": task.progress,
        "error_message": task.error_message,
        "completed_at": task.completed_at,
    }
