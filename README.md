# Auto Learning System

自动学习文档并生成 Obsidian 笔记的本地优先工具。

## 功能特性

- **多源输入**: 支持 URL 爬取、本地 Markdown/PDF 文件
- **智能分块**: 基于段落边界，目标 1500 tokens，保留 200 字符重叠
- **两级摘要**:
  - L1: 内容压缩为 bullet points
  - L2: 结构化中文学习笔记（可选）
- **Obsidian 集成**: YAML frontmatter、双向链接、标签系统
- **SQLite 缓存**: 内容哈希去重，避免重复处理
- **OpenAI 兼容**: 支持 Ollama 和任意 OpenAI 兼容端点

## 项目结构

```
.
├── src/
│   ├── config.py          # 配置管理
│   ├── models.py          # 数据模型
│   ├── cache.py           # SQLite 缓存
│   ├── chunker.py         # 文本分块
│   ├── llm/               # LLM 客户端
│   ├── crawler/           # 文档爬取 (URL/本地/PDF)
│   ├── summarizer.py      # 摘要生成
│   ├── exporter/          # Markdown/Obsidian 导出
│   ├── pipeline.py        # 处理流程编排
│   ├── cli.py             # 命令行接口
│   └── api/               # FastAPI HTTP 接口
├── tests/                 # 单元测试
├── config.yaml.example    # 配置示例
└── pyproject.toml         # 项目配置
```

## 安装

### 使用 UV (推荐)

```bash
# 创建虚拟环境并安装依赖
uv venv
uv pip install -e ".[dev]"
```

### 使用 pip

```bash
pip install -e ".[dev]"
```

## 配置

复制配置示例并修改：

```bash
cp config.yaml.example config.yaml
```

编辑 `config.yaml`:

```yaml
llm:
  base_url: http://localhost:11434/v1  # Ollama 或其他 OpenAI 兼容端点
  api_key: ollama
  model: llama3
  temperature: 0.7

output:
  format: obsidian          # markdown 或 obsidian
  path: ./vault/            # 输出目录
  filename_template: "{title}.md"

features:
  chinese_notes: true       # 是否生成 L2 中文笔记

chunker:
  target_tokens: 1500       # 分块目标 token 数
  overlap_chars: 200        # 块间重叠字符数

cache:
  enabled: true
  db_path: ./data/cache.db
```

支持环境变量：`${VAR_NAME}` 语法可在配置中使用。

## 使用方法

### CLI 命令

```bash
# 处理单个 URL
uv run python -m src.cli process https://example.com/article

# 处理本地 Markdown 文件
uv run python -m src.cli process ./docs/guide.md

# 处理 PDF 文件
uv run python -m src.cli process ./papers/research.pdf

# 批量处理（从文件读取来源列表）
echo "https://example.com/page1" > sources.txt
echo "./local/doc.md" >> sources.txt
uv run python -m src.cli batch sources.txt

# 使用自定义配置
uv run python -m src.cli process https://example.com --config ./myconfig.yaml

# 查看配置示例
uv run python -m src.cli config --example
```

### API 服务

```bash
# 启动 HTTP API 服务
uv run python -m src.cli serve

# 指定端口
uv run python -m src.cli serve --port 8080
```

API 端点：

- `GET /health` - 健康检查
- `POST /process` - 处理单个文档
- `POST /batch` - 批量处理文档

示例：

```bash
curl -X POST http://localhost:8000/process \
  -H "Content-Type: application/json" \
  -d '{"source": "https://example.com/article"}'
```

### Python API

```python
import asyncio
from src.config import load_config
from src.pipeline import Pipeline

async def main():
    config = load_config()
    pipeline = Pipeline(config)

    result = await pipeline.process_document("https://example.com/article")
    print(f"Generated: {result.output_path}")

asyncio.run(main())
```

## 输出格式

### Markdown 格式

标准 Markdown，包含：
- 文档元数据（来源、生成时间）
- L1 Summary (bullet points)
- L2 学习笔记（中文，可选）

### Obsidian 格式

增强功能：
- YAML frontmatter (标题、日期、标签)
- 双向链接 `[[Topic]]`
- 概念自动链接

示例输出：

```markdown
---
title: "Article Title"
date: 2024-01-15
time: 10:30
source: "https://example.com/article"
tags: [auto-learning, concept/Python, concept/Async]
chunks: 3
---

## Related Topics

- [[Programming]]
- [[Python]]

## Summary

- Key point 1
- Key point 2

### Key Concepts

- [[Python]] `Python`
- [[Async]] `Async`

---

## 学习笔记

### 概述
...
```

## 开发

### 运行测试

```bash
# 运行全部测试
uv run pytest tests/ -v

# 运行特定模块测试
uv run pytest tests/test_crawler.py -v

# 覆盖率报告
uv run pytest tests/ --cov=src --cov-report=html
```

### 代码风格

```bash
# 格式化
uv run black src/ tests/

# 检查
uv run ruff check src/ tests/
uv run mypy src/
```

## 技术栈

- **Python 3.10+**
- **pydantic**: 数据验证
- **tiktoken**: Token 计数
- **BeautifulSoup**: HTML 解析
- **PyMuPDF**: PDF 处理
- **OpenAI**: LLM 客户端
- **Typer**: CLI 框架
- **FastAPI**: HTTP API
- **SQLite**: 本地缓存

## 许可证

MIT
