"""GraphRAG query tool for regulation knowledge retrieval.

Provides local_search and global_search functions that query
the GraphRAG index built from GMP regulation documents.
"""

import os
import subprocess
from pathlib import Path


GRAPHRAG_ROOT = Path(__file__).parent.parent.parent / "graphrag_index"


def _run_graphrag_query(query: str, method: str = "local") -> str:
    """Run a GraphRAG query via CLI.

    Args:
        query: The search query
        method: Search method - "local" or "global"

    Returns:
        Query result text
    """
    env = os.environ.copy()
    env["GRAPHRAG_API_KEY"] = os.getenv("SILICONFLOW_API_KEY", "")

    cmd = [
        "python", "-m", "graphrag", "query",
        "--root", str(GRAPHRAG_ROOT),
        "--method", method,
        "--query", query,
    ]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=120,
            env=env,
            cwd=str(GRAPHRAG_ROOT),
        )

        if result.returncode == 0:
            return result.stdout.strip()
        else:
            raise RuntimeError(f"GraphRAG query failed: {result.stderr}")
    except subprocess.TimeoutExpired:
        raise RuntimeError("GraphRAG query timed out")
    except Exception as e:
        raise RuntimeError(f"GraphRAG query error: {e}")


async def graphrag_search(query: str, method: str = "local") -> list[dict]:
    """Search GMP regulations using GraphRAG.

    Falls back to local search if global search fails.

    Args:
        query: Search query about GMP regulations
        method: "local" for specific clause search, "global" for overview

    Returns:
        List of regulation dicts with title, content, relevance
    """
    try:
        result = _run_graphrag_query(query, method)
    except Exception:
        # Try the other method as fallback
        fallback = "global" if method == "local" else "local"
        try:
            result = _run_graphrag_query(query, fallback)
        except Exception:
            return []

    # Parse the result into structured format
    # GraphRAG returns text, we wrap it in a standard format
    return [
        {
            "regulation": "GMP法规知识库",
            "chapter": "GraphRAG检索",
            "article": "",
            "title": f"关于'{query[:30]}...'的检索结果",
            "content": result[:500],
            "relevance": "GraphRAG知识图谱匹配",
        }
    ]
