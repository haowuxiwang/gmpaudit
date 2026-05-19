"""Shared JSON parsing utilities for LLM output."""

import json
import logging
import re

logger = logging.getLogger(__name__)

_TRAILING_COMMA_RE = re.compile(r",\s*([\]}])")


def _try_parse(text: str):
    """Try parsing JSON, first directly then with trailing comma removal."""
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    # LLMs often output trailing commas: {"a": 1,} or [1, 2,]
    cleaned = _TRAILING_COMMA_RE.sub(r"\1", text)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        return None


def parse_llm_json(content: str) -> list[dict]:
    """Robustly parse JSON from LLM output."""
    content = re.sub(r"```json\s*", "", content)
    content = re.sub(r"```\s*", "", content)
    content = content.strip()

    result = _try_parse(content)
    if result is not None:
        return result if isinstance(result, list) else [result]

    for pattern in [r"\[.*\]", r"\{.*\}"]:
        match = re.search(pattern, content, re.DOTALL)
        if match:
            result = _try_parse(match.group())
            if result is not None:
                return result if isinstance(result, list) else [result]

    logger.warning("Failed to parse JSON from LLM output (length=%d): %.200s", len(content), content)
    return []
