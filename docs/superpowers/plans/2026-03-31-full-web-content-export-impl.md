# 网页完整内容导出实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让导出结果默认包含"学习笔记 + 完整网页正文"，并对正文做轻量 Markdown 优化

**Architecture:** 在现有 `MarkdownExporter` 和 `ObsidianExporter` 中新增原文正文导出能力，并在 `BaseExporter` 中实现轻量 Markdown 格式化函数。保持现有抓取和摘要流程不变，仅修改导出阶段。

**Tech Stack:** Python 3.10+, pytest

**参考设计:** [网页完整内容导出设计](/mnt/d/work/ai_learning_system/docs/superpowers/specs/2026-03-31-full-web-content-export-design.md)

---

## 文件结构

| 文件 | 变更类型 | 责任 |
|------|----------|------|
| `src/exporter/__init__.py` | 修改 | 在 `BaseExporter` 新增 `_format_original_content()`；在 `MarkdownExporter._generate_content()` 和 `ObsidianExporter._generate_content()` 中追加原文正文输出 |
| `tests/test_exporter.py` | 修改 | 新增原文正文导出测试、格式化测试、空正文测试；更新现有测试断言 |

---

## Task 1: 新增原文正文格式化函数

**Files:**
- Modify: `src/exporter/__init__.py:22-40` (BaseExporter 类)

- [ ] **Step 1: 在 `BaseExporter` 中实现 `_format_original_content` 方法**

```python
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
    lines = content.split('\n')
    cleaned = []
    
    # 噪音行模式（保守规则）
    noise_patterns = [
        r'^\s*Home\s*$',
        r'^\s*Menu\s*$',
        r'^\s*Navigation\s*$',
        r'^\s*Skip to content\s*$',
        r'^\s*Back to top\s*$',
        r'^\s*上一篇\s*$',
        r'^\s*下一篇\s*$',
        r'^\s*Cookie',
        r'^\s*Privacy',
        r'^\s*Copyright\s*©',
        r'^\s*All rights reserved',
        r'^\s*返回顶部',
        r'^\s*导航',
    ]
    
    prev_line = None
    empty_count = 0
    
    for line in lines:
        stripped = line.strip()
        
        # 跳过噪音行
        is_noise = any(re.match(pattern, stripped, re.IGNORECASE) for pattern in noise_patterns)
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
    result = '\n'.join(cleaned).strip()
    
    return result
```

- [ ] **Step 2: Commit**

```bash
git add src/exporter/__init__.py
git commit -m "feat(exporter): add _format_original_content for light markdown optimization"
```

---

## Task 2: 在 MarkdownExporter 中追加原文正文输出

**Files:**
- Modify: `src/exporter/__init__.py:69-130` (MarkdownExporter._generate_content 方法)

- [ ] **Step 1: 在 `_generate_content` 末尾添加原文正文输出**

找到 `return "\n".join(lines)` 这一行，在其之前插入以下代码：

```python
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
```

修改后，`_generate_content` 方法的完整结构应该是：
1. 标题
2. 元数据
3. 学习笔记 (L2摘要)
4. 原文正文（新增）
5. return

- [ ] **Step 2: Commit**

```bash
git add src/exporter/__init__.py
git commit -m "feat(exporter): append original content to markdown export"
```

---

## Task 3: 在 ObsidianExporter 中追加原文正文输出

**Files:**
- Modify: `src/exporter/__init__.py:160-226` (ObsidianExporter._generate_content 方法)

- [ ] **Step 1: 在 `_generate_content` 末尾添加原文正文输出**

找到 `return "\n".join(lines)` 这一行，在其之前插入以下代码：

```python
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
```

- [ ] **Step 2: Commit**

```bash
git add src/exporter/__init__.py
git commit -m "feat(exporter): append original content to obsidian export"
```

---

## Task 4: 新增格式化函数测试

**Files:**
- Modify: `tests/test_exporter.py`

- [ ] **Step 1: 在 `TestMarkdownExporter` 类中添加格式化测试**

在 `test_export_error_handling` 方法之后添加：

```python
    def test_format_original_content_basic(self, output_config):
        """测试基础格式化：空行合并、首尾清理"""
        exporter = MarkdownExporter(output_config)
        
        content = "\n\n\n第一段内容\n\n\n\n第二段内容\n\n\n"
        result = exporter._format_original_content(content)
        
        # 验证空行被合并为最多2个
        assert "\n\n\n" not in result
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
        lines = [l for l in result.split('\n') if l.strip()]
        assert lines == ["行1", "行2", "行3"]

    def test_format_original_content_empty(self, output_config):
        """测试空内容处理"""
        exporter = MarkdownExporter(output_config)
        
        assert exporter._format_original_content("") == ""
        assert exporter._format_original_content("   ") == ""
        assert exporter._format_original_content("\n\n\n") == ""
```

- [ ] **Step 2: Run tests to verify**

```bash
uv run pytest tests/test_exporter.py::TestMarkdownExporter::test_format_original_content_basic -v
uv run pytest tests/test_exporter.py::TestMarkdownExporter::test_format_original_content_noise_removal -v
uv run pytest tests/test_exporter.py::TestMarkdownExporter::test_format_original_content_duplicate_removal -v
uv run pytest tests/test_exporter.py::TestMarkdownExporter::test_format_original_content_empty -v
```

Expected: All PASS

- [ ] **Step 3: Commit**

```bash
git add tests/test_exporter.py
git commit -m "test(exporter): add tests for _format_original_content"
```

---

## Task 5: 更新导出结构测试

**Files:**
- Modify: `tests/test_exporter.py:60-70` (test_export_content_structure)

- [ ] **Step 1: 修改 `sample_result` fixture 添加 `original_content`**

找到 `sample_result` fixture（大约在第20-40行），添加 `original_content` 字段：

```python
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
```

- [ ] **Step 2: 更新 `test_export_content_structure` 断言**

修改现有测试以验证原文正文导出：

```python
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
```

- [ ] **Step 3: 运行测试验证**

```bash
uv run pytest tests/test_exporter.py::TestMarkdownExporter::test_export_content_structure -v
```

Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add tests/test_exporter.py
git commit -m "test(exporter): update fixture and structure test for original content"
```

---

## Task 6: 新增空正文测试

**Files:**
- Modify: `tests/test_exporter.py`

- [ ] **Step 1: 在 `TestMarkdownExporter` 类中添加空正文测试**

```python
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
```

- [ ] **Step 2: 运行测试验证**

```bash
uv run pytest tests/test_exporter.py::TestMarkdownExporter::test_export_without_original_content -v
```

Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add tests/test_exporter.py
git commit -m "test(exporter): add test for empty original content"
```

---

## Task 7: 更新 Obsidian 导出测试

**Files:**
- Modify: `tests/test_exporter.py:98-129` (TestObsidianExporter 类)

- [ ] **Step 1: 在 `TestObsidianExporter` 中添加原文正文测试**

在 `test_no_bidirectional_links` 之后添加：

```python
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
```

- [ ] **Step 2: 运行所有 Obsidian 测试**

```bash
uv run pytest tests/test_exporter.py::TestObsidianExporter -v
```

Expected: All PASS

- [ ] **Step 3: Commit**

```bash
git add tests/test_exporter.py
git commit -m "test(exporter): add Obsidian exporter tests for original content"
```

---

## Task 8: 运行完整测试套件

**Files:**
- Test: `tests/test_exporter.py`

- [ ] **Step 1: 运行完整测试套件**

```bash
uv run pytest tests/test_exporter.py -v
```

Expected: All PASS (大约 12+ tests)

- [ ] **Step 2: 运行代码质量检查**

```bash
uv run black src/exporter/__init__.py tests/test_exporter.py
uv run ruff check src/exporter/__init__.py tests/test_exporter.py
```

Expected: No errors

- [ ] **Step 3: Commit**

```bash
git add -A
git commit -m "style: format code with black"
```

---

## Task 9: 验证端到端行为

**Files:**
- Manual verification

- [ ] **Step 1: 创建简单测试脚本**

创建临时测试脚本 `test_e2e.py`：

```python
"""端到端测试：验证导出器输出格式"""
from datetime import datetime
from pathlib import Path
import tempfile

from src.exporter import MarkdownExporter, ObsidianExporter
from src.models import ProcessResult, SummaryL1, SummaryL2
from src.config import OutputConfig

# 创建测试数据
result = ProcessResult(
    document_id="test-1",
    document_title="Test Article",
    source_url="https://example.com/article",
    chunks_count=2,
    l1_summary=SummaryL1(
        bullets=["要点1", "要点2"],
        key_concepts=["Python"],
    ),
    l2_summary=SummaryL2(
        overview="这是文章概述。",
        key_points=["关键点A", "关键点B"],
    ),
    original_content="""这是原始网页正文。

Home
Menu

第一段内容，介绍主题。

第二段内容，详细说明。

Back to top

第三段内容，总结。""",
    generated_at=datetime.now(),
)

# 测试 Markdown 导出
with tempfile.TemporaryDirectory() as tmpdir:
    config = OutputConfig(format="markdown", path=tmpdir, filename_template="{title}.md")
    exporter = MarkdownExporter(config)
    export_result = exporter.export(result)
    
    if export_result.success:
        content = export_result.file_path.read_text()
        print("=== Markdown Export ===")
        print(content[:500] + "...\n")
        
        # 验证关键元素
        assert "## 学习笔记" in content
        assert "## 原文正文" in content
        assert "Home" not in content  # 噪音被移除
        assert "Menu" not in content
        assert "Back to top" not in content
        assert "第一段内容" in content
        print("✓ Markdown export verification passed")
    else:
        print(f"✗ Export failed: {export_result.error}")

# 测试 Obsidian 导出
with tempfile.TemporaryDirectory() as tmpdir:
    config = OutputConfig(format="obsidian", path=tmpdir, filename_template="{title}.md")
    exporter = ObsidianExporter(config)
    export_result = exporter.export(result)
    
    if export_result.success:
        content = export_result.file_path.read_text()
        print("\n=== Obsidian Export ===")
        print(content[:500] + "...\n")
        
        assert content.startswith("---")
        assert "## 原文正文" in content
        print("✓ Obsidian export verification passed")
    else:
        print(f"✗ Export failed: {export_result.error}")

print("\n✓ All end-to-end tests passed!")
```

- [ ] **Step 2: 运行测试脚本**

```bash
uv run python test_e2e.py
```

Expected: All checks passed

- [ ] **Step 3: 清理临时文件**

```bash
rm test_e2e.py
```

- [ ] **Step 4: Final commit**

```bash
git add -A
git commit -m "feat(exporter): implement full web content export with markdown optimization

- Add _format_original_content() for light markdown formatting
- Append original content to both Markdown and Obsidian exports
- Include noise filtering for common UI text (Home, Menu, Back to top, etc.)
- Merge consecutive empty lines (max 2)
- Remove duplicate consecutive lines
- Update all tests to verify new export structure

Fixes: content too short in generated documents"
```

---

## Self-Review Checklist

在标记计划完成前，验证以下 spec 要求是否都被覆盖：

| Spec 要求 | 覆盖任务 | 状态 |
|-----------|----------|------|
| 默认导出包含完整网页正文 | Task 2, 3 | ✓ |
| 学习笔记保留在正文之前 | Task 2, 3 (插入位置在学习笔记之后) | ✓ |
| Markdown 结构保留 | Task 1 (不破坏现有 Markdown) | ✓ |
| 空白与段落规整 | Task 1, Task 4 (测试) | ✓ |
| 轻量降噪 | Task 1 (noise_patterns), Task 4 (测试) | ✓ |
| 空正文不输出章节 | Task 6, Task 7 | ✓ |
| Markdown 和 Obsidian 都支持 | Task 2, 3, 7 | ✓ |
| 测试覆盖 | Task 4, 5, 6, 7, 8 | ✓ |
| 代码格式检查 | Task 8 | ✓ |

---

## 执行方式选择

**Plan complete and saved to `docs/superpowers/plans/2026-03-31-full-web-content-export-impl.md`. Two execution options:**

**1. Subagent-Driven (recommended)** - I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints for review

**Which approach?**
