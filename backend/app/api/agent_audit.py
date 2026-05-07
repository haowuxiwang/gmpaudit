"""Agent-based audit API routes.

This module provides API endpoints that use the LangGraph Agent system
for GMP compliance auditing. This replaces the old audit_engine approach.
"""

import sys
import logging
from pathlib import Path
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from typing import Optional

from app.core.database import get_db, async_session
from app.models.document import Document, DocumentStatus
from app.models.audit_task import AuditTask, TaskStatus, TaskType
from app.models.finding import Finding, SeverityLevel, FindingType

logger = logging.getLogger(__name__)

# Import agent system at module level
AGENT_AVAILABLE = False
try:
    _project_root = str(Path(__file__).parent.parent.parent.parent)
    if _project_root not in sys.path:
        sys.path.insert(0, _project_root)
    from agent.graph import build_audit_graph
    AGENT_AVAILABLE = True
except ImportError as e:
    logger.warning(f"Agent system not available: {e}")

router = APIRouter()


class AgentAuditRequest(BaseModel):
    """Request model for agent-based audit"""
    document_id: int
    audit_type: str = "deviation"  # deviation, sop, change_control
    focus: Optional[str] = None


class AgentAuditResponse(BaseModel):
    """Response model for agent-based audit"""
    task_id: int
    status: str
    message: str


async def _run_agent_audit(task_id: int, document_path: str, document_type: str, focus: str = ""):
    """Background task to run agent audit with proper task state management."""
    async with async_session() as db:
        try:
            if not AGENT_AVAILABLE:
                raise RuntimeError("Agent审计系统不可用，请检查依赖安装")

            # Mark task as running
            result = await db.execute(select(AuditTask).where(AuditTask.id == task_id))
            task = result.scalar_one_or_none()
            if not task:
                logger.error(f"Task {task_id} not found")
                return

            graph = build_audit_graph()

            initial_state = {
                "document_name": document_path,
                "document_type": document_type,
                "audit_focus": focus,
                "document_content": "",
                "next_agent": "",
                "supervisor_reasoning": "",
                "matched_regulations": [],
                "regulation_summary": "",
                "findings": [],
                "risk_score": 0,
                "risk_level": "",
                "report_markdown": "",
                "report_path": "",
                "messages": [],
                "iteration": 0,
                "status": "running",
            }

            agent_result = await graph.ainvoke(initial_state)

            # Store findings in database
            findings = agent_result.get("findings", [])
            for finding_data in findings:
                severity_raw = finding_data.get("severity", "medium").lower()
                if severity_raw in ("high", "critical"):
                    severity = SeverityLevel.HIGH
                elif severity_raw in ("low", "info"):
                    severity = SeverityLevel.LOW
                else:
                    severity = SeverityLevel.MEDIUM

                finding_type_raw = finding_data.get("type", "compliance_risk").lower()
                type_map = {
                    "logic_flaw": FindingType.LOGIC_FLAW,
                    "compliance": FindingType.COMPLIANCE_RISK,
                    "compliance_risk": FindingType.COMPLIANCE_RISK,
                    "inconsistency": FindingType.INCONSISTENCY,
                    "missing_info": FindingType.MISSING_INFO,
                    "best_practice": FindingType.BEST_PRACTICE,
                }
                finding_type = type_map.get(finding_type_raw, FindingType.COMPLIANCE_RISK)

                finding = Finding(
                    task_id=task_id,
                    finding_type=finding_type,
                    severity=severity,
                    title=finding_data.get("title", "未知问题"),
                    description=finding_data.get("description", ""),
                    evidence=finding_data.get("evidence", ""),
                    suggestion=finding_data.get("suggestion", ""),
                    location=finding_data.get("location", ""),
                )
                db.add(finding)

            # Update task status to completed
            task.status = TaskStatus.COMPLETED
            task.progress = 100
            await db.commit()
            logger.info(f"Agent audit completed for task {task_id}: {len(findings)} findings")

        except Exception as e:
            logger.error(f"Agent audit failed for task {task_id}: {e}")
            try:
                # Update task status to failed
                result = await db.execute(select(AuditTask).where(AuditTask.id == task_id))
                task = result.scalar_one_or_none()
                if task:
                    task.status = TaskStatus.FAILED
                    task.error_message = str(e)
                    await db.commit()
            except Exception as db_err:
                logger.error(f"Failed to update task status: {db_err}")


@router.post("/run", response_model=AgentAuditResponse)
async def run_agent_audit(
    request: AgentAuditRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db)
):
    """Run an agent-based audit on a document"""

    if not AGENT_AVAILABLE:
        raise HTTPException(status_code=503, detail="Agent审计系统不可用，请检查依赖安装")

    # Get document
    result = await db.execute(select(Document).where(Document.id == request.document_id))
    document = result.scalar_one_or_none()
    if not document:
        raise HTTPException(status_code=404, detail="文档不存在")

    if document.process_status != DocumentStatus.PROCESSED:
        raise HTTPException(status_code=400, detail="文档尚未处理完成")

    # Create audit task
    task = AuditTask(
        task_name=f"Agent审计 - {document.filename}",
        task_type=TaskType.DEVIATION_ANALYSIS,  # Default
        status=TaskStatus.RUNNING,
        document_ids=[request.document_id],
        progress=0
    )
    db.add(task)
    await db.commit()
    await db.refresh(task)

    # Run agent audit in background
    background_tasks.add_task(
        _run_agent_audit,
        task.id,
        document.file_path,
        request.audit_type,
        request.focus or ""
    )

    return AgentAuditResponse(
        task_id=task.id,
        status="running",
        message="Agent审计已启动"
    )


@router.get("/status/{task_id}")
async def get_agent_audit_status(task_id: int, db: AsyncSession = Depends(get_db)):
    """Get the status of an agent audit task"""
    result = await db.execute(select(AuditTask).where(AuditTask.id == task_id))
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")

    return {
        "task_id": task.id,
        "status": task.status.value,
        "progress": task.progress,
        "error_message": task.error_message
    }
