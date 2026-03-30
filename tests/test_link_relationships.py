"""测试文档链接关系解析"""
import pytest
from pathlib import Path
from src.models import Document, SourceType, DocFormat, Link, DocumentGraph
from src.crawler import LocalFileCrawler, WIKI_LINK_PATTERN, MARKDOWN_LINK_PATTERN


class TestLinkPatterns:
    """测试链接正则表达式"""

    def test_wiki_link_basic(self):
        """测试基本Wiki链接 [[Page]]"""
        content = "See [[Python]] for more info"
        matches = WIKI_LINK_PATTERN.findall(content)
        assert len(matches) == 1
        assert "Python" in matches[0]

    def test_wiki_link_with_alias(self):
        """测试带别名的Wiki链接 [[Page|Display]]"""
        content = "See [[Python|the Python language]] for more"
        matches = WIKI_LINK_PATTERN.findall(content)
        assert len(matches) == 1
        # 正则捕获整个内容，代码中会处理别名
        assert "Python" in matches[0]

    def test_wiki_link_multiple(self):
        """测试多个Wiki链接"""
        content = "[[A]] and [[B]] and [[C]]"
        matches = WIKI_LINK_PATTERN.findall(content)
        assert len(matches) == 3

    def test_markdown_link_basic(self):
        """测试基本Markdown链接 [text](path)"""
        content = "See [Python Guide](./python.md) for more"
        matches = MARKDOWN_LINK_PATTERN.findall(content)
        assert len(matches) == 1
        assert matches[0] == ("Python Guide", "./python.md")

    def test_markdown_link_exclude_image(self):
        """测试图片链接也被匹配（代码中会排除）"""
        content = "![alt](image.png) and [text](link.md)"
        matches = MARKDOWN_LINK_PATTERN.findall(content)
        # 正则匹配所有[]()，包括图片（2个）
        assert len(matches) == 2
        # 代码中通过检查前面是否有!来排除图片

    def test_markdown_link_external_url(self):
        """测试外部URL链接"""
        content = "[Google](https://google.com)"
        matches = MARKDOWN_LINK_PATTERN.findall(content)
        assert len(matches) == 1
        assert matches[0] == ("Google", "https://google.com")


class TestLocalFileCrawlerLinkExtraction:
    """测试本地文件爬虫的链接提取"""

    @pytest.fixture
    def crawler(self):
        return LocalFileCrawler()

    def test_extract_wiki_links(self, crawler):
        """测试提取Wiki链接"""
        content = """# Test Document

This is about [[Python]] and [[Async Programming]].
Also see [[Python]] again for details.
"""
        doc = Document(
            id="test-1",
            source_type=SourceType.LOCAL_FILE,
            source_path="/test/doc.md",
            content=content
        )

        links = crawler._extract_links(doc)
        wiki_links = [l for l in links if l.link_type == "wiki"]

        assert len(wiki_links) == 3
        assert wiki_links[0].target_path == "Python"
        assert wiki_links[1].target_path == "Async Programming"

    def test_extract_markdown_links(self, crawler, tmp_path):
        """测试提取Markdown链接"""
        content = """# Test Document

See [Guide](./guide.md) for basics.
Advanced topics in [Advanced](./advanced.md).
External link [Google](https://google.com) should be ignored.
Anchor link [Section](#section) should be ignored.
"""
        doc = Document(
            id="test-1",
            source_type=SourceType.LOCAL_FILE,
            source_path=str(tmp_path / "doc.md"),
            content=content
        )

        links = crawler._extract_links(doc)
        md_links = [l for l in links if l.link_type == "markdown"]

        assert len(md_links) == 2
        assert "guide.md" in md_links[0].target_path
        assert "advanced.md" in md_links[1].target_path

    def test_extract_mixed_links(self, crawler, tmp_path):
        """测试混合链接类型"""
        content = """# Main Document

Both [[Wiki Link]] and [MD Link](./other.md) work.
Also [[Another|With Alias]] here.
"""
        doc = Document(
            id="test-1",
            source_type=SourceType.LOCAL_FILE,
            source_path=str(tmp_path / "doc.md"),
            content=content
        )

        links = crawler._extract_links(doc)

        wiki_links = [l for l in links if l.link_type == "wiki"]
        md_links = [l for l in links if l.link_type == "markdown"]

        assert len(wiki_links) == 2
        assert len(md_links) == 1


class TestDocumentGraph:
    """测试文档关系图"""

    @pytest.fixture
    def sample_graph(self):
        """创建示例图"""
        graph = DocumentGraph(root_path=Path("/vault"))

        # 创建文档
        doc_a = Document(
            id="doc-a",
            source_type=SourceType.LOCAL_FILE,
            source_path="/vault/python.md",
            title="Python"
        )
        doc_b = Document(
            id="doc-b",
            source_type=SourceType.LOCAL_FILE,
            source_path="/vault/async.md",
            title="Async Programming"
        )
        doc_c = Document(
            id="doc-c",
            source_type=SourceType.LOCAL_FILE,
            source_path="/vault/guide.md",
            title="Guide"
        )

        graph.add_document(doc_a)
        graph.add_document(doc_b)
        graph.add_document(doc_c)

        # B和C都链接到A（A被引用最多，应该优先处理）
        graph.add_link(Link(source_doc_id="doc-b", target_path="python.md", link_text="Python", link_type="markdown"))
        graph.add_link(Link(source_doc_id="doc-c", target_path="python.md", link_text="Python", link_type="wiki"))
        # C还链接到B
        graph.add_link(Link(source_doc_id="doc-c", target_path="async.md", link_text="Async", link_type="wiki"))

        return graph

    def test_add_document(self, sample_graph):
        """测试添加文档"""
        assert len(sample_graph.documents) == 3
        assert "doc-a" in sample_graph.documents

    def test_add_link(self, sample_graph):
        """测试添加链接"""
        assert len(sample_graph.links) == 3

    def test_incoming_links(self, sample_graph):
        """测试入链统计"""
        # doc-a 被引用2次
        assert len(sample_graph.incoming_links["doc-a"]) == 2
        # doc-b 被引用1次
        assert len(sample_graph.incoming_links["doc-b"]) == 1
        # doc-c 没有被引用
        assert len(sample_graph.incoming_links["doc-c"]) == 0

    def test_outgoing_links(self, sample_graph):
        """测试出链统计"""
        # doc-a 没有出链
        assert len(sample_graph.outgoing_links["doc-a"]) == 0
        # doc-b 有1个出链
        assert len(sample_graph.outgoing_links["doc-b"]) == 1
        # doc-c 有2个出链
        assert len(sample_graph.outgoing_links["doc-c"]) == 2

    def test_processing_order(self, sample_graph):
        """测试处理顺序（被引用最多的优先）"""
        order = sample_graph.get_processing_order()

        # doc-a 被引用最多(2次)，应该排第一
        assert order[0] == "doc-a"
        # doc-b 被引用1次，排第二
        assert order[1] == "doc-b"
        # doc-c 没有被引用但有出链，排最后
        assert order[2] == "doc-c"

    def test_get_related_documents(self, sample_graph):
        """测试获取相关文档"""
        # doc-c 的相关文档是 doc-a 和 doc-b
        related = sample_graph.get_related_documents("doc-c")
        assert "doc-a" in related
        assert "doc-b" in related
        assert len(related) == 2

        # doc-a 的相关文档是 doc-b 和 doc-c（引用它的）
        related_a = sample_graph.get_related_documents("doc-a")
        assert "doc-b" in related_a
        assert "doc-c" in related_a

    def test_get_statistics(self, sample_graph):
        """测试统计信息"""
        stats = sample_graph.get_statistics()

        assert stats["total_documents"] == 3
        assert stats["total_links"] == 3
        assert stats["wiki_links"] == 2
        assert stats["markdown_links"] == 1
        assert stats["broken_links"] == 0

    def test_resolve_target_by_stem(self, sample_graph):
        """测试通过文件名（不含扩展名）解析目标"""
        # 添加一个使用不带扩展名的Wiki链接的文档
        link = Link(
            source_doc_id="doc-c",
            target_path="python",  # 不带.md
            link_text="Python",
            link_type="wiki"
        )
        target = sample_graph._resolve_target("python")
        assert target is not None
        assert target.id == "doc-a"


class TestFolderCrawling:
    """测试文件夹爬取"""

    @pytest.fixture
    def sample_vault(self, tmp_path):
        """创建示例Obsidian Vault结构"""
        # 创建文件
        (tmp_path / "Python.md").write_text("""# Python

Python is a programming language.
See [[Async]] for async programming.
""")
        (tmp_path / "Async.md").write_text("""# Async Programming

About async/await in [[Python]].
Also see [Guide](./Guide.md).
""")
        (tmp_path / "Guide.md").write_text("""# Guide

Learning guide for [[Python]] and [[Async]].
""")
        # 孤立文件
        (tmp_path / "Standalone.md").write_text("""# Standalone

No links here.
""")
        return tmp_path

    def test_crawl_folder_builds_graph(self, sample_vault):
        """测试爬取文件夹构建关系图"""
        crawler = LocalFileCrawler()
        graph = crawler.crawl_folder(sample_vault)

        assert len(graph.documents) == 4
        assert graph.get_statistics()["total_links"] == 5

    def test_crawl_folder_processing_order(self, sample_vault):
        """测试文件夹爬取的处理顺序"""
        crawler = LocalFileCrawler()
        graph = crawler.crawl_folder(sample_vault)

        order = graph.get_processing_order()

        # Python被引用最多，应该排第一
        first_doc = graph.documents[order[0]]
        assert first_doc.title == "Python"

    def test_crawl_with_recursive(self, tmp_path):
        """测试递归爬取子文件夹"""
        # 创建子文件夹
        subdir = tmp_path / "subdir"
        subdir.mkdir()
        (subdir / "Subdoc.md").write_text("# Subdoc\n\nLink to [[Main]].")
        (tmp_path / "Main.md").write_text("# Main\n\nMain document.")

        crawler = LocalFileCrawler()
        graph = crawler.crawl_folder(tmp_path, recursive=True)

        assert len(graph.documents) == 2

    def test_crawl_without_recursive(self, tmp_path):
        """测试非递归爬取"""
        subdir = tmp_path / "subdir"
        subdir.mkdir()
        (subdir / "Subdoc.md").write_text("# Subdoc")
        (tmp_path / "Main.md").write_text("# Main")

        crawler = LocalFileCrawler()
        graph = crawler.crawl_folder(tmp_path, recursive=False)

        assert len(graph.documents) == 1
        assert "Main" in [d.title for d in graph.documents.values()]


class TestBrokenLinks:
    """测试断链检测"""

    def test_detect_broken_links(self, tmp_path):
        """测试检测指向不存在的文件的链接"""
        (tmp_path / "Valid.md").write_text("# Valid\n\nValid doc.")
        (tmp_path / "Broken.md").write_text("# Broken\n\nLink to [[NonExistent]].")

        crawler = LocalFileCrawler()
        graph = crawler.crawl_folder(tmp_path)

        stats = graph.get_statistics()
        assert stats["broken_links"] == 1
