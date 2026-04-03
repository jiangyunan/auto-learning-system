"""OpenCLI 爬虫模块 - 处理 opencli:// 来源"""

from typing import Optional
from urllib.parse import urlparse, parse_qs


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
        path_parts = parsed.path.strip("/").split("/")

        if len(path_parts) < 1:
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
