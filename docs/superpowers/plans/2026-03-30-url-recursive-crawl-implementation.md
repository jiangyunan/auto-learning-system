# URL 递归采集功能实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为 URLCrawler 增加递归采集功能，支持手动指定链接模式，合并多页面内容为单个文档

**Architecture:** 在现有 URLCrawler 基础上扩展，通过递归爬取 + 模式匹配发现子页面，最后合并所有内容

**Tech Stack:** Python, requests, BeautifulSoup, fnmatch

---

## 文件结构

```
src/
├── crawler/__init__.py      # 修改: 添加 crawl_recursive 及辅助方法
├── pipeline.py              # 修改: 添加 process_url_recursive 方法
└── cli.py                   # 修改: 添加 --pattern, --max-depth, --no-merge 参数
tests/
└── test_crawler.py          # 修改: 添加递归采集测试
```

---

## Task 1: 实现 URLCrawler 辅助方法

**Files:**
- Modify: `src/crawler/__init__.py:129-165`

- [ ] **Step 1: 添加 discover_links 方法**

在 `_download_images` 方法后添加:

```python
def discover_links(self, soup: BeautifulSoup, base_url: str) -> list[str]:
    """从页面发现所有链接"""
    links = []
    for a in soup.find_all('a', href=True):
        href = a['href']
        if href.startswith(('mailto:', 'tel:', 'javascript:')):
            continue
        full_url = urljoin(base_url, href)
        parsed = urlparse(full_url)
        if parsed.scheme in ('http', 'https'):
            links.append(full_url)
    return list(set(links))  # 去重
```

- [ ] **Step 2: 添加 match_pattern 方法**

```python
import fnmatch

def match_pattern(self, url: str, patterns: list[str]) -> bool:
    """判断URL是否匹配任一模式"""
    if not patterns:
        return True
    parsed = urlparse(url)
    path = parsed.path
    for pattern in patterns:
        if fnmatch.fnmatch(path, pattern) or fnmatch.fnmatch(url, pattern):
            return True
    return False
```

- [ ] **Step 3: 添加 merge_documents 方法**

```python
def merge_documents(self, documents: list[Document], base_url: str) -> Document:
    """合并多个文档为一个"""
    if not documents:
        raise ValueError("No documents to merge")
    if len(documents) == 1:
        return documents[0]
    
    merged = Document(
        id=self._generate_id(base_url),
        source_type=SourceType.URL,
        source_path=base_url,
        title=f"合并文档 ({len(documents)} 页)"
    )
    
    parts = [f"> 来源: {base_url}"]
    parts.append(f"> 采集页面数: {len(documents)}\n")
    
    for i, doc in enumerate(documents, 1):
        parts.append(f"---\n\n## Page {i}: {doc.title or 'Untitled'}")
        parts.append(f"来源: {doc.source_path}\n")
        parts.append(doc.content)
    
    merged.content = "\n".join(parts)
    merged.format = DocFormat.MARKDOWN
    merged.metadata = {
        "url": base_url,
        "merged_count": len(documents),
        "source_urls": [doc.source_path for doc in documents],
    }
    return merged
```

- [ ] **Step 4: 验证代码语法**

Run: `cd /mnt/d/work/ai_learning_system && python -c "from src.crawler import URLCrawler; print('OK')"`
Expected: OK

- [ ] **Step 5: 提交**

```bash
git add src/crawler/__init__.py
git commit -m "feat(crawler): add helper methods for recursive crawl"
```

---

## Task 2: 实现 crawl_recursive 方法

**Files:**
- Modify: `src/crawler/__init__.py:46-92`

- [ ] **Step 1: 在 URLCrawler 类中添加 crawl_recursive 方法**

在 `crawl` 方法后添加:

```python
def crawl_recursive(
    self,
    url: str,
    patterns: list[str] = None,
    max_depth: int = 3,
    visited: set = None,
    download_images: bool = False,
    image_dir: Path = None
) -> CrawlResult:
    """
    递归爬取URL及匹配的子页面
    
    Args:
        url: 起始URL
        patterns: 链接匹配模式列表（支持 glob 格式）
        max_depth: 最大递归深度
        visited: 已访问URL集合（内部使用）
        download_images: 是否下载图片
        image_dir: 图片保存目录
    
    Returns:
        CrawlResult: 合并后的文档及统计信息
    """
    if visited is None:
        visited = set()
    
    result = CrawlResult(
        document=Document(
            id=self._generate_id(url),
            source_type=SourceType.URL,
            source_path=url,
        )
    )
    
    if url in visited:
        return result
    visited.add(url)
    
    try:
        response = requests.get(url, headers=self.headers, timeout=self.timeout)
        response.raise_for_status()
        response.encoding = response.apparent_encoding or "utf-8"
        
        soup = BeautifulSoup(response.text, "html.parser")
        
        title = self._extract_title(soup)
        content = self._extract_content(soup)
        
        current_doc = Document(
            id=self._generate_id(url),
            source_type=SourceType.URL,
            source_path=url,
            title=title,
            content=content,
            format=DocFormat.HTML,
        )
        
        documents = [current_doc]
        child_urls = []
        
        if max_depth > 0:
            links = self.discover_links(soup, url)
            for link in links:
                if link not in visited and self.match_pattern(link, patterns):
                    child_urls.append(link)
        
        for child_url in child_urls:
            child_result = self.crawl_recursive(
                child_url,
                patterns=patterns,
                max_depth=max_depth - 1,
                visited=visited,
                download_images=download_images,
                image_dir=image_dir
            )
            if child_result.document.content:
                documents.append(child_result.document)
            result.errors.extend(child_result.errors)
        
        merged_doc = self.merge_documents(documents, url)
        result.document = merged_doc
        result.images_downloaded = len([img for img in merged_doc.images if img.local_path])
        
    except Exception as e:
        result.errors.append(f"{url}: {str(e)}")
    
    return result
```

- [ ] **Step 2: 验证代码语法**

Run: `cd /mnt/d/work/ai_learning_system && python -c "from src.crawler import URLCrawler; c = URLCrawler(); print(hasattr(c, 'crawl_recursive'))"`
Expected: True

- [ ] **Step 3: 提交**

```bash
git add src/crawler/__init__.py
git commit -m "feat(crawler): implement crawl_recursive method"
```

---

## Task 3: 更新 Crawler 统一接口

**Files:**
- Modify: `src/crawler/__init__.py:436-478`

- [ ] **Step 1: 在 Crawler 类中添加 crawl_url_recursive 方法**

在 `crawl_url` 方法后添加:

```python
def crawl_url_recursive(self, url: str, patterns: list[str] = None, max_depth: int = 3, **kwargs) -> CrawlResult:
    """递归爬取URL及匹配的子页面"""
    return self.url_crawler.crawl_recursive(url, patterns=patterns, max_depth=max_depth, **kwargs)
```

- [ ] **Step 2: 验证代码语法**

Run: `cd /mnt/d/work/ai_learning_system && python -c "from src.crawler import Crawler; c = Crawler(); print(hasattr(c, 'crawl_url_recursive'))"`
Expected: True

- [ ] **Step 3: 提交**

```bash
git add src/crawler/__init__.py
git commit -m "feat(crawler): add crawl_url_recursive to unified interface"
```

---

## Task 4: 更新 Pipeline 支持递归采集

**Files:**
- Modify: `src/pipeline.py:46-108`

- [ ] **Step 1: 在 Pipeline 类中添加 process_url_recursive 方法**

在 `process_document` 方法后添加:

```python
async def process_url_recursive(
    self,
    url: str,
    patterns: list[str] = None,
    max_depth: int = 3,
    progress_callback=None
) -> ProcessResult:
    """处理URL（递归采集所有匹配页面并合并）"""
    if progress_callback:
        progress_callback(PipelineProgress("crawl", 0, 4, f"Fetching {url}..."))
    
    crawl_result = self.crawler.crawl_url_recursive(url, patterns=patterns, max_depth=max_depth)
    
    if not crawl_result or not crawl_result.document.content:
        raise ValueError(f"Failed to crawl: {url}")
    
    doc = crawl_result.document
    
    if progress_callback:
        progress_callback(PipelineProgress("chunk", 1, 4, "Chunking document..."))
    
    chunks = list(self.chunker.chunk(doc.id, doc.content))
    
    if progress_callback:
        progress_callback(PipelineProgress("summarize", 2, 4, f"Summarizing {len(chunks)} chunks..."))
    
    chunk_summaries = []
    for chunk in chunks:
        summary = await self.summarizer.summarize_chunk(chunk)
        chunk_summaries.append(summary)
    
    l1_summaries = [s.l1 for s in chunk_summaries]
    l2_summaries = [s.l2 for s in chunk_summaries if s.l2.overview]
    
    merged_l1 = await self.summarizer.merge_l1_summaries(l1_summaries)
    merged_l2 = await self.summarizer.merge_l2_summaries(l2_summaries)
    
    result = ProcessResult(
        document_id=doc.id,
        document_title=doc.title,
        source_url=url,
        chunks_count=len(chunks),
        l1_summary=merged_l1,
        l2_summary=merged_l2,
    )
    
    if progress_callback:
        progress_callback(PipelineProgress("export", 3, 4, "Exporting..."))
    
    export_result = self.exporter.export(result)
    if export_result.success:
        result.output_path = export_result.file_path
    
    if progress_callback:
        progress_callback(PipelineProgress("complete", 4, 4, "Done!"))
    
    return result
```

- [ ] **Step 2: 验证代码语法**

Run: `cd /mnt/d/work/ai_learning_system && python -c "from src.pipeline import Pipeline; print('OK')"`
Expected: OK

- [ ] **Step 3: 提交**

```bash
git add src/pipeline.py
git commit -m "feat(pipeline): add process_url_recursive method"
```

---

## Task 5: 更新 CLI 参数

**Files:**
- Modify: `src/cli.py:18-97`

- [ ] **Step 1: 修改 process 命令，添加新参数**

更新 `process` 函数签名:

```python
@app.command()
def process(
    source: str = typer.Argument(..., help="文档来源 (URL, 文件路径或目录)"),
    config_path: Optional[str] = typer.Option(None, "--config", "-c", help="配置文件路径"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="详细输出"),
    recursive: bool = typer.Option(True, "--recursive", "-r", help="递归处理子文件夹"),
    no_related_context: bool = typer.Option(False, "--no-related-context", help="不包含相关文档上下文"),
    pattern: Optional[list[str]] = typer.Option(None, "--pattern", "-p", help="URL匹配模式 (可用于URL递归采集)"),
    max_depth: int = typer.Option(3, "--max-depth", "-d", help="URL递归最大深度"),
    no_merge: bool = typer.Option(False, "--no-merge", help="不合并URL页面，单独处理"),
):
```

- [ ] **Step 2: 更新 process 命令逻辑**

在 `async def run()` 中，修改 URL 处理逻辑:

```python
async def run():
    if is_folder:
        # 文件夹处理模式
        result = await pipeline.process_folder(
            source,
            recursive=recursive,
            include_related_context=not no_related_context,
            progress_callback=progress_callback
        )
        progress.update(task, description=f"✓ Processed {len(result.results)} documents")
        return result
    elif source.startswith(("http://", "https://")):
        # URL处理模式
        if pattern:
            # 递归采集模式
            result = await pipeline.process_url_recursive(
                source,
                patterns=pattern,
                max_depth=max_depth,
                progress_callback=progress_callback
            )
            progress.update(task, description=f"✓ Exported to {result.output_path}")
            return result
        else:
            # 单URL处理
            result = await pipeline.process_document(source, progress_callback)
            progress.update(task, description=f"✓ Exported to {result.output_path}")
            return result
    else:
        # 单文件处理
        result = await pipeline.process_document(source, progress_callback)
        progress.update(task, description=f"✓ Exported to {result.output_path}")
        return result
```

- [ ] **Step 3: 验证CLI帮助**

Run: `cd /mnt/d/work/ai_learning_system && python -m src.cli process --help`
Expected: 输出中应包含 --pattern, --max-depth, --no-merge 参数说明

- [ ] **Step 4: 提交**

```bash
git add src/cli.py
git commit -m "feat(cli): add --pattern, --max-depth, --no-merge for URL recursive crawl"
```

---

## Task 6: 添加测试

**Files:**
- Modify: `tests/test_crawler.py`

- [ ] **Step 1: 添加 discover_links 测试**

```python
def test_discover_links():
    from src.crawler import URLCrawler
    from bs4 import BeautifulSoup
    
    crawler = URLCrawler()
    html = """
    <html>
        <body>
            <a href="/page1">Page 1</a>
            <a href="/page2">Page 2</a>
            <a href="https://other.com/page">External</a>
            <a href="mailto:test@example.com">Email</a>
        </body>
    </html>
    """
    soup = BeautifulSoup(html, "html.parser")
    links = crawler.discover_links(soup, "https://example.com/")
    
    assert "https://example.com/page1" in links
    assert "https://example.com/page2" in links
    assert "https://other.com/page" in links
    assert len(links) == 3  # 排除 mailto
```

- [ ] **Step 2: 添加 match_pattern 测试**

```python
def test_match_pattern():
    from src.crawler import URLCrawler
    
    crawler = URLCrawler()
    
    # 无模式
    assert crawler.match_pattern("https://example.com/page", None) == True
    assert crawler.match_pattern("https://example.com/page", []) == True
    
    # glob 模式
    assert crawler.match_pattern("https://example.com/docs/page.md", ["*.md"]) == True
    assert crawler.match_pattern("https://example.com/docs/page.txt", ["*.md"]) == False
    assert crawler.match_pattern("https://example.com/docs/page", ["*/docs/*"]) == True
    assert crawler.match_pattern("https://example.com/api/page", ["*/docs/*"]) == False
```

- [ ] **Step 3: 添加 merge_documents 测试**

```python
def test_merge_documents():
    from src.crawler import URLCrawler
    from src.models import Document, SourceType, DocFormat
    
    crawler = URLCrawler()
    docs = [
        Document(id="1", source_type=SourceType.URL, source_path="https://example.com/1", 
                 title="Page 1", content="Content 1"),
        Document(id="2", source_type=SourceType.URL, source_path="https://example.com/2",
                 title="Page 2", content="Content 2"),
    ]
    
    merged = crawler.merge_documents(docs, "https://example.com")
    
    assert merged.title == "合并文档 (2 页)"
    assert "Page 1" in merged.content
    assert "Page 2" in merged.content
    assert "Content 1" in merged.content
    assert "Content 2" in merged.content
    assert merged.metadata["merged_count"] == 2
```

- [ ] **Step 4: 运行测试**

Run: `cd /mnt/d/work/ai_learning_system && python -m pytest tests/test_crawler.py -v -k "discover or match_pattern or merge"`
Expected: 所有测试通过

- [ ] **Step 5: 提交**

```bash
git add tests/test_crawler.py
git commit -m "test: add tests for recursive crawl features"
```

---

## Task 7: 更新配置示例

**Files:**
- Modify: `config.yaml.example`

- [ ] **Step 1: 添加 crawl 配置示例**

在文件末尾添加:

```yaml
# URL递归采集配置 (可选)
crawl:
  patterns:
    - "*.md"
    - "*/docs/*"
  max_depth: 3
```

- [ ] **Step 2: 提交**

```bash
git add config.yaml.example
git commit -m "docs: add crawl config example"
```

---

## 验证清单

- [ ] `python -m src.cli process --help` 显示新参数
- [ ] `python -m pytest tests/test_crawler.py -v` 所有测试通过
- [ ] 手动测试: `python -m src.cli process "https://example.com" --pattern "*.md" --max-depth 2 -v`

---

**Plan complete.** 两个执行选项：

1. **Subagent-Driven (推荐)** - 每个任务派发一个子agent，快速迭代
2. **Inline Execution** - 在当前会话批量执行，带检查点
