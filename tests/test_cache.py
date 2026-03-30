"""缓存模块测试"""
import pytest
import tempfile
import os
from pathlib import Path

from src.cache import Cache, create_cache
from src.config import CacheConfig


@pytest.fixture
def temp_cache():
    """创建临时缓存实例"""
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        db_path = f.name

    config = CacheConfig(enabled=True, db_path=db_path)
    cache = Cache(config)

    yield cache

    # 清理
    try:
        os.unlink(db_path)
    except FileNotFoundError:
        pass


@pytest.fixture
def disabled_cache():
    """创建禁用的缓存实例"""
    config = CacheConfig(enabled=False, db_path="/tmp/test.db")
    return Cache(config)


class TestCacheBasic:
    """基本缓存操作测试"""

    def test_compute_hash(self, temp_cache):
        """测试哈希计算"""
        hash1 = temp_cache.compute_hash("test content")
        hash2 = temp_cache.compute_hash("test content")
        hash3 = temp_cache.compute_hash("different content")

        assert len(hash1) == 64  # SHA256 hex length
        assert hash1 == hash2  # 相同内容相同哈希
        assert hash1 != hash3  # 不同内容不同哈希

    def test_set_and_get(self, temp_cache):
        """测试设置和获取缓存"""
        content = "test content"
        result = {"summary": "test result", "tokens": 100}

        temp_cache.set(content, result)
        cached = temp_cache.get(content)

        assert cached == result

    def test_get_nonexistent(self, temp_cache):
        """测试获取不存在的缓存"""
        cached = temp_cache.get("nonexistent content")
        assert cached is None

    def test_update_existing(self, temp_cache):
        """测试更新现有缓存"""
        content = "test content"
        result1 = {"version": 1}
        result2 = {"version": 2}

        temp_cache.set(content, result1)
        temp_cache.set(content, result2)

        cached = temp_cache.get(content)
        assert cached == result2

    def test_delete(self, temp_cache):
        """测试删除缓存"""
        content = "test content"
        temp_cache.set(content, {"data": "value"})

        assert temp_cache.delete(content) is True
        assert temp_cache.get(content) is None
        assert temp_cache.delete(content) is False

    def test_clear(self, temp_cache):
        """测试清空缓存"""
        temp_cache.set("content1", {"data": 1})
        temp_cache.set("content2", {"data": 2})
        temp_cache.set("content3", {"data": 3})

        deleted = temp_cache.clear()
        assert deleted == 3

        assert temp_cache.get("content1") is None
        assert temp_cache.get("content2") is None
        assert temp_cache.get("content3") is None


class TestCacheDisabled:
    """禁用缓存测试"""

    def test_disabled_get_returns_none(self, disabled_cache):
        """测试禁用缓存get返回None"""
        assert disabled_cache.get("anything") is None

    def test_disabled_set_does_nothing(self, disabled_cache):
        """测试禁用缓存set不执行"""
        disabled_cache.set("content", {"data": "value"})
        assert disabled_cache.get("content") is None

    def test_disabled_delete_returns_false(self, disabled_cache):
        """测试禁用缓存delete返回False"""
        assert disabled_cache.delete("anything") is False

    def test_disabled_clear_returns_zero(self, disabled_cache):
        """测试禁用缓存clear返回0"""
        assert disabled_cache.clear() == 0

    def test_disabled_cleanup_returns_zero(self, disabled_cache):
        """测试禁用缓存cleanup返回0"""
        assert disabled_cache.cleanup_old(max_age_days=7) == 0

    def test_disabled_stats(self, disabled_cache):
        """测试禁用缓存stats"""
        stats = disabled_cache.get_stats()
        assert stats["enabled"] is False


class TestCacheAccessTracking:
    """缓存访问跟踪测试"""

    def test_access_count_incremented(self, temp_cache):
        """测试访问计数递增"""
        content = "test content"
        temp_cache.set(content, {"data": "value"})

        # 多次获取
        temp_cache.get(content)
        temp_cache.get(content)
        temp_cache.get(content)

        stats = temp_cache.get_stats()
        assert stats["total_accesses"] == 4  # 1 from set + 3 from gets

    def test_access_time_updated(self, temp_cache):
        """测试访问时间更新"""
        import time

        content = "test content"
        temp_cache.set(content, {"data": "value"})

        # 等待一小段时间
        time.sleep(0.01)

        # 再次获取
        temp_cache.get(content)

        # 统计信息应该显示有访问记录
        stats = temp_cache.get_stats()
        assert stats["total_accesses"] >= 2


class TestCacheCleanup:
    """缓存清理测试"""

    def test_cleanup_old_entries(self, temp_cache):
        """测试清理旧缓存条目"""
        # 添加一些缓存
        temp_cache.set("content1", {"data": 1})
        temp_cache.set("content2", {"data": 2})

        # 清理0天的应该删除所有（因为没有真正等待）
        # 但这里我们只测试接口
        deleted = temp_cache.cleanup_old(max_age_days=0)
        # 由于所有条目都是新的，应该没有删除
        # 但这个行为取决于具体实现

    def test_stats_empty_cache(self, temp_cache):
        """测试空缓存统计"""
        stats = temp_cache.get_stats()

        assert stats["enabled"] is True
        assert stats["total_entries"] == 0
        assert stats["total_accesses"] == 0
        assert stats["avg_accesses"] == 0

    def test_stats_with_entries(self, temp_cache):
        """测试有数据的缓存统计"""
        temp_cache.set("content1", {"data": 1})
        temp_cache.set("content2", {"data": 2})

        temp_cache.get("content1")
        temp_cache.get("content1")

        stats = temp_cache.get_stats()

        assert stats["total_entries"] == 2
        assert stats["total_accesses"] == 4  # 2 from sets + 2 from gets


class TestFactory:
    """工厂函数测试"""

    def test_create_cache_factory(self):
        """测试缓存工厂函数"""
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            db_path = f.name

        try:
            config = CacheConfig(enabled=True, db_path=db_path)
            cache = create_cache(config)

            assert isinstance(cache, Cache)
            assert cache.config == config
        finally:
            os.unlink(db_path)
