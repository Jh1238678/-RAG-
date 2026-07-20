"""Embedding 服务。

使用 sentence-transformers 加载 bge-small-zh，支持批量向量化。
"""
from typing import Optional

from app.config import settings
from app.core.logger import logger


class EmbeddingService:
    """向量化服务：将文本转为向量。"""

    _model = None  # 单例模型

    def __init__(self):
        # 不在构造时加载模型，改为首次 embed 时懒加载
        # 这样 health/documents 等不需要 embedding 的接口不会被阻塞
        pass

    @classmethod
    def _ensure_model(cls):
        """懒加载模型，全局共享。首次调用时才加载。"""
        if cls._model is None:
            logger.info(f"加载 Embedding 模型: {settings.EMBEDDING_MODEL}")
            from sentence_transformers import SentenceTransformer
            import numpy as np  # 确保 numpy 可用
            cls._model = SentenceTransformer(
                settings.EMBEDDING_MODEL,
                device=settings.EMBEDDING_DEVICE,
            )
            logger.info("Embedding 模型加载完成")

    def embed_batch(self, texts: list[str]):
        """批量向量化文本。返回 (n, dim) 的 float32 numpy 数组。"""
        import numpy as np
        if not texts:
            return np.array([], dtype=np.float32)
        self._ensure_model()  # 首次调用时加载模型
        vectors = self._model.encode(
            texts,
            batch_size=32,
            show_progress_bar=False,
            convert_to_numpy=True,
            normalize_embeddings=True,  # bge 推荐归一化，便于内积检索
        )
        return vectors.astype(np.float32)

    def embed_query(self, text: str):
        """单条 query 向量化。返回 (dim,) 一维数组。"""
        vec = self.embed_batch([text])
        return vec[0]

    @property
    def dimension(self) -> int:
        """向量维度。"""
        self._ensure_model()  # 首次调用时加载模型
        return self._model.get_sentence_embedding_dimension()
