"""文本分块服务。

策略：按 token 数切分，支持 overlap，尽量在句末/段落边界切分。
"""
import re
from dataclasses import dataclass
from typing import Optional

from app.config import settings
from app.parsers.base import PageInfo
from app.utils.tokenizer_helper import count_tokens


@dataclass
class ChunkData:
    """切分后的 chunk 数据（入库前结构）。"""
    chunk_index: int
    content: str
    page_num: Optional[int] = None
    char_count: int = 0
    token_count: int = 0
    metadata: dict = None

    def __post_init__(self):
        if self.char_count == 0:
            self.char_count = len(self.content)
        if self.token_count == 0:
            self.token_count = count_tokens(self.content)
        if self.metadata is None:
            self.metadata = {}


class ChunkService:
    """文本分块服务。"""

    def __init__(
        self,
        chunk_size: int = settings.CHUNK_SIZE,
        overlap: int = settings.CHUNK_OVERLAP,
    ):
        self.chunk_size = chunk_size
        self.overlap = overlap

    def split(self, text: str, pages: list[PageInfo] | None = None) -> list[ChunkData]:
        """将文本切分为多个 chunk。

        若提供 pages（PDF），则尽量保留页码信息。
        """
        if not text or not text.strip():
            return []

        # 优先按段落切，再按 token 数组装
        paragraphs = self._split_paragraphs(text)
        chunks: list[ChunkData] = []
        current = ""
        current_tokens = 0
        idx = 0

        for para in paragraphs:
            para_tokens = count_tokens(para)

            # 单段就超长：硬切
            if para_tokens > self.chunk_size:
                if current:
                    chunks.append(self._make_chunk(idx, current, pages))
                    idx += 1
                    current = ""
                    current_tokens = 0
                for sub in self._hard_split(para):
                    chunks.append(self._make_chunk(idx, sub, pages))
                    idx += 1
                continue

            # 累加后超长：先保存当前，再开新块（带 overlap）
            if current_tokens + para_tokens > self.chunk_size:
                chunks.append(self._make_chunk(idx, current, pages))
                idx += 1
                # overlap：保留当前块末尾一部分
                current = self._take_overlap(current) + para
                current_tokens = count_tokens(current)
            else:
                current = (current + "\n" + para) if current else para
                current_tokens += para_tokens

        if current.strip():
            chunks.append(self._make_chunk(idx, current, pages))

        return chunks

    def _make_chunk(self, idx: int, content: str, pages: list[PageInfo] | None) -> ChunkData:
        page_num = self._guess_page_num(content, pages)
        return ChunkData(
            chunk_index=idx,
            content=content.strip(),
            page_num=page_num,
        )

    @staticmethod
    def _split_paragraphs(text: str) -> list[str]:
        """按空行分段，空段过滤。"""
        paras = re.split(r"\n\s*\n", text)
        return [p.strip() for p in paras if p.strip()]

    @staticmethod
    def _hard_split(text: str, chunk_size: int = settings.CHUNK_SIZE) -> list[str]:
        """对超长段落按句号硬切。"""
        sentences = re.split(r"(?<=[。！？.!?\n])", text)
        result: list[str] = []
        current = ""
        for s in sentences:
            if not s.strip():
                continue
            if count_tokens(current + s) > chunk_size and current:
                result.append(current.strip())
                current = s
            else:
                current += s
        if current.strip():
            result.append(current.strip())
        return result

    def _take_overlap(self, text: str) -> str:
        """取末尾 overlap 个 token 的文本。"""
        if self.overlap <= 0 or not text:
            return ""
        # 简单实现：取末尾若干字符
        char_overlap = self.overlap * 2  # 粗略：1 token ≈ 2 字符（中文）
        if len(text) <= char_overlap:
            return text
        return text[-char_overlap:]

    @staticmethod
    def _guess_page_num(content: str, pages: list[PageInfo] | None) -> Optional[int]:
        """根据内容猜测所属页码。

        策略：若只有一页，返回 1；多页时返回内容首字符所在页。
        此处用简化逻辑：单页文档返回 1，多页返回 None（更精确需基于偏移量）。
        """
        if not pages:
            return None
        if len(pages) == 1:
            return pages[0].page_num
        # 多页：取内容片段在 pages 中的首次出现页
        snippet = content[:50]
        for p in pages:
            if snippet in p.text:
                return p.page_num
        return pages[0].page_num
