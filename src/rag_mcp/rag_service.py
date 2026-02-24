"""RAG service: shared txtai index primitives (build and search)."""

import json
import logging
from pathlib import Path

from txtai.embeddings import Embeddings

from .config import EMBEDDING_MODEL

logger = logging.getLogger(__name__)

INDEXES_DIR = Path(__file__).parent.parent.parent / "indexes"


def _index_dir(name: str) -> Path:
    """Return the directory path where a txtai index is stored."""
    safe_name = name.replace("/", "_").replace("\\", "_")
    return INDEXES_DIR / safe_name


def upsert_chunks_to_index(chunks: list[dict], idx_dir: Path) -> None:
    """Load an existing txtai index, upsert new chunks, and save back."""
    embeddings = Embeddings(
        path=EMBEDDING_MODEL,
        content=True,
    )
    embeddings.load(str(idx_dir))

    documents = [(c["chunk_id"], c["text"], None) for c in chunks]
    embeddings.upsert(documents)
    embeddings.save(str(idx_dir))

    logger.info(f"Upserted {len(chunks)} chunks into '{idx_dir}'")


def build_index_from_chunks(chunks: list[dict], idx_dir: Path, meta: dict) -> None:
    """Build a txtai embeddings index from chunk dicts and save to idx_dir."""
    embeddings = Embeddings(
        path=EMBEDDING_MODEL,
        content=True,
    )

    documents = [(str(c["chunk_id"]), c["text"], None) for c in chunks]
    embeddings.index(documents)

    idx_dir.mkdir(parents=True, exist_ok=True)
    embeddings.save(str(idx_dir))

    with open(idx_dir / "meta.json", "w") as f:
        json.dump(meta, f, indent=2)

    logger.info(f"Index saved to '{idx_dir}'")


def search_index(idx_dir: Path, query: str, top_k: int = 3) -> list[dict]:
    """Load a txtai index and search it. Returns [{"text", "score", "chunk_id"}]."""
    if not idx_dir.exists():
        raise FileNotFoundError(f"No index found at '{idx_dir}'.")

    embeddings = Embeddings(
        path=EMBEDDING_MODEL,
        content=True,
    )
    embeddings.load(str(idx_dir))

    results = embeddings.search(query, top_k)

    output = []
    for item in results:
        if isinstance(item, dict):
            output.append({
                "text": item.get("text", ""),
                "score": round(float(item.get("score", 0)), 4),
                "chunk_id": item.get("id", ""),
            })
        else:
            output.append({
                "text": str(item[0]),
                "score": round(float(item[1]), 4),
                "chunk_id": "",
            })

    return output
