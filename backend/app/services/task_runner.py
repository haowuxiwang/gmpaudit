import asyncio
import hashlib
import logging
from collections.abc import Callable
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from app.services.event_bus import EventBus

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.orm.attributes import flag_modified

from app.core.config import settings
from app.models.audit_task import AuditTask, TaskStatus, TaskType
from app.models.document import Document, DocumentStatus
from app.models.finding import Finding, SeverityLevel
from app.models.report import Report, ReportType
from app.models.risk_alert import AlertLevel, RiskAlert
from app.services.notification import (
    is_feishu_configured,
    notify_audit_complete,
    notify_high_risk_finding,
    notify_task_failed,
)
from app.utils.agent_helpers import (
    build_initial_state,
    get_build_audit_graph,
    is_agent_available,
    normalize_finding,
)


def _safe_flag_modified(instance, attr: str) -> None:
    """Flag attribute as modified, safe for mock objects in tests."""
    if hasattr(instance, "_sa_instance_state"):
        flag_modified(instance, attr)


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
    return datetime.now(UTC).isoformat()


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
    _safe_flag_modified(task, "config")
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
    # Force SQLAlchemy to detect the JSON column change (nested dict mutations
    # may not be tracked reliably with aiosqlite + plain Column(JSON))
    _safe_flag_modified(task, "config")
    return meta


async def build_task_payload(
    db: AsyncSession,
    task: AuditTask,
    *,
    _findings_count: int | None = None,
    _report_id: int | None = None,
) -> dict[str, Any]:
    if _findings_count is None:
        _findings_count = len((await db.execute(select(Finding).where(Finding.task_id == task.id))).scalars().all())
    if _report_id is None:
        report = (
            (await db.execute(select(Report).where(Report.task_id == task.id).order_by(Report.created_at.desc())))
            .scalars()
            .first()
        )
        _report_id = report.id if report else None
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
        "created_at": task.created_at.replace(tzinfo=UTC).isoformat() if task.created_at else None,
        "started_at": meta.get("started_at"),
        "completed_at": task.completed_at.replace(tzinfo=UTC).isoformat()
        if task.completed_at
        else meta.get("completed_at"),
        "findings_count": _findings_count,
        "report_id": _report_id,
        "events": meta.get("events", []),
        "documents": meta.get("documents", []),
        "trace": (task.config or {}).get("_trace"),
    }


def build_aggregate_report(
    task_name: str, document_results: list[dict[str, Any]], findings: list[dict[str, Any]]
) -> str:
    lines = [
        f"# 审计报告 - {task_name}",
        "",
        "## 概要",
        f"- 文档数量: {len(document_results)}",
        f"- 发现数量: {len(findings)}",
        "",
        "## 文档结果",
    ]

    for item in document_results:
        lines.extend(
            [
                f"### {item['filename']}",
                f"- 状态: {item['status']}",
                f"- 发现数: {item['findings_count']}",
                f"- 风险等级: {item['risk_level']}",
                "",
            ]
        )

    lines.extend(["## 审计发现", ""])
    if not findings:
        lines.append("未发现审计问题。")
        return "\n".join(lines)

    for index, finding in enumerate(findings, start=1):
        lines.extend(
            [
                f"### {index}. [{finding.get('severity', 'medium').upper()}] {finding.get('title', '无标题')}",
                finding.get("description", ""),
                f"文档编号: {finding.get('document_id', 'N/A')}",
                "",
            ]
        )
    return "\n".join(lines)


def choose_report_content(
    task_name: str,
    document_results: list[dict[str, Any]],
    findings: list[dict[str, Any]],
    agent_reports: list[str],
    agent_report_sources: list[str] | None = None,
) -> tuple[str, dict[str, Any]]:
    non_empty_agent_reports = [report for report in agent_reports if report.strip()]
    if len(document_results) == 1 and non_empty_agent_reports:
        source = "agent_report_writer"
        mode = "single_document"
        # Check if agent reported fallback (LLM unavailable)
        if agent_report_sources and "fallback" in agent_report_sources:
            source = "fallback"
            mode = "degraded"
        return non_empty_agent_reports[0], {
            "report_source": source,
            "report_mode": mode,
        }

    source = "task_runner_aggregate"
    mode = "multi_document" if len(document_results) > 1 else "fallback_aggregate"
    # Check if any document used fallback
    if agent_report_sources and "fallback" in agent_report_sources:
        source = "partial_fallback" if len(document_results) > 1 else "fallback"
        mode = "degraded"
    return build_aggregate_report(task_name, document_results, findings), {
        "report_source": source,
        "report_mode": mode,
    }


def _build_node_summary(node_name: str, output: dict) -> str:
    """Build a user-friendly Chinese summary for a completed agent node."""
    if node_name == "regulation_expert":
        regs = output.get("matched_regulations", [])
        source = "知识图谱" if "lightrag" in str(output.get("regulation_summary", "")) else "内置法规库"
        return f"法规检索完成，从{source}找到 {len(regs)} 条相关条款"

    if node_name == "risk_assessor":
        findings = output.get("findings", [])
        risk_level = output.get("risk_level", "未知")
        return f"风险评估完成，发现 {len(findings)} 个问题，风险等级: {risk_level}"

    if node_name == "report_writer":
        report_path = output.get("report_path", "")
        if report_path:
            return "审计报告生成完成"
        return "报告生成完成（使用备用模板）"

    if node_name == "parse_doc":
        doc_name = output.get("document_name", "")
        doc_type = output.get("document_type", "")
        return f"文档解析完成: {doc_name} (类型: {doc_type})"

    return f"{node_name} 完成"


_RESULT_CACHE_MAX_SIZE = 50
_RESULT_CACHE_TTL = 1800  # 30 minutes

# Cached audit graph (compiled once, reused across all documents)
_cached_audit_graph = None


def _get_audit_graph():
    """Return cached audit graph, building it once on first call."""
    global _cached_audit_graph
    if _cached_audit_graph is None:
        build_fn = get_build_audit_graph()
        if build_fn is None:
            raise RuntimeError("Agent system is not available")
        _cached_audit_graph = build_fn()
    return _cached_audit_graph


class TaskRunner:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        max_concurrency: int = 2,
        llm_concurrency: int = 3,
        event_bus: "EventBus | None" = None,
    ):
        self._session_factory = session_factory
        self._max_concurrency = max_concurrency
        self._semaphore = asyncio.Semaphore(max_concurrency)
        self._active: dict[int, asyncio.Task] = {}
        self._event_bus = event_bus
        # LLM concurrency limiter for parallel document processing
        self._llm_semaphore = asyncio.Semaphore(llm_concurrency)
        # Per-document result cache: key -> (result_state, timestamp)
        self._result_cache: dict[str, tuple[dict, float]] = {}

    async def _publish(self, task_id: int, event: dict[str, Any]) -> None:
        """Publish event to the in-memory event bus (non-blocking)."""
        if self._event_bus:
            await self._event_bus.publish(task_id, event)

    async def _publish_done(self, task_id: int, status: str) -> None:
        """Publish terminal event to the in-memory event bus."""
        if self._event_bus:
            await self._event_bus.publish_done(task_id, status)

    async def _publish_progress(self, task_id: int, percent: int, stage: str) -> None:
        """Publish progress event to the in-memory event bus and persist to DB."""
        if self._event_bus:
            await self._event_bus.publish(
                task_id,
                {
                    "type": "progress",
                    "data": {"percent": percent, "stage": stage},
                },
            )
        # Atomic UPDATE: persist both progress AND stage to DB
        # Stage is stored in config.execution.stage for reconnect recovery
        try:
            from sqlalchemy import update as sa_update

            async with self._session_factory() as db:
                # Update progress column
                await db.execute(
                    sa_update(AuditTask)
                    .where(AuditTask.id == task_id, AuditTask.progress < percent)
                    .values(progress=percent)
                )
                # Also persist stage to config JSON for reconnect recovery
                # Read-modify-write on the ORM object for the JSON column
                task_row = (
                    await db.execute(select(AuditTask).where(AuditTask.id == task_id))
                ).scalar_one_or_none()
                if task_row and task_row.config:
                    execution = task_row.config.get("execution", {})
                    execution["stage"] = stage
                    task_row.config["execution"] = execution
                    _safe_flag_modified(task_row, "config")
                await db.commit()
        except Exception:
            logger.debug("Failed to persist progress for task %d (non-critical)", task_id)

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
            raise RuntimeError(f"Task queue full ({len(self._active)}/{self._max_concurrency * 2}), try again later")
        task = asyncio.create_task(self._run(task_id))
        self._active[task_id] = task
        task.add_done_callback(lambda _: self._active.pop(task_id, None))
        return True

    async def cancel(self, task_id: int) -> bool:
        """Cancel a running task."""
        active = self._active.get(task_id)
        if active is None or active.done():
            return False
        active.cancel()
        return True

    async def shutdown(self, timeout: float = 30.0) -> None:
        if not self._active:
            return
        logger.info("Waiting for %d active tasks to complete (timeout: %ss)", len(self._active), timeout)
        done, pending = await asyncio.wait(self._active.values(), timeout=timeout)
        for task in pending:
            task.cancel()
            logger.warning("Cancelled task: %s", task.get_name() if hasattr(task, "get_name") else "unknown")
        logger.info("TaskRunner shutdown complete: %d completed, %d cancelled", len(done), len(pending))

    async def _run(self, task_id: int) -> None:
        async with self._semaphore:
            async with self._session_factory() as db:
                result = await db.execute(select(AuditTask).where(AuditTask.id == task_id))
                task = result.scalar_one_or_none()
                if task is None:
                    return

                if not is_agent_available():
                    await self._mark_failed(db, task, "Agent audit system is unavailable")
                    return

                doc_ids = task.document_ids or []

                task.status = TaskStatus.RUNNING
                task.progress = 0
                task.error_message = None
                set_stage(task, "running")
                append_event(task, "Task execution started", stage="running")
                await db.commit()
                await self._publish(
                    task_id,
                    {
                        "type": "event",
                        "data": {
                            "time": datetime.now(UTC).isoformat(),
                            "stage": "running",
                            "level": "info",
                            "message": "Task execution started",
                        },
                    },
                )

            # Task-level total timeout: per-document timeout * doc count + 5 min buffer
            total_timeout = settings.AGENT_TASK_TIMEOUT * len(doc_ids) + 300
            try:
                await asyncio.wait_for(
                    self._execute_task(task_id),
                    timeout=total_timeout,
                )
            except TimeoutError:
                logger.error("Task %s timed out after %ds", task_id, total_timeout)
                async with self._session_factory() as db:
                    result = await db.execute(select(AuditTask).where(AuditTask.id == task_id))
                    task = result.scalar_one_or_none()
                    if task:
                        await self._mark_failed(db, task, f"Task total timeout ({total_timeout}s)")
            except asyncio.CancelledError:
                logger.info("Task %s was cancelled", task_id)
                async with self._session_factory() as db:
                    result = await db.execute(select(AuditTask).where(AuditTask.id == task_id))
                    task = result.scalar_one_or_none()
                    if task:
                        task.status = TaskStatus.CANCELLED
                        task.completed_at = datetime.now(UTC)
                        task.error_message = "Task cancelled"
                        set_stage(task, "cancelled")
                        append_event(task, "Task cancelled by user", stage="cancelled", level="warning")
                        await db.commit()
                        await self._publish(
                            task.id,
                            {
                                "type": "event",
                                "data": {
                                    "time": datetime.now(UTC).isoformat(),
                                    "stage": "cancelled",
                                    "level": "warning",
                                    "message": "Task cancelled by user",
                                },
                            },
                        )
                        await self._publish_done(task.id, "cancelled")
            except Exception as exc:
                logger.exception("Task %s failed", task_id)
                async with self._session_factory() as db:
                    result = await db.execute(select(AuditTask).where(AuditTask.id == task_id))
                    task = result.scalar_one_or_none()
                    if task:
                        await self._mark_failed(db, task, str(exc))

    async def _process_single_document(
        self,
        task_id: int,
        document: "Document",
        agent_doc_type: str,
        focus: str,
        timeout_seconds: int,
        doc_index: int,
        total_docs: int,
    ) -> dict[str, Any]:
        """Process a single document through the agent pipeline.

        Returns a dict with keys: findings, document_result, report, report_source, trace, error.
        Errors are captured in the 'error' key rather than raised (for parallel isolation).
        """
        from agent.trace import PipelineTrace, clear_current_trace, get_current_trace, set_current_trace

        NODE_STAGE_MAP = {
            "parse_doc": "parsing",
            "regulation_expert": "regulation",
            "risk_assessor": "risk",
            "report_writer": "report",
        }
        NODE_PROGRESS_MAP = {
            "parse_doc": 5,
            "regulation_expert": 25,
            "risk_assessor": 50,
            "report_writer": 70,
        }
        NODE_START_MESSAGES = {
            "parse_doc": "正在解析文档...",
            "regulation_expert": "正在检索相关法规条款...",
            "risk_assessor": "正在评估合规风险...",
            "report_writer": "正在生成审计报告...",
        }

        percent_start = int(((doc_index - 1) / total_docs) * 80)
        percent_end = int((doc_index / total_docs) * 80)

        await self._publish(
            task_id,
            {
                "type": "event",
                "data": {
                    "time": datetime.now(UTC).isoformat(),
                    "stage": "parsing",
                    "level": "info",
                    "message": f"Processing document {document.filename}",
                },
            },
        )
        await self._publish_progress(task_id, percent_start, "parsing")

        # Check per-document result cache
        import time as _time

        _cache_key_str = f"{document.content_text or ''}:{agent_doc_type}:{focus or ''}"
        _cache_key = hashlib.md5(_cache_key_str.encode()).hexdigest()
        _cached = self._result_cache.get(_cache_key)
        if _cached and (_time.time() - _cached[1]) < _RESULT_CACHE_TTL:
            logger.info("Cache hit for document %s, skipping agent pipeline", document.filename)
            cached_result = _cached[0].copy()
            cached_result["_cache_hit"] = True
            return cached_result

        graph = _get_audit_graph()
        initial_state = build_initial_state(
            document_path=document.file_path,
            document_type=agent_doc_type,
            focus=focus,
            document_content=document.content_text or "",
            document_name=document.filename,
        )

        trace = PipelineTrace(document_name=document.filename)
        set_current_trace(trace)
        thinking_events: list[dict] = []

        try:

            async def _stream_graph():
                result = {}
                async for event in graph.astream_events(initial_state, version="v2"):
                    kind = event.get("event", "")
                    node_name = event.get("name", "")

                    if kind == "on_chain_start" and node_name in NODE_STAGE_MAP:
                        stage_name = NODE_STAGE_MAP[node_name]
                        thinking_event = {
                            "stage": stage_name,
                            "node": node_name,
                            "status": "started",
                            "message": NODE_START_MESSAGES.get(node_name, f"Agent {node_name} started"),
                            "doc_name": document.filename,
                        }
                        await self._publish(
                            task_id,
                            {
                                "type": "agent_thinking",
                                "data": thinking_event,
                            },
                        )
                        # Persist for SSE reconnect replay
                        thinking_events.append(thinking_event)
                        if node_name in NODE_PROGRESS_MAP:
                            node_pct = NODE_PROGRESS_MAP[node_name]
                            progress = percent_start + int((node_pct / 80) * (percent_end - percent_start))
                            await self._publish_progress(task_id, progress, stage_name)

                    elif kind == "on_chain_end" and node_name in NODE_STAGE_MAP:
                        output = event.get("data", {}).get("output", {})
                        if isinstance(output, dict):
                            summary = _build_node_summary(node_name, output)
                            thinking_event = {
                                "stage": NODE_STAGE_MAP[node_name],
                                "node": node_name,
                                "status": "completed",
                                "message": summary,
                                "doc_name": document.filename,
                            }
                            await self._publish(
                                task_id,
                                {
                                    "type": "agent_thinking",
                                    "data": thinking_event,
                                },
                            )
                            # Persist for SSE reconnect replay
                            thinking_events.append(thinking_event)
                            result.update(output)
                return result

            result_state = await asyncio.wait_for(_stream_graph(), timeout=timeout_seconds)

            current_trace = get_current_trace()
            if current_trace:
                current_trace.finalize(status=result_state.get("status", "completed"))
                result_state["_trace"] = current_trace.to_dict()

            if not result_state:
                logger.warning("Agent graph returned no result for document %s, using empty state", document.filename)
                result_state = {"findings": [], "status": "completed", "risk_level": "unknown"}

            # Detect LLM auth failure and publish user-friendly warning
            report_source = result_state.get("report_source", "")
            if report_source == "fallback":
                await self._publish(
                    task_id,
                    {
                        "type": "agent_thinking",
                        "data": {
                            "stage": "report",
                            "node": "report_writer",
                            "status": "completed",
                            "message": "API Key 无效或已过期，使用了备用模板生成报告。请在「设置」页面重新配置 API Key",
                            "doc_name": document.filename,
                        },
                    },
                )

            doc_findings = result_state.get("findings", [])
            for finding in doc_findings:
                finding["document_id"] = document.id

            await self._publish_progress(task_id, percent_end, "report")
            await self._publish(
                task_id,
                {
                    "type": "event",
                    "data": {
                        "time": datetime.now(UTC).isoformat(),
                        "stage": "report",
                        "level": "info",
                        "message": f"Completed document {document.filename}",
                    },
                },
            )

            # Cache the result for repeat documents
            _result_to_cache = {
                "findings": doc_findings,
                "document_result": {
                    "document_id": document.id,
                    "filename": document.filename,
                    "status": result_state.get("status", "completed"),
                    "findings_count": len(doc_findings),
                    "risk_level": result_state.get("risk_level", "unknown"),
                    "report_path": result_state.get("report_path", ""),
                },
                "report": result_state.get("report_markdown", ""),
                "report_source": result_state.get("report_source", ""),
                "trace": result_state.get("_trace"),
                "thinking_events": thinking_events,
                "error": None,
            }
            if len(self._result_cache) >= _RESULT_CACHE_MAX_SIZE:
                oldest_key = min(self._result_cache, key=lambda k: self._result_cache[k][1])
                del self._result_cache[oldest_key]
            self._result_cache[_cache_key] = (_result_to_cache, _time.time())

            return _result_to_cache

        except TimeoutError:
            logger.error("Document %s timed out after %ds", document.filename, timeout_seconds)
            return {
                "findings": [],
                "document_result": {
                    "document_id": document.id,
                    "filename": document.filename,
                    "status": "timeout",
                    "findings_count": 0,
                    "risk_level": "unknown",
                    "report_path": "",
                },
                "report": "",
                "report_source": "timeout",
                "trace": None,
                "thinking_events": thinking_events,
                "error": f"Document {document.filename} processing timed out",
            }
        except Exception as e:
            logger.exception("Document %s failed", document.filename)
            return {
                "findings": [],
                "document_result": {
                    "document_id": document.id,
                    "filename": document.filename,
                    "status": "failed",
                    "findings_count": 0,
                    "risk_level": "unknown",
                    "report_path": "",
                },
                "report": "",
                "report_source": "error",
                "trace": None,
                "thinking_events": thinking_events,
                "error": str(e),
            }
        finally:
            clear_current_trace()

    async def _execute_task(self, task_id: int) -> None:
        async with self._session_factory() as db:
            result = await db.execute(select(AuditTask).where(AuditTask.id == task_id))
            task = result.scalar_one_or_none()
            if task is None:
                return

            doc_ids = task.document_ids or []
            if doc_ids:
                result = await db.execute(select(Document).where(Document.id.in_(doc_ids)))
                documents = list(result.scalars().all())
            else:
                documents = []

            if not documents:
                raise RuntimeError("No documents available for audit")

            if any(doc.process_status != DocumentStatus.PROCESSED for doc in documents):
                raise RuntimeError("All documents must be processed before audit")

            # Backup existing data before re-run (B6: data loss protection)
            old_finding_ids = list(
                (await db.execute(select(Finding.id).where(Finding.task_id == task.id))).scalars().all()
            )
            old_report_ids = list(
                (await db.execute(select(Report.id).where(Report.task_id == task.id))).scalars().all()
            )

            timeout_seconds = settings.AGENT_TASK_TIMEOUT
            focus = get_execution_meta(task).get("focus", "")
            agent_doc_type = TASK_TYPE_TO_AGENT_TYPE.get(task.task_type, "deviation")

            total_docs = len(documents)
            await self._publish(
                task_id,
                {
                    "type": "event",
                    "data": {
                        "time": datetime.now(UTC).isoformat(),
                        "stage": "parsing",
                        "level": "info",
                        "message": f"Starting audit of {total_docs} document(s)",
                    },
                },
            )

            # Process documents in parallel (or sequentially if only 1)
            if total_docs == 1:
                doc_results = [
                    await self._process_single_document(
                        task_id,
                        documents[0],
                        agent_doc_type,
                        focus,
                        timeout_seconds,
                        1,
                        1,
                    )
                ]
            else:
                # Parallel processing with concurrency limiter
                async def _limited_process(doc, idx):
                    async with self._llm_semaphore:
                        return await self._process_single_document(
                            task_id,
                            doc,
                            agent_doc_type,
                            focus,
                            timeout_seconds,
                            idx,
                            total_docs,
                        )

                doc_results = await asyncio.gather(
                    *[_limited_process(doc, i) for i, doc in enumerate(documents, start=1)],
                    return_exceptions=False,  # exceptions already caught in _process_single_document
                )

            # Aggregate results from all documents
            findings_to_save: list[tuple[dict[str, Any], int]] = []
            document_results: list[dict[str, Any]] = []
            agent_reports: list[str] = []
            agent_report_sources: list[str] = []
            all_traces: list[dict[str, Any]] = []
            all_thinking_events: list[dict[str, Any]] = []
            errors: list[str] = []

            for doc_result in doc_results:
                if doc_result.get("error"):
                    errors.append(doc_result["error"])
                for finding in doc_result["findings"]:
                    findings_to_save.append((finding, finding["document_id"]))
                document_results.append(doc_result["document_result"])
                agent_reports.append(doc_result["report"])
                agent_report_sources.append(doc_result["report_source"])
                if doc_result.get("trace"):
                    all_traces.append(doc_result["trace"])
                all_thinking_events.extend(doc_result.get("thinking_events", []))

            # Check if ALL documents failed
            all_failed = all(r.get("error") for r in doc_results)
            if all_failed:
                raise RuntimeError(f"All {total_docs} documents failed: {'; '.join(errors)}")

            # Log partial failures
            if errors:
                append_event(task, f"{len(errors)}/{total_docs} document(s) had errors", stage="risk", level="warning")
                await self._publish(
                    task_id,
                    {
                        "type": "event",
                        "data": {
                            "time": datetime.now(UTC).isoformat(),
                            "stage": "risk",
                            "level": "warning",
                            "message": f"{len(errors)}/{total_docs} document(s) had errors",
                        },
                    },
                )

            # Store trace metadata and thinking events on task
            task_config = dict(task.config or {})
            if all_traces:
                task_config["_trace"] = all_traces if len(all_traces) > 1 else all_traces[0]
            if all_thinking_events:
                task_config.setdefault("execution", {})["thinking_events"] = all_thinking_events
            task.config = task_config
            _safe_flag_modified(task, "config")

            # Update task with document results
            meta = get_execution_meta(task)
            meta["documents"] = document_results
            set_execution_meta(task, meta)
            _safe_flag_modified(task, "config")
            task.progress = 80
            await db.commit()
            await self._publish_progress(task_id, 80, "report")

            # Validate findings before persisting
            all_finding_dicts = [f for f, _ in findings_to_save]
            valid_finding_dicts = validate_findings(all_finding_dicts)
            valid_set = {id(f) for f in valid_finding_dicts}
            dropped_count = len(findings_to_save) - len(valid_finding_dicts)
            if dropped_count > 0:
                append_event(
                    task,
                    f"Filtered {dropped_count} invalid findings (missing title/description)",
                    stage="risk",
                    level="warning",
                )
                await self._publish(
                    task_id,
                    {
                        "type": "event",
                        "data": {
                            "time": datetime.now(UTC).isoformat(),
                            "stage": "risk",
                            "level": "warning",
                            "message": f"Filtered {dropped_count} invalid findings",
                        },
                    },
                )

            # Add new findings to session first (before deleting old data)
            persisted_findings: list[dict[str, Any]] = []
            for finding_data, document_id in findings_to_save:
                if id(finding_data) in valid_set:
                    persisted_findings.append(finding_data)
                    db.add(normalize_finding(finding_data, task.id, document_id))

            report_markdown, report_metadata = choose_report_content(
                task.task_name,
                document_results,
                persisted_findings,
                agent_reports,
                agent_report_sources=agent_report_sources,
            )
            append_event(task, "Generating audit report", stage="report")
            await self._publish(
                task_id,
                {
                    "type": "event",
                    "data": {
                        "time": datetime.now(UTC).isoformat(),
                        "stage": "report",
                        "level": "info",
                        "message": "Generating audit report",
                    },
                },
            )
            await self._publish_progress(task_id, 90, "report")
            report = Report(
                task_id=task.id,
                report_type=ReportType.FULL_REPORT,
                title=f"Audit Report - {task.task_name}",
                content=report_markdown,
                report_metadata=report_metadata,
            )
            db.add(report)

            # Delete old data after new data is staged (atomic: both in one commit)
            if old_finding_ids:
                await db.execute(delete(RiskAlert).where(RiskAlert.finding_id.in_(old_finding_ids)))
                await db.execute(delete(Finding).where(Finding.id.in_(old_finding_ids)))
            if old_report_ids:
                await db.execute(delete(Report).where(Report.id.in_(old_report_ids)))
            await db.commit()

            # Create RiskAlerts immediately after findings are committed (same as AWAITING_REVIEW path)
            result = await db.execute(select(Finding).where(Finding.task_id == task.id))
            saved_findings = result.scalars().all()
            for finding in saved_findings:
                if finding.severity == SeverityLevel.HIGH:
                    db.add(RiskAlert(finding_id=finding.id, alert_level=AlertLevel.CRITICAL))
                elif finding.severity == SeverityLevel.MEDIUM:
                    db.add(RiskAlert(finding_id=finding.id, alert_level=AlertLevel.WARNING))
            await db.commit()

            # Persist findings to audit memory (JSONL)
            from app.services.memory import append_findings

            await append_findings(task.id, task.task_name, persisted_findings, document_results)

            # Pre-compute finding statistics for notification
            high_risk_count = sum(
                1 for item in persisted_findings if item.get("severity", "").lower() in {"high", "critical"}
            )
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
                append_event(
                    task,
                    f"Task awaiting review: {high_risk_count} high-risk findings detected",
                    stage="awaiting_review",
                )
                await db.commit()
                await self._publish(
                    task_id,
                    {
                        "type": "event",
                        "data": {
                            "time": datetime.now(UTC).isoformat(),
                            "stage": "awaiting_review",
                            "level": "warning",
                            "message": f"Task awaiting review: {high_risk_count} high-risk findings detected",
                        },
                    },
                )
                await self._publish_done(task_id, "awaiting_review")
                await db.refresh(report)

                if is_feishu_configured():
                    try:
                        await notify_audit_complete(
                            task.task_name,
                            len(persisted_findings),
                            high_risk_count,
                            medium_count,
                            top_findings,
                            task_id=task.id,
                        )
                    except Exception:
                        logger.exception("Failed to send audit complete notification for task %s", task.id)
                return

            task.status = TaskStatus.COMPLETED
            task.progress = 100
            task.completed_at = datetime.now(UTC)
            set_stage(task, "completed")
            append_event(task, "Task completed successfully", stage="completed")
            await db.commit()
            await self._publish(
                task_id,
                {
                    "type": "event",
                    "data": {
                        "time": datetime.now(UTC).isoformat(),
                        "stage": "completed",
                        "level": "info",
                        "message": "Task completed successfully",
                    },
                },
            )
            await self._publish_progress(task_id, 100, "completed")
            await self._publish_done(task_id, "completed")
            await db.refresh(report)

            if is_feishu_configured():
                try:
                    await notify_audit_complete(
                        task.task_name,
                        len(persisted_findings),
                        high_risk_count,
                        medium_count,
                        top_findings,
                        task_id=task.id,
                    )
                except Exception:
                    logger.exception("Failed to send audit complete notification for task %s", task.id)
                for item in persisted_findings:
                    if item.get("severity", "").lower() in {"high", "critical"}:
                        try:
                            await notify_high_risk_finding(
                                task.task_name,
                                item.get("title", ""),
                                item.get("severity", ""),
                                item.get("description", ""),
                            )
                        except Exception:
                            logger.exception("Failed to send high-risk finding notification for task %s", task.id)

    async def _mark_failed(self, db: AsyncSession, task: AuditTask, error: str) -> None:
        task.status = TaskStatus.FAILED
        task.error_message = error
        task.completed_at = datetime.now(UTC)
        set_stage(task, "failed", error=error)
        append_event(task, error, stage="failed", level="error")
        await db.commit()
        await self._publish(
            task.id,
            {
                "type": "event",
                "data": {"time": datetime.now(UTC).isoformat(), "stage": "failed", "level": "error", "message": error},
            },
        )
        await self._publish_done(task.id, "failed")
        if is_feishu_configured():
            try:
                await notify_task_failed(task.task_name, error)
            except Exception:
                logger.exception("Failed to send task failed notification for task %s", task.id)


def get_task_runner_factory(
    session_factory: async_sessionmaker[AsyncSession],
    max_concurrency: int,
    llm_concurrency: int = 3,
    event_bus: "EventBus | None" = None,
) -> Callable[[], TaskRunner]:
    runner: TaskRunner | None = None

    def factory() -> TaskRunner:
        nonlocal runner
        if runner is None:
            runner = TaskRunner(
                session_factory=session_factory,
                max_concurrency=max_concurrency,
                llm_concurrency=llm_concurrency,
                event_bus=event_bus,
            )
        return runner

    return factory


def validate_findings(findings: list[dict]) -> list[dict]:
    validated = []
    for f in findings:
        if not f.get("title") or not f.get("description"):
            logger.debug("Dropped finding: missing title or description")
            continue
        if f.get("title") == "Untitled finding":
            logger.debug("Dropped finding:Untitled finding")
            continue
        if len(f.get("description", "").strip()) < 2:
            logger.debug("Dropped finding: description too short: %s", f.get("title"))
            continue
        validated.append(f)
    return validated
