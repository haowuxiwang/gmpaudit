"""Shared state definition for the GMP audit workflow."""

from typing import Annotated, TypedDict


def merge_lists(existing: list, new: list) -> list:
    return existing + new


class AuditState(TypedDict):
    document_content: str
    document_name: str
    document_path: str
    document_type: str
    audit_focus: str

    next_agent: str
    supervisor_reasoning: str

    matched_regulations: list[dict]
    regulation_summary: str
    regulation_checked: bool

    findings: list[dict]
    risk_score: int
    risk_level: str
    risk_assessed: bool

    report_markdown: str
    report_path: str
    report_generated: bool

    messages: Annotated[list, merge_lists]
    iteration: int
    status: str
