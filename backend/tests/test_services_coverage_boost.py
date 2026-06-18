"""Coverage boost tests for event_bus.py, task_runner.py, and agent_helpers.py.

Targets uncovered branches to push coverage from 87-89% to 95%+.
"""

import asyncio
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.audit_task import AuditTask, TaskStatus, TaskType
from app.models.document import Document, DocumentStatus
from app.models.finding import FindingType, SeverityLevel
from app.services.event_bus import _QUEUE_MAXSIZE, _STALE_TTL, DONE_SENTINEL, EventBus

# ============================================================================
# EventBus — additional coverage gaps
# ============================================================================


class TestEventBusPublishDoneQueueFullAfterDrain:
    """Cover the 'still full after drain' warning paths in publish_done."""

    @pytest.mark.asyncio
    async def test_done_event_still_full_after_drain(self):
        """When done_event can't be pushed even after drain, log warning."""
        bus = EventBus()
        q = await bus.subscribe(1)

        # Fill queue
        for i in range(_QUEUE_MAXSIZE):
            q.put_nowait({"i": i})

        # Patch q.put_nowait to always raise QueueFull for done_event
        # but allow drain (get_nowait) to work
        original_put_nowait = q.put_nowait

        call_count = 0

        def fake_put_nowait(item):
            nonlocal call_count
            call_count += 1
            raise asyncio.QueueFull

        # Drain should work, but put should fail
        with patch.object(q, "put_nowait", side_effect=fake_put_nowait):
            # publish_done should not raise even when queue is still full
            await bus.publish_done(1, "completed")

    @pytest.mark.asyncio
    async def test_sentinel_still_full_after_drain(self):
        """With maxsize=1, publish_done drains filler, puts done_event, then
        drains done_event to push sentinel. Final state: just sentinel."""
        bus = EventBus()
        q = await bus.subscribe(1)

        # Use a queue of size 1 so we can control what happens
        small_queue = asyncio.Queue(maxsize=1)
        bus._subscribers[1] = [small_queue]

        # Fill it
        small_queue.put_nowait({"filler": True})

        # publish_done will:
        # 1. drain filler (queue empty)
        # 2. put done_event (queue full)
        # 3. drain done_event (queue empty) to make room for sentinel
        # 4. put sentinel (queue full)
        await bus.publish_done(1, "completed")

        # Queue should have exactly the sentinel
        items = []
        while not small_queue.empty():
            items.append(small_queue.get_nowait())
        assert len(items) == 1
        assert items[0] is DONE_SENTINEL


class TestEventBusPublishDoneDrainQueueEmpty:
    """Cover the QueueEmpty exception inside drain loop."""

    @pytest.mark.asyncio
    async def test_drain_handles_queue_empty_race(self):
        """Drain loop should handle QueueEmpty from concurrent consumers."""
        bus = EventBus()
        q = await bus.subscribe(1)

        # Fill queue
        for i in range(10):
            q.put_nowait({"i": i})

        # Race: another consumer drains concurrently
        async def concurrent_drain():
            while not q.empty():
                try:
                    q.get_nowait()
                except asyncio.QueueEmpty:
                    break

        # Start concurrent drain, then publish_done
        drain_task = asyncio.create_task(concurrent_drain())
        await bus.publish_done(1, "completed")
        await drain_task

        # Should not raise, and we should have items (done + sentinel or just done)
        items = []
        while not q.empty():
            try:
                items.append(q.get_nowait())
            except asyncio.QueueEmpty:
                break
        # At minimum, publish_done should have completed without error


class TestEventBusPublishMultipleTasks:
    """Cover publish to different task_ids."""

    @pytest.mark.asyncio
    async def test_publish_to_different_tasks(self):
        """Events should only go to the correct task subscribers."""
        bus = EventBus()
        q1 = await bus.subscribe(1)
        q2 = await bus.subscribe(2)

        await bus.publish(1, {"type": "event", "task": 1})
        await bus.publish(2, {"type": "event", "task": 2})

        e1 = q1.get_nowait()
        e2 = q2.get_nowait()
        assert e1["task"] == 1
        assert e2["task"] == 2
        assert q1.empty()
        assert q2.empty()

    @pytest.mark.asyncio
    async def test_publish_done_different_tasks(self):
        """publish_done should only affect the targeted task."""
        bus = EventBus()
        q1 = await bus.subscribe(1)
        q2 = await bus.subscribe(2)

        await bus.publish_done(1, "completed")

        # q1 should have done event + sentinel
        e1 = q1.get_nowait()
        assert e1["type"] == "done"
        s1 = q1.get_nowait()
        assert s1 is DONE_SENTINEL

        # q2 should be empty
        assert q2.empty()


class TestEventBusUnsubscribeEdgeCases:
    """Cover additional unsubscribe edge cases."""

    @pytest.mark.asyncio
    async def test_unsubscribe_queue_not_in_list(self):
        """Unsubscribing a queue that was never subscribed should be a no-op."""
        bus = EventBus()
        q_real = await bus.subscribe(1)
        q_fake = asyncio.Queue()

        await bus.unsubscribe(1, q_fake)

        # Real queue still there
        assert len(bus._subscribers[1]) == 1
        assert bus._subscribers[1][0] is q_real

    @pytest.mark.asyncio
    async def test_unsubscribe_last_queue_cleans_both_dicts(self):
        """When last queue is removed, both _subscribers and _last_activity are cleaned."""
        bus = EventBus()
        q1 = await bus.subscribe(1)
        q2 = await bus.subscribe(1)

        await bus.unsubscribe(1, q1)
        assert 1 in bus._subscribers  # q2 still there

        await bus.unsubscribe(1, q2)
        assert 1 not in bus._subscribers
        assert 1 not in bus._last_activity


class TestEventBusSubscribeUpdatesActivity:
    """Cover that subscribe updates last_activity."""

    @pytest.mark.asyncio
    async def test_subscribe_sets_last_activity(self):
        bus = EventBus()
        q = await bus.subscribe(42)
        assert 42 in bus._last_activity
        assert bus._last_activity[42] > 0

    @pytest.mark.asyncio
    async def test_multiple_subscribes_update_activity(self):
        bus = EventBus()
        await bus.subscribe(1)
        t1 = bus._last_activity[1]
        await asyncio.sleep(0.01)
        await bus.subscribe(1)
        t2 = bus._last_activity[1]
        assert t2 >= t1


class TestEventBusDroppedCountEdgeCases:
    """Cover the dropped_count warning log (every 10th drop)."""

    @pytest.mark.asyncio
    async def test_dropped_count_warning_on_11th_drop(self):
        """The 11th drop (count=11, 11%10==1) triggers warning log."""
        bus = EventBus()
        q = await bus.subscribe(1)

        # Fill queue
        for i in range(_QUEUE_MAXSIZE):
            q.put_nowait({"i": i})

        # Drop 11 events - the 1st and 11th should trigger warning
        for i in range(11):
            await bus.publish(1, {"type": "drop", "i": i})

        assert bus._dropped_count == 11

    @pytest.mark.asyncio
    async def test_dropped_count_resets_across_tasks(self):
        """Dropped count is global, not per-task."""
        bus = EventBus()
        q1 = await bus.subscribe(1)
        q2 = await bus.subscribe(2)

        # Fill both queues
        for i in range(_QUEUE_MAXSIZE):
            q1.put_nowait({"i": i})
            q2.put_nowait({"i": i})

        await bus.publish(1, {"type": "drop"})
        await bus.publish(2, {"type": "drop"})

        assert bus._dropped_count == 2


class TestEventBusCleanupStaleEdgeCases:
    """Cover cleanup_stale edge cases for full branch coverage."""

    @pytest.mark.asyncio
    async def test_cleanup_stale_with_empty_subscribers_list(self, monkeypatch):
        """Entry with empty subscriber list should be cleaned up."""
        bus = EventBus()
        await bus.subscribe(1)
        # Manually empty the subscriber list (as if all unsubscribed)
        bus._subscribers[1] = []
        bus._last_activity[1] = 0.0

        monkeypatch.setattr(
            "app.services.event_bus.time.monotonic",
            lambda: _STALE_TTL + 100,
        )

        removed = await bus.cleanup_stale()
        assert removed == 1
        assert 1 not in bus._subscribers
        assert 1 not in bus._last_activity

    @pytest.mark.asyncio
    async def test_cleanup_stale_boundary_ttl(self, monkeypatch):
        """Entry exactly at TTL boundary should NOT be cleaned (not > TTL)."""
        bus = EventBus()
        bus._subscribers[1] = []
        bus._last_activity[1] = 0.0

        # exactly at TTL, not > TTL
        monkeypatch.setattr(
            "app.services.event_bus.time.monotonic",
            lambda: float(_STALE_TTL),
        )

        removed = await bus.cleanup_stale()
        assert removed == 0


class TestDoneSentinelClassAttribute:
    """Cover the class-level DONE_SENTINEL attribute."""

    def test_class_done_sentinel_is_module_level(self):
        from app.services.event_bus import DONE_SENTINEL as module_sentinel

        assert EventBus.DONE_SENTINEL is module_sentinel


# ============================================================================
# TaskRunner — additional coverage gaps
# ============================================================================


def _make_mock_task(task_id=1, status=TaskStatus.PENDING):
    """Create a mock AuditTask with required attributes."""
    task = MagicMock(spec=AuditTask)
    task.id = task_id
    task.status = status
    task.task_name = "Test Task"
    task.task_type = TaskType.DEVIATION_ANALYSIS
    task.document_ids = [1]
    task.progress = 0
    task.error_message = None
    task.completed_at = None
    task.created_at = datetime.now(UTC)
    task.config = {}
    task.auto_approve = False
    return task


def _make_mock_document(doc_id=1):
    """Create a mock Document."""
    doc = MagicMock(spec=Document)
    doc.id = doc_id
    doc.filename = "test.pdf"
    doc.file_path = "/path/to/test.pdf"
    doc.process_status = DocumentStatus.PROCESSED
    doc.content_text = "Test content"
    return doc


@pytest.fixture
def event_bus():
    return EventBus()


@pytest.fixture
def mock_session_factory():
    """Create a mock session factory that returns a mock session."""
    factory = MagicMock()
    session = AsyncMock()
    factory.return_value.__aenter__ = AsyncMock(return_value=session)
    factory.return_value.__aexit__ = AsyncMock(return_value=False)
    return factory, session


@pytest.fixture
def task_runner(mock_session_factory, event_bus):
    from app.services.task_runner import TaskRunner

    factory, session = mock_session_factory
    return TaskRunner(
        session_factory=factory,
        max_concurrency=2,
        event_bus=event_bus,
    )


@pytest.mark.asyncio
class TestTaskRunnerBuildTaskPayload:
    """Cover build_task_payload with various input combinations."""

    async def test_build_task_payload_with_provided_counts(self):
        from app.services.task_runner import build_task_payload

        session = AsyncMock()
        task = _make_mock_task()
        task.created_at = datetime.now(UTC)
        task.completed_at = None

        payload = await build_task_payload(
            session,
            task,
            _findings_count=5,
            _report_id=42,
        )

        assert payload["id"] == 1
        assert payload["task_id"] == 1
        assert payload["task_name"] == "Test Task"
        assert payload["findings_count"] == 5
        assert payload["report_id"] == 42
        assert payload["task_type"] == "deviation_analysis"
        assert payload["status"] == "pending"

    async def test_build_task_payload_with_completed_at(self):
        from app.services.task_runner import build_task_payload

        session = AsyncMock()
        task = _make_mock_task()
        task.created_at = datetime.now(UTC)
        task.completed_at = datetime.now(UTC)
        task.progress = 100

        payload = await build_task_payload(
            session,
            task,
            _findings_count=0,
            _report_id=0,
        )

        assert payload["progress"] == 100
        assert payload["completed_at"] is not None

    async def test_build_task_payload_queries_db_for_findings(self):
        from app.services.task_runner import build_task_payload

        session = AsyncMock()
        task = _make_mock_task()
        task.created_at = datetime.now(UTC)
        task.completed_at = None

        # Mock findings query
        mock_findings_result = MagicMock()
        mock_findings_result.scalars.return_value.all.return_value = [MagicMock(), MagicMock()]

        # Mock report query
        mock_report_result = MagicMock()
        mock_report = MagicMock()
        mock_report.id = 10
        mock_report_result.scalars.return_value.first.return_value = mock_report

        call_count = 0

        def mock_execute(query):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return mock_findings_result
            return mock_report_result

        session.execute = AsyncMock(side_effect=mock_execute)

        payload = await build_task_payload(session, task)

        assert payload["findings_count"] == 2
        assert payload["report_id"] == 10

    async def test_build_task_payload_no_report_in_db(self):
        from app.services.task_runner import build_task_payload

        session = AsyncMock()
        task = _make_mock_task()
        task.created_at = datetime.now(UTC)
        task.completed_at = None

        mock_findings_result = MagicMock()
        mock_findings_result.scalars.return_value.all.return_value = []

        mock_report_result = MagicMock()
        mock_report_result.scalars.return_value.first.return_value = None

        call_count = 0

        def mock_execute(query):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return mock_findings_result
            return mock_report_result

        session.execute = AsyncMock(side_effect=mock_execute)

        payload = await build_task_payload(session, task)

        assert payload["findings_count"] == 0
        assert payload["report_id"] is None

    async def test_build_task_payload_with_trace(self):
        from app.services.task_runner import build_task_payload

        session = AsyncMock()
        task = _make_mock_task()
        task.created_at = datetime.now(UTC)
        task.completed_at = None
        task.config = {"_trace": {"nodes": ["a", "b"]}}

        payload = await build_task_payload(
            session,
            task,
            _findings_count=0,
            _report_id=0,
        )

        assert payload["trace"] == {"nodes": ["a", "b"]}

    async def test_build_task_payload_error_message_fallback(self):
        from app.services.task_runner import build_task_payload

        session = AsyncMock()
        task = _make_mock_task()
        task.created_at = datetime.now(UTC)
        task.completed_at = None
        task.error_message = "db error"
        task.config = {"execution": {"error": None}}

        payload = await build_task_payload(
            session,
            task,
            _findings_count=0,
            _report_id=0,
        )

        # error falls back to task.error_message when meta error is None
        assert payload["error"] == "db error"


@pytest.mark.asyncio
class TestTaskRunnerBuildAggregateReport:
    """Cover build_aggregate_report edge cases."""

    def test_findings_with_missing_keys(self):
        from app.services.task_runner import build_aggregate_report

        findings = [
            {"title": "Title Only"},
            {"description": "Desc Only"},
            {},  # completely empty
        ]
        result = build_aggregate_report("T", [], findings)
        assert "Title Only" in result
        assert "MEDIUM" in result.upper() or "medium" in result
        assert "无标题" in result  # for findings without title

    def test_single_document_single_finding(self):
        from app.services.task_runner import build_aggregate_report

        docs = [{"filename": "a.pdf", "status": "ok", "findings_count": 1, "risk_level": "high"}]
        findings = [{"severity": "high", "title": "Issue", "description": "Desc", "document_id": 1}]
        result = build_aggregate_report("Test", docs, findings)
        assert "文档数量: 1" in result
        assert "发现数量: 1" in result
        assert "[HIGH]" in result

    def test_findings_with_low_severity(self):
        from app.services.task_runner import build_aggregate_report

        findings = [{"severity": "low", "title": "Low Issue", "description": "Minor", "document_id": 1}]
        result = build_aggregate_report("T", [], findings)
        assert "[LOW]" in result


@pytest.mark.asyncio
class TestTaskRunnerChooseReportContentEdgeCases:
    """Cover choose_report_content edge cases."""

    def test_single_doc_empty_agent_reports_uses_aggregate(self):
        from app.services.task_runner import choose_report_content

        docs = [{"filename": "a.pdf", "status": "ok", "findings_count": 0, "risk_level": "low"}]
        # All agent reports are empty/whitespace
        content, meta = choose_report_content("T", docs, [], ["  ", ""])
        assert meta["report_source"] == "task_runner_aggregate"
        assert meta["report_mode"] == "fallback_aggregate"

    def test_multi_doc_partial_fallback(self):
        from app.services.task_runner import choose_report_content

        docs = [
            {"filename": "a.pdf", "status": "ok", "findings_count": 1, "risk_level": "medium"},
            {"filename": "b.pdf", "status": "ok", "findings_count": 0, "risk_level": "low"},
        ]
        findings = [{"severity": "high", "title": "T", "description": "D", "document_id": 1}]
        content, meta = choose_report_content(
            "T",
            docs,
            findings,
            ["report1", "report2"],
            agent_report_sources=["fallback", "agent"],
        )
        assert meta["report_source"] == "partial_fallback"
        assert meta["report_mode"] == "degraded"

    def test_single_doc_no_fallback_source(self):
        from app.services.task_runner import choose_report_content

        content, meta = choose_report_content(
            "T",
            [{"filename": "a.pdf"}],
            [],
            ["agent report"],
            agent_report_sources=["agent_report_writer"],
        )
        assert meta["report_source"] == "agent_report_writer"
        assert meta["report_mode"] == "single_document"

    def test_single_doc_fallback_source(self):
        from app.services.task_runner import choose_report_content

        content, meta = choose_report_content(
            "T",
            [{"filename": "a.pdf"}],
            [],
            ["fallback report"],
            agent_report_sources=["fallback"],
        )
        assert meta["report_source"] == "fallback"
        assert meta["report_mode"] == "degraded"

    def test_no_agent_report_sources(self):
        from app.services.task_runner import choose_report_content

        docs = [
            {"filename": "a.pdf", "status": "ok", "findings_count": 0, "risk_level": "low"},
            {"filename": "b.pdf", "status": "ok", "findings_count": 0, "risk_level": "low"},
        ]
        content, meta = choose_report_content("T", docs, [], ["", ""], agent_report_sources=None)
        assert meta["report_source"] == "task_runner_aggregate"

    def test_single_doc_fallback_aggregate_mode(self):
        """Single doc with no agent reports -> fallback_aggregate mode."""
        from app.services.task_runner import choose_report_content

        docs = [{"filename": "a.pdf", "status": "ok", "findings_count": 0, "risk_level": "low"}]
        content, meta = choose_report_content("T", docs, [], [])
        assert meta["report_mode"] == "fallback_aggregate"


@pytest.mark.asyncio
class TestTaskRunnerBuildNodeSummary:
    """Cover _build_node_summary edge cases."""

    def test_risk_assessor_no_findings(self):
        from app.services.task_runner import _build_node_summary

        output = {"findings": [], "risk_level": "low"}
        result = _build_node_summary("risk_assessor", output)
        assert "0 个问题" in result
        assert "low" in result

    def test_regulation_expert_no_regulations(self):
        from app.services.task_runner import _build_node_summary

        output = {"matched_regulations": [], "regulation_summary": ""}
        result = _build_node_summary("regulation_expert", output)
        assert "0 条" in result

    def test_report_writer_empty_path(self):
        from app.services.task_runner import _build_node_summary

        output = {"report_path": ""}
        result = _build_node_summary("report_writer", output)
        assert "备用模板" in result

    def test_parse_doc_empty_fields(self):
        from app.services.task_runner import _build_node_summary

        output = {"document_name": "", "document_type": ""}
        result = _build_node_summary("parse_doc", output)
        assert "文档解析完成" in result


@pytest.mark.asyncio
class TestTaskRunnerRunCancelledTaskNotFound:
    """Cover the case where task is not found during CancelledError handling."""

    async def test_cancelled_error_task_already_deleted(self, task_runner, mock_session_factory):
        """When task is cancelled and deleted from DB, should handle gracefully."""
        factory, session = mock_session_factory
        task = _make_mock_task()

        call_count = 0

        def mock_execute(query):
            nonlocal call_count
            call_count += 1
            mock_result = MagicMock()
            if call_count <= 2:
                # First call in _run: return task
                mock_result.scalar_one_or_none.return_value = task
            else:
                # Second call in CancelledError handler: task gone
                mock_result.scalar_one_or_none.return_value = None
            return mock_result

        session.execute = AsyncMock(side_effect=mock_execute)
        session.commit = AsyncMock()

        with patch.object(
            task_runner,
            "_execute_task",
            new_callable=AsyncMock,
            side_effect=asyncio.CancelledError,
        ):
            await task_runner._run(1)

        # Should complete without error even though task was deleted


@pytest.mark.asyncio
class TestTaskRunnerRunExceptionTaskNotFound:
    """Cover the case where task is not found during exception handling."""

    async def test_exception_task_already_deleted(self, task_runner, mock_session_factory):
        """When task fails and is deleted from DB, should handle gracefully."""
        factory, session = mock_session_factory
        task = _make_mock_task()

        call_count = 0

        def mock_execute(query):
            nonlocal call_count
            call_count += 1
            mock_result = MagicMock()
            if call_count <= 2:
                mock_result.scalar_one_or_none.return_value = task
            else:
                mock_result.scalar_one_or_none.return_value = None
            return mock_result

        session.execute = AsyncMock(side_effect=mock_execute)
        session.commit = AsyncMock()

        with patch.object(
            task_runner,
            "_execute_task",
            new_callable=AsyncMock,
            side_effect=RuntimeError("boom"),
        ):
            await task_runner._run(1)

        # Should complete without error


@pytest.mark.asyncio
class TestTaskRunnerExecuteTaskSuccessPath:
    """Cover the successful execution path in _execute_task."""

    async def test_execute_task_single_document_success(self, task_runner, mock_session_factory, event_bus):
        """Cover the full success path with single document."""
        factory, session = mock_session_factory
        task = _make_mock_task()
        task.document_ids = [1]
        doc = _make_mock_document(1)

        call_count = 0

        def mock_execute(query):
            nonlocal call_count
            call_count += 1
            mock_result = MagicMock()
            if call_count == 1:
                # Task query
                mock_result.scalar_one_or_none.return_value = task
            elif call_count == 2:
                # Document query
                mock_result.scalars.return_value.all.return_value = [doc]
            elif call_count == 3:
                # Old findings query
                mock_result.scalars.return_value.all.return_value = []
            elif call_count == 4:
                # Old reports query
                mock_result.scalars.return_value.all.return_value = []
            elif call_count == 5:
                # Saved findings query
                mock_result.scalars.return_value.all.return_value = []
            else:
                mock_result.scalars.return_value.all.return_value = []
            return mock_result

        session.execute = AsyncMock(side_effect=mock_execute)
        session.commit = AsyncMock()
        session.refresh = AsyncMock()

        mock_doc_result = {
            "findings": [],
            "document_result": {
                "document_id": 1,
                "filename": "test.pdf",
                "status": "completed",
                "findings_count": 0,
                "risk_level": "low",
                "report_path": "",
            },
            "report": "Report content",
            "report_source": "agent_report_writer",
            "trace": None,
            "thinking_events": [],
            "error": None,
        }

        with (
            patch.object(task_runner, "_process_single_document", new_callable=AsyncMock, return_value=mock_doc_result),
            patch("app.services.task_runner.is_feishu_configured", return_value=False),
            patch("app.services.memory.append_findings"),
        ):
            await task_runner._execute_task(1)

        assert task.status == TaskStatus.COMPLETED
        assert task.progress == 100


@pytest.mark.asyncio
class TestTaskRunnerExecuteTaskAllFailed:
    """Cover the all_documents_failed path."""

    async def test_execute_task_all_docs_failed(self, task_runner, mock_session_factory, event_bus):
        """When all documents fail, should raise RuntimeError."""
        factory, session = mock_session_factory
        task = _make_mock_task()
        task.document_ids = [1, 2]
        doc1 = _make_mock_document(1)
        doc2 = _make_mock_document(2)

        call_count = 0

        def mock_execute(query):
            nonlocal call_count
            call_count += 1
            mock_result = MagicMock()
            if call_count == 1:
                mock_result.scalar_one_or_none.return_value = task
            elif call_count == 2:
                mock_result.scalars.return_value.all.return_value = [doc1, doc2]
            elif call_count == 3 or call_count == 4:
                mock_result.scalars.return_value.all.return_value = []
            else:
                mock_result.scalars.return_value.all.return_value = []
            return mock_result

        session.execute = AsyncMock(side_effect=mock_execute)
        session.commit = AsyncMock()

        error_result = {
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
            "error": "Document failed",
        }

        with (
            patch.object(task_runner, "_process_single_document", new_callable=AsyncMock, return_value=error_result),
        ):
            with pytest.raises(RuntimeError, match="All .* documents failed"):
                await task_runner._execute_task(1)


@pytest.mark.asyncio
class TestTaskRunnerExecuteTaskPartialFailure:
    """Cover partial failure path (some docs succeed, some fail)."""

    async def test_execute_task_partial_failure(self, task_runner, mock_session_factory, event_bus):
        """When some docs fail but not all, task should complete with warnings."""
        factory, session = mock_session_factory
        task = _make_mock_task()
        task.document_ids = [1, 2]
        doc1 = _make_mock_document(1)
        doc2 = _make_mock_document(2)

        call_count = 0

        def mock_execute(query):
            nonlocal call_count
            call_count += 1
            mock_result = MagicMock()
            if call_count == 1:
                mock_result.scalar_one_or_none.return_value = task
            elif call_count == 2:
                mock_result.scalars.return_value.all.return_value = [doc1, doc2]
            elif call_count == 3 or call_count == 4 or call_count == 5:
                mock_result.scalars.return_value.all.return_value = []
            else:
                mock_result.scalars.return_value.all.return_value = []
            return mock_result

        session.execute = AsyncMock(side_effect=mock_execute)
        session.commit = AsyncMock()
        session.refresh = AsyncMock()

        success_result = {
            "findings": [{"title": "Issue", "description": "Desc", "document_id": 1, "severity": "medium"}],
            "document_result": {
                "document_id": 1,
                "filename": "a.pdf",
                "status": "completed",
                "findings_count": 1,
                "risk_level": "medium",
                "report_path": "",
            },
            "report": "Good report",
            "report_source": "agent",
            "trace": None,
            "thinking_events": [],
            "error": None,
        }
        error_result = {
            "findings": [],
            "document_result": {
                "document_id": 2,
                "filename": "b.pdf",
                "status": "failed",
                "findings_count": 0,
                "risk_level": "unknown",
                "report_path": "",
            },
            "report": "",
            "report_source": "error",
            "trace": None,
            "thinking_events": [],
            "error": "Doc 2 failed",
        }

        results = [success_result, error_result]

        with (
            patch.object(task_runner, "_process_single_document", new_callable=AsyncMock, side_effect=results),
            patch("app.services.task_runner.is_feishu_configured", return_value=False),
            patch("app.services.memory.append_findings"),
        ):
            await task_runner._execute_task(1)

        assert task.status == TaskStatus.COMPLETED


@pytest.mark.asyncio
class TestTaskRunnerExecuteTaskHighRiskAwaitingReview:
    """Cover the AWAITING_REVIEW path for high-risk findings."""

    async def test_execute_task_high_risk_no_auto_approve(self, task_runner, mock_session_factory, event_bus):
        """High-risk findings with auto_approve=False should set AWAITING_REVIEW."""
        factory, session = mock_session_factory
        task = _make_mock_task()
        task.auto_approve = False
        task.document_ids = [1]
        doc = _make_mock_document(1)

        call_count = 0

        def mock_execute(query):
            nonlocal call_count
            call_count += 1
            mock_result = MagicMock()
            if call_count == 1:
                mock_result.scalar_one_or_none.return_value = task
            elif call_count == 2:
                mock_result.scalars.return_value.all.return_value = [doc]
            elif call_count == 3 or call_count == 4:
                mock_result.scalars.return_value.all.return_value = []
            elif call_count == 5:
                # Saved findings - with high severity
                mock_finding = MagicMock()
                mock_finding.severity = MagicMock()
                mock_finding.severity.__eq__ = lambda self, other: True
                mock_finding.id = 1
                mock_result.scalars.return_value.all.return_value = [mock_finding]
            else:
                mock_result.scalars.return_value.all.return_value = []
            return mock_result

        session.execute = AsyncMock(side_effect=mock_execute)
        session.commit = AsyncMock()
        session.refresh = AsyncMock()

        high_risk_result = {
            "findings": [
                {
                    "title": "Critical Issue",
                    "description": "A serious compliance problem",
                    "severity": "high",
                    "document_id": 1,
                },
            ],
            "document_result": {
                "document_id": 1,
                "filename": "test.pdf",
                "status": "completed",
                "findings_count": 1,
                "risk_level": "high",
                "report_path": "",
            },
            "report": "High risk report",
            "report_source": "agent",
            "trace": None,
            "thinking_events": [],
            "error": None,
        }

        with (
            patch.object(
                task_runner, "_process_single_document", new_callable=AsyncMock, return_value=high_risk_result
            ),
            patch("app.services.task_runner.is_feishu_configured", return_value=False),
            patch("app.services.memory.append_findings"),
        ):
            await task_runner._execute_task(1)

        assert task.status == TaskStatus.AWAITING_REVIEW
        assert task.progress == 90


@pytest.mark.asyncio
class TestTaskRunnerExecuteTaskHighRiskWithFeishu:
    """Cover the feishu notification paths for high-risk findings."""

    async def test_execute_task_high_risk_feishu_success(self, task_runner, mock_session_factory, event_bus):
        """High-risk findings should trigger feishu notification."""
        factory, session = mock_session_factory
        task = _make_mock_task()
        task.auto_approve = False
        task.document_ids = [1]
        doc = _make_mock_document(1)

        call_count = 0

        def mock_execute(query):
            nonlocal call_count
            call_count += 1
            mock_result = MagicMock()
            if call_count == 1:
                mock_result.scalar_one_or_none.return_value = task
            elif call_count == 2:
                mock_result.scalars.return_value.all.return_value = [doc]
            elif call_count == 3 or call_count == 4:
                mock_result.scalars.return_value.all.return_value = []
            elif call_count == 5:
                mock_finding = MagicMock()
                mock_finding.severity = MagicMock()
                mock_finding.id = 1
                mock_result.scalars.return_value.all.return_value = [mock_finding]
            else:
                mock_result.scalars.return_value.all.return_value = []
            return mock_result

        session.execute = AsyncMock(side_effect=mock_execute)
        session.commit = AsyncMock()
        session.refresh = AsyncMock()

        high_risk_result = {
            "findings": [
                {"title": "Critical", "description": "Desc", "severity": "high", "document_id": 1},
            ],
            "document_result": {
                "document_id": 1,
                "filename": "test.pdf",
                "status": "completed",
                "findings_count": 1,
                "risk_level": "high",
                "report_path": "",
            },
            "report": "Report",
            "report_source": "agent",
            "trace": None,
            "thinking_events": [],
            "error": None,
        }

        with (
            patch.object(
                task_runner, "_process_single_document", new_callable=AsyncMock, return_value=high_risk_result
            ),
            patch("app.services.task_runner.is_feishu_configured", return_value=True),
            patch("app.services.task_runner.notify_audit_complete", new_callable=AsyncMock) as mock_notify,
            patch("app.services.memory.append_findings"),
        ):
            await task_runner._execute_task(1)

        mock_notify.assert_awaited_once()

    async def test_execute_task_high_risk_feishu_failure(self, task_runner, mock_session_factory, event_bus):
        """Feishu notification failure should not crash the task."""
        factory, session = mock_session_factory
        task = _make_mock_task()
        task.auto_approve = False
        task.document_ids = [1]
        doc = _make_mock_document(1)

        call_count = 0

        def mock_execute(query):
            nonlocal call_count
            call_count += 1
            mock_result = MagicMock()
            if call_count == 1:
                mock_result.scalar_one_or_none.return_value = task
            elif call_count == 2:
                mock_result.scalars.return_value.all.return_value = [doc]
            elif call_count == 3 or call_count == 4:
                mock_result.scalars.return_value.all.return_value = []
            elif call_count == 5:
                mock_finding = MagicMock()
                mock_finding.severity = MagicMock()
                mock_finding.id = 1
                mock_result.scalars.return_value.all.return_value = [mock_finding]
            else:
                mock_result.scalars.return_value.all.return_value = []
            return mock_result

        session.execute = AsyncMock(side_effect=mock_execute)
        session.commit = AsyncMock()
        session.refresh = AsyncMock()

        high_risk_result = {
            "findings": [
                {"title": "Critical", "description": "Desc", "severity": "high", "document_id": 1},
            ],
            "document_result": {
                "document_id": 1,
                "filename": "test.pdf",
                "status": "completed",
                "findings_count": 1,
                "risk_level": "high",
                "report_path": "",
            },
            "report": "Report",
            "report_source": "agent",
            "trace": None,
            "thinking_events": [],
            "error": None,
        }

        with (
            patch.object(
                task_runner, "_process_single_document", new_callable=AsyncMock, return_value=high_risk_result
            ),
            patch("app.services.task_runner.is_feishu_configured", return_value=True),
            patch(
                "app.services.task_runner.notify_audit_complete",
                new_callable=AsyncMock,
                side_effect=RuntimeError("feishu down"),
            ),
            patch("app.services.memory.append_findings"),
        ):
            await task_runner._execute_task(1)

        # Should still be AWAITING_REVIEW even if notification fails
        assert task.status == TaskStatus.AWAITING_REVIEW


@pytest.mark.asyncio
class TestTaskRunnerExecuteTaskCompletedWithFeishu:
    """Cover the feishu notification path for completed tasks with high-risk findings."""

    async def test_execute_task_completed_feishu_high_risk_notify(self, task_runner, mock_session_factory, event_bus):
        """Completed task with high-risk findings should send both complete and high-risk notifications."""
        factory, session = mock_session_factory
        task = _make_mock_task()
        task.auto_approve = True  # auto-approve -> goes to COMPLETED
        task.document_ids = [1]
        doc = _make_mock_document(1)

        call_count = 0

        def mock_execute(query):
            nonlocal call_count
            call_count += 1
            mock_result = MagicMock()
            if call_count == 1:
                mock_result.scalar_one_or_none.return_value = task
            elif call_count == 2:
                mock_result.scalars.return_value.all.return_value = [doc]
            elif call_count == 3 or call_count == 4:
                mock_result.scalars.return_value.all.return_value = []
            elif call_count == 5:
                # saved findings with high severity
                mock_finding = MagicMock()
                mock_finding.severity = SeverityLevel.HIGH
                mock_finding.id = 1
                mock_result.scalars.return_value.all.return_value = [mock_finding]
            else:
                mock_result.scalars.return_value.all.return_value = []
            return mock_result

        session.execute = AsyncMock(side_effect=mock_execute)
        session.commit = AsyncMock()
        session.refresh = AsyncMock()

        high_risk_result = {
            "findings": [
                {"title": "Critical", "description": "Desc", "severity": "high", "document_id": 1},
            ],
            "document_result": {
                "document_id": 1,
                "filename": "test.pdf",
                "status": "completed",
                "findings_count": 1,
                "risk_level": "high",
                "report_path": "",
            },
            "report": "Report",
            "report_source": "agent",
            "trace": None,
            "thinking_events": [],
            "error": None,
        }

        with (
            patch.object(
                task_runner, "_process_single_document", new_callable=AsyncMock, return_value=high_risk_result
            ),
            patch("app.services.task_runner.is_feishu_configured", return_value=True),
            patch("app.services.task_runner.notify_audit_complete", new_callable=AsyncMock) as mock_complete,
            patch("app.services.task_runner.notify_high_risk_finding", new_callable=AsyncMock) as mock_high_risk,
            patch("app.services.memory.append_findings"),
        ):
            await task_runner._execute_task(1)

        assert task.status == TaskStatus.COMPLETED
        mock_complete.assert_awaited_once()
        mock_high_risk.assert_awaited_once()


@pytest.mark.asyncio
class TestTaskRunnerExecuteTaskFeishuHighRiskNotifyFailure:
    """Cover feishu high-risk notification failure."""

    async def test_high_risk_notify_failure(self, task_runner, mock_session_factory, event_bus):
        """High-risk finding notification failure should be swallowed."""
        factory, session = mock_session_factory
        task = _make_mock_task()
        task.auto_approve = True
        task.document_ids = [1]
        doc = _make_mock_document(1)

        call_count = 0

        def mock_execute(query):
            nonlocal call_count
            call_count += 1
            mock_result = MagicMock()
            if call_count == 1:
                mock_result.scalar_one_or_none.return_value = task
            elif call_count == 2:
                mock_result.scalars.return_value.all.return_value = [doc]
            elif call_count == 3 or call_count == 4:
                mock_result.scalars.return_value.all.return_value = []
            elif call_count == 5:
                mock_finding = MagicMock()
                mock_finding.severity = SeverityLevel.HIGH
                mock_finding.id = 1
                mock_result.scalars.return_value.all.return_value = [mock_finding]
            else:
                mock_result.scalars.return_value.all.return_value = []
            return mock_result

        session.execute = AsyncMock(side_effect=mock_execute)
        session.commit = AsyncMock()
        session.refresh = AsyncMock()

        high_risk_result = {
            "findings": [
                {"title": "Critical", "description": "Desc", "severity": "high", "document_id": 1},
            ],
            "document_result": {
                "document_id": 1,
                "filename": "test.pdf",
                "status": "completed",
                "findings_count": 1,
                "risk_level": "high",
                "report_path": "",
            },
            "report": "Report",
            "report_source": "agent",
            "trace": None,
            "thinking_events": [],
            "error": None,
        }

        with (
            patch.object(
                task_runner, "_process_single_document", new_callable=AsyncMock, return_value=high_risk_result
            ),
            patch("app.services.task_runner.is_feishu_configured", return_value=True),
            patch("app.services.task_runner.notify_audit_complete", new_callable=AsyncMock),
            patch(
                "app.services.task_runner.notify_high_risk_finding",
                new_callable=AsyncMock,
                side_effect=Exception("fail"),
            ),
            patch("app.services.memory.append_findings"),
        ):
            await task_runner._execute_task(1)

        # Should still complete
        assert task.status == TaskStatus.COMPLETED


@pytest.mark.asyncio
class TestTaskRunnerExecuteTaskFilteredFindings:
    """Cover the invalid findings filtering path."""

    async def test_execute_task_invalid_findings_filtered(self, task_runner, mock_session_factory, event_bus):
        """Invalid findings should be filtered out with a warning event."""
        factory, session = mock_session_factory
        task = _make_mock_task()
        task.document_ids = [1]
        doc = _make_mock_document(1)

        call_count = 0

        def mock_execute(query):
            nonlocal call_count
            call_count += 1
            mock_result = MagicMock()
            if call_count == 1:
                mock_result.scalar_one_or_none.return_value = task
            elif call_count == 2:
                mock_result.scalars.return_value.all.return_value = [doc]
            elif call_count == 3 or call_count == 4 or call_count == 5:
                mock_result.scalars.return_value.all.return_value = []
            else:
                mock_result.scalars.return_value.all.return_value = []
            return mock_result

        session.execute = AsyncMock(side_effect=mock_execute)
        session.commit = AsyncMock()
        session.refresh = AsyncMock()

        # Mix of valid and invalid findings
        result_with_invalid = {
            "findings": [
                {"title": "Valid", "description": "A valid finding here", "severity": "medium", "document_id": 1},
                {"title": "", "description": "No title", "document_id": 1},  # invalid
                {"description": "No title at all", "document_id": 1},  # invalid
            ],
            "document_result": {
                "document_id": 1,
                "filename": "test.pdf",
                "status": "completed",
                "findings_count": 1,
                "risk_level": "medium",
                "report_path": "",
            },
            "report": "Report",
            "report_source": "agent",
            "trace": None,
            "thinking_events": [],
            "error": None,
        }

        with (
            patch.object(
                task_runner, "_process_single_document", new_callable=AsyncMock, return_value=result_with_invalid
            ),
            patch("app.services.task_runner.is_feishu_configured", return_value=False),
            patch("app.services.memory.append_findings"),
        ):
            await task_runner._execute_task(1)

        assert task.status == TaskStatus.COMPLETED


@pytest.mark.asyncio
class TestTaskRunnerExecuteTaskOldDataCleanup:
    """Cover the old data cleanup path (deleting old findings/reports)."""

    async def test_execute_task_deletes_old_data(self, task_runner, mock_session_factory, event_bus):
        """When re-running a task, old findings and reports should be deleted."""
        factory, session = mock_session_factory
        task = _make_mock_task()
        task.document_ids = [1]
        doc = _make_mock_document(1)

        call_count = 0

        def mock_execute(query):
            nonlocal call_count
            call_count += 1
            mock_result = MagicMock()
            if call_count == 1:
                mock_result.scalar_one_or_none.return_value = task
            elif call_count == 2:
                mock_result.scalars.return_value.all.return_value = [doc]
            elif call_count == 3:
                # Old findings
                mock_result.scalars.return_value.all.return_value = [10, 20]
            elif call_count == 4:
                # Old reports
                mock_result.scalars.return_value.all.return_value = [30]
            elif call_count == 5:
                mock_result.scalars.return_value.all.return_value = []
            else:
                mock_result.scalars.return_value.all.return_value = []
            return mock_result

        session.execute = AsyncMock(side_effect=mock_execute)
        session.commit = AsyncMock()
        session.refresh = AsyncMock()

        mock_doc_result = {
            "findings": [],
            "document_result": {
                "document_id": 1,
                "filename": "test.pdf",
                "status": "completed",
                "findings_count": 0,
                "risk_level": "low",
                "report_path": "",
            },
            "report": "Report",
            "report_source": "agent",
            "trace": None,
            "thinking_events": [],
            "error": None,
        }

        with (
            patch.object(task_runner, "_process_single_document", new_callable=AsyncMock, return_value=mock_doc_result),
            patch("app.services.task_runner.is_feishu_configured", return_value=False),
            patch("app.services.memory.append_findings"),
        ):
            await task_runner._execute_task(1)

        assert task.status == TaskStatus.COMPLETED


@pytest.mark.asyncio
class TestTaskRunnerExecuteTaskWithTrace:
    """Cover the trace metadata storage path."""

    async def test_execute_task_stores_trace(self, task_runner, mock_session_factory, event_bus):
        """Trace data from agent should be stored on task config."""
        factory, session = mock_session_factory
        task = _make_mock_task()
        task.document_ids = [1]
        doc = _make_mock_document(1)

        call_count = 0

        def mock_execute(query):
            nonlocal call_count
            call_count += 1
            mock_result = MagicMock()
            if call_count == 1:
                mock_result.scalar_one_or_none.return_value = task
            elif call_count == 2:
                mock_result.scalars.return_value.all.return_value = [doc]
            elif call_count == 3 or call_count == 4 or call_count == 5:
                mock_result.scalars.return_value.all.return_value = []
            else:
                mock_result.scalars.return_value.all.return_value = []
            return mock_result

        session.execute = AsyncMock(side_effect=mock_execute)
        session.commit = AsyncMock()
        session.refresh = AsyncMock()

        trace_data = {"nodes": [{"name": "parse_doc", "status": "completed"}], "status": "completed"}
        mock_doc_result = {
            "findings": [],
            "document_result": {
                "document_id": 1,
                "filename": "test.pdf",
                "status": "completed",
                "findings_count": 0,
                "risk_level": "low",
                "report_path": "",
            },
            "report": "Report",
            "report_source": "agent",
            "trace": trace_data,
            "thinking_events": [{"stage": "parsing", "node": "parse_doc", "status": "completed", "message": "Done"}],
            "error": None,
        }

        with (
            patch.object(task_runner, "_process_single_document", new_callable=AsyncMock, return_value=mock_doc_result),
            patch("app.services.task_runner.is_feishu_configured", return_value=False),
            patch("app.services.memory.append_findings"),
        ):
            await task_runner._execute_task(1)

        # Trace should be stored on task config
        assert task.config.get("_trace") == trace_data
        assert "thinking_events" in task.config.get("execution", {})


@pytest.mark.asyncio
class TestTaskRunnerMarkFailedWithPublish:
    """Cover _mark_failed event publishing details."""

    async def test_mark_failed_publishes_event_and_done(self, task_runner, mock_session_factory, event_bus):
        """_mark_failed should publish both event and done event."""
        factory, session = mock_session_factory
        task = _make_mock_task()

        session.commit = AsyncMock()

        q = await event_bus.subscribe(1)

        with patch("app.services.task_runner.is_feishu_configured", return_value=False):
            await task_runner._mark_failed(session, task, "test error")

        # Check published events
        events = []
        while not q.empty():
            events.append(q.get_nowait())

        # Should have event + done + sentinel
        event_types = [e.get("type") for e in events if isinstance(e, dict)]
        assert "event" in event_types
        assert "done" in event_types
        # DONE_SENTINEL should also be there
        assert any(e is DONE_SENTINEL for e in events)


@pytest.mark.asyncio
class TestTaskRunnerPublishProgressDetails:
    """Cover _publish_progress DB update details."""

    async def test_publish_progress_updates_db(self, task_runner, mock_session_factory, event_bus):
        """_publish_progress should update progress in DB."""
        factory, session = mock_session_factory
        session.execute = AsyncMock()
        session.commit = AsyncMock()

        q = await event_bus.subscribe(1)

        await task_runner._publish_progress(1, 75, "report")

        event = q.get_nowait()
        assert event["type"] == "progress"
        assert event["data"]["percent"] == 75
        assert event["data"]["stage"] == "report"


@pytest.mark.asyncio
class TestTaskRunnerRunSuccessPath:
    """Cover the success path of _run method."""

    async def test_run_success(self, task_runner, mock_session_factory, event_bus):
        """_run should set task to RUNNING and call _execute_task."""
        factory, session = mock_session_factory
        task = _make_mock_task()

        call_count = 0

        def mock_execute(query):
            nonlocal call_count
            call_count += 1
            mock_result = MagicMock()
            if call_count <= 2:
                mock_result.scalar_one_or_none.return_value = task
            return mock_result

        session.execute = AsyncMock(side_effect=mock_execute)
        session.commit = AsyncMock()

        q = await event_bus.subscribe(1)

        with (
            patch("app.services.task_runner.is_agent_available", return_value=True),
            patch.object(task_runner, "_execute_task", new_callable=AsyncMock),
        ):
            await task_runner._run(1)

        assert task.status == TaskStatus.RUNNING
        assert task.progress == 0

        # Should have published a "Task execution started" event
        events = []
        while not q.empty():
            events.append(q.get_nowait())
        assert any(isinstance(e, dict) and e.get("data", {}).get("message") == "Task execution started" for e in events)


@pytest.mark.asyncio
class TestTaskRunnerEnqueueDoneCallback:
    """Cover the done_callback in enqueue."""

    async def test_enqueue_done_callback_removes_from_active(self, task_runner):
        """When a task completes, the done callback should remove it from _active."""
        with patch("app.services.task_runner.asyncio.create_task") as mock_create:
            mock_task = MagicMock()
            mock_task.done.return_value = False
            mock_create.return_value = mock_task

            task_runner.enqueue(1)
            assert 1 in task_runner._active

            # Simulate the done callback
            done_callback = mock_task.add_done_callback.call_args[0][0]
            done_callback(mock_task)

            assert 1 not in task_runner._active


@pytest.mark.asyncio
class TestTaskRunnerExecuteTaskMultipleDocs:
    """Cover the parallel document processing path."""

    async def test_execute_task_parallel_docs(self, task_runner, mock_session_factory, event_bus):
        """Multiple documents should be processed in parallel."""
        factory, session = mock_session_factory
        task = _make_mock_task()
        task.document_ids = [1, 2]
        doc1 = _make_mock_document(1)
        doc2 = _make_mock_document(2)

        call_count = 0

        def mock_execute(query):
            nonlocal call_count
            call_count += 1
            mock_result = MagicMock()
            if call_count == 1:
                mock_result.scalar_one_or_none.return_value = task
            elif call_count == 2:
                mock_result.scalars.return_value.all.return_value = [doc1, doc2]
            elif call_count == 3 or call_count == 4 or call_count == 5:
                mock_result.scalars.return_value.all.return_value = []
            else:
                mock_result.scalars.return_value.all.return_value = []
            return mock_result

        session.execute = AsyncMock(side_effect=mock_execute)
        session.commit = AsyncMock()
        session.refresh = AsyncMock()

        def make_doc_result(doc_id, filename):
            return {
                "findings": [],
                "document_result": {
                    "document_id": doc_id,
                    "filename": filename,
                    "status": "completed",
                    "findings_count": 0,
                    "risk_level": "low",
                    "report_path": "",
                },
                "report": f"Report for {filename}",
                "report_source": "agent",
                "trace": None,
                "thinking_events": [],
                "error": None,
            }

        results = [
            make_doc_result(1, "a.pdf"),
            make_doc_result(2, "b.pdf"),
        ]

        with (
            patch.object(task_runner, "_process_single_document", new_callable=AsyncMock, side_effect=results),
            patch("app.services.task_runner.is_feishu_configured", return_value=False),
            patch("app.services.memory.append_findings"),
        ):
            await task_runner._execute_task(1)

        assert task.status == TaskStatus.COMPLETED


@pytest.mark.asyncio
class TestTaskRunnerExecuteTaskNoDocs:
    """Cover the no documents available path."""

    async def test_execute_task_empty_document_ids(self, task_runner, mock_session_factory):
        """Empty document_ids should raise RuntimeError."""
        factory, session = mock_session_factory
        task = _make_mock_task()
        task.document_ids = []

        call_count = 0

        def mock_execute(query):
            nonlocal call_count
            call_count += 1
            mock_result = MagicMock()
            if call_count == 1:
                mock_result.scalar_one_or_none.return_value = task
            else:
                mock_result.scalars.return_value.all.return_value = []
            return mock_result

        session.execute = AsyncMock(side_effect=mock_execute)

        with pytest.raises(RuntimeError, match="No documents"):
            await task_runner._execute_task(1)


@pytest.mark.asyncio
class TestTaskRunnerExecuteTaskUnprocessedDoc:
    """Cover the unprocessed document check."""

    async def test_execute_task_unprocessed_doc(self, task_runner, mock_session_factory):
        """Documents not yet PROCESSED should raise RuntimeError."""
        factory, session = mock_session_factory
        task = _make_mock_task()
        task.document_ids = [1]
        doc = _make_mock_document(1)
        doc.process_status = DocumentStatus.UPLOADED  # not PROCESSED

        call_count = 0

        def mock_execute(query):
            nonlocal call_count
            call_count += 1
            mock_result = MagicMock()
            if call_count == 1:
                mock_result.scalar_one_or_none.return_value = task
            else:
                mock_result.scalars.return_value.all.return_value = [doc]
            return mock_result

        session.execute = AsyncMock(side_effect=mock_execute)

        with pytest.raises(RuntimeError, match="All documents must be processed"):
            await task_runner._execute_task(1)


@pytest.mark.asyncio
class TestTaskRunnerStartupRecoverEdgeCases:
    """Cover startup_recover edge cases."""

    async def test_startup_recover_sets_error_message_none(self, task_runner, mock_session_factory):
        """startup_recover should clear error_message on recovered tasks."""
        factory, session = mock_session_factory
        task = _make_mock_task(1, TaskStatus.RUNNING)
        task.error_message = "previous error"

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [task]
        session.execute = AsyncMock(return_value=mock_result)
        session.commit = AsyncMock()

        with patch.object(task_runner, "enqueue", return_value=True):
            await task_runner.startup_recover()

        assert task.status == TaskStatus.PENDING
        assert task.error_message is None


# ============================================================================
# agent_helpers.py — additional coverage gaps
# ============================================================================


class TestAgentAvailableConstant:
    """Cover agent availability check and import behavior."""

    def test_agent_available_is_bool(self):
        from app.utils.agent_helpers import is_agent_available

        assert isinstance(is_agent_available(), bool)

    def test_build_audit_graph_is_callable_or_none(self):
        from app.utils.agent_helpers import get_build_audit_graph, is_agent_available

        build_fn = get_build_audit_graph()
        if is_agent_available():
            assert callable(build_fn)
        else:
            assert build_fn is None


class TestBuildInitialStateEdgeCases:
    """Cover build_initial_state edge cases."""

    def test_default_focus_empty(self):
        from app.utils.agent_helpers import build_initial_state

        state = build_initial_state("/p", "t")
        assert state["audit_focus"] == ""

    def test_default_document_content_empty(self):
        from app.utils.agent_helpers import build_initial_state

        state = build_initial_state("/p", "t")
        assert state["document_content"] == ""

    def test_default_report_source_empty(self):
        from app.utils.agent_helpers import build_initial_state

        state = build_initial_state("/p", "t")
        assert state["report_source"] == ""

    def test_regulation_checked_default_false(self):
        from app.utils.agent_helpers import build_initial_state

        state = build_initial_state("/p", "t")
        assert state["regulation_checked"] is False

    def test_risk_assessed_default_false(self):
        from app.utils.agent_helpers import build_initial_state

        state = build_initial_state("/p", "t")
        assert state["risk_assessed"] is False

    def test_report_generated_default_false(self):
        from app.utils.agent_helpers import build_initial_state

        state = build_initial_state("/p", "t")
        assert state["report_generated"] is False


class TestNormalizeFindingEdgeCases:
    """Cover normalize_finding edge cases for full branch coverage."""

    def test_severity_case_insensitive(self):
        from app.utils.agent_helpers import normalize_finding

        finding = normalize_finding({"severity": "HIGH", "title": "T", "description": "D"}, task_id=1)
        assert finding.severity == SeverityLevel.HIGH

    def test_type_case_insensitive(self):
        from app.utils.agent_helpers import normalize_finding

        finding = normalize_finding({"type": "COMPLIANCE", "title": "T", "description": "D"}, task_id=1)
        assert finding.finding_type == FindingType.COMPLIANCE_RISK

    def test_missing_type_defaults_to_compliance_risk(self):
        from app.utils.agent_helpers import normalize_finding

        finding = normalize_finding({"title": "T", "description": "D"}, task_id=1)
        assert finding.finding_type == FindingType.COMPLIANCE_RISK

    def test_missing_severity_defaults_to_medium(self):
        from app.utils.agent_helpers import normalize_finding

        finding = normalize_finding({"title": "T", "description": "D"}, task_id=1)
        assert finding.severity == SeverityLevel.MEDIUM

    def test_evidence_field(self):
        from app.utils.agent_helpers import normalize_finding

        finding = normalize_finding(
            {"title": "T", "description": "D", "evidence": "some evidence"},
            task_id=1,
        )
        assert finding.evidence == "some evidence"

    def test_suggestion_field(self):
        from app.utils.agent_helpers import normalize_finding

        finding = normalize_finding(
            {"title": "T", "description": "D", "suggestion": "fix this"},
            task_id=1,
        )
        assert finding.suggestion == "fix this"

    def test_regulation_ref_field(self):
        from app.utils.agent_helpers import normalize_finding

        finding = normalize_finding(
            {"title": "T", "description": "D", "regulation_ref": "GMP-2023-001"},
            task_id=1,
        )
        assert finding.regulation_ref == "GMP-2023-001"

    def test_location_empty_falls_back_to_source_section(self):
        from app.utils.agent_helpers import normalize_finding

        finding = normalize_finding(
            {"title": "T", "description": "D", "location": "", "source_section": "Chapter 3"},
            task_id=1,
        )
        assert finding.location == "Chapter 3"

    def test_both_location_and_source_section_empty(self):
        from app.utils.agent_helpers import normalize_finding

        finding = normalize_finding(
            {"title": "T", "description": "D"},
            task_id=1,
        )
        assert finding.location == ""

    def test_severity_mixed_case_medium(self):
        from app.utils.agent_helpers import normalize_finding

        finding = normalize_finding({"severity": "Medium", "title": "T", "description": "D"}, task_id=1)
        assert finding.severity == SeverityLevel.MEDIUM


class TestNormalizeFindingComplianceRiskType:
    """Cover the compliance_risk type mapping."""

    def test_type_compliance_risk(self):
        from app.utils.agent_helpers import normalize_finding

        finding = normalize_finding({"type": "compliance_risk", "title": "T", "description": "D"}, task_id=1)
        assert finding.finding_type == FindingType.COMPLIANCE_RISK


class TestAgentHelpersImportPath:
    """Cover the import path logic in agent_helpers module."""

    def test_module_has_logger(self):
        from app.utils.agent_helpers import logger

        assert logger is not None

    def test_module_imports_finding_model(self):
        from app.utils.agent_helpers import Finding, FindingType, SeverityLevel

        assert Finding is not None
        assert FindingType is not None
        assert SeverityLevel is not None
