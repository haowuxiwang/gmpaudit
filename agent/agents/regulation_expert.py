"""GMP Regulation Expert Agent.

Queries regulation knowledge base (LightRAG or fallback DB)
to find relevant GMP clauses for the document.
"""

import logging
from pathlib import Path

from agent.config import get_llm, call_llm_with_retry
from agent.tools.json_parser import parse_llm_json as _parse_llm_json

logger = logging.getLogger(__name__)
from agent.state import AuditState
from agent.tools.regulation_db import search_regulations


def _load_prompt() -> str:
    prompt_path = Path(__file__).parent.parent / "prompts" / "regulation_expert.txt"
    return prompt_path.read_text(encoding="utf-8")


async def regulation_expert_node(state: AuditState) -> dict:
    """Find relevant GMP regulations for the document.

    Uses LightRAG knowledge graph, falls back to hardcoded regulation DB.
    Then uses LLM to summarize relevance.
    """
    full_content = state.get("document_content", "")
    doc_type = state.get("document_type", "unknown")
    if len(full_content) > 3000:
        logger.warning("Document content truncated from %d to 3000 chars for %s", len(full_content), state.get("document_name", "unknown"))
    doc_content = full_content[:3000]
    logger.info(f"Regulation Expert: analyzing doc_type={doc_type}, content_len={len(doc_content)}")

    # Step 1: Search regulation database
    # Try LightRAG first, fall back to hardcoded DB
    reg_results = []
    source = "fallback DB"
    try:
        from agent.tools.lightrag_tool import lightrag_search
        reg_results = await lightrag_search(doc_content)
        if reg_results:
            source = "LightRAG"
        else:
            logger.info("LightRAG returned empty results, using fallback regulation DB")
            keywords = f"{doc_type} 偏差 变更 CAPA 文件管理 设备维护"
            reg_results = search_regulations(keywords, n_results=5)
    except Exception as e:
        logger.info(f"LightRAG unavailable ({e}), using fallback regulation DB")
        keywords = f"{doc_type} 偏差 变更 CAPA 文件管理 设备维护"
        reg_results = search_regulations(keywords, n_results=5)

    # Step 2: Use LLM to analyze document against regulations
    try:
        llm = get_llm(provider=None, temperature=0.2)
        prompt_template = _load_prompt()
        prompt = prompt_template.format(document_content=doc_content)

        response = await call_llm_with_retry(llm, prompt)
        llm_analysis = _parse_llm_json(response.content)
    except Exception as e:
        logger.warning(f"Regulation Expert LLM call failed: {e}, using fallback")
        summary_lines = [f"Regulation analysis ({source}, LLM failed):"]
        for reg in reg_results[:5]:
            title = reg.get("title", reg.get("article", "N/A"))
            reg_name = reg.get("regulation", "Unknown")
            summary_lines.append(f"- {reg_name}: {title}")
        return {
            "matched_regulations": reg_results,
            "regulation_summary": "\n".join(summary_lines),
            "regulation_checked": True,
            "status": "running",
            "messages": [f"Regulation Expert: LLM failed, used {len(reg_results)} clauses from {source}"],
        }

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

    logger.info(f"Regulation Expert: found {len(matched)} clauses from {source}")
    return {
        "matched_regulations": matched,
        "regulation_summary": "\n".join(summary_lines),
        "regulation_checked": True,
        "messages": [f"Regulation Expert: found {len(matched)} relevant clauses ({source})"],
    }
