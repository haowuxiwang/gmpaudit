"""Risk Assessor Agent.

Analyzes document content against regulations to identify
compliance issues and calculate risk scores.
"""

import logging
from pathlib import Path

from agent.config import get_llm, call_llm_with_retry
from agent.tools.json_parser import parse_llm_json as _parse_llm_json

logger = logging.getLogger(__name__)
from agent.state import AuditState
from agent.tools.risk_matrix import calculate_risk_score


def _load_prompt() -> str:
    prompt_path = Path(__file__).parent.parent / "prompts" / "risk_assessor.txt"
    return prompt_path.read_text(encoding="utf-8")


def _format_regulations(regulations: list[dict]) -> str:
    """Format regulations into a readable context string."""
    if not regulations:
        return "No specific regulations matched."

    lines = []
    for reg in regulations[:5]:
        reg_name = reg.get("regulation", "")
        title = reg.get("title", "")
        content = reg.get("content", "")[:200]
        lines.append(f"- {reg_name} | {title}: {content}")
    return "\n".join(lines)


async def risk_assessor_node(state: AuditState) -> dict:
    """Analyze document for compliance issues and risk assessment.

    Uses LLM to identify findings, then calculates risk score.
    """
    doc_content = state.get("document_content", "")[:3000]
    doc_type = state.get("document_type", "unknown")
    regulations = state.get("matched_regulations", [])
    logger.info(f"Risk Assessor: doc_type={doc_type}, regulations={len(regulations)}")

    # Format regulation context for the prompt
    regulation_context = _format_regulations(regulations)

    # Call LLM for analysis
    try:
        llm = get_llm(provider=None, temperature=0.2)
        prompt_template = _load_prompt()
        prompt = prompt_template.format(
            document_content=doc_content,
            regulation_context=regulation_context,
            document_type=doc_type,
        )

        response = await call_llm_with_retry(llm, prompt)
        findings = _parse_llm_json(response.content)
    except Exception as e:
        logger.warning(f"Risk Assessor LLM call failed: {e}")
        return {
            "findings": [],
            "risk_score": 0,
            "risk_level": "not_assessed",
            "risk_assessed": True,
            "status": "running",
            "messages": [f"Risk Assessor: LLM call failed, continuing with empty findings — {e}"],
        }

    # Ensure each finding has required fields
    for f in findings:
        f.setdefault("severity", "medium")
        f.setdefault("type", "compliance")
        f.setdefault("title", "Untitled finding")
        f.setdefault("description", "")

    # Calculate risk score
    risk_score, risk_level = calculate_risk_score(findings)

    logger.info(f"Risk Assessor: {len(findings)} findings, score={risk_score}, level={risk_level}")

    return {
        "findings": findings,
        "risk_score": risk_score,
        "risk_level": risk_level,
        "risk_assessed": True,
        "messages": [
            f"Risk Assessor: identified {len(findings)} findings",
            f"Risk score: {risk_score}/100, level: {risk_level}",
        ],
    }
