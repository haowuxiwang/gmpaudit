from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List
from pydantic import BaseModel

from app.core.database import get_db
from app.models.audit_task import AuditTask, TaskStatus, TaskType
from app.models.document import Document
from app.models.finding import Finding
from app.services.audit_engine import get_audit_engine, AuditConfig

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
        documents = []
        for doc_id in task.document_ids:
            doc_result = await db.execute(select(Document).where(Document.id == doc_id))
            doc = doc_result.scalar_one_or_none()
            if doc and doc.content_text:
                documents.append(doc.content_text)

        if not documents:
            raise HTTPException(status_code=400, detail="没有可分析的文档内容")

        audit_engine = get_audit_engine()
        config = AuditConfig()

        all_findings = []

        if task.task_type == TaskType.DEVIATION_ANALYSIS:
            for doc in documents:
                findings = await audit_engine.analyze_deviation(doc, config)
                all_findings.extend(findings)
        elif task.task_type == TaskType.SOP_COMPLIANCE:
            for doc in documents:
                findings = await audit_engine.analyze_sop(doc, config)
                all_findings.extend(findings)
        elif task.task_type == TaskType.CONSISTENCY_CHECK:
            findings = await audit_engine.check_consistency(documents, config)
            all_findings.extend(findings)

        for finding_data in all_findings[:config.max_findings]:
            finding = Finding(
                task_id=task.id,
                finding_type=finding_data.get("type", "logic_flaw"),
                severity=finding_data.get("severity", "medium"),
                title=finding_data.get("title", "未知问题"),
                description=finding_data.get("description", ""),
                evidence=finding_data.get("evidence", ""),
                suggestion=finding_data.get("suggestion", ""),
                location=finding_data.get("location", "")
            )
            db.add(finding)

        task.status = TaskStatus.COMPLETED
        task.progress = 100
        await db.commit()

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
