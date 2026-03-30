"""爬虫模块 - 支持URL、本地文件和PDF"""

import fnmatch
import hashlib
import re
import time
from pathlib import Path
from typing import Iterator
from urllib.parse import urljoin, urlparse
from dataclasses import dataclass

import requests
import fitz  # PyMuPDF
from bs4 import BeautifulSoup

from src.models import Document, SourceType, DocFormat, ImageInfo, Link, DocumentGraph


WIKI_LINK_PATTERN = re.compile(r"\[\[([^\]|]+)(?:\|[^\]]*)?\]\]")
MARKDOWN_LINK_PATTERN = re.compile(r"\[([^\]]*)\]\(([^)]+)\)")
MARKDOWN_IMAGE_PATTERN = re.compile(r"!\[([^\]]*)\]\(([^)]+)\)")


@dataclass
class CrawlResult:
    """爬取结果"""

    document: Document
    images_downloaded: int = 0
    errors: list[str] = None

    def __post_init__(self):
        if self.errors is None:
            self.errors = []


class BaseCrawler:
    """爬虫基类"""

    def __init__(self, timeout: int = 30, headers: dict = None):
        self.timeout = timeout
        self.headers = headers or {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.0"
        }

    def _generate_id(self, source: str) -> str:
        """生成文档ID"""
        return hashlib.sha256(source.encode()).hexdigest()[:16]


class URLCrawler(BaseCrawler):
    """URL爬虫"""

    def crawl(
        self, url: str, download_images: bool = False, image_dir: Path = None
    ) -> CrawlResult:
        """爬取URL内容"""
        result = CrawlResult(
            document=Document(
                id=self._generate_id(url),
                source_type=SourceType.URL,
                source_path=url,
            )
        )

        try:
            response = requests.get(url, headers=self.headers, timeout=self.timeout)
            response.raise_for_status()
            response.encoding = response.apparent_encoding or "utf-8"

            soup = BeautifulSoup(response.text, "html.parser")

            # 提取标题
            title = self._extract_title(soup)

            # 提取主要内容
            content = self._extract_content(soup)

            # 处理图片
            images = []
            if download_images and image_dir:
                images = self._download_images(soup, url, image_dir)
                result.images_downloaded = len(
                    [img for img in images if img.local_path]
                )

            result.document.title = title
            result.document.content = content
            result.document.format = DocFormat.HTML
            result.document.images = images
            result.document.metadata = {
                "url": url,
                "status_code": response.status_code,
                "content_type": response.headers.get("Content-Type", ""),
            }

        except Exception as e:
            result.errors.append(str(e))

        return result

    def crawl_recursive(
        self,
        url: str,
        patterns: list[str] | None = None,
        max_depth: int = 3,
        visited: set | None = None,
        download_images: bool = False,
        image_dir: Path = None,
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
                time.sleep(0.1)
                child_result = self.crawl_recursive(
                    child_url,
                    patterns=patterns,
                    max_depth=max_depth - 1,
                    visited=visited,
                    download_images=download_images,
                    image_dir=image_dir,
                )
                if child_result.document.content:
                    documents.append(child_result.document)
                result.errors.extend(child_result.errors)

            merged_doc = self.merge_documents(documents, url)
            result.document = merged_doc
            result.images_downloaded = len(
                [img for img in merged_doc.images if img.local_path]
            )

        except Exception as e:
            result.errors.append(f"{url}: {str(e)}")

        return result

    def _extract_title(self, soup: BeautifulSoup) -> str:
        """提取页面标题"""
        # 尝试各种标题选择器
        for selector in ["h1", ".article-title", ".post-title", "title"]:
            elem = soup.select_one(selector)
            if elem:
                return elem.get_text(strip=True)
        return ""

    def _extract_content(self, soup: BeautifulSoup) -> str:
        """提取主要内容"""
        # 尝试常见的内容容器
        for selector in [
            "article",
            "main",
            ".content",
            ".article-content",
            ".post-content",
            ".markdown-body",
            "[role='main']",
        ]:
            elem = soup.select_one(selector)
            if elem:
                return elem.get_text(separator="\n", strip=True)

        # 回退：提取body文本
        body = soup.find("body")
        if body:
            # 移除脚本和样式
            for tag in body.find_all(["script", "style", "nav", "footer", "header"]):
                tag.decompose()
            return body.get_text(separator="\n", strip=True)

        return ""

    def _download_images(
        self, soup: BeautifulSoup, base_url: str, image_dir: Path
    ) -> list[ImageInfo]:
        """下载页面图片"""
        images = []
        image_dir.mkdir(parents=True, exist_ok=True)

        for img in soup.find_all("img"):
            src = img.get("src")
            if not src:
                continue

            # 处理相对URL
            full_url = urljoin(base_url, src)

            # 生成本地文件名
            parsed = urlparse(full_url)
            ext = Path(parsed.path).suffix or ".png"
            local_name = f"{hashlib.md5(full_url.encode()).hexdigest()[:12]}{ext}"
            local_path = image_dir / local_name

            try:
                response = requests.get(
                    full_url, headers=self.headers, timeout=self.timeout
                )
                response.raise_for_status()
                local_path.write_bytes(response.content)

                images.append(
                    ImageInfo(
                        original_url=full_url,
                        local_path=local_path,
                        alt_text=img.get("alt", ""),
                    )
                )
            except Exception:
                # 下载失败但仍记录原URL
                images.append(
                    ImageInfo(
                        original_url=full_url,
                        alt_text=img.get("alt", ""),
                    )
                )

        return images

    def discover_links(self, soup: BeautifulSoup, base_url: str) -> list[str]:
        """从页面发现所有链接"""
        links = []
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if href.startswith(("mailto:", "tel:", "javascript:")):
                continue
            full_url = urljoin(base_url, href)
            parsed = urlparse(full_url)
            if parsed.scheme in ("http", "https"):
                links.append(full_url)
        return list(set(links))

    def match_pattern(self, url: str, patterns: list[str] | None) -> bool:
        """判断URL是否匹配任一模式"""
        if not patterns:
            return True
        for pattern in patterns:
            if fnmatch.fnmatch(url, pattern):
                return True
        return False

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
            title=f"合并文档 ({len(documents)} 页)",
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


class LocalFileCrawler(BaseCrawler):
    """本地文件爬虫 - 支持文件夹批量处理和链接关系分析"""

    def crawl(
        self, file_path: Path | str, recursive: bool = False, build_graph: bool = True
    ) -> Iterator[CrawlResult]:
        """
        爬取本地文件

        Args:
            file_path: 文件或文件夹路径
            recursive: 是否递归处理子文件夹
            build_graph: 是否构建文档关系图（仅在处理文件夹时有效）
        """
        path = Path(file_path)

        if path.is_file():
            yield self._process_file(path)
        elif path.is_dir():
            if build_graph:
                # 构建文档关系图并按依赖顺序处理
                graph = self._build_graph(path, recursive)
                stats = graph.get_statistics()
                print(
                    f"Document graph: {stats['total_documents']} documents, {stats['total_links']} links"
                )
                if stats["broken_links"] > 0:
                    print(f"  Warning: {stats['broken_links']} broken links detected")

                processing_order = graph.get_processing_order()
                for doc_id in processing_order:
                    doc = graph.documents[doc_id]
                    result = CrawlResult(document=doc)
                    result.document.metadata["graph"] = graph
                    result.document.metadata["related_docs"] = (
                        graph.get_related_documents(doc_id)
                    )
                    yield result
            else:
                # 简单模式：不按顺序处理
                pattern = path.rglob("*.md") if recursive else path.glob("*.md")
                for file_path in pattern:
                    yield self._process_file(file_path)

    def crawl_folder(
        self, folder_path: Path | str, recursive: bool = True
    ) -> DocumentGraph:
        """
        爬取整个文件夹并返回文档关系图

        Args:
            folder_path: 文件夹路径
            recursive: 是否递归处理子文件夹

        Returns:
            DocumentGraph: 包含所有文档和链接关系的图
        """
        path = Path(folder_path)
        if not path.is_dir():
            raise ValueError(f"Not a directory: {path}")

        return self._build_graph(path, recursive)

    def _build_graph(self, root_path: Path, recursive: bool) -> DocumentGraph:
        """构建文档关系图"""
        graph = DocumentGraph(root_path=root_path)

        # 第一步：收集所有文档
        pattern = root_path.rglob("*.md") if recursive else root_path.glob("*.md")
        for file_path in pattern:
            result = self._process_file(file_path)
            if result.document.content:
                graph.add_document(result.document)

        # 第二步：解析所有文档中的链接
        for doc in list(graph.documents.values()):
            links = self._extract_links(doc)
            for link in links:
                graph.add_link(link)

        return graph

    def _extract_links(self, doc: Document) -> list[Link]:
        """从文档内容中提取链接"""
        links = []
        content = doc.content
        doc_path = Path(doc.source_path)
        doc_dir = doc_path.parent

        for line_num, line in enumerate(content.split("\n"), 1):
            # 提取 [[Wiki链接]]
            for match in WIKI_LINK_PATTERN.finditer(line):
                link_text = match.group(1).strip()
                # Wiki链接可能有别名：[[Target|Display]]
                target = link_text.split("|")[0].strip()

                links.append(
                    Link(
                        source_doc_id=doc.id,
                        target_path=target,
                        link_text=target,
                        link_type="wiki",
                        line_number=line_num,
                    )
                )

            # 提取 [Text](path) Markdown链接（排除图片）
            for match in MARKDOWN_LINK_PATTERN.finditer(line):
                # 确保不是图片链接
                start_pos = match.start()
                if start_pos > 0 and line[start_pos - 1] == "!":
                    continue

                link_text = match.group(1)
                target_path = match.group(2).strip()

                # 忽略外部URL
                if target_path.startswith(("http://", "https://", "#")):
                    continue

                # 解析相对路径
                resolved_target = self._resolve_link_path(target_path, doc_dir)

                links.append(
                    Link(
                        source_doc_id=doc.id,
                        target_path=resolved_target,
                        link_text=link_text,
                        link_type="markdown",
                        line_number=line_num,
                    )
                )

        return links

    def _resolve_link_path(self, target_path: str, base_dir: Path) -> str:
        """解析链接路径为相对或绝对路径"""
        # 如果是绝对路径（以/开头），视为相对于根目录
        if target_path.startswith("/"):
            return target_path[1:]

        # 如果是锚点链接，指向同一文件
        if target_path.startswith("#"):
            return ""

        # 处理相对路径
        target = Path(target_path)
        if target.is_absolute():
            return str(target)

        # 尝试解析为相对于当前文件的绝对路径
        resolved = (base_dir / target).resolve()
        return str(resolved)

    def _process_file(self, file_path: Path) -> CrawlResult:
        """处理单个文件"""
        result = CrawlResult(
            document=Document(
                id=self._generate_id(str(file_path)),
                source_type=SourceType.LOCAL_FILE,
                source_path=str(file_path),
            )
        )

        try:
            content = file_path.read_text(encoding="utf-8")

            # 尝试从内容提取标题
            title = self._extract_markdown_title(content) or file_path.stem

            result.document.title = title
            result.document.content = content
            result.document.format = DocFormat.MARKDOWN
            result.document.metadata = {
                "file_path": str(file_path),
                "file_size": file_path.stat().st_size,
                "relative_path": file_path.name,
            }

        except Exception as e:
            result.errors.append(str(e))

        return result

    def _extract_markdown_title(self, content: str) -> str:
        """从Markdown内容提取标题"""
        # 查找第一个 # 开头的行
        match = re.search(r"^#\s+(.+)$", content, re.MULTILINE)
        if match:
            return match.group(1).strip()
        return ""


class PDFCrawler(BaseCrawler):
    """PDF爬虫"""

    def crawl(
        self, pdf_path: Path | str, extract_images: bool = False, image_dir: Path = None
    ) -> CrawlResult:
        """爬取PDF内容"""
        path = Path(pdf_path)
        result = CrawlResult(
            document=Document(
                id=self._generate_id(str(path)),
                source_type=SourceType.PDF,
                source_path=str(path),
            )
        )

        try:
            doc = fitz.open(path)

            # 提取文本
            text_parts = []
            for page in doc:
                text_parts.append(page.get_text())

            content = "\n\n".join(text_parts)

            # 提取标题（从文件名或第一页文本）
            title = path.stem
            if text_parts:
                first_lines = text_parts[0].strip().split("\n")[:5]
                for line in first_lines:
                    line = line.strip()
                    if line and len(line) < 200:
                        title = line
                        break

            # 提取图片
            images = []
            if extract_images and image_dir:
                image_dir.mkdir(parents=True, exist_ok=True)
                images = self._extract_images(doc, image_dir)
                result.images_downloaded = len(images)

            result.document.title = title
            result.document.content = content
            result.document.format = DocFormat.PDF
            result.document.images = images
            result.document.metadata = {
                "file_path": str(path),
                "page_count": len(doc),
                "file_size": path.stat().st_size,
            }

            doc.close()

        except Exception as e:
            result.errors.append(str(e))

        return result

    def _extract_images(self, doc: fitz.Document, image_dir: Path) -> list[ImageInfo]:
        """从PDF提取图片"""
        images = []

        for page_num, page in enumerate(doc):
            image_list = page.get_images()

            for img_index, img in enumerate(image_list, start=1):
                xref = img[0]
                base_image = doc.extract_image(xref)
                image_bytes = base_image["image"]
                image_ext = base_image["ext"]

                # 生成文件名
                local_name = f"page{page_num + 1}_img{img_index}.{image_ext}"
                local_path = image_dir / local_name

                try:
                    local_path.write_bytes(image_bytes)
                    images.append(
                        ImageInfo(
                            local_path=local_path,
                            alt_text=f"Page {page_num + 1} Image {img_index}",
                        )
                    )
                except Exception:
                    pass

        return images


class Crawler:
    """统一爬虫接口"""

    def __init__(self):
        self.url_crawler = URLCrawler()
        self.file_crawler = LocalFileCrawler()
        self.pdf_crawler = PDFCrawler()

    def crawl_url(self, url: str, **kwargs) -> CrawlResult:
        """爬取URL"""
        return self.url_crawler.crawl(url, **kwargs)

    def crawl_local(self, path: Path | str, **kwargs) -> Iterator[CrawlResult]:
        """爬取本地文件"""
        return self.file_crawler.crawl(path, **kwargs)

    def crawl_folder(
        self, folder_path: Path | str, recursive: bool = True
    ) -> DocumentGraph:
        """
        爬取整个文件夹并构建文档关系图

        Args:
            folder_path: 文件夹路径
            recursive: 是否递归处理子文件夹

        Returns:
            DocumentGraph: 包含所有文档和链接关系的图
        """
        return self.file_crawler.crawl_folder(folder_path, recursive)

    def crawl_pdf(self, path: Path | str, **kwargs) -> CrawlResult:
        """爬取PDF"""
        return self.pdf_crawler.crawl(path, **kwargs)

    def crawl(self, source: str, **kwargs) -> CrawlResult | Iterator[CrawlResult]:
        """自动识别来源类型并爬取"""
        if source.startswith(("http://", "https://")):
            return self.crawl_url(source, **kwargs)

        path = Path(source)
        if path.suffix.lower() == ".pdf":
            return self.crawl_pdf(source, **kwargs)

        return self.crawl_local(source, **kwargs)
