"""Stability Verification: Same input repeated 5 times.

Verifies that the pipeline produces consistent output structure
when run multiple times with the same input (using mocked LLM).
"""

import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agent.trace import PipelineTrace, set_current_trace, clear_current_trace


@pytest.fixture(autouse=True)
def cleanup_trace():
    yield
    clear_current_trace()


def _build_initial_state():
    return {
        "document_name": "sample_deviation.txt",
        "document_path": "sample_deviation.txt",
        "document_type": "deviation",
        "audit_focus": "",
        "document_content": "偏差处理程序 DEV-2024-0156：片剂压片机压力异常偏差调查",
        "next_agent": "",
        "supervisor_reasoning": "",
        "matched_regulations": [],
        "regulation_summary": "",
        "findings": [],
        "risk_score": 0,
        "risk_level": "",
        "report_markdown": "",
        "report_path": "",
        "messages": [],
        "iteration": 0,
        "status": "running",
        "regulation_checked": False,
        "risk_assessed": False,
        "report_generated": False,
    }


def _mock_dependencies():
    """Set up mock dependencies for the pipeline."""
    mock_regs = [{"regulation": "GMP", "title": "test", "content": "content"}]
    mock_findings = [{"title": "finding", "severity": "medium", "description": "desc"}]

    mock_lightrag = MagicMock()
    mock_lightrag.lightrag_search = AsyncMock(return_value=mock_regs)

    mock_llm = MagicMock()
    mock_llm._provider = "test"
    mock_llm._model = "test-model"
    mock_llm._trace_node = "unknown"
    mock_llm.ainvoke = AsyncMock(return_value=MagicMock(content='[{"title":"test"}]'))

    return mock_lightrag, mock_llm


@pytest.mark.asyncio
class TestStability:
    """Verify pipeline output stability across multiple runs."""

    async def test_5_runs_same_output_keys(self):
        """5 runs produce the same output keys."""
        from agent.graph import build_audit_graph

        mock_lightrag, mock_llm = _mock_dependencies()
        all_keys = []

        for i in range(5):
            trace = PipelineTrace(document_name=f"test_{i}.txt")
            set_current_trace(trace)

            with patch.dict(sys.modules, {"agent.tools.lightrag_tool": mock_lightrag}), \
                 patch("agent.agents.regulation_expert.get_llm_with_fallback", return_value=mock_llm), \
                 patch("agent.agents.regulation_expert.load_prompt", return_value="Analyze: {document_content}"), \
                 patch("agent.agents.risk_assessor.get_llm_with_fallback", return_value=mock_llm), \
                 patch("agent.agents.risk_assessor.load_prompt", return_value="Assess: {document_content}"), \
                 patch("agent.agents.report_writer.get_llm_with_fallback", return_value=mock_llm), \
                 patch("agent.agents.report_writer.load_prompt", return_value="Report: {document_name}"):
                graph = build_audit_graph()
                final_state = await graph.ainvoke(_build_initial_state())

            all_keys.append(set(final_state.keys()))
            clear_current_trace()

        # All runs should produce identical key sets
        assert all(keys == all_keys[0] for keys in all_keys), \
            f"Inconsistent output keys across runs: {[sorted(k) for k in all_keys]}"

    async def test_5_runs_all_complete(self):
        """5 runs all reach 'completed' status."""
        from agent.graph import build_audit_graph

        mock_lightrag, mock_llm = _mock_dependencies()
        statuses = []

        for i in range(5):
            trace = PipelineTrace(document_name=f"test_{i}.txt")
            set_current_trace(trace)

            with patch.dict(sys.modules, {"agent.tools.lightrag_tool": mock_lightrag}), \
                 patch("agent.agents.regulation_expert.get_llm_with_fallback", return_value=mock_llm), \
                 patch("agent.agents.regulation_expert.load_prompt", return_value="Analyze: {document_content}"), \
                 patch("agent.agents.risk_assessor.get_llm_with_fallback", return_value=mock_llm), \
                 patch("agent.agents.risk_assessor.load_prompt", return_value="Assess: {document_content}"), \
                 patch("agent.agents.report_writer.get_llm_with_fallback", return_value=mock_llm), \
                 patch("agent.agents.report_writer.load_prompt", return_value="Report: {document_name}"):
                graph = build_audit_graph()
                final_state = await graph.ainvoke(_build_initial_state())

            statuses.append(final_state.get("status"))
            clear_current_trace()

        assert all(s == "completed" for s in statuses), f"Not all runs completed: {statuses}"

    async def test_5_runs_findings_structure(self):
        """5 runs produce findings with consistent structure."""
        from agent.graph import build_audit_graph

        mock_lightrag, mock_llm = _mock_dependencies()
        all_findings_keys = []

        for i in range(5):
            trace = PipelineTrace(document_name=f"test_{i}.txt")
            set_current_trace(trace)

            with patch.dict(sys.modules, {"agent.tools.lightrag_tool": mock_lightrag}), \
                 patch("agent.agents.regulation_expert.get_llm_with_fallback", return_value=mock_llm), \
                 patch("agent.agents.regulation_expert.load_prompt", return_value="Analyze: {document_content}"), \
                 patch("agent.agents.risk_assessor.get_llm_with_fallback", return_value=mock_llm), \
                 patch("agent.agents.risk_assessor.load_prompt", return_value="Assess: {document_content}"), \
                 patch("agent.agents.report_writer.get_llm_with_fallback", return_value=mock_llm), \
                 patch("agent.agents.report_writer.load_prompt", return_value="Report: {document_name}"):
                graph = build_audit_graph()
                final_state = await graph.ainvoke(_build_initial_state())

            findings = final_state.get("findings", [])
            if findings:
                all_findings_keys.append(set(findings[0].keys()))
            clear_current_trace()

        # All findings should have the same structure
        assert len(all_findings_keys) == 5
        assert all(keys == all_findings_keys[0] for keys in all_findings_keys), \
            "Inconsistent finding structure across runs"

    async def test_5_runs_trace_structure(self):
        """5 runs produce trace with consistent structure."""
        from agent.graph import build_audit_graph

        mock_lightrag, mock_llm = _mock_dependencies()
        trace_structures = []

        for i in range(5):
            trace = PipelineTrace(document_name=f"test_{i}.txt")
            set_current_trace(trace)

            with patch.dict(sys.modules, {"agent.tools.lightrag_tool": mock_lightrag}), \
                 patch("agent.agents.regulation_expert.get_llm_with_fallback", return_value=mock_llm), \
                 patch("agent.agents.regulation_expert.load_prompt", return_value="Analyze: {document_content}"), \
                 patch("agent.agents.risk_assessor.get_llm_with_fallback", return_value=mock_llm), \
                 patch("agent.agents.risk_assessor.load_prompt", return_value="Assess: {document_content}"), \
                 patch("agent.agents.report_writer.get_llm_with_fallback", return_value=mock_llm), \
                 patch("agent.agents.report_writer.load_prompt", return_value="Report: {document_name}"):
                graph = build_audit_graph()
                await graph.ainvoke(_build_initial_state())

            trace.finalize()
            trace_dict = trace.to_dict()
            trace_structures.append({
                "node_count": len(trace_dict["node_events"]),
                "kg_count": len(trace_dict["kg_events"]),
                "llm_count": len(trace_dict["llm_events"]),
            })
            clear_current_trace()

        # All traces should have the same event counts
        assert all(t == trace_structures[0] for t in trace_structures), \
            f"Inconsistent trace structures: {trace_structures}"
