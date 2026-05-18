"""Tests for agent/tools/regulation_db.py"""

from agent.tools.regulation_db import search_regulations


class TestSearchRegulations:
    """Test search_regulations function."""

    def test_keyword_match(self):
        """Single keyword returns matching regulations."""
        results = search_regulations("偏差处理")
        assert len(results) > 0
        # Should find the deviation handling regulation
        titles = [r["title"] for r in results]
        assert "偏差处理" in titles

    def test_multiple_keywords(self):
        """Multiple keywords with relevance scoring."""
        results = search_regulations("变更 控制 系统")
        assert len(results) > 0
        # First result should be most relevant (变更控制)
        assert "变更" in results[0]["title"] or "变更" in results[0]["content"]

    def test_no_match(self):
        """Non-matching query returns empty list."""
        results = search_regulations("xyz不存在的内容")
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
        # "的" is single char, should be ignored
        results = search_regulations("的")
        assert results == []

    def test_case_insensitive(self):
        """Search is case insensitive (for English content)."""
        results_lower = search_regulations("capa")
        results_upper = search_regulations("CAPA")
        # Both should find CAPA-related regulations
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
