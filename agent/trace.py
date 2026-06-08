"""Pipeline tracing infrastructure for GMP Audit Agent.

Provides structured trace events for every pipeline execution,
enabling per-layer debugging and explainability.

Usage:
    from agent.trace import PipelineTrace, set_current_trace, get_current_trace

    trace = PipelineTrace(document_name="sample.txt")
    set_current_trace(trace)
    try:
        # ... run pipeline ...
        trace.finalize()
    finally:
        clear_current_trace()
"""

import contextvars
import time
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone


# ---------------------------------------------------------------------------
# Trace event data classes
# ---------------------------------------------------------------------------

@dataclass
class KGTraceEvent:
    """Records a single KG/RAG query attempt."""
    source: str = ""          # "lightrag" | "fallback_db" | "lightrag_failed"
    query: str = ""           # actual query text sent to KG
    result_count: int = 0
    latency_ms: float = 0.0
    error: str | None = None

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class LLMTraceEvent:
    """Records a single LLM call attempt."""
    provider: str = ""
    model: str = ""
    node: str = ""            # regulation_expert | risk_assessor | report_writer
    prompt_length: int = 0
    prompt_preview: str = ""  # first 200 chars
    response_length: int = 0
    latency_ms: float = 0.0
    success: bool = True
    error: str | None = None
    was_fallback: bool = False
    retry_count: int = 0

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class NodeTraceEvent:
    """Records a single LangGraph node execution."""
    node: str = ""
    started_at: float = 0.0
    finished_at: float = 0.0
    latency_ms: float = 0.0
    error: str | None = None

    def to_dict(self) -> dict:
        return asdict(self)


# ---------------------------------------------------------------------------
# Pipeline trace container
# ---------------------------------------------------------------------------

@dataclass
class PipelineTrace:
    """Container for all trace events in a single pipeline run."""
    run_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    document_name: str = ""
    kg_events: list[KGTraceEvent] = field(default_factory=list)
    llm_events: list[LLMTraceEvent] = field(default_factory=list)
    node_events: list[NodeTraceEvent] = field(default_factory=list)
    started_at: str = field(default_factory=lambda: _utcnow())
    finished_at: str | None = None
    status: str = "running"

    def finalize(self, status: str = "completed"):
        """Compute summary fields from events."""
        self.status = status
        self.finished_at = _utcnow()

    def to_dict(self) -> dict:
        """Serialize to dict for JSON output."""
        d = asdict(self)
        d["summary"] = self._summary_dict()
        return d

    def _summary_dict(self) -> dict:
        kg_sources = [e.source for e in self.kg_events]
        llm_providers = [e.provider for e in self.llm_events]
        llm_successes = sum(1 for e in self.llm_events if e.success)
        llm_fallbacks = sum(1 for e in self.llm_events if e.was_fallback)
        total_latency = sum(e.latency_ms for e in self.node_events)

        return {
            "total_nodes": len(self.node_events),
            "total_kg_queries": len(self.kg_events),
            "kg_sources": kg_sources,
            "total_llm_calls": len(self.llm_events),
            "llm_successes": llm_successes,
            "llm_failures": len(self.llm_events) - llm_successes,
            "llm_fallbacks": llm_fallbacks,
            "llm_providers": list(set(llm_providers)),
            "total_latency_ms": round(total_latency, 1),
        }

    def summary_report(self) -> str:
        """Human-readable trace report."""
        lines = []
        lines.append(f"=== Pipeline Trace: {self.document_name} ===")
        lines.append(f"Run ID:    {self.run_id}")
        lines.append(f"Status:    {self.status}")
        lines.append(f"Started:   {self.started_at}")
        lines.append(f"Finished:  {self.finished_at or 'N/A'}")
        lines.append("")

        # Node execution path
        lines.append("--- Node Execution Path ---")
        for ne in self.node_events:
            status_icon = "ERROR" if ne.error else "OK"
            lines.append(
                f"  [{status_icon}] {ne.node}: {ne.latency_ms:.0f}ms"
                + (f" error={ne.error}" if ne.error else "")
            )
        lines.append("")

        # KG queries
        lines.append("--- KG/RAG Queries ---")
        for i, ke in enumerate(self.kg_events, 1):
            lines.append(
                f"  Q{i}: source={ke.source}, results={ke.result_count}, "
                f"latency={ke.latency_ms:.0f}ms"
            )
            if ke.query:
                query_preview = ke.query[:80] + ("..." if len(ke.query) > 80 else "")
                lines.append(f'       query="{query_preview}"')
            if ke.error:
                lines.append(f"       error={ke.error}")
        lines.append("")

        # LLM calls
        lines.append("--- LLM Calls ---")
        for i, le in enumerate(self.llm_events, 1):
            status_icon = "OK" if le.success else "FAIL"
            fb = " (FALLBACK)" if le.was_fallback else ""
            lines.append(
                f"  L{i}: [{status_icon}] {le.provider}/{le.model} "
                f"node={le.node}{fb}"
            )
            lines.append(
                f"       prompt={le.prompt_length}chars, "
                f"response={le.response_length}chars, "
                f"latency={le.latency_ms:.0f}ms"
            )
            if le.retry_count > 0:
                lines.append(f"       retries={le.retry_count}")
            if le.error:
                lines.append(f"       error={le.error}")
        lines.append("")

        # Summary
        s = self._summary_dict()
        lines.append("--- Summary ---")
        lines.append(f"  Nodes executed:   {s['total_nodes']}")
        lines.append(f"  KG queries:       {s['total_kg_queries']} (sources: {s['kg_sources']})")
        lines.append(f"  LLM calls:        {s['total_llm_calls']} ({s['llm_successes']} ok, {s['llm_failures']} failed, {s['llm_fallbacks']} fallback)")
        lines.append(f"  LLM providers:    {s['llm_providers']}")
        lines.append(f"  Total latency:    {s['total_latency_ms']}ms")

        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Thread-local context
# ---------------------------------------------------------------------------

_current_trace: contextvars.ContextVar[PipelineTrace | None] = contextvars.ContextVar(
    '_current_trace', default=None
)


def get_current_trace() -> PipelineTrace | None:
    """Get the current pipeline trace (or None if no trace is active)."""
    return _current_trace.get()


def set_current_trace(trace: PipelineTrace):
    """Set the current pipeline trace."""
    _current_trace.set(trace)


def clear_current_trace():
    """Clear the current pipeline trace."""
    _current_trace.set(None)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def now_ms() -> float:
    """Current time in milliseconds (monotonic, immune to clock adjustments)."""
    return time.monotonic() * 1000
