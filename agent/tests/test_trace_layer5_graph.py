"""Layer 5: LangGraph Execution Path Verification.

Tests that the graph execution is predictable and all nodes are traced.
"""

import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agent.trace import PipelineTrace, set_current_trace, clear_current_trace


@pytest.fixture(autouse=True)
def cleanup_trace():
    yield
    clear_current_trace()


@pytest.mark.asyncio
class TestGraphTrace:
    """Verify LangGraph execution path is traced."""

    async def test_full_mock_pipeline_traces_all_nodes(self):
        """All 5 nodes appear in the trace when running with mocked LLM."""
        from agent.graph import build_audit_graph

        trace = PipelineTrace(document_name="test.txt")
        set_current_trace(trace)

        initial_state = {
            "document_name": "test.txt",
            "document_path": "test.txt",
            "document_type": "deviation",
            "audit_focus": "",
            "document_content": "偏差处理程序 DEV-2024-0156",
            "matched_regulations": [],
            "regulation_summary": "",
            "findings": [],
            "risk_score": 0,
            "risk_level": "",
            "report_markdown": "",
            "report_path": "",
            "messages": [],
            "status": "running",
            "regulation_checked": False,
            "risk_assessed": False,
            "report_generated": False,
        }

        mock_regs = [{"regulation": "GMP", "title": "test", "content": "content"}]
        mock_findings = [{"title": "test finding", "severity": "medium", "description": "test"}]
        mock_lightrag = MagicMock()
        mock_lightrag.lightrag_search = AsyncMock(return_value=mock_regs)

        mock_llm = MagicMock()
        mock_llm._provider = "test"
        mock_llm._model = "test-model"
        mock_llm._trace_node = "unknown"
        mock_llm.ainvoke = AsyncMock(return_value=MagicMock(content='[{"title":"test"}]'))

        with patch.dict(sys.modules, {"agent.tools.lightrag_tool": mock_lightrag}), \
             patch("agent.agents.regulation_expert.get_llm_with_fallback", return_value=mock_llm), \
             patch("agent.agents.regulation_expert.load_prompt", return_value="Analyze: {document_content}"), \
             patch("agent.agents.risk_assessor.get_llm_with_fallback", return_value=mock_llm), \
             patch("agent.agents.risk_assessor.load_prompt", return_value="Assess: {document_content}"), \
             patch("agent.agents.report_writer.get_llm_with_fallback", return_value=mock_llm), \
             patch("agent.agents.report_writer.load_prompt", return_value="Report: {document_name}"):
            graph = build_audit_graph()
            final_state = await graph.ainvoke(initial_state)

        # Verify all expected nodes were traced
        traced_nodes = [e.node for e in trace.node_events]
        expected_nodes = {"parse_doc", "regulation_expert", "risk_assessor", "report_writer"}
        assert expected_nodes.issubset(set(traced_nodes)), f"Missing nodes: {expected_nodes - set(traced_nodes)}"

        # Verify pipeline completed
        assert final_state.get("report_generated") is True
        assert final_state.get("status") == "completed"

    async def test_error_state_traced(self):
        """Error in parse_doc is recorded in trace with error field."""
        from agent.graph import build_audit_graph

        trace = PipelineTrace(document_name="nonexistent.txt")
        set_current_trace(trace)

        initial_state = {
            "document_name": "nonexistent.txt",
            "document_path": "/nonexistent/file.txt",
            "document_type": "unknown",
            "audit_focus": "",
            "document_content": "",
            "matched_regulations": [],
            "regulation_summary": "",
            "findings": [],
            "risk_score": 0,
            "risk_level": "",
            "report_markdown": "",
            "report_path": "",
            "messages": [],
            "status": "running",
            "regulation_checked": False,
            "risk_assessed": False,
            "report_generated": False,
        }

        graph = build_audit_graph()
        final_state = await graph.ainvoke(initial_state)

        # parse_doc should handle the error gracefully (returns error state, not raises)
        assert final_state.get("status") == "error"
        # Trace should have recorded the parse_doc node
        assert any(e.node == "parse_doc" for e in trace.node_events)

    async def test_trace_events_have_latency(self):
        """All node trace events have non-negative latency."""
        from agent.graph import build_audit_graph

        trace = PipelineTrace(document_name="test.txt")
        set_current_trace(trace)

        initial_state = {
            "document_name": "test.txt",
            "document_path": "test.txt",
            "document_type": "deviation",
            "audit_focus": "",
            "document_content": "偏差处理程序",
            "matched_regulations": [],
            "regulation_summary": "",
            "findings": [],
            "risk_score": 0,
            "risk_level": "",
            "report_markdown": "",
            "report_path": "",
            "messages": [],
            "status": "running",
            "regulation_checked": False,
            "risk_assessed": False,
            "report_generated": False,
        }

        mock_llm = MagicMock()
        mock_llm._provider = "test"
        mock_llm._model = "test-model"
        mock_llm._trace_node = "unknown"
        mock_llm.ainvoke = AsyncMock(return_value=MagicMock(content='[{"title":"test"}]'))

        with patch.dict(sys.modules, {"agent.tools.lightrag_tool": None}), \
             patch("agent.agents.regulation_expert.get_llm_with_fallback", return_value=mock_llm), \
             patch("agent.agents.regulation_expert.load_prompt", return_value="Analyze: {document_content}"), \
             patch("agent.agents.risk_assessor.get_llm_with_fallback", return_value=mock_llm), \
             patch("agent.agents.risk_assessor.load_prompt", return_value="Assess: {document_content}"), \
             patch("agent.agents.report_writer.get_llm_with_fallback", return_value=mock_llm), \
             patch("agent.agents.report_writer.load_prompt", return_value="Report: {document_name}"):
            graph = build_audit_graph()
            await graph.ainvoke(initial_state)

        for event in trace.node_events:
            assert event.latency_ms >= 0, f"Negative latency for {event.node}"
            assert event.finished_at, f"Missing finished_at for {event.node}"
