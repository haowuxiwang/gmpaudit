"""GMP Regulation Expert Agent.

Queries regulation knowledge base (GraphRAG or fallback DB)
to find relevant GMP clauses for the document.
"""

import json
import re
from pathlib import Path

from agent.config import get_llm
from agent.state import AuditState
from agent.tools.regulation_db import search_regulations


def _load_prompt() -> str:
    prompt_path = Path(__file__).parent.parent / "prompts" / "regulation_expert.txt"
    return prompt_path.read_text(encoding="utf-8")


def _parse_llm_json(content: str) -> list[dict]:
    """Robustly parse JSON from LLM output."""
    # Remove markdown code block markers
    content = re.sub(r"```json\s*", "", content)
    content = re.sub(r"```\s*", "", content)
    content = content.strip()

    try:
        result = json.loads(content)
        return result if isinstance(result, list) else [result]
    except json.JSONDecodeError:
        pass

    # Try to extract JSON array from text
    for pattern in [r"\[.*\]", r"\{.*\}"]:
        match = re.search(pattern, content, re.DOTALL)
        if match:
            try:
                result = json.loads(match.group())
                return result if isinstance(result, list) else [result]
            except json.JSONDecodeError:
                continue

    return []


async def regulation_expert_node(state: AuditState) -> dict:
    """Find relevant GMP regulations for the document.

    Uses fallback regulation DB (Phase 2) or GraphRAG (Phase 3).
    Then uses LLM to summarize relevance.
    """
    doc_content = state.get("document_content", "")[:3000]
    doc_type = state.get("document_type", "unknown")

    # Step 1: Search regulation database
    # Try GraphRAG first, fall back to hardcoded DB
    try:
        from agent.tools.graphrag_tool import graphrag_search
        reg_results = await graphrag_search(doc_content)
        source = "GraphRAG"
    except (ImportError, Exception):
        # Fallback: keyword search in hardcoded regulations
        keywords = f"{doc_type} 偏差 变更 CAPA 文件管理 设备维护"
        reg_results = search_regulations(keywords, n_results=5)
        source = "fallback DB"

    # Step 2: Use LLM to analyze document against regulations
    try:
        llm = get_llm(provider=None, temperature=0.2)
        prompt_template = _load_prompt()
        prompt = prompt_template.format(document_content=doc_content)

        response = await llm.ainvoke(prompt)
        llm_analysis = _parse_llm_json(response.content)
    except Exception as e:
        llm_analysis = []
        # Continue with fallback results even if LLM fails

    # Merge results: LLM analysis takes priority, supplement with DB results
    if llm_analysis:
        matched = llm_analysis
    else:
        matched = reg_results

    # Generate summary
    summary_lines = [f"Regulation analysis ({source}):"]
    for reg in matched[:5]:
        title = reg.get("title", reg.get("article", "N/A"))
        reg_name = reg.get("regulation", "Unknown")
        summary_lines.append(f"- {reg_name}: {title}")

    return {
        "matched_regulations": matched,
        "regulation_summary": "\n".join(summary_lines),
        "messages": [f"Regulation Expert: found {len(matched)} relevant clauses ({source})"],
    }
