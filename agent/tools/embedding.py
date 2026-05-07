"""Embedding tool using local BAAI/bge-large-zh-v1.5 model.

Uses sentence-transformers for local inference — no API calls needed.
"""

import logging
from typing import List
from pathlib import Path

logger = logging.getLogger(__name__)

_model = None
_MODEL_DIR = Path(__file__).parent.parent.parent / "model"


def _get_model():
    """Lazy-load the sentence-transformers model."""
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer
        logger.info(f"Loading local embedding model from {_MODEL_DIR}")
        _model = SentenceTransformer(str(_MODEL_DIR))
        logger.info(f"Embedding model loaded, dim={_model.get_sentence_embedding_dimension()}")
    return _model


def embed_texts(texts: List[str]) -> List[List[float]]:
    """Embed a list of texts using local BGE model.

    Args:
        texts: List of text strings to embed

    Returns:
        List of embedding vectors
    """
    model = _get_model()
    embeddings = model.encode(texts, normalize_embeddings=True)
    logger.info(f"Embedded {len(texts)} texts, dim={len(embeddings[0]) if len(embeddings) > 0 else 0}")
    return embeddings.tolist()


def embed_query(query: str) -> List[float]:
    """Embed a single query string.

    Args:
        query: Query text to embed

    Returns:
        Embedding vector as list of floats
    """
    embeddings = embed_texts([query])
    return embeddings[0]


class SiliconFlowEmbeddingFunction:
    """Embedding function compatible with GraphRAG/LanceDB.

    Kept for interface compatibility — now uses local model.
    """

    def __call__(self, texts: List[str]) -> List[List[float]]:
        """Embed texts and return as list of lists."""
        return embed_texts(texts)


if __name__ == "__main__":
    test_texts = ["GMP合规性审计", "偏差处理流程", "变更控制管理"]
    try:
        embeddings = embed_texts(test_texts)
        print(f"Embedded {len(test_texts)} texts")
        print(f"Embedding dimension: {len(embeddings[0])}")
        print(f"First embedding (first 5 dims): {embeddings[0][:5]}")
    except Exception as e:
        print(f"Error: {e}")
