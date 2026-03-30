"""API模块 - FastAPI接口"""
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from src.config import Config
from src.pipeline import Pipeline, PipelineProgress


# 全局配置和pipeline实例
_app_config: Config = None


class ProcessRequest(BaseModel):
    source: str


class ProcessResponse(BaseModel):
    document_id: str
    title: str
    chunks_count: int
    output_path: str
    success: bool
    error: str = ""


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

    @app.post("/process", response_model=ProcessResponse)
    async def process(request: ProcessRequest):
        """处理文档"""
        pipeline = Pipeline(_app_config)

        try:
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
        """批量处理"""
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

    return app
