"""解析器抽象基类与统一输出结构。

所有 parser 输出 ParsedDocument，包含纯文本和按页信息。
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class PageInfo:
    """单页信息。"""
    page_num: Optional[int] # 1-based 页码（支持 None 表示无页码概念）
    text: str               # 该页文本


@dataclass
class ParsedDocument:
    """解析后的统一文档结构。"""
    text: str                                     # 全文拼接
    pages: list[PageInfo] = field(default_factory=list)  # 按页拆分（PDF 有，其他类型为单页）
    metadata: dict = field(default_factory=dict)  # 额外元信息（标题、段落数等）

    @property
    def page_count(self) -> int:
        return len(self.pages) if self.pages else 1


class BaseParser(ABC):
    """解析器抽象基类。"""

    @abstractmethod
    def parse(self, file_path: str) -> ParsedDocument:
        """解析文档，返回 ParsedDocument。"""
        ...


def merge_pages_to_text(pages: list[PageInfo]) -> str:
    """将多页文本拼接为全文，页与页之间用换行分隔。"""
    return "\n".join(p.text for p in pages)
