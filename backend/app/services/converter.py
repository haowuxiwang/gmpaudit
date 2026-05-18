"""Document-to-Markdown converter using Microsoft markitdown."""

import asyncio
import os
import tempfile
import logging

logger = logging.getLogger(__name__)

_markitdown_instance = None


def _get_markitdown():
    global _markitdown_instance
    if _markitdown_instance is None:
        from markitdown import MarkItDown
        _markitdown_instance = MarkItDown()
    return _markitdown_instance


def _convert_sync(content: bytes, suffix: str) -> str:
    """Synchronous conversion: write bytes to temp file, convert, clean up."""
    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            tmp.write(content)
            tmp_path = tmp.name

        md = _get_markitdown()
        result = md.convert(tmp_path)
        return result.text_content
    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.remove(tmp_path)


async def convert_to_markdown(content: bytes, filename: str) -> str:
    """Convert PDF/DOCX content to Markdown using markitdown.

    Args:
        content: Raw file bytes.
        filename: Original filename (used to determine format via extension).

    Returns:
        Markdown text content.

    Raises:
        RuntimeError: If conversion fails.
    """
    suffix = os.path.splitext(filename)[1].lower()
    loop = asyncio.get_running_loop()
    try:
        return await loop.run_in_executor(None, _convert_sync, content, suffix)
    except Exception as exc:
        logger.error("markitdown conversion failed for %s: %s", filename, exc)
        raise RuntimeError(f"文档转换失败: {exc}") from exc
