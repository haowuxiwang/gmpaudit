import markdown
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.audit_task import AuditTask
from app.models.finding import Finding
from app.models.report import Report, ReportType
from app.services.llm_engine import get_llm_engine

router = APIRouter()


@router.get("/")
async def list_reports(
    task_id: int | None = None,
    page: int = 1,
    page_size: int = 20,
    db: AsyncSession = Depends(get_db),
):
    query = select(Report)
    count_query = select(func.count()).select_from(Report)

    if task_id:
        query = query.where(Report.task_id == task_id)
        count_query = count_query.where(Report.task_id == task_id)

    total = (await db.execute(count_query)).scalar()
    query = query.order_by(Report.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    reports = (await db.execute(query)).scalars().all()

    return {
        "items": [
            {
                "id": report.id,
                "task_id": report.task_id,
                "report_type": report.report_type.value,
                "title": report.title,
                "created_at": report.created_at,
                "report_metadata": report.report_metadata,
            }
            for report in reports
        ],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.post("/generate/{task_id}")
async def generate_report(
    task_id: int,
    db: AsyncSession = Depends(get_db),
):
    task = (await db.execute(select(AuditTask).where(AuditTask.id == task_id))).scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    findings = (await db.execute(select(Finding).where(Finding.task_id == task_id))).scalars().all()
    if not findings:
        raise HTTPException(status_code=400, detail="No findings available for this task")

    llm = get_llm_engine()
    findings_data = [
        {
            "severity": finding.severity.value,
            "title": finding.title,
            "description": finding.description,
            "evidence": finding.evidence or "",
            "suggestion": finding.suggestion or "",
            "location": finding.location or "",
        }
        for finding in findings
    ]
    report_content = await llm.generate_report(findings_data)

    report = Report(
        task_id=task_id,
        report_type=ReportType.FULL_REPORT,
        title=f"Audit Report - {task.task_name}",
        content=report_content,
        report_metadata={
            "findings_count": len(findings),
            "task_type": task.task_type.value,
            "report_source": "backend_llm_generate",
            "report_mode": "manual_regeneration",
        },
    )
    db.add(report)
    await db.commit()
    await db.refresh(report)

    return {
        "id": report.id,
        "title": report.title,
        "content": report_content,
        "report_metadata": report.report_metadata,
    }


@router.get("/{report_id}")
async def get_report(
    report_id: int,
    db: AsyncSession = Depends(get_db),
):
    report = (await db.execute(select(Report).where(Report.id == report_id))).scalar_one_or_none()
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")

    return {
        "id": report.id,
        "task_id": report.task_id,
        "report_type": report.report_type.value,
        "title": report.title,
        "content": report.content,
        "created_at": report.created_at,
        "report_metadata": report.report_metadata,
    }


@router.get("/{report_id}/export/html", response_class=HTMLResponse)
async def export_report_html(
    report_id: int,
    db: AsyncSession = Depends(get_db),
):
    report = (await db.execute(select(Report).where(Report.id == report_id))).scalar_one_or_none()
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")

    html_body = markdown.markdown(report.content or "", extensions=["tables", "fenced_code"])
    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<title>{report.title}</title>
<style>
  body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; max-width: 800px; margin: 40px auto; padding: 0 20px; color: #1a1a1a; line-height: 1.6; }}
  h1 {{ color: #D97757; border-bottom: 2px solid #E8E5E0; padding-bottom: 8px; }}
  h2 {{ color: #1a1a1a; margin-top: 24px; }}
  table {{ border-collapse: collapse; width: 100%; margin: 16px 0; }}
  th, td {{ border: 1px solid #E8E5E0; padding: 8px 12px; text-align: left; }}
  th {{ background: #FAFAF8; font-weight: 600; }}
  code {{ background: #FAFAF8; padding: 2px 6px; border-radius: 4px; font-size: 0.9em; }}
  pre {{ background: #FAFAF8; padding: 16px; border-radius: 8px; overflow-x: auto; }}
  .meta {{ color: #6B7280; font-size: 0.9em; margin-bottom: 24px; }}
  @media print {{ body {{ margin: 20px; }} }}
</style>
</head>
<body>
<h1>{report.title}</h1>
<div class="meta">类型: {report.report_type.value} | 生成时间: {report.created_at}</div>
{html_body}
</body>
</html>"""
    return HTMLResponse(content=html)
