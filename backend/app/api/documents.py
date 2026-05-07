from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List
import os
import shutil
import uuid

from app.core.database import get_db
from app.core.config import settings
from app.models.document import Document, DocumentStatus
from app.utils.file_utils import get_file_type, get_file_size

router = APIRouter()


def _generate_safe_filename(original_filename: str) -> str:
    """生成安全的文件名，防止路径遍历攻击"""
    # 获取文件扩展名
    ext = os.path.splitext(original_filename)[1].lower()
    # 使用 UUID 生成唯一文件名
    safe_name = f"{uuid.uuid4().hex}{ext}"
    return safe_name


@router.post("/upload")
async def upload_document(file: UploadFile = File(...), db: AsyncSession = Depends(get_db)):
    file_type = get_file_type(file.filename)
    if file_type == "unknown":
        raise HTTPException(status_code=400, detail="不支持的文件类型")

    # 使用安全的文件名
    safe_filename = _generate_safe_filename(file.filename)
    file_path = os.path.join(settings.UPLOAD_DIR, safe_filename)

    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    document = Document(
        filename=file.filename,  # 保留原始文件名用于显示
        file_path=file_path,     # 使用安全的路径
        file_type=file_type,
        file_size=get_file_size(file_path),
        process_status=DocumentStatus.UPLOADED
    )

    db.add(document)
    await db.commit()
    await db.refresh(document)

    return {"id": document.id, "filename": document.filename, "status": "uploaded"}


@router.post("/upload/batch")
async def upload_documents_batch(files: List[UploadFile] = File(...), db: AsyncSession = Depends(get_db)):
    results = []
    for file in files:
        file_type = get_file_type(file.filename)
        if file_type == "unknown":
            continue

        # 使用安全的文件名
        safe_filename = _generate_safe_filename(file.filename)
        file_path = os.path.join(settings.UPLOAD_DIR, safe_filename)

        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        document = Document(
            filename=file.filename,
            file_path=file_path,
            file_type=file_type,
            file_size=get_file_size(file_path),
            process_status=DocumentStatus.UPLOADED
        )
        db.add(document)
        results.append({"filename": file.filename, "status": "uploaded"})

    await db.commit()
    return results

@router.get("/")
async def list_documents(page: int = 1, page_size: int = 20, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Document).offset((page - 1) * page_size).limit(page_size))
    documents = result.scalars().all()
    return [{"id": d.id, "filename": d.filename, "file_type": d.file_type, "file_size": d.file_size,
             "upload_time": d.upload_time, "process_status": d.process_status.value} for d in documents]

@router.get("/{document_id}")
async def get_document(document_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Document).where(Document.id == document_id))
    document = result.scalar_one_or_none()
    if not document:
        raise HTTPException(status_code=404, detail="文档不存在")
    return {
        "id": document.id, "filename": document.filename, "file_type": document.file_type,
        "file_size": document.file_size, "upload_time": document.upload_time,
        "process_status": document.process_status.value, "content_text": document.content_text
    }

@router.post("/{document_id}/process")
async def process_document(document_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Document).where(Document.id == document_id))
    document = result.scalar_one_or_none()
    if not document:
        raise HTTPException(status_code=404, detail="文档不存在")

    document.process_status = DocumentStatus.PROCESSING
    await db.commit()

    try:
        from app.services.document_processor import get_document_processor
        processor = get_document_processor()
        process_result = await processor.process_document(document.file_path, document.file_type)

        document.content_text = process_result["content"]
        document.process_status = DocumentStatus.PROCESSED
        await db.commit()

        return {"status": "success", "char_count": process_result["char_count"], "chunk_count": process_result["chunk_count"]}
    except Exception as e:
        document.process_status = DocumentStatus.FAILED
        await db.commit()
        raise HTTPException(status_code=500, detail=f"处理失败: {str(e)}")

@router.delete("/{document_id}")
async def delete_document(document_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Document).where(Document.id == document_id))
    document = result.scalar_one_or_none()
    if not document:
        raise HTTPException(status_code=404, detail="文档不存在")

    if os.path.exists(document.file_path):
        os.remove(document.file_path)

    await db.delete(document)
    await db.commit()
    return {"status": "success"}
