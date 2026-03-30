"""分块模块 - 智能文本分块"""
import re
import hashlib
from typing import Iterator
from dataclasses import dataclass

import tiktoken

from src.config import ChunkerConfig
from src.models import Chunk


@dataclass
class ChunkerStats:
    """分块统计"""
    total_chars: int
    total_tokens: int
    chunk_count: int
    avg_chunk_tokens: float


class Chunker:
    """智能文本分块器"""

    def __init__(self, config: ChunkerConfig):
        self.config = config
        self.encoding = tiktoken.get_encoding("cl100k_base")

    def count_tokens(self, text: str) -> int:
        """计算文本的token数"""
        return len(self.encoding.encode(text))

    def _split_into_paragraphs(self, text: str) -> list[str]:
        """将文本分割为段落"""
        # 按空行分割段落
        paragraphs = re.split(r'\n\s*\n', text.strip())
        return [p.strip() for p in paragraphs if p.strip()]

    def _find_boundary(self, text: str, target_pos: int) -> int:
        """在目标位置附近找到合适的分割边界（句子结束或段落结束）"""
        if target_pos >= len(text):
            return len(text)

        # 优先寻找段落边界
        paragraph_match = re.search(r'\n\s*\n', text[target_pos:target_pos + 200])
        if paragraph_match:
            return target_pos + paragraph_match.start()

        # 其次寻找句子结束
        sentence_match = re.search(r'[.!?。！？]\s+', text[target_pos:target_pos + 100])
        if sentence_match:
            return target_pos + sentence_match.end()

        # 退回到空格位置
        space_match = re.search(r'\s', text[target_pos:target_pos + 50])
        if space_match:
            return target_pos + space_match.start()

        return target_pos

    def _generate_chunk_id(self, document_id: str, index: int, content: str) -> str:
        """生成分块唯一ID"""
        hash_input = f"{document_id}:{index}:{content[:50]}"
        return hashlib.md5(hash_input.encode()).hexdigest()[:16]

    def chunk(self, document_id: str, text: str) -> Iterator[Chunk]:
        """
        将文本分块

        策略：
        1. 优先按段落分割
        2. 如果段落超过目标token数，寻找句子边界
        3. 保持块大小接近目标token数
        4. 块之间添加重叠区域
        """
        if not text.strip():
            return

        paragraphs = self._split_into_paragraphs(text)
        current_chunk_parts = []
        current_tokens = 0
        current_start_pos = 0
        position = 0
        chunk_index = 0

        for paragraph in paragraphs:
            para_tokens = self.count_tokens(paragraph)
            para_with_newline = paragraph + "\n\n"

            # 如果单个段落就超过目标token数，需要进一步分割
            if para_tokens > self.config.target_tokens:
                # 先刷新当前累积的内容
                if current_chunk_parts:
                    chunk_content = "\n\n".join(current_chunk_parts)
                    yield self._create_chunk(
                        document_id, chunk_index, chunk_content,
                        current_start_pos, position, current_tokens
                    )
                    chunk_index += 1

                    # 添加重叠
                    overlap_text = self._get_overlap(current_chunk_parts)
                    current_chunk_parts = [overlap_text] if overlap_text else []
                    current_tokens = self.count_tokens(overlap_text) if overlap_text else 0
                    current_start_pos = position - len(overlap_text)

                # 分割大段落
                yield from self._split_large_paragraph(
                    document_id, paragraph, chunk_index, position
                )
                chunk_index += 1

                current_chunk_parts = []
                current_tokens = 0
                position += len(para_with_newline)
                current_start_pos = position

            # 如果累积内容加上新段落超过目标，先刷新
            elif current_tokens + para_tokens > self.config.target_tokens and current_chunk_parts:
                chunk_content = "\n\n".join(current_chunk_parts)
                yield self._create_chunk(
                    document_id, chunk_index, chunk_content,
                    current_start_pos, position, current_tokens
                )
                chunk_index += 1

                # 添加重叠
                overlap_text = self._get_overlap(current_chunk_parts)
                current_chunk_parts = [overlap_text, paragraph] if overlap_text else [paragraph]
                current_tokens = sum(self.count_tokens(p) for p in current_chunk_parts)
                current_start_pos = position - len(overlap_text) if overlap_text else position

                current_chunk_parts = [paragraph]
                current_tokens = para_tokens
                position += len(para_with_newline)

            else:
                # 累积段落
                current_chunk_parts.append(paragraph)
                current_tokens += para_tokens
                position += len(para_with_newline)

        # 处理最后的内容
        if current_chunk_parts:
            chunk_content = "\n\n".join(current_chunk_parts)
            yield self._create_chunk(
                document_id, chunk_index, chunk_content,
                current_start_pos, position, current_tokens
            )

    def _split_large_paragraph(
        self, document_id: str, paragraph: str, start_index: int, start_pos: int
    ) -> Iterator[Chunk]:
        """分割大段落为多个块"""
        sentences = re.split(r'(?<=[.!?。！？])\s+', paragraph)
        current_sentences = []
        current_tokens = 0
        position = start_pos
        chunk_index = start_index

        for sentence in sentences:
            sent_tokens = self.count_tokens(sentence)

            if current_tokens + sent_tokens > self.config.target_tokens and current_sentences:
                # 创建块
                chunk_content = " ".join(current_sentences)
                yield self._create_chunk(
                    document_id, chunk_index, chunk_content,
                    start_pos, position, current_tokens
                )
                chunk_index += 1

                # 添加重叠（最后一句）
                overlap_sents = self._get_overlap_sentences(current_sentences)
                current_sentences = overlap_sents + [sentence]
                current_tokens = sum(self.count_tokens(s) for s in current_sentences)
                start_pos = position - len(" ".join(overlap_sents))

            else:
                current_sentences.append(sentence)
                current_tokens += sent_tokens

            position += len(sentence) + 1

        # 最后的内容
        if current_sentences:
            chunk_content = " ".join(current_sentences)
            yield self._create_chunk(
                document_id, chunk_index, chunk_content,
                start_pos, position, current_tokens
            )

    def _get_overlap(self, paragraphs: list[str]) -> str:
        """从段落列表获取重叠文本"""
        overlap_chars = self.config.overlap_chars
        all_text = "\n\n".join(paragraphs)

        if len(all_text) <= overlap_chars:
            return all_text

        # 尝试找到段落边界
        overlap = all_text[-overlap_chars:]
        para_boundary = overlap.find("\n\n")
        if para_boundary > 0:
            return overlap[para_boundary + 2:]

        return overlap

    def _get_overlap_sentences(self, sentences: list[str]) -> list[str]:
        """从句子列表获取重叠句子"""
        overlap_chars = self.config.overlap_chars
        total_len = sum(len(s) + 1 for s in sentences)

        if total_len <= overlap_chars:
            return sentences

        # 从后往前取句子直到达到重叠大小
        overlap_sents = []
        current_len = 0
        for sent in reversed(sentences):
            if current_len + len(sent) > overlap_chars and overlap_sents:
                break
            overlap_sents.insert(0, sent)
            current_len += len(sent) + 1

        return overlap_sents

    def _create_chunk(
        self, document_id: str, index: int, content: str,
        start_pos: int, end_pos: int, token_count: int
    ) -> Chunk:
        """创建Chunk对象"""
        return Chunk(
            id=self._generate_chunk_id(document_id, index, content),
            document_id=document_id,
            index=index,
            content=content.strip(),
            start_pos=start_pos,
            end_pos=end_pos,
            token_count=token_count,
        )

    def get_stats(self, chunks: list[Chunk], original_text: str) -> ChunkerStats:
        """获取分块统计信息"""
        total_tokens = sum(c.token_count for c in chunks)
        return ChunkerStats(
            total_chars=len(original_text),
            total_tokens=total_tokens,
            chunk_count=len(chunks),
            avg_chunk_tokens=total_tokens / len(chunks) if chunks else 0,
        )


def create_chunker(config: ChunkerConfig) -> Chunker:
    """工厂函数：创建分块器"""
    return Chunker(config)
