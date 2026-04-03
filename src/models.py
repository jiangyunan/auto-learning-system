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
    OPENCLI = "opencli"


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
    local_path: Optional[Path] = None  # 本地存储路径
    alt_text: Optional[str] = None  # 替代文本


@dataclass
class Document:
    """源文档"""

    id: str  # 唯一标识（URL的hash或文件路径的hash）
    source_type: SourceType  # 来源类型
    source_path: str  # 原始路径（URL或文件路径）
    title: str = ""  # 文档标题
    content: str = ""  # 原始内容
    format: DocFormat = DocFormat.TEXT  # 文档格式
    images: list[ImageInfo] = field(default_factory=list)  # 图片列表
    fetched_at: datetime = field(default_factory=datetime.now)  # 获取时间
    metadata: dict = field(default_factory=dict)  # 额外元数据


@dataclass
class Chunk:
    """文本分块"""

    id: str  # 唯一标识
    document_id: str  # 所属文档ID
    index: int  # 在文档中的顺序索引
    content: str  # 分块内容
    start_pos: int = 0  # 在原文档中的起始位置
    end_pos: int = 0  # 在原文档中的结束位置
    token_count: int = 0  # 预估token数
    metadata: dict = field(default_factory=dict)  # 额外元数据


@dataclass
class SummaryL1:
    """L1级摘要：内容压缩为 bullet points"""

    bullets: list[str] = field(default_factory=list)  # 要点列表
    key_concepts: list[str] = field(default_factory=list)  # 关键概念


@dataclass
class SummaryL2:
    """L2级摘要：中文学习笔记"""

    overview: str = ""  # 内容概述
    key_points: list[str] = field(default_factory=list)  # 核心要点
    concepts_explained: list[dict] = field(default_factory=list)  # 概念解释
    code_examples: list[dict] = field(default_factory=list)  # 代码示例
    related_topics: list[str] = field(default_factory=list)  # 相关主题


@dataclass
class ProcessResult:
    """文档处理结果"""

    document_id: str  # 文档ID
    document_title: str = ""  # 文档标题
    source_url: Optional[str] = None  # 来源URL
    chunks_count: int = 0  # 分块数量
    l1_summary: SummaryL1 = field(default_factory=SummaryL1)  # L1摘要
    l2_summary: SummaryL2 = field(default_factory=SummaryL2)  # L2摘要
    original_content: str = ""  # 原始内容
    generated_at: datetime = field(default_factory=datetime.now)  # 生成时间
    output_path: Optional[Path] = None  # 输出文件路径


@dataclass
class CacheEntry:
    """缓存条目"""

    content_hash: str  # 内容哈希（SHA256）
    result_json: str  # 结果JSON字符串
    created_at: datetime = field(default_factory=datetime.now)  # 创建时间
    accessed_at: datetime = field(default_factory=datetime.now)  # 最后访问时间
    access_count: int = 0  # 访问次数


@dataclass
class Link:
    """文档链接"""

    source_doc_id: str  # 源文档ID
    target_path: str  # 目标路径（可以是文件名、相对路径或URL）
    link_text: str  # 链接显示文本
    link_type: str  # 链接类型：wiki, markdown, url
    line_number: int = 0  # 所在行号


@dataclass
class DocumentGraph:
    """文档关系图 - 表示文件夹内Markdown文件的链接关系"""

    root_path: Path  # 根文件夹路径
    documents: dict[str, Document] = field(default_factory=dict)  # 文档ID -> 文档
    links: list[Link] = field(default_factory=list)  # 所有链接
    incoming_links: dict[str, list[str]] = field(
        default_factory=dict
    )  # doc_id -> [source_doc_ids]
    outgoing_links: dict[str, list[str]] = field(
        default_factory=dict
    )  # doc_id -> [target_doc_ids]

    def add_document(self, doc: Document) -> None:
        """添加文档到图"""
        self.documents[doc.id] = doc
        if doc.id not in self.incoming_links:
            self.incoming_links[doc.id] = []
        if doc.id not in self.outgoing_links:
            self.outgoing_links[doc.id] = []

    def add_link(self, link: Link) -> None:
        """添加链接到图"""
        self.links.append(link)

        # 更新出链
        if link.source_doc_id not in self.outgoing_links:
            self.outgoing_links[link.source_doc_id] = []
        self.outgoing_links[link.source_doc_id].append(link.target_path)

        # 尝试解析目标文档ID并更新入链
        target_doc = self._resolve_target(link.target_path)
        if target_doc:
            if target_doc.id not in self.incoming_links:
                self.incoming_links[target_doc.id] = []
            self.incoming_links[target_doc.id].append(link.source_doc_id)

    def _resolve_target(self, target_path: str) -> Document | None:
        """解析目标路径为文档"""
        # 尝试各种匹配方式
        for doc in self.documents.values():
            doc_path = Path(doc.source_path)
            # 完全匹配文件名
            if doc_path.name == target_path or doc_path.stem == target_path:
                return doc
            # 匹配不带扩展名
            if target_path.endswith(".md") and doc_path.stem == target_path[:-3]:
                return doc
        return None

    def get_processing_order(self) -> list[str]:
        """
        获取文档处理顺序
        按拓扑排序，确保被链接的文档先处理
        返回文档ID列表
        """
        # 简单的拓扑排序实现
        # 优先处理被引用次数多的文档（核心文档）
        doc_scores = {}
        for doc_id in self.documents:
            # 被引用次数越高，优先级越高
            incoming = len(self.incoming_links.get(doc_id, []))
            # 引用他人次数越高，优先级越低（依赖越多）
            outgoing = len(self.outgoing_links.get(doc_id, []))
            doc_scores[doc_id] = incoming * 2 - outgoing

        # 按分数降序排序
        return sorted(doc_scores.keys(), key=lambda x: doc_scores[x], reverse=True)

    def get_related_documents(self, doc_id: str) -> list[str]:
        """获取与指定文档相关的文档ID列表"""
        related = set()
        # 出链
        for target in self.outgoing_links.get(doc_id, []):
            target_doc = self._resolve_target(target)
            if target_doc:
                related.add(target_doc.id)
        # 入链
        for source_id in self.incoming_links.get(doc_id, []):
            related.add(source_id)
        return list(related)

    def get_statistics(self) -> dict:
        """获取图的统计信息"""
        return {
            "total_documents": len(self.documents),
            "total_links": len(self.links),
            "wiki_links": len(
                [link for link in self.links if link.link_type == "wiki"]
            ),
            "markdown_links": len(
                [link for link in self.links if link.link_type == "markdown"]
            ),
            "broken_links": len(
                [
                    link
                    for link in self.links
                    if not self._resolve_target(link.target_path)
                ]
            ),
        }
