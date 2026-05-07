"""Risk Assessor Agent.

Analyzes document content against regulations to identify
compliance issues and calculate risk scores.
"""

import json
import re
from pathlib import Path

from agent.config import get_llm
from agent.state import AuditState
from agent.tools.risk_matrix import calculate_risk_score, format_risk_summary


def _load_prompt() -> str:
    prompt_path = Path(__file__).parent.parent / "prompts" / "risk_assessor.txt"
    return prompt_path.read_text(encoding="utf-8")


def _parse_llm_json(content: str) -> list[dict]:
    """Robustly parse JSON from LLM output."""
    content = re.sub(r"```json\s*", "", content)
    content = re.sub(r"```\s*", "", content)
    content = content.strip()

    try:
        result = json.loads(content)
        return result if isinstance(result, list) else [result]
    except json.JSONDecodeError:
        pass

    for pattern in [r"\[.*\]", r"\{.*\}"]:
        match = re.search(pattern, content, re.DOTALL)
        if match:
            try:
                result = json.loads(match.group())
                return result if isinstance(result, list) else [result]
            except json.JSONDecodeError:
                continue

    return []


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

    # Format regulation context for the prompt
    regulation_context = _format_regulations(regulations)

    # Call LLM for analysis
    try:
        llm = get_llm(provider="siliconflow", temperature=0.2)
        prompt_template = _load_prompt()
        prompt = prompt_template.format(
            document_content=doc_content,
            regulation_context=regulation_context,
            document_type=doc_type,
        )

        response = await llm.ainvoke(prompt)
        findings = _parse_llm_json(response.content)
    except Exception:
        findings = []

    # Ensure each finding has required fields
    for f in findings:
        f.setdefault("severity", "medium")
        f.setdefault("type", "compliance")
        f.setdefault("title", "Untitled finding")
        f.setdefault("description", "")

    # Calculate risk score
    risk_score, risk_level = calculate_risk_score(findings)

    # Format summary
    summary = format_risk_summary(findings)

    return {
        "findings": findings,
        "risk_score": risk_score,
        "risk_level": risk_level,
        "messages": [
            f"Risk Assessor: identified {len(findings)} findings",
            f"Risk score: {risk_score}/100, level: {risk_level}",
        ],
    }
