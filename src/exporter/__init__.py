"""导出模块 - Markdown和Obsidian格式导出"""

from pathlib import Path
from datetime import datetime
from dataclasses import dataclass
import re

from src.models import ProcessResult
from src.config import OutputConfig


@dataclass
class ExportResult:
    """导出结果"""

    file_path: Path
    format: str
    success: bool
    error: str = ""


class BaseExporter:
    """导出器基类"""

    def __init__(self, config: OutputConfig):
        self.config = config

    def _sanitize_filename(self, title: str) -> str:
        """清理文件名"""
        # 移除或替换非法字符
        sanitized = re.sub(r'[<>:"/\\|?*]', "_", title)
        sanitized = sanitized.strip(". ")
        return sanitized or "untitled"

    def _ensure_output_dir(self) -> Path:
        """确保输出目录存在"""
        output_dir = Path(self.config.path)
        output_dir.mkdir(parents=True, exist_ok=True)
        return output_dir

    def _format_original_content(self, content: str) -> str:
        """格式化原始内容为可读的 Markdown

        规则：
        1. 空白与段落规整：合并过多空行、清理首尾空白
        2. 结构保留：保留已有 Markdown 结构
        3. 轻量降噪：去除导航、版权等常见噪音
        """
        if not content:
            return ""

        # 1. 基础清理
        lines = content.split("\n")
        cleaned = []

        # 噪音行模式（保守规则）
        noise_patterns = [
            r"^\s*Home\s*$",
            r"^\s*Menu\s*$",
            r"^\s*Navigation\s*$",
            r"^\s*Skip to content\s*$",
            r"^\s*Back to top\s*$",
            r"^\s*上一篇\s*$",
            r"^\s*下一篇\s*$",
            r"^\s*Cookie",
            r"^\s*Privacy",
            r"^\s*Copyright\s*©",
            r"^\s*All rights reserved",
            r"^\s*返回顶部",
            r"^\s*导航",
        ]

        prev_line = None
        empty_count = 0

        for line in lines:
            stripped = line.strip()

            # 跳过噪音行
            is_noise = any(
                re.match(pattern, stripped, re.IGNORECASE) for pattern in noise_patterns
            )
            if is_noise:
                continue

            # 空行处理：合并连续3个以上空行为2个
            if not stripped:
                empty_count += 1
                if empty_count <= 2:
                    cleaned.append("")
                continue
            else:
                empty_count = 0

            # 跳过连续重复行（避免重复段落）
            if stripped == prev_line:
                continue

            cleaned.append(line)
            prev_line = stripped

        # 2. 合并结果并清理首尾
        result = "\n".join(cleaned).strip()

        return result


class MarkdownExporter(BaseExporter):
    """Markdown导出器"""

    def export(self, result: ProcessResult) -> ExportResult:
        """导出为Markdown格式"""
        try:
            output_dir = self._ensure_output_dir()

            # 生成文件名
            filename = self.config.filename_template.format(
                title=self._sanitize_filename(result.document_title)
            )
            file_path = output_dir / filename

            # 生成内容
            content = self._generate_content(result)

            # 写入文件
            file_path.write_text(content, encoding="utf-8")

            return ExportResult(file_path=file_path, format="markdown", success=True)

        except Exception as e:
            return ExportResult(
                file_path=Path(), format="markdown", success=False, error=str(e)
            )

    def _generate_content(self, result: ProcessResult) -> str:
        """生成Markdown内容"""
        lines = []

        # 标题
        lines.append(f"# {result.document_title}")
        lines.append("")

        # 元数据
        if result.source_url:
            lines.append(f"**Source:** {result.source_url}")
            lines.append("")

        lines.append(f"**Generated:** {result.generated_at.strftime('%Y-%m-%d %H:%M')}")
        lines.append(f"**Chunks:** {result.chunks_count}")
        lines.append("")

        # L2摘要（中文笔记）
        if result.l2_summary.overview:
            lines.append("---")
            lines.append("")
            lines.append("## 学习笔记")
            lines.append("")

            lines.append("### 概述")
            lines.append("")
            lines.append(result.l2_summary.overview)
            lines.append("")

            if result.l2_summary.key_points:
                lines.append("### 核心要点")
                lines.append("")
                for point in result.l2_summary.key_points:
                    lines.append(f"- {point}")
                lines.append("")

            if result.l2_summary.concepts_explained:
                lines.append("### 概念解释")
                lines.append("")
                for item in result.l2_summary.concepts_explained:
                    term = item.get("term", "")
                    explanation = item.get("explanation", "")
                    lines.append(f"**{term}**: {explanation}")
                    lines.append("")

        if result.l2_summary.code_examples:
            lines.append("### 代码示例")
            lines.append("")
            for item in result.l2_summary.code_examples:
                lang = item.get("language", "")
                code = item.get("code", "")
                exp = item.get("explanation", "")

                lines.append(f"```{lang}")
                lines.append(code)
                lines.append("```")
                if exp:
                    lines.append("")
                    lines.append(exp)
                lines.append("")

        # 原文正文
        if result.original_content:
            formatted_content = self._format_original_content(result.original_content)
            if formatted_content:
                lines.append("---")
                lines.append("")
                lines.append("## 原文正文")
                lines.append("")
                lines.append(formatted_content)
                lines.append("")

        return "\n".join(lines)


class ObsidianExporter(BaseExporter):
    """Obsidian导出器"""

    def export(self, result: ProcessResult) -> ExportResult:
        """导出为Obsidian格式（带YAML frontmatter）"""
        try:
            output_dir = self._ensure_output_dir()

            # 生成文件名
            filename = self.config.filename_template.format(
                title=self._sanitize_filename(result.document_title)
            )
            file_path = output_dir / filename

            # 生成内容
            content = self._generate_content(result)

            # 写入文件
            file_path.write_text(content, encoding="utf-8")

            return ExportResult(file_path=file_path, format="obsidian", success=True)

        except Exception as e:
            return ExportResult(
                file_path=Path(), format="obsidian", success=False, error=str(e)
            )

    def _generate_content(self, result: ProcessResult) -> str:
        """生成Obsidian内容（带YAML frontmatter）"""
        lines = []

        # YAML frontmatter
        lines.append("---")
        lines.append(f'title: "{result.document_title}"')
        lines.append(f"date: {result.generated_at.strftime('%Y-%m-%d')}")
        lines.append(f"time: {result.generated_at.strftime('%H:%M')}")

        if result.source_url:
            lines.append(f'source: "{result.source_url}"')

        # 标签
        tags = ["auto-learning"]
        tags.extend([f"concept/{c}" for c in result.l1_summary.key_concepts[:5]])
        lines.append(f"tags: [{', '.join(tags)}]")

        lines.append(f"chunks: {result.chunks_count}")
        lines.append("---")
        lines.append("")

        # L2中文笔记
        if result.l2_summary.overview:
            lines.append("---")
            lines.append("")
            lines.append("## 学习笔记")
            lines.append("")

            lines.append("### 概述")
            lines.append("")
            lines.append(result.l2_summary.overview)
            lines.append("")

            if result.l2_summary.key_points:
                lines.append("### 核心要点")
                lines.append("")
                for point in result.l2_summary.key_points:
                    lines.append(f"- {point}")
                lines.append("")

        if result.l2_summary.concepts_explained:
            lines.append("### 概念解释")
            lines.append("")
            for item in result.l2_summary.concepts_explained:
                term = item.get("term", "")
                explanation = item.get("explanation", "")
                lines.append(f"**{term}**: {explanation}")
                lines.append("")

        if result.l2_summary.code_examples:
            lines.append("### 代码示例")
            lines.append("")
            for item in result.l2_summary.code_examples:
                lang = item.get("language", "")
                code = item.get("code", "")
                exp = item.get("explanation", "")

                lines.append(f"```{lang}")
                lines.append(code)
                lines.append("```")
                if exp:
                    lines.append("")
                    lines.append(f"> {exp}")
                lines.append("")

        # 原文正文
        if result.original_content:
            formatted_content = self._format_original_content(result.original_content)
            if formatted_content:
                lines.append("---")
                lines.append("")
                lines.append("## 原文正文")
                lines.append("")
                lines.append(formatted_content)
                lines.append("")

        return "\n".join(lines)


class Exporter:
    """统一导出接口"""

    def __init__(self, config: OutputConfig):
        self.config = config
        self.markdown_exporter = MarkdownExporter(config)
        self.obsidian_exporter = ObsidianExporter(config)

    def export(self, result: ProcessResult) -> ExportResult:
        """根据配置导出"""
        if self.config.format == "obsidian":
            return self.obsidian_exporter.export(result)
        else:
            return self.markdown_exporter.export(result)

    def export_batch(self, results: list[ProcessResult]) -> list[ExportResult]:
        """批量导出"""
        return [self.export(r) for r in results]
