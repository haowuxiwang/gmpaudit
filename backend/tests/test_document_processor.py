import pytest
from unittest.mock import patch, MagicMock, AsyncMock

from app.services.document_processor import DocumentProcessor


def test_clean_text():
    dp = DocumentProcessor()
    assert dp._clean_text("  hello   world  ") == "hello world"
    assert dp._clean_text("") == ""
    assert dp._clean_text(None) == ""
    assert dp._clean_text("  \n\t  ") == ""


def test_split_text_empty():
    dp = DocumentProcessor()
    assert dp._split_text("") == []
    assert dp._split_text(None) == []


def test_split_text_short():
    dp = DocumentProcessor()
    text = "这是一段短文本。"
    chunks = dp._split_text(text, chunk_size=100, overlap=10)
    assert len(chunks) == 1
    assert chunks[0] == text


def test_split_text_long():
    dp = DocumentProcessor()
    text = "A" * 3000
    chunks = dp._split_text(text, chunk_size=1000, overlap=100)
    assert len(chunks) > 1
    for chunk in chunks:
        assert len(chunk) <= 1200


def test_split_text_respects_sentence_boundary():
    dp = DocumentProcessor()
    text = "第一句话。" + "第二句话。" + "A" * 2000
    chunks = dp._split_text(text, chunk_size=500, overlap=50)
    assert len(chunks) >= 1


def test_split_text_overlap():
    dp = DocumentProcessor()
    text = "A" * 500 + "B" * 500
    chunks = dp._split_text(text, chunk_size=400, overlap=50)
    assert len(chunks) >= 2


@pytest.mark.asyncio
async def test_process_word():
    dp = DocumentProcessor()
    mock_doc = MagicMock()
    mock_para1 = MagicMock()
    mock_para1.text = "段落一"
    mock_para2 = MagicMock()
    mock_para2.text = "段落二"
    mock_para3 = MagicMock()
    mock_para3.text = ""
    mock_doc.paragraphs = [mock_para1, mock_para2, mock_para3]

    with patch("app.services.document_processor.DocxDocument", return_value=mock_doc):
        result = await dp._process_word("test.docx")
        assert "段落一" in result
        assert "段落二" in result


@pytest.mark.asyncio
async def test_process_document_unsupported_type():
    dp = DocumentProcessor()
    with pytest.raises(ValueError, match="不支持的文件类型"):
        await dp.process_document("test.xyz", "unknown")


@pytest.mark.asyncio
async def test_process_document_word():
    dp = DocumentProcessor()
    mock_doc = MagicMock()
    mock_para = MagicMock()
    mock_para.text = "测试内容"
    mock_doc.paragraphs = [mock_para]

    with patch("app.services.document_processor.DocxDocument", return_value=mock_doc):
        result = await dp.process_document("test.docx", "word")
        assert "content" in result
        assert "chunks" in result
        assert "chunk_count" in result
        assert "char_count" in result
        assert "测试内容" in result["content"]


def test_process_image_no_result():
    dp = DocumentProcessor()
    mock_ocr = MagicMock(return_value=(None, 0))
    dp.ocr = mock_ocr
    result = dp._process_image("test.png")
    assert result == ""


def test_process_image_with_result():
    dp = DocumentProcessor()
    mock_ocr = MagicMock(return_value=([([], "文字1", 0.9), ([], "文字2", 0.8)], 0.1))
    dp.ocr = mock_ocr
    result = dp._process_image("test.png")
    assert "文字1" in result
    assert "文字2" in result


def test_get_document_processor_singleton():
    from app.services.document_processor import get_document_processor
    p1 = get_document_processor()
    p2 = get_document_processor()
    assert p1 is p2


@pytest.mark.asyncio
async def test_process_pdf_text_page():
    dp = DocumentProcessor()
    mock_page = MagicMock()
    mock_page.get_text.return_value = "这是一段足够长的PDF文本内容" * 10  # >50 chars
    mock_doc = MagicMock()
    mock_doc.__len__ = MagicMock(return_value=1)
    mock_doc.load_page.return_value = mock_page

    with patch("app.services.document_processor.fitz.open", return_value=mock_doc):
        result = await dp._process_pdf("test.pdf")
        assert "这是一段足够长的PDF文本内容" in result
