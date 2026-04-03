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
