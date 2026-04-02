# 全自动文档学习系统（Auto Learning System）PRD + 技术方案

## 一、项目目标

构建一个**本地优先、低成本、可扩展、可开源**的系统，实现：

* 自动抓取任意技术文档（如 LlamaIndex / LangGraph / API Docs）
* 自动分析结构
* 自动生成学习笔记（中文）
* 自动写入 Obsidian
* 支持增量更新
* 支持工作流编排（n8n / 自定义）

---

## 二、核心设计原则

1. **低 Token 成本优先**

   * 先压缩再翻译
   * 分块处理
   * 本地模型优先

2. **模块化（适合开源）**

   * crawler（抓取）
   * processor（处理）
   * llm（推理）
   * exporter（输出）

3. **完全可替换**

   * 支持 OpenAI / Ollama / 其他模型
   * 支持不同存储（Obsidian / DB）

---

## 三、系统架构

```
                ┌──────────────┐
                │   Scheduler   │
                └──────┬───────┘
                       ↓
                ┌──────────────┐
                │   Crawler     │
                └──────┬───────┘
                       ↓
                ┌──────────────┐
                │   Chunker     │
                └──────┬───────┘
                       ↓
                ┌──────────────┐
                │ Summarizer L1 │（压缩）
                └──────┬───────┘
                       ↓
                ┌──────────────┐
                │ Summarizer L2 │（整理+翻译）
                └──────┬───────┘
                       ↓
                ┌──────────────┐
                │ Formatter     │（Obsidian）
                └──────┬───────┘
                       ↓
                ┌──────────────┐
                │ Exporter      │
                └──────────────┘
```

---

## 四、功能模块拆解

### 1. 文档抓取模块（Crawler）

#### 功能

* 抓取单页
* **递归采集整站（新功能）**
* 支持 sitemap
* 支持本地 Markdown/PDF 文件读取

#### URL 递归采集功能（v1.1 新增）

**目标**: 为 URLCrawler 增加递归采集功能，支持处理单个URL时自动发现并采集匹配的子页面

**核心能力**:
- **手动指定链接模式**: 用户通过 `--pattern` 参数指定要匹配的链接模式（支持 glob 格式）
- **合并为单个文档**: 所有匹配的页面内容合并后统一生成一个摘要
- **限制递归深度**: 默认限制深度为3，可通过 `--max-depth` 调整

**CLI 参数**:

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `--pattern` | str | None | 链接匹配模式（可重复使用，如 `"*.md"`, `"*/docs/*"`） |
| `--max-depth` | int | 3 | 最大递归深度 |
| `--no-merge` | flag | False | 不合并，单独处理每个文档 |

**内容合并格式**:
```markdown
# 文档标题

> 来源: https://docs.example.com/guide/
> 采集页面数: 5

---

## Page 1: Introduction
来源: https://docs.example.com/guide/intro

[页面内容...]

---

## Page 2: Installation
来源: https://docs.example.com/guide/install

[页面内容...]
```

**配置文件支持**:
```yaml
# URL递归采集配置 (可选)
crawl:
  patterns:
    - "*.md"
    - "*/docs/*"
  max_depth: 3
```

**核心方法**:
- `crawl_recursive()`: 递归爬取URL及匹配的子页面
- `discover_links()`: 从页面发现所有链接
- `match_pattern()`: 判断URL是否匹配任一模式（使用 fnmatch）
- `merge_documents()`: 合并多个文档为一个

#### 输入

```
{
  "url": "https://docs.xxx.com",
  "depth": 2
}
```

#### 输出

```
[
  {
    "url": "...",
    "title": "...",
    "content": "..."
  }
]
```

---

### 2. 文本分块模块（Chunker）

#### 目的

* 控制 token
* 提高总结质量

#### 策略

* 每块 1000~2000 tokens
* 按段落切分

---

### 3. 一级总结（压缩层）

#### Prompt

```
Summarize into key bullet points:
- Keep only core concepts
- Remove examples
- Max 200 words
```

#### 输出

* 高密度信息摘要（英文）

---

### 4. 二级总结（学习笔记层）

#### Prompt

```
将以下内容整理为中文学习笔记：

要求：
1. 分模块
2. 提取核心概念
3. 输出 Markdown
```

---

### 5. Obsidian 格式化模块

#### 输出标准

```
# 标题

## 模块
- 概念

## [[关联概念]]

#标签
```

---

### 6. 导出模块（Exporter）

支持：

* Obsidian（.md）
* JSON
* Markdown 文件夹结构

---

## 五、数据模型设计

### Document

```python
@dataclass
class Document:
    id: str                   # 基于source的hash
    source_type: SourceType   # URL | LOCAL | PDF
    source_path: str         # URL或本地路径
    title: str
    content: str             # Markdown文本
    content_hash: str        # 用于缓存
    format: DocFormat        # HTML | MARKDOWN
    images: List[str] = field(default_factory=list)  # 图片路径列表
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)
```

---

### Chunk

```python
@dataclass
class Chunk:
    id: str
    doc_id: str
    index: int               # 块序号
    text: str
    token_count: int
    content_hash: str        # 用于块级缓存
```

---

### ProcessResult

```python
@dataclass
class ProcessResult:
    document_id: str
    document_title: str
    source_url: str
    chunks_count: int
    l1_summary: SummaryL1          # 压缩摘要
    l2_summary: Optional[SummaryL2]  # 中文笔记
    output_path: Optional[str] = None
    cached: bool = False
```

---

### CrawlResult

```python
@dataclass
class CrawlResult:
    document: Document
    images_downloaded: int = 0
    errors: List[str] = field(default_factory=list)
```

---

## 六、核心模块详细设计

### 1. Config 模块

**职责**: 配置管理（YAML + 环境变量）

**配置结构**:
```yaml
llm:
  base_url: http://localhost:11434/v1
  api_key: ollama
  model: llama3
  temperature: 0.7

output:
  format: obsidian      # markdown | obsidian
  path: ./vault/
  filename_template: "{title}.md"

features:
  chinese_notes: true   # 是否生成中文笔记

chunker:
  target_tokens: 1500
  overlap_chars: 200

cache:
  enabled: true
  db_path: ./data/cache.db

# URL递归采集配置 (v1.1新增)
crawl:
  patterns:
    - "*.md"
    - "*/docs/*"
  max_depth: 3

# v2预留接口
knowledge_base:
  enabled: false
  vector_store: chroma
```

**环境变量支持**:
- `LLM_API_KEY` - LLM API密钥
- `OLLAMA_HOST` - Ollama主机地址
- 配置文件支持 `${VAR_NAME}` 语法

---

### 2. Crawler 模块

**支持类型**:
- URL单页抓取（HTML → Markdown）
- **URL递归抓取**（v1.1新增，支持depth和pattern匹配）
- 本地Markdown文件读取
- 本地目录递归遍历
- **本地PDF文件读取**（文本+图片）

**核心组件**:
- `BaseCrawler`: 抽象基类
- `URLCrawler`: URL抓取 + 图片下载
- `LocalCrawler`: 本地文件遍历
- `PDFCrawler`: PDF解析

**URL递归采集关键方法**:
```python
def crawl_recursive(
    self,
    url: str,
    patterns: list[str] = None,    # glob模式匹配
    max_depth: int = 3,
    visited: set = None
) -> CrawlResult:
    """递归爬取URL及匹配的子页面"""

def discover_links(self, soup: BeautifulSoup, base_url: str) -> list[str]:
    """从页面发现所有链接"""

def match_pattern(self, url: str, patterns: list[str]) -> bool:
    """使用fnmatch判断URL是否匹配任一模式"""

def merge_documents(self, documents: list[Document], base_url: str) -> Document:
    """合并多个文档为一个"""
```

---

### 3. Chunker 模块

**分块策略**:
- 目标大小: 1500 tokens（约6000字符）
- 切分方式: 优先按段落边界切分
- 重叠策略: 200字符重叠保持上下文

**实现**:
```python
class Chunker:
    def __init__(self, target_tokens: int = 1500, overlap_chars: int = 200):
        self.target_chars = target_tokens * 4  # 1 token ≈ 4字符
    
    def chunk(self, doc_id: str, content: str) -> Iterator[Chunk]:
        """将文档切分为块"""
```

---

### 4. Summarizer 模块（两层级）

#### L1: 压缩层

**Prompt**:
```
Summarize the following technical documentation into key bullet points:
- Keep only core concepts and key information
- Remove examples, code snippets unless critical
- Max 200 words
- Output in English
- Use concise bullet points
```

**输出**: `SummaryL1` (bullets, key_concepts, metadata)

#### L2: 学习笔记层

**Prompt**:
```
将以下内容整理为中文学习笔记：
1. 分模块组织（使用二级标题）
2. 提取核心概念
3. 使用简洁清晰的中文
4. 适当使用列表和强调
5. 输出标准Markdown格式
```

**输出**: `SummaryL2` (overview, sections, key_concepts)

**开关控制**: `features.chinese_notes: bool`

---

### 5. LLM 模块

**设计原则**: OpenAI兼容接口，单一客户端支持所有服务

**支持场景**:
| 场景 | base_url | 说明 |
|------|----------|------|
| Ollama | `http://localhost:11434/v1` | 本地模型（默认） |
| DeepSeek | 用户配置 | 国产大模型 |
| SiliconFlow | 用户配置 | 国内API服务 |

**接口**:
```python
class LLMClient:
    def __init__(self, base_url: str, api_key: str, model: str, temperature: float = 0.7)
    def complete(self, prompt: str) -> str
    def complete_json(self, prompt: str, schema: Type[T]) -> T  # 结构化输出
    def count_tokens(self, text: str) -> int
```

---

### 6. Exporter 模块

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

{L2中文笔记内容}

## 关键概念 (Key Concepts)

- [[概念1]]: 简要说明

---

#processed #auto-learning
```

**图片处理**:
- 网页图片下载到 `./assets/{doc_id}/` 目录
- Obsidian中使用 `![[image.png]]` 引用

---

### 7. Cache 模块

**存储**: SQLite

**表结构**:
```sql
CREATE TABLE documents (
    id TEXT PRIMARY KEY,
    source TEXT,
    content_hash TEXT UNIQUE,
    title TEXT,
    content TEXT,
    images TEXT,
    metadata TEXT,
    created_at TIMESTAMP,
    l1_summary TEXT,
    l2_summary TEXT,
    output_path TEXT,
    processed_at TIMESTAMP
);

CREATE TABLE chunks (
    id TEXT PRIMARY KEY,
    doc_id TEXT,
    index INTEGER,
    content_hash TEXT UNIQUE,
    text TEXT,
    token_count INTEGER,
    l1_summary TEXT,
    created_at TIMESTAMP
);
```

**缓存策略**:
- 基于内容hash判断是否需要重新处理
- 支持强制刷新

---

### 8. API 模块（可选，v2预留）

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

---

## 七、核心工作流（Pipeline）

```python
class Pipeline:
    def __init__(self, config):
        self.crawler = Crawler(config)
        self.chunker = Chunker(config)
        self.summarizer = Summarizer(config)
        self.exporter = Exporter(config)
        self.cache = Cache(config)

    async def process_document(self, source: str) -> ProcessResult:
        # 1. 抓取/读取
        crawl_result = self.crawler.crawl(source)
        doc = crawl_result.document
        
        # 2. 检查缓存
        cached = self.cache.get(doc.content_hash)
        if cached:
            return ProcessResult(..., cached=True)
        
        # 3. 分块
        chunks = list(self.chunker.chunk(doc.id, doc.content))
        
        # 4. L1总结（按块，带缓存）
        chunk_summaries = []
        for chunk in chunks:
            cached_chunk = self.cache.get_chunk(chunk.content_hash)
            if cached_chunk:
                chunk_summaries.append(cached_chunk)
            else:
                summary = await self.summarizer.summarize_chunk(chunk)
                self.cache.save_chunk(chunk, summary)
                chunk_summaries.append(summary)
        
        # 5. 合并L1
        l1_summaries = [s.l1 for s in chunk_summaries]
        merged_l1 = await self.summarizer.merge_l1_summaries(l1_summaries)
        
        # 6. L2总结
        l2_summaries = [s.l2 for s in chunk_summaries if s.l2.overview]
        merged_l2 = await self.summarizer.merge_l2_summaries(l2_summaries)
        
        # 7. 导出
        result = ProcessResult(
            document_id=doc.id,
            document_title=doc.title,
            source_url=source,
            chunks_count=len(chunks),
            l1_summary=merged_l1,
            l2_summary=merged_l2,
        )
        export_result = self.exporter.export(result)
        result.output_path = export_result.file_path
        
        # 8. 保存缓存
        self.cache.save(doc.content_hash, result)
        
        return result
```

**简化工作流（可导入 Claude Code）**:
```
1. fetch_docs(url)
2. split_chunks(docs)
3. summarize_level1(chunks)
4. merge_summary()
5. summarize_level2()
6. format_obsidian()
7. save_file()
```



---

## 八、项目目录结构（GitHub友好）

```
auto-learning-system/
│
├── README.md
├── requirements.txt
├── pyproject.toml
├── config.yaml.example
├── main.py
│
├── src/
│   ├── __init__.py
│   ├── config.py              # 配置管理
│   ├── pipeline.py            # 核心工作流
│   ├── models.py              # 数据模型 (Document/Chunk/ProcessResult)
│   ├── cli.py                 # CLI接口 (Typer)
│   │
│   ├── crawler/
│   │   ├── __init__.py
│   │   ├── base.py            # 抽象基类
│   │   ├── url_crawler.py     # URL抓取+图片下载+递归采集(v1.1)
│   │   ├── local_crawler.py   # 本地文件遍历
│   │   └── pdf_crawler.py     # PDF解析
│   │
│   ├── chunker/
│   │   ├── __init__.py
│   │   └── chunker.py         # 文本分块
│   │
│   ├── summarizer/
│   │   ├── __init__.py
│   │   ├── summarizer.py      # 两层级摘要主类
│   │   └── prompts.py         # Prompt模板
│   │
│   ├── llm/
│   │   ├── __init__.py
│   │   └── client.py          # OpenAI兼容客户端
│   │
│   ├── exporter/
│   │   ├── __init__.py
│   │   ├── base.py            # 抽象基类
│   │   ├── markdown.py        # 标准Markdown输出
│   │   └── obsidian.py        # Obsidian格式输出
│   │
│   ├── cache/
│   │   ├── __init__.py
│   │   └── sqlite_cache.py    # SQLite缓存
│   │
│   └── api/
│       ├── __init__.py
│       ├── server.py          # FastAPI应用
│       └── routes.py          # API端点
│
├── tests/
│   ├── conftest.py
│   ├── fixtures/
│   │   ├── sample_doc.md
│   │   ├── sample.html
│   │   └── sample.pdf
│   ├── test_config.py
│   ├── test_models.py
│   ├── test_crawler.py
│   ├── test_chunker.py
│   ├── test_summarizer.py
│   ├── test_llm.py
│   ├── test_exporter.py
│   ├── test_cache.py
│   └── test_pipeline.py
│
├── docs/
│   ├── PRD.md
│   └── superpowers/
│       ├── plans/             # 实现计划
│       └── specs/             # 设计规范
│
└── data/                      # 缓存和索引 (gitignore)
```

---

## 九、快速开始

### 安装

```bash
# 克隆仓库
git clone <repo>
cd auto-learning-system

# 安装依赖
pip install -r requirements.txt
# 或使用 uv
uv venv
uv pip install -e ".[dev]"
```

### 配置

```bash
# 复制配置模板
cp config.yaml.example config.yaml

# 编辑配置（可选，默认使用Ollama本地模型）
# vim config.yaml
```

### 基本使用

```bash
# 处理单个URL
python -m src.cli process https://docs.example.com/page

# 处理本地目录
python -m src.cli process ./my-docs

# 递归采集整站（v1.1功能）
python -m src.cli process https://docs.example.com \
  --pattern "*/guide/*" \
  --max-depth 3

# 多个匹配模式
python -m src.cli process https://docs.example.com \
  --pattern "*.md" \
  --pattern "*/api/*"

# 仅生成压缩摘要（跳过中文笔记）
python -m src.cli process https://docs.example.com --no-related-context

# 强制重新处理（忽略缓存）
python -m src.cli process https://docs.example.com --force

# 启动API服务（可选）
python -m src.cli serve --port 8000
```

### 查看帮助

```bash
# 主帮助
python -m src.cli --help

# process命令帮助
python -m src.cli process --help

# serve命令帮助
python -m src.cli serve --help
```

---

## 十、CLI 完整参数说明

### process 命令

```
Usage: python -m src.cli process [OPTIONS] SOURCE

Arguments:
  SOURCE    文档来源 (URL, 文件路径或目录)  [required]

Options:
  --config, -c TEXT          配置文件路径
  --verbose, -v              详细输出
  --recursive, -r            递归处理子文件夹  [default: True]
  --no-related-context       不包含相关文档上下文
  --pattern, -p TEXT         URL匹配模式 (可用于URL递归采集)
  --max-depth, -d INTEGER    URL递归最大深度  [default: 3]
  --no-merge                 不合并URL页面，单独处理
  --help                     Show this message and exit.
```

### serve 命令

```
Usage: python -m src.cli serve [OPTIONS]

Options:
  --host TEXT        主机地址  [default: 0.0.0.0]
  --port INTEGER     端口  [default: 8000]
  --config, -c TEXT  配置文件路径
  --help             Show this message and exit.
```



---

## 十一、性能优化

### 1. Token优化

* **分块处理**: 将长文档切分为1500 token的块，避免超出模型上下文限制
* **压缩优先**: L1层先压缩为英文摘要，降低L2翻译成本
* **避免重复总结**: 基于content_hash缓存，相同内容不重复处理

### 2. 缓存策略

**文档级缓存**:
```python
# hash(content) → ProcessResult
cache.get(content_hash) → ProcessResult | None
```

**块级缓存**:
```python
# hash(chunk_text) → L1_summary
cache.get_chunk(chunk_hash) → str | None
```

**缓存命中率优化**:
- 处理相同URL时，如果内容未变更，直接返回缓存结果
- 处理长文档时，未变更的块直接使用缓存摘要

### 3. 递归采集优化

**去重机制**:
- 使用 `visited` 集合防止循环链接
- 基于URL去重，避免重复抓取同一页面

**并发控制**:
- 限制递归深度（默认3层）
- 模式匹配过滤，只采集相关页面

### 4. 增量更新（v2预留）

```python
# 只处理新增/变更的文档
def process_incremental(source_dir: str):
    for doc in scan_documents(source_dir):
        if is_modified(doc) or not in_cache(doc):
            process_document(doc)
```

---

## 十二、测试策略

### 单元测试

- 每个模块独立测试
- Mock外部依赖（LLM、网络）
- 使用fixtures提供测试数据

### 测试数据

```
tests/fixtures/
├── sample_doc.md
├── sample.html
├── sample.pdf
├── sample_config.yaml
└── expected_output.md
```

### 核心测试用例

**Config模块**:
- `test_load_config_from_file`: 从YAML加载配置
- `test_config_with_env_override`: 环境变量覆盖
- `test_default_values`: 默认值测试

**Crawler模块**:
- `test_fetch_single_page`: 单页抓取
- `test_discover_links`: 链接发现
- `test_match_pattern`: 模式匹配（fnmatch）
- `test_merge_documents`: 文档合并
- `test_crawl_recursive`: 递归采集

**Chunker模块**:
- `test_chunker_basic`: 基本分块
- `test_chunker_respects_paragraph_boundary`: 段落边界
- `test_single_short_document`: 短文档处理

**Summarizer模块**:
- `test_l1_summarize`: L1摘要
- `test_l2_summarize`: L2中文笔记
- `test_merge_l1_summaries`: 合并L1摘要

---

## 十三、决策记录

| 决策 | 原因 |
|------|------|
| **Python实现** | 生态丰富，LLM SDK支持好 |
| **SQLite缓存** | 零配置，单文件，适合本地优先 |
| **先压缩后翻译** | 降低Token成本，L1英文压缩，L2中文笔记 |
| **L2中文笔记可选** | 满足不同用户需求，通过配置开关 |
| **知识库v2实现** | 保持v1专注核心pipeline，v2扩展知识库 |
| **HTTP API可选** | 不强制依赖，轻量化部署 |
| **OpenAI兼容接口** | 一个客户端覆盖Ollama/DeepSeek/SiliconFlow等 |
| **URL递归采集v1.1** | 基于用户需求，支持整站学习 |
| **fnmatch模式匹配** | 简单直观，支持glob语法，Python内置 |
| **文档合并策略** | 合并为单文档便于整体理解和生成统一摘要 |

---

## 十三、版本规划

### v1.0 - 核心Pipeline (已完成)

**功能**:
* 单文档学习（URL/本地Markdown/PDF）
* 两层级摘要（L1压缩 + L2中文笔记）
* Obsidian/Markdown输出
* SQLite缓存
* CLI接口

**核心模块**:
* Config, Crawler, Chunker, Summarizer, LLM, Exporter, Cache

---

### v1.1 - URL递归采集 (当前开发)

**新增功能**:
* **递归采集整站**: 支持 `--pattern` 参数匹配链接模式
* **多页面合并**: 自动合并匹配的子页面为单个文档
* **深度控制**: `--max-depth` 参数限制递归深度
* **独立处理**: `--no-merge` 参数支持不合并单独处理

**CLI示例**:
```bash
# 递归采集整站
documents process https://docs.example.com --pattern "*/guide/*" --max-depth 3

# 采集多个模式
documents process https://docs.example.com -p "*.md" -p "*/api/*"

# 不合并，单独处理每个页面
documents process https://docs.example.com --pattern "*.md" --no-merge
```

---

### v2.0 - 知识库系统 (规划中)

**新增模块**:
```
src/
└── knowledge_base/
    ├── __init__.py
    ├── indexer.py        # 向量索引构建 (Chroma/Weaviate)
    ├── query_engine.py   # RAG查询引擎
    ├── embedding.py      # 文本向量化
    └── models.py         # 知识库数据模型
```

**功能**:
* **向量索引**: 将处理过的文档构建向量索引
* **RAG查询**: 支持自然语言查询，检索相关知识
* **增量更新**: 只处理新增/变更的文档
* **多文档融合**: 跨文档知识关联
* **HTTP API**: 完整的REST API接口

**API端点**:
```python
POST /index            # 构建知识库索引
POST /query            # RAG查询
GET  /documents        # 列出已索引文档
DELETE /documents/{id} # 删除文档
```

**使用场景**:
```bash
# 构建知识库索引
curl -X POST http://localhost:8000/index \
  -H "Content-Type: application/json" \
  -d '{"source": "./vault"}'

# RAG查询
curl -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{"query": "什么是RAG?"}'
```

---

### v3.0 - 高级功能 (远期规划)

**功能**:
* **NotebookLM式对话学习**: 与文档进行对话式学习
* **自动知识图谱生成**: 自动提取实体关系，生成知识图谱
* **n8n深度集成**: 支持复杂的工作流编排
* **多语言支持**: 支持除中文外的其他目标语言
* **GitHub同步**: 与GitHub文档仓库自动同步

---

## 十四、项目总结

### 系统定位

> **"自动学习任何技术文档，并沉淀为个人知识库"**

Auto Learning System 是一个本地优先、低成本、可扩展的文档学习工具，支持从URL、本地Markdown、PDF等多种来源自动抓取、分析、总结技术文档，并生成结构化的Obsidian学习笔记。

### 核心特性

| 特性 | 说明 |
|------|------|
| **多源输入** | 支持URL、本地Markdown、PDF文件 |
| **递归采集** | 整站采集，支持模式匹配和深度控制 |
| **两层级摘要** | L1英文压缩 + L2中文学习笔记 |
| **智能缓存** | 基于内容hash的文档级和块级缓存 |
| **多种输出** | 标准Markdown和Obsidian格式 |
| **完全可配置** | 支持Ollama/DeepSeek/SiliconFlow等任意OpenAI兼容服务 |

### 技术亮点

1. **低成本优先**: 先压缩后翻译，分块处理，最大化利用本地模型
2. **模块化设计**: 8个核心模块清晰分离，易于维护和扩展
3. **渐进式演进**: v1专注核心pipeline，v2扩展知识库，v3高级功能
4. **开源友好**: 完整的测试覆盖，清晰的文档，GitHub标准项目结构

### 适用场景

- 快速学习新技术文档（如LlamaIndex、LangGraph等）
- 构建个人技术知识库
- 团队文档知识沉淀
- API文档自动生成笔记

### 快速体验

```bash
# 安装
pip install -r requirements.txt

# 处理单个文档
python -m src.cli process https://docs.example.com/guide

# 递归采集整站
python -m src.cli process https://docs.example.com \
  --pattern "*/guide/*" --max-depth 3
```

---

**文档版本**: v1.1  
**最后更新**: 2026-03-31  
**状态**: 持续迭代中
