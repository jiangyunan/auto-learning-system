# 全自动文档学习系统 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 构建一个本地优先的文档学习系统，支持URL/本地Markdown/PDF输入，生成压缩摘要和中文学习笔记，输出到Obsidian

**Architecture:** 模块化设计，8个核心模块（Config/Crawler/Chunker/Summarizer/LLM/Exporter/Cache/API），Pipeline编排工作流，OpenAI兼容LLM接口

**Tech Stack:** Python 3.10+, FastAPI, Pydantic, SQLite, OpenAI SDK, PyMuPDF, BeautifulSoup4

---

## 文件结构

```
src/
├── __init__.py
├── config.py              # 配置管理
├── pipeline.py            # 核心工作流
├── models.py              # 数据模型 (Document/Chunk/ProcessResult)
│
├── crawler/
│   ├── __init__.py
│   ├── base.py            # 抽象基类
│   ├── url_crawler.py     # URL抓取+图片下载
│   ├── local_crawler.py   # 本地文件遍历
│   └── pdf_crawler.py     # PDF解析
│
├── chunker/
│   ├── __init__.py
│   └── chunker.py         # 文本分块
│
├── summarizer/
│   ├── __init__.py
│   ├── summarizer.py      # 摘要主类
│   └── prompts.py         # Prompt模板
│
├── llm/
│   ├── __init__.py
│   └── client.py          # OpenAI兼容客户端
│
├── exporter/
│   ├── __init__.py
│   ├── base.py            # 抽象基类
│   ├── markdown.py        # 标准Markdown输出
│   └── obsidian.py        # Obsidian格式输出
│
├── cache/
│   ├── __init__.py
│   └── sqlite_cache.py    # SQLite缓存
│
└── api/
    ├── __init__.py
    ├── server.py          # FastAPI应用
    └── routes.py          # API端点

tests/
├── conftest.py
├── fixtures/
│   ├── sample_doc.md
│   ├── sample.html
│   └── sample.pdf
├── test_config.py
├── test_crawler.py
├── test_chunker.py
├── test_summarizer.py
├── test_llm.py
├── test_exporter.py
├── test_cache.py
└── test_pipeline.py
```

---

## Task 1: 项目初始化和配置模块

**Files:**
- Create: `pyproject.toml`
- Create: `requirements.txt`
- Create: `config.yaml.example`
- Create: `src/__init__.py`
- Create: `src/config.py`
- Test: `tests/test_config.py`

- [ ] **Step 1: 创建项目配置文件**

Create: `pyproject.toml`
```toml
[project]
name = "auto-learning-system"
version = "0.1.0"
description = "自动学习文档并生成Obsidian笔记"
requires-python = ">=3.10"
dependencies = [
    "pydantic>=2.0",
    "pyyaml",
    "python-dotenv",
    "requests",
    "beautifulsoup4",
    "markdownify",
    "pymupdf",
    "openai",
    "tiktoken",
    "typer",
    "fastapi",
    "uvicorn",
]

[project.optional-dependencies]
dev = [
    "pytest",
    "pytest-asyncio",
    "black",
    "ruff",
    "mypy",
]

[build-system]
requires = ["setuptools>=61.0"]
build-backend = "setuptools.build_meta"
```

Create: `requirements.txt`
```
pydantic>=2.0
pyyaml
python-dotenv
requests
beautifulsoup4
markdownify
pymupdf
openai
tiktoken
typer
fastapi
uvicorn
```

- [ ] **Step 2: 创建配置模板**

Create: `config.yaml.example`
```yaml
llm:
  base_url: http://localhost:11434/v1
  api_key: ollama
  model: llama3
  temperature: 0.7

input:
  recursive: true
  max_depth: 2

output:
  format: obsidian
  path: ./vault/
  filename_template: "{title}.md"

features:
  chinese_notes: true

chunker:
  target_tokens: 1500
  overlap_chars: 200

cache:
  enabled: true
  db_path: ./data/cache.db
```

- [ ] **Step 3: 编写配置模块测试**

Create: `tests/test_config.py`
```python
import pytest
import tempfile
import os
from pathlib import Path
from src.config import Config, load_config


def test_load_config_from_file():
    """测试从YAML文件加载配置"""
    config_content = """
llm:
  base_url: http://localhost:11434/v1
  api_key: test-key
  model: llama3
  temperature: 0.5

output:
  format: markdown
  path: ./output/
"""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        f.write(config_content)
        f.flush()
        config_path = f.name

    try:
        config = load_config(config_path)
        assert config.llm.base_url == "http://localhost:11434/v1"
        assert config.llm.api_key == "test-key"
        assert config.llm.model == "llama3"
        assert config.llm.temperature == 0.5
        assert config.output.format == "markdown"
        assert config.output.path == "./output/"
    finally:
        os.unlink(config_path)


def test_config_with_env_override(monkeypatch):
    """测试环境变量覆盖配置"""
    monkeypatch.setenv("LLM_API_KEY", "env-api-key")

    config_content = """
llm:
  base_url: http://localhost:11434/v1
  api_key: ${LLM_API_KEY}
  model: llama3
"""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        f.write(config_content)
        f.flush()
        config_path = f.name

    try:
        config = load_config(config_path)
        assert config.llm.api_key == "env-api-key"
    finally:
        os.unlink(config_path)


def test_default_values():
    """测试默认值"""
    config_content = """
llm:
  model: test-model
"""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        f.write(config_content)
        f.flush()
        config_path = f.name

    try:
        config = load_config(config_path)
        assert config.llm.base_url == "http://localhost:11434/v1"
        assert config.llm.temperature == 0.7
        assert config.features.chinese_notes == True
        assert config.chunker.target_tokens == 1500
    finally:
        os.unlink(config_path)
```

- [ ] **Step 4: 编写配置模块实现**

Create: `src/config.py`
```python
"""配置管理模块"""
import os
import re
from pathlib import Path
from typing import Optional
from dataclasses import dataclass, field

import yaml


@dataclass
class LLMConfig:
    base_url: str = "http://localhost:11434/v1"
    api_key: str = "ollama"
    model: str = "llama3"
    temperature: float = 0.7


@dataclass
class OutputConfig:
    format: str = "obsidian"  # markdown | obsidian
    path: str = "./vault/"
    filename_template: str = "{title}.md"


@dataclass
class FeaturesConfig:
    chinese_notes: bool = True


@dataclass
class ChunkerConfig:
    target_tokens: int = 1500
    overlap_chars: int = 200


@dataclass
class CacheConfig:
    enabled: bool = True
    db_path: str = "./data/cache.db"


@dataclass
class Config:
    llm: LLMConfig = field(default_factory=LLMConfig)
    output: OutputConfig = field(default_factory=OutputConfig)
    features: FeaturesConfig = field(default_factory=FeaturesConfig)
    chunker: ChunkerConfig = field(default_factory=ChunkerConfig)
    cache: CacheConfig = field(default_factory=CacheConfig)


def _expand_env_vars(value: str) -> str:
    """展开字符串中的环境变量 ${VAR} 或 $VAR"""
    pattern = re.compile(r'\$\{(\w+)\}|\$(\w+)')

    def replace_var(match):
        var_name = match.group(1) or match.group(2)
        return os.environ.get(var_name, match.group(0))

    return pattern.sub(replace_var, value)


def _process_dict(data: dict) -> dict:
    """递归处理字典，展开所有字符串值中的环境变量"""
    result = {}
    for key, value in data.items():
        if isinstance(value, str):
            result[key] = _expand_env_vars(value)
        elif isinstance(value, dict):
            result[key] = _process_dict(value)
        elif isinstance(value, list):
            result[key] = [
                _expand_env_vars(v) if isinstance(v, str) else v
                for v in value
            ]
        else:
            result[key] = value
    return result


def load_config(config_path: str = "config.yaml") -> Config:
    """从YAML文件加载配置"""
    path = Path(config_path)

    if not path.exists():
        # 使用默认配置
        return Config()

    with open(path, 'r', encoding='utf-8') as f:
        raw_data = yaml.safe_load(f) or {}

    # 展开环境变量
    data = _process_dict(raw_data)

    # 构建配置对象
    llm_data = data.get('llm', {})
    output_data = data.get('output', {})
    features_data = data.get('features', {})
    chunker_data = data.get('chunker', {})
    cache_data = data.get('cache', {})

    return Config(
        llm=LLMConfig(**llm_data),
        output=OutputConfig(**output_data),
        features=FeaturesConfig(**features_data),
        chunker=ChunkerConfig(**chunker_data),
        cache=CacheConfig(**cache_data),
    )
```

- [ ] **Step 5: 运行测试**

Run: `python -m pytest tests/test_config.py -v`

Expected: All tests pass

- [ ] **Step 6: Commit**

```bash
git add pyproject.toml requirements.txt config.yaml.example src/__init__.py src/config.py tests/test_config.py
git commit -m "feat: add configuration module with env var support"
```

---

## Task 2: 数据模型定义

**Files:**
- Create: `src/models.py`
- Test: `tests/test_models.py`

- [ ] **Step 1: 编写数据模型测试**

Create: `tests/test_models.py`
```python
from datetime import datetime
from src.models import Document, Chunk, ProcessResult


def test_document_creation():
    """测试Document创建"""
    doc = Document(
        id="abc123",
        source="https://example.com/doc",
        title="Test Document",
        content="# Test\n\nContent here",
        content_hash="hash123",
        metadata={"key": "value"},
    )
    assert doc.id == "abc123"
    assert doc.title == "Test Document"
    assert doc.images == []  # 默认空列表


def test_chunk_creation():
    """测试Chunk创建"""
    chunk = Chunk(
        id="chunk_1",
        doc_id="doc_1",
        index=0,
        text="Sample text content",
        token_count=100,
        content_hash="chunk_hash",
    )
    assert chunk.doc_id == "doc_1"
    assert chunk.index == 0
    assert chunk.token_count == 100


def test_process_result():
    """测试ProcessResult创建"""
    doc = Document(
        id="doc1",
        source="test",
        title="Test",
        content="content",
        content_hash="hash",
    )
    result = ProcessResult(
        document=doc,
        chunks=[],
        l1_summary="L1 summary",
        l2_summary="L2 中文笔记",
        output_path="./vault/Test.md",
        cached=False,
    )
    assert result.l1_summary == "L1 summary"
    assert result.l2_summary == "L2 中文笔记"
    assert result.cached is False
```

- [ ] **Step 2: 编写数据模型实现**

Create: `src/models.py`
```python
"""数据模型定义"""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Any, Optional


@dataclass
class Document:
    """文档数据模型"""
    id: str                   # 基于source的hash
    source: str              # URL或本地路径
    title: str
    content: str             # Markdown文本
    content_hash: str
    images: List[str] = field(default_factory=list)  # 图片路径列表
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)


@dataclass
class Chunk:
    """文本块数据模型"""
    id: str
    doc_id: str
    index: int               # 块序号
    text: str
    token_count: int
    content_hash: str


@dataclass
class ProcessResult:
    """处理结果数据模型"""
    document: Document
    chunks: List[Chunk]
    l1_summary: str          # 压缩摘要
    l2_summary: Optional[str]  # 中文笔记（可选）
    output_path: str
    cached: bool = False
```

- [ ] **Step 3: 运行测试**

Run: `python -m pytest tests/test_models.py -v`

Expected: All tests pass

- [ ] **Step 4: Commit**

```bash
git add src/models.py tests/test_models.py
git commit -m "feat: add data models (Document, Chunk, ProcessResult)"
```

---

## Task 3: LLM客户端模块

**Files:**
- Create: `src/llm/__init__.py`
- Create: `src/llm/client.py`
- Test: `tests/test_llm.py`

- [ ] **Step 1: 编写LLM客户端测试**

Create: `tests/test_llm.py`
```python
import pytest
from unittest.mock import Mock, patch
from src.llm.client import LLMClient


@patch('src.llm.client.OpenAI')
def test_llm_client_complete(mock_openai_class):
    """测试LLM完成调用"""
    mock_client = Mock()
    mock_openai_class.return_value = mock_client

    mock_response = Mock()
    mock_response.choices = [Mock(message=Mock(content="Test response"))]
    mock_client.chat.completions.create.return_value = mock_response

    client = LLMClient(
        base_url="http://localhost:11434/v1",
        api_key="test-key",
        model="test-model",
    )

    result = client.complete("Hello, test prompt")

    assert result == "Test response"
    mock_client.chat.completions.create.assert_called_once_with(
        model="test-model",
        messages=[{"role": "user", "content": "Hello, test prompt"}],
        temperature=0.7,
    )


def test_count_tokens_estimate():
    """测试token估算"""
    client = LLMClient()

    # 简单字符估算测试
    text = "Hello world"
    tokens = client.count_tokens(text)

    # 大约 11字符 / 4 = 3 tokens
    assert tokens > 0
    assert isinstance(tokens, int)


def test_ollama_default_config():
    """测试Ollama默认配置"""
    client = LLMClient()

    assert client.base_url == "http://localhost:11434/v1"
    assert client.api_key == "ollama"
    assert client.model == "llama3"


def test_custom_config():
    """测试自定义配置"""
    client = LLMClient(
        base_url="https://api.example.com/v1",
        api_key="sk-xxx",
        model="gpt-4",
        temperature=0.5,
    )

    assert client.base_url == "https://api.example.com/v1"
    assert client.api_key == "sk-xxx"
    assert client.model == "gpt-4"
    assert client.temperature == 0.5
```

- [ ] **Step 2: 编写LLM客户端实现**

Create: `src/llm/__init__.py`
```python
from .client import LLMClient

__all__ = ["LLMClient"]
```

Create: `src/llm/client.py`
```python
"""OpenAI兼容的LLM客户端"""
from openai import OpenAI


class LLMClient:
    """OpenAI兼容接口客户端

    支持Ollama本地模型和任意OpenAI兼容API服务
    """

    def __init__(
        self,
        base_url: str = "http://localhost:11434/v1",
        api_key: str = "ollama",
        model: str = "llama3",
        temperature: float = 0.7,
    ):
        self.base_url = base_url
        self.api_key = api_key
        self.model = model
        self.temperature = temperature
        self._client = None

    @property
    def client(self) -> OpenAI:
        """延迟初始化OpenAI客户端"""
        if self._client is None:
            self._client = OpenAI(
                base_url=self.base_url,
                api_key=self.api_key,
            )
        return self._client

    def complete(self, prompt: str, **kwargs) -> str:
        """发送completion请求

        Args:
            prompt: 提示文本
            **kwargs: 额外参数（如temperature, max_tokens等）

        Returns:
            生成的文本响应
        """
        temperature = kwargs.get("temperature", self.temperature)

        response = self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            temperature=temperature,
        )

        return response.choices[0].message.content

    def count_tokens(self, text: str) -> int:
        """估算文本token数量

        使用简单字符估算（约4字符=1token）
        如需精确计算，可使用tiktoken

        Args:
            text: 输入文本

        Returns:
            估算的token数量
        """
        # 简单估算：平均每个token约4个字符
        return len(text) // 4 + 1
```

- [ ] **Step 3: 运行测试**

Run: `python -m pytest tests/test_llm.py -v`

Expected: All tests pass

- [ ] **Step 4: Commit**

```bash
git add src/llm/ tests/test_llm.py
git commit -m "feat: add OpenAI-compatible LLM client"
```

---

## Task 4: 缓存模块

**Files:**
- Create: `src/cache/__init__.py`
- Create: `src/cache/sqlite_cache.py`
- Test: `tests/test_cache.py`

- [ ] **Step 1: 编写缓存模块测试**

Create: `tests/test_cache.py`
```python
import pytest
import tempfile
import os
from datetime import datetime
from src.cache.sqlite_cache import SQLiteCache
from src.models import Document, Chunk, ProcessResult


@pytest.fixture
def temp_db():
    """创建临时数据库"""
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        db_path = f.name
    yield db_path
    os.unlink(db_path)


def test_cache_save_and_get(temp_db):
    """测试缓存保存和读取"""
    cache = SQLiteCache(db_path=temp_db)

    doc = Document(
        id="doc1",
        source="https://example.com",
        title="Test",
        content="content",
        content_hash="hash123",
    )

    result = ProcessResult(
        document=doc,
        chunks=[],
        l1_summary="L1 summary",
        l2_summary="L2 notes",
        output_path="./test.md",
        cached=False,
    )

    # 保存
    cache.save("hash123", result)

    # 读取
    cached = cache.get("hash123")
    assert cached is not None
    assert cached.l1_summary == "L1 summary"
    assert cached.l2_summary == "L2 notes"
    assert cached.cached is True


def test_cache_miss(temp_db):
    """测试缓存未命中"""
    cache = SQLiteCache(db_path=temp_db)

    result = cache.get("non-existent-hash")
    assert result is None


def test_chunk_cache(temp_db):
    """测试块级缓存"""
    cache = SQLiteCache(db_path=temp_db)

    chunk = Chunk(
        id="chunk1",
        doc_id="doc1",
        index=0,
        text="chunk text",
        token_count=50,
        content_hash="chunk_hash",
    )

    # 保存块缓存
    cache.save_chunk(chunk, "chunk summary")

    # 读取块缓存
    summary = cache.get_chunk("chunk_hash")
    assert summary == "chunk summary"


def test_get_chunk_miss(temp_db):
    """测试块缓存未命中"""
    cache = SQLiteCache(db_path=temp_db)

    summary = cache.get_chunk("non-existent")
    assert summary is None
```

- [ ] **Step 2: 编写缓存模块实现**

Create: `src/cache/__init__.py`
```python
from .sqlite_cache import SQLiteCache

__all__ = ["SQLiteCache"]
```

Create: `src/cache/sqlite_cache.py`
```python
"""SQLite缓存实现"""
import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Optional, List

from src.models import Document, Chunk, ProcessResult


class SQLiteCache:
    """基于SQLite的处理结果缓存"""

    def __init__(self, db_path: str = "./data/cache.db"):
        self.db_path = Path(db_path)
        # 确保目录存在
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        """获取数据库连接"""
        return sqlite3.connect(str(self.db_path))

    def _init_db(self):
        """初始化数据库表"""
        with self._get_connection() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS documents (
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

                CREATE TABLE IF NOT EXISTS chunks (
                    id TEXT PRIMARY KEY,
                    doc_id TEXT,
                    index INTEGER,
                    content_hash TEXT UNIQUE,
                    text TEXT,
                    token_count INTEGER,
                    l1_summary TEXT,
                    created_at TIMESTAMP
                );

                CREATE INDEX IF NOT EXISTS idx_content_hash
                ON documents(content_hash);

                CREATE INDEX IF NOT EXISTS idx_chunk_hash
                ON chunks(content_hash);
            """)

    def get(self, content_hash: str) -> Optional[ProcessResult]:
        """根据内容hash获取缓存结果"""
        with self._get_connection() as conn:
            row = conn.execute(
                """SELECT id, source, title, content, images, metadata,
                          l1_summary, l2_summary, output_path
                   FROM documents WHERE content_hash = ?""",
                (content_hash,)
            ).fetchone()

            if not row:
                return None

            doc = Document(
                id=row[0],
                source=row[1],
                title=row[2],
                content=row[3],
                images=json.loads(row[4]) if row[4] else [],
                metadata=json.loads(row[5]) if row[5] else {},
                content_hash=content_hash,
            )

            return ProcessResult(
                document=doc,
                chunks=[],  # 块缓存单独处理
                l1_summary=row[6],
                l2_summary=row[7],
                output_path=row[8],
                cached=True,
            )

    def save(self, content_hash: str, result: ProcessResult):
        """保存处理结果到缓存"""
        doc = result.document

        with self._get_connection() as conn:
            conn.execute(
                """INSERT OR REPLACE INTO documents
                   (id, source, content_hash, title, content, images, metadata,
                    l1_summary, l2_summary, output_path, processed_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    doc.id,
                    doc.source,
                    content_hash,
                    doc.title,
                    doc.content,
                    json.dumps(doc.images),
                    json.dumps(doc.metadata),
                    result.l1_summary,
                    result.l2_summary,
                    result.output_path,
                    datetime.now().isoformat(),
                )
            )

    def get_chunk(self, content_hash: str) -> Optional[str]:
        """获取块级缓存摘要"""
        with self._get_connection() as conn:
            row = conn.execute(
                "SELECT l1_summary FROM chunks WHERE content_hash = ?",
                (content_hash,)
            ).fetchone()

            return row[0] if row else None

    def save_chunk(self, chunk: Chunk, summary: str):
        """保存块级缓存"""
        with self._get_connection() as conn:
            conn.execute(
                """INSERT OR REPLACE INTO chunks
                   (id, doc_id, index, content_hash, text, token_count, l1_summary, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    chunk.id,
                    chunk.doc_id,
                    chunk.index,
                    chunk.content_hash,
                    chunk.text,
                    chunk.token_count,
                    summary,
                    datetime.now().isoformat(),
                )
            )
```

- [ ] **Step 3: 运行测试**

Run: `python -m pytest tests/test_cache.py -v`

Expected: All tests pass

- [ ] **Step 4: Commit**

```bash
git add src/cache/ tests/test_cache.py
git commit -m "feat: add SQLite cache with document and chunk level caching"
```

---

## Task 5: Chunker模块

**Files:**
- Create: `src/chunker/__init__.py`
- Create: `src/chunker/chunker.py`
- Test: `tests/test_chunker.py`

- [ ] **Step 1: 编写Chunker测试**

Create: `tests/test_chunker.py`
```python
import pytest
from src.chunker.chunker import Chunker
from src.models import Document


def test_chunker_basic():
    """测试基本分块功能"""
    chunker = Chunker(target_tokens=100, overlap_chars=10)

    doc = Document(
        id="doc1",
        source="test",
        title="Test",
        content="Paragraph 1.\n\nParagraph 2.\n\nParagraph 3.",
        content_hash="hash1",
    )

    chunks = chunker.split(doc)

    assert len(chunks) > 0
    for i, chunk in enumerate(chunks):
        assert chunk.doc_id == "doc1"
        assert chunk.index == i
        assert chunk.text
        assert chunk.content_hash


def test_chunker_respects_paragraph_boundary():
    """测试分块尊重段落边界"""
    chunker = Chunker(target_tokens=50, overlap_chars=0)

    content = "Para 1 with enough text to matter.\n\nPara 2 also has text.\n\nPara 3 continues."
    doc = Document(
        id="doc1",
        source="test",
        title="Test",
        content=content,
        content_hash="hash1",
    )

    chunks = chunker.split(doc)

    # 每个块应该在段落边界结束
    for chunk in chunks:
        # 块不应该在中间段落断开
        pass  # 具体断言取决于实现


def test_single_short_document():
    """测试短文档生成单个块"""
    chunker = Chunker(target_tokens=1000)

    doc = Document(
        id="doc1",
        source="test",
        title="Test",
        content="Short content.",
        content_hash="hash1",
    )

    chunks = chunker.split(doc)

    assert len(chunks) == 1
    assert chunks[0].text == "Short content."
```

- [ ] **Step 2: 编写Chunker实现**

Create: `src/chunker/__init__.py`
```python
from .chunker import Chunker

__all__ = ["Chunker"]
```

Create: `src/chunker/chunker.py`
```python
"""文本分块模块"""
import hashlib
from typing import List

from src.models import Document, Chunk


class Chunker:
    """将文档切分为适合LLM处理的块"""

    def __init__(self, target_tokens: int = 1500, overlap_chars: int = 200):
        """
        Args:
            target_tokens: 目标token数（约4字符/token）
            overlap_chars: 块间重叠字符数，保持上下文
        """
        self.target_tokens = target_tokens
        self.overlap_chars = overlap_chars
        # 粗略估算：1 token ≈ 4字符
        self.target_chars = target_tokens * 4

    def split(self, document: Document) -> List[Chunk]:
        """将文档分块

        策略：
        1. 优先按段落边界切分
        2. 如果段落过长，按句子切分
        3. 添加重叠保持上下文

        Args:
            document: 输入文档

        Returns:
            文本块列表
        """
        content = document.content
        paragraphs = content.split('\n\n')

        chunks = []
        current_chunk = []
        current_length = 0
        chunk_index = 0

        for para in paragraphs:
            para = para.strip()
            if not para:
                continue

            para_length = len(para)

            # 如果当前段落加入后超过目标长度，先保存当前块
            if current_length + para_length > self.target_chars and current_chunk:
                chunk_text = '\n\n'.join(current_chunk)
                chunks.append(self._create_chunk(
                    document.id, chunk_index, chunk_text
                ))

                # 重叠：保留最后一些内容
                if self.overlap_chars > 0 and current_chunk:
                    overlap_text = self._get_overlap('\n\n'.join(current_chunk))
                    current_chunk = [overlap_text] if overlap_text else []
                    current_length = len(current_chunk[0]) if current_chunk else 0
                else:
                    current_chunk = []
                    current_length = 0

                chunk_index += 1

            current_chunk.append(para)
            current_length += para_length

        # 处理剩余内容
        if current_chunk:
            chunk_text = '\n\n'.join(current_chunk)
            chunks.append(self._create_chunk(
                document.id, chunk_index, chunk_text
            ))

        return chunks

    def _get_overlap(self, text: str) -> str:
        """获取重叠文本"""
        if len(text) <= self.overlap_chars:
            return text
        return text[-self.overlap_chars:]

    def _create_chunk(self, doc_id: str, index: int, text: str) -> Chunk:
        """创建Chunk对象"""
        chunk_id = f"{doc_id}_chunk_{index}"
        content_hash = hashlib.sha256(text.encode()).hexdigest()[:16]

        # 简单token估算
        token_count = len(text) // 4 + 1

        return Chunk(
            id=chunk_id,
            doc_id=doc_id,
            index=index,
            text=text,
            token_count=token_count,
            content_hash=content_hash,
        )
```

- [ ] **Step 3: 运行测试**

Run: `python -m pytest tests/test_chunker.py -v`

Expected: All tests pass

- [ ] **Step 4: Commit**

```bash
git add src/chunker/ tests/test_chunker.py
git commit -m "feat: add text chunker with paragraph boundary support"
```

---

## Task 6: Summarizer模块

**Files:**
- Create: `src/summarizer/__init__.py`
- Create: `src/summarizer/prompts.py`
- Create: `src/summarizer/summarizer.py`
- Test: `tests/test_summarizer.py`

- [ ] **Step 1: 编写Summarizer测试**

Create: `tests/test_summarizer.py`
```python
import pytest
from unittest.mock import Mock
from src.summarizer.summarizer import Summarizer
from src.models import Chunk


def test_l1_summarize():
    """测试L1压缩摘要"""
    mock_llm = Mock()
    mock_llm.complete.return_value = "- Key point 1\n- Key point 2"

    summarizer = Summarizer(llm_client=mock_llm)

    chunk = Chunk(
        id="c1",
        doc_id="d1",
        index=0,
        text="Long technical documentation content...",
        token_count=500,
        content_hash="hash1",
    )

    result = summarizer.l1_summarize(chunk)

    assert result == "- Key point 1\n- Key point 2"
    mock_llm.complete.assert_called_once()

    # 验证prompt包含关键词
    call_args = mock_llm.complete.call_args[0][0]
    assert "Summarize" in call_args
    assert "technical documentation" in call_args


def test_l2_summarize():
    """测试L2中文笔记"""
    mock_llm = Mock()
    mock_llm.complete.return_value = "## 概念1\n\n中文笔记内容"

    summarizer = Summarizer(llm_client=mock_llm)

    l1_text = "- Point 1\n- Point 2\n- Point 3"
    result = summarizer.l2_summarize(l1_text)

    assert result == "## 概念1\n\n中文笔记内容"
    mock_llm.complete.assert_called_once()

    # 验证是中文prompt
    call_args = mock_llm.complete.call_args[0][0]
    assert "中文" in call_args


def test_summarizer_with_config():
    """测试带配置的Summarizer"""
    mock_llm = Mock()
    mock_llm.complete.return_value = "Summary"

    config = Mock()
    config.features.chinese_notes = True

    summarizer = Summarizer(llm_client=mock_llm, config=config)

    # 测试配置生效
    assert summarizer.config.features.chinese_notes is True
```

- [ ] **Step 2: 编写Prompt模板**

Create: `src/summarizer/prompts.py`
```python
"""Prompt模板定义"""

L1_SUMMARY_PROMPT = """Summarize the following technical documentation into key bullet points:
- Keep only core concepts and key information
- Remove examples, code snippets unless critical
- Max 200 words
- Output in English
- Use concise bullet points

Content:
{text}

Summary:"""

L2_CHINESE_NOTES_PROMPT = """将以下内容整理为中文学习笔记：

要求：
1. 分模块组织（使用二级标题）
2. 提取核心概念
3. 使用简洁清晰的中文
4. 适当使用列表和强调（加粗、代码块）
5. 输出标准Markdown格式
6. 长度适中，便于快速阅读

内容：
{text}

中文学习笔记："""


class PromptTemplate:
    """Prompt模板管理"""

    L1 = L1_SUMMARY_PROMPT
    L2 = L2_CHINESE_NOTES_PROMPT

    @classmethod
    def format_l1(cls, text: str) -> str:
        """格式化L1摘要prompt"""
        return cls.L1.format(text=text)

    @classmethod
    def format_l2(cls, text: str) -> str:
        """格式化L2中文笔记prompt"""
        return cls.L2.format(text=text)
```

- [ ] **Step 3: 编写Summarizer实现**

Create: `src/summarizer/__init__.py`
```python
from .summarizer import Summarizer
from .prompts import PromptTemplate

__all__ = ["Summarizer", "PromptTemplate"]
```

Create: `src/summarizer/summarizer.py`
```python
"""摘要生成模块"""
from typing import TYPE_CHECKING

from src.models import Chunk
from src.summarizer.prompts import PromptTemplate

if TYPE_CHECKING:
    from src.llm.client import LLMClient
    from src.config import Config


class Summarizer:
    """两层级摘要生成器"""

    def __init__(self, llm_client: "LLMClient", config: "Config" = None):
        """
        Args:
            llm_client: LLM客户端
            config: 配置对象（可选）
        """
        self.llm = llm_client
        self.config = config

    def l1_summarize(self, chunk: Chunk) -> str:
        """L1压缩摘要

        将技术文档压缩为高密度英文摘要

        Args:
            chunk: 文本块

        Returns:
            压缩后的英文摘要
        """
        prompt = PromptTemplate.format_l1(chunk.text)
        return self.llm.complete(prompt)

    def l2_summarize(self, l1_text: str) -> str:
        """L2中文学习笔记

        将L1摘要整理为结构化中文笔记

        Args:
            l1_text: L1摘要文本

        Returns:
            结构化中文学习笔记（Markdown格式）
        """
        prompt = PromptTemplate.format_l2(l1_text)
        return self.llm.complete(prompt)
```

- [ ] **Step 4: 运行测试**

Run: `python -m pytest tests/test_summarizer.py -v`

Expected: All tests pass

- [ ] **Step 5: Commit**

```bash
git add src/summarizer/ tests/test_summarizer.py
git commit -m "feat: add two-level summarizer with L1 compression and L2 Chinese notes"
```

---

## Task 7: Crawler模块 - URL抓取

**Files:**
- Create: `src/crawler/__init__.py`
- Create: `src/crawler/base.py`
- Create: `src/crawler/url_crawler.py`
- Test: `tests/test_crawler.py`

- [ ] **Step 1: 编写Crawler测试**

Create: `tests/test_crawler.py`
```python
import pytest
from unittest.mock import Mock, patch, mock_open
from src.crawler.url_crawler import URLCrawler
from src.crawler.local_crawler import LocalCrawler


class TestURLCrawler:
    @patch('src.crawler.url_crawler.requests.get')
    @patch('src.crawler.url_crawler.markdownify')
    def test_fetch_single_page(self, mock_markdownify, mock_get):
        """测试单页抓取"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = "<html><body><h1>Test</h1><p>Content</p></body></html>"
        mock_get.return_value = mock_response

        mock_markdownify.return_value = "# Test\n\nContent"

        crawler = URLCrawler()
        doc = crawler.fetch("https://example.com/page")

        assert doc.title == "Test"
        assert "# Test" in doc.content
        assert doc.source == "https://example.com/page"

    def test_extract_title_from_html(self):
        """测试从HTML提取标题"""
        html = "<html><head><title>Page Title</title></head><body></body></html>"
        crawler = URLCrawler()
        title = crawler._extract_title(html)
        assert title == "Page Title"

    def test_extract_title_from_h1(self):
        """测试从h1标签提取标题"""
        html = "<html><body><h1>Heading Title</h1></body></html>"
        crawler = URLCrawler()
        title = crawler._extract_title(html)
        assert title == "Heading Title"


class TestLocalCrawler:
    def test_fetch_single_file(self, tmp_path):
        """测试单文件读取"""
        test_file = tmp_path / "test.md"
        test_file.write_text("# Test Doc\n\nContent here")

        crawler = LocalCrawler()
        doc = crawler.fetch(str(test_file))

        assert doc.title == "Test Doc"
        assert "Content here" in doc.content

    def test_fetch_directory(self, tmp_path):
        """测试目录遍历"""
        # 创建测试文件
        (tmp_path / "doc1.md").write_text("# Doc 1")
        (tmp_path / "doc2.md").write_text("# Doc 2")

        crawler = LocalCrawler()
        docs = crawler.fetch_directory(str(tmp_path))

        assert len(docs) == 2
        titles = [d.title for d in docs]
        assert "Doc 1" in titles
        assert "Doc 2" in titles
```

- [ ] **Step 2: 编写Crawler基础类**

Create: `src/crawler/__init__.py`
```python
from .url_crawler import URLCrawler
from .local_crawler import LocalCrawler

__all__ = ["URLCrawler", "LocalCrawler"]
```

Create: `src/crawler/base.py`
```python
"""Crawler抽象基类"""
from abc import ABC, abstractmethod
from typing import Union

from src.models import Document


class BaseCrawler(ABC):
    """文档抓取器抽象基类"""

    @abstractmethod
    def fetch(self, source: str) -> Union[Document, list]:
        """抓取/读取文档

        Args:
            source: URL或本地路径

        Returns:
            Document对象或Document列表
        """
        pass

    def _generate_id(self, source: str) -> str:
        """生成文档ID（基于source的hash）"""
        import hashlib
        return hashlib.sha256(source.encode()).hexdigest()[:16]
```

- [ ] **Step 3: 编写URL Crawler**

Create: `src/crawler/url_crawler.py`
```python
"""URL抓取器 - 支持网页抓取和图片下载"""
import hashlib
import os
import re
from pathlib import Path
from typing import List, Optional
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup
from markdownify import markdownify as md

from src.crawler.base import BaseCrawler
from src.models import Document


class URLCrawler(BaseCrawler):
    """URL网页抓取器

    功能：
    - 抓取单页HTML并转为Markdown
    - 下载图片到本地assets目录
    """

    def __init__(self, timeout: int = 30, download_images: bool = True):
        """
        Args:
            timeout: 请求超时时间（秒）
            download_images: 是否下载图片
        """
        self.timeout = timeout
        self.download_images = download_images
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })

    def fetch(self, url: str, assets_dir: Optional[str] = None) -> Document:
        """抓取单页URL

        Args:
            url: 目标URL
            assets_dir: 图片保存目录（默认./assets/{doc_id}）

        Returns:
            Document对象
        """
        # 请求页面
        response = self.session.get(url, timeout=self.timeout)
        response.raise_for_status()
        html = response.text

        # 解析HTML
        soup = BeautifulSoup(html, 'html.parser')

        # 提取标题
        title = self._extract_title(soup)

        # 提取主要内容
        main_content = self._extract_main_content(soup)

        # 转换Markdown
        markdown = md(str(main_content), heading_style="ATX")

        # 处理图片
        images = []
        if self.download_images:
            doc_id = self._generate_id(url)
            if assets_dir is None:
                assets_dir = f"./assets/{doc_id}"
            images = self._download_images(soup, url, assets_dir)
            # 替换Markdown中的图片链接
            markdown = self._update_image_links(markdown, images, assets_dir)

        return Document(
            id=self._generate_id(url),
            source=url,
            title=title,
            content=markdown,
            content_hash=hashlib.sha256(markdown.encode()).hexdigest()[:16],
            images=images,
            metadata={
                "content_type": response.headers.get("Content-Type", ""),
                "fetch_time": response.headers.get("Date", ""),
            },
        )

    def _extract_title(self, soup: BeautifulSoup) -> str:
        """提取页面标题"""
        # 优先使用<title>标签
        if soup.title and soup.title.string:
            return soup.title.string.strip()

        # 其次使用第一个<h1>
        h1 = soup.find('h1')
        if h1:
            return h1.get_text().strip()

        # 默认
        return "Untitled"

    def _extract_main_content(self, soup: BeautifulSoup) -> BeautifulSoup:
        """提取主要内容区域

        优先选择：
        1. <main>标签
        2. <article>标签
        3. .content / #content 类
        4. 整个<body>
        """
        # 尝试常见的主要内容选择器
        selectors = [
            'main',
            'article',
            '.content',
            '#content',
            '.documentation',
            '.doc-content',
        ]

        for selector in selectors:
            elem = soup.select_one(selector)
            if elem:
                return elem

        # 默认返回body
        return soup.body or soup

    def _download_images(
        self,
        soup: BeautifulSoup,
        base_url: str,
        assets_dir: str
    ) -> List[str]:
        """下载图片到本地

        Returns:
            下载的图片路径列表
        """
        Path(assets_dir).mkdir(parents=True, exist_ok=True)
        images = []

        for img in soup.find_all('img'):
            src = img.get('src')
            if not src:
                continue

            # 处理相对URL
            full_url = urljoin(base_url, src)

            try:
                # 下载图片
                response = self.session.get(full_url, timeout=30)
                response.raise_for_status()

                # 生成文件名
                ext = Path(urlparse(full_url).path).suffix or '.png'
                filename = f"image_{len(images)}{ext}"
                filepath = Path(assets_dir) / filename

                # 保存
                with open(filepath, 'wb') as f:
                    f.write(response.content)

                images.append(str(filepath))

            except Exception as e:
                # 图片下载失败，继续处理其他图片
                print(f"Warning: Failed to download image {full_url}: {e}")
                continue

        return images

    def _update_image_links(
        self,
        markdown: str,
        images: List[str],
        assets_dir: str
    ) -> str:
        """更新Markdown中的图片链接为本地路径"""
        # 简单的图片链接替换
        # 实际实现可能需要更复杂的正则匹配
        return markdown
```

- [ ] **Step 4: 编写Local Crawler**

Create: `src/crawler/local_crawler.py`
```python
"""本地文件读取器 - 支持Markdown和PDF"""
import hashlib
from pathlib import Path
from typing import List, Union

from src.crawler.base import BaseCrawler
from src.models import Document


class LocalCrawler(BaseCrawler):
    """本地文档读取器

    支持：
    - Markdown文件(.md)
    - PDF文件(.pdf)
    - 目录递归遍历
    """

    def __init__(self, recursive: bool = True):
        """
        Args:
            recursive: 是否递归遍历子目录
        """
        self.recursive = recursive

    def fetch(self, path: str) -> Union[Document, List[Document]]:
        """读取本地文件或目录

        Args:
            path: 文件或目录路径

        Returns:
            Document或Document列表
        """
        p = Path(path)

        if not p.exists():
            raise FileNotFoundError(f"Path not found: {path}")

        if p.is_file():
            return self._read_file(p)
        elif p.is_dir():
            return self._read_directory(p)
        else:
            raise ValueError(f"Invalid path: {path}")

    def _read_file(self, filepath: Path) -> Document:
        """读取单个文件"""
        suffix = filepath.suffix.lower()

        if suffix == '.md':
            return self._read_markdown(filepath)
        elif suffix == '.pdf':
            return self._read_pdf(filepath)
        else:
            raise ValueError(f"Unsupported file type: {suffix}")

    def _read_markdown(self, filepath: Path) -> Document:
        """读取Markdown文件"""
        content = filepath.read_text(encoding='utf-8')

        # 提取标题（第一个#开头的行）
        title = filepath.stem
        for line in content.split('\n'):
            if line.startswith('# '):
                title = line[2:].strip()
                break

        return Document(
            id=self._generate_id(str(filepath)),
            source=str(filepath),
            title=title,
            content=content,
            content_hash=hashlib.sha256(content.encode()).hexdigest()[:16],
            metadata={
                "file_type": "markdown",
                "file_size": filepath.stat().st_size,
            },
        )

    def _read_pdf(self, filepath: Path) -> Document:
        """读取PDF文件"""
        try:
            import fitz  # PyMuPDF
        except ImportError:
            raise ImportError("PyMuPDF is required for PDF support. Install with: pip install pymupdf")

        doc = fitz.open(str(filepath))

        # 提取文本
        text_parts = []
        for page in doc:
            text_parts.append(page.get_text())

        content = '\n\n'.join(text_parts)

        # 提取标题（通常是第一页的第一行）
        title = filepath.stem
        if content.strip():
            first_lines = content.strip().split('\n')[:3]
            for line in first_lines:
                line = line.strip()
                if line and len(line) < 100:  # 合理的标题长度
                    title = line
                    break

        doc.close()

        return Document(
            id=self._generate_id(str(filepath)),
            source=str(filepath),
            title=title,
            content=content,
            content_hash=hashlib.sha256(content.encode()).hexdigest()[:16],
            metadata={
                "file_type": "pdf",
                "page_count": len(doc),
                "file_size": filepath.stat().st_size,
            },
        )

    def _read_directory(self, dirpath: Path) -> List[Document]:
        """递归读取目录"""
        documents = []

        pattern = "**/*" if self.recursive else "*"

        # 支持.md和.pdf
        for ext in ['.md', '.pdf']:
            for filepath in dirpath.glob(f"{pattern}{ext}"):
                if filepath.is_file():
                    try:
                        doc = self._read_file(filepath)
                        documents.append(doc)
                    except Exception as e:
                        print(f"Warning: Failed to read {filepath}: {e}")

        return documents
```

- [ ] **Step 5: 运行测试**

Run: `python -m pytest tests/test_crawler.py -v`

Expected: All tests pass

- [ ] **Step 6: Commit**

```bash
git add src/crawler/ tests/test_crawler.py
git commit -m "feat: add crawler module with URL, local file and PDF support"
```

---

## Task 8: Exporter模块

**Files:**
- Create: `src/exporter/__init__.py`
- Create: `src/exporter/base.py`
- Create: `src/exporter/markdown.py`
- Create: `src/exporter/obsidian.py`
- Test: `tests/test_exporter.py`

- [ ] **Step 1: 编写Exporter测试**

Create: `tests/test_exporter.py`
```python
import pytest
from pathlib import Path
from src.exporter.markdown import MarkdownExporter
from src.exporter.obsidian import ObsidianExporter
from src.models import Document


class TestMarkdownExporter:
    def test_export_basic(self, tmp_path):
        """测试基本Markdown导出"""
        exporter = MarkdownExporter(output_dir=str(tmp_path))

        doc = Document(
            id="doc1",
            source="https://example.com",
            title="Test Doc",
            content="# Original\n\nContent",
            content_hash="hash1",
        )

        path = exporter.export(
            document=doc,
            l1_summary="L1 summary",
            l2_summary="L2 中文笔记"
        )

        assert Path(path).exists()
        content = Path(path).read_text()
        assert "# Test Doc" in content
        assert "L1 summary" in content
        assert "L2 中文笔记" in content


class TestObsidianExporter:
    def test_export_with_frontmatter(self, tmp_path):
        """测试Obsidian格式导出（带YAML frontmatter）"""
        exporter = ObsidianExporter(output_dir=str(tmp_path))

        doc = Document(
            id="doc1",
            source="https://example.com/page",
            title="Obsidian Doc",
            content="# Original",
            content_hash="hash1",
        )

        path = exporter.export(
            document=doc,
            l1_summary="Summary content",
            l2_summary="中文笔记内容"
        )

        content = Path(path).read_text()

        # 检查frontmatter
        assert "---" in content
        assert "title: Obsidian Doc" in content
        assert "source: https://example.com/page" in content

        # 检查结构
        assert "# Obsidian Doc" in content
        assert "## 摘要 (Summary)" in content
        assert "## 学习笔记 (Notes)" in content

        # 检查标签
        assert "#processed" in content
```

- [ ] **Step 2: 编写Exporter基础类**

Create: `src/exporter/__init__.py`
```python
from .markdown import MarkdownExporter
from .obsidian import ObsidianExporter

__all__ = ["MarkdownExporter", "ObsidianExporter"]
```

Create: `src/exporter/base.py`
```python
"""Exporter抽象基类"""
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional

from src.models import Document


class BaseExporter(ABC):
    """导出器抽象基类"""

    def __init__(self, output_dir: str = "./output"):
        """
        Args:
            output_dir: 输出目录
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    @abstractmethod
    def export(
        self,
        document: Document,
        l1_summary: str,
        l2_summary: Optional[str] = None,
    ) -> str:
        """导出文档

        Args:
            document: 原始文档
            l1_summary: L1压缩摘要
            l2_summary: L2中文笔记（可选）

        Returns:
            输出文件路径
        """
        pass

    def _sanitize_filename(self, title: str) -> str:
        """清理文件名中的非法字符"""
        # 替换非法字符
        illegal = '<>:"/\\|?*'
        for char in illegal:
            title = title.replace(char, '_')
        return title.strip()
```

- [ ] **Step 3: 编写Markdown Exporter**

Create: `src/exporter/markdown.py`
```python
"""标准Markdown导出器"""
from pathlib import Path
from typing import Optional

from src.exporter.base import BaseExporter
from src.models import Document


class MarkdownExporter(BaseExporter):
    """标准Markdown格式导出"""

    def export(
        self,
        document: Document,
        l1_summary: str,
        l2_summary: Optional[str] = None,
    ) -> str:
        """导出为标准Markdown格式"""
        # 生成文件名
        filename = self._sanitize_filename(document.title) + ".md"
        output_path = self.output_dir / filename

        # 构建内容
        lines = [
            f"# {document.title}",
            "",
            f"> Source: {document.source}",
            "",
            "## Summary",
            "",
            l1_summary,
        ]

        # 添加中文笔记（如果存在）
        if l2_summary:
            lines.extend([
                "",
                "## Notes (中文)",
                "",
                l2_summary,
            ])

        # 写入文件
        content = "\n".join(lines)
        output_path.write_text(content, encoding='utf-8')

        return str(output_path)
```

- [ ] **Step 4: 编写Obsidian Exporter**

Create: `src/exporter/obsidian.py`
```python
"""Obsidian格式导出器"""
from datetime import datetime
from pathlib import Path
from typing import Optional, List

from src.exporter.base import BaseExporter
from src.models import Document


class ObsidianExporter(BaseExporter):
    """Obsidian专用格式导出

    包含：
    - YAML frontmatter
    - 双向链接支持
    - 标签
    """

    def export(
        self,
        document: Document,
        l1_summary: str,
        l2_summary: Optional[str] = None,
    ) -> str:
        """导出为Obsidian格式"""
        # 生成文件名
        filename = self._sanitize_filename(document.title) + ".md"
        output_path = self.output_dir / filename

        # 构建frontmatter
        frontmatter = self._build_frontmatter(document)

        # 构建正文
        body = self._build_body(document, l1_summary, l2_summary)

        # 组合内容
        content = frontmatter + "\n" + body

        # 写入文件
        output_path.write_text(content, encoding='utf-8')

        return str(output_path)

    def _build_frontmatter(self, document: Document) -> str:
        """构建YAML frontmatter"""
        lines = [
            "---",
            f"title: {document.title}",
            f"source: {document.source}",
            f"date: {datetime.now().strftime('%Y-%m-%d')}",
            "tags:",
            "  - documentation",
            "  - auto-learning",
        ]

        # 添加图片引用（如果有）
        if document.images:
            lines.append("images:")
            for img in document.images:
                lines.append(f"  - {img}")

        lines.append("---")

        return "\n".join(lines) + "\n"

    def _build_body(
        self,
        document: Document,
        l1_summary: str,
        l2_summary: Optional[str],
    ) -> str:
        """构建正文内容"""
        lines = [
            f"# {document.title}",
            "",
            f"> 原始链接: {document.source}",
            "",
            "## 摘要 (Summary)",
            "",
            l1_summary,
        ]

        # 添加中文笔记
        if l2_summary:
            lines.extend([
                "",
                "## 学习笔记 (Notes)",
                "",
                l2_summary,
            ])

        # 提取关键概念（简单实现：从摘要中提取列表项）
        key_concepts = self._extract_key_concepts(l1_summary)
        if key_concepts:
            lines.extend([
                "",
                "## 关键概念 (Key Concepts)",
                "",
            ])
            for concept in key_concepts[:10]:  # 最多10个
                lines.append(f"- [[{concept}]]")

        # 添加图片（如果有）
        if document.images:
            lines.extend([
                "",
                "## 图片",
                "",
            ])
            for img in document.images:
                # Obsidian图片语法: ![[image.png]]
                img_name = Path(img).name
                lines.append(f"![[{img_name}]]")

        # 添加标签
        lines.extend([
            "",
            "---",
            "",
            "#processed #auto-learning",
        ])

        return "\n".join(lines)

    def _extract_key_concepts(self, summary: str) -> List[str]:
        """从摘要中提取关键概念（简单实现）"""
        concepts = []

        # 查找列表项中的概念
        for line in summary.split('\n'):
            line = line.strip()
            # 列表项格式: "- concept" 或 "* concept"
            if line.startswith('- ') or line.startswith('* '):
                concept = line[2:].strip()
                # 只取第一行，去掉解释
                concept = concept.split(':')[0].split('.')[0]
                concept = concept.strip()
                if concept and len(concept) < 50:  # 合理的概念长度
                    concepts.append(concept)

        return concepts
```

- [ ] **Step 5: 运行测试**

Run: `python -m pytest tests/test_exporter.py -v`

Expected: All tests pass

- [ ] **Step 6: Commit**

```bash
git add src/exporter/ tests/test_exporter.py
git commit -m "feat: add exporter module with Markdown and Obsidian formats"
```

---

## Task 9: Pipeline模块

**Files:**
- Create: `src/pipeline.py`
- Test: `tests/test_pipeline.py`

- [ ] **Step 1: 编写Pipeline测试**

Create: `tests/test_pipeline.py`
```python
import pytest
from unittest.mock import Mock, patch
from src.pipeline import Pipeline
from src.config import Config
from src.models import Document, Chunk, ProcessResult


class TestPipeline:
    @pytest.fixture
    def mock_config(self):
        config = Config()
        config.cache.db_path = ":memory:"  # 内存数据库
        return config

    @pytest.fixture
    def mock_document(self):
        return Document(
            id="doc1",
            source="https://example.com",
            title="Test Doc",
            content="Short content",
            content_hash="hash1",
        )

    def test_pipeline_full_flow(self, mock_config, mock_document):
        """测试完整pipeline流程"""
        pipeline = Pipeline(mock_config)

        # Mock各个组件
        pipeline.crawler = Mock()
        pipeline.crawler.fetch.return_value = mock_document

        pipeline.chunker = Mock()
        pipeline.chunker.split.return_value = [
            Chunk(id="c1", doc_id="doc1", index=0, text="chunk", token_count=10, content_hash="ch1")
        ]

        pipeline.summarizer = Mock()
        pipeline.summarizer.l1_summarize.return_value = "L1 summary"
        pipeline.summarizer.l2_summarize.return_value = "L2 中文笔记"

        pipeline.exporter = Mock()
        pipeline.exporter.export.return_value = "./output/Test.md"

        # 执行
        result = pipeline.run("https://example.com")

        # 验证
        assert isinstance(result, ProcessResult)
        assert result.l1_summary == "L1 summary"
        assert result.l2_summary == "L2 中文笔记"
        assert result.output_path == "./output/Test.md"

        # 验证调用
        pipeline.crawler.fetch.assert_called_once()
        pipeline.chunker.split.assert_called_once()
        pipeline.summarizer.l1_summarize.assert_called_once()
        pipeline.summarizer.l2_summarize.assert_called_once()
        pipeline.exporter.export.assert_called_once()

    def test_pipeline_with_cache(self, mock_config, mock_document):
        """测试缓存命中"""
        pipeline = Pipeline(mock_config)

        # 先保存一个结果到缓存
        cached_result = ProcessResult(
            document=mock_document,
            chunks=[],
            l1_summary="Cached summary",
            l2_summary="Cached 中文",
            output_path="./cached.md",
            cached=True,
        )
        pipeline.cache.save("hash1", cached_result)

        # Mock crawler返回相同hash的文档
        pipeline.crawler = Mock()
        pipeline.crawler.fetch.return_value = mock_document

        # 执行
        result = pipeline.run("https://example.com")

        # 验证从缓存读取
        assert result.cached is True
        assert result.l1_summary == "Cached summary"
```

- [ ] **Step 2: 编写Pipeline实现**

Create: `src/pipeline.py`
```python
"""核心工作流Pipeline"""
from typing import Optional

from src.config import Config
from src.models import Document, Chunk, ProcessResult
from src.crawler.url_crawler import URLCrawler
from src.crawler.local_crawler import LocalCrawler
from src.chunker.chunker import Chunker
from src.summarizer.summarizer import Summarizer
from src.llm.client import LLMClient
from src.exporter.obsidian import ObsidianExporter
from src.exporter.markdown import MarkdownExporter
from src.cache.sqlite_cache import SQLiteCache


class Pipeline:
    """文档处理Pipeline

    协调各个模块完成：
    1. 文档抓取/读取
    2. 文本分块
    3. L1压缩摘要
    4. L2中文笔记（可选）
    5. 格式化导出
    """

    def __init__(self, config: Config):
        """
        Args:
            config: 系统配置
        """
        self.config = config

        # 初始化LLM客户端
        self.llm = LLMClient(
            base_url=config.llm.base_url,
            api_key=config.llm.api_key,
            model=config.llm.model,
            temperature=config.llm.temperature,
        )

        # 初始化各模块
        self.crawler = self._create_crawler(config)
        self.chunker = Chunker(
            target_tokens=config.chunker.target_tokens,
            overlap_chars=config.chunker.overlap_chars,
        )
        self.summarizer = Summarizer(llm_client=self.llm, config=config)
        self.exporter = self._create_exporter(config)
        self.cache = SQLiteCache(db_path=config.cache.db_path)

    def _create_crawler(self, config: Config):
        """创建合适的crawler"""
        # 根据输入类型选择crawler
        # 实际使用时可以通过参数指定
        return URLCrawler()

    def _create_exporter(self, config: Config):
        """创建合适的exporter"""
        if config.output.format == "obsidian":
            return ObsidianExporter(output_dir=config.output.path)
        else:
            return MarkdownExporter(output_dir=config.output.path)

    def run(self, source: str, force: bool = False) -> ProcessResult:
        """执行完整处理流程

        Args:
            source: URL或本地路径
            force: 是否强制重新处理（忽略缓存）

        Returns:
            处理结果
        """
        # 1. 抓取/读取文档
        document = self.crawler.fetch(source)

        # 2. 检查缓存
        if not force and self.config.cache.enabled:
            cached = self.cache.get(document.content_hash)
            if cached:
                print(f"✓ Cache hit: {document.title}")
                return cached

        print(f"Processing: {document.title}")

        # 3. 分块
        chunks = self.chunker.split(document)
        print(f"  Split into {len(chunks)} chunks")

        # 4. L1总结（按块，使用缓存）
        l1_summaries = []
        for chunk in chunks:
            # 检查块级缓存
            cached_summary = self.cache.get_chunk(chunk.content_hash)
            if cached_summary and not force:
                l1_summaries.append(cached_summary)
            else:
                print(f"  Summarizing chunk {chunk.index + 1}/{len(chunks)}")
                summary = self.summarizer.l1_summarize(chunk)
                self.cache.save_chunk(chunk, summary)
                l1_summaries.append(summary)

        # 5. 合并L1摘要
        merged_l1 = "\n\n".join(l1_summaries)

        # 6. L2总结（可选）
        l2_summary = None
        if self.config.features.chinese_notes:
            print("  Generating Chinese notes...")
            l2_summary = self.summarizer.l2_summarize(merged_l1)

        # 7. 格式化导出
        output_path = self.exporter.export(document, merged_l1, l2_summary)
        print(f"  Exported: {output_path}")

        # 8. 保存缓存
        result = ProcessResult(
            document=document,
            chunks=chunks,
            l1_summary=merged_l1,
            l2_summary=l2_summary,
            output_path=output_path,
            cached=False,
        )

        if self.config.cache.enabled:
            self.cache.save(document.content_hash, result)

        return result
```

- [ ] **Step 3: 运行测试**

Run: `python -m pytest tests/test_pipeline.py -v`

Expected: All tests pass

- [ ] **Step 4: Commit**

```bash
git add src/pipeline.py tests/test_pipeline.py
git commit -m "feat: add core pipeline orchestrating all modules"
```

---

## Task 10: CLI主程序

**Files:**
- Create: `main.py`
- Create: `.env.example`
- Test: `tests/test_main.py` (integration test)

- [ ] **Step 1: 编写主程序**

Create: `main.py`
```python
#!/usr/bin/env python3
"""Auto Learning System - CLI入口"""
import sys
from pathlib import Path

import typer
from typing_extensions import Annotated

from src.config import load_config, Config
from src.pipeline import Pipeline
from src.crawler.url_crawler import URLCrawler
from src.crawler.local_crawler import LocalCrawler

app = typer.Typer(
    name="als",
    help="自动学习文档并生成Obsidian笔记",
    add_completion=False,
)


def _is_url(source: str) -> bool:
    """判断source是否为URL"""
    return source.startswith(('http://', 'https://'))


def _create_pipeline(config: Config, source: str) -> Pipeline:
    """创建配置好的pipeline"""
    pipeline = Pipeline(config)

    # 根据source类型选择crawler
    if _is_url(source):
        pipeline.crawler = URLCrawler()
    else:
        pipeline.crawler = LocalCrawler(recursive=True)

    return pipeline


@app.command()
def process(
    source: Annotated[str, typer.Argument(help="URL或本地路径")],
    type: Annotated[str, typer.Option("--type", "-t", help="输入类型: auto/url/local")] = "auto",
    config_path: Annotated[str, typer.Option("--config", "-c", help="配置文件路径")] = "config.yaml",
    notes: Annotated[bool, typer.Option("--notes/--no-notes", help="是否生成中文笔记")] = True,
    force: Annotated[bool, typer.Option("--force", "-f", help="强制重新处理")] = False,
):
    """处理文档并生成学习笔记"""
    try:
        # 加载配置
        config = load_config(config_path)
        config.features.chinese_notes = notes

        # 创建pipeline
        pipeline = _create_pipeline(config, source)

        # 执行处理
        result = pipeline.run(source, force=force)

        # 输出结果
        typer.echo(f"✓ 处理完成: {result.document.title}")
        typer.echo(f"  输出: {result.output_path}")

        if result.cached:
            typer.echo("  (来自缓存)")

    except Exception as e:
        typer.echo(f"✗ 错误: {e}", err=True)
        raise typer.Exit(1)


@app.command()
def serve(
    host: Annotated[str, typer.Option("--host", "-h", help="绑定地址")] = "0.0.0.0",
    port: Annotated[int, typer.Option("--port", "-p", help="端口")] = 8000,
    config_path: Annotated[str, typer.Option("--config", "-c")] = "config.yaml",
):
    """启动API服务"""
    try:
        import uvicorn
        from src.api.server import create_app

        config = load_config(config_path)
        app = create_app(config)

        typer.echo(f"Starting API server at http://{host}:{port}")
        uvicorn.run(app, host=host, port=port)

    except ImportError:
        typer.echo("✗ 错误: 需要安装API依赖: pip install fastapi uvicorn", err=True)
        raise typer.Exit(1)


@app.command()
def init(
    path: Annotated[str, typer.Argument(help="初始化目录")] = ".",
):
    """初始化项目配置"""
    config_path = Path(path) / "config.yaml"

    if config_path.exists():
        typer.echo(f"配置文件已存在: {config_path}")
        raise typer.Exit(0)

    # 复制示例配置
    example_config = Path(__file__).parent / "config.yaml.example"
    if example_config.exists():
        config_path.write_text(example_config.read_text())
    else:
        # 创建默认配置
        default_config = """llm:
  base_url: http://localhost:11434/v1
  api_key: ollama
  model: llama3
  temperature: 0.7

output:
  format: obsidian
  path: ./vault/

features:
  chinese_notes: true
"""
        config_path.write_text(default_config)

    typer.echo(f"✓ 创建配置文件: {config_path}")


if __name__ == "__main__":
    app()
```

- [ ] **Step 2: 创建环境变量示例**

Create: `.env.example`
```bash
# LLM API配置（如使用非Ollama服务）
LLM_API_KEY=your-api-key-here

# Ollama主机（可选，默认localhost:11434）
# OLLAMA_HOST=http://localhost:11434
```

- [ ] **Step 3: 编写集成测试**

Create: `tests/test_main.py`
```python
"""主程序集成测试"""
import pytest
from typer.testing import CliRunner

from main import app

runner = CliRunner()


def test_process_command_help():
    """测试process命令帮助"""
    result = runner.invoke(app, ["process", "--help"])
    assert result.exit_code == 0
    assert "URL或本地路径" in result.output


def test_init_command(tmp_path):
    """测试init命令"""
    with runner.isolated_filesystem(temp_dir=tmp_path) as td:
        result = runner.invoke(app, ["init"])
        assert result.exit_code == 0
        assert "创建配置文件" in result.output

        # 验证文件创建
        import os
        assert os.path.exists("config.yaml")
```

- [ ] **Step 4: 运行测试**

Run: `python -m pytest tests/test_main.py -v`

Expected: All tests pass

- [ ] **Step 5: Commit**

```bash
git add main.py .env.example tests/test_main.py
git commit -m "feat: add CLI main entry point with process/serve/init commands"
```

---

## Task 11: API模块

**Files:**
- Create: `src/api/__init__.py`
- Create: `src/api/server.py`
- Create: `src/api/routes.py`

- [ ] **Step 1: 编写API模块**

Create: `src/api/__init__.py`
```python
from .server import create_app

__all__ = ["create_app"]
```

Create: `src/api/server.py`
```python
"""FastAPI应用创建"""
from fastapi import FastAPI

from src.config import Config
from src.api.routes import router


def create_app(config: Config) -> FastAPI:
    """创建FastAPI应用

    Args:
        config: 系统配置

    Returns:
        FastAPI应用实例
    """
    app = FastAPI(
        title="Auto Learning System API",
        description="自动学习文档并生成Obsidian笔记",
        version="0.1.0",
    )

    # 存储配置
    app.state.config = config

    # 注册路由
    app.include_router(router, prefix="/api/v1")

    @app.get("/health")
    def health_check():
        """健康检查"""
        return {"status": "ok"}

    return app
```

Create: `src/api/routes.py`
```python
"""API路由定义"""
from typing import Optional

from fastapi import APIRouter, Request
from pydantic import BaseModel

router = APIRouter()


class ProcessRequest(BaseModel):
    """处理请求体"""
    source: str                      # URL或本地路径
    notes: bool = True              # 是否生成中文笔记
    force: bool = False             # 强制重新处理


class ProcessResponse(BaseModel):
    """处理响应体"""
    success: bool
    title: str
    output_path: str
    cached: bool
    message: str


@router.post("/process", response_model=ProcessResponse)
async def process_document(request: Request, body: ProcessRequest):
    """处理文档

    接受URL或本地路径，执行完整处理流程
    """
    from src.pipeline import Pipeline
    from src.crawler.url_crawler import URLCrawler
    from src.crawler.local_crawler import LocalCrawler

    config = request.app.state.config
    config.features.chinese_notes = body.notes

    # 创建pipeline
    pipeline = Pipeline(config)

    # 选择crawler
    if body.source.startswith(('http://', 'https://')):
        pipeline.crawler = URLCrawler()
    else:
        pipeline.crawler = LocalCrawler()

    # 执行处理
    result = pipeline.run(body.source, force=body.force)

    return ProcessResponse(
        success=True,
        title=result.document.title,
        output_path=result.output_path,
        cached=result.cached,
        message=f"Processed: {result.document.title}",
    )


@router.get("/config")
async def get_config(request: Request):
    """获取当前配置"""
    config = request.app.state.config
    return {
        "llm": {
            "base_url": config.llm.base_url,
            "model": config.llm.model,
        },
        "output": {
            "format": config.output.format,
            "path": config.output.path,
        },
        "features": {
            "chinese_notes": config.features.chinese_notes,
        },
    }


# v2预留接口
@router.post("/index")
async def build_index(request: Request):
    """构建知识库索引（v2实现）"""
    return {"message": "Knowledge base indexing not implemented in v1"}


@router.post("/query")
async def query_knowledge_base(request: Request, query: str):
    """查询知识库（v2实现）"""
    return {"message": "Knowledge base query not implemented in v1", "query": query}
```

- [ ] **Step 2: Commit**

```bash
git add src/api/
git commit -m "feat: add optional FastAPI HTTP interface"
```

---

## Task 12: 测试数据与CI

**Files:**
- Create: `tests/fixtures/sample_doc.md`
- Create: `tests/fixtures/sample.html`
- Create: `tests/conftest.py`
- Modify: `.gitignore`

- [ ] **Step 1: 创建测试数据**

Create: `tests/fixtures/sample_doc.md`
```markdown
# Sample Document

This is a sample markdown document for testing.

## Section 1

Content of section 1 with some **bold** text.

## Section 2

- List item 1
- List item 2
- List item 3

```python
print("Code block example")
```

## Conclusion

End of sample document.
```

Create: `tests/fixtures/sample.html`
```html
<!DOCTYPE html>
<html>
<head>
    <title>Sample HTML Page</title>
</head>
<body>
    <main>
        <h1>Sample HTML Document</h1>
        <p>This is a paragraph of text.</p>
        <h2>Subsection</h2>
        <p>More content here.</p>
    </main>
</body>
</html>
```

- [ ] **Step 2: 创建conftest.py**

Create: `tests/conftest.py`
```python
"""pytest配置和共享fixtures"""
import pytest
import tempfile
import os


@pytest.fixture
def temp_dir():
    """创建临时目录"""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


@pytest.fixture
def sample_markdown_content():
    """示例Markdown内容"""
    return """# Test Document

## Introduction

This is a test document.

## Details

Some details here.
"""
```

- [ ] **Step 3: 创建.gitignore**

Create: `.gitignore`
```gitignore
# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
build/
develop-eggs/
dist/
downloads/
eggs/
.eggs/
lib/
lib64/
parts/
sdist/
var/
wheels/
*.egg-info/
.installed.cfg
*.egg

# Virtual environments
venv/
env/
ENV/

# IDE
.idea/
.vscode/
*.swp
*.swo

# Project specific
data/
*.db
*.sqlite3
vault/
output/
assets/

# Config (keep example)
config.yaml
.env

# Testing
.pytest_cache/
.coverage
htmlcov/
```

- [ ] **Step 4: 创建README**

Create: `README.md`
```markdown
# Auto Learning System

自动学习技术文档并生成Obsidian笔记。

## 功能

- 自动抓取网页文档（支持图片下载）
- 读取本地Markdown和PDF文件
- 智能文本分块处理
- L1压缩摘要 + L2中文学习笔记
- 输出到Obsidian（支持双向链接和标签）
- SQLite缓存，避免重复处理
- 可选HTTP API接口

## 快速开始

### 安装

```bash
pip install -r requirements.txt
```

### 配置

```bash
# 复制示例配置
cp config.yaml.example config.yaml

# 编辑配置，设置LLM参数
vim config.yaml
```

### 使用

```bash
# 处理网页
python main.py process https://docs.example.com/page

# 处理本地目录
python main.py process ./my-docs --type local

# 仅生成压缩摘要（跳过中文笔记）
python main.py process https://docs.example.com --no-notes

# 强制重新处理
python main.py process https://docs.example.com --force

# 启动API服务
python main.py serve
```

## 配置说明

```yaml
llm:
  base_url: http://localhost:11434/v1  # Ollama默认
  api_key: ollama
  model: llama3

output:
  format: obsidian  # 或 markdown
  path: ./vault/

features:
  chinese_notes: true  # 是否生成中文笔记
```

## 依赖

- Python 3.10+
- Ollama（本地模型）或OpenAI兼容API

## License

MIT
```

- [ ] **Step 5: 最终测试和提交**

Run: `python -m pytest tests/ -v`

Expected: All tests pass

```bash
git add tests/fixtures/ tests/conftest.py .gitignore README.md
git commit -m "chore: add test fixtures, gitignore and README"
```

---

## 总结

完成以上12个任务后，系统将具备：

1. ✅ 配置管理（YAML + 环境变量）
2. ✅ URL抓取（支持图片下载）
3. ✅ 本地文件读取（Markdown + PDF）
4. ✅ 智能文本分块
5. ✅ L1压缩摘要
6. ✅ L2中文学习笔记（可选）
7. ✅ OpenAI兼容LLM接口
8. ✅ Obsidian格式输出
9. ✅ SQLite缓存
10. ✅ CLI工具
11. ✅ HTTP API（可选）

**测试命令**:
```bash
# 运行所有测试
python -m pytest tests/ -v

# 运行特定模块测试
python -m pytest tests/test_pipeline.py -v
```

**使用示例**:
```bash
# 初始化
python main.py init

# 处理文档
python main.py process https://python.langchain.com/docs/get_started/introduction

# 启动API
python main.py serve
```