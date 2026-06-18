"""Shared helpers for agent audit APIs."""

import logging
import sys

from app.models.finding import Finding, FindingType, SeverityLevel

logger = logging.getLogger(__name__)

# Lazy loading: None = not checked, True = available, False = unavailable
_AGENT_CHECKED: bool | None = None
_build_audit_graph = None


def _ensure_agent() -> bool:
    """Lazy-load agent modules on first call. Returns True if available."""
    global _AGENT_CHECKED, _build_audit_graph
    if _AGENT_CHECKED is not None:
        return _AGENT_CHECKED
    try:
        from app.core import paths as _paths

        # In frozen mode, agent is bundled inside _internal/ (sys._MEIPASS)
        # In dev mode, agent is at project root
        _search = str(_paths.BUNDLE_DIR) if _paths.FROZEN else str(_paths.APP_DIR)
        if _search not in sys.path:
            sys.path.insert(0, _search)
        from agent.graph import build_audit_graph as _build

        _build_audit_graph = _build
        _AGENT_CHECKED = True
    except ImportError as exc:
        logger.warning("Agent system not available: %s", exc)
        _build_audit_graph = None
        _AGENT_CHECKED = False
    return _AGENT_CHECKED


def get_build_audit_graph():
    """Return the build_audit_graph function, loading agent if needed."""
    _ensure_agent()
    return _build_audit_graph


def is_agent_available() -> bool:
    """Check if agent system is available (triggers lazy load on first call)."""
    return _ensure_agent()


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
        "report_source": "",
        "messages": [],
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
        location=finding_data.get("location", "") or finding_data.get("source_section", ""),
        regulation_ref=finding_data.get("regulation_ref", ""),
    )
