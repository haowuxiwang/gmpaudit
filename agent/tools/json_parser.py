"""Shared JSON parsing utilities for LLM output."""

import json
import logging
import re

logger = logging.getLogger(__name__)


def parse_llm_json(content: str) -> list[dict]:
    """Robustly parse JSON from LLM output."""
    content = re.sub(r"```json\s*", "", content)
    content = re.sub(r"```\s*", "", content)
    content = content.strip()

    try:
        result = json.loads(content)
        return result if isinstance(result, list) else [result]
    except json.JSONDecodeError:
        pass

    for pattern in [r"\[.*\]", r"\{.*\}"]:
        match = re.search(pattern, content, re.DOTALL)
        if match:
            try:
                result = json.loads(match.group())
                return result if isinstance(result, list) else [result]
            except json.JSONDecodeError:
                continue

    logger.warning("Failed to parse JSON from LLM output (length=%d): %.200s", len(content), content)
    return []
