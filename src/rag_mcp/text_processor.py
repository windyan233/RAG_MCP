"""Text file parsing for plain text, Markdown, and HTML sources."""

from pathlib import Path
from typing import Iterator

from .book_processor import chunk_sections, _clean_text


SUPPORTED_TEXT_EXTENSIONS = {".txt", ".md", ".markdown", ".html", ".htm"}


def parse_text_file(file_path: Path) -> Iterator[str]:
    """Read a plain text or markdown file, yield cleaned text sections."""
    text = file_path.read_text(encoding="utf-8", errors="replace")
    text = _clean_text(text)
    if len(text) > 50:
        yield text


def parse_html_file(file_path: Path) -> Iterator[str]:
    """Read an HTML file, strip tags, yield cleaned text."""
    from bs4 import BeautifulSoup

    raw = file_path.read_text(encoding="utf-8", errors="replace")
    soup = BeautifulSoup(raw, "lxml")
    for tag in soup(["script", "style"]):
        tag.decompose()
    text = _clean_text(soup.get_text(separator=" "))
    if len(text) > 50:
        yield text


def load_text_file_chunks(
    file_path: Path,
    chunk_size: int = 500,
    overlap: int = 50,
    chunk_size_zh: int = 500,
    overlap_zh: int = 50,
) -> list[dict]:
    """Parse a text/md/html file and return chunk dicts."""
    suffix = file_path.suffix.lower()
    if suffix in (".html", ".htm"):
        sections = parse_html_file(file_path)
    elif suffix in SUPPORTED_TEXT_EXTENSIONS:
        sections = parse_text_file(file_path)
    else:
        raise ValueError(f"Unsupported text format: {suffix}")
    return chunk_sections(sections, file_path.name, chunk_size, overlap, chunk_size_zh, overlap_zh)
