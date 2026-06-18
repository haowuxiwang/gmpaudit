"""Tests for agent/tools/prompt_loader.py — file loading, caching, missing files."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from agent.tools.prompt_loader import load_prompt, _prompt_cache


class TestLoadPrompt:
    def setup_method(self):
        _prompt_cache.clear()

    def teardown_method(self):
        _prompt_cache.clear()

    def test_loads_real_prompt_file(self):
        """Should load an existing prompt file from prompts/ directory."""
        result = load_prompt("regulation_expert.txt")
        assert isinstance(result, str)
        assert len(result) > 0

    def test_caches_result(self):
        """Second call should return cached value without reading file."""
        result1 = load_prompt("regulation_expert.txt")
        result2 = load_prompt("regulation_expert.txt")
        assert result1 is result2  # same object reference = cached

    def test_different_files_cached_separately(self):
        """Different filenames should have separate cache entries."""
        result1 = load_prompt("regulation_expert.txt")
        result2 = load_prompt("risk_assessor.txt")
        assert result1 is not result2
        assert "regulation_expert.txt" in _prompt_cache
        assert "risk_assessor.txt" in _prompt_cache

    def test_missing_file_raises(self):
        """Loading a nonexistent file should raise FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            load_prompt("nonexistent_prompt_xyz.txt")

    def test_import_error_fallback_path(self, tmp_path):
        """When app.core.paths import fails, use fallback path resolution."""
        _prompt_cache.clear()

        # Create a prompt file in the expected fallback location
        prompts_dir = Path(__file__).parent.parent / "prompts"
        test_file = prompts_dir / "_test_fake_prompt.txt"
        try:
            test_file.write_text("Fake prompt content for testing", encoding="utf-8")

            with patch.dict("sys.modules", {"app": None, "app.core": None, "app.core.paths": None}):
                result = load_prompt("_test_fake_prompt.txt")

            assert result == "Fake prompt content for testing"
        finally:
            test_file.unlink(missing_ok=True)

    def test_loads_all_existing_prompts(self):
        """All three existing prompt files should be loadable."""
        for name in ("regulation_expert.txt", "risk_assessor.txt", "report_writer.txt"):
            result = load_prompt(name)
            assert isinstance(result, str)
            assert len(result) > 10  # should have substantial content

    def test_agent_dir_import_path(self, tmp_path):
        """When app.core.paths is importable, AGENT_DIR path should be used."""
        _prompt_cache.clear()
        prompts_dir = tmp_path / "prompts"
        prompts_dir.mkdir()
        (prompts_dir / "_test_agent_dir.txt").write_text("Agent dir prompt content", encoding="utf-8")

        mock_paths = MagicMock()
        mock_paths.AGENT_DIR = tmp_path

        with patch.dict("sys.modules", {"app": MagicMock(), "app.core": MagicMock(), "app.core.paths": mock_paths}):
            result = load_prompt("_test_agent_dir.txt")

        assert result == "Agent dir prompt content"
