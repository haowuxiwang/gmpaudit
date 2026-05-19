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
        return "未发现审计问题。"

    lines = []
    for i, f in enumerate(findings, 1):
        severity = f.get("severity", "N/A").upper()
        title = f.get("title", "无标题")
        desc = f.get("description", "")
        evidence = f.get("evidence", "")
        suggestion = f.get("suggestion", "")
        ref = f.get("regulation_ref", "")

        lines.append(f"### 发现 {i}: [{severity}] {title}")
        lines.append(f"问题描述: {desc}")
        if evidence:
            lines.append(f"证据: {evidence}")
        if ref:
            lines.append(f"法规依据: {ref}")
        if suggestion:
            lines.append(f"改进建议: {suggestion}")
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
    used_fallback = False
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
        used_fallback = True
        # Fallback: generate a basic report without LLM
        fallback_md = _generate_fallback_report(
            doc_name, doc_type, risk_score, risk_level,
            regulation_summary, findings,
        )
        report_md = "> **注意**: 本报告由备用逻辑生成，因为 LLM 服务不可用。\n\n" + fallback_md

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
        "report_source": "fallback" if used_fallback else "llm",
        "messages": [
            f"Report Writer: report saved to {report_path}",
            *([] if not used_fallback else ["Report Writer: LLM unavailable, generated fallback report"]),
        ],
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
        "# GMP 合规性审计报告",
        "",
        "## 1. 审计概述",
        f"- 审计对象: {doc_name}",
        f"- 文档类型: {doc_type}",
        f"- 审计日期: {date.today().isoformat()}",
        "",
        "## 2. 法规依据",
        regulation_summary or "无",
        "",
        "## 3. 审计发现",
        f"- 高风险: {len(high)}",
        f"- 中风险: {len(medium)}",
        f"- 低风险: {len(low)}",
        "",
    ]

    for i, f in enumerate(findings, 1):
        sev = f.get("severity", "N/A").upper()
        lines.append(f"### {i}. [{sev}] {f.get('title', '无标题')}")
        lines.append(f"{f.get('description', '')}")
        if f.get("evidence"):
            lines.append(f"证据: {f['evidence']}")
        lines.append("")

    lines.extend([
        "## 4. 风险评估",
        f"- 风险评分: {risk_score}/100",
        f"- 风险等级: {risk_level}",
        "",
        "## 5. 改进建议",
        "根据上述发现实施纠正预防措施（CAPA）。",
        "",
        "## 6. 结论",
        "审计完成。请参阅上述发现和建议。",
    ])

    return "\n".join(lines)
