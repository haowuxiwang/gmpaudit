"""LangGraph workflow definition for GMP audit.

Defines the StateGraph with nodes and edges for the audit workflow.

Flow:
    parse_doc -> regulation_expert -> risk_assessor -> report_writer -> END

Each node handles its own errors gracefully (returns fallback results).
"""

import logging

from langgraph.graph import StateGraph, END

from agent.state import AuditState
from agent.parsers import parse_file
from agent.agents.regulation_expert import regulation_expert_node
from agent.agents.risk_assessor import risk_assessor_node
from agent.agents.report_writer import report_writer_node

logger = logging.getLogger(__name__)


def traced_node(node_func, node_name: str = ""):
    """Wrap a LangGraph node to record execution trace events.

    Supports both sync and async node functions.
    """
    import asyncio
    from agent.trace import get_current_trace, NodeTraceEvent, now_ms

    is_async = asyncio.iscoroutinefunction(node_func)

    async def wrapper(state: AuditState) -> dict:
        trace = get_current_trace()
        name = node_name or getattr(node_func, "__name__", "unknown")
        event = NodeTraceEvent(node=name, started_at=now_ms())
        try:
            if is_async:
                result = await node_func(state)
            else:
                result = node_func(state)
            event.finished_at = now_ms()
            event.latency_ms = round(event.finished_at - event.started_at, 1)
            if trace:
                trace.node_events.append(event)
            return result
        except Exception as e:
            event.finished_at = now_ms()
            event.latency_ms = round(event.finished_at - event.started_at, 1)
            event.error = str(e)[:500]
            if trace:
                trace.node_events.append(event)
            raise
    return wrapper


def parse_document_node(state: AuditState) -> dict:
    """Parse the uploaded document and populate state."""
    file_path = state.get("document_path") or state.get("document_name", "")
    content = state.get("document_content", "")
    if not content.strip():
        try:
            content = parse_file(file_path)
        except FileNotFoundError:
            return {
                "document_content": "",
                "status": "error",
                "messages": [f"Error: File not found: {file_path}"],
            }
        except ValueError as e:
            return {
                "document_content": "",
                "status": "error",
                "messages": [f"Error: {e}"],
            }
        except Exception as e:
            return {
                "document_content": "",
                "status": "error",
                "messages": [f"Error parsing document: {e}"],
            }

    # Detect document type from filename/content heuristics
    doc_type = state.get("document_type", "unknown")
    if doc_type == "unknown":
        content_lower = content.lower()
        if any(kw in content_lower for kw in ["偏差", "deviation", "非计划"]):
            doc_type = "deviation"
        elif any(kw in content_lower for kw in ["变更", "change control"]):
            doc_type = "change_control"
        else:
            doc_type = "sop"

    return {
        "document_content": content,
        "document_type": doc_type,
        "regulation_checked": False,
        "risk_assessed": False,
        "report_generated": False,
        "status": "running",
        "messages": [f"Document parsed: {state.get('document_name', file_path)} ({len(content)} chars, type={doc_type})"],
    }


def build_audit_graph():
    """Build and compile the LangGraph workflow.

    Architecture: Sequential pipeline with error handling
    - parse_doc: entry node, parses document
    - regulation_expert: finds relevant GMP clauses
    - risk_assessor: identifies compliance issues
    - report_writer: generates final report

    Each node handles its own errors gracefully (returns fallback results).
    Pipeline stops if document parsing fails.
    """
    graph = StateGraph(AuditState)

    # Register all nodes with trace wrappers
    graph.add_node("parse_doc", traced_node(parse_document_node, "parse_doc"))
    graph.add_node("regulation_expert", traced_node(regulation_expert_node, "regulation_expert"))
    graph.add_node("risk_assessor", traced_node(risk_assessor_node, "risk_assessor"))
    graph.add_node("report_writer", traced_node(report_writer_node, "report_writer"))

    # Entry point
    graph.set_entry_point("parse_doc")

    # Conditional edge: stop on parse error, continue otherwise
    graph.add_conditional_edges(
        "parse_doc",
        lambda state: "END" if state.get("status") == "error" else "regulation_expert",
        {
            "regulation_expert": "regulation_expert",
            "END": END,
        },
    )

    # Sequential pipeline
    graph.add_edge("regulation_expert", "risk_assessor")
    graph.add_edge("risk_assessor", "report_writer")
    graph.add_edge("report_writer", END)

    return graph.compile()
