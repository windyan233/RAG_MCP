"""Book parsing and chunking for PDF and EPUB formats."""

import re
from pathlib import Path
from typing import Iterator


def _is_chinese(text: str) -> bool:
    """Return True if more than 20% of characters are CJK (Chinese/Japanese/Korean)."""
    if not text:
        return False
    cjk_count = sum(1 for c in text if "\u4e00" <= c <= "\u9fff")
    return cjk_count / len(text) > 0.2


def _chunk_text(text: str, chunk_size: int = 500, overlap: int = 50) -> list[str]:
    """Split text into overlapping chunks by word count (for English)."""
    words = text.split()
    if not words:
        return []
    chunks = []
    start = 0
    while start < len(words):
        end = min(start + chunk_size, len(words))
        chunk = " ".join(words[start:end])
        if chunk.strip():
            chunks.append(chunk.strip())
        if end == len(words):
            break
        start += chunk_size - overlap
    return chunks


def _chunk_text_zh(text: str, chunk_size: int = 500, overlap: int = 50) -> list[str]:
    """Split text into overlapping chunks by character count (for Chinese)."""
    text = text.strip()
    if not text:
        return []
    chunks = []
    start = 0
    while start < len(text):
        end = min(start + chunk_size, len(text))
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end == len(text):
            break
        start += chunk_size - overlap
    return chunks


def _clean_text(text: str) -> str:
    """Remove excessive whitespace and normalize text."""
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def parse_epub(file_path: Path) -> Iterator[str]:
    """Extract text content from an EPUB file, yielding per-chapter text."""
    import warnings
    import ebooklib
    from ebooklib import epub
    from bs4 import BeautifulSoup, XMLParsedAsHTMLWarning

    warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)

    book = epub.read_epub(str(file_path), options={"ignore_ncx": True})
    for item in book.get_items_of_type(ebooklib.ITEM_DOCUMENT):
        soup = BeautifulSoup(item.get_content(), "lxml")
        for tag in soup(["script", "style"]):
            tag.decompose()
        text = _clean_text(soup.get_text(separator=" "))
        if len(text) > 100:
            yield text


def parse_pdf(file_path: Path) -> Iterator[str]:
    """Extract text content from a PDF file, yielding per-page text."""
    import pdfplumber

    with pdfplumber.open(str(file_path)) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ""
            text = _clean_text(text)
            if len(text) > 100:
                yield text


def chunk_sections(
    sections: Iterator[str],
    source_name: str,
    chunk_size: int = 500,
    overlap: int = 50,
    chunk_size_zh: int = 500,
    overlap_zh: int = 50,
) -> list[dict]:
    """
    Convert an iterator of text sections into chunk dicts.

    Returns [{"text": ..., "source": ..., "chunk_id": ...}].
    chunk_id is stable per source: "{source_name}__{local_idx}".
    """
    chunks = []
    local_idx = 0
    for section_text in sections:
        if _is_chinese(section_text):
            section_chunks = _chunk_text_zh(section_text, chunk_size=chunk_size_zh, overlap=overlap_zh)
        else:
            section_chunks = _chunk_text(section_text, chunk_size=chunk_size, overlap=overlap)

        for chunk in section_chunks:
            chunks.append({
                "text": chunk,
                "source": source_name,
                "chunk_id": f"{source_name}__{local_idx}",
            })
            local_idx += 1

    return chunks


def load_book_chunks(
    file_path: Path,
    chunk_size: int = 500,
    overlap: int = 50,
    chunk_size_zh: int = 500,
    overlap_zh: int = 50,
) -> list[dict]:
    """
    Parse a book file and return a list of chunk dicts with keys:
      - 'text': the chunk content
      - 'source': book file name
      - 'chunk_id': sequential index

    Automatically detects Chinese vs English text and applies the
    appropriate chunking strategy per section.
    """
    suffix = file_path.suffix.lower()
    if suffix == ".epub":
        sections = parse_epub(file_path)
    elif suffix == ".pdf":
        sections = parse_pdf(file_path)
    else:
        raise ValueError(f"Unsupported file format: {suffix}. Supported: .epub, .pdf")

    return chunk_sections(sections, file_path.name, chunk_size, overlap, chunk_size_zh, overlap_zh)
