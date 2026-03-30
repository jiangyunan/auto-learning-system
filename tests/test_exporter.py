"""导出模块测试"""
import pytest
from pathlib import Path
from datetime import datetime

from src.exporter import MarkdownExporter, ObsidianExporter, Exporter, ExportResult
from src.models import ProcessResult, SummaryL1, SummaryL2
from src.config import OutputConfig


@pytest.fixture
def output_config(tmp_path):
    return OutputConfig(
        format="markdown",
        path=str(tmp_path),
        filename_template="{title}.md"
    )


@pytest.fixture
def sample_result():
    return ProcessResult(
        document_id="doc-1",
        document_title="Test Document",
        source_url="https://example.com/article",
        chunks_count=3,
        l1_summary=SummaryL1(
            bullets=["Point 1", "Point 2"],
            key_concepts=["Python", "Async"],
        ),
        l2_summary=SummaryL2(
            overview="这是概述",
            key_points=["要点1", "要点2"],
            concepts_explained=[{"term": "API", "explanation": "接口"}],
            code_examples=[{"language": "python", "code": "print('hello')", "explanation": "示例"}],
            related_topics=["Programming", "Python"],
        ),
        generated_at=datetime(2024, 1, 15, 10, 30),
    )


class TestMarkdownExporter:
    """Markdown导出测试"""

    def test_export_basic(self, output_config, sample_result, tmp_path):
        """测试基本导出"""
        exporter = MarkdownExporter(output_config)
        result = exporter.export(sample_result)

        assert result.success is True
        assert result.file_path.exists()
        assert result.format == "markdown"

        content = result.file_path.read_text()
        assert "# Test Document" in content
        assert "Point 1" in content
        assert "Point 2" in content

    def test_export_content_structure(self, output_config, sample_result):
        """测试导出内容结构"""
        exporter = MarkdownExporter(output_config)
        content = exporter._generate_content(sample_result)

        assert "# Test Document" in content
        assert "**Source:** https://example.com/article" in content
        assert "**Chunks:** 3" in content
        assert "## Summary" in content
        assert "- Point 1" in content
        assert "## 学习笔记" in content
        assert "要点1" in content

    def test_sanitize_filename(self, output_config):
        """测试文件名清理"""
        exporter = MarkdownExporter(output_config)

        assert exporter._sanitize_filename("Normal Title") == "Normal Title"
        assert exporter._sanitize_filename("Title: With/Slash") == "Title_ With_Slash"
        assert exporter._sanitize_filename("Title\\With\\Backslash") == "Title_With_Backslash"

    def test_export_error_handling(self, output_config, sample_result):
        """测试导出错误处理"""
        # 使用无效的路径
        bad_config = OutputConfig(
            format="markdown",
            path="/invalid/path/that/does/not/exist",
            filename_template="{title}.md"
        )
        exporter = MarkdownExporter(bad_config)
        result = exporter.export(sample_result)

        assert result.success is False
        assert "error" in result.error.lower() or len(result.error) > 0


class TestObsidianExporter:
    """Obsidian导出测试"""

    def test_export_has_frontmatter(self, output_config, sample_result, tmp_path):
        """测试YAML frontmatter"""
        obsidian_config = OutputConfig(
            format="obsidian",
            path=str(tmp_path),
            filename_template="{title}.md"
        )
        exporter = ObsidianExporter(obsidian_config)
        result = exporter.export(sample_result)

        content = result.file_path.read_text()

        assert content.startswith("---")
        assert 'title: "Test Document"' in content
        assert "tags:" in content
        assert "auto-learning" in content

    def test_bidirectional_links(self, output_config, sample_result):
        """测试双向链接"""
        obsidian_config = OutputConfig(
            format="obsidian",
            path="/tmp",
            filename_template="{title}.md"
        )
        exporter = ObsidianExporter(obsidian_config)
        content = exporter._generate_content(sample_result)

        # 检查双向链接格式 [[Link]]
        assert "[[Python]]" in content or "[[Programming]]" in content
        assert "[[API]]" in content


class TestExporter:
    """统一导出接口测试"""

    def test_export_markdown(self, output_config, sample_result, tmp_path):
        """测试Markdown格式导出"""
        exporter = Exporter(output_config)
        result = exporter.export(sample_result)

        assert result.success is True
        assert result.format in ["markdown", "obsidian"]

    def test_export_obsidian(self, sample_result, tmp_path):
        """测试Obsidian格式导出"""
        obsidian_config = OutputConfig(
            format="obsidian",
            path=str(tmp_path),
            filename_template="{title}.md"
        )
        exporter = Exporter(obsidian_config)
        result = exporter.export(sample_result)

        assert result.success is True
        content = result.file_path.read_text()
        assert content.startswith("---")  # YAML frontmatter

    def test_export_batch(self, output_config, sample_result):
        """测试批量导出"""
        exporter = Exporter(output_config)
        results = exporter.export_batch([sample_result, sample_result])

        assert len(results) == 2
        assert all(r.success for r in results)
