"""Tests for agent/graph.py — traced_node, parse_document_node, build_audit_graph."""

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agent.graph import build_audit_graph, parse_document_node, traced_node


_FIXTURES = Path(__file__).parent / "fixtures"


# ---------------------------------------------------------------------------
# traced_node
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
class TestTracedNode:
    async def test_async_node_wrapped(self):
        """Async node function should be called directly."""
        call_log = []

        async def my_async_node(state):
            call_log.append("called")
            return {"result": "ok"}

        wrapped = traced_node(my_async_node, "test_node")
        result = await wrapped({"test": True})
        assert result == {"result": "ok"}
        assert call_log == ["called"]

    async def test_sync_node_wrapped_via_to_thread(self):
        """Sync node function should be called via asyncio.to_thread."""
        call_log = []

        def my_sync_node(state):
            call_log.append("sync_called")
            return {"result": "sync_ok"}

        wrapped = traced_node(my_sync_node, "sync_test")
        result = await wrapped({"test": True})
        assert result == {"result": "sync_ok"}
        assert call_log == ["sync_called"]

    async def test_node_name_from_function(self):
        """Node name should be derived from __name__ if not provided."""
        async def named_node(state):
            return {}

        wrapped = traced_node(named_node)
        # The wrapper is async, so we can check the name resolution
        # by running it with a trace
        from agent.trace import PipelineTrace, set_current_trace, clear_current_trace

        trace = PipelineTrace(document_name="test")
        set_current_trace(trace)
        try:
            await wrapped({})
            assert len(trace.node_events) == 1
            assert trace.node_events[0].node == "named_node"
        finally:
            clear_current_trace()

    async def test_explicit_node_name(self):
        """Explicit node_name should override function __name__."""
        async def func_name(state):
            return {}

        wrapped = traced_node(func_name, "explicit_name")
        from agent.trace import PipelineTrace, set_current_trace, clear_current_trace

        trace = PipelineTrace(document_name="test")
        set_current_trace(trace)
        try:
            await wrapped({})
            assert trace.node_events[0].node == "explicit_name"
        finally:
            clear_current_trace()

    async def test_error_recorded_in_trace(self):
        """Exceptions should be recorded in trace events."""
        async def failing_node(state):
            raise ValueError("node failed")

        wrapped = traced_node(failing_node, "fail_node")
        from agent.trace import PipelineTrace, set_current_trace, clear_current_trace

        trace = PipelineTrace(document_name="test")
        set_current_trace(trace)
        try:
            with pytest.raises(ValueError, match="node failed"):
                await wrapped({})
            assert len(trace.node_events) == 1
            assert trace.node_events[0].error is not None
            assert "node failed" in trace.node_events[0].error
        finally:
            clear_current_trace()

    async def test_no_trace_context(self):
        """Should work fine even without a trace context."""
        async def simple_node(state):
            return {"ok": True}

        wrapped = traced_node(simple_node, "simple")
        from agent.trace import clear_current_trace
        clear_current_trace()

        result = await wrapped({})
        assert result == {"ok": True}

    async def test_latency_recorded(self):
        """Latency should be recorded in trace events."""
        async def slow_node(state):
            await asyncio.sleep(0.01)
            return {}

        wrapped = traced_node(slow_node, "slow")
        from agent.trace import PipelineTrace, set_current_trace, clear_current_trace

        trace = PipelineTrace(document_name="test")
        set_current_trace(trace)
        try:
            await wrapped({})
            assert trace.node_events[0].latency_ms > 0
            assert trace.node_events[0].started_at > 0
            assert trace.node_events[0].finished_at > 0
        finally:
            clear_current_trace()


# ---------------------------------------------------------------------------
# parse_document_node — additional coverage
# ---------------------------------------------------------------------------
class TestParseDocumentNodeExtended:
    def test_detect_change_control_type(self):
        """Documents mentioning '变更' should be detected as change_control."""
        state = {
            "document_name": str(_FIXTURES / "sample_deviation.txt"),
            "document_type": "unknown",
            "document_content": "变更控制流程管理 变更 control",
        }
        result = parse_document_node(state)
        assert result["document_type"] == "change_control"

    def test_detect_sop_type(self):
        """Documents without deviation/change keywords should default to sop."""
        state = {
            "document_name": str(_FIXTURES / "sample_deviation.txt"),
            "document_type": "unknown",
            "document_content": "Standard operating procedure for equipment cleaning",
        }
        result = parse_document_node(state)
        assert result["document_type"] == "sop"

    def test_existing_content_not_re_parsed(self):
        """If document_content already has content, skip file parsing."""
        state = {
            "document_name": "nonexistent.txt",
            "document_type": "deviation",
            "document_content": "Already loaded content about 偏差",
        }
        result = parse_document_node(state)
        assert result["document_content"] == "Already loaded content about 偏差"
        assert result["status"] == "running"

    def test_value_error_returns_error(self, tmp_path):
        """ValueError from parser should return error state."""
        f = tmp_path / "bad.csv"
        f.write_text("a,b,c", encoding="utf-8")

        state = {
            "document_name": str(f),
            "document_type": "unknown",
            "document_content": "",
        }
        result = parse_document_node(state)
        assert result["status"] == "error"
        assert "Error" in result["messages"][0]

    def test_file_not_found_returns_error(self):
        """FileNotFoundError should return error state."""
        state = {
            "document_name": "/nonexistent/file.txt",
            "document_type": "unknown",
            "document_content": "",
        }
        result = parse_document_node(state)
        assert result["status"] == "error"
        assert "not found" in result["messages"][0].lower()

    def test_document_path_used_over_name(self, tmp_path):
        """document_path should be preferred over document_name."""
        f = tmp_path / "actual.txt"
        f.write_text("Content from path", encoding="utf-8")

        state = {
            "document_name": "ignored_name.txt",
            "document_path": str(f),
            "document_type": "unknown",
            "document_content": "",
        }
        result = parse_document_node(state)
        assert result["document_content"] == "Content from path"

    def test_unexpected_exception_wrapped(self, tmp_path, monkeypatch):
        """Unexpected exceptions should be wrapped in error state."""
        f = tmp_path / "test.txt"
        f.write_text("test", encoding="utf-8")

        def mock_parse(path):
            raise RuntimeError("unexpected failure")

        monkeypatch.setattr("agent.graph.parse_file", mock_parse)
        state = {
            "document_name": str(f),
            "document_type": "unknown",
            "document_content": "",
        }
        result = parse_document_node(state)
        assert result["status"] == "error"
        assert "unexpected failure" in result["messages"][0]


# ---------------------------------------------------------------------------
# build_audit_graph — additional coverage
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
class TestBuildAuditGraphExtended:
    async def test_conditional_edge_stops_on_error(self):
        """Pipeline should stop when parse_doc returns error status."""
        with patch("agent.graph.parse_file", side_effect=FileNotFoundError("not found")):
            graph = build_audit_graph()
            result = await graph.ainvoke({
                "document_name": "missing.txt",
                "document_type": "unknown",
                "document_content": "",
                "audit_focus": "",
                "matched_regulations": [],
                "regulation_summary": "",
                "regulation_checked": False,
                "findings": [],
                "risk_score": 0,
                "risk_level": "",
                "risk_assessed": False,
                "report_markdown": "",
                "report_path": "",
                "report_generated": False,
                "messages": [],
                "status": "",
            })
            assert result["status"] == "error"

    async def test_conditional_edge_continues_on_success(self):
        """Pipeline should continue to regulation_expert on successful parse."""
        mock_reg = AsyncMock(return_value={
            "matched_regulations": [],
            "regulation_summary": "",
            "regulation_checked": True,
            "messages": ["reg done"],
        })
        mock_risk = AsyncMock(return_value={
            "findings": [],
            "risk_score": 0,
            "risk_level": "low",
            "risk_assessed": True,
            "messages": ["risk done"],
        })
        mock_report = AsyncMock(return_value={
            "report_markdown": "# Report",
            "report_path": "/tmp/r.md",
            "report_generated": True,
            "status": "completed",
            "messages": ["report done"],
        })

        with (
            patch("agent.graph.regulation_expert_node", mock_reg),
            patch("agent.graph.risk_assessor_node", mock_risk),
            patch("agent.graph.report_writer_node", mock_report),
            patch("agent.graph.parse_file", return_value="Test content"),
        ):
            graph = build_audit_graph()
            result = await graph.ainvoke({
                "document_name": "test.txt",
                "document_type": "unknown",
                "document_content": "",
                "audit_focus": "",
                "matched_regulations": [],
                "regulation_summary": "",
                "regulation_checked": False,
                "findings": [],
                "risk_score": 0,
                "risk_level": "",
                "risk_assessed": False,
                "report_markdown": "",
                "report_path": "",
                "report_generated": False,
                "messages": [],
                "status": "",
            })

        assert result["status"] == "completed"
        mock_reg.assert_called_once()
        mock_risk.assert_called_once()
        mock_report.assert_called_once()
