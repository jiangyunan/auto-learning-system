"""数据模型定义"""
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional
from pathlib import Path


class SourceType(Enum):
    """文档来源类型"""
    URL = "url"
    LOCAL_FILE = "local_file"
    PDF = "pdf"


class DocFormat(Enum):
    """文档格式"""
    MARKDOWN = "markdown"
    HTML = "html"
    PDF = "pdf"
    TEXT = "text"


@dataclass
class ImageInfo:
    """图片信息"""
    original_url: Optional[str] = None  # 原始URL（如果是网络图片）
    local_path: Optional[Path] = None   # 本地存储路径
    alt_text: Optional[str] = None      # 替代文本


@dataclass
class Document:
    """源文档"""
    id: str                             # 唯一标识（URL的hash或文件路径的hash）
    source_type: SourceType             # 来源类型
    source_path: str                    # 原始路径（URL或文件路径）
    title: str = ""                     # 文档标题
    content: str = ""                   # 原始内容
    format: DocFormat = DocFormat.TEXT  # 文档格式
    images: list[ImageInfo] = field(default_factory=list)  # 图片列表
    fetched_at: datetime = field(default_factory=datetime.now)  # 获取时间
    metadata: dict = field(default_factory=dict)  # 额外元数据


@dataclass
class Chunk:
    """文本分块"""
    id: str                             # 唯一标识
    document_id: str                    # 所属文档ID
    index: int                          # 在文档中的顺序索引
    content: str                        # 分块内容
    start_pos: int = 0                  # 在原文档中的起始位置
    end_pos: int = 0                    # 在原文档中的结束位置
    token_count: int = 0                # 预估token数
    metadata: dict = field(default_factory=dict)  # 额外元数据


@dataclass
class SummaryL1:
    """L1级摘要：内容压缩为 bullet points"""
    bullets: list[str] = field(default_factory=list)  # 要点列表
    key_concepts: list[str] = field(default_factory=list)  # 关键概念


@dataclass
class SummaryL2:
    """L2级摘要：中文学习笔记"""
    overview: str = ""                  # 内容概述
    key_points: list[str] = field(default_factory=list)  # 核心要点
    concepts_explained: list[dict] = field(default_factory=list)  # 概念解释
    code_examples: list[dict] = field(default_factory=list)  # 代码示例
    related_topics: list[str] = field(default_factory=list)  # 相关主题


@dataclass
class ProcessResult:
    """文档处理结果"""
    document_id: str                    # 文档ID
    document_title: str = ""            # 文档标题
    source_url: Optional[str] = None    # 来源URL
    chunks_count: int = 0               # 分块数量
    l1_summary: SummaryL1 = field(default_factory=SummaryL1)  # L1摘要
    l2_summary: SummaryL2 = field(default_factory=SummaryL2)  # L2摘要
    generated_at: datetime = field(default_factory=datetime.now)  # 生成时间
    output_path: Optional[Path] = None  # 输出文件路径


@dataclass
class CacheEntry:
    """缓存条目"""
    content_hash: str                   # 内容哈希（SHA256）
    result_json: str                    # 结果JSON字符串
    created_at: datetime = field(default_factory=datetime.now)  # 创建时间
    accessed_at: datetime = field(default_factory=datetime.now)  # 最后访问时间
    access_count: int = 0               # 访问次数
