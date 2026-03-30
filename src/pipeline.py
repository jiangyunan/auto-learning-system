"""Pipeline模块 - 文档处理流程编排"""

import asyncio
from pathlib import Path
from typing import AsyncIterator
from dataclasses import dataclass

from src.config import Config
from src.models import Document, Chunk, ProcessResult, SourceType, DocumentGraph
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


@dataclass
class FolderProcessResult:
    """文件夹处理结果"""

    results: list[ProcessResult]
    graph: DocumentGraph
    statistics: dict


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

    async def process_document(
        self, source: str, progress_callback=None
    ) -> ProcessResult:
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
            progress_callback(
                PipelineProgress(
                    "summarize", 2, 4, f"Summarizing {len(chunks)} chunks..."
                )
            )

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

    async def process_url_recursive(
        self,
        url: str,
        patterns: list[str] | None = None,
        max_depth: int = 3,
        progress_callback=None,
    ) -> ProcessResult:
        """处理URL（递归采集所有匹配页面并合并）"""
        if progress_callback:
            progress_callback(PipelineProgress("crawl", 0, 4, f"Fetching {url}..."))

        crawl_result = self.crawler.crawl_url_recursive(
            url, patterns=patterns, max_depth=max_depth
        )

        if not crawl_result or not crawl_result.document.content:
            raise ValueError(f"Failed to crawl: {url}")

        doc = crawl_result.document

        if progress_callback:
            progress_callback(PipelineProgress("chunk", 1, 4, "Chunking document..."))

        chunks = list(self.chunker.chunk(doc.id, doc.content))

        if progress_callback:
            progress_callback(
                PipelineProgress(
                    "summarize", 2, 4, f"Summarizing {len(chunks)} chunks..."
                )
            )

        chunk_summaries = []
        for chunk in chunks:
            summary = await self.summarizer.summarize_chunk(chunk)
            chunk_summaries.append(summary)

        l1_summaries = [s.l1 for s in chunk_summaries]
        l2_summaries = [s.l2 for s in chunk_summaries if s.l2.overview]

        merged_l1 = await self.summarizer.merge_l1_summaries(l1_summaries)
        merged_l2 = await self.summarizer.merge_l2_summaries(l2_summaries)

        result = ProcessResult(
            document_id=doc.id,
            document_title=doc.title,
            source_url=url,
            chunks_count=len(chunks),
            l1_summary=merged_l1,
            l2_summary=merged_l2,
        )

        if progress_callback:
            progress_callback(PipelineProgress("export", 3, 4, "Exporting..."))

        export_result = self.exporter.export(result)
        if export_result.success:
            result.output_path = export_result.file_path

        if progress_callback:
            progress_callback(PipelineProgress("complete", 4, 4, "Done!"))

        return result

    async def process_batch(
        self, sources: list[str], progress_callback=None
    ) -> list[ProcessResult]:
        """批量处理文档"""
        results = []
        for i, source in enumerate(sources):
            if progress_callback:
                progress_callback(
                    PipelineProgress(
                        "batch", i, len(sources), f"Processing {source}..."
                    )
                )
            try:
                result = await self.process_document(source, progress_callback)
                results.append(result)
            except Exception as e:
                print(f"Error processing {source}: {e}")
        return results

    async def process_folder(
        self,
        folder_path: str | Path,
        recursive: bool = True,
        include_related_context: bool = True,
        progress_callback=None,
    ) -> FolderProcessResult:
        """
        处理文件夹中的所有Markdown文件，按链接关系排序

        Args:
            folder_path: 文件夹路径
            recursive: 是否递归处理子文件夹
            include_related_context: 是否包含相关文档的上下文
            progress_callback: 进度回调函数

        Returns:
            FolderProcessResult: 包含所有处理结果和图信息
        """
        path = Path(folder_path)
        if not path.is_dir():
            raise ValueError(f"Not a directory: {folder_path}")

        # 1. 构建文档关系图
        if progress_callback:
            progress_callback(
                PipelineProgress(
                    "graph", 0, 3, f"Building document graph from {folder_path}..."
                )
            )

        graph = self.crawler.crawl_folder(path, recursive)
        doc_order = graph.get_processing_order()

        stats = graph.get_statistics()
        if progress_callback:
            progress_callback(
                PipelineProgress(
                    "graph",
                    1,
                    3,
                    f"Found {stats['total_documents']} documents, {stats['total_links']} links",
                )
            )

        # 2. 按依赖顺序处理文档
        results = []
        for i, doc_id in enumerate(doc_order):
            doc = graph.documents[doc_id]

            if progress_callback:
                progress_callback(
                    PipelineProgress(
                        "process", i, len(doc_order), f"Processing {doc.title}..."
                    )
                )

            try:
                # 获取相关文档作为上下文
                related_context = ""
                if include_related_context:
                    related_ids = graph.get_related_documents(doc_id)
                    related_docs = [
                        graph.documents[rid]
                        for rid in related_ids
                        if rid in graph.documents
                    ]
                    if related_docs:
                        related_context = self._build_related_context(doc, related_docs)

                result = await self._process_single_document(
                    doc,
                    related_context=related_context,
                    progress_callback=progress_callback,
                )
                results.append(result)

            except Exception as e:
                print(f"Error processing {doc.source_path}: {e}")
                # 创建失败的占位结果
                results.append(
                    ProcessResult(
                        document_id=doc.id,
                        document_title=doc.title,
                        source_url=doc.source_path,
                    )
                )

        if progress_callback:
            progress_callback(
                PipelineProgress("complete", len(doc_order), len(doc_order), "Done!")
            )

        return FolderProcessResult(
            results=results,
            graph=graph,
            statistics={
                "total": len(results),
                "successful": len([r for r in results if r.output_path]),
                **stats,
            },
        )

    def _build_related_context(
        self, current_doc: Document, related_docs: list[Document]
    ) -> str:
        """构建相关文档的上下文信息"""
        context_parts = ["\n\n## Related Documents Context\n"]
        for rel_doc in related_docs[:3]:  # 最多3个相关文档
            context_parts.append(f"\n### From: {rel_doc.title}\n")
            # 取前500字符作为预览
            preview = rel_doc.content[:500].replace("#", "").strip()
            context_parts.append(f"{preview}...\n")
        return "\n".join(context_parts)

    async def _process_single_document(
        self, doc: Document, related_context: str = "", progress_callback=None
    ) -> ProcessResult:
        """处理单个文档（内部方法）"""
        # 组合内容（原文 + 相关文档上下文）
        combined_content = doc.content
        if related_context:
            combined_content += related_context

        # 1. 分块
        chunks = list(self.chunker.chunk(doc.id, combined_content))

        # 2. 生成摘要
        chunk_summaries = []
        for chunk in chunks:
            summary = await self.summarizer.summarize_chunk(chunk)
            chunk_summaries.append(summary)

        # 合并摘要
        l1_summaries = [s.l1 for s in chunk_summaries]
        l2_summaries = [s.l2 for s in chunk_summaries if s.l2.overview]

        merged_l1 = await self.summarizer.merge_l1_summaries(l1_summaries)
        merged_l2 = await self.summarizer.merge_l2_summaries(l2_summaries)

        # 3. 构建结果
        result = ProcessResult(
            document_id=doc.id,
            document_title=doc.title,
            source_url=doc.source_path,
            chunks_count=len(chunks),
            l1_summary=merged_l1,
            l2_summary=merged_l2,
        )

        # 4. 导出
        export_result = self.exporter.export(result)
        if export_result.success:
            result.output_path = export_result.file_path

        return result
