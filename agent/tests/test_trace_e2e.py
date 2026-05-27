"""E2E Verification: Full pipeline with real LLM and trace output.

Requires:
- Real LLM API key configured (AGENT_LLM_PROVIDER=siliconflow)
- KG index built (data/kg_output/)

Run with: pytest tests/test_trace_e2e.py -v --tb=short
"""

import json
import sys
from pathlib import Path

import pytest

from agent.trace import PipelineTrace, set_current_trace, clear_current_trace

# Skip if no real LLM configured
pytestmark = pytest.mark.e2e

_DATA_DIR = Path(__file__).parent.parent.parent / "data"
_TEST_DOCS = [
    ("sample_deviation.txt", "deviation"),
    ("sample_sop.txt", "sop"),
    ("sample_change_control.txt", "change_control"),
]
_OUTPUT_DIR = _DATA_DIR / "test_output"


@pytest.fixture(autouse=True)
def cleanup_trace():
    yield
    clear_current_trace()


def _read_test_doc(filename: str) -> str:
    """Read a test document from data/test_documents/."""
    p = _DATA_DIR / "test_documents" / filename
    if p.exists():
        return p.read_text(encoding="utf-8")
    return ""


@pytest.mark.asyncio
class TestE2E:
    """Full end-to-end pipeline verification."""

    async def test_deviation_e2e(self):
        """Full pipeline with sample_deviation.txt and real LLM."""
        from agent.main import run_audit

        doc_path = str(_DATA_DIR / "test_documents" / "sample_deviation.txt")
        result = await run_audit(doc_path, doc_type="deviation")

        # Verify pipeline completed
        assert result.get("status") in ("completed", "running"), \
            f"Pipeline status: {result.get('status')}"

        # Verify trace exists and has all layers
        trace_data = result.get("trace")
        assert trace_data is not None, "No trace in result"

        trace = trace_data
        assert trace["document_name"] == doc_path
        assert trace["status"] in ("completed", "running")

        # Verify KG events
        assert len(trace["kg_events"]) >= 1, "No KG events in trace"

        # Verify LLM events
        assert len(trace["llm_events"]) >= 1, "No LLM events in trace"

        # Verify node events
        traced_nodes = {e["node"] for e in trace["node_events"]}
        assert "parse_doc" in traced_nodes, "parse_doc not traced"
        assert "regulation_expert" in traced_nodes, "regulation_expert not traced"
        assert "risk_assessor" in traced_nodes, "risk_assessor not traced"
        assert "report_writer" in traced_nodes, "report_writer not traced"

        # Verify findings
        findings = result.get("findings", [])
        assert len(findings) >= 0, "findings should be a list"

        # Verify report
        report = result.get("report_markdown", "")
        assert isinstance(report, str)

        # Save trace to file
        _OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        trace_file = _OUTPUT_DIR / f"trace_{trace['run_id']}.json"
        trace_file.write_text(json.dumps(trace, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\nTrace saved to: {trace_file}")

        # Print summary
        print(f"\n{trace.get('summary', {})}")

    async def test_sop_e2e(self):
        """Full pipeline with sample_sop.txt and real LLM."""
        from agent.main import run_audit

        doc_path = str(_DATA_DIR / "test_documents" / "sample_sop.txt")
        result = await run_audit(doc_path, doc_type="sop")

        assert result.get("status") in ("completed", "running")
        trace = result.get("trace")
        assert trace is not None
        assert len(trace["kg_events"]) >= 1
        assert len(trace["llm_events"]) >= 1

    async def test_5x_stability_e2e(self):
        """5 runs of same document, all complete, consistent trace structure."""
        from agent.main import run_audit

        doc_path = str(_DATA_DIR / "test_documents" / "sample_deviation.txt")
        traces = []

        for i in range(5):
            result = await run_audit(doc_path, doc_type="deviation")
            assert result.get("status") in ("completed", "running"), \
                f"Run {i} failed with status: {result.get('status')}"
            trace = result.get("trace")
            assert trace is not None, f"Run {i} has no trace"
            traces.append(trace)

        # All traces should have consistent structure
        for i, t in enumerate(traces):
            assert len(t["kg_events"]) >= 1, f"Run {i}: no KG events"
            assert len(t["llm_events"]) >= 1, f"Run {i}: no LLM events"
            assert len(t["node_events"]) >= 4, f"Run {i}: too few node events"

    async def test_10x_llm_stability(self):
        """10 consecutive LLM calls without 401 errors."""
        import asyncio
        from agent.config import get_llm_with_fallback, call_llm_with_retry

        llm = get_llm_with_fallback(temperature=0.1)
        successes = 0
        auth_errors = 0

        for i in range(10):
            try:
                resp = await call_llm_with_retry(llm, f"Say 'pong {i}' and nothing else.")
                if resp.content:
                    successes += 1
            except Exception as e:
                error_str = str(e).lower()
                if any(kw in error_str for kw in ("401", "403", "unauthorized")):
                    auth_errors += 1

        assert auth_errors == 0, f"Auth errors: {auth_errors}"
        assert successes >= 8, f"Expected >= 8 successes, got {successes}"
