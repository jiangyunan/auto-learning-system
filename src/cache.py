"""缓存模块 - SQLite后端"""

import sqlite3
import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Optional
from contextlib import contextmanager

from src.config import CacheConfig
from src.models import CacheEntry


class Cache:
    """SQLite缓存管理器"""

    def __init__(self, config: CacheConfig):
        self.config = config
        self.db_path = Path(config.db_path)
        if self.config.enabled:
            self._ensure_db()

    def _ensure_db(self):
        """确保数据库和表存在"""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._get_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS cache_entries (
                    content_hash TEXT PRIMARY KEY,
                    result_json TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    accessed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    access_count INTEGER DEFAULT 1
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_accessed_at
                ON cache_entries(accessed_at)
            """)
            conn.commit()

    @contextmanager
    def _get_connection(self):
        """获取数据库连接"""
        conn = sqlite3.connect(self.db_path)
        try:
            yield conn
        finally:
            conn.close()

    @staticmethod
    def compute_hash(content: str) -> str:
        """计算内容哈希"""
        return hashlib.sha256(content.encode("utf-8")).hexdigest()

    def get(self, content: str) -> Optional[dict]:
        """获取缓存结果"""
        if not self.config.enabled:
            return None

        content_hash = self.compute_hash(content)

        with self._get_connection() as conn:
            cursor = conn.execute(
                "SELECT result_json FROM cache_entries WHERE content_hash = ?",
                (content_hash,),
            )
            row = cursor.fetchone()

            if row:
                # 更新访问统计
                conn.execute(
                    """UPDATE cache_entries
                       SET accessed_at = CURRENT_TIMESTAMP,
                           access_count = access_count + 1
                       WHERE content_hash = ?""",
                    (content_hash,),
                )
                conn.commit()
                return json.loads(row[0])

        return None

    def set(self, content: str, result: dict) -> None:
        """设置缓存"""
        if not self.config.enabled:
            return

        content_hash = self.compute_hash(content)
        result_json = json.dumps(result, ensure_ascii=False)

        with self._get_connection() as conn:
            conn.execute(
                """INSERT OR REPLACE INTO cache_entries
                   (content_hash, result_json, created_at, accessed_at, access_count)
                   VALUES (?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, 1)""",
                (content_hash, result_json),
            )
            conn.commit()

    def delete(self, content: str) -> bool:
        """删除缓存条目"""
        if not self.config.enabled:
            return False

        content_hash = self.compute_hash(content)

        with self._get_connection() as conn:
            cursor = conn.execute(
                "DELETE FROM cache_entries WHERE content_hash = ?", (content_hash,)
            )
            conn.commit()
            return cursor.rowcount > 0

    def clear(self) -> int:
        """清空所有缓存，返回删除的条目数"""
        if not self.config.enabled:
            return 0

        with self._get_connection() as conn:
            cursor = conn.execute("DELETE FROM cache_entries")
            conn.commit()
            return cursor.rowcount

    def cleanup_old(self, max_age_days: int = 30) -> int:
        """清理超过指定天数的旧缓存"""
        if not self.config.enabled:
            return 0

        with self._get_connection() as conn:
            cursor = conn.execute(
                """DELETE FROM cache_entries
                   WHERE accessed_at < datetime('now', '-{} days')""".format(
                    max_age_days
                )
            )
            conn.commit()
            return cursor.rowcount

    def get_stats(self) -> dict:
        """获取缓存统计信息"""
        if not self.config.enabled:
            return {"enabled": False}

        with self._get_connection() as conn:
            cursor = conn.execute("""
                SELECT
                    COUNT(*) as total_entries,
                    SUM(access_count) as total_accesses,
                    AVG(access_count) as avg_accesses,
                    MAX(created_at) as newest_entry,
                    MIN(created_at) as oldest_entry
                FROM cache_entries
            """)
            row = cursor.fetchone()

            return {
                "enabled": True,
                "total_entries": row[0] or 0,
                "total_accesses": row[1] or 0,
                "avg_accesses": round(row[2], 2) if row[2] else 0,
                "newest_entry": row[3],
                "oldest_entry": row[4],
            }


def create_cache(config: CacheConfig) -> Cache:
    """工厂函数：创建缓存实例"""
    return Cache(config)
