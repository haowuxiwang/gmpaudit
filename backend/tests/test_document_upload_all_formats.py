"""API tests ensuring all supported document formats upload correctly with proper file_type."""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.document import Document, DocumentStatus


@pytest.mark.asyncio
async def test_upload_pdf(client: AsyncClient):
    files = {"file": ("report.pdf", b"fake pdf content", "application/pdf")}
    response = await client.post("/api/documents/upload", files=files)
    assert response.status_code == 200
    data = response.json()
    assert data["filename"] == "report.pdf"
    assert data["status"] == "uploaded"


@pytest.mark.asyncio
async def test_upload_docx(client: AsyncClient):
    files = {"file": ("report.docx", b"fake docx content", "application/vnd.openxmlformats-officedocument.wordprocessingml.document")}
    response = await client.post("/api/documents/upload", files=files)
    assert response.status_code == 200
    data = response.json()
    assert data["filename"] == "report.docx"
    assert data["status"] == "uploaded"


@pytest.mark.asyncio
async def test_upload_doc(client: AsyncClient):
    files = {"file": ("report.doc", b"fake doc content", "application/msword")}
    response = await client.post("/api/documents/upload", files=files)
    assert response.status_code == 200
    data = response.json()
    assert data["filename"] == "report.doc"
    assert data["status"] == "uploaded"


@pytest.mark.asyncio
async def test_upload_txt(client: AsyncClient):
    files = {"file": ("report.txt", b"fake text content", "text/plain")}
    response = await client.post("/api/documents/upload", files=files)
    assert response.status_code == 200
    data = response.json()
    assert data["filename"] == "report.txt"
    assert data["status"] == "uploaded"


@pytest.mark.asyncio
async def test_upload_jpg(client: AsyncClient):
    files = {"file": ("photo.jpg", b"\xff\xd8\xff\xe0fake jpg", "image/jpeg")}
    response = await client.post("/api/documents/upload", files=files)
    assert response.status_code == 200
    assert response.json()["filename"] == "photo.jpg"


@pytest.mark.asyncio
async def test_upload_png(client: AsyncClient):
    files = {"file": ("screenshot.png", b"\x89PNGfake png", "image/png")}
    response = await client.post("/api/documents/upload", files=files)
    assert response.status_code == 200
    assert response.json()["filename"] == "screenshot.png"


@pytest.mark.asyncio
async def test_upload_unsupported_type_returns_400(client: AsyncClient):
    files = {"file": ("report.xyz", b"content", "application/octet-stream")}
    response = await client.post("/api/documents/upload", files=files)
    assert response.status_code == 400
    assert "不支持" in response.json()["detail"]


@pytest.mark.asyncio
async def test_upload_doc_stored_as_word_legacy(client: AsyncClient, db_session: AsyncSession):
    files = {"file": ("report.doc", b"fake doc content", "application/msword")}
    response = await client.post("/api/documents/upload", files=files)
    assert response.status_code == 200
    doc_id = response.json()["id"]

    result = await db_session.execute(
        Document.__table__.select().where(Document.id == doc_id)
    )
    row = result.fetchone()
    assert row.file_type == "word_legacy"


@pytest.mark.asyncio
async def test_upload_docx_stored_as_word(client: AsyncClient, db_session: AsyncSession):
    files = {"file": ("report.docx", b"fake docx content", "application/vnd.openxmlformats-officedocument.wordprocessingml.document")}
    response = await client.post("/api/documents/upload", files=files)
    assert response.status_code == 200
    doc_id = response.json()["id"]

    result = await db_session.execute(
        Document.__table__.select().where(Document.id == doc_id)
    )
    row = result.fetchone()
    assert row.file_type == "word"


@pytest.mark.asyncio
async def test_batch_upload_mixed_formats(client: AsyncClient):
    files = [
        ("files", ("a.pdf", b"pdf content", "application/pdf")),
        ("files", ("b.docx", b"docx content", "application/vnd.openxmlformats-officedocument.wordprocessingml.document")),
        ("files", ("c.doc", b"doc content", "application/msword")),
        ("files", ("d.txt", b"text content", "text/plain")),
        ("files", ("e.xyz", b"bad", "application/octet-stream")),
    ]
    response = await client.post("/api/documents/upload/batch", files=files)
    assert response.status_code == 200
    results = response.json()
    assert len(results) == 4  # e.xyz skipped
    filenames = [r["filename"] for r in results]
    assert "a.pdf" in filenames
    assert "b.docx" in filenames
    assert "c.doc" in filenames
    assert "d.txt" in filenames
