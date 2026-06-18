import asyncio
import logging
import os
import subprocess
import tempfile
from typing import Any

import mammoth
import pymupdf as fitz  # PyMuPDF

logger = logging.getLogger(__name__)


class DocumentProcessor:
    def __init__(self):
        self.ocr = None

    def _get_ocr(self):
        if self.ocr is None:
            from rapidocr_onnxruntime import RapidOCR

            self.ocr = RapidOCR()
        return self.ocr

    async def process_document(self, file_path: str, file_type: str) -> dict[str, Any]:
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
                loop = asyncio.get_running_loop()
                content = await loop.run_in_executor(None, self._process_image, file_path)
            else:
                raise ValueError(f"不支持的文件类型: {file_type}")

            cleaned_content = self._clean_text(content)
            chunks = self._split_text(cleaned_content)

            return {
                "content": cleaned_content,
                "chunks": chunks,
                "chunk_count": len(chunks),
                "char_count": len(cleaned_content),
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
        # Strategy 1: antiword (fast, reliable when available)
        try:
            result = subprocess.run(
                ["antiword", file_path], capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=30
            )
            if result.returncode == 0 and (result.stdout or "").strip():
                return result.stdout
            logger.warning("antiword returned empty/failed output, trying fallback")
        except FileNotFoundError:
            logger.info("antiword not available, using pure-Python .doc parser")
        except Exception as e:
            logger.warning(f"antiword error: {e}, trying fallback")

        # Strategy 2: pure-Python olefile-based text extraction
        return self._extract_doc_text_olefile(file_path)

    def _extract_doc_text_olefile(self, file_path: str) -> str:
        import struct

        try:
            import olefile
        except ImportError:
            raise RuntimeError("olefile not installed, cannot process .doc files") from None

        try:
            ole = olefile.OleFileIO(file_path)
        except Exception as e:
            # NotOleFileError inherits from OSError, distinguish it
            if "not an ole2" in str(e).lower() or "not ole" in str(e).lower():
                raise RuntimeError("Not a valid Word .doc file") from e
            raise RuntimeError(f"Failed to open .doc file: {e}") from e

        try:
            if ole.exists("EncryptionInfo"):
                raise RuntimeError("Document is password-protected")

            if not ole.exists("WordDocument"):
                raise RuntimeError("Not a valid Word .doc file")

            word_stream = ole.openstream("WordDocument").read()

            # FIB: Flags at offset 0x000A, bit 9 -> which table stream
            flags = struct.unpack_from("<H", word_stream, 0x000A)[0]
            table_name = "1Table" if (flags & 0x0200) else "0Table"

            table_stream = ole.openstream(table_name).read()

            # FIB: fcClx at 0x01A2, lcbClx at 0x01A6
            fc_clx = struct.unpack_from("<I", word_stream, 0x01A2)[0]
            lcb_clx = struct.unpack_from("<I", word_stream, 0x01A6)[0]

            if lcb_clx == 0:
                return ""

            clx = table_stream[fc_clx : fc_clx + lcb_clx]

            # Parse CLX: skip Grpprl entries (tag=0x01), find piece table (tag=0x02)
            offset = 0
            while offset < len(clx):
                tag = clx[offset]
                if tag == 0x01:
                    cb = struct.unpack_from("<H", clx, offset + 1)[0]
                    offset += 3 + cb
                elif tag == 0x02:
                    cb = struct.unpack_from("<I", clx, offset + 1)[0]
                    piece_table_data = clx[offset + 5 : offset + 5 + cb]
                    break
                else:
                    raise RuntimeError(f"Unknown CLX tag: {tag}")
            else:
                return ""

            # Piece table: (n+1) CPs (4 bytes each) + n PCDs (8 bytes each)
            # n = (cb - 4) / 12
            n = (len(piece_table_data) - 4) // 12
            if n <= 0:
                return ""

            cps = []
            for i in range(n + 1):
                cps.append(struct.unpack_from("<I", piece_table_data, i * 4)[0])

            pcd_offset = (n + 1) * 4
            texts = []
            for i in range(n):
                _pcd = struct.unpack_from("<H", piece_table_data, pcd_offset + i * 8)[0]
                fc = struct.unpack_from("<I", piece_table_data, pcd_offset + i * 8 + 2)[0]

                char_count = cps[i + 1] - cps[i]
                if char_count <= 0:
                    continue

                # fc bit 30: 0=UTF-16LE, 1=compressed (single-byte)
                is_compressed = bool(fc & 0x40000000)
                real_fc = fc & 0x3FFFFFFF

                if is_compressed:
                    raw = word_stream[real_fc : real_fc + char_count]
                    texts.append(raw.decode("latin-1"))
                else:
                    raw = word_stream[real_fc : real_fc + char_count * 2]
                    texts.append(raw.decode("utf-16-le"))

            return "".join(texts)
        finally:
            ole.close()

    async def _process_word_legacy(self, file_path: str) -> str:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self._process_word_legacy_sync, file_path)

    def _process_text_sync(self, file_path: str) -> str:
        for encoding in ("utf-8", "gb18030", "gbk"):
            try:
                with open(file_path, encoding=encoding) as f:
                    return f.read()
            except (UnicodeDecodeError, UnicodeError):
                continue
        with open(file_path, encoding="utf-8", errors="replace") as f:
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
        for _box, text, _score in result:
            if text:
                texts.append(text)

        return "\n".join(texts)

    def _clean_text(self, text: str) -> str:
        import re

        if not text:
            return ""
        text = re.sub(r"[^\S\n]+", " ", text)
        text = re.sub(r"\n{3,}", "\n\n", text)
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
                last_period = text.rfind("。", start, end)
                if last_period == -1:
                    last_period = text.rfind(".", start, end)
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
