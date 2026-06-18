import json
import os
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.document import Document, DocumentStatus
from app.models.finding import Finding, FindingType, SeverityLevel

# ---------------------------------------------------------------------------
# Upload
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_upload_document(client: AsyncClient):
    files = {"file": ("test.pdf", b"test content", "application/pdf")}
    response = await client.post("/api/documents/upload", files=files)
    assert response.status_code == 200
    data = response.json()
    assert "id" in data
    assert data["filename"] == "test.pdf"
    assert data["status"] == "uploaded"


@pytest.mark.asyncio
async def test_upload_docx(client: AsyncClient):
    files = {
        "file": (
            "report.docx",
            b"PK\x03\x04fake docx",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )
    }
    response = await client.post("/api/documents/upload", files=files)
    assert response.status_code == 200
    assert response.json()["filename"] == "report.docx"


@pytest.mark.asyncio
async def test_upload_txt(client: AsyncClient):
    files = {"file": ("notes.txt", b"plain text content", "text/plain")}
    response = await client.post("/api/documents/upload", files=files)
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_upload_image(client: AsyncClient):
    files = {"file": ("photo.jpg", b"\xff\xd8\xff\xe0fake", "image/jpeg")}
    response = await client.post("/api/documents/upload", files=files)
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_upload_unsupported_type(client: AsyncClient):
    files = {"file": ("data.xyz", b"content", "application/octet-stream")}
    response = await client.post("/api/documents/upload", files=files)
    assert response.status_code == 400
    assert "不支持" in response.json()["detail"]


@pytest.mark.asyncio
async def test_upload_oversized_file(client: AsyncClient):
    """Content-Length header exceeding limit should be rejected."""
    from app.api.documents import MAX_UPLOAD_SIZE

    big_size = MAX_UPLOAD_SIZE + 2048
    headers = {"content-length": str(big_size)}
    files = {"file": ("big.pdf", b"x", "application/pdf")}
    response = await client.post("/api/documents/upload", files=files, headers=headers)
    assert response.status_code == 413


# ---------------------------------------------------------------------------
# Batch upload
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_batch_upload(client: AsyncClient):
    files = [
        ("files", ("a.pdf", b"%PDF-1.4 fake", "application/pdf")),
        ("files", ("b.pdf", b"%PDF-1.4 fake", "application/pdf")),
    ]
    response = await client.post("/api/documents/upload/batch", files=files)
    assert response.status_code == 200
    results = response.json()
    assert len(results) == 2
    for r in results:
        assert r["status"] == "uploaded"


@pytest.mark.asyncio
async def test_batch_upload_mixed_types(client: AsyncClient):
    files = [
        ("files", ("good.pdf", b"%PDF-1.4", "application/pdf")),
        ("files", ("bad.xyz", b"nope", "application/octet-stream")),
    ]
    response = await client.post("/api/documents/upload/batch", files=files)
    assert response.status_code == 200
    results = response.json()
    assert len(results) == 1  # bad.xyz skipped


# ---------------------------------------------------------------------------
# List documents
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_documents(client: AsyncClient):
    response = await client.get("/api/documents/")
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert "total" in data
    assert "page" in data
    assert "page_size" in data
    assert isinstance(data["items"], list)


@pytest.mark.asyncio
async def test_list_documents_pagination(client: AsyncClient, db_session: AsyncSession):
    for i in range(5):
        db_session.add(
            Document(
                filename=f"doc_{i}.pdf",
                file_path=f"/tmp/doc_{i}.pdf",
                file_type="pdf",
                file_size=100 * (i + 1),
                process_status=DocumentStatus.UPLOADED,
            )
        )
    await db_session.commit()

    resp = await client.get("/api/documents/", params={"page": 1, "page_size": 2})
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["items"]) == 2
    assert data["total"] == 5


@pytest.mark.asyncio
async def test_list_documents_empty(client: AsyncClient):
    resp = await client.get("/api/documents/")
    assert resp.status_code == 200
    assert resp.json()["total"] == 0


# ---------------------------------------------------------------------------
# Get document
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_document(client: AsyncClient):
    files = {"file": ("test.pdf", b"test content", "application/pdf")}
    upload_response = await client.post("/api/documents/upload", files=files)
    doc_id = upload_response.json()["id"]

    response = await client.get(f"/api/documents/{doc_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == doc_id
    assert data["filename"] == "test.pdf"


@pytest.mark.asyncio
async def test_get_document_with_content(client: AsyncClient, db_session: AsyncSession):
    doc = Document(
        filename="content.pdf",
        file_path="/tmp/content.pdf",
        file_type="pdf",
        file_size=100,
        process_status=DocumentStatus.PROCESSED,
        content_text="Full text content here",
    )
    db_session.add(doc)
    await db_session.commit()
    await db_session.refresh(doc)

    resp = await client.get(f"/api/documents/{doc.id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["content_text"] == "Full text content here"
    assert data["process_status"] == "processed"


@pytest.mark.asyncio
async def test_get_document_with_metadata(client: AsyncClient, db_session: AsyncSession):
    doc = Document(
        filename="meta.pdf",
        file_path="/tmp/meta.pdf",
        file_type="pdf",
        file_size=100,
        process_status=DocumentStatus.UPLOADED,
        doc_metadata=json.dumps({"pages": 10, "author": "test"}),
    )
    db_session.add(doc)
    await db_session.commit()
    await db_session.refresh(doc)

    resp = await client.get(f"/api/documents/{doc.id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["doc_metadata"]["pages"] == 10


@pytest.mark.asyncio
async def test_get_document_with_dict_metadata(client: AsyncClient, db_session: AsyncSession):
    """When doc_metadata is a JSON string, it should be parsed correctly."""
    doc = Document(
        filename="dict_meta.pdf",
        file_path="/tmp/dm.pdf",
        file_type="pdf",
        file_size=100,
        process_status=DocumentStatus.UPLOADED,
        doc_metadata='{"key": "value"}',
    )
    db_session.add(doc)
    await db_session.commit()
    await db_session.refresh(doc)

    resp = await client.get(f"/api/documents/{doc.id}")
    assert resp.status_code == 200
    assert resp.json()["doc_metadata"] == {"key": "value"}


@pytest.mark.asyncio
async def test_get_nonexistent_document(client: AsyncClient):
    response = await client.get("/api/documents/999")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_list_documents_item_fields(client: AsyncClient, db_session: AsyncSession):
    """Ensure list response includes all expected fields."""
    doc = Document(
        filename="fields.pdf",
        file_path="/tmp/fields.pdf",
        file_type="pdf",
        file_size=512,
        process_status=DocumentStatus.PROCESSED,
    )
    db_session.add(doc)
    await db_session.commit()

    resp = await client.get("/api/documents/")
    items = resp.json()["items"]
    assert len(items) >= 1
    item = [i for i in items if i["id"] == doc.id][0]
    assert item["filename"] == "fields.pdf"
    assert item["file_type"] == "pdf"
    assert item["file_size"] == 512
    assert item["process_status"] == "processed"
    assert "upload_time" in item
    assert "created_at" in item


# ---------------------------------------------------------------------------
# Process document
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_process_document_not_found(client: AsyncClient):
    resp = await client.post("/api/documents/999/process")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_process_document_already_processing(client: AsyncClient, db_session: AsyncSession):
    doc = Document(
        filename="proc.pdf",
        file_path="/tmp/proc.pdf",
        file_type="pdf",
        file_size=100,
        process_status=DocumentStatus.PROCESSING,
    )
    db_session.add(doc)
    await db_session.commit()
    await db_session.refresh(doc)

    resp = await client.post(f"/api/documents/{doc.id}/process")
    assert resp.status_code == 409
    assert "处理中" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_process_document_success(client: AsyncClient, db_session: AsyncSession):
    doc = Document(
        filename="ok.pdf",
        file_path="/tmp/ok.pdf",
        file_type="pdf",
        file_size=2048,
        process_status=DocumentStatus.UPLOADED,
    )
    db_session.add(doc)
    await db_session.commit()
    await db_session.refresh(doc)

    mock_proc = MagicMock()
    mock_proc.process_document = AsyncMock(
        return_value={
            "content": "Processed!",
            "chunks": ["c1"],
            "chunk_count": 1,
            "char_count": 10,
        }
    )

    import app.services.document_processor as dp

    orig = dp.document_processor
    dp.document_processor = mock_proc
    try:
        resp = await client.post(f"/api/documents/{doc.id}/process")
        assert resp.status_code == 200
        assert resp.json()["status"] == "success"
        assert resp.json()["char_count"] == 10
    finally:
        dp.document_processor = orig


@pytest.mark.asyncio
async def test_process_document_failure(client: AsyncClient, db_session: AsyncSession):
    doc = Document(
        filename="fail.pdf",
        file_path="/tmp/fail.pdf",
        file_type="pdf",
        file_size=100,
        process_status=DocumentStatus.UPLOADED,
    )
    db_session.add(doc)
    await db_session.commit()
    await db_session.refresh(doc)

    mock_proc = MagicMock()
    mock_proc.process_document = AsyncMock(side_effect=Exception("Processing error"))

    import app.services.document_processor as dp

    orig = dp.document_processor
    dp.document_processor = mock_proc
    try:
        resp = await client.post(f"/api/documents/{doc.id}/process")
        assert resp.status_code == 500
        assert "处理失败" in resp.json()["detail"]
    finally:
        dp.document_processor = orig


# ---------------------------------------------------------------------------
# Delete document
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_delete_document(client: AsyncClient):
    files = {"file": ("test.pdf", b"test content", "application/pdf")}
    upload_response = await client.post("/api/documents/upload", files=files)
    doc_id = upload_response.json()["id"]

    response = await client.delete(f"/api/documents/{doc_id}")
    assert response.status_code == 200
    assert response.json()["status"] == "success"

    get_response = await client.get(f"/api/documents/{doc_id}")
    assert get_response.status_code == 404


@pytest.mark.asyncio
async def test_delete_nonexistent_document(client: AsyncClient):
    response = await client.delete("/api/documents/999")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_delete_document_with_findings_rejected(client: AsyncClient, db_session: AsyncSession):
    """Document referenced by findings should not be deletable."""
    doc = Document(
        filename="ref.pdf",
        file_path="/tmp/ref.pdf",
        file_type="pdf",
        file_size=100,
        process_status=DocumentStatus.UPLOADED,
    )
    db_session.add(doc)
    await db_session.commit()
    await db_session.refresh(doc)

    finding = Finding(
        task_id=0,
        document_id=doc.id,
        finding_type=FindingType.COMPLIANCE_RISK,
        severity=SeverityLevel.HIGH,
        title="F",
        description="D",
    )
    db_session.add(finding)
    await db_session.commit()

    resp = await client.delete(f"/api/documents/{doc.id}")
    assert resp.status_code == 400
    assert "引用" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_delete_document_removes_file(client: AsyncClient, db_session: AsyncSession):
    from app.core.config import settings

    upload_dir = settings.UPLOAD_DIR
    os.makedirs(upload_dir, exist_ok=True)
    test_file = os.path.join(upload_dir, "del_test_file.pdf")
    with open(test_file, "wb") as f:
        f.write(b"test content for delete")

    doc = Document(
        filename="del.pdf",
        file_path=test_file,
        file_type="pdf",
        file_size=23,
        process_status=DocumentStatus.UPLOADED,
    )
    db_session.add(doc)
    await db_session.commit()
    await db_session.refresh(doc)

    assert os.path.exists(test_file)
    resp = await client.delete(f"/api/documents/{doc.id}")
    assert resp.status_code == 200
    assert not os.path.exists(test_file)
