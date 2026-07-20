"""摘要服务。

支持短文档单次摘要、长文档 map-reduce 分段摘要。
"""
import json
from typing import Optional

from sqlalchemy.orm import Session

from app.config import settings
from app.core.logger import logger
from app.prompts.summary_prompt import build_summary_prompt, build_reduce_prompt
from app.repositories.document_repo import ChunkRepo, DocumentRepo
from app.services.llm_service import LLMService
from app.utils.tokenizer_helper import count_tokens, truncate_by_tokens


# 单段摘要的最大输入 token
MAX_SEGMENT_TOKENS = 3000
# 触发分段摘要的阈值
SEGMENT_THRESHOLD = 4000


class SummaryService:
    """文档摘要服务。"""

    def __init__(self, db: Session):
        self.db = db
        self.doc_repo = DocumentRepo(db)
        self.chunk_repo = ChunkRepo(db)
        self.llm = LLMService()

    def generate(self, document_id: str) -> dict:
        """生成文档摘要。返回 {document_id, summary, segment_count}。"""
        document = self.doc_repo.get_by_id(document_id)
        if not document:
            from app.core.exceptions import DocumentNotFoundError
            raise DocumentNotFoundError(document_id)

        # 拼接全文
        chunks = self.chunk_repo.list_by_document(document_id)
        if not chunks:
            return {"document_id": document_id, "summary": "文档无内容", "segment_count": 0}

        full_text = "\n".join(c.content for c in chunks)
        total_tokens = count_tokens(full_text)
        logger.info(f"生成摘要: doc={document_id}, tokens={total_tokens}")

        if total_tokens <= SEGMENT_THRESHOLD:
            # 单次摘要
            prompt = build_summary_prompt(full_text)
            summary = self.llm.generate_summary(prompt)
            segment_count = 1
        else:
            # map-reduce 分段摘要
            segments = self._split_segments(full_text)
            logger.info(f"分段摘要: {len(segments)} 段")

            # map：每段单独摘要
            partial_summaries = []
            for i, seg in enumerate(segments):
                prompt = build_summary_prompt(seg)
                partial = self.llm.generate_summary(prompt)
                partial_summaries.append(partial)

            # reduce：合并
            combined = "\n\n".join(partial_summaries)
            reduce_prompt = build_reduce_prompt(combined)
            summary = self.llm.generate_summary(reduce_prompt)
            segment_count = len(segments)

        # 持久化
        self.doc_repo.update_status(document_id, document.status, summary=summary)
        logger.info(f"摘要生成完成: doc={document_id}, segments={segment_count}")

        return {
            "document_id": document_id,
            "summary": summary,
            "segment_count": segment_count,
        }

    @staticmethod
    def _split_segments(text: str) -> list[str]:
        """按 token 数切分文本为多段。"""
        # 按段落切
        import re
        paragraphs = re.split(r"\n\s*\n", text)
        segments = []
        current = ""
        for para in paragraphs:
            if count_tokens(current + para) > MAX_SEGMENT_TOKENS and current:
                segments.append(current.strip())
                current = para
            else:
                current = (current + "\n\n" + para) if current else para
        if current.strip():
            segments.append(current.strip())
        return segments
