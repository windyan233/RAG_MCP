"""MCP server exposing RAG search tools for books."""

import logging
import sys
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp import types

from .rag_service import build_index, search_book, list_available_books
from .config import CHUNK_SIZE, DEFAULT_TOP_K

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger(__name__)

server = Server("rag-mcp")


@server.list_tools()
async def list_tools() -> list[types.Tool]:
    return [
        types.Tool(
            name="search_book",
            description=(
                "Search a book by semantic similarity and return the most relevant text passages. "
                "The book must be indexed first (use index_book if needed). "
                "Usage: provide the book name (or part of it) and your query."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "book_name": {
                        "type": "string",
                        "description": "Book name or partial name (e.g. 'Principles' or full filename)",
                    },
                    "query": {
                        "type": "string",
                        "description": "The search query or question",
                    },
                    "top_k": {
                        "type": "integer",
                        "description": f"Number of text passages to return (default: {DEFAULT_TOP_K})",
                        "default": DEFAULT_TOP_K,
                        "minimum": 1,
                        "maximum": 20,
                    },
                },
                "required": ["book_name", "query"],
            },
        ),
        types.Tool(
            name="index_book",
            description=(
                "Parse and index a book file for semantic search. "
                "Must be run once per book before searching. "
                "Re-running will rebuild the index."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "book_name": {
                        "type": "string",
                        "description": "Book name or partial name to index",
                    },
                    "chunk_size": {
                        "type": "integer",
                        "description": f"Number of words per text chunk (default: {CHUNK_SIZE})",
                        "default": CHUNK_SIZE,
                        "minimum": 100,
                        "maximum": 2000,
                    },
                },
                "required": ["book_name"],
            },
        ),
        types.Tool(
            name="list_books",
            description="List all available books and whether they have been indexed.",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": [],
            },
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[types.TextContent]:
    if name == "list_books":
        books = list_available_books()
        if not books:
            text = "No books found in the books directory."
        else:
            lines = ["Available books:\n"]
            for b in books:
                status = "indexed" if b["indexed"] else "not indexed"
                lines.append(f"  - {b['name']} ({b['format']}) [{status}]")
            text = "\n".join(lines)
        return [types.TextContent(type="text", text=text)]

    elif name == "index_book":
        book_name = arguments["book_name"]
        chunk_size = arguments.get("chunk_size", CHUNK_SIZE)
        logger.info(f"Indexing book: {book_name}")
        try:
            meta = build_index(book_name, chunk_size=chunk_size)
            text = (
                f"Successfully indexed '{meta['book_name']}'.\n"
                f"  Chunks: {meta['num_chunks']}\n"
                f"  Chunk size: {meta['chunk_size']} words\n"
                f"  Model: {meta['model']}"
            )
        except FileNotFoundError as e:
            text = f"Error: {e}"
        except Exception as e:
            logger.exception("Index error")
            text = f"Indexing failed: {e}"
        return [types.TextContent(type="text", text=text)]

    elif name == "search_book":
        book_name = arguments["book_name"]
        query = arguments["query"]
        top_k = arguments.get("top_k", DEFAULT_TOP_K)
        logger.info(f"Searching '{book_name}' for: {query!r} (top_k={top_k})")
        try:
            results = search_book(book_name, query, top_k=top_k)
            if not results:
                text = "No results found."
            else:
                parts = [f"Top {len(results)} results for: \"{query}\"\n"]
                for i, r in enumerate(results, 1):
                    parts.append(f"--- Result {i} (score: {r['score']}) ---")
                    parts.append(r["text"])
                    parts.append("")
                text = "\n".join(parts)
        except FileNotFoundError as e:
            text = f"Error: {e}"
        except Exception as e:
            logger.exception("Search error")
            text = f"Search failed: {e}"
        return [types.TextContent(type="text", text=text)]

    else:
        return [types.TextContent(type="text", text=f"Unknown tool: {name}")]


async def _run():
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options(),
        )


def main():
    import asyncio
    asyncio.run(_run())


if __name__ == "__main__":
    main()
