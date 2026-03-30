"""CLI主程序"""
import asyncio
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

from src.config import load_config
from src.pipeline import Pipeline, PipelineProgress

app = typer.Typer(help="Auto Learning System - 自动学习文档生成Obsidian笔记")
console = Console()


@app.command()
def process(
    source: str = typer.Argument(..., help="文档来源 (URL, 文件路径或目录)"),
    config_path: Optional[str] = typer.Option(None, "--config", "-c", help="配置文件路径"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="详细输出"),
):
    """处理单个文档或目录"""
    config = load_config(config_path) if config_path else load_config()
    pipeline = Pipeline(config)

    def progress_callback(p: PipelineProgress):
        if verbose:
            console.print(f"[{p.stage}] {p.message}")

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Processing...", total=None)

        async def run():
            result = await pipeline.process_document(source, progress_callback)
            progress.update(task, description=f"✓ Exported to {result.output_path}")
            return result

        result = asyncio.run(run())

    # 显示结果
    table = Table(title="Processing Result")
    table.add_column("Field", style="cyan")
    table.add_column("Value", style="green")
    table.add_row("Title", result.document_title)
    table.add_row("Chunks", str(result.chunks_count))
    table.add_row("Output", str(result.output_path) if result.output_path else "N/A")
    console.print(table)


@app.command()
def batch(
    sources_file: Path = typer.Argument(..., help="包含来源列表的文件 (每行一个)"),
    config_path: Optional[str] = typer.Option(None, "--config", "-c", help="配置文件路径"),
):
    """批量处理多个文档"""
    config = load_config(config_path) if config_path else load_config()
    pipeline = Pipeline(config)

    sources = sources_file.read_text().strip().split("\n")
    sources = [s.strip() for s in sources if s.strip()]

    console.print(f"Processing {len(sources)} sources...")

    async def run():
        return await pipeline.process_batch(sources)

    results = asyncio.run(run())

    # 显示汇总
    table = Table(title=f"Batch Results ({len(results)}/{len(sources)} successful)")
    table.add_column("Title", style="cyan")
    table.add_column("Chunks", style="blue")
    table.add_column("Output", style="green")

    for r in results:
        table.add_row(
            r.document_title[:50],
            str(r.chunks_count),
            str(r.output_path) if r.output_path else "Failed"
        )
    console.print(table)


@app.command()
def serve(
    host: str = typer.Option("127.0.0.1", "--host", "-h", help="监听地址"),
    port: int = typer.Option(8000, "--port", "-p", help="监听端口"),
    config_path: Optional[str] = typer.Option(None, "--config", "-c", help="配置文件路径"),
):
    """启动API服务"""
    import uvicorn
    from src.api import create_app

    config = load_config(config_path) if config_path else load_config()
    app = create_app(config)

    console.print(f"Starting server at http://{host}:{port}")
    uvicorn.run(app, host=host, port=port)


@app.command()
def config(
    example: bool = typer.Option(False, "--example", "-e", help="显示配置示例"),
):
    """查看或生成配置"""
    if example:
        example_yaml = """
llm:
  base_url: http://localhost:11434/v1
  api_key: ollama
  model: llama3
  temperature: 0.7

output:
  format: obsidian
  path: ./vault/
  filename_template: "{title}.md"

features:
  chinese_notes: true

chunker:
  target_tokens: 1500
  overlap_chars: 200
"""
        console.print(example_yaml)
    else:
        config = load_config()
        console.print(f"Current config: {config}")


if __name__ == "__main__":
    app()
