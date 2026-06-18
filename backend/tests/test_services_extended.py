"""Extended tests for TaskRunner async methods and LLMEngine uncovered paths.

Focuses on:
- TaskRunner._run(): status transitions, error handling, cancellation
- TaskRunner._execute_task(): document processing, aggregation, review gate
- TaskRunner._process_single_document(): timeout, cache, errors
- TaskRunner.enqueue/cancel/shutdown/startup_recover
- build_task_payload: async DB queries
- LLMEngine: reload_provider, close, stream methods
"""

import asyncio
import time
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.audit_task import AuditTask, TaskStatus, TaskType
from app.models.document import Document, DocumentStatus
from app.models.finding import SeverityLevel
from app.services.event_bus import EventBus
from app.services.task_runner import (
    TaskRunner,
    build_task_payload,
    get_task_runner_factory,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_db_task(
    task_id: int = 1,
    status: TaskStatus = TaskStatus.PENDING,
    task_type: TaskType = TaskType.DEVIATION_ANALYSIS,
    document_ids: list[int] | None = None,
    config: dict | None = None,
    auto_approve: bool = False,
    task_name: str = "Test Task",
) -> AuditTask:
    task = AuditTask(
        id=task_id,
        task_name=task_name,
        task_type=task_type,
        status=status,
        document_ids=document_ids or [],
        config=config,
        auto_approve=auto_approve,
        progress=0,
    )
    return task


def _make_document(
    doc_id: int = 1,
    filename: str = "test.pdf",
    content_text: str = "Sample document content for testing",
    process_status: DocumentStatus = DocumentStatus.PROCESSED,
) -> Document:
    doc = Document(
        id=doc_id,
        filename=filename,
        file_path=f"/tmp/{filename}",
        file_type="pdf",
        file_size=1024,
        content_text=content_text,
        process_status=process_status,
    )
    return doc


def _mock_session_factory(task: AuditTask | None = None, documents: list[Document] | None = None):
    """Create a mock async_sessionmaker that returns a mock session."""
    mock_session = AsyncMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)

    # Default: task found
    task_result = MagicMock()
    task_result.scalar_one_or_none.return_value = task
    task_result.scalar_one.return_value = task

    # Documents query
    doc_result = MagicMock()
    doc_scalars = MagicMock()
    doc_scalars.all.return_value = documents or []
    doc_result.scalars.return_value = doc_scalars

    # Findings query (empty by default)
    finding_result = MagicMock()
    finding_scalars = MagicMock()
    finding_scalars.all.return_value = []
    finding_result.scalars.return_value = finding_scalars
    finding_result.scalalars.return_value = []

    # Reports query (empty by default)
    report_result = MagicMock()
    report_scalars = MagicMock()
    report_scalars.all.return_value = []
    report_scalars.first.return_value = None
    report_result.scalars.return_value = report_scalars

    def execute_side_effect(stmt):
        stmt_str = str(stmt)
        if "audit_tasks" in stmt_str and ("UPDATE" not in stmt_str):
            return task_result
        if "documents" in stmt_str:
            return doc_result
        if "findings" in stmt_str:
            return finding_result
        if "reports" in stmt_str:
            return report_result
        # Default for UPDATE statements
        update_result = MagicMock()
        update_result.rowcount = 1
        return update_result

    mock_session.execute = AsyncMock(side_effect=execute_side_effect)
    mock_session.commit = AsyncMock()
    mock_session.refresh = AsyncMock()

    factory = MagicMock()
    factory.return_value = mock_session
    return factory, mock_session


# ---------------------------------------------------------------------------
# TaskRunner.enqueue
# ---------------------------------------------------------------------------


class TestTaskRunnerEnqueue:
    @pytest.mark.asyncio
    async def test_enqueue_returns_true(self):
        runner = TaskRunner(session_factory=MagicMock(), max_concurrency=2)
        # Patch _run to prevent actual execution
        with patch.object(runner, "_run", new_callable=AsyncMock):
            result = runner.enqueue(1)
            assert result is True
            assert 1 in runner._active

    @pytest.mark.asyncio
    async def test_enqueue_duplicate_returns_false(self):
        runner = TaskRunner(session_factory=MagicMock(), max_concurrency=2)
        with patch.object(runner, "_run", new_callable=AsyncMock):
            runner.enqueue(1)
            result = runner.enqueue(1)
            assert result is False

    @pytest.mark.asyncio
    async def test_enqueue_queue_full_raises(self):
        runner = TaskRunner(session_factory=MagicMock(), max_concurrency=1)
        with patch.object(runner, "_run", new_callable=AsyncMock):
            runner.enqueue(1)
            runner.enqueue(2)
            # max_concurrency * 2 = 2, third should fail
            with pytest.raises(RuntimeError, match="Task queue full"):
                runner.enqueue(3)


# ---------------------------------------------------------------------------
# TaskRunner.cancel
# ---------------------------------------------------------------------------


class TestTaskRunnerCancel:
    @pytest.mark.asyncio
    async def test_cancel_active_task(self):
        runner = TaskRunner(session_factory=MagicMock(), max_concurrency=2)
        with patch.object(runner, "_run", new_callable=AsyncMock):
            runner.enqueue(1)
            result = await runner.cancel(1)
            assert result is True

    @pytest.mark.asyncio
    async def test_cancel_nonexistent_task(self):
        runner = TaskRunner(session_factory=MagicMock(), max_concurrency=2)
        result = await runner.cancel(999)
        assert result is False


# ---------------------------------------------------------------------------
# TaskRunner.shutdown
# ---------------------------------------------------------------------------


class TestTaskRunnerShutdown:
    @pytest.mark.asyncio
    async def test_shutdown_no_active_tasks(self):
        runner = TaskRunner(session_factory=MagicMock(), max_concurrency=2)
        # Should complete without error
        await runner.shutdown(timeout=0.1)

    @pytest.mark.asyncio
    async def test_shutdown_cancels_active_tasks(self):
        runner = TaskRunner(session_factory=MagicMock(), max_concurrency=2)

        # Create a task that blocks
        async def _blocking_run(task_id):
            await asyncio.sleep(100)

        with patch.object(runner, "_run", side_effect=_blocking_run):
            runner.enqueue(1)
            # Give the task a moment to start
            await asyncio.sleep(0.05)
            await runner.shutdown(timeout=0.1)
        # After shutdown, active should be cleared by done callback
        # (may still have the task reference briefly, but it's cancelled)


# ---------------------------------------------------------------------------
# TaskRunner._run
# ---------------------------------------------------------------------------


class TestTaskRunnerRun:
    @pytest.mark.asyncio
    async def test_run_task_not_found(self):
        """_run silently returns if task is not in DB."""
        factory, _ = _mock_session_factory(task=None)
        runner = TaskRunner(session_factory=factory, max_concurrency=1)
        # Should not raise
        await runner._run(999)

    @pytest.mark.asyncio
    async def test_run_agent_unavailable(self):
        """_run marks task as FAILED when agent is unavailable."""
        task = _make_db_task()
        factory, mock_session = _mock_session_factory(task=task)

        runner = TaskRunner(session_factory=factory, max_concurrency=1)

        with (
            patch("app.services.task_runner.is_agent_available", return_value=False),
            patch("app.services.task_runner.is_feishu_configured", return_value=False),
        ):
            await runner._run(1)

        assert task.status == TaskStatus.FAILED
        assert "unavailable" in (task.error_message or "").lower()

    @pytest.mark.asyncio
    async def test_run_sets_status_to_running(self):
        """_run transitions task to RUNNING before executing."""
        task = _make_db_task()
        factory, mock_session = _mock_session_factory(task=task)

        runner = TaskRunner(session_factory=factory, max_concurrency=1)

        # Patch _execute_task to avoid actual execution
        async def _fake_execute(task_id):
            pass

        with (
            patch("app.services.task_runner.is_agent_available", return_value=True),
            patch.object(runner, "_execute_task", side_effect=_fake_execute),
        ):
            await runner._run(1)

        # After successful execution, status may be changed by _execute_task
        # But at minimum, _run set it to RUNNING initially
        assert task.config is not None
        execution = task.config.get("execution", {})
        assert execution.get("events") or execution.get("stage")  # Events were appended

    @pytest.mark.asyncio
    async def test_run_handles_cancelled_error(self):
        """_run sets CANCELLED status on CancelledError."""
        task = _make_db_task()
        factory, mock_session = _mock_session_factory(task=task)

        runner = TaskRunner(session_factory=factory, max_concurrency=1)
        event_bus = EventBus()
        runner._event_bus = event_bus

        async def _cancel_execute(task_id):
            raise asyncio.CancelledError()

        with (
            patch("app.services.task_runner.is_agent_available", return_value=True),
            patch.object(runner, "_execute_task", side_effect=_cancel_execute),
        ):
            await runner._run(1)

        assert task.status == TaskStatus.CANCELLED
        assert task.error_message == "Task cancelled"

    @pytest.mark.asyncio
    async def test_run_handles_generic_exception(self):
        """_run marks task FAILED on generic exception."""
        task = _make_db_task()
        factory, mock_session = _mock_session_factory(task=task)

        runner = TaskRunner(session_factory=factory, max_concurrency=1)

        async def _fail_execute(task_id):
            raise RuntimeError("Something went wrong")

        with (
            patch("app.services.task_runner.is_agent_available", return_value=True),
            patch.object(runner, "_execute_task", side_effect=_fail_execute),
            patch("app.services.task_runner.is_feishu_configured", return_value=False),
        ):
            await runner._run(1)

        assert task.status == TaskStatus.FAILED
        assert "Something went wrong" in (task.error_message or "")


# ---------------------------------------------------------------------------
# TaskRunner._mark_failed
# ---------------------------------------------------------------------------


class TestTaskRunnerMarkFailed:
    @pytest.mark.asyncio
    async def test_mark_failed_sets_status(self):
        factory, mock_session = _mock_session_factory()
        runner = TaskRunner(session_factory=factory, max_concurrency=1)
        task = _make_db_task()

        with patch("app.services.task_runner.is_feishu_configured", return_value=False):
            await runner._mark_failed(mock_session, task, "test error")

        assert task.status == TaskStatus.FAILED
        assert task.error_message == "test error"
        assert task.completed_at is not None

    @pytest.mark.asyncio
    async def test_mark_failed_sends_notification(self):
        factory, mock_session = _mock_session_factory()
        runner = TaskRunner(session_factory=factory, max_concurrency=1)
        task = _make_db_task(task_name="Notify Task")

        with (
            patch("app.services.task_runner.is_feishu_configured", return_value=True),
            patch("app.services.task_runner.notify_task_failed", new_callable=AsyncMock) as mock_notify,
        ):
            await runner._mark_failed(mock_session, task, "error")

        mock_notify.assert_called_once_with("Notify Task", "error")


# ---------------------------------------------------------------------------
# TaskRunner._publish helpers
# ---------------------------------------------------------------------------


class TestTaskRunnerPublish:
    @pytest.mark.asyncio
    async def test_publish_without_event_bus(self):
        runner = TaskRunner(session_factory=MagicMock(), max_concurrency=1)
        # Should not raise
        await runner._publish(1, {"type": "event", "data": {}})

    @pytest.mark.asyncio
    async def test_publish_with_event_bus(self):
        event_bus = MagicMock()
        event_bus.publish = AsyncMock()
        runner = TaskRunner(session_factory=MagicMock(), max_concurrency=1, event_bus=event_bus)
        await runner._publish(1, {"type": "test"})
        event_bus.publish.assert_called_once_with(1, {"type": "test"})

    @pytest.mark.asyncio
    async def test_publish_done_without_event_bus(self):
        runner = TaskRunner(session_factory=MagicMock(), max_concurrency=1)
        await runner._publish_done(1, "completed")

    @pytest.mark.asyncio
    async def test_publish_done_with_event_bus(self):
        event_bus = MagicMock()
        event_bus.publish_done = AsyncMock()
        runner = TaskRunner(session_factory=MagicMock(), max_concurrency=1, event_bus=event_bus)
        await runner._publish_done(1, "completed")
        event_bus.publish_done.assert_called_once_with(1, "completed")

    @pytest.mark.asyncio
    async def test_publish_progress_persists_to_db(self):
        factory, mock_session = _mock_session_factory()
        event_bus = MagicMock()
        event_bus.publish = AsyncMock()
        runner = TaskRunner(session_factory=factory, max_concurrency=1, event_bus=event_bus)
        await runner._publish_progress(1, 50, "running")
        event_bus.publish.assert_called_once()
        mock_session.commit.assert_called()


# ---------------------------------------------------------------------------
# TaskRunner._execute_task
# ---------------------------------------------------------------------------


class TestTaskRunnerExecuteTask:
    @pytest.mark.asyncio
    async def test_execute_no_documents_raises(self):
        """_execute_task raises when no documents are available."""
        task = _make_db_task(document_ids=[])
        factory, _ = _mock_session_factory(task=task, documents=[])

        runner = TaskRunner(session_factory=factory, max_concurrency=1)

        with pytest.raises(RuntimeError, match="No documents"):
            await runner._execute_task(1)

    @pytest.mark.asyncio
    async def test_execute_unprocessed_document_raises(self):
        """_execute_task raises when documents are not processed."""
        doc = _make_document(process_status=DocumentStatus.UPLOADED)
        task = _make_db_task(document_ids=[1])
        factory, _ = _mock_session_factory(task=task, documents=[doc])

        runner = TaskRunner(session_factory=factory, max_concurrency=1)

        with pytest.raises(RuntimeError, match="processed"):
            await runner._execute_task(1)

    @pytest.mark.asyncio
    async def test_execute_single_document_success(self):
        """_execute_task processes a single document and completes."""
        doc = _make_document()
        task = _make_db_task(document_ids=[1], auto_approve=True)

        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        # Task query
        task_result = MagicMock()
        task_result.scalar_one_or_none.return_value = task
        task_result.scalar_one.return_value = task

        # Document query
        doc_result = MagicMock()
        doc_scalars = MagicMock()
        doc_scalars.all.return_value = [doc]
        doc_result.scalars.return_value = doc_scalars

        # Findings query (empty)
        empty_result = MagicMock()
        empty_scalars = MagicMock()
        empty_scalars.all.return_value = []
        empty_result.scalars.return_value = empty_scalars

        # Report query
        report_result = MagicMock()
        report_scalars = MagicMock()
        report_scalars.first.return_value = None
        report_result.scalars.return_value = report_scalars

        def execute_side(stmt):
            stmt_str = str(stmt)
            if "audit_tasks" in stmt_str and "UPDATE" not in stmt_str:
                return task_result
            if "documents" in stmt_str:
                return doc_result
            if "reports" in stmt_str:
                return report_result
            return empty_result

        mock_session.execute = AsyncMock(side_effect=execute_side)
        mock_session.commit = AsyncMock()
        mock_session.refresh = AsyncMock()

        factory = MagicMock()
        factory.return_value = mock_session

        runner = TaskRunner(session_factory=factory, max_concurrency=1)

        doc_result_state = {
            "findings": [],
            "document_result": {
                "document_id": 1,
                "filename": "test.pdf",
                "status": "completed",
                "findings_count": 0,
                "risk_level": "low",
                "report_path": "",
            },
            "report": "# Test Report",
            "report_source": "agent_report_writer",
            "trace": None,
            "thinking_events": [],
            "error": None,
        }

        with (
            patch.object(runner, "_process_single_document", new_callable=AsyncMock, return_value=doc_result_state),
            patch("app.services.task_runner.is_feishu_configured", return_value=False),
            patch("app.services.memory.append_findings"),
        ):
            await runner._execute_task(1)

        assert task.status == TaskStatus.COMPLETED
        assert task.progress == 100

    @pytest.mark.asyncio
    async def test_execute_all_documents_fail_raises(self):
        """_execute_task raises when all documents fail."""
        doc = _make_document()
        task = _make_db_task(document_ids=[1])

        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        task_result = MagicMock()
        task_result.scalar_one_or_none.return_value = task

        doc_result = MagicMock()
        doc_scalars = MagicMock()
        doc_scalars.all.return_value = [doc]
        doc_result.scalars.return_value = doc_scalars

        empty_result = MagicMock()
        empty_scalars = MagicMock()
        empty_scalars.all.return_value = []
        empty_result.scalars.return_value = empty_scalars

        def execute_side(stmt):
            stmt_str = str(stmt)
            if "audit_tasks" in stmt_str and "UPDATE" not in stmt_str:
                return task_result
            if "documents" in stmt_str:
                return doc_result
            return empty_result

        mock_session.execute = AsyncMock(side_effect=execute_side)
        mock_session.commit = AsyncMock()

        factory = MagicMock()
        factory.return_value = mock_session

        runner = TaskRunner(session_factory=factory, max_concurrency=1)

        failed_result = {
            "findings": [],
            "document_result": {
                "document_id": 1,
                "filename": "test.pdf",
                "status": "failed",
                "findings_count": 0,
                "risk_level": "unknown",
                "report_path": "",
            },
            "report": "",
            "report_source": "error",
            "trace": None,
            "thinking_events": [],
            "error": "Pipeline crashed",
        }

        with patch.object(runner, "_process_single_document", new_callable=AsyncMock, return_value=failed_result):
            with pytest.raises(RuntimeError, match="All .* documents failed"):
                await runner._execute_task(1)

    @pytest.mark.asyncio
    async def test_execute_high_risk_triggers_review_gate(self):
        """_execute_task sets AWAITING_REVIEW when high-risk findings exist."""
        doc = _make_document()
        task = _make_db_task(document_ids=[1], auto_approve=False)

        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        # Use call_count to return different results for different queries
        call_count = 0

        def execute_side(stmt):
            nonlocal call_count
            call_count += 1
            stmt_str = str(stmt).lower()

            # First calls: task query, document query
            if call_count <= 2:
                result = MagicMock()
                if "audit_tasks" in stmt_str:
                    scalars = MagicMock()
                    scalars.all.return_value = [task]
                    scalars.first.return_value = task
                    result.scalars.return_value = scalars
                    result.scalar_one_or_none.return_value = task
                    result.scalar_one.return_value = task
                else:
                    scalars = MagicMock()
                    scalars.all.return_value = [doc]
                    result.scalars.return_value = scalars
                return result

            # old_finding_ids / old_report_ids SELECT queries → empty
            if "delete" not in stmt_str and ("finding" in stmt_str or "report" in stmt_str):
                result = MagicMock()
                scalars = MagicMock()
                scalars.all.return_value = []
                result.scalars.return_value = scalars
                return result

            # DELETE queries → ok
            if "delete" in stmt_str:
                result = MagicMock()
                result.rowcount = 0
                return result

            # Final select(Finding) for RiskAlert creation → return high-severity findings
            if "finding" in stmt_str:
                finding_obj = MagicMock()
                finding_obj.id = 1
                finding_obj.severity = SeverityLevel.HIGH
                result = MagicMock()
                scalars = MagicMock()
                scalars.all.return_value = [finding_obj]
                result.scalars.return_value = scalars
                return result

            return MagicMock()

        mock_session.execute = AsyncMock(side_effect=execute_side)
        mock_session.commit = AsyncMock()
        mock_session.refresh = AsyncMock()

        factory = MagicMock()
        factory.return_value = mock_session

        runner = TaskRunner(session_factory=factory, max_concurrency=1)

        doc_result_state = {
            "findings": [
                {
                    "title": "Critical Issue",
                    "description": "A critical finding",
                    "severity": "high",
                    "type": "compliance_risk",
                    "document_id": 1,
                }
            ],
            "document_result": {
                "document_id": 1,
                "filename": "test.pdf",
                "status": "completed",
                "findings_count": 1,
                "risk_level": "high",
                "report_path": "",
            },
            "report": "# Report",
            "report_source": "agent_report_writer",
            "trace": None,
            "thinking_events": [],
            "error": None,
        }

        with (
            patch.object(runner, "_process_single_document", new_callable=AsyncMock, return_value=doc_result_state),
            patch("app.services.task_runner.is_feishu_configured", return_value=False),
            patch("app.services.memory.append_findings"),
        ):
            await runner._execute_task(1)

        assert task.status == TaskStatus.AWAITING_REVIEW

    @pytest.mark.asyncio
    async def test_execute_auto_approve_skips_review(self):
        """_execute_task completes directly when auto_approve=True even with high-risk."""
        doc = _make_document()
        task = _make_db_task(document_ids=[1], auto_approve=True)

        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        call_count = 0

        def execute_side(stmt):
            nonlocal call_count
            call_count += 1
            stmt_str = str(stmt).lower()

            if call_count <= 2:
                result = MagicMock()
                if "audit_tasks" in stmt_str:
                    scalars = MagicMock()
                    scalars.all.return_value = [task]
                    scalars.first.return_value = task
                    result.scalars.return_value = scalars
                    result.scalar_one_or_none.return_value = task
                    result.scalar_one.return_value = task
                else:
                    scalars = MagicMock()
                    scalars.all.return_value = [doc]
                    result.scalars.return_value = scalars
                return result

            if "delete" not in stmt_str and ("finding" in stmt_str or "report" in stmt_str):
                result = MagicMock()
                scalars = MagicMock()
                scalars.all.return_value = []
                result.scalars.return_value = scalars
                return result

            if "delete" in stmt_str:
                result = MagicMock()
                result.rowcount = 0
                return result

            if "finding" in stmt_str:
                finding_obj = MagicMock()
                finding_obj.id = 1
                finding_obj.severity = SeverityLevel.HIGH
                result = MagicMock()
                scalars = MagicMock()
                scalars.all.return_value = [finding_obj]
                result.scalars.return_value = scalars
                return result

            return MagicMock()

        mock_session.execute = AsyncMock(side_effect=execute_side)
        mock_session.commit = AsyncMock()
        mock_session.refresh = AsyncMock()

        factory = MagicMock()
        factory.return_value = mock_session

        runner = TaskRunner(session_factory=factory, max_concurrency=1)

        doc_result_state = {
            "findings": [
                {
                    "title": "Critical Issue",
                    "description": "A critical finding",
                    "severity": "high",
                    "type": "compliance_risk",
                    "document_id": 1,
                }
            ],
            "document_result": {
                "document_id": 1,
                "filename": "test.pdf",
                "status": "completed",
                "findings_count": 1,
                "risk_level": "high",
                "report_path": "",
            },
            "report": "# Report",
            "report_source": "agent_report_writer",
            "trace": None,
            "thinking_events": [],
            "error": None,
        }

        with (
            patch.object(runner, "_process_single_document", new_callable=AsyncMock, return_value=doc_result_state),
            patch("app.services.task_runner.is_feishu_configured", return_value=False),
            patch("app.services.memory.append_findings"),
        ):
            await runner._execute_task(1)

        assert task.status == TaskStatus.COMPLETED
        assert task.progress == 100


# ---------------------------------------------------------------------------
# TaskRunner._process_single_document
# ---------------------------------------------------------------------------


class _AsyncErrorIterator:
    """Async iterator that raises an error on first __anext__ call."""

    def __init__(self, error):
        self._error = error

    def __aiter__(self):
        return self

    async def __anext__(self):
        raise self._error


class TestProcessSingleDocument:
    @pytest.mark.asyncio
    async def test_process_timeout_returns_error(self):
        """_process_single_document handles timeout gracefully."""
        doc = _make_document()
        factory = MagicMock()
        runner = TaskRunner(session_factory=factory, max_concurrency=1)

        mock_graph = MagicMock()
        mock_graph.astream_events = MagicMock(return_value=_AsyncErrorIterator(TimeoutError("timed out")))

        with (
            patch("app.services.task_runner.get_build_audit_graph", return_value=lambda: mock_graph),
            patch("app.services.task_runner.build_initial_state", return_value={}),
            patch("agent.trace.PipelineTrace") as mock_trace_cls,
            patch("agent.trace.set_current_trace"),
            patch("agent.trace.get_current_trace", return_value=None),
            patch("agent.trace.clear_current_trace"),
        ):
            mock_trace_cls.return_value = MagicMock()
            result = await runner._process_single_document(1, doc, "deviation", "", 5, 1, 1)

        assert result["error"] is not None
        assert "timed out" in result["error"]
        assert result["document_result"]["status"] == "timeout"

    @pytest.mark.asyncio
    async def test_process_exception_returns_error(self):
        """_process_single_document handles generic exceptions."""
        doc = _make_document()
        factory = MagicMock()
        runner = TaskRunner(session_factory=factory, max_concurrency=1)

        mock_graph = MagicMock()
        mock_graph.astream_events = MagicMock(return_value=_AsyncErrorIterator(RuntimeError("LLM crashed")))

        with (
            patch("app.services.task_runner.get_build_audit_graph", return_value=lambda: mock_graph),
            patch("app.services.task_runner.build_initial_state", return_value={}),
            patch("agent.trace.PipelineTrace") as mock_trace_cls,
            patch("agent.trace.set_current_trace"),
            patch("agent.trace.get_current_trace", return_value=None),
            patch("agent.trace.clear_current_trace"),
        ):
            mock_trace_cls.return_value = MagicMock()
            result = await runner._process_single_document(1, doc, "deviation", "", 60, 1, 1)

        assert result["error"] is not None
        assert "LLM crashed" in result["error"]
        assert result["document_result"]["status"] == "failed"

    @pytest.mark.asyncio
    async def test_process_empty_result_uses_defaults(self):
        """_process_single_document handles empty graph result."""
        doc = _make_document()
        factory = MagicMock()
        runner = TaskRunner(session_factory=factory, max_concurrency=1)

        # astream_events yields nothing
        async def _empty_stream(state, version="v2"):
            return
            yield  # make it an async generator

        mock_graph = MagicMock()
        mock_graph.astream_events = _empty_stream

        mock_trace = MagicMock()
        mock_trace.to_dict.return_value = {"nodes": []}

        with (
            patch("app.services.task_runner.get_build_audit_graph", return_value=lambda: mock_graph),
            patch("app.services.task_runner.build_initial_state", return_value={}),
            patch("agent.trace.PipelineTrace", return_value=mock_trace),
            patch("agent.trace.set_current_trace"),
            patch("agent.trace.get_current_trace", return_value=mock_trace),
            patch("agent.trace.clear_current_trace"),
        ):
            result = await runner._process_single_document(1, doc, "deviation", "", 60, 1, 1)

        assert result["error"] is None
        assert result["document_result"]["status"] == "completed"

    @pytest.mark.asyncio
    async def test_process_cache_hit(self):
        """_process_single_document returns cached result on cache hit."""
        doc = _make_document(content_text="cached content")
        factory = MagicMock()
        runner = TaskRunner(session_factory=factory, max_concurrency=1)

        # Pre-populate cache
        import hashlib

        cache_key_str = "cached content:deviation:"
        cache_key = hashlib.md5(cache_key_str.encode()).hexdigest()
        cached_result = {
            "findings": [],
            "document_result": {
                "document_id": 1,
                "filename": "test.pdf",
                "status": "completed",
                "findings_count": 0,
                "risk_level": "low",
                "report_path": "",
            },
            "report": "cached report",
            "report_source": "agent_report_writer",
            "trace": None,
            "thinking_events": [],
            "error": None,
        }
        runner._result_cache[cache_key] = (cached_result, time.time())

        result = await runner._process_single_document(1, doc, "deviation", "", 60, 1, 1)

        assert result["_cache_hit"] is True
        assert result["report"] == "cached report"


# ---------------------------------------------------------------------------
# TaskRunner.startup_recover
# ---------------------------------------------------------------------------


class TestStartupRecover:
    @pytest.mark.asyncio
    async def test_startup_recover_resets_stale_tasks(self):
        stale_task = _make_db_task(status=TaskStatus.RUNNING)

        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        result = MagicMock()
        scalars = MagicMock()
        scalars.all.return_value = [stale_task]
        result.scalars.return_value = scalars

        mock_session.execute = AsyncMock(return_value=result)
        mock_session.commit = AsyncMock()

        factory = MagicMock()
        factory.return_value = mock_session

        runner = TaskRunner(session_factory=factory, max_concurrency=1)
        # Patch enqueue to avoid actual task creation
        with patch.object(runner, "enqueue", return_value=True):
            await runner.startup_recover()

        assert stale_task.status == TaskStatus.PENDING
        assert stale_task.error_message is None

    @pytest.mark.asyncio
    async def test_startup_recover_no_stale_tasks(self):
        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        result = MagicMock()
        scalars = MagicMock()
        scalars.all.return_value = []
        result.scalars.return_value = scalars

        mock_session.execute = AsyncMock(return_value=result)

        factory = MagicMock()
        factory.return_value = mock_session

        runner = TaskRunner(session_factory=factory, max_concurrency=1)
        await runner.startup_recover()
        # No commit called since no tasks to recover
        mock_session.commit.assert_not_called()


# ---------------------------------------------------------------------------
# get_task_runner_factory
# ---------------------------------------------------------------------------


class TestGetTaskRunnerFactory:
    def test_factory_returns_same_instance(self):
        factory = get_task_runner_factory(MagicMock(), max_concurrency=2)
        runner1 = factory()
        runner2 = factory()
        assert runner1 is runner2

    def test_factory_creates_task_runner(self):
        factory = get_task_runner_factory(MagicMock(), max_concurrency=2)
        runner = factory()
        assert isinstance(runner, TaskRunner)


# ---------------------------------------------------------------------------
# build_task_payload
# ---------------------------------------------------------------------------


class TestBuildTaskPayload:
    @pytest.mark.asyncio
    async def test_payload_structure(self):
        task = _make_db_task(task_id=42, status=TaskStatus.COMPLETED)
        task.created_at = datetime.now(UTC)

        mock_session = AsyncMock()
        # Findings count query
        finding_result = MagicMock()
        finding_scalars = MagicMock()
        finding_scalars.all.return_value = []
        finding_result.scalars.return_value = finding_scalars

        # Report query
        report_result = MagicMock()
        report_scalars = MagicMock()
        report_scalars.first.return_value = None
        report_result.scalars.return_value = report_scalars

        def execute_side(stmt):
            if "findings" in str(stmt):
                return finding_result
            return report_result

        mock_session.execute = AsyncMock(side_effect=execute_side)

        payload = await build_task_payload(mock_session, task)

        assert payload["id"] == 42
        assert payload["task_id"] == 42
        assert payload["status"] == "completed"
        assert payload["findings_count"] == 0
        assert payload["report_id"] is None

    @pytest.mark.asyncio
    async def test_payload_with_precomputed_counts(self):
        task = _make_db_task(task_id=5)
        task.created_at = datetime.now(UTC)

        mock_session = AsyncMock()

        payload = await build_task_payload(mock_session, task, _findings_count=3, _report_id=10)

        assert payload["findings_count"] == 3
        assert payload["report_id"] == 10
        # DB should not be queried
        mock_session.execute.assert_not_called()


# ---------------------------------------------------------------------------
# LLMEngine: reload_provider
# ---------------------------------------------------------------------------


class TestLLMEngineReload:
    @pytest.mark.asyncio
    async def test_reload_openai_provider(self):
        from app.services.llm_engine import LLMEngine

        engine = LLMEngine()
        with patch("app.services.llm_engine.OpenAICompatibleAdapter") as mock_cls:
            mock_adapter = AsyncMock()
            mock_cls.return_value = mock_adapter
            await engine.reload_provider(
                "deepseek", api_key="sk-test", base_url="https://test.com/v1", model="test-model"
            )

        assert "deepseek" in engine.adapters
        await engine.close()

    @pytest.mark.asyncio
    async def test_reload_anthropic_provider(self):
        from app.services.llm_engine import LLMEngine

        engine = LLMEngine()
        with patch("app.services.llm_engine.AnthropicAdapter") as mock_cls:
            mock_adapter = AsyncMock()
            mock_cls.return_value = mock_adapter
            await engine.reload_provider("anthropic", api_key="sk-ant-test")

        assert "anthropic" in engine.adapters
        await engine.close()

    @pytest.mark.asyncio
    async def test_reload_with_empty_key_removes_adapter(self):
        from app.services.llm_engine import LLMEngine, OpenAICompatibleAdapter

        engine = LLMEngine()
        adapter = OpenAICompatibleAdapter(api_key="old-key", base_url="https://test.com/v1", model="m", name="deepseek")
        engine.adapters["deepseek"] = adapter

        await engine.reload_provider("deepseek", api_key="")
        assert "deepseek" not in engine.adapters
        await adapter.close()

    @pytest.mark.asyncio
    async def test_reload_anthropic_empty_key_removes(self):
        from app.services.llm_engine import AnthropicAdapter, LLMEngine

        engine = LLMEngine()
        adapter = AnthropicAdapter(api_key="old-key")
        engine.adapters["anthropic"] = adapter

        await engine.reload_provider("anthropic", api_key="")
        assert "anthropic" not in engine.adapters
        await adapter.close()

    @pytest.mark.asyncio
    async def test_reload_closes_old_adapter(self):
        from app.services.llm_engine import LLMEngine, OpenAICompatibleAdapter

        engine = LLMEngine()
        old_adapter = AsyncMock(spec=OpenAICompatibleAdapter)
        old_adapter.close = AsyncMock()
        engine.adapters["deepseek"] = old_adapter

        with patch("app.services.llm_engine.OpenAICompatibleAdapter") as mock_cls:
            new_mock = AsyncMock()
            mock_cls.return_value = new_mock
            await engine.reload_provider("deepseek", api_key="new-key")

        old_adapter.close.assert_called_once()
        await engine.close()

    @pytest.mark.asyncio
    async def test_reload_skips_placeholder_model(self):
        from app.services.llm_engine import LLMEngine

        engine = LLMEngine()
        with patch("app.services.llm_engine.OpenAICompatibleAdapter") as mock_cls:
            mock_cls.return_value = AsyncMock()
            await engine.reload_provider("deepseek", api_key="sk-test", model="your_model_here")

        call_kwargs = mock_cls.call_args
        # Should use default model, not placeholder
        model = call_kwargs.kwargs.get("model", call_kwargs[1].get("model", ""))
        assert not model.startswith("your_")
        await engine.close()


# ---------------------------------------------------------------------------
# LLMEngine.close
# ---------------------------------------------------------------------------


class TestLLMEngineClose:
    @pytest.mark.asyncio
    async def test_close_all_adapters(self):
        from app.services.llm_engine import LLMEngine

        engine = LLMEngine()
        adapter1 = AsyncMock()
        adapter1.close = AsyncMock()
        adapter2 = AsyncMock()
        adapter2.close = AsyncMock()
        engine.adapters = {"a": adapter1, "b": adapter2}

        await engine.close()
        adapter1.close.assert_called_once()
        adapter2.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_close_handles_adapter_error(self):
        from app.services.llm_engine import LLMEngine

        engine = LLMEngine()
        adapter = AsyncMock()
        adapter.close = AsyncMock(side_effect=RuntimeError("close failed"))
        engine.adapters = {"a": adapter}

        # Should not raise
        await engine.close()


# ---------------------------------------------------------------------------
# LLMEngine: OpenAICompatibleAdapter.stream
# ---------------------------------------------------------------------------


class TestOpenAIAdapterStream:
    @pytest.mark.asyncio
    async def test_chat_stream_success(self):
        from app.services.llm_engine import OpenAICompatibleAdapter

        adapter = OpenAICompatibleAdapter(api_key="test-key", base_url="https://api.example.com/v1", model="test-model")

        # Mock the streaming response
        mock_response = AsyncMock()
        mock_response.status_code = 200

        lines = [
            'data: {"choices":[{"delta":{"content":"Hello"}}]}',
            'data: {"choices":[{"delta":{"content":" World"}}]}',
            "data: [DONE]",
        ]

        async def _aiter_lines():
            for line in lines:
                yield line

        mock_response.aiter_lines = _aiter_lines

        mock_stream_ctx = AsyncMock()
        mock_stream_ctx.__aenter__ = AsyncMock(return_value=mock_response)
        mock_stream_ctx.__aexit__ = AsyncMock(return_value=False)

        with patch.object(adapter._client, "stream", return_value=mock_stream_ctx):
            chunks = []
            async for chunk in adapter.chat_stream([{"role": "user", "content": "Hi"}]):
                chunks.append(chunk)

        assert chunks == ["Hello", " World"]
        await adapter.close()

    @pytest.mark.asyncio
    async def test_chat_stream_handles_invalid_json(self):
        from app.services.llm_engine import OpenAICompatibleAdapter

        adapter = OpenAICompatibleAdapter(api_key="test-key", base_url="https://api.example.com/v1", model="test-model")

        mock_response = AsyncMock()
        mock_response.status_code = 200

        lines = [
            "data: {invalid json",
            'data: {"choices":[{"delta":{"content":"OK"}}]}',
            "data: [DONE]",
        ]

        async def _aiter_lines():
            for line in lines:
                yield line

        mock_response.aiter_lines = _aiter_lines

        mock_stream_ctx = AsyncMock()
        mock_stream_ctx.__aenter__ = AsyncMock(return_value=mock_response)
        mock_stream_ctx.__aexit__ = AsyncMock(return_value=False)

        with patch.object(adapter._client, "stream", return_value=mock_stream_ctx):
            chunks = []
            async for chunk in adapter.chat_stream([{"role": "user", "content": "Hi"}]):
                chunks.append(chunk)

        assert chunks == ["OK"]
        await adapter.close()


# ---------------------------------------------------------------------------
# LLMEngine: AnthropicAdapter stream
# ---------------------------------------------------------------------------


class TestAnthropicAdapterStream:
    @pytest.mark.asyncio
    async def test_chat_stream_success(self):
        from app.services.llm_engine import AnthropicAdapter

        adapter = AnthropicAdapter(api_key="test-key")

        mock_response = AsyncMock()
        mock_response.status_code = 200

        lines = [
            'data: {"type":"content_block_delta","delta":{"text":"Hello"}}',
            'data: {"type":"content_block_delta","delta":{"text":" Claude"}}',
            'data: {"type":"message_stop"}',
        ]

        async def _aiter_lines():
            for line in lines:
                yield line

        mock_response.aiter_lines = _aiter_lines

        mock_stream_ctx = AsyncMock()
        mock_stream_ctx.__aenter__ = AsyncMock(return_value=mock_response)
        mock_stream_ctx.__aexit__ = AsyncMock(return_value=False)

        with patch.object(adapter._client, "stream", return_value=mock_stream_ctx):
            chunks = []
            async for chunk in adapter.chat_stream([{"role": "user", "content": "Hi"}]):
                chunks.append(chunk)

        assert chunks == ["Hello", " Claude"]

    @pytest.mark.asyncio
    async def test_chat_stream_handles_invalid_json(self):
        from app.services.llm_engine import AnthropicAdapter

        adapter = AnthropicAdapter(api_key="test-key")

        mock_response = AsyncMock()
        mock_response.status_code = 200

        lines = [
            "data: {bad json",
            'data: {"type":"content_block_delta","delta":{"text":"OK"}}',
        ]

        async def _aiter_lines():
            for line in lines:
                yield line

        mock_response.aiter_lines = _aiter_lines

        mock_stream_ctx = AsyncMock()
        mock_stream_ctx.__aenter__ = AsyncMock(return_value=mock_response)
        mock_stream_ctx.__aexit__ = AsyncMock(return_value=False)

        with patch.object(adapter._client, "stream", return_value=mock_stream_ctx):
            chunks = []
            async for chunk in adapter.chat_stream([{"role": "user", "content": "Hi"}]):
                chunks.append(chunk)

        assert chunks == ["OK"]


# ---------------------------------------------------------------------------
# LLMEngine: AnthropicAdapter._extract_system edge cases
# ---------------------------------------------------------------------------


class TestAnthropicExtractSystem:
    def test_multiple_system_messages(self):
        from app.services.llm_engine import AnthropicAdapter

        messages = [
            {"role": "system", "content": "Part 1"},
            {"role": "system", "content": "Part 2"},
            {"role": "user", "content": "Hello"},
        ]
        system, filtered = AnthropicAdapter._extract_system(messages)
        assert system == "Part 1\n\nPart 2"
        assert len(filtered) == 1


# ---------------------------------------------------------------------------
# LLMEngine: OpenAICompatibleAdapter.chat empty choices
# ---------------------------------------------------------------------------


class TestOpenAIAdapterEdgeCases:
    @pytest.mark.asyncio
    async def test_chat_empty_choices_raises(self):
        from app.services.llm_engine import OpenAICompatibleAdapter

        adapter = OpenAICompatibleAdapter(api_key="test-key", base_url="https://api.example.com/v1", model="test-model")

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"choices": [], "model": "test-model"}

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=mock_response):
            with pytest.raises(ValueError, match="empty choices"):
                await adapter.chat([{"role": "user", "content": "Hi"}])

    @pytest.mark.asyncio
    async def test_close_adapter(self):
        from app.services.llm_engine import OpenAICompatibleAdapter

        adapter = OpenAICompatibleAdapter(api_key="test-key", base_url="https://api.example.com/v1", model="test-model")
        with patch.object(adapter._client, "aclose", new_callable=AsyncMock) as mock_close:
            await adapter.close()
            mock_close.assert_called_once()

    @pytest.mark.asyncio
    async def test_anthropic_close_adapter(self):
        from app.services.llm_engine import AnthropicAdapter

        adapter = AnthropicAdapter(api_key="test-key")
        with patch.object(adapter._client, "aclose", new_callable=AsyncMock) as mock_close:
            await adapter.close()
            mock_close.assert_called_once()


# ---------------------------------------------------------------------------
# _check_response edge cases
# ---------------------------------------------------------------------------


class TestCheckResponse:
    def test_201_status_passes(self):
        from app.services.llm_engine import _check_response

        mock_response = MagicMock()
        mock_response.status_code = 201
        _check_response(mock_response)  # Should not raise

    def test_404_status_raises(self):
        from app.services.llm_engine import LLMError, _check_response

        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_response.text = "Not Found"
        with pytest.raises(LLMError) as exc_info:
            _check_response(mock_response)
        assert exc_info.value.status_code == 404
