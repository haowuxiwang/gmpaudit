"""GMP Regulation Expert Agent.

Queries regulation knowledge base (LightRAG or fallback DB)
to find relevant GMP clauses for the document.

Supports two strategies based on document size:
- Stuff: single LLM call for documents ≤ STUFF_LIMIT
- Map-Reduce: chunked analysis for larger documents
"""

import asyncio
import hashlib
import logging
import time

from agent.config import get_llm_with_fallback, call_llm_with_retry, MAX_DOCUMENT_CHARS, STUFF_LIMIT, LLMAuthError
from agent.tools.document_chunker import select_strategy, chunk_document, deduplicate_findings
from agent.tools.json_parser import parse_llm_json as _parse_llm_json
from agent.tools.prompt_loader import load_prompt

logger = logging.getLogger(__name__)
from agent.state import AuditState

# LLM response cache for regulation_expert (avoids re-analyzing same document)
_LLM_CACHE_MAX_SIZE = 50
_LLM_CACHE_TTL = 1800  # 30 minutes
_llm_cache: dict[str, tuple[dict, float]] = {}


def _llm_cache_key(content: str, doc_type: str) -> str:
    return hashlib.md5(f"{doc_type}:{content}".encode()).hexdigest()


def _get_llm_cached(content: str, doc_type: str) -> dict | None:
    key = _llm_cache_key(content, doc_type)
    entry = _llm_cache.get(key)
    if entry is None:
        return None
    result, ts = entry
    if time.time() - ts > _LLM_CACHE_TTL:
        _llm_cache.pop(key, None)
        return None
    logger.debug("LLM cache hit for regulation_expert (doc_type=%s)", doc_type)
    return result


def _set_llm_cached(content: str, doc_type: str, result: dict) -> None:
    key = _llm_cache_key(content, doc_type)
    if len(_llm_cache) >= _LLM_CACHE_MAX_SIZE:
        oldest_key = min(_llm_cache, key=lambda k: _llm_cache[k][1])
        del _llm_cache[oldest_key]
    _llm_cache[key] = (result, time.time())


def clear_llm_cache() -> None:
    """Clear the regulation expert LLM response cache."""
    _llm_cache.clear()
from agent.tools.regulation_db import search_regulations


async def _search_regulations(query: str) -> tuple[list[dict], str]:
    """Search regulations via LightRAG, fall back to DB.

    Returns:
        Tuple of (results, source) where source indicates which backend was used.
    """
    from agent.trace import get_current_trace, KGTraceEvent, now_ms

    trace = get_current_trace()
    t0 = now_ms()

    try:
        from agent.tools.lightrag_tool import lightrag_search
        results = await lightrag_search(query)
        latency = now_ms() - t0
        if results:
            if trace:
                trace.kg_events.append(KGTraceEvent(
                    source="lightrag",
                    query=query[:200],
                    result_count=len(results),
                    latency_ms=round(latency, 1),
                ))
            return results, "lightrag"
        # LightRAG returned empty — still record it
        if trace:
            trace.kg_events.append(KGTraceEvent(
                source="lightrag",
                query=query[:200],
                result_count=0,
                latency_ms=round(latency, 1),
            ))
    except Exception as e:
        latency = now_ms() - t0
        if trace:
            trace.kg_events.append(KGTraceEvent(
                source="lightrag_failed",
                query=query[:200],
                result_count=0,
                latency_ms=round(latency, 1),
                error=str(e)[:500],
            ))
        logger.info("LightRAG unavailable (%s), using fallback DB", e)

    # Fallback
    t1 = now_ms()
    keywords = "偏差 变更 CAPA 文件管理 设备维护"
    fb_results = search_regulations(keywords, n_results=5)
    fb_latency = now_ms() - t1
    if trace:
        trace.kg_events.append(KGTraceEvent(
            source="fallback_db",
            query=keywords,
            result_count=len(fb_results),
            latency_ms=round(fb_latency, 1),
        ))
    return fb_results, "fallback_db"


def _deduplicate_regulations(regs: list[dict]) -> list[dict]:
    """Deduplicate regulations by title."""
    seen = set()
    unique = []
    for reg in regs:
        key = reg.get("title", "") or reg.get("content", "")[:50]
        if key not in seen:
            seen.add(key)
            unique.append(reg)
    return unique


async def regulation_expert_node(state: AuditState) -> dict:
    """Find relevant GMP regulations for the document.

    Uses LightRAG knowledge graph, falls back to hardcoded regulation DB.
    Then uses LLM to summarize relevance.

    Strategy selection:
    - Stuff (≤STUFF_LIMIT): single LLM call with full content
    - Map-Reduce (>STUFF_LIMIT): chunk → per-chunk KG query → aggregate
    """
    full_content = state.get("document_content", "")
    doc_type = state.get("document_type", "unknown")
    doc_name = state.get("document_name", "unknown")

    # Check LLM response cache
    cached = _get_llm_cached(full_content, doc_type)
    if cached is not None:
        logger.info("Regulation Expert: cache hit for doc_type=%s", doc_type)
        return cached

    strategy = select_strategy(full_content)

    logger.info("Regulation Expert: doc_type=%s, content_len=%d, strategy=%s",
                doc_type, len(full_content), strategy)

    # Step 1: Search regulation database
    if strategy == "stuff":
        # Single query with content summary (first 2000 chars)
        reg_results, source = await _search_regulations(full_content[:2000])
    else:
        # Map-Reduce: query KG per chunk in parallel for better coverage
        chunks = chunk_document(full_content)
        logger.info("Map-Reduce: %d chunks, querying KG per chunk (parallel)", len(chunks))
        tasks = [_search_regulations(chunk.content[:500]) for chunk in chunks]
        results_list = await asyncio.gather(*tasks)
        all_regs = []
        for chunk_regs, _ in results_list:
            all_regs.extend(chunk_regs)
        reg_results = _deduplicate_regulations(all_regs)
        source = "lightrag_multi" if reg_results else "fallback_db"

    if not reg_results:
        keywords = f"{doc_type} 偏差 变更 CAPA 文件管理 设备维护"
        reg_results = search_regulations(keywords, n_results=5)
        source = "fallback_db"

    # Step 2: Use LLM to analyze document against regulations
    # For stuff strategy, use full content; for map_reduce, use a summary
    if strategy == "stuff":
        doc_for_llm = full_content[:MAX_DOCUMENT_CHARS] if len(full_content) > MAX_DOCUMENT_CHARS else full_content
    else:
        # For map-reduce, send first chunk + summary of rest
        chunks = chunk_document(full_content)
        doc_for_llm = chunks[0].content
        if len(chunks) > 1:
            doc_for_llm += f"\n\n[... 文档共 {len(chunks)} 个章节，以下为其余章节摘要 ...]"
            for chunk in chunks[1:4]:  # Include up to 3 more chunk summaries
                doc_for_llm += f"\n\n## {chunk.section_path}\n{chunk.content[:300]}..."

    try:
        llm = get_llm_with_fallback(temperature=0.2)
        prompt_template = load_prompt("regulation_expert.txt")
        prompt = prompt_template.format(document_content=doc_for_llm)

        response = await call_llm_with_retry(llm, prompt, node="regulation_expert")
        llm_analysis = _parse_llm_json(response.content)
    except LLMAuthError as e:
        logger.warning("Regulation Expert auth error: %s, using fallback", e)
        summary_lines = [f"Regulation analysis ({source}, LLM auth error):"]
        for reg in reg_results[:5]:
            title = reg.get("title", reg.get("article", "N/A"))
            reg_name = reg.get("regulation", "Unknown")
            summary_lines.append(f"- {reg_name}: {title}")
        return {
            "matched_regulations": reg_results,
            "regulation_summary": "\n".join(summary_lines),
            "regulation_checked": True,
            "status": "running",
            "messages": [f"Regulation Expert: {e.user_message}, used {len(reg_results)} clauses from {source}"],
        }
    except Exception as e:
        logger.warning("Regulation Expert LLM call failed: %s, using fallback", e)
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
    summary_lines = [f"Regulation analysis ({source}, strategy={strategy}):"]
    for reg in matched[:5]:
        title = reg.get("title", reg.get("article", "N/A"))
        reg_name = reg.get("regulation", "Unknown")
        summary_lines.append(f"- {reg_name}: {title}")

    logger.info("Regulation Expert: found %d clauses from %s (%s)", len(matched), source, strategy)
    result = {
        "matched_regulations": matched,
        "regulation_summary": "\n".join(summary_lines),
        "regulation_checked": True,
        "messages": [f"Regulation Expert: found {len(matched)} relevant clauses ({source}, {strategy})"],
    }
    _set_llm_cached(full_content, doc_type, result)
    return result
