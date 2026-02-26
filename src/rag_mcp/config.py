# ============================================================
# RAG MCP 配置文件 — 在这里修改所有参数
# 修改后运行 python reindex.py 重新建立索引
# ============================================================

# Embedding 模型
# 可选：
#   "sentence-transformers/all-MiniLM-L6-v2"   轻量英文（默认，~90MB）
#   "sentence-transformers/all-mpnet-base-v2"   更强英文（~420MB）
#   "BAAI/bge-base-en-v1.5"                     英文检索优秀（~430MB）
#   "BAAI/bge-m3"                               中英双语（~2.2GB）
#   "shibing624/text2vec-base-chinese"           中文专用（~400MB）
EMBEDDING_MODEL = "BAAI/bge-m3"

# 英文文本块大小（按空格分词的词数）
# 较小（200）→ 更精准但上下文少；较大（800）→ 上下文更完整
CHUNK_SIZE = 800

# 英文相邻块重叠词数
CHUNK_OVERLAP = 80

# 中文文本块大小（按字符数）
# 300~600 字为宜，500 字约一页书
CHUNK_SIZE_ZH = 500

# 中文相邻块重叠字符数
CHUNK_OVERLAP_ZH = 100

# 每次查询默认返回的段落数量（调用时可覆盖）
DEFAULT_TOP_K = 5
