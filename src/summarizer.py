"""摘要生成模块 - 两级摘要生成"""

import logging
from dataclasses import dataclass

from src.llm import LLMClient
from src.cache import Cache
from src.config import FeaturesConfig
from src.models import Chunk, SummaryL1, SummaryL2

logger = logging.getLogger(__name__)


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
        self.cache.set(
            cache_key,
            {
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
            },
        )

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
            logger.error(f"L1 摘要生成失败: {e}")
            logger.debug(f"失败提示词前200字符: {prompt[:200]}...")
            # 降级处理：返回空摘要
            return SummaryL1(
                bullets=["Error generating summary"],
                key_concepts=[],
            )

    async def _generate_l2(self, text: str, l1: SummaryL1) -> SummaryL2:
        """生成 L2 级摘要（中文学习笔记）"""
        # 结合原始文本和 L1 摘要生成更好的 L2
        combined_text = f"Original content:\n{text}\n\nKey points:\n" + "\n".join(
            f"- {b}" for b in l1.bullets
        )

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
            logger.error(f"L2 摘要生成失败: {e}")
            logger.debug(f"失败提示词前200字符: {prompt[:200]}...")
            # 降级处理
            return SummaryL2(
                overview="摘要生成失败",
                key_points=l1.bullets,
            )

    # 合并提示词：智能汇总多个摘要
    MERGE_SYSTEM_PROMPT = """You are an expert at synthesizing information. Your task is to merge multiple summaries into a cohesive document-level summary.

Rules:
1. Remove duplicates and merge similar points
2. Preserve the most important information
3. Maintain logical flow and structure
4. Keep technical terms accurate
5. Output in the same language as the input"""

    MERGE_L1_PROMPT_TEMPLATE = """Please merge the following bullet points into a concise document summary:

Input points:
{points}

Provide your response as a JSON object with this structure:
{{
    "bullets": ["merged point 1", "merged point 2", ...],
    "key_concepts": ["concept 1", "concept 2", ...]
}}

Guidelines:
- Create 15-25 high-quality bullets that cover the main topics
- Remove duplicates and merge related points
- Ensure bullets flow logically"""

    MERGE_L2_PROMPT_TEMPLATE = """请根据以下多个学习笔记片段，合并生成一份完整的文档级学习笔记：

输入内容：
{text}

请以下列JSON格式输出：
{{
    "overview": "内容概述（3-5句话，概括全文核心内容）",
    "key_points": ["核心要点1", "核心要点2", ...],
    "concepts_explained": [
        {{"term": "概念名称", "explanation": "中文解释"}}
    ],
    "code_examples": [
        {{"language": "代码语言", "code": "代码示例", "explanation": "代码解释"}}
    ],
    "related_topics": ["相关主题1", "相关主题2", ...]
}}

要求：
- 合并重复的概念解释，保留最清晰的
- 整合所有代码示例
- 相关主题去重
- 确保输出高质量、完整的学习笔记"""

    async def merge_l1_summaries(self, summaries: list[SummaryL1]) -> SummaryL1:
        """合并多个 L1 摘要为文档级摘要（使用 LLM 智能汇总）"""
        all_bullets = []
        all_concepts = set()

        for s in summaries:
            all_bullets.extend(s.bullets)
            all_concepts.update(s.key_concepts)

        # 去重并保持顺序
        unique_bullets = list(dict.fromkeys(all_bullets))
        unique_concepts = list(all_concepts)

        # 如果内容较少，直接返回（无需 LLM 汇总）
        if len(unique_bullets) <= 30:
            return SummaryL1(
                bullets=unique_bullets,
                key_concepts=unique_concepts,
            )

        # 使用 LLM 智能汇总
        logger.info(f"L1 摘要需要汇总: {len(unique_bullets)} bullets -> 请求 LLM 合并")
        points_text = "\n".join(f"- {b}" for b in unique_bullets)
        prompt = self.MERGE_L1_PROMPT_TEMPLATE.format(points=points_text)

        try:
            response = await self.llm.complete_json(
                prompt=prompt,
                system_prompt=self.MERGE_SYSTEM_PROMPT,
            )

            merged_bullets = response.get("bullets", unique_bullets[:30])
            merged_concepts = response.get("key_concepts", unique_concepts)

            logger.info(f"L1 合并完成: {len(merged_bullets)} bullets")
            return SummaryL1(
                bullets=merged_bullets,
                key_concepts=merged_concepts,
            )
        except Exception as e:
            logger.warning(f"L1 智能合并失败，使用截断策略: {e}")
            # 降级：使用更宽松的截断
            if len(unique_bullets) > 50:
                logger.warning(
                    f"L1 内容被截断: {len(unique_bullets)} -> 50 bullets, "
                    f"{len(unique_concepts)} -> 30 concepts"
                )
            return SummaryL1(
                bullets=unique_bullets[:50],  # 增加限制
                key_concepts=unique_concepts[:30],
            )

    async def merge_l2_summaries(self, summaries: list[SummaryL2]) -> SummaryL2:
        """合并多个 L2 摘要为文档级摘要（使用 LLM 智能汇总）"""
        if not summaries:
            return SummaryL2()

        # 收集所有内容
        all_key_points = []
        all_concepts = []
        all_code_examples = []
        all_related = set()

        for s in summaries:
            all_key_points.extend(s.key_points)
            all_concepts.extend(s.concepts_explained)
            all_code_examples.extend(s.code_examples)
            all_related.update(s.related_topics)

        # 去重
        unique_key_points = list(dict.fromkeys(all_key_points))
        unique_concepts = list(
            {c.get("term", str(c)): c for c in all_concepts}.values()
        )
        unique_code_examples = list(
            {c.get("code", str(c)): c for c in all_code_examples}.values()
        )
        unique_related = list(all_related)

        # 如果内容较少，直接返回（无需 LLM 汇总）
        total_items = (
            len(unique_key_points)
            + len(unique_concepts)
            + len(unique_code_examples)
            + len(unique_related)
        )
        if total_items <= 40:
            # 生成一个综合的 overview
            overview_parts = [s.overview for s in summaries if s.overview]
            overview = overview_parts[0] if overview_parts else ""

            return SummaryL2(
                overview=overview,
                key_points=unique_key_points,
                concepts_explained=unique_concepts,
                code_examples=unique_code_examples,
                related_topics=unique_related,
            )

        # 使用 LLM 智能汇总
        logger.info(
            f"L2 摘要需要汇总: {len(unique_key_points)} points, "
            f"{len(unique_concepts)} concepts, {len(unique_code_examples)} examples"
        )

        # 构建合并输入
        merge_input = []
        merge_input.append("## Key Points:")
        for p in unique_key_points:
            merge_input.append(f"- {p}")

        merge_input.append("\n## Concepts Explained:")
        for c in unique_concepts:
            merge_input.append(f"- {c.get('term', '')}: {c.get('explanation', '')}")

        merge_input.append("\n## Code Examples:")
        for c in unique_code_examples:
            merge_input.append(f"\nLanguage: {c.get('language', 'unknown')}")
            merge_input.append(f"```\n{c.get('code', '')}\n```")

        merge_input.append("\n## Related Topics:")
        for r in unique_related:
            merge_input.append(f"- {r}")

        text = "\n".join(merge_input)
        prompt = self.MERGE_L2_PROMPT_TEMPLATE.format(text=text)

        try:
            response = await self.llm.complete_json(
                prompt=prompt,
                system_prompt=self.MERGE_SYSTEM_PROMPT,
            )

            merged = SummaryL2(
                overview=response.get("overview", ""),
                key_points=response.get("key_points", unique_key_points[:20]),
                concepts_explained=response.get(
                    "concepts_explained", unique_concepts[:15]
                ),
                code_examples=response.get("code_examples", unique_code_examples[:10]),
                related_topics=response.get("related_topics", unique_related[:15]),
            )

            logger.info(
                f"L2 合并完成: {len(merged.key_points)} points, "
                f"{len(merged.concepts_explained)} concepts, "
                f"{len(merged.code_examples)} examples"
            )
            return merged
        except Exception as e:
            logger.warning(f"L2 智能合并失败，使用截断策略: {e}")
            # 降级：使用更宽松的截断
            if total_items > 60:
                logger.warning(
                    f"L2 内容被截断: {len(unique_key_points)} points -> 25, "
                    f"{len(unique_concepts)} concepts -> 15, "
                    f"{len(unique_code_examples)} examples -> 8"
                )

            overview_parts = [s.overview for s in summaries if s.overview]
            return SummaryL2(
                overview=overview_parts[0] if overview_parts else "",
                key_points=unique_key_points[:25],
                concepts_explained=unique_concepts[:15],
                code_examples=unique_code_examples[:8],
                related_topics=unique_related[:15],
            )
