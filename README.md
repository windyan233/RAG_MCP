# RAG MCP

基于 [txtai](https://github.com/neuml/txtai) 的书籍语义检索服务，封装为 [MCP](https://modelcontextprotocol.io/) 服务器，可在 Claude Code 中直接调用。

支持 PDF 和 EPUB 格式，无需调用 LLM，直接返回召回的原文段落。

---

## 项目结构

```
RAG_MCP/
├── books/                  # 放置书籍文件（.epub / .pdf）
├── indexes/                # 持久化向量索引（自动生成，每本书一个子目录）
├── src/rag_mcp/
│   ├── config.py           # ← 统一配置（模型、chunk size、top_k）
│   ├── book_processor.py   # 书籍解析与分块（EPUB / PDF）
│   ├── rag_service.py      # txtai 索引构建 / 加载 / 语义检索
│   └── mcp_server.py       # MCP 服务器（暴露 3 个工具）
├── reindex.py              # 重建索引脚本
├── .mcp.json               # Claude Code MCP 配置（自动发现）
└── pyproject.toml
```

### 核心流程

```
书籍文件 (.epub/.pdf)
      │
      ▼
book_processor.py       解析文本 → 按词数分块（默认 500 词，重叠 50 词）
      │
      ▼
rag_service.py          txtai 向量化（sentence-transformers）→ 保存索引到 indexes/
      │
      ▼
mcp_server.py           MCP 工具接口
      │
      ▼
Claude Code             调用 search_book / index_book / list_books
```

---

## 环境要求

- Python 3.12+
- [uv](https://github.com/astral-sh/uv)（包管理器）

---

## 安装

```bash
# 安装 uv（如未安装）
curl -LsSf https://astral.sh/uv/install.sh | sh

# 安装项目依赖
cd RAG_MCP
uv sync
```

首次运行时会自动从 HuggingFace 下载 embedding 模型（~90MB），缓存到 `~/.cache/huggingface/`。

---

## 使用方式

### 1. 添加书籍

将 `.epub` 或 `.pdf` 文件放入 `books/` 目录。

### 2. 在 Claude Code 中使用

`.mcp.json` 已配置好，在本项目目录下打开 Claude Code 后 MCP 服务会**自动加载**。

直接对话即可调用以下工具：

#### `list_books` — 查看所有书籍及索引状态

```
列出 books 目录下所有书籍
```

#### `index_book` — 对书籍建立向量索引

```
对《Principles》建立索引
```

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `book_name` | string | 必填 | 书名或部分书名 |
| `chunk_size` | integer | 500 | 每个文本块的词数 |

> 每本书只需索引一次，索引持久化保存在 `indexes/`，重启后无需重建。

#### `search_book` — 语义检索召回原文段落

```
在《Principles》中搜索：What causes empires to rise and fall？返回 5 段
```

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `book_name` | string | 必填 | 书名或部分书名 |
| `query` | string | 必填 | 查询语句 |
| `top_k` | integer | 3 | 返回段落数量（1–20） |

返回示例：

```
Top 3 results for: "What causes empires to rise and fall?"

--- Result 1 (score: 0.6251) ---
...while I can't be sure that I have the formula for what makes the world's
greatest empires and their markets rise and fall exactly right...

--- Result 2 (score: 0.5731) ---
...key variables were the distribution of land ownership and taxation...
```

---

## 修改配置与重建索引

所有参数集中在 **`src/rag_mcp/config.py`**，修改后运行 `reindex.py` 即可。

```python
# src/rag_mcp/config.py

EMBEDDING_MODEL  = "sentence-transformers/all-MiniLM-L6-v2"  # embedding 模型

# 英文：按空格分词的词数
CHUNK_SIZE       = 800    # 每个文本块的词数
CHUNK_OVERLAP    = 80     # 相邻块重叠词数

# 中文：按字符数切块（自动检测，无需手动指定语言）
CHUNK_SIZE_ZH    = 300    # 每个文本块的字符数（300~600 字为宜，约半页~一页）
CHUNK_OVERLAP_ZH = 30     # 相邻块重叠字符数

DEFAULT_TOP_K    = 5      # 默认返回段落数
```

**语言自动检测**：每个 section（章节/页面）中 CJK 字符占比 > 20% 时自动切换为中文模式，中英混排书籍也能正确处理，无需手动配置。

修改后重建索引：

```bash
# 重建所有书籍索引
python reindex.py

# 只重建指定书籍
python reindex.py Principles
python reindex.py "Book A" "Book B"
```

> 更换 `EMBEDDING_MODEL` 后必须重建索引，旧索引与模型绑定，不可混用。

### 可选 Embedding 模型

| 模型 | 大小 | 适用场景 |
|------|------|----------|
| `sentence-transformers/all-MiniLM-L6-v2` | ~90MB | 英文，快速轻量（默认） |
| `sentence-transformers/all-mpnet-base-v2` | ~420MB | 英文，质量更高 |
| `BAAI/bge-base-en-v1.5` | ~430MB | 英文，检索效果优秀 |
| `BAAI/bge-m3` | ~2.2GB | 中英双语，多语言 SOTA |
| `shibing624/text2vec-base-chinese` | ~400MB | 中文专用 |

---

## 注册为全局 MCP 服务

若需在**任意项目窗口**中使用（而不仅限于本项目目录），将服务注册到用户级别配置：

```bash
claude mcp add -s user rag-mcp \
  "/Users/yanluo/Documents/Claudecode Projects/RAG_MCP/.venv/bin/python" \
  -e "PYTHONPATH=/Users/yanluo/Documents/Claudecode Projects/RAG_MCP/src" \
  -- -m rag_mcp.mcp_server
```

> 注意：路径中如有空格，需用引号包裹整个路径（如上所示）。

---

## 测试

### 1. 确认服务已加载

在 Claude Code 中输入：

```
/mcp
```

看到 `rag-mcp` 状态为 `connected` 即表示服务正常。

### 2. 在 Claude Code 对话中直接调用

```
列出所有可用的书籍
```

```
对《Principles》建立索引
```

```
在《Principles》里搜索：What causes empires to rise and fall？返回 5 段
```

### 3. MCP Inspector（可视化调试）

```bash
npx @modelcontextprotocol/inspector \
  "/Users/yanluo/Documents/Claudecode Projects/RAG_MCP/.venv/bin/python" \
  -m rag_mcp.mcp_server
```

会打开本地网页，可手动填写参数调用每个工具，适合排查问题。

---

## 手动运行服务器（调试用）

```bash
cd RAG_MCP
PYTHONPATH=src .venv/bin/python -m rag_mcp.mcp_server
```
