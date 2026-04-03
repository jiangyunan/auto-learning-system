"""OpenCLI 爬虫测试"""

from src.models import SourceType


def test_source_type_opencli_exists():
    """测试 SourceType 包含 OPENCLI"""
    assert SourceType.OPENCLI.value == "opencli"
    assert hasattr(SourceType, "OPENCLI")
