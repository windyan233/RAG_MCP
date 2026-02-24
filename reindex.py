#!/usr/bin/env python
"""
重新索引书籍脚本。

用法：
  # 索引所有书籍
  python reindex.py

  # 索引指定书籍（部分书名即可）
  python reindex.py Principles
  python reindex.py "Principles" "Another Book"
"""

import sys
import logging
from pathlib import Path

# 确保 src/ 在 import 路径中
sys.path.insert(0, str(Path(__file__).parent / "src"))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

from rag_mcp.config import EMBEDDING_MODEL, CHUNK_SIZE, CHUNK_OVERLAP, CHUNK_SIZE_ZH, CHUNK_OVERLAP_ZH
from rag_mcp.rag_service import build_index, list_available_books


def main():
    print("=" * 60)
    print(f"  Embedding model   : {EMBEDDING_MODEL}")
    print(f"  Chunk size  (EN)  : {CHUNK_SIZE} words  / overlap {CHUNK_OVERLAP}")
    print(f"  Chunk size  (ZH)  : {CHUNK_SIZE_ZH} chars / overlap {CHUNK_OVERLAP_ZH}")
    print("=" * 60)

    targets = sys.argv[1:]  # 命令行传入的书名（可多个）

    if targets:
        books_to_index = targets
    else:
        # 索引 books/ 目录下所有书籍
        available = list_available_books()
        if not available:
            logger.error("books/ 目录下没有找到任何书籍（.epub / .pdf）")
            sys.exit(1)
        books_to_index = [b["name"] for b in available]
        print(f"\n未指定书名，将索引全部 {len(books_to_index)} 本书籍：")
        for name in books_to_index:
            print(f"  - {name}")

    print()
    success, failed = 0, 0
    for book_name in books_to_index:
        print(f">>> 正在索引：{book_name}")
        try:
            meta = build_index(book_name, chunk_size=CHUNK_SIZE, overlap=CHUNK_OVERLAP)
            print(f"    完成：{meta['num_chunks']} chunks\n")
            success += 1
        except Exception as e:
            print(f"    失败：{e}\n")
            failed += 1

    print("=" * 60)
    print(f"  完成 {success} 本，失败 {failed} 本")
    print("=" * 60)


if __name__ == "__main__":
    main()
