import asyncio
import logging
from collections.abc import Callable
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models.audit_task import AuditTask, TaskStatus, TaskType
from app.models.document import Document, DocumentStatus
from app.models.finding import Finding, SeverityLevel
from app.models.report import Report, ReportType
from app.models.risk_alert import AlertLevel, RiskAlert
from app.services.notification import (
    notify_audit_complete,
    notify_high_risk_finding,
    notify_task_failed,
)
from app.utils.agent_helpers import (
    AGENT_AVAILABLE,
    build_audit_graph,
    build_initial_state,
    normalize_finding,
)

logger = logging.getLogger(__name__)

TASK_TYPE_TO_AGENT_TYPE = {
    TaskType.DEVIATION_ANALYSIS: "deviation",
    TaskType.SOP_COMPLIANCE: "sop",
    TaskType.CONSISTENCY_CHECK: "change_control",
    TaskType.RISK_ASSESSMENT: "deviation",
}

DEFAULT_EXECUTION = {
    "stage": "pending",
    "events": [],
    "started_at": None,
    "completed_at": None,
    "error": None,
    "focus": "",
    "retry_count": 0,
    "documents": [],
}


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def get_execution_meta(task: AuditTask) -> dict[str, Any]:
    meta = dict(DEFAULT_EXECUTION)
    task_config = task.config or {}
    execution = task_config.get("execution", {})
    meta.update(execution)
    meta["events"] = list(meta.get("events", []))
    meta["documents"] = list(meta.get("documents", []))
    return meta


def set_execution_meta(task: AuditTask, meta: dict[str, Any]) -> None:
    task_config = dict(task.config or {})
    task_config["execution"] = meta
    task.config = task_config


def append_event(task: AuditTask, message: str, stage: str | None = None, level: str = "info") -> dict[str, Any]:
    meta = get_execution_meta(task)
    if stage:
        meta["stage"] = stage
    meta["events"].append(
        {
            "time": _utcnow(),
            "stage": meta.get("stage", "pending"),
            "level": level,
            "message": message,
        }
    )
    set_execution_meta(task, meta)
    return meta


def set_stage(task: AuditTask, stage: str, error: str | None = None) -> dict[str, Any]:
    meta = get_execution_meta(task)
    meta["stage"] = stage
    meta["error"] = error
    if stage == "running" and not meta.get("started_at"):
        meta["started_at"] = _utcnow()
    if stage in {"completed", "failed"}:
        meta["completed_at"] = _utcnow()
    set_execution_meta(task, meta)
    return meta


async def build_task_payload(db: AsyncSession, task: AuditTask) -> dict[str, Any]:
    findings_count = (
        await db.execute(select(Finding).where(Finding.task_id == task.id))
    ).scalars().all()
    report = (
        await db.execute(select(Report).where(Report.task_id == task.id).order_by(Report.created_at.desc()))
    ).scalars().first()
    meta = get_execution_meta(task)
    return {
        "id": task.id,
        "task_id": task.id,
        "task_name": task.task_name,
        "task_type": task.task_type.value,
        "status": task.status.value,
        "progress": task.progress or 0,
        "stage": meta.get("stage", "pending"),
        "error": meta.get("error") or task.error_message,
        "error_message": meta.get("error") or task.error_message,
        "created_at": task.created_at,
        "started_at": meta.get("started_at"),
        "completed_at": task.completed_at or meta.get("completed_at"),
        "findings_count": len(findings_count),
        "report_id": report.id if report else None,
        "events": meta.get("events", []),
        "documents": meta.get("documents", []),
    }


def build_aggregate_report(task_name: str, document_results: list[dict[str, Any]], findings: list[dict[str, Any]]) -> str:
    lines = [
        f"# Audit Report - {task_name}",
        "",
        "## Summary",
        f"- Documents: {len(document_results)}",
        f"- Findings: {len(findings)}",
        "",
        "## Document Results",
    ]

    for item in document_results:
        lines.extend(
            [
                f"### {item['filename']}",
                f"- Status: {item['status']}",
                f"- Findings: {item['findings_count']}",
                f"- Risk: {item['risk_level']}",
                "",
            ]
        )

    lines.extend(["## Findings", ""])
    if not findings:
        lines.append("No findings identified.")
        return "\n".join(lines)

    for index, finding in enumerate(findings, start=1):
        lines.extend(
            [
                f"### {index}. [{finding.get('severity', 'medium').upper()}] {finding.get('title', 'Untitled')}",
                finding.get("description", ""),
                f"Document ID: {finding.get('document_id', 'N/A')}",
                "",
            ]
        )
    return "\n".join(lines)


def choose_report_content(
    task_name: str,
    document_results: list[dict[str, Any]],
    findings: list[dict[str, Any]],
    agent_reports: list[str],
) -> tuple[str, dict[str, Any]]:
    non_empty_agent_reports = [report for report in agent_reports if report.strip()]
    if len(document_results) == 1 and non_empty_agent_reports:
        return non_empty_agent_reports[0], {
            "report_source": "agent_report_writer",
            "report_mode": "single_document",
        }

    return build_aggregate_report(task_name, document_results, findings), {
        "report_source": "task_runner_aggregate",
        "report_mode": "multi_document" if len(document_results) > 1 else "fallback_aggregate",
    }


class TaskRunner:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession], max_concurrency: int = 2):
        self._session_factory = session_factory
        self._max_concurrency = max_concurrency
        self._semaphore = asyncio.Semaphore(max_concurrency)
        self._active: dict[int, asyncio.Task] = {}

    async def startup_recover(self) -> None:
        async with self._session_factory() as db:
            result = await db.execute(
                select(AuditTask).where(AuditTask.status.in_([TaskStatus.PENDING, TaskStatus.RUNNING]))
            )
            recoverable = result.scalars().all()
            for task in recoverable:
                append_event(task, "Recovered task after process restart", stage="queued", level="warning")
                task.status = TaskStatus.PENDING
                task.error_message = None
            if recoverable:
                await db.commit()

        for task in recoverable:
            self.enqueue(task.id)

    def enqueue(self, task_id: int) -> bool:
        active = self._active.get(task_id)
        if active and not active.done():
            return False
        if len(self._active) >= self._max_concurrency * 2:
            logger.warning("Task queue full, rejecting task %s", task_id)
            return False
        task = asyncio.create_task(self._run(task_id))
        self._active[task_id] = task
        task.add_done_callback(lambda _: self._active.pop(task_id, None))
        return True

    async def shutdown(self, timeout: float = 30.0) -> None:
        if not self._active:
            return
        logger.info("Waiting for %d active tasks to complete (timeout: %ss)", len(self._active), timeout)
        done, pending = await asyncio.wait(self._active.values(), timeout=timeout)
        for task in pending:
            task.cancel()
            logger.warning("Cancelled task: %s", task.get_name() if hasattr(task, 'get_name') else 'unknown')
        logger.info("TaskRunner shutdown complete: %d completed, %d cancelled", len(done), len(pending))

    async def _run(self, task_id: int) -> None:
        async with self._semaphore:
            async with self._session_factory() as db:
                result = await db.execute(select(AuditTask).where(AuditTask.id == task_id))
                task = result.scalar_one_or_none()
                if task is None:
                    return

                if not AGENT_AVAILABLE:
                    await self._mark_failed(db, task, "Agent audit system is unavailable")
                    return

                task.status = TaskStatus.RUNNING
                task.progress = 0
                task.error_message = None
                set_stage(task, "running")
                append_event(task, "Task execution started", stage="running")
                await db.commit()

            try:
                await self._execute_task(task_id)
            except Exception as exc:
                logger.exception("Task %s failed", task_id)
                async with self._session_factory() as db:
                    result = await db.execute(select(AuditTask).where(AuditTask.id == task_id))
                    task = result.scalar_one_or_none()
                    if task:
                        await self._mark_failed(db, task, str(exc))

    async def _execute_task(self, task_id: int) -> None:
        async with self._session_factory() as db:
            result = await db.execute(select(AuditTask).where(AuditTask.id == task_id))
            task = result.scalar_one_or_none()
            if task is None:
                return

            documents: list[Document] = []
            for doc_id in task.document_ids or []:
                doc = (await db.execute(select(Document).where(Document.id == doc_id))).scalar_one_or_none()
                if doc is not None:
                    documents.append(doc)

            if not documents:
                raise RuntimeError("No documents available for audit")

            if any(doc.process_status != DocumentStatus.PROCESSED for doc in documents):
                raise RuntimeError("All documents must be processed before audit")

            await db.execute(delete(RiskAlert).where(RiskAlert.finding_id.in_(select(Finding.id).where(Finding.task_id == task.id))))
            await db.execute(delete(Finding).where(Finding.task_id == task.id))
            await db.execute(delete(Report).where(Report.task_id == task.id))
            await db.commit()

            graph = build_audit_graph()
            timeout_seconds = 300
            focus = get_execution_meta(task).get("focus", "")
            agent_doc_type = TASK_TYPE_TO_AGENT_TYPE.get(task.task_type, "deviation")

            findings_to_save: list[tuple[dict[str, Any], int]] = []
            document_results: list[dict[str, Any]] = []
            agent_reports: list[str] = []

            for index, document in enumerate(documents, start=1):
                percent_start = int(((index - 1) / len(documents)) * 80)
                percent_end = int((index / len(documents)) * 80)
                task.progress = percent_start
                append_event(task, f"Processing document {document.filename}", stage="parsing")
                await db.commit()

                initial_state = build_initial_state(
                    document_path=document.file_path,
                    document_type=agent_doc_type,
                    focus=focus,
                    document_content=document.content_text or "",
                    document_name=document.filename,
                )
                result_state = await asyncio.wait_for(graph.ainvoke(initial_state), timeout=timeout_seconds)

                doc_findings = result_state.get("findings", [])
                for finding in doc_findings:
                    finding["document_id"] = document.id
                    findings_to_save.append((finding, document.id))

                document_results.append(
                    {
                        "document_id": document.id,
                        "filename": document.filename,
                        "status": result_state.get("status", "completed"),
                        "findings_count": len(doc_findings),
                        "risk_level": result_state.get("risk_level", "unknown"),
                        "report_path": result_state.get("report_path", ""),
                    }
                )
                agent_reports.append(result_state.get("report_markdown", ""))

                task.progress = percent_end
                meta = get_execution_meta(task)
                meta["documents"] = document_results
                set_execution_meta(task, meta)
                append_event(task, f"Completed document {document.filename}", stage="regulation")
                await db.commit()

            persisted_findings: list[dict[str, Any]] = []
            for finding_data, document_id in findings_to_save:
                persisted_findings.append(finding_data)
                db.add(normalize_finding(finding_data, task.id, document_id))

            report_markdown, report_metadata = choose_report_content(
                task.task_name,
                document_results,
                persisted_findings,
                agent_reports,
            )
            append_event(task, "Generating audit report", stage="report")
            await db.commit()
            report = Report(
                task_id=task.id,
                report_type=ReportType.FULL_REPORT,
                title=f"Audit Report - {task.task_name}",
                content=report_markdown,
                report_metadata=report_metadata,
            )
            db.add(report)

            # Pre-compute finding statistics for notification
            high_risk_count = sum(1 for item in persisted_findings if item.get("severity", "").lower() in {"high", "critical"})
            medium_count = sum(1 for item in persisted_findings if item.get("severity", "").lower() == "medium")
            top_findings = [
                {"title": item.get("title", ""), "severity": item.get("severity", "")}
                for item in persisted_findings
                if item.get("severity", "").lower() in {"high", "critical"}
            ][:3]

            # Check risk level for review gate
            if high_risk_count > 0 and not task.auto_approve:
                task.status = TaskStatus.AWAITING_REVIEW
                task.progress = 90
                set_stage(task, "awaiting_review")
                append_event(task, f"Task awaiting review: {high_risk_count} high-risk findings detected", stage="awaiting_review")
                await db.commit()
                await db.refresh(report)
                await notify_audit_complete(task.task_name, len(persisted_findings), high_risk_count, medium_count, top_findings)
                return

            task.status = TaskStatus.COMPLETED
            task.progress = 100
            task.completed_at = datetime.now(timezone.utc)
            set_stage(task, "completed")
            append_event(task, "Task completed successfully", stage="completed")
            await db.commit()
            await db.refresh(report)

            result = await db.execute(select(Finding).where(Finding.task_id == task.id))
            saved_findings = result.scalars().all()
            for finding in saved_findings:
                if finding.severity == SeverityLevel.HIGH:
                    db.add(RiskAlert(finding_id=finding.id, alert_level=AlertLevel.CRITICAL))
                elif finding.severity == SeverityLevel.MEDIUM:
                    db.add(RiskAlert(finding_id=finding.id, alert_level=AlertLevel.WARNING))
            await db.commit()

            await notify_audit_complete(task.task_name, len(persisted_findings), high_risk_count, medium_count, top_findings)
            for item in persisted_findings:
                if item.get("severity", "").lower() in {"high", "critical"}:
                    await notify_high_risk_finding(
                        task.task_name,
                        item.get("title", ""),
                        item.get("severity", ""),
                        item.get("description", ""),
                    )

    async def _mark_failed(self, db: AsyncSession, task: AuditTask, error: str) -> None:
        task.status = TaskStatus.FAILED
        task.error_message = error
        task.completed_at = datetime.now(timezone.utc)
        set_stage(task, "failed", error=error)
        append_event(task, error, stage="failed", level="error")
        await db.commit()
        await notify_task_failed(task.task_name, error)


def get_task_runner_factory(
    session_factory: async_sessionmaker[AsyncSession],
    max_concurrency: int,
) -> Callable[[], TaskRunner]:
    runner: TaskRunner | None = None

    def factory() -> TaskRunner:
        nonlocal runner
        if runner is None:
            runner = TaskRunner(session_factory=session_factory, max_concurrency=max_concurrency)
        return runner

    return factory


def validate_findings(findings: list[dict]) -> list[dict]:
    validated = []
    for f in findings:
        if not f.get("title") or not f.get("description"):
            continue
        if f.get("title") == "Untitled finding":
            continue
        if len(f.get("description", "")) < 10:
            continue
        validated.append(f)
    return validated
