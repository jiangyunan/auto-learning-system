"""导出模块测试"""

import pytest
from datetime import datetime

from src.exporter import MarkdownExporter, ObsidianExporter, Exporter
from src.models import ProcessResult, SummaryL1, SummaryL2
from src.config import OutputConfig


@pytest.fixture
def output_config(tmp_path):
    return OutputConfig(
        format="markdown", path=str(tmp_path), filename_template="{title}.md"
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
            code_examples=[
                {"language": "python", "code": "print('hello')", "explanation": "示例"}
            ],
            related_topics=["Programming", "Python"],
        ),
        original_content="这是原始网页正文的第一段。\n\n这是第二段内容，包含一些技术细节。\n\n\n\n\n这是最后一段。",  # 新增
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
        # 新的格式：不包含原文Summary，只包含学习笔记
        assert "要点1" in content

    def test_export_content_structure(self, output_config, sample_result):
        """测试导出内容结构"""
        exporter = MarkdownExporter(output_config)
        content = exporter._generate_content(sample_result)

        assert "# Test Document" in content
        assert "**Source:** https://example.com/article" in content
        assert "**Chunks:** 3" in content
        assert "## 学习笔记" in content
        assert "要点1" in content
        # 验证原文正文区块
        assert "## 原文正文" in content
        assert "这是原始网页正文的第一段" in content

    def test_sanitize_filename(self, output_config):
        """测试文件名清理"""
        exporter = MarkdownExporter(output_config)

        assert exporter._sanitize_filename("Normal Title") == "Normal Title"
        assert exporter._sanitize_filename("Title: With/Slash") == "Title_ With_Slash"
        assert (
            exporter._sanitize_filename("Title\\With\\Backslash")
            == "Title_With_Backslash"
        )

    def test_export_error_handling(self, output_config, sample_result):
        """测试导出错误处理"""
        # 使用无效的路径
        bad_config = OutputConfig(
            format="markdown",
            path="/invalid/path/that/does/not/exist",
            filename_template="{title}.md",
        )
        exporter = MarkdownExporter(bad_config)
        result = exporter.export(sample_result)

        assert result.success is False
        assert "error" in result.error.lower() or len(result.error) > 0

    def test_format_original_content_basic(self, output_config):
        """测试基础格式化：空行合并、首尾清理"""
        exporter = MarkdownExporter(output_config)

        content = "\n\n\n第一段内容\n\n\n\n第二段内容\n\n\n"
        result = exporter._format_original_content(content)

        # 验证连续4个以上空行被合并（保留最多2个空行，即3个换行符）
        # 允许段落间有3个换行符（2空行+内容行）
        assert "\n\n\n\n" not in result
        # 验证首尾空白被清理
        assert not result.startswith("\n")
        assert not result.endswith("\n")
        # 验证内容保留
        assert "第一段内容" in result
        assert "第二段内容" in result

    def test_format_original_content_noise_removal(self, output_config):
        """测试噪音行过滤"""
        exporter = MarkdownExporter(output_config)

        content = """正文第一段
Home
Menu
正文第二段
Back to top
上一篇
Copyright © 2024
正文第三段"""

        result = exporter._format_original_content(content)

        # 验证噪音被移除
        assert "Home" not in result
        assert "Menu" not in result
        assert "Back to top" not in result
        assert "上一篇" not in result
        assert "Copyright" not in result
        # 验证正文保留
        assert "正文第一段" in result
        assert "正文第二段" in result
        assert "正文第三段" in result

    def test_format_original_content_duplicate_removal(self, output_config):
        """测试重复行压缩"""
        exporter = MarkdownExporter(output_config)

        content = "行1\n行1\n行1\n行2\n行2\n行3"
        result = exporter._format_original_content(content)

        # 验证连续重复被压缩
        lines = [line for line in result.split("\n") if line.strip()]
        assert lines == ["行1", "行2", "行3"]

    def test_format_original_content_empty(self, output_config):
        """测试空内容处理"""
        exporter = MarkdownExporter(output_config)

        assert exporter._format_original_content("") == ""
        assert exporter._format_original_content("   ") == ""
        assert exporter._format_original_content("\n\n\n") == ""

    def test_export_without_original_content(self, output_config):
        """测试当 original_content 为空时不输出原文正文章节"""
        from datetime import datetime

        result_without_content = ProcessResult(
            document_id="doc-2",
            document_title="Empty Content Doc",
            source_url="https://example.com/empty",
            chunks_count=1,
            l1_summary=SummaryL1(bullets=["Point"], key_concepts=["Test"]),
            l2_summary=SummaryL2(overview="概述"),
            original_content="",  # 空正文
            generated_at=datetime(2024, 1, 15, 10, 30),
        )

        exporter = MarkdownExporter(output_config)
        content = exporter._generate_content(result_without_content)

        # 验证学习笔记仍然存在
        assert "## 学习笔记" in content
        assert "概述" in content
        # 验证原文正文章节不存在
        assert "## 原文正文" not in content


class TestObsidianExporter:
    """Obsidian导出测试"""

    def test_export_has_frontmatter(self, output_config, sample_result, tmp_path):
        """测试YAML frontmatter"""
        obsidian_config = OutputConfig(
            format="obsidian", path=str(tmp_path), filename_template="{title}.md"
        )
        exporter = ObsidianExporter(obsidian_config)
        result = exporter.export(sample_result)

        content = result.file_path.read_text()

        assert content.startswith("---")
        assert 'title: "Test Document"' in content
        assert "tags:" in content
        assert "auto-learning" in content

    def test_no_bidirectional_links(self, output_config, sample_result):
        """测试不再包含双向链接"""
        obsidian_config = OutputConfig(
            format="obsidian", path="/tmp", filename_template="{title}.md"
        )
        exporter = ObsidianExporter(obsidian_config)
        content = exporter._generate_content(sample_result)

        # 新的格式：不再包含双向链接
        assert "[[Python]]" not in content
        assert "[[Programming]]" not in content
        assert "[[API]]" not in content
        # 但仍然包含内容
        assert "这是概述" in content

    def test_export_includes_original_content(self, output_config, sample_result):
        """测试 Obsidian 导出包含原文正文"""
        obsidian_config = OutputConfig(
            format="obsidian", path="/tmp", filename_template="{title}.md"
        )
        exporter = ObsidianExporter(obsidian_config)
        content = exporter._generate_content(sample_result)

        # 验证 frontmatter 存在
        assert content.startswith("---")
        # 验证学习笔记存在
        assert "## 学习笔记" in content
        assert "这是概述" in content
        # 验证原文正文存在
        assert "## 原文正文" in content
        assert "这是原始网页正文的第一段" in content

    def test_export_without_original_content_obsidian(self, output_config):
        """测试 Obsidian 导出当 original_content 为空"""
        from datetime import datetime

        result_without_content = ProcessResult(
            document_id="doc-3",
            document_title="No Content",
            source_url="https://example.com",
            chunks_count=1,
            l1_summary=SummaryL1(bullets=["B"], key_concepts=["C"]),
            l2_summary=SummaryL2(overview="概述"),
            original_content="",
            generated_at=datetime(2024, 1, 15, 10, 30),
        )

        obsidian_config = OutputConfig(
            format="obsidian", path="/tmp", filename_template="{title}.md"
        )
        exporter = ObsidianExporter(obsidian_config)
        content = exporter._generate_content(result_without_content)

        assert "## 学习笔记" in content
        assert "## 原文正文" not in content


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
            format="obsidian", path=str(tmp_path), filename_template="{title}.md"
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
