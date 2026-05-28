"""Risk Assessor Agent.

Analyzes document content against regulations to identify
compliance issues and calculate risk scores.

Supports two strategies based on document size:
- Stuff: single LLM call for documents ≤ STUFF_LIMIT
- Map-Reduce: chunked analysis for larger documents
"""

import logging

from agent.config import get_llm_with_fallback, call_llm_with_retry, MAX_DOCUMENT_CHARS
from agent.tools.document_chunker import select_strategy, chunk_document, deduplicate_findings
from agent.tools.json_parser import parse_llm_json as _parse_llm_json
from agent.tools.prompt_loader import load_prompt

logger = logging.getLogger(__name__)
from agent.state import AuditState
from agent.tools.risk_matrix import calculate_risk_score


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


async def _analyze_chunk(
    llm,
    prompt_template: str,
    chunk_content: str,
    regulation_context: str,
    doc_type: str,
    section_path: str,
) -> list[dict]:
    """Analyze a single document chunk for compliance findings."""
    try:
        prompt = prompt_template.format(
            document_content=chunk_content,
            regulation_context=regulation_context,
            document_type=doc_type,
        )
        response = await call_llm_with_retry(llm, prompt, node="risk_assessor")
        findings = _parse_llm_json(response.content)

        # Tag each finding with its source section
        for f in findings:
            if section_path:
                f.setdefault("source_section", section_path)

        return findings
    except Exception as e:
        logger.warning("Chunk analysis failed for section '%s': %s", section_path, e)
        return []


def _ensure_finding_defaults(findings: list[dict]) -> list[dict]:
    """Ensure each finding has required fields."""
    for f in findings:
        f.setdefault("severity", "medium")
        f.setdefault("type", "compliance")
        f.setdefault("title", "Untitled finding")
        f.setdefault("description", "")
    return findings


async def risk_assessor_node(state: AuditState) -> dict:
    """Analyze document for compliance issues and risk assessment.

    Strategy selection:
    - Stuff (≤STUFF_LIMIT): single LLM call with full content
    - Map-Reduce (>STUFF_LIMIT): chunk → per-chunk analysis → aggregate + deduplicate
    """
    full_content = state.get("document_content", "")
    doc_type = state.get("document_type", "unknown")
    regulations = state.get("matched_regulations", [])
    doc_name = state.get("document_name", "unknown")
    strategy = select_strategy(full_content)

    logger.info("Risk Assessor: doc_type=%s, content_len=%d, regulations=%d, strategy=%s",
                doc_type, len(full_content), len(regulations), strategy)

    regulation_context = _format_regulations(regulations)

    try:
        llm = get_llm_with_fallback(temperature=0.2)
        prompt_template = load_prompt("risk_assessor.txt")
        if strategy == "stuff":
            # Single analysis with full content (no truncation for stuff strategy)
            doc_for_llm = full_content
            findings = await _analyze_chunk(
                llm, prompt_template, doc_for_llm, regulation_context, doc_type, ""
            )
        else:
            # Map-Reduce: analyze each chunk
            chunks = chunk_document(full_content)
            logger.info("Map-Reduce: analyzing %d chunks", len(chunks))
            all_findings = []
            for chunk in chunks:
                chunk_findings = await _analyze_chunk(
                    llm, prompt_template, chunk.content, regulation_context, doc_type,
                    chunk.section_path,
                )
                all_findings.extend(chunk_findings)

            # Deduplicate findings across chunks
            findings = deduplicate_findings(all_findings)
            logger.info("Map-Reduce: %d raw findings → %d after dedup", len(all_findings), len(findings))
    except Exception as e:
        logger.warning("Risk Assessor LLM call failed: %s, using empty findings", e)
        return {
            "findings": [],
            "risk_score": 0,
            "risk_level": "not_assessed",
            "risk_assessed": True,
            "status": "running",
            "messages": [f"Risk Assessor: LLM failed ({e}), no findings generated"],
        }

    if not findings:
        logger.warning("Risk Assessor: no findings generated")
        return {
            "findings": [],
            "risk_score": 0,
            "risk_level": "not_assessed",
            "risk_assessed": True,
            "status": "running",
            "messages": ["Risk Assessor: no findings identified"],
        }

    # Ensure each finding has required fields
    findings = _ensure_finding_defaults(findings)

    # Calculate risk score
    risk_score, risk_level = calculate_risk_score(findings)

    logger.info("Risk Assessor: %d findings, score=%d, level=%s", len(findings), risk_score, risk_level)

    return {
        "findings": findings,
        "risk_score": risk_score,
        "risk_level": risk_level,
        "risk_assessed": True,
        "messages": [
            f"Risk Assessor: identified {len(findings)} findings ({strategy})",
            f"Risk score: {risk_score}/100, level: {risk_level}",
        ],
    }
