"""Layer 3: RAG/KG Retrieval Verification.

Tests that the trace system correctly records KG queries and LLM calls.
Uses mocked dependencies for deterministic results.
"""

import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agent.trace import PipelineTrace, set_current_trace, clear_current_trace, KGTraceEvent


@pytest.fixture(autouse=True)
def cleanup_trace():
    yield
    clear_current_trace()


@pytest.mark.asyncio
class TestKGTraceEvents:
    """Verify KG trace events are recorded."""

    async def test_search_records_kg_trace_event(self):
        """_search_regulations records a KGTraceEvent."""
        from agent.agents.regulation_expert import _search_regulations

        trace = PipelineTrace(document_name="test.txt")
        set_current_trace(trace)

        # Make lightrag fail so we go to fallback
        with patch.dict(sys.modules, {"agent.tools.lightrag_tool": None}):
            results, source = await _search_regulations("偏差处理")

        assert source == "fallback_db"
        assert len(trace.kg_events) >= 1, "No KG events recorded"
        assert trace.kg_events[-1].source == "fallback_db"
        assert trace.kg_events[-1].result_count > 0

    async def test_search_prefers_lightrag(self):
        """When LightRAG is available and returns results, source is 'lightrag'."""
        from agent.agents.regulation_expert import _search_regulations

        trace = PipelineTrace(document_name="test.txt")
        set_current_trace(trace)

        mock_regs = [{"regulation": "GMP法规知识库", "title": "test", "content": "test"}]
        mock_module = MagicMock()
        mock_module.lightrag_search = AsyncMock(return_value=mock_regs)

        with patch.dict(sys.modules, {"agent.tools.lightrag_tool": mock_module}):
            results, source = await _search_regulations("偏差处理")

        assert source == "lightrag"
        assert results == mock_regs
        # Should have one KG event for the lightrag query
        lightrag_events = [e for e in trace.kg_events if e.source == "lightrag"]
        assert len(lightrag_events) >= 1

    async def test_search_fallback_on_lightrag_failure(self):
        """When LightRAG raises exception, falls back and records error."""
        from agent.agents.regulation_expert import _search_regulations

        trace = PipelineTrace(document_name="test.txt")
        set_current_trace(trace)

        mock_module = MagicMock()
        mock_module.lightrag_search = AsyncMock(side_effect=RuntimeError("KG unavailable"))

        with patch.dict(sys.modules, {"agent.tools.lightrag_tool": mock_module}):
            results, source = await _search_regulations("偏差处理")

        assert source == "fallback_db"
        assert len(results) > 0
        # Should have both a lightrag_failed event and a fallback_db event
        failed_events = [e for e in trace.kg_events if e.source == "lightrag_failed"]
        fb_events = [e for e in trace.kg_events if e.source == "fallback_db"]
        assert len(failed_events) >= 1, "No lightrag_failed event"
        assert len(fb_events) >= 1, "No fallback_db event"
        assert failed_events[0].error is not None

    async def test_node_records_kg_and_llm_events(self):
        """regulation_expert_node records both KG and LLM trace events."""
        from agent.agents.regulation_expert import regulation_expert_node

        trace = PipelineTrace(document_name="test.txt")
        set_current_trace(trace)

        state = {
            "document_content": "偏差处理程序 DEV-2024-0156",
            "document_type": "deviation",
            "document_name": "test.txt",
        }

        mock_regs = [{"regulation": "GMP", "title": "test", "content": "content"}]
        mock_module = MagicMock()
        mock_module.lightrag_search = AsyncMock(return_value=mock_regs)

        mock_llm = MagicMock()
        mock_llm._provider = "test"
        mock_llm._model = "test-model"
        mock_llm._trace_node = "regulation_expert"
        mock_llm.ainvoke = AsyncMock(return_value=MagicMock(content='[{"title":"test"}]'))

        with patch.dict(sys.modules, {"agent.tools.lightrag_tool": mock_module}), \
             patch("agent.agents.regulation_expert.get_llm_with_fallback", return_value=mock_llm), \
             patch("agent.agents.regulation_expert.load_prompt", return_value="Analyze: {document_content}"):
            result = await regulation_expert_node(state)

        assert result["regulation_checked"] is True
        assert len(trace.kg_events) >= 1, "No KG events"
        assert len(trace.llm_events) >= 1, "No LLM events"
        # Query rewrite (regulation_expert_rewrite) runs before main analysis (regulation_expert)
        llm_nodes = [e.node for e in trace.llm_events]
        assert "regulation_expert_rewrite" in llm_nodes or "regulation_expert" in llm_nodes, \
            f"Expected regulation_expert nodes, got: {llm_nodes}"
