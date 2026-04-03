"""OpenCLI 爬虫模块 - 处理 opencli:// 来源"""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
import tempfile
from pathlib import Path
from typing import Optional, TYPE_CHECKING
from urllib.parse import urlparse, parse_qs

from src.models import Document, DocFormat, SourceType

if TYPE_CHECKING:
    from src.crawler import CrawlResult


class OpenCLIError(Exception):
    """OpenCLI 执行错误"""

    def __init__(self, message: str, exit_code: int = 0):
        super().__init__(message)
        self.exit_code = exit_code


class OpenCLICrawler:
    """OpenCLI 爬虫 - 支持有限的内容型命令"""

    def __init__(self):
        # 白名单：site/command 模式
        self.whitelist = {
            "zhihu/download",
            "weixin/download",
            "xiaohongshu/note",
            "bilibili/subtitle",
        }

    def _parse_url(self, url: str) -> dict:
        """解析 opencli:// URL

        Args:
            url: opencli://site/command/arg?params 格式的 URL

        Returns:
            dict: {'site': str, 'command': str, 'arg': str|None, 'params': dict}
        """
        if not url.startswith("opencli://"):
            raise ValueError(f"Invalid opencli URL: {url}")

        # 去掉 opencli:// 前缀
        url_body = url[10:]  # len('opencli://') == 10

        # 使用标准 URL 解析
        parsed = urlparse(f"http://{url_body}")  # 用 http 做解析，实际 scheme 已处理

        site = parsed.hostname

        # 添加检查
        if not site:
            raise ValueError(f"Missing site in URL: {url}")

        path_parts = parsed.path.strip("/").split("/")

        if len(path_parts) < 1 or not path_parts[0]:
            raise ValueError(f"Missing command in URL: {url}")

        command = path_parts[0]
        arg = path_parts[1] if len(path_parts) > 1 else None

        # 解析查询参数
        params = parse_qs(parsed.query)

        return {"site": site, "command": command, "arg": arg, "params": params}

    def _check_whitelist(self, site: str, command: str, arg: Optional[str]) -> bool:
        """检查命令是否在白名单中

        Args:
            site: 站点名称
            command: 命令名称
            arg: 位置参数（用于判断是否需要 arg）

        Returns:
            bool: 是否在白名单中
        """
        key = f"{site}/{command}"
        return key in self.whitelist

    def _parse_stdout_content(self, site: str, command: str, data: dict) -> Document:
        """解析 stdout 输出的 JSON 数据为 Document

        Args:
            site: 站点名称
            command: 命令名称
            data: stdout 输出的 JSON 字典

        Returns:
            Document: 转换后的文档
        """
        doc_id = self._generate_id(f"{site}/{command}/{data.get('url', str(data))}")

        # 根据站点和命令提取标题和内容
        if site == "bilibili" and command == "subtitle":
            title = data.get("title", "Bilibili Subtitle")
            content = self._format_bilibili_subtitle(data)
        elif site == "xiaohongshu" and command == "note":
            title = data.get("title", "小红书笔记")
            content = data.get("content", "")
        else:
            title = data.get("title", f"{site} {command}")
            content = json.dumps(data, ensure_ascii=False, indent=2)

        return Document(
            id=doc_id,
            source_type=SourceType.OPENCLI,
            source_path=f"opencli://{site}/{command}",
            title=title,
            content=content,
            format=DocFormat.TEXT,
            metadata={
                "opencli_site": site,
                "opencli_command": command,
                "opencli_raw_output_type": "stdout",
                "opencli_data_keys": list(data.keys()),
            },
        )

    def _format_bilibili_subtitle(self, data: dict) -> str:
        """格式化 bilibili 字幕为可读文本"""
        subtitles = data.get("subtitles", [])
        if not subtitles:
            return data.get("title", "")

        lines = [data.get("title", ""), ""]
        for sub in subtitles:
            text = sub.get("text", "").strip()
            if text:
                lines.append(text)

        return "\n".join(lines)

    def _generate_id(self, source: str) -> str:
        """生成文档 ID"""
        return hashlib.sha256(source.encode()).hexdigest()[:16]

    def _parse_file_output(
        self, output_dir: str, site: str, command: str, params: dict
    ) -> Document:
        """解析文件产出型命令生成的文件

        Args:
            output_dir: 输出目录路径
            site: 站点名称
            command: 命令名称
            params: 命令参数

        Returns:
            Document: 转换后的文档

        Raises:
            OpenCLIError: 未找到生成的文件
        """
        output_path = Path(output_dir)

        # 查找 markdown 文件
        md_files = list(output_path.glob("*.md"))
        if not md_files:
            raise OpenCLIError("未找到导出文件，请检查 opencli 是否成功执行")

        # 取第一个 markdown 文件
        md_file = md_files[0]
        content = md_file.read_text(encoding="utf-8")

        # 提取标题（从第一行 # 开头的标题或文件名）
        title = self._extract_title_from_markdown(content) or md_file.stem

        doc_id = self._generate_id(str(md_file))

        # 获取原始 URL
        original_url = params.get("url", [""])[0] if "url" in params else ""

        return Document(
            id=doc_id,
            source_type=SourceType.OPENCLI,
            source_path=f"opencli://{site}/{command}",
            title=title,
            content=content,
            format=DocFormat.MARKDOWN,
            metadata={
                "opencli_site": site,
                "opencli_command": command,
                "opencli_raw_output_type": "file",
                "generated_file": str(md_file),
                "original_url": original_url,
            },
        )

    def _extract_title_from_markdown(self, content: str) -> str:
        """从 markdown 内容提取标题"""
        match = re.search(r"^#\s+(.+)$", content, re.MULTILINE)
        if match:
            return match.group(1).strip()
        return ""

    def _execute_command(self, cmd: list) -> str:
        """执行 opencli 命令

        Args:
            cmd: 命令参数列表

        Returns:
            str: stdout 输出

        Raises:
            OpenCLIError: 执行失败
        """
        try:
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=300  # 5分钟超时
            )
        except FileNotFoundError:
            raise OpenCLIError(
                "opencli 未安装。请运行: npm install -g @jackwener/opencli",
                exit_code=127,
            )
        except subprocess.TimeoutExpired:
            raise OpenCLIError("opencli 命令执行超时（5分钟）", exit_code=124)

        # 检查退出码
        if result.returncode != 0:
            error_msg = self._map_exit_code(result.returncode, result.stderr)
            raise OpenCLIError(error_msg, exit_code=result.returncode)

        return result.stdout

    def _map_exit_code(self, exit_code: int, stderr: str) -> str:
        """将退出码映射为清晰错误信息

        Args:
            exit_code: subprocess 退出码
            stderr: 标准错误输出

        Returns:
            str: 用户友好的错误信息
        """
        exit_code_messages = {
            2: "命令或参数不合法",
            69: "浏览器扩展未连接。请安装并启用 opencli Browser Bridge 扩展",
            77: "目标站点缺少登录态或认证失败。请先在浏览器中登录目标站点",
            78: "配置错误：缺少凭证或配置不正确",
            124: "命令执行超时",
            127: "opencli 未安装",
            130: "命令被中断",
        }

        if exit_code in exit_code_messages:
            return exit_code_messages[exit_code]

        # 通用错误
        return f"opencli 执行失败 (exit code {exit_code}): {stderr[:200]}"

    def crawl(self, url: str) -> "CrawlResult":
        """爬取 opencli:// 来源

        Args:
            url: opencli:// URL

        Returns:
            CrawlResult: 包含文档或错误信息
        """
        from src.crawler import CrawlResult

        result = CrawlResult(
            document=Document(
                id="",
                source_type=SourceType.OPENCLI,
                source_path=url,
            )
        )

        try:
            # 1. 解析 URL
            parsed = self._parse_url(url)
            site = parsed["site"]
            command = parsed["command"]
            arg = parsed["arg"]
            params = parsed["params"]

            # 2. 白名单校验
            if not self._check_whitelist(site, command, arg):
                raise OpenCLIError(
                    f"当前版本不支持 opencli://{site}/{command}。"
                    f'仅支持: {", ".join(sorted(self.whitelist))}'
                )

            # 3. 构建命令
            cmd = ["opencli", site, command]
            if arg:
                cmd.append(arg)

            # 添加命名参数
            for key, values in params.items():
                for value in values:
                    cmd.append(f"--{key}")
                    cmd.append(value)

            # 4. 判断输出类型并执行
            key = f"{site}/{command}"

            if key in ["xiaohongshu/note", "bilibili/subtitle"]:
                # stdout 内容型
                cmd.append("--format")
                cmd.append("json")

                stdout = self._execute_command(cmd)
                data = json.loads(stdout)

                doc = self._parse_stdout_content(site, command, data)
                result.document = doc

            elif key in ["zhihu/download", "weixin/download"]:
                # 文件产出型
                with tempfile.TemporaryDirectory() as tmpdir:
                    cmd.append("--output")
                    cmd.append(tmpdir)

                    self._execute_command(cmd)

                    doc = self._parse_file_output(tmpdir, site, command, params)
                    result.document = doc

        except OpenCLIError as e:
            if result.errors is None:
                result.errors = []
            result.errors.append(str(e))
            result.document.id = self._generate_id(url + str(e))
        except Exception as e:
            if result.errors is None:
                result.errors = []
            result.errors.append(f"未知错误: {str(e)}")
            result.document.id = self._generate_id(url + str(e))

        return result
