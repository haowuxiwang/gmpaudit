"""LightRAG-based knowledge graph for GMP regulation retrieval.

LightRAG-based knowledge graph for GMP regulation retrieval.
Uses local BAAI/bge-large-zh-v1.5 for embeddings and the project's
LLM provider for entity extraction and querying.
"""

import asyncio
import contextlib
import hashlib
import logging
import os
import shutil
import time
from pathlib import Path

import httpx

logger = logging.getLogger(__name__)

# Module-level httpx client for LLM calls (reused across LightRAG operations)
_llm_client: httpx.AsyncClient | None = None
_llm_client_lock = asyncio.Lock()


async def _get_llm_client() -> httpx.AsyncClient:
    """Get or create a singleton httpx.AsyncClient for LLM calls."""
    global _llm_client
    if _llm_client is None or _llm_client.is_closed:
        async with _llm_client_lock:
            if _llm_client is None or _llm_client.is_closed:
                _llm_client = httpx.AsyncClient(timeout=180)
    return _llm_client


try:
    from app.core import paths as _paths

    INPUT_DIR = _paths.KG_INPUT_DIR
    WORKING_DIR = _paths.KG_OUTPUT_DIR
    MODEL_DIR = _paths.MODEL_DIR
except ImportError:
    # Standalone mode (agent CLI without backend)
    _PROJECT_ROOT = Path(__file__).parent.parent.parent
    INPUT_DIR = _PROJECT_ROOT / "data" / "kg_input"
    WORKING_DIR = _PROJECT_ROOT / "data" / "kg_output"
    MODEL_DIR = Path(os.getenv("EMBEDDING_MODEL_PATH", str(_PROJECT_ROOT / "model")))

# Module-level singleton for embedding model
_embedding_model = None
_embedding_lock = asyncio.Lock()


def _get_embedding_func():
    """Create embedding function using local BAAI/bge-large-zh-v1.5 model."""
    from lightrag.utils import EmbeddingFunc

    async def embed(texts: list[str]) -> list[list[float]]:
        global _embedding_model
        if _embedding_model is None:
            async with _embedding_lock:
                if _embedding_model is None:
                    from sentence_transformers import SentenceTransformer

                    logger.info("Loading embedding model from %s", MODEL_DIR)
                    _embedding_model = SentenceTransformer(str(MODEL_DIR), device="cpu")
        import numpy as np

        loop = asyncio.get_running_loop()
        embeddings = await loop.run_in_executor(None, lambda: _embedding_model.encode(texts, normalize_embeddings=True))
        return np.array(embeddings)

    return EmbeddingFunc(
        embedding_dim=1024,
        func=embed,
        max_token_size=512,
    )


def _get_llm_func():
    """Create LLM function using the project's configured provider via OpenAI API.

    Integrates with the agent trace system for observability.
    Enforces Chinese output for entity extraction tasks.
    """
    from agent.trace import LLMTraceEvent, get_current_trace, now_ms

    # System prompt to enforce Chinese output for GMP domain
    _CHINESE_SYSTEM_PROMPT = """你是一个专业的药品生产质量管理规范（GMP）法规专家。
重要要求：
1. 所有实体名称必须使用中文表述（如"质量保证体系"而非"Quality Assurance System"）
2. 所有关系描述必须使用中文
3. 不要将中文术语翻译为英文，保持原文的中文表述
4. 实体类型使用中文（如"法规"、"条款"、"概念"、"流程"等）"""

    async def llm_complete(
        prompt: str,
        system_prompt: str = None,
        history_messages: list = None,
        **kwargs,
    ) -> str:
        from agent.config import LLMAuthError, get_default_provider, get_llm_config

        # Inject Chinese system prompt for entity extraction tasks
        is_extraction = "entity" in prompt.lower() and "relationship" in prompt.lower()
        if is_extraction:
            system_prompt = _CHINESE_SYSTEM_PROMPT + (f"\n\n{system_prompt}" if system_prompt else "")

        provider = get_default_provider()
        trace = get_current_trace()
        t0 = now_ms()
        total_retries = 0

        # Anthropic uses a different API format — delegate to LangChain adapter
        if provider == "anthropic":
            from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

            from agent.config import get_llm_with_fallback

            llm = get_llm_with_fallback(temperature=0.3)
            lc_messages = []
            if system_prompt:
                lc_messages.append(SystemMessage(content=system_prompt))
            if history_messages:
                for m in history_messages:
                    if m.get("role") == "user":
                        lc_messages.append(HumanMessage(content=m["content"]))
                    elif m.get("role") == "assistant":
                        lc_messages.append(AIMessage(content=m["content"]))
            lc_messages.append(HumanMessage(content=prompt))
            try:
                resp = await llm.ainvoke(lc_messages)
                latency = now_ms() - t0
                if trace:
                    trace.llm_events.append(
                        LLMTraceEvent(
                            provider="anthropic",
                            model=getattr(llm, "_model", "unknown"),
                            node="lightrag",
                            prompt_length=len(prompt),
                            prompt_preview=prompt[:200],
                            response_length=len(resp.content),
                            latency_ms=round(latency, 1),
                            success=True,
                        )
                    )
                return resp.content
            except Exception as e:
                latency = now_ms() - t0
                if trace:
                    trace.llm_events.append(
                        LLMTraceEvent(
                            provider="anthropic",
                            model=getattr(llm, "_model", "unknown"),
                            node="lightrag",
                            prompt_length=len(prompt),
                            prompt_preview=prompt[:200],
                            response_length=0,
                            latency_ms=round(latency, 1),
                            success=False,
                            error=str(e)[:500],
                        )
                    )
                raise

        config = get_llm_config()

        # Ensure model name is not empty (fallback to provider default)
        if not config.get("model"):
            from agent.config import MODEL_ENDPOINTS

            config["model"] = MODEL_ENDPOINTS.get(provider, {}).get("default_model", "mimo-v2.5-pro")
            logger.warning("LLM model name was empty, falling back to default: %s", config["model"])

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        if history_messages:
            messages.extend(history_messages)
        messages.append({"role": "user", "content": prompt})

        headers = {"Content-Type": "application/json"}
        if config.get("api_key"):
            headers["Authorization"] = f"Bearer {config['api_key']}"

        base_url = config.get("base_url", "https://api.xiaomimimo.com/v1").rstrip("/")
        url = f"{base_url}/chat/completions"
        model_name = config.get("model", "mimo-v2.5-pro")

        client = await _get_llm_client()
        for _attempt in range(3):
            try:
                resp = await client.post(
                    url,
                    json={
                        "model": model_name,
                        "messages": messages,
                        "temperature": 0.3,
                        "max_tokens": kwargs.get("max_tokens", 4096),
                    },
                    headers=headers,
                )
                resp.raise_for_status()
                data = resp.json()
                msg = data["choices"][0]["message"]
                content = msg.get("content", "")
                # Reasoning models (DeepSeek-R1, etc.) put output in reasoning_content
                if not content:
                    reasoning = msg.get("reasoning_content", "")
                    if reasoning:
                        content = reasoning
                        logger.info("Recovered %d chars from reasoning_content (raw HTTP, model=%s)", len(reasoning), model_name)
                latency = now_ms() - t0
                if trace:
                    trace.llm_events.append(
                        LLMTraceEvent(
                            provider=provider,
                            model=model_name,
                            node="lightrag",
                            prompt_length=len(prompt),
                            prompt_preview=prompt[:200],
                            response_length=len(content),
                            latency_ms=round(latency, 1),
                            success=True,
                            retry_count=total_retries,
                        )
                    )
                return content
            except httpx.HTTPStatusError as e:
                total_retries = _attempt
                resp_body = ""
                with contextlib.suppress(Exception):
                    resp_body = e.response.text[:500]
                total_chars = sum(len(m.get("content", "")) for m in messages)
                logger.error(
                    "LLM HTTP %d (attempt %d/3): %s | model=%s msgs=%d chars=%d max_tokens=%d | body: %s",
                    e.response.status_code,
                    _attempt + 1,
                    url,
                    model_name,
                    len(messages),
                    total_chars,
                    kwargs.get("max_tokens", 4096),
                    resp_body,
                )
                # Auth errors: wrap with LLMAuthError for consistent handling
                if e.response.status_code in (401, 403):
                    latency = now_ms() - t0
                    if trace:
                        trace.llm_events.append(
                            LLMTraceEvent(
                                provider=provider,
                                model=model_name,
                                node="lightrag",
                                prompt_length=len(prompt),
                                prompt_preview=prompt[:200],
                                response_length=0,
                                latency_ms=round(latency, 1),
                                success=False,
                                error=f"HTTP {e.response.status_code}",
                                retry_count=total_retries,
                            )
                        )
                    raise LLMAuthError(provider, str(e)) from e
                if e.response.status_code in (429, 500, 502, 503, 504) and _attempt < 2:
                    await asyncio.sleep(2**_attempt)
                    continue
                # Non-retryable error
                latency = now_ms() - t0
                if trace:
                    trace.llm_events.append(
                        LLMTraceEvent(
                            provider=provider,
                            model=model_name,
                            node="lightrag",
                            prompt_length=len(prompt),
                            prompt_preview=prompt[:200],
                            response_length=0,
                            latency_ms=round(latency, 1),
                            success=False,
                            error=f"HTTP {e.response.status_code}",
                            retry_count=total_retries,
                        )
                    )
                raise
            except (httpx.TimeoutException, httpx.ConnectError) as e:
                total_retries = _attempt
                if _attempt < 2:
                    await asyncio.sleep(2**_attempt)
                    continue
                latency = now_ms() - t0
                if trace:
                    trace.llm_events.append(
                        LLMTraceEvent(
                            provider=provider,
                            model=model_name,
                            node="lightrag",
                            prompt_length=len(prompt),
                            prompt_preview=prompt[:200],
                            response_length=0,
                            latency_ms=round(latency, 1),
                            success=False,
                            error=str(e)[:500],
                            retry_count=total_retries,
                        )
                    )
                raise

    return llm_complete


_lightrag_instance = None
_lightrag_lock = asyncio.Lock()


async def get_lightrag():
    """Get or create the LightRAG singleton instance."""
    global _lightrag_instance
    if _lightrag_instance is not None:
        return _lightrag_instance

    async with _lightrag_lock:
        if _lightrag_instance is not None:
            return _lightrag_instance

        from lightrag import LightRAG

        WORKING_DIR.mkdir(parents=True, exist_ok=True)

        rag = LightRAG(
            working_dir=str(WORKING_DIR),
            embedding_func=_get_embedding_func(),
            llm_model_func=_get_llm_func(),
            chunk_token_size=1200,
            chunk_overlap_token_size=100,
        )
        await rag.initialize_storages()
        _lightrag_instance = rag
        logger.info("LightRAG initialized, working_dir=%s", WORKING_DIR)
        return rag


def reset_lightrag():
    """Reset the LightRAG singleton instance."""
    global _lightrag_instance
    _lightrag_instance = None


async def build_index(force_rebuild: bool = False):
    """Build the knowledge graph index from regulation documents in input/ directory.

    Args:
        force_rebuild: If True, clear existing index and rebuild from scratch.
    """
    if not INPUT_DIR.is_dir():
        raise FileNotFoundError(f"Input directory not found: {INPUT_DIR}")

    txt_files = sorted(list(INPUT_DIR.glob("*.txt")) + list(INPUT_DIR.glob("*.md")))
    if not txt_files:
        raise FileNotFoundError(f"No .txt or .md files found in {INPUT_DIR}")

    if force_rebuild:
        logger.info("Force rebuild: clearing existing index at %s", WORKING_DIR)
        if WORKING_DIR.exists():
            shutil.rmtree(WORKING_DIR)
        reset_lightrag()

    rag = await get_lightrag()

    for f in txt_files:
        content = f.read_text(encoding="utf-8")
        if not content.strip():
            logger.warning("Skipping empty file: %s", f.name)
            continue
        logger.info("Indexing: %s (%d chars)", f.name, len(content))
        await rag.ainsert(content, ids=[f.name])
        logger.info("Done: %s", f.name)

    logger.info("Index build complete: %d documents indexed", len(txt_files))


# ---------------------------------------------------------------------------
# Query result cache (LRU with TTL)
# ---------------------------------------------------------------------------

_QUERY_CACHE_MAX_SIZE = 100
_QUERY_CACHE_TTL = 3600  # 1 hour in seconds
_query_cache: dict[str, tuple[list[dict], float]] = {}
_cache_hits = 0
_cache_misses = 0


def _cache_key(query: str, method: str) -> str:
    return hashlib.md5(f"{method}:{query}".encode()).hexdigest()


def _get_cached(query: str, method: str) -> list[dict] | None:
    global _cache_hits
    key = _cache_key(query, method)
    entry = _query_cache.get(key)
    if entry is None:
        return None
    result, ts = entry
    if time.time() - ts > _QUERY_CACHE_TTL:
        _query_cache.pop(key, None)
        return None
    _cache_hits += 1
    return result


def _set_cached(query: str, method: str, result: list[dict]) -> None:
    global _query_cache
    key = _cache_key(query, method)
    # Evict oldest if at capacity
    if len(_query_cache) >= _QUERY_CACHE_MAX_SIZE:
        oldest_key = min(_query_cache, key=lambda k: _query_cache[k][1])
        del _query_cache[oldest_key]
    _query_cache[key] = (result, time.time())


def get_cache_stats() -> dict:
    """Return cache statistics for monitoring."""
    total = _cache_hits + _cache_misses
    return {
        "size": len(_query_cache),
        "max_size": _QUERY_CACHE_MAX_SIZE,
        "hits": _cache_hits,
        "misses": _cache_misses,
        "hit_rate": f"{_cache_hits / total * 100:.1f}%" if total > 0 else "N/A",
    }


def _extract_title(content: str, query: str) -> str:
    """Extract a meaningful title from search result content."""
    # Try first line if it looks like a heading (short, no period)
    first_line = content.split("\n")[0].strip()
    if first_line and len(first_line) <= 80 and not first_line.endswith(("。", "，", "；")):
        return first_line[:80]
    # Fall back to first sentence
    for sep in ("。", "；", "\n"):
        idx = content.find(sep)
        if 0 < idx <= 60:
            return content[:idx].strip()
    # Truncate
    return content[:60].strip() + ("..." if len(content) > 60 else "")


def _extract_keywords_locally(query: str) -> tuple[list[str], list[str]]:
    """Extract high-level and low-level keywords from query using jieba, skipping LLM call.

    Returns (hl_keywords, ll_keywords) for LightRAG QueryParam.
    """
    try:
        import jieba
        words = [w.strip() for w in jieba.cut(query) if len(w.strip()) > 1]
    except ImportError:
        # Fallback: split on whitespace and punctuation
        import re
        words = [w.strip() for w in re.split(r'[\s，。；、]+', query) if len(w.strip()) > 1]

    if not words:
        return [query], [query]

    # hl_keywords = longer phrases (2-3 words), ll_keywords = individual terms
    hl_keywords = list(dict.fromkeys(words))[:5]  # deduplicated, max 5
    ll_keywords = [w for w in words if len(w) >= 2][:8]  # meaningful terms, max 8

    return hl_keywords or [query], ll_keywords or [query]


async def lightrag_search(query: str, method: str = "local") -> list[dict]:
    """Search GMP regulations using LightRAG knowledge graph.

    Args:
        query: Search query about GMP regulations
        method: "local" for specific search, "global" for overview

    Returns:
        List of regulation dicts with title, content, relevance
    """
    global _cache_misses

    # Check cache first
    cached = _get_cached(query, method)
    if cached is not None:
        logger.debug("LightRAG cache hit for query: %s...", query[:50])
        return cached

    _cache_misses += 1
    try:
        from lightrag.base import QueryParam

        rag = await get_lightrag()
        # Use "mix" mode by default (combines local + global graph traversal)
        mode = method if method in ("local", "global", "naive", "mix", "hybrid") else "mix"

        # Pre-extract keywords locally to skip LightRAG's LLM-based keyword extraction (saves 3-8s)
        hl_keywords, ll_keywords = _extract_keywords_locally(query)

        param = QueryParam(
            mode=mode,
            top_k=10,
            chunk_top_k=10,
            enable_rerank=True,
            hl_keywords=hl_keywords,
            ll_keywords=ll_keywords,
        )
        result = await asyncio.wait_for(
            rag.aquery(query, param=param),
            timeout=120,
        )

        if not result or not result.strip():
            _set_cached(query, method, [])
            return []

        # Return as single coherent result (LightRAG returns synthesized text, not a list)
        results = [
            {
                "regulation": "GMP法规知识库",
                "chapter": f"查询: {query[:40]}",
                "title": _extract_title(result, query),
                "content": result,
                "relevance": "知识图谱语义匹配",
            }
        ]
        _set_cached(query, method, results)
        return results
    except Exception as e:
        # Let LLMAuthError propagate immediately — don't mask API key failures
        from agent.config import LLMAuthError
        if isinstance(e, LLMAuthError):
            raise
        logger.warning("LightRAG search failed: %s", e)
        raise


async def preload_embedding_model():
    """Preload the embedding model to avoid cold start delay."""
    global _embedding_model
    if _embedding_model is not None:
        return

    async with _embedding_lock:
        if _embedding_model is not None:
            return
        try:
            from sentence_transformers import SentenceTransformer

            logger.info("Preloading embedding model from %s", MODEL_DIR)
            loop = asyncio.get_running_loop()
            _embedding_model = await loop.run_in_executor(
                None, lambda: SentenceTransformer(str(MODEL_DIR), device="cpu")
            )
            logger.info("Embedding model preloaded successfully")
        except Exception as e:
            logger.warning("Failed to preload embedding model: %s", e)
