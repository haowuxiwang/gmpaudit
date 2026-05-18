"""Unit tests for get_file_type() - ensures all supported extensions map correctly."""

from app.utils.file_utils import get_file_type


def test_pdf_extension():
    assert get_file_type("report.pdf") == "pdf"


def test_docx_extension():
    assert get_file_type("report.docx") == "word"


def test_doc_extension():
    assert get_file_type("report.doc") == "word_legacy"


def test_txt_extension():
    assert get_file_type("report.txt") == "text"


def test_jpg_extension():
    assert get_file_type("photo.jpg") == "image"


def test_jpeg_extension():
    assert get_file_type("photo.jpeg") == "image"


def test_png_extension():
    assert get_file_type("screenshot.png") == "image"


def test_tiff_extension():
    assert get_file_type("scan.tiff") == "image"


def test_bmp_extension():
    assert get_file_type("scan.bmp") == "image"


def test_uppercase_extension():
    assert get_file_type("report.PDF") == "pdf"
    assert get_file_type("report.DOCX") == "word"
    assert get_file_type("report.DOC") == "word_legacy"


def test_unknown_extension():
    assert get_file_type("report.xyz") == "unknown"
    assert get_file_type("report.xlsx") == "unknown"
    assert get_file_type("report.csv") == "unknown"


def test_no_extension():
    assert get_file_type("report") == "unknown"


def test_doc_and_docx_are_distinct():
    assert get_file_type("a.doc") != get_file_type("a.docx")
    assert get_file_type("a.doc") == "word_legacy"
    assert get_file_type("a.docx") == "word"
