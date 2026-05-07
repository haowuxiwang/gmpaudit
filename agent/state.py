"""Shared state definition for the GMP audit workflow.

This TypedDict is the data bus that all agents read/write.
LangGraph uses it to manage state transitions between nodes.
"""

from typing import TypedDict, Annotated


def merge_lists(existing: list, new: list) -> list:
    """Reducer: append new items to existing list."""
    return existing + new


class AuditState(TypedDict):
    # === Input ===
    document_content: str           # Parsed document text
    document_name: str              # Filename
    document_type: str              # "deviation" | "sop" | "change_control"
    audit_focus: str                # Optional user-specified focus area

    # === Supervisor decisions ===
    next_agent: str                 # Next agent to call
    supervisor_reasoning: str       # Why this agent was chosen

    # === Regulation expert output ===
    matched_regulations: list[dict] # Matched regulation clauses
    regulation_summary: str         # Summary of regulation analysis

    # === Risk assessor output ===
    findings: list[dict]            # Audit findings list
    risk_score: int                 # 0-100
    risk_level: str                 # "high" | "medium" | "low"

    # === Report output ===
    report_markdown: str            # Generated markdown report
    report_path: str                # Report file path

    # === Flow control ===
    messages: Annotated[list, merge_lists]  # Agent message log (append-only)
    iteration: int                  # Current iteration count
    status: str                     # "running" | "completed" | "error"
