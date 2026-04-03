"""OpenCLI 爬虫模块 - 处理 opencli:// 来源"""

from dataclasses import dataclass
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse, parse_qs
import subprocess
import tempfile
import json

from src.models import Document, SourceType, DocFormat


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
