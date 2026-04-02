"""摘要生成模块测试"""

import pytest
from unittest.mock import Mock, AsyncMock

from src.summarizer import Summarizer, SummaryResult
from src.models import Chunk, SummaryL1, SummaryL2
from src.config import FeaturesConfig


@pytest.fixture
def mock_llm():
    """模拟LLM客户端"""
    return Mock()


@pytest.fixture
def mock_cache():
    """模拟缓存"""
    cache = Mock()
    cache.get = Mock(return_value=None)
    cache.set = Mock()
    return cache


@pytest.fixture
def features_enabled():
    return FeaturesConfig(chinese_notes=True)


@pytest.fixture
def features_disabled():
    return FeaturesConfig(chinese_notes=False)


@pytest.fixture
def sample_chunk():
    return Chunk(
        id="chunk-1",
        document_id="doc-1",
        index=0,
        content="This is a test chunk about Python programming.",
        token_count=10,
    )


class TestSummarizerL1:
    """L1摘要生成测试"""

    @pytest.mark.asyncio
    async def test_generate_l1_basic(
        self, mock_llm, mock_cache, features_enabled, sample_chunk
    ):
        """测试基本的L1生成"""
        mock_llm.complete_json = AsyncMock(
            return_value={
                "bullets": ["Point 1", "Point 2"],
                "key_concepts": ["Python", "Programming"],
            }
        )

        summarizer = Summarizer(mock_llm, mock_cache, features_enabled)
        result = await summarizer.summarize_chunk(sample_chunk)

        assert result.l1.bullets == ["Point 1", "Point 2"]
        assert result.l1.key_concepts == ["Python", "Programming"]
        assert result.from_cache is False

    @pytest.mark.asyncio
    async def test_generate_l1_empty_response(
        self, mock_llm, mock_cache, features_enabled, sample_chunk
    ):
        """测试L1空响应处理"""
        mock_llm.complete_json = AsyncMock(return_value={})

        summarizer = Summarizer(mock_llm, mock_cache, features_enabled)
        result = await summarizer.summarize_chunk(sample_chunk)

        assert result.l1.bullets == []
        assert result.l1.key_concepts == []

    @pytest.mark.asyncio
    async def test_generate_l1_error_handling(
        self, mock_llm, mock_cache, features_enabled, sample_chunk
    ):
        """测试L1错误处理"""
        mock_llm.complete_json = AsyncMock(side_effect=Exception("LLM error"))

        summarizer = Summarizer(mock_llm, mock_cache, features_enabled)
        result = await summarizer.summarize_chunk(sample_chunk)

        # 应该有降级处理
        assert len(result.l1.bullets) >= 1


class TestSummarizerL2:
    """L2摘要生成测试"""

    @pytest.mark.asyncio
    async def test_generate_l2_when_enabled(
        self, mock_llm, mock_cache, features_enabled, sample_chunk
    ):
        """测试启用中文笔记时生成L2"""
        mock_llm.complete_json = AsyncMock(
            side_effect=[
                {"bullets": ["Point 1"], "key_concepts": ["Concept"]},  # L1 response
                {  # L2 response
                    "overview": "概述",
                    "key_points": ["要点1"],
                    "concepts_explained": [{"term": "term", "explanation": "解释"}],
                    "code_examples": [],
                    "related_topics": [],
                },
            ]
        )

        summarizer = Summarizer(mock_llm, mock_cache, features_enabled)
        result = await summarizer.summarize_chunk(sample_chunk)

        assert result.l2.overview == "概述"
        assert result.l2.key_points == ["要点1"]

    @pytest.mark.asyncio
    async def test_skip_l2_when_disabled(
        self, mock_llm, mock_cache, features_disabled, sample_chunk
    ):
        """测试禁用时跳过L2"""
        mock_llm.complete_json = AsyncMock(
            return_value={
                "bullets": ["Point 1"],
                "key_concepts": [],
            }
        )

        summarizer = Summarizer(mock_llm, mock_cache, features_disabled)
        result = await summarizer.summarize_chunk(sample_chunk)

        # 只调用一次complete_json（只生成L1）
        assert mock_llm.complete_json.call_count == 1
        assert result.l2.overview == ""

    @pytest.mark.asyncio
    async def test_l2_error_handling(
        self, mock_llm, mock_cache, features_enabled, sample_chunk
    ):
        """测试L2错误处理"""
        mock_llm.complete_json = AsyncMock(
            side_effect=[
                {"bullets": ["Point 1"], "key_concepts": []},  # L1 success
                Exception("L2 error"),  # L2 failure
            ]
        )

        summarizer = Summarizer(mock_llm, mock_cache, features_enabled)
        result = await summarizer.summarize_chunk(sample_chunk)

        # L2应该有降级处理
        assert result.l2.key_points == ["Point 1"]  # 使用L1的bullets


class TestSummarizerCache:
    """缓存相关测试"""

    @pytest.mark.asyncio
    async def test_cache_hit(
        self, mock_llm, mock_cache, features_enabled, sample_chunk
    ):
        """测试缓存命中"""
        mock_cache.get = Mock(
            return_value={
                "l1": {"bullets": ["Cached point"], "key_concepts": ["Cached"]},
                "l2": {
                    "overview": "Cached overview",
                    "key_points": [],
                    "concepts_explained": [],
                    "code_examples": [],
                    "related_topics": [],
                },
            }
        )

        summarizer = Summarizer(mock_llm, mock_cache, features_enabled)
        result = await summarizer.summarize_chunk(sample_chunk)

        assert result.from_cache is True
        assert result.l1.bullets == ["Cached point"]
        assert result.l2.overview == "Cached overview"
        mock_llm.complete_json.assert_not_called()

    @pytest.mark.asyncio
    async def test_cache_miss_saves(
        self, mock_llm, mock_cache, features_enabled, sample_chunk
    ):
        """测试缓存未命中时保存"""
        mock_llm.complete_json = AsyncMock(
            return_value={
                "bullets": ["Point 1"],
                "key_concepts": [],
            }
        )

        summarizer = Summarizer(mock_llm, mock_cache, features_enabled)
        await summarizer.summarize_chunk(sample_chunk)

        mock_cache.set.assert_called_once()
        cache_key = mock_cache.set.call_args[0][0]
        assert "chunk:" in cache_key


class TestMergeSummaries:
    """摘要合并测试"""

    @pytest.mark.asyncio
    async def test_merge_l1_summaries(self, mock_llm, mock_cache, features_enabled):
        """测试L1摘要合并"""
        summaries = [
            SummaryL1(bullets=["A", "B"], key_concepts=["X", "Y"]),
            SummaryL1(bullets=["B", "C"], key_concepts=["Y", "Z"]),
        ]

        summarizer = Summarizer(mock_llm, mock_cache, features_enabled)
        merged = await summarizer.merge_l1_summaries(summaries)

        # 应该去重并合并
        assert "A" in merged.bullets
        assert "B" in merged.bullets
        assert "C" in merged.bullets
        assert "X" in merged.key_concepts
        assert "Y" in merged.key_concepts
        assert "Z" in merged.key_concepts

    @pytest.mark.asyncio
    async def test_merge_l1_empty(self, mock_llm, mock_cache, features_enabled):
        """测试合并空L1列表"""
        summarizer = Summarizer(mock_llm, mock_cache, features_enabled)
        merged = await summarizer.merge_l1_summaries([])

        assert merged.bullets == []
        assert merged.key_concepts == []

    @pytest.mark.asyncio
    async def test_merge_l2_summaries(self, mock_llm, mock_cache, features_enabled):
        """测试L2摘要合并"""
        summaries = [
            SummaryL2(
                overview="Overview 1",
                key_points=["A"],
                concepts_explained=[{"term": "T1"}],
            ),
            SummaryL2(
                overview="Overview 2",
                key_points=["B"],
                concepts_explained=[{"term": "T2"}],
            ),
        ]

        summarizer = Summarizer(mock_llm, mock_cache, features_enabled)
        merged = await summarizer.merge_l2_summaries(summaries)

        assert merged.overview == "Overview 1"  # 使用第一个
        assert "A" in merged.key_points
        assert "B" in merged.key_points
        assert len(merged.concepts_explained) == 2

    @pytest.mark.asyncio
    async def test_merge_l2_empty(self, mock_llm, mock_cache, features_enabled):
        """测试合并空L2列表"""
        summarizer = Summarizer(mock_llm, mock_cache, features_enabled)
        merged = await summarizer.merge_l2_summaries([])

        assert merged.overview == ""
        assert merged.key_points == []
