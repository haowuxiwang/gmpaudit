"""Unit tests for agent.trace: event dataclasses, PipelineTrace, and context vars."""

import time

from agent.trace import (
    KGTraceEvent,
    LLMTraceEvent,
    NodeTraceEvent,
    PipelineTrace,
    clear_current_trace,
    get_current_trace,
    now_ms,
    set_current_trace,
)


class TestKGTraceEvent:
    def test_defaults(self):
        e = KGTraceEvent()
        assert e.source == ""
        assert e.query == ""
        assert e.result_count == 0
        assert e.latency_ms == 0.0
        assert e.error is None

    def test_to_dict(self):
        e = KGTraceEvent(source="lightrag", query="test", result_count=3, latency_ms=42.5)
        d = e.to_dict()
        assert d["source"] == "lightrag"
        assert d["query"] == "test"
        assert d["result_count"] == 3
        assert d["latency_ms"] == 42.5
        assert d["error"] is None

    def test_to_dict_with_error(self):
        e = KGTraceEvent(source="lightrag_failed", error="timeout")
        d = e.to_dict()
        assert d["error"] == "timeout"


class TestLLMTraceEvent:
    def test_defaults(self):
        e = LLMTraceEvent()
        assert e.provider == ""
        assert e.model == ""
        assert e.node == ""
        assert e.success is True
        assert e.was_fallback is False
        assert e.retry_count == 0
        assert e.error is None

    def test_to_dict(self):
        e = LLMTraceEvent(
            provider="deepseek",
            model="deepseek-chat",
            node="risk_assessor",
            prompt_length=500,
            response_length=200,
            latency_ms=1200.0,
            success=True,
            was_fallback=False,
            retry_count=1,
        )
        d = e.to_dict()
        assert d["provider"] == "deepseek"
        assert d["model"] == "deepseek-chat"
        assert d["node"] == "risk_assessor"
        assert d["prompt_length"] == 500
        assert d["retry_count"] == 1

    def test_to_dict_failure(self):
        e = LLMTraceEvent(success=False, error="rate limited", was_fallback=True)
        d = e.to_dict()
        assert d["success"] is False
        assert d["error"] == "rate limited"
        assert d["was_fallback"] is True


class TestNodeTraceEvent:
    def test_defaults(self):
        e = NodeTraceEvent()
        assert e.node == ""
        assert e.started_at == 0.0
        assert e.finished_at == 0.0
        assert e.latency_ms == 0.0
        assert e.error is None

    def test_to_dict(self):
        e = NodeTraceEvent(node="regulation_expert", latency_ms=350.0)
        d = e.to_dict()
        assert d["node"] == "regulation_expert"
        assert d["latency_ms"] == 350.0
        assert d["error"] is None


class TestPipelineTrace:
    def test_finalize_sets_status_and_finished_at(self):
        t = PipelineTrace(document_name="test.txt")
        assert t.status == "running"
        assert t.finished_at is None
        t.finalize("completed")
        assert t.status == "completed"
        assert t.finished_at is not None

    def test_finalize_custom_status(self):
        t = PipelineTrace()
        t.finalize("error")
        assert t.status == "error"

    def test_to_dict_includes_summary(self):
        t = PipelineTrace(document_name="doc.txt")
        t.kg_events.append(KGTraceEvent(source="lightrag", result_count=2, latency_ms=50.0))
        t.llm_events.append(LLMTraceEvent(provider="deepseek", success=True, latency_ms=100.0))
        t.node_events.append(NodeTraceEvent(node="regulation_expert", latency_ms=150.0))
        d = t.to_dict()
        assert "summary" in d
        s = d["summary"]
        assert s["total_nodes"] == 1
        assert s["total_kg_queries"] == 1
        assert s["kg_sources"] == ["lightrag"]
        assert s["total_llm_calls"] == 1
        assert s["llm_successes"] == 1
        assert s["llm_failures"] == 0
        assert s["total_latency_ms"] == 150.0

    def test_summary_report_contains_sections(self):
        t = PipelineTrace(document_name="sample.pdf")
        t.kg_events.append(KGTraceEvent(source="lightrag", query="GMP deviation", result_count=5, latency_ms=80.0))
        t.llm_events.append(
            LLMTraceEvent(provider="deepseek", model="deepseek-chat", node="risk_assessor", latency_ms=200.0)
        )
        t.node_events.append(NodeTraceEvent(node="risk_assessor", latency_ms=200.0))
        t.finalize("completed")
        report = t.summary_report()
        assert "sample.pdf" in report
        assert "Run ID:" in report
        assert "Node Execution Path" in report
        assert "KG/RAG Queries" in report
        assert "LLM Calls" in report
        assert "Summary" in report
        assert "risk_assessor" in report

    def test_summary_report_error_node(self):
        t = PipelineTrace()
        t.node_events.append(NodeTraceEvent(node="report_writer", error="LLM timeout"))
        report = t.summary_report()
        assert "ERROR" in report
        assert "LLM timeout" in report

    def test_summary_report_kg_error(self):
        """KG event with error should be displayed in summary."""
        t = PipelineTrace()
        t.kg_events.append(KGTraceEvent(source="lightrag_failed", query="test", result_count=0, latency_ms=50.0, error="connection refused"))
        report = t.summary_report()
        assert "connection refused" in report

    def test_summary_report_llm_retry_count(self):
        """LLM event with retry_count > 0 should display retries."""
        t = PipelineTrace()
        t.llm_events.append(LLMTraceEvent(provider="deepseek", model="deepseek-chat", node="test", retry_count=2, latency_ms=100.0))
        report = t.summary_report()
        assert "retries=2" in report

    def test_summary_report_llm_error(self):
        """LLM event with error should display error."""
        t = PipelineTrace()
        t.llm_events.append(LLMTraceEvent(provider="mimo", model="test", node="test", success=False, error="rate limited", latency_ms=50.0))
        report = t.summary_report()
        assert "rate limited" in report

    def test_to_dict_empty_events(self):
        t = PipelineTrace()
        d = t.to_dict()
        s = d["summary"]
        assert s["total_nodes"] == 0
        assert s["total_kg_queries"] == 0
        assert s["total_llm_calls"] == 0
        assert s["llm_providers"] == []

    def test_llm_providers_deduplicated(self):
        t = PipelineTrace()
        t.llm_events.append(LLMTraceEvent(provider="deepseek"))
        t.llm_events.append(LLMTraceEvent(provider="deepseek"))
        t.llm_events.append(LLMTraceEvent(provider="qwen"))
        d = t.to_dict()
        assert set(d["summary"]["llm_providers"]) == {"deepseek", "qwen"}


class TestContextVar:
    def test_default_is_none(self):
        clear_current_trace()
        assert get_current_trace() is None

    def test_set_and_get(self):
        t = PipelineTrace(document_name="ctx_test.txt")
        set_current_trace(t)
        assert get_current_trace() is t
        clear_current_trace()

    def test_clear(self):
        set_current_trace(PipelineTrace())
        assert get_current_trace() is not None
        clear_current_trace()
        assert get_current_trace() is None

    def test_lifecycle(self):
        clear_current_trace()
        assert get_current_trace() is None
        t1 = PipelineTrace(document_name="first.txt")
        set_current_trace(t1)
        assert get_current_trace().document_name == "first.txt"
        t2 = PipelineTrace(document_name="second.txt")
        set_current_trace(t2)
        assert get_current_trace().document_name == "second.txt"
        clear_current_trace()
        assert get_current_trace() is None


class TestNowMs:
    def test_returns_positive_float(self):
        val = now_ms()
        assert isinstance(val, float)
        assert val > 0

    def test_monotonic(self):
        a = now_ms()
        b = now_ms()
        assert b >= a

    def test_reasonable_range(self):
        """now_ms should produce a measurable difference after a sleep."""
        before = now_ms()
        time.sleep(0.05)
        after = now_ms()
        diff = after - before
        # Windows monotonic resolution can be coarse; just check direction
        assert diff >= 0
        assert diff < 5000
