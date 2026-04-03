"""OpenCLI 爬虫模块 - 处理 opencli:// 来源"""

import hashlib
import json
from typing import Optional
from urllib.parse import urlparse, parse_qs

from src.models import Document, DocFormat, SourceType


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
