# Agent Guidelines for AI Learning System

This document provides guidelines for AI agents working on this codebase.

## Project Overview

Auto Learning System is a Python 3.10+ tool for automatically learning documents and generating Obsidian notes. It supports multi-source inputs (URLs, Markdown, PDFs), intelligent chunking, two-level summarization, and Obsidian integration.

## Build, Lint, and Test Commands

### Testing
```bash
# Run all tests
uv run pytest tests/ -v

# Run a single test file
uv run pytest tests/test_models.py -v

# Run a specific test
uv run pytest tests/test_models.py::test_document_creation -v

# Run with coverage
uv run pytest tests/ --cov=src --cov-report=html
```

### Code Quality
```bash
# Format code
uv run black src/ tests/

# Lint with ruff
uv run ruff check src/ tests/
uv run ruff check --fix src/ tests/

# Type check
uv run mypy src/

# Run all quality checks
uv run black --check src/ tests/ && uv run ruff check src/ tests/ && uv run mypy src/
```

### Running the Application
```bash
# Process a URL
uv run python -m src.cli process https://example.com/article

# Process a local file
uv run python -m src.cli process ./docs/guide.md

# Start API server
uv run python -m src.cli serve --port 8000

# Batch processing
uv run python -m src.cli batch sources.txt
```

## Code Style Guidelines

### Import Order
1. Standard library imports (with `__future__` if needed)
2. Third-party imports (external packages)
3. Local imports (from `src.*`)

Example:
```python
"""模块文档字符串"""
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Optional

import yaml
from pydantic import BaseModel

from src.config import Config
from src.models import Document
```

### Formatting
- **Line length**: 88 characters (Black default)
- **Quotes**: Double quotes for strings, single quotes for docstrings
- **Trailing commas**: Use trailing commas in multi-line structures
- Run `uv run black src/ tests/` before committing

### Type Hints
- Use type hints for all function parameters and return values
- Use `Optional[T]` for nullable types
- Use `list[T]`, `dict[K, V]` (Python 3.10+ style, not `List`, `Dict` from typing)
- Use `|` for union types (e.g., `str | None` instead of `Optional[str]`)

### Naming Conventions
- **Modules**: `snake_case.py`
- **Classes**: `PascalCase`
- **Functions/Methods**: `snake_case`
- **Constants**: `UPPER_SNAKE_CASE`
- **Private methods**: `_leading_underscore`
- **Variables**: `snake_case`

### Docstrings
- Use triple double quotes `"""`
- First line: Brief description in Chinese
- For classes: Document purpose and key attributes
- For functions: Document args, returns, and raises if applicable

### Error Handling
- Use try/except blocks for external API calls and file operations
- Return sensible defaults on failure (graceful degradation)
- Example pattern from `summarizer.py`:
```python
try:
    response = await self.llm.complete_json(...)
    return SummaryL1(...)
except Exception as e:
    # Graceful degradation
    return SummaryL1(
        bullets=["Error generating summary"],
        key_concepts=[],
    )
```

### Architecture Patterns

#### Dataclasses for Models
Use `@dataclass` for data models (see `src/models.py`):
```python
from dataclasses import dataclass, field

@dataclass
class Document:
    id: str
    source_type: SourceType
    source_path: str
    title: str = ""
    metadata: dict = field(default_factory=dict)
```

#### Factory Functions
Create factory functions for complex object creation:
```python
def create_chunker(config: ChunkerConfig) -> Chunker:
    """Factory function: 创建分块器"""
    return Chunker(config)
```

#### Context Managers
Use context managers for resource management (database connections, file handles):
```python
@contextmanager
def _get_connection(self):
    conn = sqlite3.connect(self.db_path)
    try:
        yield conn
    finally:
        conn.close()
```

### Project Structure
```
src/
├── __init__.py
├── cli.py              # CLI interface (Typer)
├── config.py           # Configuration management
├── models.py           # Data models (dataclasses)
├── cache.py            # SQLite caching
├── chunker.py          # Text chunking
├── summarizer.py       # Two-level summarization
├── pipeline.py         # Processing orchestration
├── llm/                # LLM client module
├── crawler/            # Document crawling (URL/local/PDF)
├── exporter/           # Markdown/Obsidian export
└── api/                # FastAPI HTTP interface
tests/                  # Unit tests (mirror src structure)
```

### Testing Guidelines
- Test files: `test_*.py` naming convention
- Test functions: `test_*` naming convention
- Use descriptive test names that explain what is being tested
- One assertion per test when possible
- Use pytest fixtures for common setup
- Mock external dependencies (LLM calls, network requests)

### Environment Setup
```bash
# Create virtual environment and install dependencies
uv venv
uv pip install -e ".[dev]"

# Copy config example
cp config.yaml.example config.yaml
```

### Configuration
- Use `config.yaml` for user configuration
- Support environment variables with `${VAR_NAME}` syntax
- Configuration defined in `src/config.py` using dataclasses

### Key Dependencies
- **pydantic**: Data validation and settings
- **typer**: CLI framework
- **fastapi**: HTTP API framework
- **tiktoken**: Token counting
- **BeautifulSoup4**: HTML parsing
- **PyMuPDF**: PDF processing

## Notes

- This project uses **UV** as the package manager (faster than pip)
- Python version: **>=3.10**
- All user-facing features support both Chinese and English where applicable
- The code prioritizes local-first processing with SQLite caching
