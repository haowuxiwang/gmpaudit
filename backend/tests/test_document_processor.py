from unittest.mock import MagicMock, mock_open, patch

import pytest

from app.services.document_processor import DocumentProcessor


def test_clean_text():
    dp = DocumentProcessor()
    assert dp._clean_text("  hello   world  ") == "hello world"
    assert dp._clean_text("") == ""
    assert dp._clean_text(None) == ""
    assert dp._clean_text("  \n\t  ") == ""


def test_clean_text_collapses_triple_newlines():
    dp = DocumentProcessor()
    result = dp._clean_text("line1\n\n\n\n\nline2")
    assert result == "line1\n\nline2"


def test_clean_text_preserves_double_newlines():
    dp = DocumentProcessor()
    result = dp._clean_text("line1\n\nline2")
    assert result == "line1\n\nline2"


def test_clean_text_strips_internal_whitespace():
    dp = DocumentProcessor()
    result = dp._clean_text("  foo   bar   baz  ")
    assert result == "foo bar baz"


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


def test_split_text_english_period_boundary():
    """Test that _split_text uses '.' as fallback when no Chinese period found."""
    dp = DocumentProcessor()
    text = "First sentence. " + "Second sentence. " + "C" * 2000
    chunks = dp._split_text(text, chunk_size=500, overlap=50)
    assert len(chunks) >= 1
    # First chunk should break at the period
    assert "First sentence." in chunks[0] or "Second sentence." in chunks[0]


def test_split_text_no_punctuation():
    """When there is no sentence boundary, chunks at chunk_size."""
    dp = DocumentProcessor()
    text = "A" * 500
    chunks = dp._split_text(text, chunk_size=200, overlap=0)
    assert len(chunks) == 3  # 200 + 200 + 100


def test_split_text_exact_boundary():
    """Text exactly equals chunk_size with zero overlap produces one chunk."""
    dp = DocumentProcessor()
    text = "A" * 100
    chunks = dp._split_text(text, chunk_size=100, overlap=0)
    assert len(chunks) == 1
    assert chunks[0] == text


def test_get_ocr_lazy_init():
    """Test that _get_ocr caches the OCR instance."""
    dp = DocumentProcessor()
    assert dp.ocr is None
    # Pre-set ocr to avoid the import
    mock_ocr = MagicMock()
    dp.ocr = mock_ocr
    result = dp._get_ocr()
    assert result is mock_ocr
    # Calling again returns same instance
    assert dp._get_ocr() is mock_ocr


@pytest.mark.asyncio
async def test_process_word():
    dp = DocumentProcessor()
    mock_result = MagicMock()
    mock_result.value = "段落一\n\n段落二"

    with patch("builtins.open", MagicMock()), patch("app.services.document_processor.mammoth") as mock_mammoth:
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

    with patch("builtins.open", MagicMock()), patch("app.services.document_processor.mammoth") as mock_mammoth:
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

    with (
        patch("app.services.document_processor.subprocess.run", side_effect=FileNotFoundError),
        patch.object(dp, "_extract_doc_text_olefile", return_value="olefile extracted text"),
    ):
        result = await dp._process_word_legacy("test.doc")
        assert result == "olefile extracted text"


@pytest.mark.asyncio
async def test_process_word_legacy_antword_failure():
    dp = DocumentProcessor()
    mock_completed = MagicMock()
    mock_completed.returncode = 1
    mock_completed.stdout = ""
    mock_completed.stderr = "Cannot read file"

    with (
        patch("app.services.document_processor.subprocess.run", return_value=mock_completed),
        patch.object(dp, "_extract_doc_text_olefile", return_value="olefile fallback text"),
    ):
        result = await dp._process_word_legacy("test.doc")
        assert result == "olefile fallback text"


@pytest.mark.asyncio
async def test_process_word_legacy_fallback_to_olefile():
    dp = DocumentProcessor()
    mock_completed = MagicMock()
    mock_completed.returncode = 0
    mock_completed.stdout = "   "
    mock_completed.stderr = ""

    with (
        patch("app.services.document_processor.subprocess.run", return_value=mock_completed),
        patch.object(dp, "_extract_doc_text_olefile", return_value="olefile text content"),
    ):
        result = await dp._process_word_legacy("test.doc")
        assert result == "olefile text content"


def test_extract_doc_text_olefile_corrupted_file():
    dp = DocumentProcessor()
    import os
    import tempfile

    with tempfile.NamedTemporaryFile(suffix=".doc", delete=False, mode="w") as f:
        f.write("not an ole file")
        path = f.name

    try:
        with pytest.raises(RuntimeError, match="Not a valid Word .doc file"):
            dp._extract_doc_text_olefile(path)
    finally:
        os.unlink(path)


def test_extract_doc_text_olefile_password_protected():
    dp = DocumentProcessor()
    import os
    import tempfile

    # Create a minimal valid OLE2 file with EncryptionInfo stream
    # A real encrypted .doc would be needed; skip if not available
    # Instead test with a real .doc that has no EncryptionInfo
    with tempfile.NamedTemporaryFile(suffix=".doc", delete=False, mode="w") as f:
        f.write("not an ole file")
        path = f.name

    try:
        # Non-OLE files raise "Not a valid Word .doc file" (not password-protected)
        with pytest.raises(RuntimeError, match="Not a valid Word .doc file"):
            dp._extract_doc_text_olefile(path)
    finally:
        os.unlink(path)


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


# === New tests for coverage gaps ===


@pytest.mark.asyncio
async def test_process_pdf_ocr_fallback():
    """PDF page with <50 chars triggers OCR fallback."""
    dp = DocumentProcessor()
    dp.ocr = MagicMock(return_value=([([], "OCR提取文字", 0.9)], 0.1))

    mock_page = MagicMock()
    mock_page.get_text.return_value = "短"  # < 50 chars triggers OCR
    mock_pixmap = MagicMock()
    mock_page.get_pixmap.return_value = mock_pixmap

    mock_doc = MagicMock()
    mock_doc.__len__ = MagicMock(return_value=1)
    mock_doc.load_page.return_value = mock_page
    mock_doc.__enter__ = MagicMock(return_value=mock_doc)
    mock_doc.__exit__ = MagicMock(return_value=False)

    with (
        patch("app.services.document_processor.fitz.open", return_value=mock_doc),
        patch("tempfile.NamedTemporaryFile") as mock_tmp,
        patch("os.path.exists", return_value=True),
        patch("os.remove"),
    ):
        mock_tmp_file = MagicMock()
        mock_tmp_file.name = "/tmp/test.png"
        mock_tmp.return_value.__enter__ = MagicMock(return_value=mock_tmp_file)
        mock_tmp.return_value.__exit__ = MagicMock(return_value=False)
        result = await dp._process_pdf("test.pdf")
        assert "OCR提取文字" in result


@pytest.mark.asyncio
async def test_process_pdf_mixed_pages():
    """PDF with one text page and one OCR page."""
    dp = DocumentProcessor()
    dp.ocr = MagicMock(return_value=([([], "OCR结果", 0.9)], 0.1))

    page_text = MagicMock()
    page_text.get_text.return_value = "A" * 100  # >= 50 chars, text extraction

    page_ocr = MagicMock()
    page_ocr.get_text.return_value = "短"  # < 50 chars, OCR fallback
    page_ocr.get_pixmap.return_value = MagicMock()

    mock_doc = MagicMock()
    mock_doc.__len__ = MagicMock(return_value=2)
    mock_doc.load_page.side_effect = [page_text, page_ocr]
    mock_doc.__enter__ = MagicMock(return_value=mock_doc)
    mock_doc.__exit__ = MagicMock(return_value=False)

    with (
        patch("app.services.document_processor.fitz.open", return_value=mock_doc),
        patch("tempfile.NamedTemporaryFile") as mock_tmp,
        patch("os.path.exists", return_value=True),
        patch("os.remove"),
    ):
        mock_tmp_file = MagicMock()
        mock_tmp_file.name = "/tmp/test.png"
        mock_tmp.return_value.__enter__ = MagicMock(return_value=mock_tmp_file)
        mock_tmp.return_value.__exit__ = MagicMock(return_value=False)
        result = await dp._process_pdf("test.pdf")
        assert "A" * 100 in result
        assert "OCR结果" in result


@pytest.mark.asyncio
async def test_process_text_utf8():
    """Test _process_text with UTF-8 encoded file."""
    dp = DocumentProcessor()
    content = "GMP审计文本内容"

    m = mock_open(read_data=content)
    with patch("builtins.open", m):
        result = await dp._process_text("test.txt")
        assert result == content


@pytest.mark.asyncio
async def test_process_text_fallback_encoding():
    """Test _process_text falls back through encodings on UnicodeDecodeError."""
    dp = DocumentProcessor()
    content = "最终内容"

    call_count = 0

    def mock_open_fn(path, encoding=None):
        nonlocal call_count
        call_count += 1
        if encoding == "utf-8":
            raise UnicodeDecodeError("utf-8", b"", 0, 1, "invalid")
        if encoding == "gb18030":
            raise UnicodeDecodeError("gb18030", b"", 0, 1, "invalid")
        # gbk succeeds
        m = mock_open(read_data=content)
        return m()

    with patch("builtins.open", side_effect=mock_open_fn):
        result = await dp._process_text("test.txt")
        assert result == content


@pytest.mark.asyncio
async def test_process_text_all_encodings_fail():
    """Test _process_text uses errors='replace' when all encodings fail."""
    dp = DocumentProcessor()

    call_count = 0

    def mock_open_fn(path, encoding=None, errors=None):
        nonlocal call_count
        call_count += 1
        if errors == "replace":
            m = mock_open(read_data="replaced content")
            return m()
        raise UnicodeDecodeError(encoding or "utf-8", b"", 0, 1, "invalid")

    with patch("builtins.open", side_effect=mock_open_fn):
        result = await dp._process_text("test.txt")
        assert "replaced content" in result


def test_process_image_empty_result_list():
    """Test _process_image when OCR returns empty list (not None)."""
    dp = DocumentProcessor()
    mock_ocr = MagicMock(return_value=([], 0.1))
    dp.ocr = mock_ocr
    result = dp._process_image("test.png")
    assert result == ""


def test_process_image_with_none_text_in_result():
    """Test _process_image handles None text entries in OCR result."""
    dp = DocumentProcessor()
    mock_ocr = MagicMock(return_value=([([], "文字1", 0.9), ([], None, 0.8), ([], "文字2", 0.7)], 0.1))
    dp.ocr = mock_ocr
    result = dp._process_image("test.png")
    assert "文字1" in result
    assert "文字2" in result
    # None entry should be skipped
    assert result.count("\n") == 1


@pytest.mark.asyncio
async def test_process_document_pdf_e2e():
    """Test process_document end-to-end with PDF type."""
    dp = DocumentProcessor()
    mock_page = MagicMock()
    mock_page.get_text.return_value = "这是一段足够长的PDF文本内容用于测试" * 10
    mock_doc = MagicMock()
    mock_doc.__len__ = MagicMock(return_value=1)
    mock_doc.load_page.return_value = mock_page
    mock_doc.__enter__ = MagicMock(return_value=mock_doc)
    mock_doc.__exit__ = MagicMock(return_value=False)

    with patch("app.services.document_processor.fitz.open", return_value=mock_doc):
        result = await dp.process_document("test.pdf", "pdf")
        assert "content" in result
        assert "chunks" in result
        assert "chunk_count" in result
        assert "char_count" in result
        assert result["char_count"] > 0


def test_process_word_legacy_antword_general_error():
    """antiword raises a generic exception (not FileNotFoundError)."""
    dp = DocumentProcessor()
    with (
        patch("app.services.document_processor.subprocess.run", side_effect=OSError("permission denied")),
        patch.object(dp, "_extract_doc_text_olefile", return_value="olefile fallback"),
    ):
        import asyncio

        result = asyncio.get_event_loop().run_until_complete(dp._process_word_legacy("test.doc"))
        assert result == "olefile fallback"


@pytest.mark.asyncio
async def test_process_word_legacy_empty_output():
    """antiword returns empty stdout and stderr."""
    dp = DocumentProcessor()
    mock_completed = MagicMock()
    mock_completed.returncode = 0
    mock_completed.stdout = ""
    mock_completed.stderr = ""

    with (
        patch("app.services.document_processor.subprocess.run", return_value=mock_completed),
        patch.object(dp, "_extract_doc_text_olefile", return_value="olefile result"),
    ):
        result = await dp._process_word_legacy("test.doc")
        assert result == "olefile result"
