"""Document parsers for different file formats.

Provides a unified parse_file() entry point that dispatches
to format-specific parsers based on file extension.
"""

from pathlib import Path

from .pdf_parser import parse_pdf
from .docx_parser import parse_docx
from .text_parser import parse_text


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
    """
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    suffix = path.suffix.lower()

    if suffix == ".pdf":
        return parse_pdf(path)
    elif suffix == ".docx":
        return parse_docx(path)
    elif suffix in (".txt", ".md", ".text"):
        return parse_text(path)
    else:
        raise ValueError(f"Unsupported file format: {suffix}")
