"""Audit memory accumulation via JSONL file.

Persists audit findings to a JSONL file for cross-audit knowledge reference.
Each line is a JSON object with task_id, task_name, timestamp, findings, and documents.
"""

import asyncio
import json
import logging
from datetime import UTC, datetime
from pathlib import Path

from app.core import paths

logger = logging.getLogger(__name__)

MEMORY_FILE: Path = paths.DATA_DIR / "audit_memory.jsonl"


def _append_sync(entry: dict) -> None:
    """Synchronous file append (runs in thread pool)."""
    with open(MEMORY_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


async def append_findings(
    task_id: int,
    task_name: str,
    findings: list[dict],
    document_results: list[dict],
) -> None:
    """Append audit findings to JSONL memory file (async-safe)."""
    entry = {
        "task_id": task_id,
        "task_name": task_name,
        "timestamp": datetime.now(UTC).isoformat(),
        "findings_count": len(findings),
        "findings": findings,
        "documents": [d.get("filename", "") for d in document_results],
        "risk_levels": {d.get("filename", ""): d.get("risk_level", "unknown") for d in document_results},
    }
    try:
        await asyncio.to_thread(_append_sync, entry)
        logger.info("Appended %d findings to audit memory", len(findings))
    except Exception:
        logger.exception("Failed to append to audit memory")


def _load_sync(limit: int) -> list[dict]:
    """Synchronous file load (runs in thread pool)."""
    if not MEMORY_FILE.exists():
        return []
    entries: list[dict] = []
    with open(MEMORY_FILE, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                entries.append(json.loads(line))
    return entries[-limit:]


async def load_memory(limit: int = 100) -> list[dict]:
    """Load recent audit memory entries from JSONL file (async-safe)."""
    try:
        return await asyncio.to_thread(_load_sync, limit)
    except Exception:
        logger.exception("Failed to load audit memory")
        return []
