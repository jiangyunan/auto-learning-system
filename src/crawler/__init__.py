"""爬虫模块 - 支持URL、本地文件和PDF"""
import hashlib
import re
from pathlib import Path
from typing import Iterator
from urllib.parse import urljoin, urlparse
from dataclasses import dataclass

import requests
import fitz  # PyMuPDF
from bs4 import BeautifulSoup

from src.models import Document, SourceType, DocFormat, ImageInfo


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

    def crawl(self, url: str, download_images: bool = False, image_dir: Path = None) -> CrawlResult:
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
                result.images_downloaded = len([img for img in images if img.local_path])

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

    def _download_images(self, soup: BeautifulSoup, base_url: str, image_dir: Path) -> list[ImageInfo]:
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
                response = requests.get(full_url, headers=self.headers, timeout=self.timeout)
                response.raise_for_status()
                local_path.write_bytes(response.content)

                images.append(ImageInfo(
                    original_url=full_url,
                    local_path=local_path,
                    alt_text=img.get("alt", ""),
                ))
            except Exception:
                # 下载失败但仍记录原URL
                images.append(ImageInfo(
                    original_url=full_url,
                    alt_text=img.get("alt", ""),
                ))

        return images


class LocalFileCrawler(BaseCrawler):
    """本地文件爬虫"""

    def crawl(self, file_path: Path | str, recursive: bool = False) -> Iterator[CrawlResult]:
        """爬取本地文件"""
        path = Path(file_path)

        if path.is_file():
            yield self._process_file(path)
        elif path.is_dir() and recursive:
            for file_path in path.rglob("*.md"):
                yield self._process_file(file_path)
        elif path.is_dir():
            for file_path in path.glob("*.md"):
                yield self._process_file(file_path)

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
            }

        except Exception as e:
            result.errors.append(str(e))

        return result

    def _extract_markdown_title(self, content: str) -> str:
        """从Markdown内容提取标题"""
        # 查找第一个 # 开头的行
        match = re.search(r'^#\s+(.+)$', content, re.MULTILINE)
        if match:
            return match.group(1).strip()
        return ""


class PDFCrawler(BaseCrawler):
    """PDF爬虫"""

    def crawl(self, pdf_path: Path | str, extract_images: bool = False, image_dir: Path = None) -> CrawlResult:
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
                    images.append(ImageInfo(
                        local_path=local_path,
                        alt_text=f"Page {page_num + 1} Image {img_index}",
                    ))
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
