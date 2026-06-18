"""Tests for document upload and processing to cover uncovered code paths.

Targets specific uncovered lines in documents.py to increase coverage.
"""

import io
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient

from app.models.document import Document, DocumentStatus


@pytest.mark.asyncio
class TestDocumentUpload:
    """Test POST /documents/upload endpoint."""

    async def test_upload_txt_file(self, client: AsyncClient):
        """Upload a txt file."""
        file_content = b"Test document content for GMP audit"
        files = {"file": ("test.txt", io.BytesIO(file_content), "text/plain")}
        resp = await client.post("/api/documents/upload", files=files)
        assert resp.status_code == 200
        data = resp.json()
        assert "id" in data
        assert data["filename"] == "test.txt"
        assert data["status"] == "uploaded"

    async def test_upload_unsupported_type(self, client: AsyncClient):
        """Upload unsupported file type."""
        file_content = b"test"
        files = {"file": ("test.xyz", io.BytesIO(file_content), "application/octet-stream")}
        resp = await client.post("/api/documents/upload", files=files)
        assert resp.status_code == 400

    async def test_upload_pdf_file(self, client: AsyncClient):
        """Upload a PDF file."""
        file_content = b"%PDF-1.4 test content"
        files = {"file": ("test.pdf", io.BytesIO(file_content), "application/pdf")}
        resp = await client.post("/api/documents/upload", files=files)
        assert resp.status_code == 200
        data = resp.json()
        assert data["filename"] == "test.pdf"

    async def test_upload_docx_file(self, client: AsyncClient):
        """Upload a DOCX file."""
        file_content = b"PK test docx content"
        files = {
            "file": (
                "test.docx",
                io.BytesIO(file_content),
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )
        }
        resp = await client.post("/api/documents/upload", files=files)
        assert resp.status_code == 200


@pytest.mark.asyncio
class TestDocumentBatchUpload:
    """Test POST /documents/upload/batch endpoint."""

    async def test_batch_upload(self, client: AsyncClient):
        """Upload multiple files."""
        files = [
            ("files", ("test1.txt", io.BytesIO(b"content1"), "text/plain")),
            ("files", ("test2.txt", io.BytesIO(b"content2"), "text/plain")),
        ]
        resp = await client.post("/api/documents/upload/batch", files=files)
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) == 2

    async def test_batch_upload_mixed_types(self, client: AsyncClient):
        """Upload mixed file types."""
        files = [
            ("files", ("test.txt", io.BytesIO(b"content"), "text/plain")),
            ("files", ("test.xyz", io.BytesIO(b"bad"), "application/octet-stream")),
        ]
        resp = await client.post("/api/documents/upload/batch", files=files)
        assert resp.status_code == 200
        data = resp.json()
        # Only the txt file should be uploaded
        assert len(data) == 1


@pytest.mark.asyncio
class TestDocumentProcess:
    """Test POST /documents/{id}/process endpoint."""

    async def test_process_document_success(self, client: AsyncClient, db_session):
        """Process a document successfully."""
        doc = Document(
            filename="process.txt",
            file_path="/tmp/process.txt",
            file_type="txt",
            file_size=100,
            process_status=DocumentStatus.UPLOADED,
        )
        db_session.add(doc)
        await db_session.commit()
        await db_session.refresh(doc)

        with patch("app.services.document_processor.get_document_processor") as mock_proc:
            mock_processor = MagicMock()
            mock_processor.process_document = AsyncMock(
                return_value={
                    "content": "Processed content",
                    "char_count": 17,
                    "chunk_count": 1,
                }
            )
            mock_proc.return_value = mock_processor

            resp = await client.post(f"/api/documents/{doc.id}/process")
            assert resp.status_code == 200
            data = resp.json()
            assert data["status"] == "success"
            assert data["char_count"] == 17

    async def test_process_document_already_processing(self, client: AsyncClient, db_session):
        """Process document that's already processing."""
        doc = Document(
            filename="processing.txt",
            file_path="/tmp/processing.txt",
            file_type="txt",
            file_size=100,
            process_status=DocumentStatus.PROCESSING,
        )
        db_session.add(doc)
        await db_session.commit()
        await db_session.refresh(doc)

        resp = await client.post(f"/api/documents/{doc.id}/process")
        assert resp.status_code == 409

    async def test_process_document_failure(self, client: AsyncClient, db_session):
        """Process document that fails."""
        doc = Document(
            filename="fail.txt",
            file_path="/tmp/fail.txt",
            file_type="txt",
            file_size=100,
            process_status=DocumentStatus.UPLOADED,
        )
        db_session.add(doc)
        await db_session.commit()
        await db_session.refresh(doc)

        with patch("app.services.document_processor.get_document_processor") as mock_proc:
            mock_processor = MagicMock()
            mock_processor.process_document = AsyncMock(side_effect=Exception("Processing failed"))
            mock_proc.return_value = mock_processor

            resp = await client.post(f"/api/documents/{doc.id}/process")
            assert resp.status_code == 500


@pytest.mark.asyncio
class TestDocumentDelete:
    """Test DELETE /documents/{id} endpoint."""

    async def test_delete_document_not_found(self, client: AsyncClient):
        """Delete nonexistent document."""
        resp = await client.delete("/api/documents/99999")
        assert resp.status_code == 404


@pytest.mark.asyncio
class TestDocumentGet:
    """Test GET /documents/{id} endpoint."""

    async def test_get_document(self, client: AsyncClient, db_session):
        """Get document by ID."""
        doc = Document(
            filename="get.txt",
            file_path="/tmp/get.txt",
            file_type="txt",
            file_size=100,
            process_status=DocumentStatus.PROCESSED,
            content_text="Test content",
        )
        db_session.add(doc)
        await db_session.commit()
        await db_session.refresh(doc)

        resp = await client.get(f"/api/documents/{doc.id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["filename"] == "get.txt"
        assert data["content_text"] == "Test content"

    async def test_get_document_not_found(self, client: AsyncClient):
        """Get nonexistent document."""
        resp = await client.get("/api/documents/99999")
        assert resp.status_code == 404


@pytest.mark.asyncio
class TestDocumentList:
    """Test GET /documents/ endpoint."""

    async def test_list_documents_empty(self, client: AsyncClient):
        """List documents when empty."""
        resp = await client.get("/api/documents/")
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert "total" in data

    async def test_list_documents_with_data(self, client: AsyncClient, db_session):
        """List documents with data."""
        doc = Document(
            filename="list.txt",
            file_path="/tmp/list.txt",
            file_type="txt",
            file_size=100,
            process_status=DocumentStatus.UPLOADED,
        )
        db_session.add(doc)
        await db_session.commit()

        resp = await client.get("/api/documents/")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1
        assert len(data["items"]) >= 1

    async def test_list_documents_with_pagination(self, client: AsyncClient, db_session):
        """List documents with pagination."""
        for i in range(5):
            doc = Document(
                filename=f"page_{i}.txt",
                file_path=f"/tmp/page_{i}.txt",
                file_type="txt",
                file_size=100 * (i + 1),
                process_status=DocumentStatus.UPLOADED,
            )
            db_session.add(doc)
        await db_session.commit()

        resp = await client.get("/api/documents/", params={"page": 1, "page_size": 2})
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["items"]) <= 2
        assert data["total"] >= 5
