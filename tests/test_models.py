"""数据模型测试"""

import pytest
from datetime import datetime
from pathlib import Path

from src.models import (
    Document,
    Chunk,
    SummaryL1,
    SummaryL2,
    ProcessResult,
    CacheEntry,
    SourceType,
    DocFormat,
    ImageInfo,
)


def test_document_creation():
    """测试Document创建"""
    doc = Document(
        id="test-id-123",
        source_type=SourceType.URL,
        source_path="https://example.com/article",
        title="Test Article",
        content="This is test content",
        format=DocFormat.HTML,
        metadata={"author": "test"},
    )

    assert doc.id == "test-id-123"
    assert doc.source_type == SourceType.URL
    assert doc.source_path == "https://example.com/article"
    assert doc.title == "Test Article"
    assert doc.content == "This is test content"
    assert doc.format == DocFormat.HTML
    assert doc.metadata == {"author": "test"}
    assert isinstance(doc.fetched_at, datetime)


def test_document_defaults():
    """测试Document默认值"""
    doc = Document(
        id="test-id", source_type=SourceType.LOCAL_FILE, source_path="/path/to/file.md"
    )

    assert doc.title == ""
    assert doc.content == ""
    assert doc.format == DocFormat.TEXT
    assert doc.images == []
    assert doc.metadata == {}


def test_chunk_creation():
    """测试Chunk创建"""
    chunk = Chunk(
        id="chunk-1",
        document_id="doc-1",
        index=0,
        content="This is chunk content",
        start_pos=0,
        end_pos=100,
        token_count=25,
    )

    assert chunk.id == "chunk-1"
    assert chunk.document_id == "doc-1"
    assert chunk.index == 0
    assert chunk.content == "This is chunk content"
    assert chunk.token_count == 25


def test_summary_l1_creation():
    """测试SummaryL1创建"""
    summary = SummaryL1(
        bullets=["Point 1", "Point 2", "Point 3"],
        key_concepts=["Concept A", "Concept B"],
    )

    assert summary.bullets == ["Point 1", "Point 2", "Point 3"]
    assert summary.key_concepts == ["Concept A", "Concept B"]


def test_summary_l2_creation():
    """测试SummaryL2创建"""
    summary = SummaryL2(
        overview="This is an overview",
        key_points=["Key point 1", "Key point 2"],
        concepts_explained=[
            {"term": "API", "explanation": "Application Programming Interface"}
        ],
        code_examples=[{"language": "python", "code": "print('hello')"}],
        related_topics=["Topic A", "Topic B"],
    )

    assert summary.overview == "This is an overview"
    assert len(summary.key_points) == 2
    assert len(summary.concepts_explained) == 1
    assert len(summary.code_examples) == 1


def test_process_result_creation():
    """测试ProcessResult创建"""
    l1 = SummaryL1(bullets=["Bullet 1"])
    l2 = SummaryL2(overview="Overview text")

    result = ProcessResult(
        document_id="doc-1",
        document_title="Test Doc",
        source_url="https://example.com",
        chunks_count=3,
        l1_summary=l1,
        l2_summary=l2,
        output_path=Path("./output/test.md"),
    )

    assert result.document_id == "doc-1"
    assert result.chunks_count == 3
    assert result.l1_summary.bullets == ["Bullet 1"]
    assert result.l2_summary.overview == "Overview text"
    assert result.output_path == Path("./output/test.md")


def test_cache_entry_creation():
    """测试CacheEntry创建"""
    entry = CacheEntry(content_hash="abc123hash", result_json='{"summary": "test"}')

    assert entry.content_hash == "abc123hash"
    assert entry.result_json == '{"summary": "test"}'
    assert entry.access_count == 0
    assert isinstance(entry.created_at, datetime)


def test_image_info_creation():
    """测试ImageInfo创建"""
    img = ImageInfo(
        original_url="https://example.com/image.png",
        local_path=Path("./images/image.png"),
        alt_text="An example image",
    )

    assert img.original_url == "https://example.com/image.png"
    assert img.local_path == Path("./images/image.png")
    assert img.alt_text == "An example image"


def test_source_type_enum():
    """测试SourceType枚举"""
    assert SourceType.URL.value == "url"
    assert SourceType.LOCAL_FILE.value == "local_file"
    assert SourceType.PDF.value == "pdf"


def test_doc_format_enum():
    """测试DocFormat枚举"""
    assert DocFormat.MARKDOWN.value == "markdown"
    assert DocFormat.HTML.value == "html"
    assert DocFormat.PDF.value == "pdf"
    assert DocFormat.TEXT.value == "text"
