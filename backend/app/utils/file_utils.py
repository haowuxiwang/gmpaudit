import os
from pathlib import Path

def get_file_type(filename: str) -> str:
    ext = Path(filename).suffix.lower()
    type_map = {
        '.pdf': 'pdf',
        '.docx': 'word',
        '.doc': 'word_legacy',
        '.txt': 'text',
        '.jpg': 'image',
        '.jpeg': 'image',
        '.png': 'image',
        '.tiff': 'image',
        '.bmp': 'image'
    }
    return type_map.get(ext, 'unknown')

def get_file_size(file_path: str) -> int:
    return os.path.getsize(file_path)
