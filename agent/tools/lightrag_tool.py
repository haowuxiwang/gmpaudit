"""LightRAG-based knowledge graph for GMP regulation retrieval.

LightRAG-based knowledge graph for GMP regulation retrieval.
Uses local BAAI/bge-large-zh-v1.5 for embeddings and the project's
LLM provider for entity extraction and querying.
"""

import asyncio
import hashlib
import logging
import os
import shutil
import threading
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
_embedding_lock = threading.Lock()


def _get_embedding_func():
    """Create embedding function using local BAAI/bge-large-zh-v1.5 model."""
    from lightrag.utils import EmbeddingFunc

    async def embed(texts: list[str]) -> list[list[float]]:
        global _embedding_model
        if _embedding_model is None:
            with _embedding_lock:
                if _embedding_model is None:
                    from sentence_transformers import SentenceTransformer
                    logger.info("Loading embedding model from %s", MODEL_DIR)
                    _embedding_model = SentenceTransformer(str(MODEL_DIR), device="cpu")
        import numpy as np
        embeddings = _embedding_model.encode(texts, normalize_embeddings=True)
        return np.array(embeddings)

    return EmbeddingFunc(
        embedding_dim=1024,
        func=embed,
        max_token_size=512,
    )


def _get_llm_func():
    """Create LLM function using the project's configured provider via OpenAI API."""

    async def llm_complete(
        prompt: str,
        system_prompt: str = None,
        history_messages: list = None,
        **kwargs,
    ) -> str:
        from agent.config import get_llm_config, get_default_provider

        # Anthropic uses a different API format — delegate to LangChain adapter
        if get_default_provider() == "anthropic":
            from agent.config import get_llm_with_fallback
            from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
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
            resp = await llm.ainvoke(lc_messages)
            return resp.content

        config = get_llm_config()

        # Ensure model name is not empty (fallback to provider default)
        if not config.get("model"):
            from agent.config import MODEL_ENDPOINTS
            provider = get_default_provider()
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

        client = await _get_llm_client()
        for _attempt in range(3):
            try:
                resp = await client.post(
                    url,
                    json={
                        "model": config.get("model", "mimo-v2.5-pro"),
                        "messages": messages,
                        "temperature": 0.3,
                        "max_tokens": kwargs.get("max_tokens", 4096),
                    },
                    headers=headers,
                )
                resp.raise_for_status()
                data = resp.json()
                return data["choices"][0]["message"]["content"]
            except httpx.HTTPStatusError as e:
                resp_body = ""
                try:
                    resp_body = e.response.text[:500]
                except Exception:
                    pass
                total_chars = sum(len(m.get("content", "")) for m in messages)
                logger.error(
                    "LLM HTTP %d (attempt %d/3): %s | model=%s msgs=%d chars=%d max_tokens=%d | body: %s",
                    e.response.status_code, _attempt + 1, url,
                    config.get("model"), len(messages), total_chars,
                    kwargs.get("max_tokens", 4096), resp_body,
                )
                if e.response.status_code in (429, 500, 502, 503, 504) and _attempt < 2:
                    await asyncio.sleep(2 ** _attempt)
                    continue
                raise
            except (httpx.TimeoutException, httpx.ConnectError):
                if _attempt < 2:
                    await asyncio.sleep(2 ** _attempt)
                    continue
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
            top_k=5,
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
    first_line = content.split('\n')[0].strip()
    if first_line and len(first_line) <= 80 and not first_line.endswith(('。', '，', '；')):
        return first_line[:80]
    # Fall back to first sentence
    for sep in ('。', '；', '\n'):
        idx = content.find(sep)
        if 0 < idx <= 60:
            return content[:idx].strip()
    # Truncate
    return content[:60].strip() + ('...' if len(content) > 60 else '')


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
        mode = "local" if method == "local" else "global"
        result = await rag.aquery(query, param=QueryParam(mode=mode))

        if not result or not result.strip():
            _set_cached(query, method, [])
            return []

        # Split result into multiple entries if it contains multiple paragraphs
        paragraphs = [p.strip() for p in result.split('\n\n') if p.strip()]

        if len(paragraphs) <= 1:
            # Single result
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

        # Multiple results
        results = []
        for i, para in enumerate(paragraphs[:5]):  # Limit to 5 results
            results.append({
                "regulation": "GMP法规知识库",
                "chapter": f"查询: {query[:40]}",
                "title": _extract_title(para, query),
                "content": para,
                "relevance": "知识图谱语义匹配",
            })
        _set_cached(query, method, results)
        return results
    except Exception as e:
        logger.warning("LightRAG search failed: %s", e)
        raise


async def preload_embedding_model():
    """Preload the embedding model to avoid cold start delay."""
    global _embedding_model
    if _embedding_model is not None:
        return

    with _embedding_lock:
        if _embedding_model is not None:
            return
        try:
            from sentence_transformers import SentenceTransformer
            logger.info("Preloading embedding model from %s", MODEL_DIR)
            _embedding_model = SentenceTransformer(str(MODEL_DIR), device="cpu")
            logger.info("Embedding model preloaded successfully")
        except Exception as e:
            logger.warning("Failed to preload embedding model: %s", e)
