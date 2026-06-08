"""Shared JSON parsing utilities for LLM output."""

import json
import logging
import re

logger = logging.getLogger(__name__)

_TRAILING_COMMA_RE = re.compile(r",\s*([\]}])")
_CONTROL_CHAR_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


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


def _clean_llm_output(content: str) -> str:
    """Clean LLM output to extract valid JSON."""
    # Remove markdown code blocks
    content = re.sub(r"```(?:json)?\s*", "", content)
    content = re.sub(r"```\s*", "", content)
    # Remove control characters (except \n and \t)
    content = _CONTROL_CHAR_RE.sub("", content)
    content = content.strip()
    return content


def _fix_common_json_errors(text: str) -> str:
    """Fix common JSON errors from LLM output."""
    # Remove single-line comments: // ... (but not inside strings like https://)
    # Only match // preceded by whitespace, comma, or line start (not inside URLs)
    text = re.sub(r"(?<=[:,\s])//[^\n]*", "", text)
    # Remove multi-line comments: /* ... */
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.DOTALL)
    # Replace structural single quotes with double quotes
    # Only match quotes that look like JSON delimiters (after {, ,, [ or before :, ,, ], })
    text = re.sub(r"(?<=[\[{,\s])'|'(?=[\]}:,\s])", '"', text)
    # Fix trailing commas
    text = _TRAILING_COMMA_RE.sub(r"\1", text)
    return text


def parse_llm_json(content: str) -> list[dict]:
    """Robustly parse JSON from LLM output."""
    content = _clean_llm_output(content)

    # Try direct parse
    result = _try_parse(content)
    if result is not None:
        return result if isinstance(result, list) else [result]

    # Try extracting JSON array or object with regex
    for pattern in [r"\[.*?\]", r"\{.*?\}"]:
        match = re.search(pattern, content, re.DOTALL)
        if match:
            result = _try_parse(match.group())
            if result is not None:
                return result if isinstance(result, list) else [result]

    # Try fixing common JSON errors
    fixed = _fix_common_json_errors(content)
    result = _try_parse(fixed)
    if result is not None:
        return result if isinstance(result, list) else [result]

    # Try extracting JSON from fixed content
    for pattern in [r"\[.*?\]", r"\{.*?\}"]:
        match = re.search(pattern, fixed, re.DOTALL)
        if match:
            result = _try_parse(match.group())
            if result is not None:
                return result if isinstance(result, list) else [result]

    logger.warning("Failed to parse JSON from LLM output (length=%d): %.200s", len(content), content)
    return []
