# 开发变更日志 (Development Changelog)

本文件记录项目的所有代码修改、功能更新和架构调整。

## 格式规范

每个变更记录包含：
- **日期**: YYYY-MM-DD
- **类型**: feature | fix | refactor | docs | test
- **描述**: 变更内容简述
- **文件**: 受影响的文件列表
- **详情**: 详细说明（如需要）

---

## 2026-03-31

### 导出格式优化

**类型**: refactor  
**描述**: 根据用户需求，简化导出文档格式，移除原文Summary和Related Topics，Obsidian格式移除双向链接

**修改文件**:
- `src/exporter/__init__.py`
- `tests/test_exporter.py`

**详细变更**:

#### 1. Markdown 导出格式 (MarkdownExporter)

**移除内容**:
- `## Summary` 部分（包含 L1 摘要的 bullet points）
- `### Key Concepts` 部分

**变更前**:
```markdown
# Title

**Source:** https://example.com
**Generated:** 2024-01-15 10:30
**Chunks:** 3

## Summary

- Point 1
- Point 2

### Key Concepts

- `Python`
- `Async`

---

## 学习笔记
...
```

**变更后**:
```markdown
# Title

**Source:** https://example.com
**Generated:** 2024-01-15 10:30
**Chunks:** 3

---

## 学习笔记
...
```

#### 2. Obsidian 导出格式 (ObsidianExporter)

**移除内容**:
- `## Related Topics` 部分
- `## Summary` 部分
- `### Key Concepts` 部分
- 所有双向链接格式 `[[Link]]`

**变更前**:
```markdown
---
title: "Document"
date: 2024-01-15
tags: [auto-learning, concept/Python]
chunks: 3
---

## Related Topics

- [[Programming]]
- [[Python]]

## Summary

- Point 1
- Point 2

### Key Concepts

- [[Python]] `Python`
- [[Async]] `Async`

---

## 学习笔记

### 概念解释

#### [[API]] API

接口说明...
```

**变更后**:
```markdown
---
title: "Document"
date: 2024-01-15
tags: [auto-learning, concept/Python]
chunks: 3
---

---

## 学习笔记

### 概念解释

**API**: 接口说明...
```

**代码修改位置**:
- `src/exporter/__init__.py:69-100` - MarkdownExporter._generate_content()
- `src/exporter/__init__.py:175-210` - ObsidianExporter._generate_content()

#### 3. 测试文件更新

**修改文件**: `tests/test_exporter.py`

**变更内容**:
1. `test_export_basic()`: 移除对 "Point 1" 的断言，改为验证 "要点1" 存在
2. `test_export_content_structure()`: 移除对 "## Summary" 的断言
3. `test_bidirectional_links()` → `test_no_bidirectional_links()`: 改为验证双向链接不存在

**理由**:
- 用户反馈原文 Summary 和 Related Topics 冗余
- Obsidian 双向链接在简单学习场景中不需要
- 简化输出，聚焦于中文学习笔记内容

**测试状态**: ✅ 9/9 测试通过

---

## 变更统计

| 指标 | 本次变更 |
|------|----------|
| 修改文件数 | 2 |
| 删除代码行 | ~50 行 |
| 新增代码行 | ~5 行 |
| 测试更新 | 3 个测试用例 |

---

## 版本标记

- **当前版本**: v1.1.1
- **变更日期**: 2026-03-31
- **变更类型**: 格式优化 (breaking change)

**兼容性说明**:
- 此变更为破坏性变更（Breaking Change）
- 旧版本生成的文档格式不再兼容
- 建议用户在升级后重新处理已有文档
