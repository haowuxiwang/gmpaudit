"""Tests for agent.tools.document_chunker."""

import pytest

from agent.tools.document_chunker import (
    DocumentChunk,
    _split_by_sentences,
    _split_by_sections,
    _split_content,
    _title_similarity,
    chunk_document,
    deduplicate_findings,
    select_strategy,
)


class TestSelectStrategy:
    def test_short_text_returns_stuff(self):
        assert select_strategy("short text") == "stuff"

    def test_exact_limit_returns_stuff(self, monkeypatch):
        monkeypatch.setattr("agent.tools.document_chunker.STUFF_LIMIT", 10)
        assert select_strategy("x" * 10) == "stuff"

    def test_over_limit_returns_map_reduce(self, monkeypatch):
        monkeypatch.setattr("agent.tools.document_chunker.STUFF_LIMIT", 10)
        assert select_strategy("x" * 11) == "map_reduce"

    def test_empty_text_returns_stuff(self):
        assert select_strategy("") == "stuff"


class TestChunkDocument:
    def test_empty_text(self):
        assert chunk_document("") == []

    def test_whitespace_only(self):
        assert chunk_document("   \n\n  ") == []

    def test_short_text_single_chunk(self):
        chunks = chunk_document("Hello world", max_chars=100)
        assert len(chunks) == 1
        assert chunks[0].content == "Hello world"
        assert chunks[0].chunk_index == 0
        assert chunks[0].char_count == 11

    def test_sections_detected(self):
        text = "Intro text\n\n一、First section\nContent A\n\n二、Second section\nContent B"
        chunks = chunk_document(text, max_chars=1000)
        section_paths = [c.section_path for c in chunks]
        assert any("一、" in p for p in section_paths)
        assert any("二、" in p for p in section_paths)

    def test_markdown_headings(self):
        text = "# Title\n\nBody here\n\n## Subtitle\n\nMore content"
        chunks = chunk_document(text, max_chars=1000)
        assert len(chunks) >= 2
        section_paths = [c.section_path for c in chunks]
        assert any("# Title" in p for p in section_paths)
        assert any("## Subtitle" in p for p in section_paths)

    def test_numbered_sections(self):
        text = "1. Introduction\nSome intro\n2. Methods\nSome methods"
        chunks = chunk_document(text, max_chars=1000)
        section_paths = [c.section_path for c in chunks]
        assert any("1." in p for p in section_paths)

    def test_no_heading_fallback(self):
        text = "Plain text with no headings at all."
        chunks = chunk_document(text, max_chars=100)
        assert len(chunks) == 1
        assert chunks[0].section_path == ""

    def test_long_content_splits_by_paragraph(self):
        para = "A" * 50
        text = para + "\n\n" + "B" * 50
        chunks = chunk_document(text, max_chars=60)
        assert len(chunks) == 2

    def test_oversized_paragraph_splits_by_sentence(self):
        from agent.tools.document_chunker import _split_by_sentences

        long = "Short. " * 200  # each "Short. " is 7 chars, total ~1400
        chunks = _split_by_sentences(long, max_chars=100)
        for c in chunks:
            assert len(c) <= 100

    def test_chunk_indices_sequential(self):
        text = "Para one.\n\nPara two.\n\nPara three."
        chunks = chunk_document(text, max_chars=20)
        for i, c in enumerate(chunks):
            assert c.chunk_index == i

    def test_gmp_heading_pattern(self):
        text = "第一章 总则\nContent here\n第二章 质量管理\nMore content"
        chunks = chunk_document(text, max_chars=1000)
        section_paths = [c.section_path for c in chunks]
        assert any("第一章" in p for p in section_paths)
        assert any("第二章" in p for p in section_paths)


class TestSplitBySections:
    def test_no_heading(self):
        result = _split_by_sections("Just plain text")
        assert len(result) == 1
        assert result[0][0] is None

    def test_chinese_heading(self):
        text = "一、General\nContent A\n\n二、Specific\nContent B"
        result = _split_by_sections(text)
        assert len(result) >= 2
        assert any("一、" in (r[0] or "") for r in result)

    def test_markdown_heading(self):
        text = "## Section One\nBody\n## Section Two\nMore"
        result = _split_by_sections(text)
        assert len(result) >= 2

    def test_pre_heading_content(self):
        text = "Preamble\n\n## Main\nBody"
        result = _split_by_sections(text)
        # First section should be preamble (no heading)
        assert result[0][0] is None


class TestSplitContent:
    def test_within_limit(self):
        result = _split_content("short text", max_chars=100)
        assert result == ["short text"]

    def test_oversized_paragraph(self):
        para = "X" * 200
        result = _split_content(para, max_chars=100)
        for chunk in result:
            assert len(chunk) <= 100

    def test_multiple_paragraphs(self):
        text = "Para one is long enough.\n\nPara two is also long enough.\n\nPara three is long enough too."
        result = _split_content(text, max_chars=30)
        assert len(result) >= 2


class TestSplitBySentences:
    def test_short_text(self):
        result = _split_by_sentences("Hello. World.", max_chars=100)
        assert len(result) >= 1

    def test_hard_truncate_long_sentence(self):
        long_sent = "A" * 200
        result = _split_by_sentences(long_sent, max_chars=50)
        assert result[0] == "A" * 50

    def test_chinese_sentences(self):
        text = "这是第一句话的内容。这是第二句话的内容！这是第三句话的内容？"
        result = _split_by_sentences(text, max_chars=10)
        assert len(result) >= 2


class TestDeduplicateFindings:
    def test_empty_list(self):
        assert deduplicate_findings([]) == []

    def test_no_duplicates(self):
        findings = [
            {"title": "Missing deviation record", "description": "A"},
            {"title": "Equipment calibration overdue", "description": "B"},
        ]
        result = deduplicate_findings(findings)
        assert len(result) == 2

    def test_exact_duplicate_keeps_longer(self):
        findings = [
            {"title": "Missing record", "description": "First"},
            {"title": "Missing record", "description": "Second"},
        ]
        result = deduplicate_findings(findings)
        assert len(result) == 1
        # Code keeps the one with longer description when titles match
        assert result[0]["description"] == "Second"

    def test_duplicate_keeps_longer_description(self):
        findings = [
            {"title": "Missing record", "description": "Short"},
            {"title": "Missing record", "description": "Much longer detailed description"},
        ]
        result = deduplicate_findings(findings)
        assert len(result) == 1
        assert result[0]["description"] == "Much longer detailed description"

    def test_similar_titles_deduped(self):
        # "Missing deviation record" vs "Missing deviation records" have ~96% bigram overlap
        findings = [
            {"title": "Missing deviation record", "description": "A"},
            {"title": "Missing deviation records", "description": "B"},
        ]
        result = deduplicate_findings(findings)
        assert len(result) == 1

    def test_different_titles_not_deduped(self):
        findings = [
            {"title": "Equipment calibration", "description": "A"},
            {"title": "Personnel training record", "description": "B"},
        ]
        result = deduplicate_findings(findings)
        assert len(result) == 2

    def test_finding_without_title(self):
        findings = [
            {"description": "No title here"},
            {"title": "Something", "description": "B"},
        ]
        result = deduplicate_findings(findings)
        assert len(result) == 2


class TestTitleSimilarity:
    def test_identical(self):
        assert _title_similarity("test", "test") == 1.0

    def test_completely_different(self):
        assert _title_similarity("abc", "xyz") == 0.0

    def test_empty_strings(self):
        assert _title_similarity("", "test") == 0.0
        assert _title_similarity("test", "") == 0.0
        assert _title_similarity("", "") == 0.0

    def test_chinese_bigram(self):
        # "偏差处理" bigrams: {偏差, 差处, 处理}
        # "偏差管理" bigrams: {偏差, 差管, 管理}
        # intersection: {偏差}, union: {偏差, 差处, 处理, 差管, 管理} => 1/5 = 0.2
        score = _title_similarity("偏差处理", "偏差管理")
        assert 0.0 < score < 1.0

    def test_partial_overlap(self):
        score = _title_similarity("hello world", "hello earth")
        assert 0.0 < score < 1.0

    def test_single_char_strings(self):
        assert _title_similarity("a", "a") == 0.0  # no bigrams possible
        assert _title_similarity("a", "b") == 0.0


class TestDocumentChunk:
    def test_post_init_sets_char_count(self):
        c = DocumentChunk(content="hello", section_path="test", chunk_index=0)
        assert c.char_count == 5

    def test_default_values(self):
        c = DocumentChunk(content="")
        assert c.section_path == ""
        assert c.chunk_index == 0
        assert c.char_count == 0


class TestChunkDocumentDefaults:
    """Test default max_chars behavior."""

    def test_zero_max_chars_uses_default(self):
        """max_chars=0 should use CHUNK_MAX_CHARS default."""
        text = "Short text"
        chunks = chunk_document(text, max_chars=0)
        assert len(chunks) == 1
        assert chunks[0].content == text

    def test_negative_max_chars_uses_default(self):
        """Negative max_chars should use CHUNK_MAX_CHARS default."""
        text = "Short text"
        chunks = chunk_document(text, max_chars=-5)
        assert len(chunks) == 1
        assert chunks[0].content == text


class TestSplitContentEdgeCases:
    """Test edge cases in _split_content for coverage gaps."""

    def test_empty_paragraph_skipped(self):
        """Whitespace-only paragraphs should be skipped in _split_content."""
        # Use a text that exceeds max_chars to enter the paragraph-split path,
        # with a whitespace-only paragraph between two content paragraphs.
        text = "A" * 80 + "\n\n   \t  \n\n" + "B" * 80
        result = _split_content(text, max_chars=100)
        # The whitespace-only paragraph should be skipped; two content paragraphs remain
        assert len(result) == 2
        assert "A" * 80 in result[0]
        assert "B" * 80 in result[1]

    def test_flush_current_before_oversized_paragraph(self):
        """Current chunk should be flushed before an oversized paragraph."""
        # Build: normal paragraph + oversized paragraph
        normal = "Short paragraph."
        oversized = "A" * 200
        text = normal + "\n\n" + oversized
        result = _split_content(text, max_chars=100)
        assert len(result) >= 2
        assert normal in result[0]

    def test_flush_current_before_oversized_sentence(self):
        """Current chunk should be flushed before an oversized sentence in _split_by_sentences."""
        # Build: normal sentence + oversized sentence within same paragraph
        normal = "Short sentence."
        oversized = "B" * 200
        text = normal + " " + oversized
        result = _split_by_sentences(text, max_chars=100)
        assert len(result) >= 2
        assert normal in result[0]
