import asyncio
import os
import logging
import subprocess
import tempfile
from typing import Dict, Any

import fitz  # PyMuPDF
import mammoth

logger = logging.getLogger(__name__)

class DocumentProcessor:
    def __init__(self):
        self.ocr = None

    def _get_ocr(self):
        if self.ocr is None:
            from rapidocr_onnxruntime import RapidOCR
            self.ocr = RapidOCR()
        return self.ocr

    async def process_document(self, file_path: str, file_type: str) -> Dict[str, Any]:
        try:
            if file_type == "pdf":
                content = await self._process_pdf(file_path)
            elif file_type == "word":
                content = await self._process_word(file_path)
            elif file_type == "word_legacy":
                content = await self._process_word_legacy(file_path)
            elif file_type == "text":
                content = await self._process_text(file_path)
            elif file_type == "image":
                content = self._process_image(file_path)
            else:
                raise ValueError(f"不支持的文件类型: {file_type}")

            cleaned_content = self._clean_text(content)
            chunks = self._split_text(cleaned_content)

            return {
                "content": cleaned_content,
                "chunks": chunks,
                "chunk_count": len(chunks),
                "char_count": len(cleaned_content)
            }
        except Exception as e:
            logger.error(f"文档处理失败: {e}")
            raise

    def _process_pdf_sync(self, file_path: str) -> str:
        with fitz.open(file_path) as doc:
            texts = []
            for page_num in range(len(doc)):
                page = doc.load_page(page_num)
                text = page.get_text()

                if len(text.strip()) < 50:
                    pix = page.get_pixmap()
                    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
                        img_path = tmp.name
                    pix.save(img_path)
                    try:
                        ocr_text = self._process_image(img_path)
                        texts.append(ocr_text)
                    finally:
                        if os.path.exists(img_path):
                            os.remove(img_path)
                else:
                    texts.append(text)
            return "\n\n".join(texts)

    async def _process_pdf(self, file_path: str) -> str:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self._process_pdf_sync, file_path)

    def _process_word_sync(self, file_path: str) -> str:
        with open(file_path, "rb") as doc_file:
            result = mammoth.extract_raw_text(doc_file)
            return result.value

    async def _process_word(self, file_path: str) -> str:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self._process_word_sync, file_path)

    def _process_word_legacy_sync(self, file_path: str) -> str:
        try:
            result = subprocess.run(
                ["antiword", file_path],
                capture_output=True, text=True, timeout=30
            )
            if result.returncode == 0 and result.stdout.strip():
                return result.stdout
            raise RuntimeError(f"antiword failed: {result.stderr}")
        except FileNotFoundError:
            raise RuntimeError("antiword not installed, cannot process .doc files")

    async def _process_word_legacy(self, file_path: str) -> str:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self._process_word_legacy_sync, file_path)

    def _process_text_sync(self, file_path: str) -> str:
        for encoding in ("utf-8", "gb18030", "gbk"):
            try:
                with open(file_path, "r", encoding=encoding) as f:
                    return f.read()
            except (UnicodeDecodeError, UnicodeError):
                continue
        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            return f.read()

    async def _process_text(self, file_path: str) -> str:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self._process_text_sync, file_path)

    def _process_image(self, file_path: str) -> str:
        ocr = self._get_ocr()
        result, elapse = ocr(file_path)
        if result is None or len(result) == 0:
            return ""

        texts = []
        for box, text, score in result:
            if text:
                texts.append(text)

        return "\n".join(texts)

    def _clean_text(self, text: str) -> str:
        import re
        if not text:
            return ""
        text = re.sub(r'[^\S\n]+', ' ', text)
        text = re.sub(r'\n{3,}', '\n\n', text)
        return text.strip()

    def _split_text(self, text: str, chunk_size: int = 2000, overlap: int = 200):
        if not text:
            return []

        chunks = []
        start = 0
        text_len = len(text)

        while start < text_len:
            end = start + chunk_size
            if end < text_len:
                last_period = text.rfind('。', start, end)
                if last_period == -1:
                    last_period = text.rfind('.', start, end)
                if last_period != -1 and last_period > start:
                    end = last_period + 1

            chunk = text[start:end].strip()
            if chunk:
                chunks.append(chunk)
            start = end - overlap

        return chunks

document_processor = None

def get_document_processor() -> DocumentProcessor:
    global document_processor
    if document_processor is None:
        document_processor = DocumentProcessor()
    return document_processor
