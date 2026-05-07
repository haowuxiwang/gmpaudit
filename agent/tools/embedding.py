"""Embedding tool using SiliconFlow API.

Uses Qwen/Qwen3-Embedding-8B via SiliconFlow API for Chinese text embedding.
This is the fallback when local BGE model is not available.
"""

import os
from typing import List

import requests
from dotenv import load_dotenv
from pathlib import Path

# Load environment variables
_project_root = Path(__file__).parent.parent.parent
load_dotenv(_project_root / "config" / ".env")

SILICONFLOW_API_URL = "https://api.siliconflow.cn/v1/embeddings"
EMBEDDING_MODEL = "Qwen/Qwen3-Embedding-8B"


def _get_api_key() -> str:
    """Get SiliconFlow API key from environment."""
    api_key = os.getenv("SILICONFLOW_API_KEY", "")
    if not api_key:
        raise ValueError("SILICONFLOW_API_KEY not set in config/.env")
    return api_key


def embed_texts(texts: List[str]) -> List[List[float]]:
    """Embed a list of texts using SiliconFlow API.

    Args:
        texts: List of text strings to embed

    Returns:
        List of embedding vectors
    """
    api_key = _get_api_key()

    response = requests.post(
        SILICONFLOW_API_URL,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        },
        json={
            "model": EMBEDDING_MODEL,
            "input": texts
        },
        timeout=60
    )

    if response.status_code != 200:
        raise RuntimeError(f"Embedding API failed: {response.status_code} {response.text}")

    data = response.json()
    # Sort by index to maintain order
    embeddings = sorted(data["data"], key=lambda x: x["index"])
    return [item["embedding"] for item in embeddings]


def embed_query(query: str) -> List[float]:
    """Embed a single query string.

    Args:
        query: Query text to embed

    Returns:
        Embedding vector as list of floats
    """
    embeddings = embed_texts([query])
    return embeddings[0]


# For GraphRAG integration
class SiliconFlowEmbeddingFunction:
    """Embedding function compatible with GraphRAG/LanceDB."""

    def __call__(self, texts: List[str]) -> List[List[float]]:
        """Embed texts and return as list of lists."""
        return embed_texts(texts)


if __name__ == "__main__":
    # Test the embedding
    test_texts = ["GMP合规性审计", "偏差处理流程", "变更控制管理"]
    try:
        embeddings = embed_texts(test_texts)
        print(f"Embedded {len(test_texts)} texts")
        print(f"Embedding dimension: {len(embeddings[0])}")
        print(f"First embedding (first 5 dims): {embeddings[0][:5]}")
    except Exception as e:
        print(f"Error: {e}")
