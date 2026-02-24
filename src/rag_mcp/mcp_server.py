"""MCP server exposing RAG search tools for topics."""

import logging
import sys
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp import types

from .topic_service import (
    create_topic, add_topic_source, add_topic_file, build_topic_index,
    search_topic, list_available_topics,
)
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
            name="list_topics",
            description="List all topics with their sources and index status.",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": [],
            },
        ),
        types.Tool(
            name="create_topic",
            description=(
                "Create a new topic directory for grouping multiple sources "
                "(books, blogs, tutorials, transcripts, etc.)."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "topic_name": {
                        "type": "string",
                        "description": "Name for the topic (used as directory name)",
                    },
                },
                "required": ["topic_name"],
            },
        ),
        types.Tool(
            name="add_topic_source",
            description=(
                "Add raw text content as a named source file to a topic. "
                "The topic will be created if it doesn't exist. "
                "Automatically indexes the new content: incremental upsert if the source "
                "is new, full rebuild if updating an existing source. "
                "Use source_name with an appropriate extension (.txt, .md, .html)."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "topic_name": {
                        "type": "string",
                        "description": "Topic name to add the source to",
                    },
                    "content": {
                        "type": "string",
                        "description": "The text content to add",
                    },
                    "source_name": {
                        "type": "string",
                        "description": "Filename for the source (e.g. 'blog-post.md', 'transcript.txt')",
                    },
                },
                "required": ["topic_name", "content", "source_name"],
            },
        ),
        types.Tool(
            name="add_topic_file",
            description=(
                "Copy an existing local file into a topic and automatically index it. "
                "Supports .epub, .pdf, .txt, .md, .html files. "
                "Use this instead of add_topic_source when the content already exists as a file on disk."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "topic_name": {
                        "type": "string",
                        "description": "Topic name to add the file to",
                    },
                    "file_path": {
                        "type": "string",
                        "description": "Absolute path to the source file on disk",
                    },
                },
                "required": ["topic_name", "file_path"],
            },
        ),
        types.Tool(
            name="index_topic",
            description=(
                "Force a full rebuild of a topic's search index from all its sources. "
                "Supports .epub, .pdf, .txt, .md, .html files. "
                "Use this after manually placing files in topics/ or after changing config."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "topic_name": {
                        "type": "string",
                        "description": "Topic name to index",
                    },
                    "chunk_size": {
                        "type": "integer",
                        "description": f"Number of words per text chunk (default: {CHUNK_SIZE})",
                        "default": CHUNK_SIZE,
                        "minimum": 100,
                        "maximum": 2000,
                    },
                },
                "required": ["topic_name"],
            },
        ),
        types.Tool(
            name="search_topic",
            description=(
                "Search a topic by semantic similarity and return the most relevant text passages. "
                "The topic must be indexed first (use index_topic if needed)."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "topic_name": {
                        "type": "string",
                        "description": "Topic name or partial name to search",
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
                "required": ["topic_name", "query"],
            },
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[types.TextContent]:
    if name == "list_topics":
        topics = list_available_topics()
        if not topics:
            text = "No topics found in the topics directory."
        else:
            lines = ["Available topics:\n"]
            for t in topics:
                status = "indexed" if t["indexed"] else "not indexed"
                lines.append(f"  - {t['name']} ({t['num_sources']} sources) [{status}]")
                for s in t["sources"]:
                    lines.append(f"      • {s}")
            text = "\n".join(lines)
        return [types.TextContent(type="text", text=text)]

    elif name == "create_topic":
        topic_name = arguments["topic_name"]
        try:
            path = create_topic(topic_name)
            text = f"Topic '{topic_name}' created at {path}"
        except Exception as e:
            text = f"Failed to create topic: {e}"
        return [types.TextContent(type="text", text=text)]

    elif name == "add_topic_source":
        topic_name = arguments["topic_name"]
        content = arguments["content"]
        source_name = arguments["source_name"]
        try:
            result = add_topic_source(topic_name, content, source_name)
            action = result["action"]
            if action == "incremental_upsert":
                text = (
                    f"Source '{source_name}' added to topic '{topic_name}'.\n"
                    f"  Indexed: {result['new_chunks']} new chunks (incremental upsert)\n"
                    f"  Total chunks in topic: {result['total_chunks']}"
                )
            else:
                label = "initial build" if action == "initial_build" else "full rebuild"
                text = (
                    f"Source '{source_name}' added to topic '{topic_name}'.\n"
                    f"  Indexed: {result['total_chunks']} chunks ({label})"
                )
        except Exception as e:
            text = f"Failed to add source: {e}"
        return [types.TextContent(type="text", text=text)]

    elif name == "add_topic_file":
        topic_name = arguments["topic_name"]
        file_path = arguments["file_path"]
        try:
            result = add_topic_file(topic_name, file_path)
            action = result["action"]
            if action == "incremental_upsert":
                text = (
                    f"File '{file_path}' added to topic '{topic_name}'.\n"
                    f"  Indexed: {result['new_chunks']} new chunks (incremental upsert)\n"
                    f"  Total chunks in topic: {result['total_chunks']}"
                )
            else:
                label = "initial build" if action == "initial_build" else "full rebuild"
                text = (
                    f"File '{file_path}' added to topic '{topic_name}'.\n"
                    f"  Indexed: {result['total_chunks']} chunks ({label})"
                )
        except (FileNotFoundError, ValueError) as e:
            text = f"Error: {e}"
        except Exception as e:
            logger.exception("add_topic_file error")
            text = f"Failed to add file: {e}"
        return [types.TextContent(type="text", text=text)]

    elif name == "index_topic":
        topic_name = arguments["topic_name"]
        chunk_size = arguments.get("chunk_size", CHUNK_SIZE)
        logger.info(f"Indexing topic: {topic_name}")
        try:
            meta = build_topic_index(topic_name, chunk_size=chunk_size)
            text = (
                f"Successfully indexed topic '{meta['topic_name']}'.\n"
                f"  Sources: {meta['num_sources']}\n"
                f"  Chunks: {meta['num_chunks']}\n"
                f"  Chunk size: {meta['chunk_size']} words\n"
                f"  Model: {meta['model']}"
            )
        except FileNotFoundError as e:
            text = f"Error: {e}"
        except Exception as e:
            logger.exception("Topic index error")
            text = f"Indexing failed: {e}"
        return [types.TextContent(type="text", text=text)]

    elif name == "search_topic":
        topic_name = arguments["topic_name"]
        query = arguments["query"]
        top_k = arguments.get("top_k", DEFAULT_TOP_K)
        logger.info(f"Searching topic '{topic_name}' for: {query!r} (top_k={top_k})")
        try:
            results = search_topic(topic_name, query, top_k=top_k)
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
            logger.exception("Topic search error")
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
