# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Install dependencies
uv sync

# Run MCP server directly
.venv/bin/python -m rag_mcp.mcp_server

# Reindex all topics
python reindex.py

# Reindex specific topic (partial name match)
python reindex.py "machine-learning"
```

## Architecture

RAG semantic search service exposed via Model Context Protocol (MCP).

**Data flow:** MCP tools → `topic_service.py` → processors → txtai

- `mcp_server.py` — 6 MCP tools: `create_topic`, `add_topic_source`, `add_topic_file`, `index_topic`, `search_topic`, `list_topics`
- `topic_service.py` — Topic management: multi-source collections, incremental upsert logic, indexed_sources.json tracking
- `rag_service.py` — Shared txtai primitives (`build_index_from_chunks`, `upsert_chunks_to_index`, `search_index`)
- `book_processor.py` — Parses EPUB/PDF, detects language (CJK ratio), chunks text. Exports `chunk_sections()` for reuse
- `text_processor.py` — Parses .txt/.md/.html files, reuses `chunk_sections()`
- `config.py` — Central config: embedding model, chunk sizes, overlap values

**Storage layout:**
- `topics/{topic_name}/` — Source files (any supported format: .epub, .pdf, .txt, .md, .html)
- `indexes/topic__{topic_name}/` — Persisted txtai indexes per topic
- `indexes/topic__{topic_name}/indexed_sources.json` — Per-source SHA-256 hashes for incremental update detection

**Indexing behavior (add_topic_source / add_topic_file):**
- New file + index exists → `incremental_upsert`: only embeds the new file via `embeddings.upsert()`
- Existing file updated → `full_rebuild`: FAISS cannot delete old vectors, must rebuild
- No index yet → `initial_build`: full build from all sources
- `index_topic` always forces a full rebuild (use after manual file drops or config changes)

**Chunk ID format:** `{source_filename}__{local_idx}` (e.g. `paper.pdf__0`). Stable per source, enabling safe upsert without ID collisions.

