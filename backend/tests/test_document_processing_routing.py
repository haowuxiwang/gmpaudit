"""Tests verifying each file_type routes to the correct processor method."""

import pytest
from unittest.mock import patch, MagicMock, AsyncMock

from app.services.document_processor import DocumentProcessor


@pytest.mark.asyncio
async def test_pdf_routes_to_pymupdf():
    dp = DocumentProcessor()
    mock_page = MagicMock()
    mock_page.get_text.return_value = "PDF text content " * 10
    mock_doc = MagicMock()
    mock_doc.__len__ = MagicMock(return_value=1)
    mock_doc.load_page.return_value = mock_page
    mock_doc.__enter__ = MagicMock(return_value=mock_doc)
    mock_doc.__exit__ = MagicMock(return_value=False)

    with patch("app.services.document_processor.fitz.open", return_value=mock_doc):
        result = await dp.process_document("test.pdf", "pdf")
        assert result["content"] != ""
        assert result["chunk_count"] > 0


@pytest.mark.asyncio
async def test_word_routes_to_mammoth():
    dp = DocumentProcessor()
    mock_result = MagicMock()
    mock_result.value = "Word document content"

    with patch("builtins.open", MagicMock()), \
         patch("app.services.document_processor.mammoth") as mock_mammoth:
        mock_mammoth.extract_raw_text.return_value = mock_result
        result = await dp.process_document("test.docx", "word")
        assert "Word document content" in result["content"]
        assert result["char_count"] > 0


@pytest.mark.asyncio
async def test_word_legacy_routes_to_antiword():
    dp = DocumentProcessor()
    mock_completed = MagicMock()
    mock_completed.returncode = 0
    mock_completed.stdout = "Legacy doc content from antiword"
    mock_completed.stderr = ""

    with patch("app.services.document_processor.subprocess.run", return_value=mock_completed) as mock_run:
        result = await dp.process_document("test.doc", "word_legacy")
        assert "Legacy doc content from antiword" in result["content"]
        mock_run.assert_called_once()
        args = mock_run.call_args
        assert "antiword" in args[0][0]


@pytest.mark.asyncio
async def test_text_routes_to_file_read():
    dp = DocumentProcessor()
    mock_file = MagicMock()
    mock_file.__enter__ = MagicMock(return_value=mock_file)
    mock_file.__exit__ = MagicMock(return_value=False)
    mock_file.read.return_value = "Text file content"

    with patch("builtins.open", return_value=mock_file):
        result = await dp.process_document("test.txt", "text")
        assert "Text file content" in result["content"]


@pytest.mark.asyncio
async def test_image_routes_to_ocr():
    dp = DocumentProcessor()
    mock_ocr = MagicMock(return_value=([([], "OCR text", 0.9)], 0.1))
    dp.ocr = mock_ocr

    result = await dp.process_document("test.png", "image")
    assert "OCR text" in result["content"]


@pytest.mark.asyncio
async def test_unknown_type_raises_valueerror():
    dp = DocumentProcessor()
    with pytest.raises(ValueError, match="不支持的文件类型"):
        await dp.process_document("test.xyz", "unknown")
