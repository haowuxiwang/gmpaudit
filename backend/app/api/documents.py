import logging
import os
import shutil
import tempfile
import uuid
from typing import List

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import async_session, get_db
from app.models.document import Document, DocumentStatus
from app.utils.file_utils import get_file_size, get_file_type

logger = logging.getLogger(__name__)

router = APIRouter()


def _generate_safe_filename(original_filename: str) -> str:
    ext = os.path.splitext(original_filename)[1].lower()
    return f"{uuid.uuid4().hex}{ext}"


def _get_upload_dir() -> str:
    preferred_dir = settings.UPLOAD_DIR
    try:
        os.makedirs(preferred_dir, exist_ok=True)
        probe_path = os.path.join(preferred_dir, ".write_test")
        with open(probe_path, "w", encoding="utf-8") as probe:
            probe.write("ok")
        os.remove(probe_path)
        return preferred_dir
    except OSError:
        fallback_dir = os.path.join(tempfile.gettempdir(), "gmpaudit_uploads")
        os.makedirs(fallback_dir, exist_ok=True)
        return fallback_dir


MAX_UPLOAD_SIZE = 50 * 1024 * 1024  # 50MB


async def _process_document_bg(document_id: int):
    """Process a document in the background after upload."""
    async with async_session() as db:
        try:
            result = await db.execute(select(Document).where(Document.id == document_id))
            document = result.scalar_one_or_none()
            if not document:
                logger.error("Document %s not found for background processing", document_id)
                return

            document.process_status = DocumentStatus.PROCESSING
            await db.commit()

            from app.services.document_processor import get_document_processor
            process_result = await get_document_processor().process_document(document.file_path, document.file_type)
            document.content_text = process_result["content"]
            document.process_status = DocumentStatus.PROCESSED
            await db.commit()
            logger.info("Document %s processed: %d chars, %d chunks", document_id, process_result["char_count"], process_result["chunk_count"])
        except Exception as exc:
            logger.exception("Background processing failed for document %s", document_id)
            try:
                result = await db.execute(select(Document).where(Document.id == document_id))
                document = result.scalar_one_or_none()
                if document:
                    document.process_status = DocumentStatus.FAILED
                    await db.commit()
            except Exception:
                logger.exception("Failed to persist failure state for document %s", document_id)


@router.post("/upload")
async def upload_document(file: UploadFile = File(...), background_tasks: BackgroundTasks = BackgroundTasks(), db: AsyncSession = Depends(get_db)):
    file_type = get_file_type(file.filename)
    if file_type == "unknown":
        raise HTTPException(status_code=400, detail="不支持的文件类型")

    content = await file.read()
    if len(content) > MAX_UPLOAD_SIZE:
        raise HTTPException(status_code=413, detail=f"文件大小超过限制（最大 {MAX_UPLOAD_SIZE // 1024 // 1024}MB）")

    upload_dir = _get_upload_dir()
    safe_filename = _generate_safe_filename(file.filename)
    file_path = os.path.join(upload_dir, safe_filename)

    with open(file_path, "wb") as buffer:
        buffer.write(content)

    try:
        document = Document(
            filename=file.filename,
            file_path=file_path,
            file_type=file_type,
            file_size=get_file_size(file_path),
            process_status=DocumentStatus.UPLOADED,
        )
        db.add(document)
        await db.commit()
        await db.refresh(document)
    except Exception:
        if os.path.exists(file_path):
            os.remove(file_path)
        raise

    background_tasks.add_task(_process_document_bg, document.id)

    return {"id": document.id, "filename": document.filename, "status": "uploaded"}


@router.post("/upload/batch")
async def upload_documents_batch(files: List[UploadFile] = File(...), background_tasks: BackgroundTasks = BackgroundTasks(), db: AsyncSession = Depends(get_db)):
    upload_dir = _get_upload_dir()
    results = []

    for file in files:
        file_type = get_file_type(file.filename)
        if file_type == "unknown":
            continue

        safe_filename = _generate_safe_filename(file.filename)
        file_path = os.path.join(upload_dir, safe_filename)

        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        try:
            document = Document(
                filename=file.filename,
                file_path=file_path,
                file_type=file_type,
                file_size=get_file_size(file_path),
                process_status=DocumentStatus.UPLOADED,
            )
            db.add(document)
            await db.flush()
            results.append({"id": document.id, "filename": file.filename, "status": "uploaded"})
        except Exception:
            if os.path.exists(file_path):
                os.remove(file_path)
            raise

    await db.commit()

    for item in results:
        background_tasks.add_task(_process_document_bg, item["id"])

    return results


@router.get("/")
async def list_documents(page: int = 1, page_size: int = 20, db: AsyncSession = Depends(get_db)):
    from sqlalchemy import func

    count_result = await db.execute(select(func.count()).select_from(Document))
    total = count_result.scalar()

    result = await db.execute(select(Document).offset((page - 1) * page_size).limit(page_size))
    documents = result.scalars().all()
    return {
        "items": [
            {
                "id": document.id,
                "filename": document.filename,
                "file_type": document.file_type,
                "file_size": document.file_size,
                "upload_time": document.upload_time,
                "created_at": document.upload_time,
                "process_status": document.process_status.value,
            }
            for document in documents
        ],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.get("/{document_id}")
async def get_document(document_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Document).where(Document.id == document_id))
    document = result.scalar_one_or_none()
    if not document:
        raise HTTPException(status_code=404, detail="文档不存在")

    return {
        "id": document.id,
        "filename": document.filename,
        "file_type": document.file_type,
        "file_size": document.file_size,
        "upload_time": document.upload_time,
        "created_at": document.upload_time,
        "process_status": document.process_status.value,
        "content_text": document.content_text,
    }


@router.post("/{document_id}/process")
async def process_document(document_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Document).where(Document.id == document_id))
    document = result.scalar_one_or_none()
    if not document:
        raise HTTPException(status_code=404, detail="文档不存在")

    if document.process_status == DocumentStatus.PROCESSING:
        raise HTTPException(status_code=409, detail="文档正在处理中")

    document.process_status = DocumentStatus.PROCESSING
    await db.commit()

    try:
        from app.services.document_processor import get_document_processor

        process_result = await get_document_processor().process_document(document.file_path, document.file_type)
        document.content_text = process_result["content"]
        document.process_status = DocumentStatus.PROCESSED
        await db.commit()
        return {
            "status": "success",
            "char_count": process_result["char_count"],
            "chunk_count": process_result["chunk_count"],
        }
    except Exception as exc:
        document.process_status = DocumentStatus.FAILED
        await db.commit()
        raise HTTPException(status_code=500, detail=f"处理失败: {exc}") from exc


@router.delete("/{document_id}")
async def delete_document(document_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Document).where(Document.id == document_id))
    document = result.scalar_one_or_none()
    if not document:
        raise HTTPException(status_code=404, detail="文档不存在")

    if document.file_path:
        upload_dir = os.path.abspath(_get_upload_dir())
        file_abs = os.path.abspath(document.file_path)
        if not file_abs.startswith(upload_dir):
            raise HTTPException(status_code=400, detail="文件路径异常")
        if os.path.exists(file_abs):
            os.remove(file_abs)

    await db.delete(document)
    await db.commit()
    return {"status": "success"}
