"""Plain text file parser."""

from pathlib import Path


def parse_text(file_path: Path) -> str:
    """Read a plain text file.

    Tries UTF-8 first, falls back to reading with replacement characters.

    Args:
        file_path: Path to the text file

    Returns:
        File content as string
    """
    for encoding in ("utf-8", "gb18030", "gbk"):
        try:
            return file_path.read_text(encoding=encoding)
        except UnicodeDecodeError:
            continue
    return file_path.read_text(encoding="utf-8", errors="replace")
