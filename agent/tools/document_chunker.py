"""Structure-aware document chunker for GMP audit documents.

Splits documents by Chinese/Markdown section headings, then by paragraphs,
then by sentences for oversized sections. Each chunk carries section path
metadata for traceability in audit findings.
"""

import logging
import re
from dataclasses import dataclass

from agent.config import CHUNK_MAX_CHARS, STUFF_LIMIT

logger = logging.getLogger(__name__)

# Chinese/Markdown section heading patterns
_SECTION_RE = re.compile(
    r"^(?:"
    r"#{1,4}\s+.+|"  # Markdown: # ## ### ####
    r"[一二三四五六七八九十]+[、.]\s*.+|"  # 一、 二、 三.
    r"(?:第[一二三四五六七八九十百千]+[章节条款])[、.\s]*.*|"  # 第一章 第2节
    r"\d+(?:\.\d+)*[、.\s]\s*\S.*"  # 1. 2.1 3.2.1
    r")$",
    re.MULTILINE,
)

# Paragraph split: two or more newlines
_PARA_RE = re.compile(r"\n{2,}")

# Sentence split: Chinese/English period, question mark, exclamation
_SENTENCE_RE = re.compile(r"(?<=[。！？.!?])\s*")


@dataclass
class DocumentChunk:
    """A chunk of document content with section metadata."""

    content: str
    section_path: str = ""
    chunk_index: int = 0
    char_count: int = 0

    def __post_init__(self):
        self.char_count = len(self.content)


def select_strategy(text: str) -> str:
    """Select processing strategy based on document size.

    Returns:
        "stuff" for documents that fit in a single LLM call,
        "map_reduce" for documents that need chunked analysis.
    """
    if len(text) <= STUFF_LIMIT:
        return "stuff"
    return "map_reduce"


def chunk_document(text: str, max_chars: int = 0) -> list[DocumentChunk]:
    """Split document into structure-aware chunks.

    Strategy:
    1. Split by section headings (Chinese/Markdown)
    2. Within each section, split by paragraphs
    3. Oversized paragraphs split by sentences
    4. Each chunk carries section_path metadata

    Args:
        text: Full document text
        max_chars: Max chars per chunk (0 = use CHUNK_MAX_CHARS)

    Returns:
        List of DocumentChunk with section metadata
    """
    if not text or not text.strip():
        return []

    if max_chars <= 0:
        max_chars = CHUNK_MAX_CHARS

    # Step 1: Split by section headings
    sections = _split_by_sections(text)

    # Step 2-3: Split each section into chunks
    chunks = []
    for section_title, section_content in sections:
        section_path = section_title or ""
        sub_chunks = _split_content(section_content, max_chars)
        for sub in sub_chunks:
            if sub.strip():
                chunks.append(
                    DocumentChunk(
                        content=sub.strip(),
                        section_path=section_path,
                        chunk_index=len(chunks),
                    )
                )

    # Ensure at least one chunk
    if not chunks and text.strip():
        chunks.append(
            DocumentChunk(
                content=text.strip()[:max_chars],
                chunk_index=0,
            )
        )

    logger.info("Document split into %d chunks (max_chars=%d, total=%d chars)", len(chunks), max_chars, len(text))
    return chunks


def _split_by_sections(text: str) -> list[tuple[str | None, str]]:
    """Split text by section headings.

    Returns list of (heading_text, section_content) tuples.
    Content before the first heading has heading_text=None.
    """
    matches = list(_SECTION_RE.finditer(text))
    if not matches:
        return [(None, text)]

    sections = []

    # Content before first heading
    if matches[0].start() > 0:
        pre = text[: matches[0].start()].strip()
        if pre:
            sections.append((None, pre))

    # Each heading + its content (up to next heading)
    for i, match in enumerate(matches):
        heading = match.group().strip()
        start = match.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        content = text[start:end].strip()
        if content:
            sections.append((heading, content))

    return sections


def _split_content(text: str, max_chars: int) -> list[str]:
    """Split section content into chunks respecting max_chars.

    Strategy: split by paragraphs first, then by sentences for oversized ones.
    """
    if len(text) <= max_chars:
        return [text]

    # Split by paragraphs
    paragraphs = _PARA_RE.split(text)
    chunks = []
    current = ""

    for para in paragraphs:
        para = para.strip()
        if not para:
            continue

        # If single paragraph exceeds limit, split by sentences
        if len(para) > max_chars:
            if current:
                chunks.append(current)
                current = ""
            sentence_chunks = _split_by_sentences(para, max_chars)
            chunks.extend(sentence_chunks)
            continue

        # Try to merge with current chunk
        if current and len(current) + len(para) + 2 <= max_chars:
            current += "\n\n" + para
        else:
            if current:
                chunks.append(current)
            current = para

    if current:
        chunks.append(current)

    return chunks


def _split_by_sentences(text: str, max_chars: int) -> list[str]:
    """Split text by sentences, merging into chunks up to max_chars."""
    sentences = _SENTENCE_RE.split(text)
    chunks = []
    current = ""

    for sent in sentences:
        sent = sent.strip()
        if not sent:
            continue

        # If single sentence exceeds limit, hard truncate
        if len(sent) > max_chars:
            if current:
                chunks.append(current)
                current = ""
            chunks.append(sent[:max_chars])
            continue

        if current and len(current) + len(sent) + 1 <= max_chars:
            current += " " + sent
        else:
            if current:
                chunks.append(current)
            current = sent

    if current:
        chunks.append(current)

    return chunks


def deduplicate_findings(findings: list[dict]) -> list[dict]:
    """Remove duplicate findings based on title similarity.

    Keeps the first occurrence when titles are >80% similar.
    """
    if not findings:
        return []

    seen: list[dict] = []
    for finding in findings:
        title = finding.get("title", "")
        is_dup = False
        for existing in seen:
            existing_title = existing.get("title", "")
            if _title_similarity(title, existing_title) > 0.8:
                # Keep the one with more detail (longer description)
                if len(finding.get("description", "")) > len(existing.get("description", "")):
                    seen.remove(existing)
                    seen.append(finding)
                is_dup = True
                break
        if not is_dup:
            seen.append(finding)

    return seen


def _title_similarity(a: str, b: str) -> float:
    """Bigram Jaccard similarity, works well for Chinese titles."""
    if not a or not b:
        return 0.0
    bigrams_a = {a[i : i + 2] for i in range(len(a) - 1)}
    bigrams_b = {b[i : i + 2] for i in range(len(b) - 1)}
    if not bigrams_a or not bigrams_b:
        return 0.0
    intersection = len(bigrams_a & bigrams_b)
    union = len(bigrams_a | bigrams_b)
    return intersection / union if union > 0 else 0.0
