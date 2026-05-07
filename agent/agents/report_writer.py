"""Report Writer Agent.

Generates a structured GMP audit report in Markdown format.
"""

from datetime import date
from pathlib import Path

from agent.config import get_llm
from agent.state import AuditState
from agent.tools.risk_matrix import format_risk_summary


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

        response = await llm.ainvoke(prompt)
        report_md = response.content
    except Exception:
        # Fallback: generate a basic report without LLM
        report_md = _generate_fallback_report(
            doc_name, doc_type, risk_score, risk_level,
            regulation_summary, findings,
        )

    # Save report to file
    safe_name = Path(doc_name).stem
    report_filename = f"{safe_name}_{date.today().isoformat()}.md"
    report_dir = Path(__file__).parent.parent.parent / "data" / "reports"
    report_dir.mkdir(parents=True, exist_ok=True)
    report_path = report_dir / report_filename

    report_path.write_text(report_md, encoding="utf-8")

    return {
        "report_markdown": report_md,
        "report_path": str(report_path),
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
