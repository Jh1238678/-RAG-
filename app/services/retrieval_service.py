"""检索服务。

编排向量检索 + rerank，返回最终引用 chunk。
支持增强检索：Multi-Query Retrieval（多查询并集）和 HyDE（假设性文档检索）。
"""
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.core.logger import logger
from app.models.entities import Chunk, Document
from app.repositories.document_repo import ChunkRepo
from app.repositories.index_repo import IndexRepo
from app.services.embedding_service import EmbeddingService
from app.services.rerank_service import RerankService
from app.services.vector_service import VectorService
from app.utils.text_cleaner import truncate_for_display


class RetrievalService:
    """检索服务：query -> 向量检索 -> rerank -> 引用 chunk。"""

    def __init__(self, db: Session):
        self.db = db
        self.chunk_repo = ChunkRepo(db)
        self.index_repo = IndexRepo(db)
        self.embedding_service = EmbeddingService()
        self.vector_service = VectorService()
        self.rerank_service = RerankService()
        # LLM 客户端懒加载（避免无增强检索时也初始化）
        self._llm = None

    @property
    def llm(self):
        """懒加载 LLM 服务，仅在多路召回/HyDE 时使用。"""
        if self._llm is None:
            from app.services.llm_service import LLMService
            self._llm = LLMService()
        return self._llm

    def retrieve(
        self,
        query: str,
        document_ids: Optional[list[str]] = None,
        top_k: int = settings.TOP_K_CANDIDATES,
        top_n: int = settings.TOP_N_FINAL,
        similarity_threshold: float = settings.SIMILARITY_THRESHOLD,
        enable_multi_query: Optional[bool] = None,
        enable_hyde: Optional[bool] = None,
    ) -> list[dict]:
        """检索相关 chunk。

        Args:
            query: 检索 query
            document_ids: 限定文档范围
            top_k: 向量检索候选数
            top_n: rerank 后保留数
            similarity_threshold: 相似度阈值
            enable_multi_query: 是否启用多路召回；None 则按配置
            enable_hyde: 是否启用 HyDE；None 则按配置

        返回 [{chunk_id, document_id, document_name, page_num, content, snippet, score}]。
        """
        use_multi = settings.MULTI_QUERY_ENABLED if enable_multi_query is None else enable_multi_query
        use_hyde = settings.HYDE_ENABLED if enable_hyde is None else enable_hyde

        # HyDE：用假设性文档 embedding 检索
        hyde_query = None
        if use_hyde:
            hyde_query = self._try_hyde(query)
            if hyde_query:
                logger.info(f"HyDE 生效，使用假设性文档检索")

        # Multi-Query：生成多个变种问题，并集检索
        extra_queries: list[str] = []
        if use_multi:
            extra_queries = self._try_multi_query(query)

        all_queries = [query] + extra_queries
        if hyde_query:
            all_queries.append(hyde_query)

        # 去重
        seen = set()
        unique_queries = []
        for q in all_queries:
            if q and q not in seen:
                seen.add(q)
                unique_queries.append(q)

        # 多路并集检索
        if len(unique_queries) > 1:
            candidates = self._retrieve_multi(
                unique_queries,
                document_ids=document_ids,
                top_k=top_k,
                similarity_threshold=similarity_threshold,
            )
        else:
            candidates = self._retrieve_single(
                unique_queries[0] if unique_queries else query,
                document_ids=document_ids,
                top_k=top_k,
                similarity_threshold=similarity_threshold,
            )

        if not candidates:
            return []

        # Rerank 重排（用原始 query 作为 rerank 输入，保证语义一致性）
        if settings.RERANK_ENABLED and len(candidates) > 1:
            candidates = self.rerank_service.rerank(query, candidates, top_n=top_n)
        else:
            # 多路召回时去重后按最高分排序
            candidates = self._dedup_and_sort(candidates, top_n)

        logger.info(
            f"检索完成: query='{query[:30]}...', queries={len(unique_queries)}, "
            f"候选={len(candidates)}, 最终={len(candidates)}"
        )
        return candidates

    # ============ 增强检索方法 ============

    def _try_multi_query(self, query: str) -> list[str]:
        """尝试生成多变种问题，失败时返回空列表。"""
        try:
            from app.prompts.multi_query_prompt import build_multi_query_prompt
            prompt = build_multi_query_prompt(query, settings.MULTI_QUERY_COUNT)
            variants = self.llm.generate_multi_queries(prompt, settings.MULTI_QUERY_COUNT)
            logger.info(f"Multi-Query 生成 {len(variants)} 个变种: {variants}")
            return variants
        except Exception as e:
            logger.warning(f"Multi-Query 生成失败，跳过: {e}")
            return []

    def _try_hyde(self, query: str) -> Optional[str]:
        """尝试生成 HyDE 假设性文档，失败时返回 None。"""
        try:
            from app.prompts.hyde_prompt import build_hyde_prompt
            prompt = build_hyde_prompt(query)
            hyde_doc = self.llm.generate_hyde_document(prompt)
            if hyde_doc and len(hyde_doc) > 20:
                return hyde_doc
            return None
        except Exception as e:
            logger.warning(f"HyDE 生成失败，跳过: {e}")
            return None

    def _retrieve_single(
        self,
        query: str,
        document_ids: Optional[list[str]] = None,
        top_k: int = settings.TOP_K_CANDIDATES,
        similarity_threshold: float = settings.SIMILARITY_THRESHOLD,
    ) -> list[dict]:
        """单路检索。"""
        query_vec = self.embedding_service.embed_query(query)
        allowed_faiss_ids = self._get_allowed_faiss_ids(document_ids)
        if document_ids and not allowed_faiss_ids:
            return []

        hits = self.vector_service.search(query_vec, top_k=top_k, allowed_faiss_ids=allowed_faiss_ids)
        if not hits:
            return []

        hits = [(fid, s) for fid, s in hits if s >= similarity_threshold]
        if not hits:
            return []

        return self._build_candidates(hits)

    def _retrieve_multi(
        self,
        queries: list[str],
        document_ids: Optional[list[str]] = None,
        top_k: int = settings.TOP_K_CANDIDATES,
        similarity_threshold: float = settings.SIMILARITY_THRESHOLD,
    ) -> list[dict]:
        """多路并集检索，按 chunk_id 去重，保留每条 chunk 的最高分。"""
        allowed_faiss_ids = self._get_allowed_faiss_ids(document_ids)
        if document_ids and not allowed_faiss_ids:
            return []

        chunk_id_to_best: dict[str, tuple[str, float]] = {}  # chunk_id -> (faiss_id, max_score)

        for q in queries:
            try:
                q_vec = self.embedding_service.embed_query(q)
                hits = self.vector_service.search(q_vec, top_k=top_k, allowed_faiss_ids=allowed_faiss_ids)
                if not hits:
                    continue
                for fid, score in hits:
                    if score < similarity_threshold:
                        continue
                    cid = self.index_repo.get_chunk_id_by_faiss_id(fid)
                    if not cid:
                        continue
                    if cid not in chunk_id_to_best or score > chunk_id_to_best[cid][1]:
                        chunk_id_to_best[cid] = (fid, score)
            except Exception as e:
                logger.warning(f"多路检索 query='{q[:30]}' 失败: {e}")
                continue

        if not chunk_id_to_best:
            return []

        hits = [(v[0], v[1]) for v in chunk_id_to_best.values()]
        return self._build_candidates(hits)

    def _get_allowed_faiss_ids(self, document_ids: Optional[list[str]]) -> Optional[list[int]]:
        """根据文档范围获取允许的 faiss id 列表。"""
        if not document_ids:
            return None
        allowed = []
        for did in document_ids:
            allowed.extend(self.index_repo.get_faiss_ids_by_document(did))
        return allowed if allowed else None

    def _build_candidates(self, hits: list[tuple[int, float]]) -> list[dict]:
        """从 (faiss_id, score) 构建候选 dict 列表。"""
        if not hits:
            return []

        chunk_ids = []
        faiss_id_to_score = {}
        for fid, score in hits:
            cid = self.index_repo.get_chunk_id_by_faiss_id(fid)
            if cid:
                chunk_ids.append(cid)
                faiss_id_to_score[cid] = score

        chunks = self.chunk_repo.get_by_ids(chunk_ids)
        if not chunks:
            return []

        doc_id_to_name = self._get_doc_names([c.document_id for c in chunks])

        candidates = []
        for c in chunks:
            candidates.append({
                "chunk_id": c.id,
                "document_id": c.document_id,
                "document_name": doc_id_to_name.get(c.document_id, "未知"),
                "page_num": c.page_num,
                "content": c.content,
                "snippet": truncate_for_display(c.content, 200),
                "score": faiss_id_to_score.get(c.id, 0.0),
            })
        return candidates

    @staticmethod
    def _dedup_and_sort(candidates: list[dict], top_n: int) -> list[dict]:
        """关闭 rerank 时的去重与排序。"""
        seen = set()
        unique = []
        for c in candidates:
            cid = c["chunk_id"]
            if cid not in seen:
                seen.add(cid)
                unique.append(c)
        unique.sort(key=lambda x: x.get("rerank_score", x.get("score", 0)), reverse=True)
        return unique[:top_n]

    def _get_doc_names(self, document_ids: list[str]) -> dict[str, str]:
        """批量获取文档名。"""
        from app.models.entities import Document
        stmt = select(Document).where(Document.id.in_(document_ids))
        docs = list(self.db.execute(stmt).scalars().all())
        return {d.id: d.file_name for d in docs}
