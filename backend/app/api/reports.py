from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_db
from app.models.report import Report, ReportType
from app.models.finding import Finding
from app.models.audit_task import AuditTask
from app.services.llm_engine import get_llm_engine

router = APIRouter()

@router.get("/")
async def list_reports(task_id: int = None, db: AsyncSession = Depends(get_db)):
    query = select(Report)
    if task_id:
        query = query.where(Report.task_id == task_id)
    result = await db.execute(query)
    reports = result.scalars().all()
    return [{"id": r.id, "task_id": r.task_id, "report_type": r.report_type.value,
             "title": r.title, "created_at": r.created_at} for r in reports]

@router.post("/generate/{task_id}")
async def generate_report(task_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(AuditTask).where(AuditTask.id == task_id))
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")

    findings_result = await db.execute(select(Finding).where(Finding.task_id == task_id))
    findings = findings_result.scalars().all()
    if not findings:
        raise HTTPException(status_code=400, detail="没有审计发现")

    llm = get_llm_engine()
    findings_data = [{"severity": f.severity.value, "title": f.title, "description": f.description} for f in findings]
    report_content = await llm.generate_report(findings_data)

    report = Report(
        task_id=task_id,
        report_type=ReportType.FULL_REPORT,
        title=f"审计报告 - {task.task_name}",
        content=report_content,
        report_metadata={"findings_count": len(findings), "task_type": task.task_type.value}
    )
    db.add(report)
    await db.commit()
    await db.refresh(report)

    return {"id": report.id, "title": report.title, "content": report_content}

@router.get("/{report_id}")
async def get_report(report_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Report).where(Report.id == report_id))
    report = result.scalar_one_or_none()
    if not report:
        raise HTTPException(status_code=404, detail="报告不存在")
    return {"id": report.id, "task_id": report.task_id, "report_type": report.report_type.value,
            "title": report.title, "content": report.content, "created_at": report.created_at}
