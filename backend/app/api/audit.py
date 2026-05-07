import sys
import logging
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List
from pydantic import BaseModel

from app.core.database import get_db
from app.models.audit_task import AuditTask, TaskStatus, TaskType
from app.models.document import Document
from app.models.finding import Finding, SeverityLevel, FindingType
from app.services.audit_engine import get_audit_engine, AuditConfig
from app.services.notification import notify_audit_complete

logger = logging.getLogger(__name__)

# Import agent system at module level (once)
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

class AuditTaskCreate(BaseModel):
    task_name: str
    task_type: TaskType
    document_ids: List[int]

@router.post("/tasks")
async def create_audit_task(task_data: AuditTaskCreate, db: AsyncSession = Depends(get_db)):
    task = AuditTask(
        task_name=task_data.task_name,
        task_type=task_data.task_type,
        document_ids=task_data.document_ids,
        status=TaskStatus.PENDING
    )
    db.add(task)
    await db.commit()
    await db.refresh(task)
    return {"id": task.id, "task_name": task.task_name, "status": task.status.value}

@router.get("/tasks")
async def list_audit_tasks(status: TaskStatus = None, db: AsyncSession = Depends(get_db)):
    query = select(AuditTask)
    if status:
        query = query.where(AuditTask.status == status)
    result = await db.execute(query)
    tasks = result.scalars().all()
    return [{"id": t.id, "task_name": t.task_name, "task_type": t.task_type.value,
             "status": t.status.value, "created_at": t.created_at, "progress": t.progress} for t in tasks]

@router.get("/tasks/{task_id}")
async def get_audit_task(task_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(AuditTask).where(AuditTask.id == task_id))
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    return {
        "id": task.id, "task_name": task.task_name, "task_type": task.task_type.value,
        "status": task.status.value, "created_at": task.created_at, "completed_at": task.completed_at,
        "progress": task.progress, "document_ids": task.document_ids
    }

@router.post("/tasks/{task_id}/run")
async def run_audit_task(task_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(AuditTask).where(AuditTask.id == task_id))
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")

    if task.status == TaskStatus.RUNNING:
        raise HTTPException(status_code=400, detail="任务正在运行中")

    task.status = TaskStatus.RUNNING
    task.progress = 0
    await db.commit()

    try:
        if not AGENT_AVAILABLE:
            raise HTTPException(status_code=503, detail="Agent审计系统不可用，请检查依赖安装")

        # Get document paths for agent
        document_paths = []
        for doc_id in task.document_ids:
            doc_result = await db.execute(select(Document).where(Document.id == doc_id))
            doc = doc_result.scalar_one_or_none()
            if doc:
                document_paths.append(doc.file_path)

        if not document_paths:
            raise HTTPException(status_code=400, detail="没有可分析的文档")

        graph = build_audit_graph()
        all_findings = []

        for doc_path in document_paths:
            task.progress = 30
            await db.commit()

            initial_state = {
                "document_name": doc_path,
                "document_type": task.task_type.value,
                "audit_focus": "",
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
            all_findings.extend(agent_result.get("findings", []))

            task.progress = 80
            await db.commit()

        # Map agent findings to DB model
        for finding_data in all_findings:
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
                task_id=task.id,
                finding_type=finding_type,
                severity=severity,
                title=finding_data.get("title", "未知问题"),
                description=finding_data.get("description", ""),
                evidence=finding_data.get("evidence", ""),
                suggestion=finding_data.get("suggestion", ""),
                location=finding_data.get("location", ""),
            )
            db.add(finding)

        task.status = TaskStatus.COMPLETED
        task.progress = 100
        await db.commit()

        high_count = sum(1 for f in all_findings if f.get("severity", "").lower() in ("high", "critical"))
        medium_count = sum(1 for f in all_findings if f.get("severity", "").lower() == "medium")
        await notify_audit_complete(task.task_name, len(all_findings), high_count, medium_count)

        return {"status": "success", "findings_count": len(all_findings)}
    except Exception as e:
        task.status = TaskStatus.FAILED
        task.error_message = str(e)
        await db.commit()
        raise HTTPException(status_code=500, detail=f"审计失败: {str(e)}")

@router.get("/tasks/{task_id}/findings")
async def get_task_findings(task_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Finding).where(Finding.task_id == task_id))
    findings = result.scalars().all()
    return [{"id": f.id, "finding_type": f.finding_type.value, "severity": f.severity.value,
             "title": f.title, "description": f.description, "evidence": f.evidence,
             "suggestion": f.suggestion, "location": f.location} for f in findings]

@router.get("/tasks/{task_id}/risk")
async def get_task_risk_assessment(task_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Finding).where(Finding.task_id == task_id))
    findings = result.scalars().all()

    audit_engine = get_audit_engine()
    risk = await audit_engine.assess_risk([{"severity": f.severity.value} for f in findings])
    return risk


@router.get("/dashboard")
async def get_dashboard_stats(db: AsyncSession = Depends(get_db)):
    """Aggregate stats for dashboard charts."""
    from sqlalchemy import func

    # Task counts by status
    task_counts = {}
    for status in TaskStatus:
        result = await db.execute(
            select(func.count()).select_from(AuditTask).where(AuditTask.status == status)
        )
        task_counts[status.value] = result.scalar()

    # Finding counts by severity
    severity_counts = {}
    from app.models.finding import SeverityLevel
    for level in SeverityLevel:
        result = await db.execute(
            select(func.count()).select_from(Finding).where(Finding.severity == level)
        )
        severity_counts[level.value] = result.scalar()

    # Total counts
    total_tasks = sum(task_counts.values())
    total_findings = sum(severity_counts.values())

    return {
        "task_counts": task_counts,
        "severity_counts": severity_counts,
        "total_tasks": total_tasks,
        "total_findings": total_findings,
    }
