"""Crawl4AI 爬虫模块 - 基于浏览器的异步内容爬取"""

from __future__ import annotations

import fnmatch
import logging
from typing import TYPE_CHECKING
from urllib.parse import urljoin, urlparse, urlunparse

from src.models import Document, DocFormat, SourceType

if TYPE_CHECKING:
    from src.crawler import CrawlResult

try:
    from crawl4ai import AsyncWebCrawler
except ImportError:
    AsyncWebCrawler = None  # type: ignore[misc,assignment]

logger = logging.getLogger(__name__)


class Crawl4AICrawler:
    """基于 Crawl4AI 的异步网页爬虫"""

    @staticmethod
    def _generate_id(source: str) -> str:
        """生成文档ID"""
        import hashlib

        return hashlib.sha256(source.encode()).hexdigest()[:16]

    @staticmethod
    def _normalize_url(url: str) -> str:
        """归一化URL：去除锚点，统一尾部斜杠"""
        parsed = urlparse(url)
        path = parsed.path
        # 如果路径没有文件扩展名（非 .html/.pdf 等），统一加尾部斜杠
        if path and not path.endswith("/") and "." not in path.rsplit("/", 1)[-1]:
            path = path + "/"
        return urlunparse(
            (parsed.scheme, parsed.netloc, path, parsed.params, parsed.query, "")
        )

    async def _acrawl_internal(self, url: str) -> tuple["CrawlResult", list[str]]:
        """内部方法：爬取单个URL并返回结果及内部链接列表"""
        from src.crawler import CrawlResult

        result = CrawlResult(
            document=Document(
                id=self._generate_id(url),
                source_type=SourceType.URL,
                source_path=url,
            )
        )
        internal_links: list[str] = []

        if AsyncWebCrawler is None:
            result.errors.append("crawl4ai is not installed. Run: uv pip install crawl4ai")
            return result, internal_links

        try:
            async with AsyncWebCrawler() as crawler:
                c4a_result = await crawler.arun(url=url)

                if not c4a_result.success:
                    result.errors.append(
                        c4a_result.error_message or "Crawl4AI crawl failed"
                    )
                    return result, internal_links

                title = ""
                if c4a_result.metadata:
                    title = c4a_result.metadata.get("title", "")

                content = ""
                if c4a_result.markdown:
                    content = str(c4a_result.markdown)

                result.document.title = title
                result.document.content = content
                result.document.format = DocFormat.MARKDOWN
                result.document.metadata = {
                    "url": url,
                    "crawler": "crawl4ai",
                }

                # 提取内部链接
                if hasattr(c4a_result, "links") and c4a_result.links:
                    raw_links = c4a_result.links.get("internal", [])
                    for link in raw_links:
                        href = getattr(link, "href", None) or str(link)
                        if href:
                            full_url = urljoin(url, href)
                            normalized = self._normalize_url(full_url)
                            if normalized not in internal_links:
                                internal_links.append(normalized)

                result.links_found = len(internal_links)

        except Exception as e:
            logger.warning(f"Crawl4AI crawl failed for {url}: {e}")
            result.errors.append(str(e))

        return result, internal_links

    async def acrawl(self, url: str) -> "CrawlResult":
        """异步爬取单个URL"""
        result, _ = await self._acrawl_internal(url)
        return result

    async def acrawl_recursive(
        self,
        url: str,
        patterns: list[str] | None = None,
        max_depth: int = 3,
    ) -> "CrawlResult":
        """递归爬取URL及匹配的子页面"""
        from src.crawler import CrawlResult, URLCrawler

        url = self._normalize_url(url)

        result = CrawlResult(
            document=Document(
                id=self._generate_id(url),
                source_type=SourceType.URL,
                source_path=url,
            ),
            pages_crawled=0,
        )

        visited: set[str] = set()
        documents: list[Document] = []

        async def _crawl_page(current_url: str, depth: int) -> None:
            nonlocal result

            current_url = self._normalize_url(current_url)
            if current_url in visited or depth > max_depth:
                return

            visited.add(current_url)

            page_result, child_links = await self._acrawl_internal(current_url)
            result.pages_crawled += 1

            if page_result.errors:
                result.errors.extend(page_result.errors)

            doc = page_result.document
            if not doc.content:
                return

            documents.append(doc)

            # 发现子链接并递归
            if depth < max_depth:
                result.links_found += len(child_links)

                matched = [
                    u for u in child_links if self._match_pattern(u, patterns) and u not in visited
                ]
                result.links_matched += len(matched)

                for child_url in matched:
                    await _crawl_page(child_url, depth + 1)

        try:
            await _crawl_page(url, 0)

            if not documents:
                result.errors.append(f"No content fetched from {url}")
                return result

            merged_doc = URLCrawler().merge_documents(documents, url)
            result.document = merged_doc
        except Exception as e:
            logger.warning(f"Crawl4AI recursive crawl failed for {url}: {e}")
            result.errors.append(str(e))

        return result

    def _match_pattern(self, url: str, patterns: list[str] | None) -> bool:
        """判断URL是否匹配任一模式"""
        if not patterns:
            return True
        for pattern in patterns:
            if fnmatch.fnmatch(url, pattern):
                return True
        return False
