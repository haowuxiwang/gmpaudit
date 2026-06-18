"""Shared prompt template loader with module-level caching.

Reads prompt files from agent/prompts/ directory. Caches results
in memory so repeated calls don't hit disk.
"""

from pathlib import Path

_prompt_cache: dict[str, str] = {}


def load_prompt(filename: str) -> str:
    """Load a prompt template file by name (e.g. 'regulation_expert.txt').

    Uses module-level cache so the file is read at most once per process.
    """
    if filename not in _prompt_cache:
        try:
            from app.core.paths import AGENT_DIR

            prompt_path = AGENT_DIR / "prompts" / filename
        except ImportError:
            prompt_path = Path(__file__).parent.parent / "prompts" / filename
        _prompt_cache[filename] = prompt_path.read_text(encoding="utf-8")
    return _prompt_cache[filename]
