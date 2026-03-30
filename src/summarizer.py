"""摘要生成模块 - 两级摘要生成"""
import json
from typing import Optional
from dataclasses import dataclass

from src.llm import LLMClient
from src.cache import Cache
from src.config import FeaturesConfig
from src.models import Chunk, SummaryL1, SummaryL2


@dataclass
class SummaryResult:
    """摘要生成结果"""
    l1: SummaryL1
    l2: SummaryL2
    from_cache: bool = False


class Summarizer:
    """两级摘要生成器"""

    # L1 提示词：压缩内容为 bullet points
    L1_SYSTEM_PROMPT = """You are a content compression expert. Your task is to extract the key information from the provided text and present it as concise bullet points.

Rules:
1. Extract only the most important facts, concepts, and takeaways
2. Use concise language - each bullet should be one sentence
3. Preserve technical terms and key concepts
4. Output in the same language as the input text
5. Focus on what matters for understanding the core content"""

    L1_USER_PROMPT_TEMPLATE = """Please summarize the following text into bullet points:

{text}

Provide your response as a JSON object with this structure:
{{
    "bullets": ["point 1", "point 2", ...],
    "key_concepts": ["concept 1", "concept 2", ...]
}}"""

    # L2 提示词：生成中文学习笔记
    L2_SYSTEM_PROMPT = """你是一位专业的技术文档学习笔记作者。你的任务是将技术内容转化为结构化的中文学习笔记，帮助读者深入理解核心概念。

规则：
1. 使用清晰、易懂的中文解释技术概念
2. 保留重要的英文术语，但提供中文解释
3. 包含具体的代码示例和解释
4. 结构化输出，便于复习和理解
5. 突出核心要点和实际应用场景"""

    L2_USER_PROMPT_TEMPLATE = """请根据以下内容生成中文学习笔记：

{text}

请以下列JSON格式输出：
{{
    "overview": "内容概述（2-3句话）",
    "key_points": ["核心要点1", "核心要点2", ...],
    "concepts_explained": [
        {{"term": "概念名称", "explanation": "中文解释"}}
    ],
    "code_examples": [
        {{"language": "代码语言", "code": "代码示例", "explanation": "代码解释"}}
    ],
    "related_topics": ["相关主题1", "相关主题2", ...]
}}"""

    def __init__(
        self,
        llm_client: LLMClient,
        cache: Cache,
        features_config: FeaturesConfig,
    ):
        self.llm = llm_client
        self.cache = cache
        self.config = features_config

    async def summarize_chunk(self, chunk: Chunk) -> SummaryResult:
        """为单个分块生成两级摘要"""
        cache_key = f"chunk:{chunk.id}:{hash(chunk.content)}"

        # 尝试从缓存获取
        if cached := self.cache.get(cache_key):
            return SummaryResult(
                l1=SummaryL1(**cached["l1"]),
                l2=SummaryL2(**cached["l2"]),
                from_cache=True,
            )

        # 生成 L1 摘要
        l1 = await self._generate_l1(chunk.content)

        # 根据配置决定是否生成 L2
        if self.config.chinese_notes:
            l2 = await self._generate_l2(chunk.content, l1)
        else:
            l2 = SummaryL2()

        result = SummaryResult(l1=l1, l2=l2)

        # 缓存结果
        self.cache.set(cache_key, {
            "l1": {
                "bullets": l1.bullets,
                "key_concepts": l1.key_concepts,
            },
            "l2": {
                "overview": l2.overview,
                "key_points": l2.key_points,
                "concepts_explained": l2.concepts_explained,
                "code_examples": l2.code_examples,
                "related_topics": l2.related_topics,
            },
        })

        return result

    async def _generate_l1(self, text: str) -> SummaryL1:
        """生成 L1 级摘要（内容压缩）"""
        prompt = self.L1_USER_PROMPT_TEMPLATE.format(text=text)

        try:
            response = await self.llm.complete_json(
                prompt=prompt,
                system_prompt=self.L1_SYSTEM_PROMPT,
            )

            return SummaryL1(
                bullets=response.get("bullets", []),
                key_concepts=response.get("key_concepts", []),
            )
        except Exception as e:
            # 降级处理：返回空摘要
            return SummaryL1(
                bullets=["Error generating summary"],
                key_concepts=[],
            )

    async def _generate_l2(self, text: str, l1: SummaryL1) -> SummaryL2:
        """生成 L2 级摘要（中文学习笔记）"""
        # 结合原始文本和 L1 摘要生成更好的 L2
        combined_text = f"Original content:\n{text}\n\nKey points:\n" + "\n".join(f"- {b}" for b in l1.bullets)

        prompt = self.L2_USER_PROMPT_TEMPLATE.format(text=combined_text)

        try:
            response = await self.llm.complete_json(
                prompt=prompt,
                system_prompt=self.L2_SYSTEM_PROMPT,
            )

            return SummaryL2(
                overview=response.get("overview", ""),
                key_points=response.get("key_points", []),
                concepts_explained=response.get("concepts_explained", []),
                code_examples=response.get("code_examples", []),
                related_topics=response.get("related_topics", []),
            )
        except Exception as e:
            # 降级处理
            return SummaryL2(
                overview="摘要生成失败",
                key_points=l1.bullets,
            )

    async def merge_l1_summaries(self, summaries: list[SummaryL1]) -> SummaryL1:
        """合并多个 L1 摘要为文档级摘要"""
        all_bullets = []
        all_concepts = set()

        for s in summaries:
            all_bullets.extend(s.bullets)
            all_concepts.update(s.key_concepts)

        # 去重并保持顺序
        unique_bullets = list(dict.fromkeys(all_bullets))
        unique_concepts = list(all_concepts)

        return SummaryL1(
            bullets=unique_bullets[:20],  # 限制数量
            key_concepts=unique_concepts[:15],
        )

    async def merge_l2_summaries(self, summaries: list[SummaryL2]) -> SummaryL2:
        """合并多个 L2 摘要为文档级摘要"""
        if not summaries:
            return SummaryL2()

        # 使用第一个作为主要基础
        overview = summaries[0].overview
        all_key_points = []
        all_concepts = []
        all_code_examples = []
        all_related = set()

        for s in summaries:
            all_key_points.extend(s.key_points)
            all_concepts.extend(s.concepts_explained)
            all_code_examples.extend(s.code_examples)
            all_related.update(s.related_topics)

        return SummaryL2(
            overview=overview,
            key_points=list(dict.fromkeys(all_key_points))[:15],
            concepts_explained=all_concepts[:10],
            code_examples=all_code_examples[:5],
            related_topics=list(all_related)[:10],
        )
