"""Tests for app.services.converter — document-to-markdown conversion."""

import os
import tempfile
from unittest.mock import MagicMock, patch

import pytest

from app.services.converter import _convert_sync, _get_markitdown, convert_to_markdown


class TestGetMarkitdown:
    def test_singleton_behavior(self):
        """Two calls return the same instance."""
        with patch("app.services.converter._markitdown_instance", None):
            with patch("markitdown.MarkItDown") as mock_cls:
                instance1 = _get_markitdown()
                instance2 = _get_markitdown()
                assert instance1 is instance2
                mock_cls.assert_called_once()


class TestConvertSync:
    def test_successful_conversion(self):
        mock_md = MagicMock()
        mock_result = MagicMock()
        mock_result.text_content = "# Converted Content"
        mock_md.convert.return_value = mock_result

        with patch("app.services.converter._get_markitdown", return_value=mock_md):
            result = _convert_sync(b"test content", ".pdf")
            assert result == "# Converted Content"
            mock_md.convert.assert_called_once()

    def test_temp_file_cleanup_on_success(self):
        mock_md = MagicMock()
        mock_result = MagicMock()
        mock_result.text_content = "content"
        mock_md.convert.return_value = mock_result

        temp_files_before = set(os.listdir(tempfile.gettempdir()))
        with patch("app.services.converter._get_markitdown", return_value=mock_md):
            _convert_sync(b"test", ".pdf")
        temp_files_after = set(os.listdir(tempfile.gettempdir()))
        # No new temp files should remain
        new_files = temp_files_after - temp_files_before
        assert len(new_files) == 0

    def test_temp_file_cleanup_on_failure(self):
        mock_md = MagicMock()
        mock_md.convert.side_effect = RuntimeError("conversion failed")

        temp_files_before = set(os.listdir(tempfile.gettempdir()))
        with patch("app.services.converter._get_markitdown", return_value=mock_md):
            with pytest.raises(RuntimeError, match="conversion failed"):
                _convert_sync(b"test", ".pdf")
        temp_files_after = set(os.listdir(tempfile.gettempdir()))
        new_files = temp_files_after - temp_files_before
        assert len(new_files) == 0


@pytest.mark.asyncio
class TestConvertToMarkdown:
    async def test_suffix_extraction(self):
        mock_md = MagicMock()
        mock_result = MagicMock()
        mock_result.text_content = "content"
        mock_md.convert.return_value = mock_result

        with patch("app.services.converter._get_markitdown", return_value=mock_md):
            result = await convert_to_markdown(b"test", "/path/to/file.DOCX")
            assert result == "content"
            # Verify the suffix was passed correctly
            call_args = mock_md.convert.call_args
            temp_path = call_args[0][0]
            assert temp_path.endswith(".docx")

    async def test_error_wraps_runtimeerror(self):
        mock_md = MagicMock()
        mock_md.convert.side_effect = ValueError("bad format")

        with patch("app.services.converter._get_markitdown", return_value=mock_md):
            with pytest.raises(RuntimeError, match="文档转换失败"):
                await convert_to_markdown(b"test", "file.pdf")

    async def test_magika_error_message(self):
        mock_md = MagicMock()
        mock_md.convert.side_effect = FileNotFoundError("magika model dir not found")

        with patch("app.services.converter._get_markitdown", return_value=mock_md):
            with pytest.raises(RuntimeError, match="magika"):
                await convert_to_markdown(b"test", "file.pdf")
