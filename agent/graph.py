"""LangGraph workflow definition for GMP audit.

Defines the StateGraph with nodes and edges for the audit workflow.
Phase 2: full graph with all 4 agents (supervisor pattern).

Flow:
    parse_doc -> supervisor -> regulation_expert -> supervisor
                             -> risk_assessor    -> supervisor
                             -> report_writer    -> supervisor -> END
"""

from langgraph.graph import StateGraph, END

from agent.state import AuditState
from agent.parsers import parse_file
from agent.agents.supervisor import supervisor_node
from agent.agents.regulation_expert import regulation_expert_node
from agent.agents.risk_assessor import risk_assessor_node
from agent.agents.report_writer import report_writer_node


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

    Architecture: Supervisor pattern
    - parse_doc: entry node, parses document
    - supervisor: routes to specialized agents
    - regulation_expert: finds relevant GMP clauses
    - risk_assessor: identifies compliance issues
    - report_writer: generates final report

    Each agent returns to supervisor after completion.
    Supervisor decides next step or terminates.
    """
    graph = StateGraph(AuditState)

    # Register all nodes
    graph.add_node("parse_doc", parse_document_node)
    graph.add_node("supervisor", supervisor_node)
    graph.add_node("regulation_expert", regulation_expert_node)
    graph.add_node("risk_assessor", risk_assessor_node)
    graph.add_node("report_writer", report_writer_node)

    # Entry point
    graph.set_entry_point("parse_doc")

    # parse_doc -> supervisor
    graph.add_edge("parse_doc", "supervisor")

    # Supervisor conditional routing
    graph.add_conditional_edges(
        "supervisor",
        lambda state: state.get("next_agent", "FINISH"),
        {
            "regulation_expert": "regulation_expert",
            "risk_assessor": "risk_assessor",
            "report_writer": "report_writer",
            "FINISH": END,
        },
    )

    # All agents return to supervisor after completion
    graph.add_edge("regulation_expert", "supervisor")
    graph.add_edge("risk_assessor", "supervisor")
    graph.add_edge("report_writer", "supervisor")

    return graph.compile()
