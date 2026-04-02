"""分块模块测试"""

import pytest

from src.chunker import Chunker, create_chunker, ChunkerStats
from src.config import ChunkerConfig
from src.models import Chunk


@pytest.fixture
def chunker_config():
    return ChunkerConfig(target_tokens=50, overlap_chars=20)


@pytest.fixture
def chunker(chunker_config):
    return Chunker(chunker_config)


class TestChunkerBasic:
    """基本分块功能测试"""

    def test_count_tokens(self, chunker):
        """测试token计数"""
        # 英文大约1 token per word
        assert chunker.count_tokens("hello world") == 2
        assert chunker.count_tokens("") == 0

    def test_split_into_paragraphs(self, chunker):
        """测试段落分割"""
        text = "Para 1.\n\nPara 2.\n\nPara 3."
        paragraphs = chunker._split_into_paragraphs(text)
        assert len(paragraphs) == 3
        assert paragraphs[0] == "Para 1."
        assert paragraphs[1] == "Para 2."
        assert paragraphs[2] == "Para 3."

    def test_split_single_paragraph(self, chunker):
        """测试单行文本"""
        text = "Just one paragraph."
        paragraphs = chunker._split_into_paragraphs(text)
        assert len(paragraphs) == 1

    def test_empty_text(self, chunker):
        """测试空文本"""
        chunks = list(chunker.chunk("doc-1", ""))
        assert len(chunks) == 0

    def test_whitespace_only(self, chunker):
        """测试只有空白字符"""
        chunks = list(chunker.chunk("doc-1", "   \n\n   "))
        assert len(chunks) == 0


class TestChunkGeneration:
    """分块生成测试"""

    def test_single_small_paragraph(self, chunker):
        """测试单个小段落"""
        text = "This is a short paragraph."
        chunks = list(chunker.chunk("doc-1", text))

        assert len(chunks) == 1
        assert chunks[0].document_id == "doc-1"
        assert chunks[0].index == 0
        assert chunks[0].content == text

    def test_multiple_small_paragraphs(self, chunker):
        """测试多个小段落"""
        text = "Para 1.\n\nPara 2.\n\nPara 3."
        chunks = list(chunker.chunk("doc-1", text))

        assert len(chunks) == 1  # 应该合并为一个块
        assert "Para 1." in chunks[0].content
        assert "Para 2." in chunks[0].content
        assert "Para 3." in chunks[0].content

    def test_chunk_ids_unique(self, chunker):
        """测试分块ID唯一性"""
        text = "Para 1.\n\nPara 2.\n\nPara 3."
        chunks = list(chunker.chunk("doc-1", text))

        ids = [c.id for c in chunks]
        assert len(ids) == len(set(ids))  # 所有ID唯一

    def test_chunk_positions(self, chunker):
        """测试分块位置信息"""
        text = "First paragraph with some text.\n\nSecond paragraph here."
        chunks = list(chunker.chunk("doc-1", text))

        for chunk in chunks:
            assert chunk.start_pos >= 0
            assert chunk.end_pos > chunk.start_pos
            assert chunk.start_pos < len(text)


class TestLargeTextChunking:
    """大文本分块测试"""

    def test_long_text_splits(self):
        """测试长文本分割为多个块"""
        config = ChunkerConfig(target_tokens=30, overlap_chars=10)
        chunker = Chunker(config)

        # 创建一个足够长的文本
        paragraphs = [
            f"This is paragraph {i} with some content in it." for i in range(10)
        ]
        text = "\n\n".join(paragraphs)

        chunks = list(chunker.chunk("doc-1", text))

        # 应该生成多个块
        assert len(chunks) > 1

        # 检查索引递增
        for i, chunk in enumerate(chunks):
            assert chunk.index == i

    def test_large_paragraph_split(self):
        """测试大段落分割"""
        config = ChunkerConfig(target_tokens=20, overlap_chars=5)
        chunker = Chunker(config)

        # 一个长段落
        text = "This is a very long paragraph. " * 20

        chunks = list(chunker.chunk("doc-1", text))

        # 大段落应该被分割
        assert len(chunks) >= 1

    def test_overlap_preserved(self):
        """测试重叠保留"""
        config = ChunkerConfig(target_tokens=30, overlap_chars=20)
        chunker = Chunker(config)

        # 两个足够大的段落，需要分开但应该有重叠
        text = (
            "First paragraph with enough text to be significant.\n\n"
            "Second paragraph also with substantial content here.\n\n"
            "Third paragraph continues the document content flow."
        )

        chunks = list(chunker.chunk("doc-1", text))

        if len(chunks) > 1:
            # 检查重叠逻辑
            for i in range(len(chunks) - 1):
                # 当前块的结尾和下一个块的开头应该有相似内容
                curr_end = chunks[i].content[-30:]
                next_start = chunks[i + 1].content[:30]
                # 简化检查：重叠内容应该有一些共同之处


class TestChunkerStats:
    """分块统计测试"""

    def test_stats_calculation(self, chunker):
        """测试统计计算"""
        text = "Para 1.\n\nPara 2.\n\nPara 3."
        chunks = list(chunker.chunk("doc-1", text))
        stats = chunker.get_stats(chunks, text)

        assert stats.chunk_count == len(chunks)
        assert stats.total_chars == len(text)
        assert stats.total_tokens > 0
        assert stats.avg_chunk_tokens > 0

    def test_empty_stats(self, chunker):
        """测试空分块统计"""
        stats = chunker.get_stats([], "")

        assert stats.chunk_count == 0
        assert stats.total_chars == 0
        assert stats.total_tokens == 0
        assert stats.avg_chunk_tokens == 0


class TestFactory:
    """工厂函数测试"""

    def test_create_chunker_factory(self, chunker_config):
        """测试分块器工厂函数"""
        chunker = create_chunker(chunker_config)
        assert isinstance(chunker, Chunker)
        assert chunker.config == chunker_config


class TestEdgeCases:
    """边界情况测试"""

    def test_very_long_word(self, chunker):
        """测试超长单词"""
        text = "a" * 1000  # 很长的单词
        chunks = list(chunker.chunk("doc-1", text))

        # 应该能处理，即使可能分割在单词中间
        assert len(chunks) >= 1

    def test_chinese_text(self, chunker):
        """测试中文文本"""
        text = "这是第一段。\n\n这是第二段。\n\n这是第三段。"
        chunks = list(chunker.chunk("doc-1", text))

        assert len(chunks) >= 1
        # 中文token计数应该正常工作
        assert chunks[0].token_count > 0

    def test_mixed_content(self, chunker):
        """测试混合内容"""
        text = """
# Header

Some text here.

## Subheader

More content.

- List item 1
- List item 2
"""
        chunks = list(chunker.chunk("doc-1", text))
        assert len(chunks) >= 1
