# URL 递归采集功能设计

## 概述

为 `URLCrawler` 增加递归采集功能，支持处理单个URL时自动发现并采集匹配的子页面，将内容合并为单个文档。

## 需求

1. **手动指定链接模式**：用户通过CLI参数指定要匹配的链接模式
2. **合并为单个文档**：所有匹配的页面内容合并后统一生成一个摘要
3. **限制递归深度**：默认限制深度为3

## 实现方案

### 1. 新增方法 (URLCrawler)

```python
def crawl_recursive(
    self,
    url: str,
    patterns: list[str] = None,
    max_depth: int = 3,
    visited: set = None
) -> CrawlResult:
    """
    递归爬取URL及匹配的子页面
    
    Args:
        url: 起始URL
        patterns: 链接匹配模式列表（支持 glob 格式）
        max_depth: 最大递归深度
        visited: 已访问URL集合（内部使用）
    
    Returns:
        CrawlResult: 合并后的文档
    """
```

### 2. 辅助方法

```python
def discover_links(self, soup: BeautifulSoup, base_url: str) -> list[str]:
    """从页面发现所有链接"""
    
def match_pattern(self, url: str, patterns: list[str]) -> bool:
    """判断URL是否匹配任一模式"""

def merge_documents(self, documents: list[Document]) -> Document:
    """合并多个文档为一个"""
```

### 3. CLI 参数

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `--pattern` | str | None | 链接匹配模式（可重复使用） |
| `--max-depth` | int | 3 | 最大递归深度 |
| `--no-merge` | flag | False | 不合并，单独处理每个文档 |

### 4. 内容合并格式

```markdown
# 文档标题

> 来源: https://docs.example.com/guide/
> 采集页面数: 5

---

## Page 1: Introduction
来源: https://docs.example.com/guide/intro

[页面内容...]

---

## Page 2: Installation
来源: https://docs.example.com/guide/install

[页面内容...]

---
```

## 配置文件支持

```yaml
crawl:
  patterns:
    - "*.md"
    - "*/docs/*"
  max_depth: 3
```

## 错误处理

- 链接匹配失败：跳过并记录
- 页面爬取失败：跳过并继续
- 深度耗尽：停止递归
- 循环链接检测：通过 visited 集合防止重复

## 实现任务

1. 修改 `src/crawler/__init__.py`：
   - 在 `URLCrawler` 类中添加 `crawl_recursive()` 方法
   - 添加 `discover_links()`, `match_pattern()`, `merge_documents()` 辅助方法

2. 修改 `src/pipeline.py`：
   - 在 `Pipeline` 类中添加 `process_url_recursive()` 方法

3. 修改 `src/cli.py`：
   - 添加 `--pattern`, `--max-depth`, `--no-merge` 参数
   - 更新 `process` 命令逻辑

4. 更新测试 `tests/test_crawler.py`：
   - 添加递归采集相关测试

## 依赖

无新增依赖，使用现有的：
- `requests` - HTTP请求
- `BeautifulSoup` - HTML解析
- `fnmatch` / `re` - 模式匹配
