"""Topic service: manage multi-source topic collections and their indexes."""

import hashlib
import json
import logging
import shutil
from pathlib import Path

from .config import CHUNK_SIZE, CHUNK_OVERLAP, CHUNK_SIZE_ZH, CHUNK_OVERLAP_ZH, EMBEDDING_MODEL
from .book_processor import load_book_chunks
from .text_processor import load_text_file_chunks, SUPPORTED_TEXT_EXTENSIONS
from .rag_service import build_index_from_chunks, upsert_chunks_to_index, search_index, INDEXES_DIR

logger = logging.getLogger(__name__)

TOPICS_DIR = Path(__file__).parent.parent.parent / "topics"
TOPIC_INDEX_PREFIX = "topic__"

BOOK_EXTENSIONS = {".epub", ".pdf"}
INDEXED_SOURCES_FILE = "indexed_sources.json"


def _file_hash(path: Path) -> str:
    """SHA-256 hash of a file's bytes, used to detect modifications."""
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


def _load_indexed_sources(idx_dir: Path) -> dict[str, str]:
    """Return {filename: hash} from the tracking file in the index directory."""
    f = idx_dir / INDEXED_SOURCES_FILE
    if f.exists():
        return json.loads(f.read_text())
    return {}


def _save_indexed_sources(idx_dir: Path, data: dict[str, str]) -> None:
    idx_dir.mkdir(parents=True, exist_ok=True)
    (idx_dir / INDEXED_SOURCES_FILE).write_text(json.dumps(data, indent=2))


def _load_chunks_for_file(
    file_path: Path,
    chunk_size: int, overlap: int,
    chunk_size_zh: int, overlap_zh: int,
) -> list[dict]:
    """Chunk a single source file (book or text)."""
    suffix = file_path.suffix.lower()
    if suffix in BOOK_EXTENSIONS:
        return load_book_chunks(file_path, chunk_size, overlap, chunk_size_zh, overlap_zh)
    elif suffix in SUPPORTED_TEXT_EXTENSIONS:
        return load_text_file_chunks(file_path, chunk_size, overlap, chunk_size_zh, overlap_zh)
    return []


def _topic_dir(topic_name: str) -> Path:
    safe = topic_name.replace("/", "_").replace("\\", "_")
    return TOPICS_DIR / safe


def _topic_index_dir(topic_name: str) -> Path:
    safe = topic_name.replace("/", "_").replace("\\", "_")
    return INDEXES_DIR / f"{TOPIC_INDEX_PREFIX}{safe}"


def find_topic(topic_name: str) -> Path | None:
    """Locate a topic directory. Supports exact and case-insensitive partial match."""
    if not TOPICS_DIR.exists():
        return None
    candidate = _topic_dir(topic_name)
    if candidate.is_dir():
        return candidate
    name_lower = topic_name.lower()
    for d in TOPICS_DIR.iterdir():
        if d.is_dir() and name_lower in d.name.lower():
            return d
    return None


def create_topic(topic_name: str) -> Path:
    """Create a new topic directory. Returns the path."""
    topic_dir = _topic_dir(topic_name)
    topic_dir.mkdir(parents=True, exist_ok=True)
    return topic_dir


def add_topic_source(topic_name: str, content: str, source_name: str) -> dict:
    """Write content as a source file and auto-trigger incremental or full indexing.

    Returns a dict with keys: path, action, new_chunks, total_chunks.
    - action="incremental_upsert": new source appended to existing index (fast)
    - action="full_rebuild":       existing source updated; full reindex needed
    - action="initial_build":      no index existed yet; built from all sources
    """
    topic_dir = find_topic(topic_name)
    if topic_dir is None:
        topic_dir = create_topic(topic_name)

    dest = topic_dir / source_name
    is_new_source = not dest.exists()
    dest.write_text(content, encoding="utf-8")

    idx_dir = _topic_index_dir(topic_dir.name)
    index_exists = (idx_dir / "config").exists() or (idx_dir / "embeddings").exists()

    if index_exists and is_new_source:
        # Fast path: only embed and upsert this one new file
        chunks = _load_chunks_for_file(dest, CHUNK_SIZE, CHUNK_OVERLAP, CHUNK_SIZE_ZH, CHUNK_OVERLAP_ZH)
        upsert_chunks_to_index(chunks, idx_dir)

        indexed = _load_indexed_sources(idx_dir)
        indexed[source_name] = _file_hash(dest)
        _save_indexed_sources(idx_dir, indexed)

        meta_file = idx_dir / "meta.json"
        old_meta = json.loads(meta_file.read_text()) if meta_file.exists() else {}
        sources = list_topic_sources(topic_dir)
        new_meta = {
            **old_meta,
            "topic_name": topic_dir.name,
            "num_sources": len(sources),
            "source_files": [s["name"] for s in sources],
            "num_chunks": old_meta.get("num_chunks", 0) + len(chunks),
        }
        meta_file.write_text(json.dumps(new_meta, indent=2))

        logger.info(f"Incremental upsert: {len(chunks)} new chunks for '{source_name}' in topic '{topic_dir.name}'")
        return {
            "path": str(dest),
            "action": "incremental_upsert",
            "new_chunks": len(chunks),
            "total_chunks": new_meta["num_chunks"],
        }
    else:
        # Full rebuild: source was updated (can't remove old vectors) or no index yet
        action = "full_rebuild" if index_exists else "initial_build"
        meta = build_topic_index(topic_dir.name)
        logger.info(f"{action}: {meta['num_chunks']} chunks in topic '{topic_dir.name}'")
        return {
            "path": str(dest),
            "action": action,
            "new_chunks": meta["num_chunks"],
            "total_chunks": meta["num_chunks"],
        }


def add_topic_file(topic_name: str, file_path: str) -> dict:
    """Copy an existing file into a topic and auto-trigger incremental or full indexing.

    Returns a dict with keys: path, action, new_chunks, total_chunks.
    Supports all formats: .epub, .pdf, .txt, .md, .markdown, .html, .htm
    """
    src = Path(file_path)
    if not src.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    all_ext = BOOK_EXTENSIONS | SUPPORTED_TEXT_EXTENSIONS
    if src.suffix.lower() not in all_ext:
        raise ValueError(
            f"Unsupported format '{src.suffix}'. Supported: {', '.join(sorted(all_ext))}"
        )

    topic_dir = find_topic(topic_name)
    if topic_dir is None:
        topic_dir = create_topic(topic_name)

    dest = topic_dir / src.name
    is_new_source = not dest.exists()
    shutil.copy2(src, dest)

    idx_dir = _topic_index_dir(topic_dir.name)
    index_exists = (idx_dir / "config").exists() or (idx_dir / "embeddings").exists()

    if index_exists and is_new_source:
        chunks = _load_chunks_for_file(dest, CHUNK_SIZE, CHUNK_OVERLAP, CHUNK_SIZE_ZH, CHUNK_OVERLAP_ZH)
        upsert_chunks_to_index(chunks, idx_dir)

        indexed = _load_indexed_sources(idx_dir)
        indexed[src.name] = _file_hash(dest)
        _save_indexed_sources(idx_dir, indexed)

        meta_file = idx_dir / "meta.json"
        old_meta = json.loads(meta_file.read_text()) if meta_file.exists() else {}
        sources = list_topic_sources(topic_dir)
        new_meta = {
            **old_meta,
            "topic_name": topic_dir.name,
            "num_sources": len(sources),
            "source_files": [s["name"] for s in sources],
            "num_chunks": old_meta.get("num_chunks", 0) + len(chunks),
        }
        meta_file.write_text(json.dumps(new_meta, indent=2))

        logger.info(f"Incremental upsert: {len(chunks)} new chunks for '{src.name}' in topic '{topic_dir.name}'")
        return {
            "path": str(dest),
            "action": "incremental_upsert",
            "new_chunks": len(chunks),
            "total_chunks": new_meta["num_chunks"],
        }
    else:
        action = "full_rebuild" if index_exists else "initial_build"
        meta = build_topic_index(topic_dir.name)
        logger.info(f"{action}: {meta['num_chunks']} chunks in topic '{topic_dir.name}'")
        return {
            "path": str(dest),
            "action": action,
            "new_chunks": meta["num_chunks"],
            "total_chunks": meta["num_chunks"],
        }


def list_topic_sources(topic_dir: Path) -> list[dict]:
    """List all supported source files in a topic directory."""
    all_ext = BOOK_EXTENSIONS | SUPPORTED_TEXT_EXTENSIONS
    sources = []
    for f in sorted(topic_dir.iterdir()):
        if f.is_file() and f.suffix.lower() in all_ext:
            sources.append({"name": f.name, "format": f.suffix.lstrip(".").upper(), "path": str(f)})
    return sources


def build_topic_index(topic_name: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP,
                      chunk_size_zh: int = CHUNK_SIZE_ZH, overlap_zh: int = CHUNK_OVERLAP_ZH) -> dict:
    """Full rebuild: chunk all sources and rebuild the unified index from scratch."""
    topic_dir = find_topic(topic_name)
    if topic_dir is None:
        raise FileNotFoundError(f"Topic '{topic_name}' not found in {TOPICS_DIR}.")

    sources = list_topic_sources(topic_dir)
    if not sources:
        raise ValueError(f"Topic '{topic_dir.name}' has no supported source files.")

    all_chunks: list[dict] = []
    for src in sources:
        chunks = _load_chunks_for_file(
            Path(src["path"]), chunk_size, overlap, chunk_size_zh, overlap_zh
        )
        all_chunks.extend(chunks)

    if not all_chunks:
        raise ValueError(f"No text extracted from any source in topic '{topic_dir.name}'.")

    idx_dir = _topic_index_dir(topic_dir.name)
    meta = {
        "topic_name": topic_dir.name,
        "num_sources": len(sources),
        "source_files": [s["name"] for s in sources],
        "num_chunks": len(all_chunks),
        "chunk_size": chunk_size,
        "model": EMBEDDING_MODEL,
    }
    build_index_from_chunks(all_chunks, idx_dir, meta)

    # Record each source's hash so add_topic_source can detect new vs updated sources
    indexed = {s["name"]: _file_hash(Path(s["path"])) for s in sources}
    _save_indexed_sources(idx_dir, indexed)

    return meta


def search_topic(topic_name: str, query: str, top_k: int = 3) -> list[dict]:
    """Search a topic's unified index."""
    topic_dir = find_topic(topic_name)
    if topic_dir is None:
        raise FileNotFoundError(f"Topic '{topic_name}' not found in {TOPICS_DIR}.")
    idx_dir = _topic_index_dir(topic_dir.name)
    if not idx_dir.exists():
        raise FileNotFoundError(
            f"No index for topic '{topic_dir.name}'. Run index_topic first."
        )
    return search_index(idx_dir, query, top_k)


def list_available_topics() -> list[dict]:
    """List all topics with source counts and index status."""
    if not TOPICS_DIR.exists():
        return []
    result = []
    for d in sorted(TOPICS_DIR.iterdir()):
        if not d.is_dir():
            continue
        sources = list_topic_sources(d)
        idx_dir = _topic_index_dir(d.name)
        indexed = (idx_dir / "config").exists() or (idx_dir / "embeddings").exists()
        result.append({
            "name": d.name,
            "num_sources": len(sources),
            "sources": [s["name"] for s in sources],
            "indexed": indexed,
        })
    return result
