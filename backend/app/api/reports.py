import asyncio
import html as html_module
import io
import logging
from datetime import UTC

logger = logging.getLogger(__name__)

import bleach
import markdown
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import HTMLResponse, StreamingResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.models.audit_task import AuditTask
from app.models.finding import Finding
from app.models.report import Report, ReportType
from app.services.llm_engine import get_llm_engine

router = APIRouter()

# Tags allowed in markdown-generated HTML (strip <script>, <iframe>, etc.)
_ALLOWED_TAGS = [
    "h1",
    "h2",
    "h3",
    "h4",
    "h5",
    "h6",
    "p",
    "ul",
    "ol",
    "li",
    "table",
    "thead",
    "tbody",
    "tr",
    "th",
    "td",
    "code",
    "pre",
    "blockquote",
    "strong",
    "em",
    "a",
    "br",
    "hr",
    "span",
    "div",
]
_ALLOWED_ATTRS = {"a": ["href", "title"]}


def _sanitize_html(html_str: str) -> str:
    """Strip dangerous tags from markdown-generated HTML."""
    return bleach.clean(html_str, tags=_ALLOWED_TAGS, attributes=_ALLOWED_ATTRS, strip=True)


@router.get("/")
async def list_reports(
    task_id: int | None = None,
    page: int = Query(1, ge=1, le=10000),
    page_size: int = Query(20, ge=1, le=100),
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
                "created_at": report.created_at.replace(tzinfo=UTC).isoformat() if report.created_at else None,
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
        raise HTTPException(status_code=404, detail="任务不存在")

    findings = (await db.execute(select(Finding).where(Finding.task_id == task_id))).scalars().all()
    if not findings:
        raise HTTPException(status_code=400, detail="该任务暂无审计发现")

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
    try:
        report_content = await asyncio.wait_for(
            llm.generate_report(findings_data), timeout=settings.LLM_REQUEST_TIMEOUT
        )
    except ValueError as exc:
        raise HTTPException(status_code=503, detail=f"LLM 服务不可用: {exc}") from exc
    except TimeoutError:
        raise HTTPException(status_code=504, detail=f"LLM 调用超时（{settings.LLM_REQUEST_TIMEOUT}秒）") from None
    except Exception as exc:
        logger.exception("Report generation failed")
        raise HTTPException(status_code=502, detail="LLM 调用失败，请检查配置") from exc

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
        raise HTTPException(status_code=404, detail="报告不存在")

    return {
        "id": report.id,
        "task_id": report.task_id,
        "report_type": report.report_type.value,
        "title": report.title,
        "content": report.content,
        "created_at": report.created_at.replace(tzinfo=UTC).isoformat() if report.created_at else None,
        "report_metadata": report.report_metadata,
    }


@router.get("/{report_id}/export/html", response_class=HTMLResponse)
async def export_report_html(
    report_id: int,
    db: AsyncSession = Depends(get_db),
):
    report = (await db.execute(select(Report).where(Report.id == report_id))).scalar_one_or_none()
    if not report:
        raise HTTPException(status_code=404, detail="报告不存在")

    safe_title = html_module.escape(report.title or "Untitled")
    created_display = report.created_at.replace(tzinfo=UTC).isoformat() if report.created_at else ""
    html_body = _sanitize_html(markdown.markdown(report.content or "", extensions=["tables", "fenced_code"]))
    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<title>{safe_title}</title>
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
<h1>{safe_title}</h1>
<div class="meta">类型: {report.report_type.value} | 生成时间: {created_display}</div>
{html_body}
</body>
</html>"""
    return HTMLResponse(content=html)


@router.get("/{report_id}/export/pdf")
async def export_report_pdf(
    report_id: int,
    db: AsyncSession = Depends(get_db),
):
    report = (await db.execute(select(Report).where(Report.id == report_id))).scalar_one_or_none()
    if not report:
        raise HTTPException(status_code=404, detail="报告不存在")

    safe_title = html_module.escape(report.title or "Untitled")
    created_display = report.created_at.replace(tzinfo=UTC).isoformat() if report.created_at else ""
    html_body = _sanitize_html(markdown.markdown(report.content or "", extensions=["tables", "fenced_code"]))
    full_html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<title>{safe_title}</title>
<style>
  body {{ font-family: STSong-Light, sans-serif; margin: 0 auto; padding: 40px 20px; color: #1a1a1a; line-height: 1.6; }}
  h1 {{ color: #D97757; border-bottom: 2px solid #E8E5E0; padding-bottom: 8px; }}
  h2 {{ color: #1a1a1a; margin-top: 24px; }}
  h3 {{ color: #374151; }}
  table {{ width: 100%; margin: 16px 0; }}
  th, td {{ border: 1px solid #E8E5E0; padding: 8px 12px; text-align: left; }}
  th {{ background: #FAFAF8; font-weight: bold; }}
  code {{ background: #FAFAF8; padding: 2px 6px; font-size: 10pt; }}
  pre {{ background: #FAFAF8; padding: 16px; }}
  .meta {{ color: #6B7280; font-size: 10pt; margin-bottom: 24px; }}
  @page {{ size: A4; margin: 2cm; }}
</style>
</head>
<body>
<h1>{safe_title}</h1>
<div class="meta">类型: {report.report_type.value} | 生成时间: {created_display}</div>
{html_body}
</body>
</html>"""

    try:
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.cidfonts import UnicodeCIDFont

        pdfmetrics.registerFont(UnicodeCIDFont("STSong-Light"))

        from xhtml2pdf import pisa

        pdf_buffer = io.BytesIO()
        status = await asyncio.to_thread(pisa.CreatePDF, full_html, dest=pdf_buffer, encoding="utf-8")
        if status.err:
            raise RuntimeError(f"PDF rendering errors: {status.err}")
        pdf_bytes = pdf_buffer.getvalue()
    except Exception as exc:
        raise HTTPException(status_code=500, detail="PDF 生成失败") from exc

    import re

    safe_filename = re.sub(r"[^\w一-鿿\-]", "_", (report.title or "report"))[:100]
    return StreamingResponse(
        io.BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{safe_filename}.pdf"'},
    )
