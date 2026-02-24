#!/usr/bin/env python
"""
重新索引 topic 脚本。

用法：
  # 索引所有 topic
  python reindex.py

  # 索引指定 topic（部分名称即可）
  python reindex.py machine-learning
  python reindex.py "machine-learning" "web-dev"
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
from rag_mcp.topic_service import build_topic_index, list_available_topics


def main():
    print("=" * 60)
    print(f"  Embedding model   : {EMBEDDING_MODEL}")
    print(f"  Chunk size  (EN)  : {CHUNK_SIZE} words  / overlap {CHUNK_OVERLAP}")
    print(f"  Chunk size  (ZH)  : {CHUNK_SIZE_ZH} chars / overlap {CHUNK_OVERLAP_ZH}")
    print("=" * 60)

    targets = sys.argv[1:]

    if targets:
        topics_to_index = targets
    else:
        available = list_available_topics()
        if not available:
            logger.error("topics/ 目录下没有找到任何 topic")
            sys.exit(1)
        topics_to_index = [t["name"] for t in available]
        print(f"\n未指定 topic，将索引全部 {len(topics_to_index)} 个 topic：")
        for name in topics_to_index:
            print(f"  - {name}")

    print()
    success, failed = 0, 0
    for topic_name in topics_to_index:
        print(f">>> 正在索引：{topic_name}")
        try:
            meta = build_topic_index(topic_name, chunk_size=CHUNK_SIZE, overlap=CHUNK_OVERLAP)
            print(f"    完成：{meta['num_sources']} sources, {meta['num_chunks']} chunks\n")
            success += 1
        except Exception as e:
            print(f"    失败：{e}\n")
            failed += 1

    print("=" * 60)
    print(f"  完成 {success} 个，失败 {failed} 个")
    print("=" * 60)


if __name__ == "__main__":
    main()
