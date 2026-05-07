"""Plain text file parser."""

from pathlib import Path


def parse_text(file_path: Path) -> str:
    """Read a plain text file.

    Args:
        file_path: Path to the text file

    Returns:
        File content as string
    """
    return file_path.read_text(encoding="utf-8")
