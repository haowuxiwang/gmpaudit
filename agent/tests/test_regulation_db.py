"""Tests for agent/tools/regulation_db.py — tokenization, search, edge cases."""

import builtins
from unittest.mock import patch

from agent.tools.regulation_db import (
    GMP_REGULATIONS,
    _tokenize_chinese,
    search_regulations,
)


class TestTokenizeChinese:
    def test_with_jieba(self):
        """jieba tokenization returns meaningful tokens."""
        tokens = _tokenize_chinese("偏差处理程序是否符合GMP要求")
        assert len(tokens) > 0
        assert all(isinstance(t, str) for t in tokens)
        # All tokens should be > 1 char (filtered)
        assert all(len(t) > 1 for t in tokens)

    def test_single_char_filtered(self):
        """Single character tokens should be filtered out."""
        tokens = _tokenize_chinese("的了吗呢")
        # These are common single-char stop words in Chinese
        # After filtering len > 1, they should all be gone
        assert all(len(t) > 1 for t in tokens)

    def test_fallback_without_jieba(self, monkeypatch):
        """When jieba is not available, falls back to bigrams."""
        real_import = builtins.__import__

        def mock_import(name, *args, **kwargs):
            if name == "jieba":
                raise ImportError("mocked jieba not installed")
            return real_import(name, *args, **kwargs)

        monkeypatch.setattr(builtins, "__import__", mock_import)
        tokens = _tokenize_chinese("偏差处理程序")
        assert len(tokens) > 0
        assert all(len(t) > 1 for t in tokens)

    def test_fallback_english_words(self, monkeypatch):
        """Fallback should handle English words with bigrams."""
        real_import = builtins.__import__

        def mock_import(name, *args, **kwargs):
            if name == "jieba":
                raise ImportError("no jieba")
            return real_import(name, *args, **kwargs)

        monkeypatch.setattr(builtins, "__import__", mock_import)
        tokens = _tokenize_chinese("hello world test")
        assert len(tokens) > 0

    def test_fallback_short_word_filtered(self, monkeypatch):
        """Single-char words in fallback mode should be filtered."""
        real_import = builtins.__import__

        def mock_import(name, *args, **kwargs):
            if name == "jieba":
                raise ImportError("no jieba")
            return real_import(name, *args, **kwargs)

        monkeypatch.setattr(builtins, "__import__", mock_import)
        tokens = _tokenize_chinese("a b c")
        # All single-char, should return empty
        assert tokens == []


class TestSearchRegulations:
    def test_keyword_match(self):
        """Single keyword returns matching regulations."""
        results = search_regulations("偏差处理")
        assert len(results) > 0
        titles = [r["title"] for r in results]
        assert "偏差处理" in titles

    def test_multiple_keywords(self):
        """Multiple keywords with relevance scoring."""
        results = search_regulations("变更 控制 系统")
        assert len(results) > 0
        assert "变更" in results[0]["title"] or "变更" in results[0]["content"]

    def test_no_match(self):
        """Non-matching query returns empty list."""
        results = search_regulations("qwertyuiopasdfghjkl")
        assert results == []

    def test_n_results_limit(self):
        """Respects n_results parameter."""
        results = search_regulations("质量", n_results=2)
        assert len(results) <= 2

    def test_empty_query(self):
        """Empty query returns empty list (no keywords to match)."""
        results = search_regulations("")
        assert results == []

    def test_single_char_keywords_ignored(self):
        """Single character keywords are filtered out."""
        results = search_regulations("的")
        assert results == []

    def test_case_insensitive(self):
        """Search is case insensitive (for English content)."""
        results_lower = search_regulations("capa")
        results_upper = search_regulations("CAPA")
        assert len(results_lower) == len(results_upper)

    def test_returns_regulation_structure(self):
        """Returned results have expected fields."""
        results = search_regulations("偏差")
        assert len(results) > 0
        reg = results[0]
        assert "regulation" in reg
        assert "chapter" in reg
        assert "article" in reg
        assert "title" in reg
        assert "content" in reg

    def test_max_n_results(self):
        """Requesting more results than available returns all matches."""
        results = search_regulations("质量", n_results=100)
        assert len(results) <= len(GMP_REGULATIONS)

    def test_score_ordering(self):
        """Results should be ordered by score (most relevant first)."""
        # "偏差" should match deviation regulation strongly
        results = search_regulations("偏差处理程序调查")
        if len(results) >= 2:
            # First result should be more relevant
            assert results[0]["title"] == "偏差处理"

    def test_english_keyword_match(self):
        """English keywords should also match (CAPA, FMEA, etc.)."""
        results = search_regulations("CAPA")
        assert len(results) > 0
        content_texts = [r["content"] for r in results]
        assert any("CAPA" in c for c in content_texts)

    def test_ich_regulations_searchable(self):
        """ICH Q9/Q10 regulations should be searchable."""
        results = search_regulations("FMEA")
        assert len(results) > 0
        assert any("ICH" in r.get("regulation", "") for r in results)
