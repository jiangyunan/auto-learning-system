# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Auto Learning System is a Python 3.10+ tool that automatically processes documents (URLs, Markdown files, PDFs) and generates Obsidian notes using LLM-powered two-level summarization.

## Common Commands

This project uses **uv** as the package manager.

```bash
# Install dependencies
uv venv
uv pip install -e ".[dev]"

# Run tests
uv run pytest tests/ -v
uv run pytest tests/test_crawler.py -v
uv run pytest tests/test_models.py::test_document_creation -v

# Code quality
uv run black src/ tests/
uv run ruff check src/ tests/
uv run ruff check --fix src/ tests/
uv run mypy src/

# Run the application
uv run python -m src.cli process https://example.com/article
uv run python -m src.cli process ./docs/guide.md
uv run python -m src.cli serve --port 8000
uv run python -m src.cli batch sources.txt
```

## High-Level Architecture

### Processing Pipeline (`src/pipeline.py`)

The `Pipeline` class orchestrates the document processing flow:

1. **Crawl** (`src/crawler/`): Fetch content from URLs, local files, PDFs, or `opencli://` sources.
2. **Chunk** (`src/chunker.py`): Split text into paragraph-bounded chunks (~1500 tokens with 200-char overlap).
3. **Summarize** (`src/summarizer.py`): Generate L1 (bullet points) and optional L2 (structured Chinese notes) summaries per chunk, then merge them into document-level summaries.
4. **Export** (`src/exporter/`): Write results as Markdown or Obsidian-format files.

### Key Components

- **`src/crawler/__init__.py`**: The unified `Crawler` delegates to specialized crawlers:
  - `URLCrawler`: Fetches single URLs or recursively crawls matching sub-pages (glob patterns).
  - `LocalFileCrawler`: Processes Markdown files. When given a folder, it builds a `DocumentGraph` by parsing Wiki links (`[[Page Name]]`) and Markdown links (`[text](./path.md)`), then yields documents in topological order (most-referenced first).
  - `PDFCrawler`: Extracts text (and optionally images) from PDFs via PyMuPDF.
  - `OpenCLICrawler`: Handles `opencli://site/command` sources by executing whitelisted `opencli` commands.

- **`src/summarizer.py`**: `Summarizer` uses the `LLMClient` to generate JSON-structured summaries.
  - L1 extracts bullets and key concepts.
  - L2 generates Chinese learning notes (overview, key points, concept explanations, code examples).
  - Chunk-level results are cached via `Cache`; document-level results merge chunks using either simple deduplication or LLM synthesis when content is large.

- **`src/llm/__init__.py`**: `LLMClient` is an OpenAI-compatible async client. It supports standard completion, streaming, and JSON-mode requests with fallback parsing for markdown code blocks.

- **`src/cache.py`**: SQLite-backed `Cache` stores LLM results keyed by content SHA256 hash.

- **`src/api/__init__.py`**: FastAPI application exposing `/health`, `/process`, `/folder`, and `/batch` endpoints.

- **`src/cli.py`**: Typer CLI with Rich progress output. Supports `process`, `batch`, `serve`, `config`, and `cache` subcommands.

### Configuration

Configuration is loaded from `config.yaml` (copy `config.yaml.example`). It supports environment variable substitution using `${VAR_NAME}` syntax. Key sections: `llm`, `output`, `features`, `chunker`, `cache`.

## Code Style

- Import order: stdlib → third-party → `src.*`
- Format with **Black** (88-character line length)
- Type hints: use `list[T]`, `dict[K, V]`, and `str | None` (Python 3.10+ style)
- Models are dataclasses in `src/models.py`
- Use graceful degradation for LLM and I/O failures (return sensible defaults instead of crashing)
