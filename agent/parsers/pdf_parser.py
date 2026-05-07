"""PDF document parser using PyMuPDF."""

from pathlib import Path


def parse_pdf(file_path: Path) -> str:
    """Extract text from a PDF file.

    Args:
        file_path: Path to the PDF file

    Returns:
        Extracted text content
    """
    import pymupdf

    text_parts = []
    with pymupdf.open(str(file_path)) as doc:
        for page in doc:
            text_parts.append(page.get_text())

    return "\n".join(text_parts)
