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
    mock_result = MagicMock()
    mock_result.value = "段落一\n\n段落二"

    with patch("builtins.open", MagicMock()), \
         patch("app.services.document_processor.mammoth") as mock_mammoth:
        mock_mammoth.extract_raw_text.return_value = mock_result
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
    mock_result = MagicMock()
    mock_result.value = "测试内容"

    with patch("builtins.open", MagicMock()), \
         patch("app.services.document_processor.mammoth") as mock_mammoth:
        mock_mammoth.extract_raw_text.return_value = mock_result
        result = await dp.process_document("test.docx", "word")
        assert "content" in result
        assert "chunks" in result
        assert "chunk_count" in result
        assert "char_count" in result
        assert "测试内容" in result["content"]


@pytest.mark.asyncio
async def test_process_word_legacy():
    dp = DocumentProcessor()
    mock_completed = MagicMock()
    mock_completed.returncode = 0
    mock_completed.stdout = "偏差调查报告内容"
    mock_completed.stderr = ""

    with patch("app.services.document_processor.subprocess.run", return_value=mock_completed):
        result = await dp._process_word_legacy("test.doc")
        assert "偏差调查报告内容" in result


@pytest.mark.asyncio
async def test_process_word_legacy_antword_missing():
    dp = DocumentProcessor()

    with patch("app.services.document_processor.subprocess.run", side_effect=FileNotFoundError):
        with pytest.raises(RuntimeError, match="antiword not installed"):
            await dp._process_word_legacy("test.doc")


@pytest.mark.asyncio
async def test_process_word_legacy_antword_failure():
    dp = DocumentProcessor()
    mock_completed = MagicMock()
    mock_completed.returncode = 1
    mock_completed.stdout = ""
    mock_completed.stderr = "Cannot read file"

    with patch("app.services.document_processor.subprocess.run", return_value=mock_completed):
        with pytest.raises(RuntimeError, match="antiword failed"):
            await dp._process_word_legacy("test.doc")


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
    mock_doc.__enter__ = MagicMock(return_value=mock_doc)
    mock_doc.__exit__ = MagicMock(return_value=False)

    with patch("app.services.document_processor.fitz.open", return_value=mock_doc):
        result = await dp._process_pdf("test.pdf")
        assert "这是一段足够长的PDF文本内容" in result


@pytest.mark.asyncio
async def test_process_document_word_legacy_e2e():
    dp = DocumentProcessor()
    mock_completed = MagicMock()
    mock_completed.returncode = 0
    mock_completed.stdout = "偏差调查报告"
    mock_completed.stderr = ""

    with patch("app.services.document_processor.subprocess.run", return_value=mock_completed):
        result = await dp.process_document("test.doc", "word_legacy")
        assert "content" in result
        assert "chunks" in result
        assert "chunk_count" in result
        assert "char_count" in result
        assert "偏差调查报告" in result["content"]


@pytest.mark.asyncio
async def test_process_document_text_e2e():
    dp = DocumentProcessor()
    mock_file = MagicMock()
    mock_file.__enter__ = MagicMock(return_value=mock_file)
    mock_file.__exit__ = MagicMock(return_value=False)
    mock_file.read.return_value = "GMP合规审查文本内容"

    with patch("builtins.open", return_value=mock_file):
        result = await dp.process_document("test.txt", "text")
        assert "content" in result
        assert "chunks" in result
        assert "GMP合规审查文本内容" in result["content"]


@pytest.mark.asyncio
async def test_process_document_image_e2e():
    dp = DocumentProcessor()
    mock_ocr = MagicMock(return_value=([([], "图片中的文字", 0.95)], 0.1))
    dp.ocr = mock_ocr

    result = await dp.process_document("test.png", "image")
    assert "content" in result
    assert "chunks" in result
    assert "图片中的文字" in result["content"]
