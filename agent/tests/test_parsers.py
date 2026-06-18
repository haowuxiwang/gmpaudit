"""Tests for agent.parsers: parse_file dispatcher, parse_text encoding fallback,
parse_docx (mocked python-docx), parse_pdf (mocked PyMuPDF)."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from agent.parsers import parse_file
from agent.parsers.text_parser import parse_text


class TestParseText:
    def test_utf8_file(self, tmp_path):
        f = tmp_path / "test.txt"
        f.write_text("Hello world\n", encoding="utf-8")
        assert parse_text(f) == "Hello world\n"

    def test_chinese_content(self, tmp_path):
        f = tmp_path / "chinese.txt"
        content = "GMP偏差处理规范\n第二章 质量管理"
        f.write_text(content, encoding="utf-8")
        assert parse_text(f) == content

    def test_encoding_fallback_gb18030(self, tmp_path):
        f = tmp_path / "gb.txt"
        content = "测试内容"
        f.write_bytes(content.encode("gb18030"))
        assert parse_text(f) == content

    def test_encoding_fallback_gbk(self, tmp_path):
        f = tmp_path / "gbk.txt"
        content = "质量控制"
        f.write_bytes(content.encode("gbk"))
        assert parse_text(f) == content

    def test_empty_file(self, tmp_path):
        f = tmp_path / "empty.txt"
        f.write_text("", encoding="utf-8")
        assert parse_text(f) == ""

    def test_binary_garbage_falls_back(self, tmp_path):
        """Invalid bytes should fall back to replace mode."""
        f = tmp_path / "garbage.txt"
        f.write_bytes(b"\xff\xfe\x00\x01")
        result = parse_text(f)
        assert isinstance(result, str)  # should not raise


class TestParseFile:
    def test_txt_file(self, tmp_path):
        f = tmp_path / "sample.txt"
        f.write_text("Test content", encoding="utf-8")
        assert parse_file(str(f)) == "Test content"

    def test_md_file(self, tmp_path):
        f = tmp_path / "readme.md"
        f.write_text("# Title\n\nBody", encoding="utf-8")
        result = parse_file(str(f))
        assert "# Title" in result

    def test_text_extension(self, tmp_path):
        f = tmp_path / "data.text"
        f.write_text("text extension", encoding="utf-8")
        assert parse_file(str(f)) == "text extension"

    def test_unsupported_format_raises(self, tmp_path):
        f = tmp_path / "data.csv"
        f.write_text("a,b,c", encoding="utf-8")
        with pytest.raises(ValueError, match="Unsupported file format"):
            parse_file(str(f))

    def test_file_not_found_raises(self):
        with pytest.raises(FileNotFoundError):
            parse_file("/nonexistent/path/to/file.txt")

    def test_pdf_delegates_to_pdf_parser(self, tmp_path, monkeypatch):
        f = tmp_path / "test.pdf"
        f.write_bytes(b"%PDF-1.4 fake")

        called_with = {}

        def mock_parse_pdf(path):
            called_with["path"] = path
            return "pdf content"

        monkeypatch.setattr("agent.parsers.parse_pdf", mock_parse_pdf)
        result = parse_file(str(f))
        assert result == "pdf content"
        assert called_with["path"] == f

    def test_docx_delegates_to_docx_parser(self, tmp_path, monkeypatch):
        f = tmp_path / "test.docx"
        f.write_bytes(b"PK fake docx")

        called_with = {}

        def mock_parse_docx(path):
            called_with["path"] = path
            return "docx content"

        monkeypatch.setattr("agent.parsers.parse_docx", mock_parse_docx)
        result = parse_file(str(f))
        assert result == "docx content"
        assert called_with["path"] == f

    def test_pdf_parser_error_wrapped_as_value_error(self, tmp_path, monkeypatch):
        f = tmp_path / "corrupt.pdf"
        f.write_bytes(b"%PDF-1.4")

        def mock_parse_pdf(path):
            raise RuntimeError("corrupted file")

        monkeypatch.setattr("agent.parsers.parse_pdf", mock_parse_pdf)
        with pytest.raises(ValueError, match="Failed to parse .pdf file"):
            parse_file(str(f))

    def test_docx_parser_error_wrapped_as_value_error(self, tmp_path, monkeypatch):
        """DOCX parser errors should also be wrapped as ValueError."""
        f = tmp_path / "corrupt.docx"
        f.write_bytes(b"PK bad")

        def mock_parse_docx(path):
            raise RuntimeError("corrupted docx")

        monkeypatch.setattr("agent.parsers.parse_docx", mock_parse_docx)
        with pytest.raises(ValueError, match="Failed to parse .docx file"):
            parse_file(str(f))


# ---------------------------------------------------------------------------
# parse_docx — mock python-docx
# ---------------------------------------------------------------------------
class TestParseDocx:
    def _make_mock_docx_module(self, mock_doc):
        """Create a mock docx module with Document class."""
        mock_docx = MagicMock()
        mock_docx.Document.return_value = mock_doc
        return mock_docx

    def test_paragraphs_only(self, tmp_path):
        """Extract text from paragraphs."""
        from agent.parsers.docx_parser import parse_docx

        f = tmp_path / "test.docx"

        mock_para1 = MagicMock()
        mock_para1.text = "First paragraph"
        mock_para2 = MagicMock()
        mock_para2.text = "Second paragraph"
        mock_para_empty = MagicMock()
        mock_para_empty.text = "   "  # should be skipped

        mock_doc = MagicMock()
        mock_doc.paragraphs = [mock_para1, mock_para2, mock_para_empty]
        mock_doc.tables = []

        mock_docx = self._make_mock_docx_module(mock_doc)
        with patch.dict("sys.modules", {"docx": mock_docx}):
            result = parse_docx(f)

        assert "First paragraph" in result
        assert "Second paragraph" in result
        # Empty paragraph should be skipped
        lines = result.strip().split("\n")
        assert len(lines) == 2

    def test_tables_extracted(self, tmp_path):
        """Extract text from tables."""
        from agent.parsers.docx_parser import parse_docx

        f = tmp_path / "test.docx"

        # Mock table with one row, two cells
        mock_cell1 = MagicMock()
        mock_cell1.text = "Cell A"
        mock_cell2 = MagicMock()
        mock_cell2.text = "Cell B"

        mock_row = MagicMock()
        mock_row.cells = [mock_cell1, mock_cell2]

        mock_table = MagicMock()
        mock_table.rows = [mock_row]

        mock_doc = MagicMock()
        mock_doc.paragraphs = []
        mock_doc.tables = [mock_table]

        mock_docx = self._make_mock_docx_module(mock_doc)
        with patch.dict("sys.modules", {"docx": mock_docx}):
            result = parse_docx(f)

        assert "Cell A" in result
        assert "Cell B" in result
        assert " | " in result

    def test_mixed_paragraphs_and_tables(self, tmp_path):
        """Both paragraphs and tables should be extracted."""
        from agent.parsers.docx_parser import parse_docx

        f = tmp_path / "test.docx"

        mock_para = MagicMock()
        mock_para.text = "Document title"

        mock_cell = MagicMock()
        mock_cell.text = "Table data"
        mock_row = MagicMock()
        mock_row.cells = [mock_cell]
        mock_table = MagicMock()
        mock_table.rows = [mock_row]

        mock_doc = MagicMock()
        mock_doc.paragraphs = [mock_para]
        mock_doc.tables = [mock_table]

        mock_docx = self._make_mock_docx_module(mock_doc)
        with patch.dict("sys.modules", {"docx": mock_docx}):
            result = parse_docx(f)

        assert "Document title" in result
        assert "Table data" in result

    def test_empty_table_row_skipped(self, tmp_path):
        """Table rows with all empty cells should be skipped."""
        from agent.parsers.docx_parser import parse_docx

        f = tmp_path / "test.docx"

        mock_cell_empty = MagicMock()
        mock_cell_empty.text = "   "
        mock_row = MagicMock()
        mock_row.cells = [mock_cell_empty]
        mock_table = MagicMock()
        mock_table.rows = [mock_row]

        mock_doc = MagicMock()
        mock_doc.paragraphs = [MagicMock(text="Content")]
        mock_doc.tables = [mock_table]

        mock_docx = self._make_mock_docx_module(mock_doc)
        with patch.dict("sys.modules", {"docx": mock_docx}):
            result = parse_docx(f)

        # Only the paragraph should appear, not the empty table row
        assert "Content" in result


# ---------------------------------------------------------------------------
# parse_pdf — mock PyMuPDF
# ---------------------------------------------------------------------------
class TestParsePdf:
    def test_single_page(self, tmp_path):
        """Extract text from single page PDF."""
        from agent.parsers.pdf_parser import parse_pdf

        f = tmp_path / "test.pdf"

        mock_page = MagicMock()
        mock_page.get_text.return_value = "Page 1 content"

        mock_doc = MagicMock()
        mock_doc.__iter__ = MagicMock(return_value=iter([mock_page]))
        mock_doc.__enter__ = MagicMock(return_value=mock_doc)
        mock_doc.__exit__ = MagicMock(return_value=False)

        mock_pymupdf = MagicMock()
        mock_pymupdf.open.return_value = mock_doc

        with patch.dict("sys.modules", {"pymupdf": mock_pymupdf}):
            result = parse_pdf(f)

        assert result == "Page 1 content"

    def test_multi_page(self, tmp_path):
        """Extract text from multiple pages."""
        from agent.parsers.pdf_parser import parse_pdf

        f = tmp_path / "multi.pdf"

        mock_page1 = MagicMock()
        mock_page1.get_text.return_value = "Page 1"
        mock_page2 = MagicMock()
        mock_page2.get_text.return_value = "Page 2"
        mock_page3 = MagicMock()
        mock_page3.get_text.return_value = "Page 3"

        mock_doc = MagicMock()
        mock_doc.__iter__ = MagicMock(return_value=iter([mock_page1, mock_page2, mock_page3]))
        mock_doc.__enter__ = MagicMock(return_value=mock_doc)
        mock_doc.__exit__ = MagicMock(return_value=False)

        mock_pymupdf = MagicMock()
        mock_pymupdf.open.return_value = mock_doc

        with patch.dict("sys.modules", {"pymupdf": mock_pymupdf}):
            result = parse_pdf(f)

        assert "Page 1" in result
        assert "Page 2" in result
        assert "Page 3" in result

    def test_empty_pdf(self, tmp_path):
        """PDF with no pages returns empty string."""
        from agent.parsers.pdf_parser import parse_pdf

        f = tmp_path / "empty.pdf"

        mock_doc = MagicMock()
        mock_doc.__iter__ = MagicMock(return_value=iter([]))
        mock_doc.__enter__ = MagicMock(return_value=mock_doc)
        mock_doc.__exit__ = MagicMock(return_value=False)

        mock_pymupdf = MagicMock()
        mock_pymupdf.open.return_value = mock_doc

        with patch.dict("sys.modules", {"pymupdf": mock_pymupdf}):
            result = parse_pdf(f)

        assert result == ""

    def test_pdf_open_error_propagates(self, tmp_path):
        """Corrupted PDF raises exception from pymupdf."""
        from agent.parsers.pdf_parser import parse_pdf

        f = tmp_path / "bad.pdf"

        mock_pymupdf = MagicMock()
        mock_pymupdf.open.side_effect = RuntimeError("corrupted PDF")

        with patch.dict("sys.modules", {"pymupdf": mock_pymupdf}):
            with pytest.raises(RuntimeError, match="corrupted PDF"):
                parse_pdf(f)
