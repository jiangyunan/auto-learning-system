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

# URL 递归采集配置 (可选)
crawl:
  patterns:
    - "*.md"
    - "*/docs/*"
  max_depth: 3
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

# 处理文件夹（自动分析文件链接关系）
uv run python -m src.cli process ./my-obsidian-vault/

# 处理文件夹（不包含相关文档上下文）
uv run python -m src.cli process ./my-obsidian-vault/ --no-related-context

# 处理文件夹（非递归）
uv run python -m src.cli process ./folder/ --no-recursive

### URL 递归采集

处理单个 URL 时，可指定链接模式递归采集所有匹配的子页面，内容自动合并为单个文档：

```bash
# 递归采集所有 .md 页面（默认深度3）
uv run python -m src.cli process https://docs.example.com \
  --pattern "*.md"

# 指定递归深度
uv run python -m src.cli process https://docs.example.com/guide/ \
  --pattern "*/guide/*" \
  --max-depth 5

# 多个匹配模式
uv run python -m src.cli process https://docs.example.com \
  --pattern "*/docs/*" \
  --pattern "*/api/*"
```

**模式匹配说明：**
- `*.md` - 匹配所有 .md 结尾的 URL
- `*/docs/*` - 匹配路径包含 /docs/ 的 URL
- 支持多个 `--pattern` 参数

**批量处理（从文件读取来源列表）**
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
- `POST /process` - 处理单个文档或文件夹
- `POST /folder` - 专门处理文件夹
- `POST /batch` - 批量处理文档

示例：

```bash
# 处理单个文档
curl -X POST http://localhost:8000/process \
  -H "Content-Type: application/json" \
  -d '{"source": "https://example.com/article"}'

# 处理文件夹
curl -X POST http://localhost:8000/process \
  -H "Content-Type: application/json" \
  -d '{"source": "./my-vault", "recursive": true}'

# 使用专门的文件夹端点
curl -X POST http://localhost:8000/folder \
  -H "Content-Type: application/json" \
  -d '{"path": "./my-vault", "include_related_context": true}'
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

## 文件夹批量处理与链接关系

当处理本地 Markdown 文件夹时，系统会自动：

1. **扫描所有 Markdown 文件**（支持递归子文件夹）
2. **解析文件链接关系**：
   - Obsidian Wiki 链接：`[[Page Name]]`
   - Markdown 链接：`[Text](./path/to/file.md)`
3. **构建文档关系图**：分析文件间的引用关系
4. **按依赖顺序处理**：被引用最多的文件优先处理
5. **包含相关文档上下文**：处理时自动附加相关文档的内容作为上下文

### 链接关系示例

假设有以下 Obsidian Vault 结构：

```
vault/
├── Python.md          (被 3 个文件引用)
├── Async Programming.md  (被 1 个文件引用，引用 Python)
└── Guide.md           (引用 Python 和 Async Programming)
```

系统会：
1. 首先处理 `Python.md`（核心文档）
2. 然后处理 `Async Programming.md`
3. 最后处理 `Guide.md`（会包含前两个文档的上下文）

### API 端点

```bash
# 处理文件夹
POST /folder
{
  "path": "./my-vault",
  "recursive": true,
  "include_related_context": true
}

# 通用处理端点（自动识别文件夹）
POST /process
{
  "source": "./my-vault",
  "recursive": true
}
```

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
