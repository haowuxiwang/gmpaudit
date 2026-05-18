"""LightRAG-based knowledge graph for GMP regulation retrieval.

LightRAG-based knowledge graph for GMP regulation retrieval.
Uses local BAAI/bge-large-zh-v1.5 for embeddings and the project's
LLM provider for entity extraction and querying.
"""

import asyncio
import logging
import os
import shutil
from pathlib import Path

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).parent.parent.parent
INPUT_DIR = PROJECT_ROOT / "graphrag_index" / "input"
WORKING_DIR = PROJECT_ROOT / "graphrag_index" / "lightrag_output"
MODEL_DIR = Path(os.getenv("EMBEDDING_MODEL_PATH", str(PROJECT_ROOT / "model")))

# Module-level singleton for embedding model
_embedding_model = None


def _get_embedding_func():
    """Create embedding function using local BAAI/bge-large-zh-v1.5 model."""
    from lightrag.utils import EmbeddingFunc

    async def embed(texts: list[str]) -> list[list[float]]:
        global _embedding_model
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
    import httpx

    async def llm_complete(
        prompt: str,
        system_prompt: str = None,
        history_messages: list = None,
        **kwargs,
    ) -> str:
        from agent.config import get_llm_config
        config = get_llm_config()

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

        async with httpx.AsyncClient(timeout=180) as client:
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

    txt_files = sorted(INPUT_DIR.glob("*.txt"))
    if not txt_files:
        raise FileNotFoundError(f"No .txt files found in {INPUT_DIR}")

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


async def lightrag_search(query: str, method: str = "local") -> list[dict]:
    """Search GMP regulations using LightRAG knowledge graph.

    Args:
        query: Search query about GMP regulations
        method: "local" for specific search, "global" for overview

    Returns:
        List of regulation dicts with title, content, relevance
    """
    try:
        from lightrag.base import QueryParam
        rag = await get_lightrag()
        mode = "local" if method == "local" else "global"
        result = await rag.aquery(query, param=QueryParam(mode=mode))

        if not result or not result.strip():
            return []

        # Split result into multiple entries if it contains multiple paragraphs
        paragraphs = [p.strip() for p in result.split('\n\n') if p.strip()]

        if len(paragraphs) <= 1:
            # Single result
            return [
                {
                    "regulation": "GMP法规知识库",
                    "chapter": "LightRAG检索",
                    "title": f"关于'{query[:30]}...'的检索结果",
                    "content": result,
                    "relevance": "知识图谱语义匹配",
                }
            ]

        # Multiple results
        results = []
        for i, para in enumerate(paragraphs[:5]):  # Limit to 5 results
            results.append({
                "regulation": "GMP法规知识库",
                "chapter": f"相关段落 {i + 1}",
                "title": f"关于'{query[:30]}...'的检索结果",
                "content": para,
                "relevance": "知识图谱语义匹配",
            })
        return results
    except Exception as e:
        logger.warning("LightRAG search failed: %s", e)
        raise


async def preload_embedding_model():
    """Preload the embedding model to avoid cold start delay."""
    global _embedding_model
    if _embedding_model is not None:
        return

    try:
        from sentence_transformers import SentenceTransformer
        logger.info("Preloading embedding model from %s", MODEL_DIR)
        _embedding_model = SentenceTransformer(str(MODEL_DIR), device="cpu")
        logger.info("Embedding model preloaded successfully")
    except Exception as e:
        logger.warning("Failed to preload embedding model: %s", e)
