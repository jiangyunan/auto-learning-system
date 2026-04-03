"""API模块 - FastAPI接口"""

from contextlib import asynccontextmanager
from typing import AsyncGenerator
from pathlib import Path

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from src.config import Config
from src.pipeline import Pipeline

# 全局配置和pipeline实例
_app_config: Config | None = None


class ProcessRequest(BaseModel):
    source: str
    recursive: bool = True
    include_related_context: bool = True


class ProcessResponse(BaseModel):
    document_id: str
    title: str
    chunks_count: int
    output_path: str
    success: bool
    error: str = ""


class FolderProcessResponse(BaseModel):
    total: int
    successful: int
    statistics: dict
    results: list[dict]


class HealthResponse(BaseModel):
    status: str
    llm_ready: bool


def create_app(config: Config) -> FastAPI:
    """创建FastAPI应用"""
    global _app_config
    _app_config = config

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncGenerator:
        """应用生命周期管理"""
        # 启动时检查
        yield
        # 关闭时清理

    app = FastAPI(
        title="Auto Learning System API",
        description="自动学习文档生成Obsidian笔记",
        version="0.1.0",
        lifespan=lifespan,
    )

    @app.get("/health", response_model=HealthResponse)
    async def health():
        """健康检查"""
        pipeline = Pipeline(_app_config)
        llm_ready = await pipeline.llm.health_check()
        return HealthResponse(
            status="healthy" if llm_ready else "degraded",
            llm_ready=llm_ready,
        )

    @app.post("/process")
    async def process(request: ProcessRequest):
        """处理文档或文件夹"""
        pipeline = Pipeline(_app_config)

        try:
            source_path = Path(request.source)
            is_folder = source_path.is_dir()

            if is_folder:
                # 文件夹处理
                result = await pipeline.process_folder(
                    request.source,
                    recursive=request.recursive,
                    include_related_context=request.include_related_context,
                )
                return FolderProcessResponse(
                    total=result.statistics["total"],
                    successful=result.statistics["successful"],
                    statistics={
                        "total_documents": result.statistics.get("total_documents", 0),
                        "total_links": result.statistics.get("total_links", 0),
                        "wiki_links": result.statistics.get("wiki_links", 0),
                        "markdown_links": result.statistics.get("markdown_links", 0),
                        "broken_links": result.statistics.get("broken_links", 0),
                    },
                    results=[
                        {
                            "document_id": r.document_id,
                            "title": r.document_title,
                            "chunks_count": r.chunks_count,
                            "output_path": (
                                str(r.output_path) if r.output_path else None
                            ),
                            "success": r.output_path is not None,
                        }
                        for r in result.results
                    ],
                )
            else:
                # 单文件处理
                result = await pipeline.process_document(request.source)
                return ProcessResponse(
                    document_id=result.document_id,
                    title=result.document_title,
                    chunks_count=result.chunks_count,
                    output_path=str(result.output_path) if result.output_path else "",
                    success=result.output_path is not None,
                )
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @app.post("/batch")
    async def batch(sources: list[str]):
        """批量处理（保留向后兼容）"""
        pipeline = Pipeline(_app_config)
        results = await pipeline.process_batch(sources)
        return {
            "total": len(sources),
            "successful": len([r for r in results if r.output_path]),
            "results": [
                {
                    "title": r.document_title,
                    "success": r.output_path is not None,
                }
                for r in results
            ],
        }

    @app.post("/folder")
    async def process_folder(
        path: str, recursive: bool = True, include_related_context: bool = True
    ):
        """专门处理文件夹的端点"""
        pipeline = Pipeline(_app_config)

        try:
            result = await pipeline.process_folder(
                path,
                recursive=recursive,
                include_related_context=include_related_context,
            )
            return FolderProcessResponse(
                total=result.statistics["total"],
                successful=result.statistics["successful"],
                statistics={
                    "total_documents": result.statistics.get("total_documents", 0),
                    "total_links": result.statistics.get("total_links", 0),
                    "wiki_links": result.statistics.get("wiki_links", 0),
                    "markdown_links": result.statistics.get("markdown_links", 0),
                    "broken_links": result.statistics.get("broken_links", 0),
                },
                results=[
                    {
                        "document_id": r.document_id,
                        "title": r.document_title,
                        "chunks_count": r.chunks_count,
                        "output_path": str(r.output_path) if r.output_path else None,
                        "success": r.output_path is not None,
                    }
                    for r in result.results
                ],
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    return app
