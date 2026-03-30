"""Pipeline模块 - 文档处理流程编排"""
import asyncio
from pathlib import Path
from typing import AsyncIterator
from dataclasses import dataclass

from src.config import Config
from src.models import Document, Chunk, ProcessResult, SourceType
from src.crawler import Crawler
from src.chunker import Chunker
from src.summarizer import Summarizer
from src.exporter import Exporter
from src.cache import Cache
from src.llm import LLMClient


@dataclass
class PipelineProgress:
    """处理进度"""
    stage: str
    current: int
    total: int
    message: str = ""


class Pipeline:
    """文档处理流水线"""

    def __init__(self, config: Config):
        self.config = config
        self.crawler = Crawler()
        self.chunker = Chunker(config.chunker)
        self.cache = Cache(config.cache)
        self.llm = LLMClient(config.llm)
        self.summarizer = Summarizer(self.llm, self.cache, config.features)
        self.exporter = Exporter(config.output)

    async def process_document(self, source: str, progress_callback=None) -> ProcessResult:
        """处理单个文档"""
        # 1. 爬取
        if progress_callback:
            progress_callback(PipelineProgress("crawl", 0, 4, f"Fetching {source}..."))

        if source.startswith(("http://", "https://")):
            crawl_result = self.crawler.crawl_url(source)
        elif Path(source).suffix.lower() == ".pdf":
            crawl_result = self.crawler.crawl_pdf(source)
        else:
            crawl_results = list(self.crawler.crawl_local(source))
            crawl_result = crawl_results[0] if crawl_results else None

        if not crawl_result or not crawl_result.document.content:
            raise ValueError(f"Failed to crawl: {source}")

        doc = crawl_result.document

        # 2. 分块
        if progress_callback:
            progress_callback(PipelineProgress("chunk", 1, 4, "Chunking document..."))

        chunks = list(self.chunker.chunk(doc.id, doc.content))

        # 3. 生成摘要
        if progress_callback:
            progress_callback(PipelineProgress("summarize", 2, 4, f"Summarizing {len(chunks)} chunks..."))

        chunk_summaries = []
        for i, chunk in enumerate(chunks):
            summary = await self.summarizer.summarize_chunk(chunk)
            chunk_summaries.append(summary)

        # 合并摘要
        l1_summaries = [s.l1 for s in chunk_summaries]
        l2_summaries = [s.l2 for s in chunk_summaries if s.l2.overview]

        merged_l1 = await self.summarizer.merge_l1_summaries(l1_summaries)
        merged_l2 = await self.summarizer.merge_l2_summaries(l2_summaries)

        # 4. 构建结果
        result = ProcessResult(
            document_id=doc.id,
            document_title=doc.title,
            source_url=doc.source_path if doc.source_type == SourceType.URL else None,
            chunks_count=len(chunks),
            l1_summary=merged_l1,
            l2_summary=merged_l2,
        )

        # 5. 导出
        if progress_callback:
            progress_callback(PipelineProgress("export", 3, 4, "Exporting..."))

        export_result = self.exporter.export(result)
        if export_result.success:
            result.output_path = export_result.file_path

        if progress_callback:
            progress_callback(PipelineProgress("complete", 4, 4, "Done!"))

        return result

    async def process_batch(self, sources: list[str], progress_callback=None) -> list[ProcessResult]:
        """批量处理文档"""
        results = []
        for i, source in enumerate(sources):
            if progress_callback:
                progress_callback(PipelineProgress(
                    "batch", i, len(sources), f"Processing {source}..."
                ))
            try:
                result = await self.process_document(source, progress_callback)
                results.append(result)
            except Exception as e:
                print(f"Error processing {source}: {e}")
        return results
