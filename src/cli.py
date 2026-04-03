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
    config_path: Optional[str] = typer.Option(
        None, "--config", "-c", help="配置文件路径"
    ),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="详细输出"),
    recursive: bool = typer.Option(True, "--recursive", "-r", help="递归处理子文件夹"),
    no_related_context: bool = typer.Option(
        False, "--no-related-context", help="不包含相关文档上下文"
    ),
    pattern: Optional[list[str]] = typer.Option(
        None, "--pattern", "-p", help="URL匹配模式 (可用于URL递归采集)"
    ),
    max_depth: int = typer.Option(3, "--max-depth", "-d", help="URL递归最大深度"),
):
    """处理单个文档或目录"""
    config = load_config(config_path) if config_path else load_config()
    pipeline = Pipeline(config)

    source_path = Path(source)
    is_folder = source_path.is_dir()

    def progress_callback(p: PipelineProgress):
        if verbose:
            if p.total > 0:
                percentage = (p.current / p.total) * 100
                console.print(
                    f"[bold cyan][{p.stage}][/bold cyan] "
                    f"[dim]({p.current}/{p.total}, {percentage:.1f}%)[/dim] "
                    f"{p.message}"
                )
            else:
                console.print(f"[bold cyan][{p.stage}][/bold cyan] {p.message}")

            # 显示详细摘要信息
            if p.metadata:
                if p.stage == "crawl":
                    if "title" in p.metadata:
                        console.print(f"  页面标题: {p.metadata['title']}")
                    if "links_found" in p.metadata:
                        console.print(f"  发现链接: {p.metadata['links_found']} 个")
                    if "links_matched" in p.metadata:
                        console.print(f"  匹配链接: {p.metadata['links_matched']} 个")
                    if "pages_crawled" in p.metadata:
                        console.print(f"  爬取页面: {p.metadata['pages_crawled']} 个")
                    if "pages_merged" in p.metadata:
                        console.print(
                            f"  成功合并: {p.metadata['pages_merged']} 个页面"
                        )
                    if "errors" in p.metadata:
                        console.print(
                            f"  [red]错误数量: {p.metadata['errors']} 个[/red]"
                        )
                    if "error_details" in p.metadata and p.metadata["error_details"]:
                        console.print("  [red]错误详情:[/red]")
                        for error in p.metadata["error_details"]:
                            console.print(f"    - {error}")
                elif p.stage == "chunk":
                    console.print(
                        f"  内容大小: {p.metadata.get('content_size_kb', 'N/A')} KB ({p.metadata.get('content_size', 'N/A')} 字符)"
                    )
                    console.print(
                        f"  预计分块: {p.metadata.get('estimated_chunks', 'N/A')} 个"
                    )
                elif p.stage == "summarize":
                    if "chunk_index" in p.metadata:
                        console.print(
                            f"  当前块: {p.metadata['chunk_index']}/{p.metadata.get('total_chunks', '?')}"
                        )
                        console.print(
                            f"  块大小: {p.metadata.get('chunk_size', 'N/A')} 字符"
                        )
                elif p.stage == "export":
                    console.print(
                        f"  文档标题: {p.metadata.get('document_title', 'N/A')}"
                    )
                    console.print(
                        f"  分块数量: {p.metadata.get('chunks_count', 'N/A')}"
                    )
                    console.print(
                        f"  L1摘要: {p.metadata.get('l1_bullets', 0)} 个要点, {p.metadata.get('l1_concepts', 0)} 个概念"
                    )
                    if p.metadata.get("l2_has_overview"):
                        console.print("  L2摘要: 已生成")
                elif p.stage == "complete":
                    if "output_path" in p.metadata:
                        console.print(f"  导出路径: {p.metadata['output_path']}")

    # 递归采集模式：在 Progress 之前完成链接发现和用户确认
    confirmed_recursive = False
    if source.startswith(("http://", "https://")) and pattern:

        console.print("\n[bold blue]正在发现链接...[/bold blue]")
        console.print(f"起始URL: {source}")
        console.print(f"匹配模式: {pattern}")
        console.print(f"最大深度: {max_depth}")

        # 发现所有匹配的链接
        all_links, matched_links = pipeline.crawler.discover_links(
            source, patterns=pattern, max_depth=max_depth
        )

        console.print(
            f"\n[bold green]发现 {len(matched_links)} 个匹配的链接:[/bold green]"
        )

        # 显示匹配的链接
        for i, link in enumerate(sorted(matched_links), 1):
            console.print(f"  {i}. {link}")

        if len(matched_links) == 0:
            console.print("[yellow]没有匹配的链接，退出。[/yellow]")
            raise typer.Exit()

        # 询问用户确认
        confirm = console.input("\n[yellow]是否继续爬取这些链接? (y/n): [/yellow]")
        if confirm.lower() != "y":
            console.print("[yellow]已取消。[/yellow]")
            raise typer.Exit()

        console.print("\n[bold blue]开始爬取...[/bold blue]\n")
        confirmed_recursive = True

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Processing...", total=None)

        async def run():
            if is_folder:
                # 使用文件夹处理模式
                result = await pipeline.process_folder(
                    source,
                    recursive=recursive,
                    include_related_context=not no_related_context,
                    progress_callback=progress_callback,
                )
                progress.update(
                    task, description=f"✓ Processed {len(result.results)} documents"
                )
                return result
            elif source.startswith(("http://", "https://")):
                # URL处理模式
                if confirmed_recursive:
                    # 递归采集模式（已通过用户确认）
                    result = await pipeline.process_url_recursive(
                        source,
                        patterns=pattern,
                        max_depth=max_depth,
                        progress_callback=progress_callback,
                    )
                    progress.update(
                        task, description=f"✓ Exported to {result.output_path}"
                    )
                    return result
                else:
                    # 单URL处理
                    result = await pipeline.process_document(source, progress_callback)
                    progress.update(
                        task, description=f"✓ Exported to {result.output_path}"
                    )
                    return result
            else:
                # 单文件处理
                result = await pipeline.process_document(source, progress_callback)
                progress.update(task, description=f"✓ Exported to {result.output_path}")
                return result

        result = asyncio.run(run())

    # 显示结果
    if is_folder:
        # 文件夹处理结果
        table = Table(
            title=f"Folder Processing Results ({result.statistics['successful']}/{result.statistics['total']} successful)"
        )
        table.add_column("Field", style="cyan")
        table.add_column("Value", style="green")
        table.add_row("Total Documents", str(result.statistics["total_documents"]))
        table.add_row("Total Links", str(result.statistics["total_links"]))
        table.add_row("Wiki Links", str(result.statistics["wiki_links"]))
        table.add_row("Markdown Links", str(result.statistics["markdown_links"]))
        table.add_row("Broken Links", str(result.statistics["broken_links"]))
        console.print(table)

        # 详细结果表
        detail_table = Table(title="Processed Documents")
        detail_table.add_column("Title", style="cyan")
        detail_table.add_column("Chunks", style="blue")
        detail_table.add_column("Output", style="green")
        for r in result.results:
            detail_table.add_row(
                r.document_title[:50],
                str(r.chunks_count),
                str(r.output_path) if r.output_path else "Failed",
            )
        console.print(detail_table)
    else:
        # 单文件处理结果
        table = Table(title="Processing Result")
        table.add_column("Field", style="cyan")
        table.add_column("Value", style="green")
        table.add_row("Title", result.document_title)
        table.add_row("Chunks", str(result.chunks_count))
        table.add_row(
            "Output", str(result.output_path) if result.output_path else "N/A"
        )
        console.print(table)


@app.command()
def batch(
    sources_file: Path = typer.Argument(..., help="包含来源列表的文件 (每行一个)"),
    config_path: Optional[str] = typer.Option(
        None, "--config", "-c", help="配置文件路径"
    ),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="详细输出"),
):
    """批量处理多个文档"""
    config = load_config(config_path) if config_path else load_config()
    pipeline = Pipeline(config)

    sources = sources_file.read_text().strip().split("\n")
    sources = [s.strip() for s in sources if s.strip()]

    console.print(f"Processing {len(sources)} sources...")

    def progress_callback(p: PipelineProgress):
        if verbose:
            if p.total > 0:
                percentage = (p.current / p.total) * 100
                console.print(
                    f"[bold cyan][{p.stage}][/bold cyan] "
                    f"[dim]({p.current}/{p.total}, {percentage:.1f}%)[/dim] "
                    f"{p.message}"
                )
            else:
                console.print(f"[bold cyan][{p.stage}][/bold cyan] {p.message}")

    async def run():
        return await pipeline.process_batch(sources, progress_callback)

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
            str(r.output_path) if r.output_path else "Failed",
        )
    console.print(table)


@app.command()
def serve(
    host: str = typer.Option("127.0.0.1", "--host", "-h", help="监听地址"),
    port: int = typer.Option(8000, "--port", "-p", help="监听端口"),
    config_path: Optional[str] = typer.Option(
        None, "--config", "-c", help="配置文件路径"
    ),
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


@app.command()
def cache(
    action: str = typer.Argument(
        ..., help="操作: stats(查看统计), clear(清空), clean(清理旧缓存)"
    ),
    config_path: Optional[str] = typer.Option(
        None, "--config", "-c", help="配置文件路径"
    ),
    days: int = typer.Option(
        30, "--days", "-d", help="清理超过多少天的缓存(仅clean操作)"
    ),
):
    """管理缓存"""
    from src.cache import create_cache

    config = load_config(config_path) if config_path else load_config()
    cache_instance = create_cache(config.cache)

    if action == "stats":
        stats = cache_instance.get_stats()
        if not stats.get("enabled"):
            console.print("[yellow]缓存已禁用[/yellow]")
            return

        table = Table(title="Cache Statistics")
        table.add_column("Metric", style="cyan")
        table.add_column("Value", style="green")
        table.add_row("Total Entries", str(stats["total_entries"]))
        table.add_row("Total Accesses", str(stats["total_accesses"]))
        table.add_row("Avg Accesses", str(stats["avg_accesses"]))
        table.add_row("Newest Entry", str(stats["newest_entry"]))
        table.add_row("Oldest Entry", str(stats["oldest_entry"]))
        console.print(table)

    elif action == "clear":
        confirm = console.input("[red]确定要清空所有缓存? (y/n): [/red]")
        if confirm.lower() == "y":
            deleted = cache_instance.clear()
            console.print(f"[green]已清空 {deleted} 条缓存[/green]")
        else:
            console.print("[yellow]已取消[/yellow]")

    elif action == "clean":
        deleted = cache_instance.cleanup_old(days)
        console.print(f"[green]已清理 {deleted} 条超过 {days} 天的缓存[/green]")

    else:
        console.print(f"[red]未知操作: {action}. 可用: stats, clear, clean[/red]")


if __name__ == "__main__":
    app()
