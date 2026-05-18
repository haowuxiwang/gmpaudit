import os
import sys
import tempfile
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.document import Document, DocumentStatus


@pytest.mark.asyncio
async def test_upload_unsupported_type(client: AsyncClient):
    files = {"file": ("test.xyz", b"content", "application/octet-stream")}
    response = await client.post("/api/documents/upload", files=files)
    assert response.status_code == 400
    assert "不支持" in response.json()["detail"]


@pytest.mark.asyncio
async def test_upload_document_image(client: AsyncClient):
    files = {"file": ("test.jpg", b"\xff\xd8\xff\xe0fake jpg", "image/jpeg")}
    response = await client.post("/api/documents/upload", files=files)
    assert response.status_code == 200
    assert response.json()["filename"] == "test.jpg"


@pytest.mark.asyncio
async def test_batch_upload(client: AsyncClient):
    files = [
        ("files", ("a.pdf", b"%PDF-1.4 fake", "application/pdf")),
        ("files", ("b.pdf", b"%PDF-1.4 fake", "application/pdf")),
        ("files", ("c.xyz", b"bad", "application/octet-stream")),
    ]
    response = await client.post("/api/documents/upload/batch", files=files)
    assert response.status_code == 200
    results = response.json()
    assert len(results) == 2  # c.xyz rejected


@pytest.mark.asyncio
async def test_delete_nonexistent_document(client: AsyncClient):
    response = await client.delete("/api/documents/999")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_process_document_not_found(client: AsyncClient):
    response = await client.post("/api/documents/999/process")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_list_documents_with_pagination(client: AsyncClient, db_session: AsyncSession):
    for i in range(5):
        doc = Document(
            filename=f"test_{i}.pdf",
            file_path=f"/tmp/test_{i}.pdf",
            file_type="pdf",
            file_size=1024 * (i + 1),
            process_status=DocumentStatus.UPLOADED,
        )
        db_session.add(doc)
    await db_session.commit()

    response = await client.get("/api/documents/?page=1&page_size=2")
    assert response.status_code == 200
    data = response.json()
    assert len(data["items"]) <= 2
    assert data["total"] == 5


@pytest.mark.asyncio
async def test_process_document_success(client: AsyncClient, db_session: AsyncSession):
    doc = Document(
        filename="process.pdf",
        file_path="/tmp/process.pdf",
        file_type="pdf",
        file_size=2048,
        process_status=DocumentStatus.UPLOADED,
    )
    db_session.add(doc)
    await db_session.commit()
    await db_session.refresh(doc)

    from unittest.mock import AsyncMock, MagicMock
    import app.services.document_processor as dp_module

    mock_processor = MagicMock()
    mock_processor.process_document = AsyncMock(return_value={
        "content": "Processed content",
        "chunks": ["chunk1"],
        "chunk_count": 1,
        "char_count": 16,
    })

    original = dp_module.document_processor
    dp_module.document_processor = mock_processor
    try:
        response = await client.post(f"/api/documents/{doc.id}/process")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert data["char_count"] == 16
    finally:
        dp_module.document_processor = original


@pytest.mark.asyncio
async def test_process_document_failure(client: AsyncClient, db_session: AsyncSession):
    doc = Document(
        filename="fail.pdf",
        file_path="/tmp/fail.pdf",
        file_type="pdf",
        file_size=1024,
        process_status=DocumentStatus.UPLOADED,
    )
    db_session.add(doc)
    await db_session.commit()
    await db_session.refresh(doc)

    from unittest.mock import AsyncMock, MagicMock
    import app.services.document_processor as dp_module

    mock_processor = MagicMock()
    mock_processor.process_document = AsyncMock(side_effect=Exception("Processing error"))

    original = dp_module.document_processor
    dp_module.document_processor = mock_processor
    try:
        response = await client.post(f"/api/documents/{doc.id}/process")
        assert response.status_code == 500
        assert "处理失败" in response.json()["detail"]
    finally:
        dp_module.document_processor = original


@pytest.mark.asyncio
async def test_delete_document_removes_file(client: AsyncClient, db_session: AsyncSession):
    from app.core.config import settings
    upload_dir = settings.UPLOAD_DIR
    os.makedirs(upload_dir, exist_ok=True)
    test_file = os.path.join(upload_dir, "test_delete_file.pdf")
    with open(test_file, "wb") as f:
        f.write(b"test content")

    doc = Document(
        filename="delete.pdf",
        file_path=test_file,
        file_type="pdf",
        file_size=12,
        process_status=DocumentStatus.UPLOADED,
    )
    db_session.add(doc)
    await db_session.commit()
    await db_session.refresh(doc)

    response = await client.delete(f"/api/documents/{doc.id}")
    assert response.status_code == 200
    assert not os.path.exists(test_file)
