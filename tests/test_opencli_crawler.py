"""OpenCLI 爬虫测试"""

from src.models import SourceType
from src.crawler.opencli import OpenCLICrawler


def test_source_type_opencli_exists():
    """测试 SourceType 包含 OPENCLI"""
    assert SourceType.OPENCLI.value == "opencli"
    assert hasattr(SourceType, "OPENCLI")


def test_opencli_crawler_can_be_instantiated():
    """测试 OpenCLICrawler 可被实例化"""
    crawler = OpenCLICrawler()
    assert crawler is not None


def test_opencli_crawler_has_whitelist():
    """测试 OpenCLICrawler 有白名单配置"""
    crawler = OpenCLICrawler()
    assert hasattr(crawler, "whitelist")
    assert isinstance(crawler.whitelist, set)
    assert len(crawler.whitelist) > 0


def test_parse_url_xiaohongshu_note():
    """测试解析小红书笔记 URL"""
    crawler = OpenCLICrawler()
    result = crawler._parse_url("opencli://xiaohongshu/note/abc123")

    assert result["site"] == "xiaohongshu"
    assert result["command"] == "note"
    assert result["arg"] == "abc123"
    assert result["params"] == {}


def test_parse_url_zhihu_download():
    """测试解析知乎下载 URL"""
    crawler = OpenCLICrawler()
    result = crawler._parse_url("opencli://zhihu/download?url=https://example.com")

    assert result["site"] == "zhihu"
    assert result["command"] == "download"
    assert result["arg"] is None
    assert result["params"] == {"url": ["https://example.com"]}


def test_check_whitelist_allowed():
    """测试白名单允许通过的命令"""
    crawler = OpenCLICrawler()

    # 应该通过
    assert crawler._check_whitelist("xiaohongshu", "note", "abc123") is True
    assert crawler._check_whitelist("bilibili", "subtitle", "BV1xx") is True
    assert crawler._check_whitelist("zhihu", "download", None) is True


def test_check_whitelist_blocked():
    """测试白名单拒绝的命令"""
    crawler = OpenCLICrawler()

    # 应该拒绝
    assert crawler._check_whitelist("bilibili", "hot", None) is False
    assert crawler._check_whitelist("hackernews", "top", None) is False
    assert crawler._check_whitelist("zhihu", "search", None) is False
