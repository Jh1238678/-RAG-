"""向量检索服务。

使用 FAISS IndexIDMap2 包装 IndexFlatIP（内积，配合归一化向量等价于余弦相似度）。
支持增删查、持久化、按文档过滤检索。
"""
import os
from pathlib import Path
from typing import Optional

from app.config import settings
from app.core.logger import logger
from app.repositories.index_repo import IndexRepo
from app.db.session import SessionLocal


class VectorService:
    """FAISS 向量索引管理。"""

    _index = None  # faiss.IndexIDMap2
    _dimension: Optional[int] = None

    def __init__(self):
        self.index_dir = Path(settings.FAISS_INDEX_DIR)
        self.index_dir.mkdir(parents=True, exist_ok=True)
        self.index_path = self.index_dir / "faiss.index"
        # 不在构造时加载索引，改为首次使用时懒加载
        # 这样 health 检查等不需要索引的接口不会被阻塞

    @classmethod
    def _ensure_index(cls):
        """加载或创建 FAISS 索引。首次使用时才调用。"""
        if cls._index is not None:
            return

        import faiss
        index_path = Path(settings.FAISS_INDEX_DIR) / "faiss.index"
        if index_path.exists():
            logger.info(f"加载已有 FAISS 索引: {index_path}")
            cls._index = faiss.read_index(str(index_path))
            cls._dimension = cls._index.d
            logger.info(f"FAISS 索引加载完成，维度={cls._dimension}, 向量数={cls._index.ntotal}")
        else:
            # 维度由 embedding 模型决定，首次需通过 embedding_service 获取
            from app.services.embedding_service import EmbeddingService
            dim = EmbeddingService().dimension
            cls._dimension = dim
            base = faiss.IndexFlatIP(dim)
            cls._index = faiss.IndexIDMap2(base)
            logger.info(f"创建新 FAISS 索引，维度={dim}")

    def add(self, vectors, faiss_ids: list[int]) -> None:
        """添加向量。vectors: (n, dim) numpy, faiss_ids: 长度 n 的 int64 列表。"""
        import numpy as np
        if len(vectors) == 0:
            return
        self._ensure_index()
        ids = np.array(faiss_ids, dtype=np.int64)
        self._index.add_with_ids(vectors, ids)
        self._save()

    def search(
        self,
        query_vec,
        top_k: int = 10,
        allowed_faiss_ids: Optional[list[int]] = None,
    ) -> list[tuple[int, float]]:
        """检索 top-k 最相似向量。

        返回 [(faiss_id, score), ...]，按相似度降序。
        若指定 allowed_faiss_ids，则只在这些向量中检索。
        """
        import numpy as np
        self._ensure_index()  # 确保索引已加载
        if self._index is None or self._index.ntotal == 0:
            return []

        vec = query_vec.reshape(1, -1).astype(np.float32)
        k = min(top_k, self._index.ntotal)
        scores, ids = self._index.search(vec, k)

        results = []
        for faiss_id, score in zip(ids[0], scores[0]):
            if faiss_id < 0:
                continue
            if allowed_faiss_ids is not None and faiss_id not in allowed_faiss_ids:
                continue
            results.append((int(faiss_id), float(score)))
        return results

    def remove_ids(self, faiss_ids: list[int]) -> None:
        """按 ID 删除向量。IndexIDMap2 支持 remove_ids。"""
        import numpy as np
        import faiss
        if not faiss_ids:
            return
        self._ensure_index()
        ids = np.array(faiss_ids, dtype=np.int64)
        selector = faiss.IDSelectorBatch(ids)
        removed = self._index.remove_ids(selector)
        logger.info(f"FAISS 删除 {removed} 个向量")
        self._save()

    def _save(self) -> None:
        """持久化索引到磁盘。"""
        import faiss
        faiss.write_index(self._index, str(self.index_path))

    @property
    def total(self) -> int:
        return self._index.ntotal if self._index else 0

    @property
    def is_loaded(self) -> bool:
        return self._index is not None

    def rebuild(self, vectors, faiss_ids: list[int]) -> None:
        """全量重建索引。"""
        import faiss
        self._ensure_index()
        base = faiss.IndexFlatIP(self._dimension)
        self._index = faiss.IndexIDMap2(base)
        if len(vectors) > 0:
            self.add(vectors, faiss_ids)
        logger.info(f"FAISS 索引重建完成，共 {self._index.ntotal} 个向量")

    def next_faiss_id(self) -> int:
        """分配下一个可用的 faiss_id。从 index_mapping 表查最大值 +1。"""
        db = SessionLocal()
        try:
            repo = IndexRepo(db)
            return repo.get_max_faiss_id() + 1
        finally:
            db.close()
