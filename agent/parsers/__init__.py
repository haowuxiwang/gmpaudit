"""Document parsers for different file formats.

Provides a unified parse_file() entry point that dispatches
to format-specific parsers based on file extension.
"""

import logging
from pathlib import Path

from .docx_parser import parse_docx
from .pdf_parser import parse_pdf
from .text_parser import parse_text

logger = logging.getLogger(__name__)


def parse_file(file_path: str) -> str:
    """Parse a document file and return its text content.

    Supported formats: .pdf, .docx, .txt, .md

    Args:
        file_path: Path to the document file

    Returns:
        Extracted text content

    Raises:
        ValueError: If file format is not supported
        FileNotFoundError: If file does not exist
        ValueError: If file is corrupted or unreadable
    """
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    suffix = path.suffix.lower()

    try:
        if suffix == ".pdf":
            return parse_pdf(path)
        elif suffix == ".docx":
            return parse_docx(path)
        elif suffix in (".txt", ".md", ".text"):
            return parse_text(path)
        else:
            raise ValueError(f"Unsupported file format: {suffix}")
    except (FileNotFoundError, ValueError):
        raise
    except Exception as e:
        logger.error("Failed to parse %s file '%s': [%s] %s", suffix, file_path, type(e).__name__, e)
        raise ValueError(f"Failed to parse {suffix} file: {e}") from e
