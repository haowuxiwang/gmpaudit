"""Report Writer Agent.

Generates a structured GMP audit report in Markdown format.
"""

import logging
from datetime import date
from pathlib import Path

from agent.config import get_llm, call_llm_with_retry

logger = logging.getLogger(__name__)
from agent.state import AuditState


def _load_prompt() -> str:
    prompt_path = Path(__file__).parent.parent / "prompts" / "report_writer.txt"
    return prompt_path.read_text(encoding="utf-8")


def _format_findings(findings: list[dict]) -> str:
    """Format findings into a readable text block."""
    if not findings:
        return "No findings identified."

    lines = []
    for i, f in enumerate(findings, 1):
        severity = f.get("severity", "N/A").upper()
        title = f.get("title", "Untitled")
        desc = f.get("description", "")
        evidence = f.get("evidence", "")
        suggestion = f.get("suggestion", "")
        ref = f.get("regulation_ref", "")

        lines.append(f"### Finding {i}: [{severity}] {title}")
        lines.append(f"Description: {desc}")
        if evidence:
            lines.append(f"Evidence: {evidence}")
        if ref:
            lines.append(f"Regulation: {ref}")
        if suggestion:
            lines.append(f"Suggestion: {suggestion}")
        lines.append("")

    return "\n".join(lines)


async def report_writer_node(state: AuditState) -> dict:
    """Generate the final audit report in Markdown format."""
    doc_name = state.get("document_name", "Unknown")
    doc_type = state.get("document_type", "unknown")
    risk_score = state.get("risk_score", 0)
    risk_level = state.get("risk_level", "unknown")
    logger.info(f"Report Writer: generating report for {doc_name}")
    regulation_summary = state.get("regulation_summary", "")
    findings = state.get("findings", [])

    findings_text = _format_findings(findings)

    # Call LLM to generate the report
    try:
        llm = get_llm(provider=None, temperature=0.3)
        prompt_template = _load_prompt()
        prompt = prompt_template.format(
            document_name=doc_name,
            document_type=doc_type,
            risk_score=risk_score,
            risk_level=risk_level,
            regulation_summary=regulation_summary,
            findings_text=findings_text,
        )

        response = await call_llm_with_retry(llm, prompt)
        report_md = response.content
    except Exception as e:
        logger.warning(f"Report Writer LLM call failed, using fallback: {e}")
        # Fallback: generate a basic report without LLM
        report_md = _generate_fallback_report(
            doc_name, doc_type, risk_score, risk_level,
            regulation_summary, findings,
        )

    # Save report to file
    safe_name = Path(doc_name).stem
    from datetime import datetime
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_filename = f"{safe_name}_{timestamp}.md"
    report_dir = Path(__file__).parent.parent.parent / "data" / "reports"
    report_dir.mkdir(parents=True, exist_ok=True)
    report_path = report_dir / report_filename

    try:
        report_path.write_text(report_md, encoding="utf-8")
        logger.info(f"Report Writer: report saved to {report_path}")
    except Exception as e:
        logger.error(f"Report Writer: failed to save report: {e}")
        return {
            "report_markdown": report_md,
            "report_path": "",
            "report_generated": True,
            "status": "completed",
            "messages": [f"Report Writer: generated report but failed to save to disk — {e}"],
        }

    return {
        "report_markdown": report_md,
        "report_path": str(report_path),
        "report_generated": True,
        "status": "completed",
        "messages": [f"Report Writer: report saved to {report_path}"],
    }


def _generate_fallback_report(
    doc_name: str,
    doc_type: str,
    risk_score: int,
    risk_level: str,
    regulation_summary: str,
    findings: list[dict],
) -> str:
    """Generate a basic report when LLM is unavailable."""
    high = [f for f in findings if f.get("severity") == "high"]
    medium = [f for f in findings if f.get("severity") == "medium"]
    low = [f for f in findings if f.get("severity") == "low"]

    lines = [
        "# GMP Compliance Audit Report",
        "",
        "## 1. Audit Overview",
        f"- Document: {doc_name}",
        f"- Type: {doc_type}",
        f"- Date: {date.today().isoformat()}",
        "",
        "## 2. Regulation Basis",
        regulation_summary or "N/A",
        "",
        "## 3. Audit Findings",
        f"- High severity: {len(high)}",
        f"- Medium severity: {len(medium)}",
        f"- Low severity: {len(low)}",
        "",
    ]

    for i, f in enumerate(findings, 1):
        sev = f.get("severity", "N/A").upper()
        lines.append(f"### {i}. [{sev}] {f.get('title', 'Untitled')}")
        lines.append(f"{f.get('description', '')}")
        if f.get("evidence"):
            lines.append(f"Evidence: {f['evidence']}")
        lines.append("")

    lines.extend([
        "## 4. Risk Assessment",
        f"- Risk Score: {risk_score}/100",
        f"- Risk Level: {risk_level}",
        "",
        "## 5. Recommendations",
        "Implement CAPA based on findings above.",
        "",
        "## 6. Conclusion",
        "Review completed. See findings and recommendations.",
    ])

    return "\n".join(lines)
