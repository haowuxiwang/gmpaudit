"""Shared helpers for agent audit APIs."""

import logging
import sys
from pathlib import Path

from app.models.finding import Finding, FindingType, SeverityLevel

logger = logging.getLogger(__name__)

AGENT_AVAILABLE = False
build_audit_graph = None

try:
    project_root = str(Path(__file__).parent.parent.parent.parent)
    if project_root not in sys.path:
        sys.path.insert(0, project_root)
    from agent.graph import build_audit_graph

    AGENT_AVAILABLE = True
except ImportError as exc:
    logger.warning("Agent system not available: %s", exc)
    build_audit_graph = None


def build_initial_state(
    document_path: str,
    document_type: str,
    focus: str = "",
    document_content: str = "",
    document_name: str | None = None,
) -> dict:
    return {
        "document_name": document_name or document_path,
        "document_path": document_path,
        "document_type": document_type,
        "audit_focus": focus,
        "document_content": document_content,
        "next_agent": "",
        "supervisor_reasoning": "",
        "matched_regulations": [],
        "regulation_summary": "",
        "regulation_checked": False,
        "findings": [],
        "risk_score": 0,
        "risk_level": "",
        "risk_assessed": False,
        "report_markdown": "",
        "report_path": "",
        "report_generated": False,
        "messages": [],
        "iteration": 0,
        "status": "running",
    }


def normalize_finding(finding_data: dict, task_id: int, document_id: int | None = None) -> Finding:
    severity_raw = finding_data.get("severity", "medium").lower()
    if severity_raw in ("high", "critical"):
        severity = SeverityLevel.HIGH
    elif severity_raw in ("low", "info"):
        severity = SeverityLevel.LOW
    else:
        severity = SeverityLevel.MEDIUM

    type_map = {
        "logic_flaw": FindingType.LOGIC_FLAW,
        "compliance": FindingType.COMPLIANCE_RISK,
        "compliance_risk": FindingType.COMPLIANCE_RISK,
        "inconsistency": FindingType.INCONSISTENCY,
        "missing_info": FindingType.MISSING_INFO,
        "best_practice": FindingType.BEST_PRACTICE,
    }
    finding_type = type_map.get(finding_data.get("type", "compliance_risk").lower(), FindingType.COMPLIANCE_RISK)

    return Finding(
        task_id=task_id,
        document_id=document_id,
        finding_type=finding_type,
        severity=severity,
        title=finding_data.get("title", "Unknown finding"),
        description=finding_data.get("description", ""),
        evidence=finding_data.get("evidence", ""),
        suggestion=finding_data.get("suggestion", ""),
        location=finding_data.get("location", ""),
        regulation_ref=finding_data.get("regulation_ref", ""),
    )
