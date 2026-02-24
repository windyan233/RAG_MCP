"""RAG service: build/load txtai embeddings index and search books."""

import json
import logging
from pathlib import Path

from txtai.embeddings import Embeddings

from .book_processor import load_book_chunks
from .config import EMBEDDING_MODEL, CHUNK_SIZE, CHUNK_OVERLAP, CHUNK_SIZE_ZH, CHUNK_OVERLAP_ZH

logger = logging.getLogger(__name__)

BOOKS_DIR = Path(__file__).parent.parent.parent / "books"
INDEXES_DIR = Path(__file__).parent.parent.parent / "indexes"


def _index_dir(book_name: str) -> Path:
    """Return the directory path where the txtai index for a book is stored."""
    # Sanitize book_name to a safe directory name
    safe_name = book_name.replace("/", "_").replace("\\", "_")
    return INDEXES_DIR / safe_name


def _meta_path(book_name: str) -> Path:
    return _index_dir(book_name) / "meta.json"


def find_book_file(book_name: str) -> Path | None:
    """Locate a book file in the books directory by name (with or without extension)."""
    books_dir = BOOKS_DIR
    if not books_dir.exists():
        return None

    # Exact match first
    for ext in (".epub", ".pdf"):
        candidate = books_dir / (book_name + ext)
        if candidate.exists():
            return candidate

    # Try treating book_name as a full filename
    candidate = books_dir / book_name
    if candidate.exists():
        return candidate

    # Case-insensitive partial match on stem
    book_name_lower = book_name.lower()
    for f in books_dir.iterdir():
        if f.suffix.lower() in (".epub", ".pdf"):
            if book_name_lower in f.stem.lower():
                return f

    return None


def list_available_books() -> list[dict]:
    """Return info about all book files in the books directory."""
    books_dir = BOOKS_DIR
    if not books_dir.exists():
        return []
    result = []
    for f in sorted(books_dir.iterdir()):
        if f.suffix.lower() in (".epub", ".pdf"):
            idx_dir = _index_dir(f.name)
            indexed = (idx_dir / "config").exists() or (idx_dir / "embeddings").exists()
            result.append({
                "name": f.name,
                "format": f.suffix.lstrip(".").upper(),
                "indexed": indexed,
                "path": str(f),
            })
    return result


def build_index(book_name: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP,
                chunk_size_zh: int = CHUNK_SIZE_ZH, overlap_zh: int = CHUNK_OVERLAP_ZH) -> dict:
    """
    Parse a book file, build txtai embeddings index, save to disk.
    Returns summary info.
    """
    book_file = find_book_file(book_name)
    if book_file is None:
        raise FileNotFoundError(
            f"Book '{book_name}' not found in {BOOKS_DIR}. "
            f"Available files: {[f.name for f in BOOKS_DIR.iterdir() if f.is_file()]}"
        )

    logger.info(f"Parsing '{book_file.name}'...")
    chunks = load_book_chunks(book_file, chunk_size=chunk_size, overlap=overlap,
                              chunk_size_zh=chunk_size_zh, overlap_zh=overlap_zh)
    if not chunks:
        raise ValueError(f"No text could be extracted from '{book_file.name}'")

    logger.info(f"Extracted {len(chunks)} chunks. Building embeddings index...")

    embeddings = Embeddings(
        path=EMBEDDING_MODEL,
        content=True,  # store original text alongside vectors
    )

    # txtai expects (id, text, tags) tuples or just text strings
    documents = [(str(c["chunk_id"]), c["text"], None) for c in chunks]
    embeddings.index(documents)

    idx_dir = _index_dir(book_file.name)
    idx_dir.mkdir(parents=True, exist_ok=True)
    embeddings.save(str(idx_dir))

    # Save metadata
    meta = {
        "book_name": book_file.name,
        "book_path": str(book_file),
        "num_chunks": len(chunks),
        "chunk_size": chunk_size,
        "overlap": overlap,
        "chunk_size_zh": chunk_size_zh,
        "overlap_zh": overlap_zh,
        "model": EMBEDDING_MODEL,
    }
    with open(_meta_path(book_file.name), "w") as f:
        json.dump(meta, f, indent=2)

    logger.info(f"Index saved to '{idx_dir}'")
    return meta


def search_book(book_name: str, query: str, top_k: int = 3) -> list[dict]:
    """
    Search a book's index for the given query.
    Returns a list of dicts with 'text', 'score', 'chunk_id'.
    Raises FileNotFoundError if the book has not been indexed yet.
    """
    # Resolve actual book file name (for directory lookup)
    book_file = find_book_file(book_name)
    if book_file is None:
        raise FileNotFoundError(
            f"Book '{book_name}' not found in {BOOKS_DIR}."
        )

    idx_dir = _index_dir(book_file.name)
    if not idx_dir.exists():
        raise FileNotFoundError(
            f"No index found for '{book_file.name}'. "
            f"Please run index_book('{book_name}') first."
        )

    embeddings = Embeddings(
        path=EMBEDDING_MODEL,
        content=True,
    )
    embeddings.load(str(idx_dir))

    results = embeddings.search(query, top_k)

    # txtai returns list of (id, score) when content=False,
    # or list of dicts when content=True
    output = []
    for item in results:
        if isinstance(item, dict):
            output.append({
                "text": item.get("text", ""),
                "score": round(float(item.get("score", 0)), 4),
                "chunk_id": item.get("id", ""),
            })
        else:
            # fallback: (id, score)
            output.append({
                "text": str(item[0]),
                "score": round(float(item[1]), 4),
                "chunk_id": "",
            })

    return output
