"""爬虫模块测试"""

import pytest
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

from src.crawler import URLCrawler, LocalFileCrawler, PDFCrawler, Crawler, CrawlResult
from src.models import SourceType, DocFormat


class TestURLCrawler:
    """URL爬虫测试"""

    @pytest.fixture
    def url_crawler(self):
        return URLCrawler()

    @patch("src.crawler.requests.get")
    def test_crawl_basic(self, mock_get, url_crawler):
        """测试基本URL爬取"""
        mock_response = Mock()
        mock_response.text = """
        <html>
            <head><title>Test Page</title></head>
            <body>
                <article>
                    <h1>Article Title</h1>
                    <p>This is the content.</p>
                </article>
            </body>
        </html>
        """
        mock_response.status_code = 200
        mock_response.headers = {"Content-Type": "text/html"}
        mock_response.apparent_encoding = "utf-8"
        mock_get.return_value = mock_response

        result = url_crawler.crawl("https://example.com/article")

        assert result.document.source_type == SourceType.URL
        assert result.document.source_path == "https://example.com/article"
        assert result.document.title == "Article Title"
        assert "This is the content" in result.document.content
        assert result.document.format == DocFormat.HTML

    @patch("src.crawler.requests.get")
    def test_crawl_no_article(self, mock_get, url_crawler):
        """测试无article标签的页面"""
        mock_response = Mock()
        mock_response.text = """
        <html>
            <body>
                <div class="content">
                    <h1>Page Title</h1>
                    <p>Content here.</p>
                </div>
            </body>
        </html>
        """
        mock_response.status_code = 200
        mock_response.headers = {}
        mock_response.apparent_encoding = "utf-8"
        mock_get.return_value = mock_response

        result = url_crawler.crawl("https://example.com/page")

        assert "Content here" in result.document.content

    @patch("src.crawler.requests.get")
    def test_crawl_error(self, mock_get, url_crawler):
        """测试请求错误处理"""
        mock_get.side_effect = Exception("Connection error")

        result = url_crawler.crawl("https://example.com/error")

        assert len(result.errors) > 0
        assert "Connection error" in result.errors[0]

    def test_discover_links(self, url_crawler):
        """测试从页面发现链接"""
        from bs4 import BeautifulSoup

        html = """
        <html>
            <body>
                <a href="/page1">Page 1</a>
                <a href="/page2">Page 2</a>
                <a href="https://other.com/page">External</a>
                <a href="mailto:test@example.com">Email</a>
                <a href="javascript:void(0)">JS Link</a>
            </body>
        </html>
        """
        soup = BeautifulSoup(html, "html.parser")
        links = url_crawler.discover_links(soup, "https://example.com/")

        # URL被归一化：无扩展名的路径会统一加尾部斜杠
        assert "https://example.com/page1/" in links
        assert "https://example.com/page2/" in links
        assert "https://other.com/page/" in links
        assert len(links) == 3  # 排除 mailto 和 javascript

    def test_match_pattern(self, url_crawler):
        """测试URL模式匹配"""
        # 无模式 - 匹配所有
        assert url_crawler.match_pattern("https://example.com/page", None) == True
        assert url_crawler.match_pattern("https://example.com/page", []) == True

        # glob 模式
        assert (
            url_crawler.match_pattern("https://example.com/docs/page.md", ["*.md"])
            == True
        )
        assert (
            url_crawler.match_pattern("https://example.com/docs/page.txt", ["*.md"])
            == False
        )
        assert (
            url_crawler.match_pattern("https://example.com/docs/page", ["*/docs/*"])
            == True
        )
        assert (
            url_crawler.match_pattern("https://example.com/api/page", ["*/docs/*"])
            == False
        )

    def test_merge_documents(self, url_crawler):
        """测试文档合并"""
        from src.models import Document

        docs = [
            Document(
                id="1",
                source_type=SourceType.URL,
                source_path="https://example.com/1",
                title="Page 1",
                content="Content 1",
            ),
            Document(
                id="2",
                source_type=SourceType.URL,
                source_path="https://example.com/2",
                title="Page 2",
                content="Content 2",
            ),
        ]

        merged = url_crawler.merge_documents(docs, "https://example.com")

        assert merged.title == "Page 1 (2 页)"
        assert "Page 1" in merged.content
        assert "Page 2" in merged.content
        assert "Content 1" in merged.content
        assert "Content 2" in merged.content
        assert merged.metadata["merged_count"] == 2


class TestLocalFileCrawler:
    """本地文件爬虫测试"""

    @pytest.fixture
    def file_crawler(self):
        return LocalFileCrawler()

    def test_crawl_single_file(self, file_crawler, tmp_path):
        """测试单文件爬取"""
        test_file = tmp_path / "test.md"
        test_file.write_text("# Test Title\n\nThis is content.")

        results = list(file_crawler.crawl(test_file))

        assert len(results) == 1
        assert results[0].document.source_type == SourceType.LOCAL_FILE
        assert results[0].document.title == "Test Title"
        assert results[0].document.content == "# Test Title\n\nThis is content."
        assert results[0].document.format == DocFormat.MARKDOWN

    def test_crawl_directory(self, file_crawler, tmp_path):
        """测试目录爬取"""
        # 创建多个markdown文件
        (tmp_path / "file1.md").write_text("# File 1")
        (tmp_path / "file2.md").write_text("# File 2")
        (tmp_path / "other.txt").write_text("Not markdown")

        results = list(file_crawler.crawl(tmp_path))

        assert len(results) == 2  # 只包含.md文件
        titles = [r.document.title for r in results]
        assert "File 1" in titles
        assert "File 2" in titles

    def test_crawl_recursive(self, file_crawler, tmp_path):
        """测试递归爬取"""
        (tmp_path / "root.md").write_text("# Root")
        subdir = tmp_path / "subdir"
        subdir.mkdir()
        (subdir / "nested.md").write_text("# Nested")

        results = list(file_crawler.crawl(tmp_path, recursive=True))

        assert len(results) == 2
        titles = [r.document.title for r in results]
        assert "Root" in titles
        assert "Nested" in titles

    def test_extract_markdown_title(self, file_crawler):
        """测试Markdown标题提取"""
        content = "# Title\n\nSome content"
        assert file_crawler._extract_markdown_title(content) == "Title"

        content = "No title here"
        assert file_crawler._extract_markdown_title(content) == ""


class TestPDFCrawler:
    """PDF爬虫测试"""

    @pytest.fixture
    def pdf_crawler(self):
        return PDFCrawler()

    @patch("src.crawler.fitz.open")
    def test_crawl_pdf(self, mock_fitz_open, pdf_crawler, tmp_path):
        """测试PDF爬取"""
        # 模拟PDF文档
        mock_doc = Mock()
        mock_doc.__len__ = Mock(return_value=3)

        mock_page = Mock()
        mock_page.get_text.return_value = "Page content here"
        mock_doc.__iter__ = Mock(return_value=iter([mock_page, mock_page, mock_page]))

        mock_doc.get_images.return_value = []
        mock_fitz_open.return_value = mock_doc

        pdf_file = tmp_path / "test.pdf"
        pdf_file.touch()

        with patch.object(Path, "stat"):
            result = pdf_crawler.crawl(pdf_file)

        assert result.document.source_type == SourceType.PDF
        assert result.document.format == DocFormat.PDF
        assert "Page content" in result.document.content
        mock_doc.close.assert_called_once()

    @patch("src.crawler.fitz.open")
    def test_crawl_pdf_error(self, mock_fitz_open, pdf_crawler, tmp_path):
        """测试PDF错误处理"""
        mock_fitz_open.side_effect = Exception("PDF read error")

        pdf_file = tmp_path / "test.pdf"
        pdf_file.touch()

        result = pdf_crawler.crawl(pdf_file)

        assert len(result.errors) > 0
        assert "PDF read error" in result.errors[0]


class TestCrawler:
    """统一爬虫接口测试"""

    @pytest.fixture
    def crawler(self):
        return Crawler()

    @patch("src.crawler.URLCrawler.crawl")
    def test_crawl_url(self, mock_crawl, crawler):
        """测试URL自动识别"""
        mock_crawl.return_value = Mock(document=Mock())

        crawler.crawl("https://example.com")

        mock_crawl.assert_called_once()

    @patch("src.crawler.LocalFileCrawler.crawl")
    def test_crawl_local(self, mock_crawl, crawler):
        """测试本地文件自动识别"""
        mock_crawl.return_value = iter([Mock(document=Mock())])

        with tempfile.TemporaryDirectory() as tmpdir:
            list(crawler.crawl(tmpdir))

        mock_crawl.assert_called_once()

    @patch("src.crawler.PDFCrawler.crawl")
    def test_crawl_pdf(self, mock_crawl, crawler):
        """测试PDF自动识别"""
        mock_crawl.return_value = Mock(document=Mock())

        with tempfile.TemporaryDirectory() as tmpdir:
            pdf_path = Path(tmpdir) / "test.pdf"
            pdf_path.touch()
            crawler.crawl(str(pdf_path))

        mock_crawl.assert_called_once()


class TestCrawlResult:
    """爬取结果测试"""

    def test_result_creation(self):
        """测试结果对象创建"""
        doc = Mock()
        result = CrawlResult(document=doc, images_downloaded=5)

        assert result.document == doc
        assert result.images_downloaded == 5
        assert result.errors == []

    def test_result_with_errors(self):
        """测试带错误的结果"""
        result = CrawlResult(document=Mock(), errors=["Error 1", "Error 2"])

        assert len(result.errors) == 2
        assert "Error 1" in result.errors
