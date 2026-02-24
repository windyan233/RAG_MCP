# RAG MCP

## 设计哲学

### 起点：一对一的苏格拉底式学习

本项目受到栋哥 [@dontbesilent](https://www.xiaohongshu.com/user/profile/dontbesilent) 的"任何领域十倍速入门"的启发（[链接](http://xhslink.com/o/1IwXr29GdG8)）。如何学得比任何人都快10倍？答案是：靠AI，因为AI agent可以低成本模拟一对一辅导和掌握学习法。Agent能读写本地文件，为你定制化学习计划，主动发起定制化的提问，并根据你的回答来生成难度递进的学习内容，实现个性化教学。

### 问题：模型的知识是模糊的

虽然我们可以默认Claude Code知道所有书本的内容。但在实践中，当你让 Claude 讲解一本书，它给出的内容来自训练数据的模糊记忆，细节会漂移，引用会捏造，某些小众书籍甚至根本没被训练到。你以为在学"这本书"。因此，才有个这个改进的方案。

### 解法：让 AI 基于你指定的原文回答

RAG（检索增强生成）解决的正是这个问题。它的逻辑是：**先检索，再生成。** 每次回答前，先从你提供的原始资料中精确召回最相关的段落，再让模型基于这些段落作答。这样，模型的每一句话都有据可查，幻觉被大幅压制，答案的质量和可信度本质上取决于你投入的资料质量。

这个项目做的，就是把这套机制轻量化、本地化，并通过 MCP 无缝接入 Claude Code 的对话流。

### 延伸：从"读书"到"学习任何话题"

更进一步，知识从来不只存在于书里。一个话题的最佳学习资料，可能是某篇博客、一个播客的逐字稿、一份内部文档、或者几篇论文的组合。

所以这个项目的组织单元不是"书"，而是 **Topic**——你围绕一个主题，把所有你认为高质量的信息源汇聚在一起，统一索引，然后用对话的方式把它们的知识提取出来。格式不限，来源不限。

### 核心洞察：人的角色转变

在这套系统里，AI 负责检索、理解、表达；而人的核心价值在于：寻找高质量的信息源以及持续不断的进步。

未来，学习的门槛会越来越低，学习的效率会越来越高，学习的深度上限也会越来越高。**希望我们都能成为终身学习者。**

---

基于 [txtai](https://github.com/neuml/txtai) 的语义检索服务，封装为 [MCP](https://modelcontextprotocol.io/) 服务器，可在 Claude Code 中直接调用。

以 **Topic** 为单位组织资料，一个 topic 下可以放任意格式的文件（PDF、EPUB、TXT、MD、HTML），统一索引和检索。无需调用 LLM，直接返回召回的原文段落。

---

## 项目结构

```
RAG_MCP/
├── topics/                 # 资料目录（每个 topic 一个子目录）
│   └── machine-learning/   #   示例：放入 .txt / .md / .html / .epub / .pdf
├── indexes/                # 持久化向量索引（自动生成）
│   └── topic__{name}/      #   每个 topic 一个索引目录
├── src/rag_mcp/
│   ├── config.py           # ← 统一配置（模型、chunk size、top_k）
│   ├── book_processor.py   # EPUB / PDF 解析与分块，导出 chunk_sections() 供复用
│   ├── text_processor.py   # 文本文件解析（.txt / .md / .html）
│   ├── rag_service.py      # txtai 共享原语（索引构建 / 语义检索）
│   ├── topic_service.py    # Topic 管理：多源聚合索引与检索
│   └── mcp_server.py       # MCP 服务器（暴露 5 个工具）
├── reindex.py              # 重建索引脚本
├── .mcp.json               # Claude Code MCP 配置（自动发现）
└── pyproject.toml
```

### 核心流程

```
源文件 (.epub / .pdf / .txt / .md / .html)
      │
      ▼
book_processor.py / text_processor.py    解析文本 → 按词数/字符数分块
      │
      ▼
rag_service.py                           txtai 向量化 → 保存索引到 indexes/
      │
      ▼
mcp_server.py                            MCP 工具接口
      │
      ▼
Claude Code                              调用 search_topic / index_topic / ...
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

### 1. 添加资料

在 `topics/` 下创建以主题命名的子目录，将相关资料放入：

```bash
mkdir -p topics/machine-learning
cp blog-post.md topics/machine-learning/
cp lecture-transcript.txt topics/machine-learning/
cp textbook.pdf topics/machine-learning/
```

支持的格式：`.txt`、`.md`、`.markdown`、`.html`、`.htm`、`.epub`、`.pdf`

> 也可以通过 MCP 工具 `create_topic` 和 `add_topic_source` 在对话中直接创建和添加。

### 2. 在 Claude Code 中使用

`.mcp.json` 已配置好，在本项目目录下打开 Claude Code 后 MCP 服务会**自动加载**。

直接对话即可调用以下工具：

#### `list_topics` — 查看所有 topic 及索引状态

```
列出所有 topic
```

#### `create_topic` — 创建新 topic

```
创建一个叫 machine-learning 的 topic
```

| 参数 | 类型 | 说明 |
|------|------|------|
| `topic_name` | string | Topic 名称（用作目录名） |

#### `add_topic_source` — 向 topic 添加文本资料（自动索引）

```
把这段博客内容添加到 machine-learning topic 里，文件名叫 blog-intro.md
```

| 参数 | 类型 | 说明 |
|------|------|------|
| `topic_name` | string | Topic 名称 |
| `content` | string | 文本内容 |
| `source_name` | string | 文件名（如 `blog.md`、`transcript.txt`） |

**添加后自动触发索引**，根据情况选择最优策略：

| 情形 | 策略 | 说明 |
|------|------|------|
| 首次添加，无索引 | `initial_build` | 全量建立索引 |
| 新文件，索引已存在 | `incremental_upsert` | 只 embed 新文件并 upsert，速度快 |
| 更新已有文件 | `full_rebuild` | FAISS 不支持删除旧向量，需全量重建 |

返回示例：
```json
{
  "path": "topics/machine-learning/blog-intro.md",
  "action": "incremental_upsert",
  "new_chunks": 3,
  "total_chunks": 15
}
```

> 也可以直接将文件放入 `topics/{topic_name}/` 目录，再调用 `index_topic` 全量索引。

#### `add_topic_file` — 从本地路径添加文件（自动索引）

```
把 /Users/me/papers/attention.pdf 添加到 research topic
```

| 参数 | 类型 | 说明 |
|------|------|------|
| `topic_name` | string | Topic 名称 |
| `file_path` | string | 文件的绝对路径 |

文件会被**复制**到 `topics/{topic_name}/`，文件名保持不变，然后触发与 `add_topic_source` 相同的增量索引逻辑。支持所有格式：`.epub`、`.pdf`、`.txt`、`.md`、`.html`。

与 `add_topic_source` 的区别：

| | `add_topic_source` | `add_topic_file` |
|--|---|---|
| 输入 | 原始文本字符串 | 本地文件路径 |
| 适合 | txt/md，paste 或 Claude 生成内容 | 任意已有文件，尤其是 epub/pdf |
| 文件名 | 自己指定 | 沿用原文件名 |

#### `index_topic` — 强制全量重建索引

```
对 machine-learning topic 建立索引
```

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `topic_name` | string | 必填 | Topic 名称 |
| `chunk_size` | integer | 800 | 每个文本块的词数 |

适用场景：
- 手动往 `topics/` 目录里放了文件（epub/pdf 等无法通过 `add_topic_source` 传内容）
- 修改了 `config.py` 中的 chunk size 或 embedding 模型后需要重建
- 想强制从零重建整个 topic 的索引

#### `search_topic` — 在 topic 中语义检索

```
在 machine-learning topic 里搜索：什么是梯度下降？返回 5 段
```

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `topic_name` | string | 必填 | Topic 名称 |
| `query` | string | 必填 | 查询语句 |
| `top_k` | integer | 3 | 返回段落数量（1–20） |

返回示例：

```
Top 3 results for: "什么是梯度下降"

--- Result 1 (score: 0.6251) ---
梯度下降是一种优化算法，通过迭代地沿着损失函数的负梯度方向更新参数...

--- Result 2 (score: 0.5731) ---
在机器学习中，梯度下降法被广泛用于最小化目标函数...
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

**语言自动检测**：每个 section（章节/页面）中 CJK 字符占比 > 20% 时自动切换为中文模式，中英混排也能正确处理，无需手动配置。

修改后重建索引：

```bash
# 重建所有 topic 索引
python reindex.py

# 只重建指定 topic
python reindex.py machine-learning
python reindex.py "topic-a" "topic-b"
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

