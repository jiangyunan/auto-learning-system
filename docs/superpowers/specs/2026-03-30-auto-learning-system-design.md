# 全自动文档学习系统 v1 设计文档

**日期**: 2026-03-30
**版本**: v1.0
**状态**: 待实现

---

## 1. 项目概述

### 1.1 目标

构建一个本地优先、低成本、可扩展的系统，实现：
- 自动抓取/读取技术文档（URL或本地）
- 自动分析结构并生成学习笔记
- 自动输出到Obsidian
- 支持增量更新和缓存
- 为v2知识库功能预留接口

### 1.2 核心设计原则

1. **低Token成本优先** - 先压缩再翻译，分块处理，本地模型优先
2. **模块化** - 清晰的模块边界，便于开源和维护
3. **完全可替换** - LLM Provider、输出格式均可配置
4. **渐进式** - v1专注核心pipeline，v2扩展知识库

---

## 2. 系统架构

### 2.1 整体架构图

```
┌─────────────────────────────────────────────────────────────┐
│                     Auto Learning System                     │
├─────────────────────────────────────────────────────────────┤
│  Input Layer      │  Processing Layer    │  Output Layer    │
│  ─────────────    │  ────────────────    │  ────────────    │
│  • URL Crawler    │  • Chunker           │  • Std Markdown  │
│  • Local MD Dir   │  • L1 Summarizer     │  • Obsidian MD   │
│                   │  • L2 (中文笔记/opt)  │                  │
│                   │                      │  Optional:       │
│                   │  Cache: SQLite       │  • HTTP API      │
│                   │  LLM: Multi-provider │    (v2预留)      │
└─────────────────────────────────────────────────────────────┘
```

### 2.2 处理流程

```
fetch (url/dir) → chunk → L1 summarize → [L2 summarize] → format → export
                      ↓                        ↓
                   cache check            optional (默认开启)
```

---

## 3. 模块设计

### 3.1 Crawler 模块

**职责**: 文档输入源统一接口

**支持类型**:
- URL单页抓取（HTML → Markdown）
- URL递归抓取（可选depth）
- 本地Markdown文件读取
- 本地目录递归遍历
- **本地PDF文件读取（文本+图片OCR）**

**输出格式**:
```python
class Document:
    id: str           # hash(url/path)
    source: str       # url or local path
    title: str
    content: str      # markdown text
    images: List[str] # 图片路径列表（可选）
    metadata: dict    # {fetch_time, content_type, ...}
```

**关键实现**:
- URL抓取使用 `requests` + `beautifulsoup4`
- HTML to Markdown 使用 `markdownify`
- 本地读取使用 `pathlib` 递归遍历
- **PDF解析使用 `pymupdf`（fitz），支持文本提取和图片OCR**
- 统一输出为markdown格式

### 3.2 Chunker 模块

**职责**: 将长文档切分为适合LLM处理的块

**分块策略**:
- 目标大小: 1000-2000 tokens（约4000-8000字符）
- 切分方式: 按段落边界切分
- 重叠策略: 可选重叠100-200字符保持上下文

**输出格式**:
```python
class Chunk:
    doc_id: str
    index: int        # 块序号
    text: str
    token_count: int
```

**关键实现**:
- Token计数使用tiktoken（OpenAI模型）或字符估算（本地模型）
- 优先在段落边界切分，避免断句

### 3.3 Summarizer 模块

**职责**: 两层级摘要生成

#### L1: 压缩层（必须）

**Prompt**:
```
Summarize the following technical documentation into key bullet points:
- Keep only core concepts and key information
- Remove examples, code snippets unless critical
- Max 200 words
- Output in English

Content:
{text}
```

**输出**: 高密度英文摘要

#### L2: 学习笔记层（可选，默认开启）

**Prompt**:
```
将以下内容整理为中文学习笔记：

要求：
1. 分模块组织（使用二级标题）
2. 提取核心概念
3. 使用简洁清晰的中文
4. 适当使用列表和强调
5. 输出标准Markdown

内容：
{text}
```

**输出**: 结构化中文学习笔记

**开关控制**: `features.chinese_notes: bool`

### 3.4 LLM 模块

**职责**: 统一LLM调用接口，OpenAI兼容格式

**设计原则**: 单一客户端，支持所有OpenAI兼容API

**支持场景**:
| 场景 | base_url | 说明 |
|------|----------|------|
| Ollama | `http://localhost:11434/v1` | 本地模型（默认） |
| 自定义 | 用户配置 | 任意OpenAI兼容服务 |

**接口设计**:
```python
from openai import OpenAI

class LLMClient:
    """OpenAI兼容接口客户端"""

    def __init__(
        self,
        base_url: str = "http://localhost:11434/v1",
        api_key: str = "ollama",
        model: str = "llama3",
        temperature: float = 0.7,
    ):
        self.client = OpenAI(base_url=base_url, api_key=api_key)
        self.model = model
        self.temperature = temperature

    def complete(self, prompt: str, **kwargs) -> str:
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            temperature=kwargs.get("temperature", self.temperature),
        )
        return response.choices[0].message.content

    def count_tokens(self, text: str) -> int:
        # 简单字符估算，或使用tiktoken
        return len(text) // 4  # 粗略估算
```

**预设常量**:
```python
LLM_PRESETS = {
    "ollama": {
        "base_url": "http://localhost:11434/v1",
        "api_key": "ollama"
    }
}
```

### 3.5 Exporter 模块

**职责**: 输出格式化

**输出格式**:

1. **Standard Markdown**:
   ```markdown
   # Title

   ## Summary

   ## Key Concepts

   ## Notes
   ```

2. **Obsidian Format**:
   ```markdown
   ---
   title: Document Title
   source: https://docs.example.com/page.html
   date: 2026-03-30
   tags:
     - documentation
     - topic
   ---

   # Document Title

   > 原始链接: https://docs.example.com/page.html

   ## 摘要 (Summary)

   {L1摘要内容}

   ## 学习笔记 (Notes)

   {L2中文笔记内容（如开启）}

   ## 关键概念 (Key Concepts)

   - [[概念1]]: 简要说明
   - [[概念2]]: 简要说明

   ---

   #processed #auto-learning
   ```

**配置**: `output.format: "markdown" | "obsidian"`

**图片处理**:
- 网页图片下载到 `./assets/` 目录
- Obsidian中使用 `![[image.png]]` 引用
- 图片按文档ID组织: `assets/{doc_id}/image_1.png`

### 3.6 Cache 模块

**职责**: 避免重复处理相同内容

**存储**: SQLite

**表结构**:
```sql
CREATE TABLE documents (
    id TEXT PRIMARY KEY,
    source TEXT,
    content_hash TEXT,
    processed_at TIMESTAMP,
    l1_summary TEXT,
    l2_summary TEXT,
    output_path TEXT
);

CREATE TABLE chunks (
    id TEXT PRIMARY KEY,
    doc_id TEXT,
    index INTEGER,
    content_hash TEXT,
    l1_summary TEXT
);
```

**缓存策略**:
- 基于内容hash判断是否需要重新处理
- 支持强制刷新

### 3.7 Config 模块

**职责**: 配置管理（YAML + 环境变量）

**配置文件** (`config.yaml`):
```yaml
llm:
  base_url: http://localhost:11434/v1  # Ollama默认
  api_key: ollama                      # Ollama无需真实key
  model: llama3
  temperature: 0.7

input:
  type: url             # url | local
  url: null             # URL输入时使用
  path: null            # 本地输入时使用
  recursive: true       # 是否递归
  max_depth: 2          # 递归深度

output:
  format: obsidian      # markdown | obsidian
  path: ./vault/        # 输出目录
  filename_template: "{title}.md"

features:
  chinese_notes: true   # 是否生成中文笔记

chunker:
  target_tokens: 1500
  overlap_chars: 200

cache:
  enabled: true
  db_path: ./data/cache.db

# v2预留接口
knowledge_base:
  enabled: false        # v2启用
  vector_store: chroma  # chroma | qdrant | weaviate
```

**环境变量**:
- `LLM_API_KEY` - LLM API密钥（如使用非Ollama服务）
- `OLLAMA_HOST` - Ollama主机地址（可选，默认localhost:11434）

优先级: 环境变量 > 配置文件

### 3.8 API 模块（可选）

**职责**: HTTP API接口，为v2知识库预留

**框架**: FastAPI

**端点设计**:

```python
# v1端点
POST /process          # 处理文档
GET  /status/{job_id}  # 查询状态
GET  /health           # 健康检查

# v2预留端点
POST /index            # 构建知识库索引
POST /query            # RAG查询
GET  /documents        # 列出已索引文档
DELETE /documents/{id} # 删除文档
```

**启动方式**:
```bash
python -m src.api  # 或通过配置启用
```

---

## 4. 数据模型

### 4.1 Document

```python
@dataclass
class Document:
    id: str
    source: str           # URL或本地路径
    title: str
    content: str          # 原始内容
    content_hash: str     # 用于缓存
    metadata: Dict[str, Any]
    created_at: datetime
```

### 4.2 Chunk

```python
@dataclass
class Chunk:
    id: str
    doc_id: str
    index: int
    text: str
    token_count: int
    content_hash: str
```

### 4.3 ProcessResult

```python
@dataclass
class ProcessResult:
    document: Document
    chunks: List[Chunk]
    l1_summary: str       # 压缩摘要
    l2_summary: Optional[str]  # 中文笔记（可选）
    output_path: str
    cached: bool          # 是否来自缓存
```

---

## 5. 工作流编排

### 5.1 核心Pipeline

```python
class Pipeline:
    def __init__(self, config):
        self.crawler = Crawler(config)
        self.chunker = Chunker(config)
        self.summarizer = Summarizer(config)
        self.exporter = Exporter(config)
        self.cache = Cache(config)

    def run(self, source: str) -> ProcessResult:
        # 1. 抓取/读取
        doc = self.crawler.fetch(source)

        # 2. 检查缓存
        if cached := self.cache.get(doc.content_hash):
            return cached

        # 3. 分块
        chunks = self.chunker.split(doc)

        # 4. L1总结（按块）
        l1_summaries = []
        for chunk in chunks:
            if cached_chunk := self.cache.get_chunk(chunk.content_hash):
                l1_summaries.append(cached_chunk.l1_summary)
            else:
                summary = self.summarizer.l1_summarize(chunk)
                self.cache.save_chunk(chunk, summary)
                l1_summaries.append(summary)

        # 5. 合并L1
        merged_l1 = "\n\n".join(l1_summaries)

        # 6. L2总结（可选）
        l2_summary = None
        if self.config.features.chinese_notes:
            l2_summary = self.summarizer.l2_summarize(merged_l1)

        # 7. 格式化输出
        output_path = self.exporter.export(doc, merged_l1, l2_summary)

        # 8. 保存缓存
        result = ProcessResult(
            document=doc,
            chunks=chunks,
            l1_summary=merged_l1,
            l2_summary=l2_summary,
            output_path=output_path,
            cached=False
        )
        self.cache.save(doc.content_hash, result)

        return result
```

### 5.2 主程序入口

```python
# main.py
import typer
from src.config import load_config
from src.pipeline import Pipeline

app = typer.Typer()

@app.command()
def process(
    source: str,                      # URL或本地路径
    type: str = "auto",               # auto | url | local
    config_path: str = "config.yaml",
    notes: bool = True,               # 是否生成中文笔记
    force: bool = False               # 强制重新处理
):
    config = load_config(config_path)
    config.features.chinese_notes = notes

    pipeline = Pipeline(config)
    result = pipeline.run(source, force=force)

    typer.echo(f"✓ 处理完成: {result.output_path}")
    if result.cached:
        typer.echo("  (来自缓存)")

@app.command()
def serve(
    host: str = "0.0.0.0",
    port: int = 8000,
    config_path: str = "config.yaml"
):
    """启动API服务（可选）"""
    from src.api import create_app
    import uvicorn

    config = load_config(config_path)
    app = create_app(config)
    uvicorn.run(app, host=host, port=port)

if __name__ == "__main__":
    app()
```

---

## 6. 项目结构

```
auto-learning-system/
├── README.md
├── requirements.txt
├── pyproject.toml
├── config.yaml
├── main.py
├── .env.example
│
├── src/
│   ├── __init__.py
│   ├── config.py           # 配置管理
│   ├── pipeline.py         # 核心工作流
│   │
│   ├── crawler/
│   │   ├── __init__.py
│   │   ├── base.py         # 抽象基类
│   │   ├── url_crawler.py  # URL抓取
│   │   └── local_crawler.py # 本地文件读取
│   │
│   ├── chunker/
│   │   ├── __init__.py
│   │   └── chunker.py      # 文本分块
│   │
│   ├── summarizer/
│   │   ├── __init__.py
│   │   ├── summarizer.py   # 摘要主类
│   │   └── prompts.py      # Prompt模板
│   │
│   ├── llm/
│   │   ├── __init__.py
│   │   └── client.py       # OpenAI兼容客户端
│   │
│   ├── exporter/
│   │   ├── __init__.py
│   │   ├── base.py
│   │   ├── markdown.py
│   │   └── obsidian.py
│   │
│   ├── cache/
│   │   ├── __init__.py
│   │   └── sqlite_cache.py
│   │
│   └── api/
│       ├── __init__.py
│       ├── server.py       # FastAPI应用
│       └── routes.py       # API端点
│
├── data/                   # 缓存和索引（gitignore）
├── tests/
├── docs/
└── scripts/
```

---

## 7. 依赖清单

### 7.1 核心依赖

```
# 基础
pydantic>=2.0
pyyaml
python-dotenv

# 爬虫
requests
beautifulsoup4
markdownify
pymupdf  # PDF解析

# OCR（可选，PDF图片提取）
# pytesseract  # 如需OCR需要安装tesseract

# LLM (OpenAI兼容接口)
openai

# 工具
tiktoken  # token计数
typer     # CLI

# API（可选）
fastapi
uvicorn

# 缓存
# sqlite3  # Python内置
```

### 7.2 开发依赖

```
pytest
pytest-asyncio
black
ruff
mypy
```

---

## 8. 错误处理

### 8.1 错误分类

| 错误类型 | 处理方式 | 示例 |
|----------|----------|------|
| 输入错误 | 立即返回，提示用户 | 无效URL、路径不存在 |
| 网络错误 | 重试3次后失败 | 请求超时 |
| LLM错误 | 降级或失败 | API限流、模型不可用 |
| 解析错误 | 警告，继续处理 | HTML解析失败 |

### 8.2 错误传播

```python
class AutoLearningError(Exception):
    """基础异常"""
    pass

class CrawlError(AutoLearningError):
    """抓取错误"""
    pass

class LLMError(AutoLearningError):
    """LLM调用错误"""
    pass

class ConfigError(AutoLearningError):
    """配置错误"""
    pass
```

---

## 9. 测试策略

### 9.1 单元测试

- 每个模块独立测试
- Mock外部依赖（LLM、网络）
- 使用fixtures提供测试数据

### 9.2 集成测试

- 完整pipeline测试
- 使用小型测试文档
- 测试缓存命中/未命中

### 9.3 测试数据

```
tests/fixtures/
├── sample_doc.md
├── sample_html.html
├── sample_config.yaml
└── expected_output.md
```

---

## 10. v2 扩展规划

### 10.1 知识库模块（LlamaIndex）

```
src/
└── knowledge_base/
    ├── __init__.py
    ├── indexer.py        # 向量索引构建
    ├── query_engine.py   # RAG查询
    └── models.py         # 数据模型
```

### 10.2 功能增强

- 全站递归抓取（增量更新）
- 多文档知识融合
- NotebookLM式对话学习
- 自动知识图谱生成
- n8n深度集成

### 10.3 预留接口

在v1中预留以下接口：
- `/index` - 构建索引
- `/query` - RAG查询
- `KnowledgeBase` 基类

---

## 11. 快速开始

### 安装

```bash
git clone <repo>
cd auto-learning-system
pip install -r requirements.txt
```

### 配置

```bash
cp config.yaml.example config.yaml
# 编辑 config.yaml 设置模型参数
```

### 使用

```bash
# 处理单个URL
python main.py process https://docs.example.com/page

# 处理本地目录
python main.py process ./my-docs --type local

# 自动检测类型
python main.py process https://docs.example.com  # 自动识别为url
python main.py process ./docs                    # 自动识别为local

# 仅生成压缩摘要（跳过中文笔记）
python main.py process https://docs.example.com --no-notes

# 强制重新处理（忽略缓存）
python main.py process https://docs.example.com --force

# 启动API服务
python main.py serve
```

---

## 12. 决策记录

| 决策 | 原因 |
|------|------|
| Python实现 | 生态丰富，LLM SDK支持好 |
| SQLite缓存 | 零配置，单文件，适合本地优先 |
| 先压缩后翻译 | 降低Token成本 |
| L2中文笔记可选 | 满足不同用户需求 |
| 知识库v2实现 | 保持v1专注核心pipeline |
| HTTP API可选 | 不强制依赖，轻量化部署 |
| OpenAI兼容接口 | 一个客户端覆盖Ollama/DeepSeek/SiliconFlow等所有服务 |

---

## 13. 待确认事项

- [x] Obsidian模板格式 - 见3.5节
- [x] 默认分块大小 - 1500 tokens
- [x] 支持图片提取 - 网页图片下载到本地assets目录
- [x] 支持PDF输入 - PDF解析为文本+图片OCR

---

**文档版本**: v1.0
**最后更新**: 2026-03-30