"""Rerank 重排服务。

使用 bge-reranker-base 对候选 chunk 二次排序。
"""
from typing import Optional

from app.config import settings
from app.core.logger import logger


class RerankService:
    """重排服务：基于交叉编码器对 query-chunk 对打分。"""

    _model = None  # 单例

    def __init__(self):
        # 不在构造时加载模型，改为首次 rerank 时懒加载
        # 这样不需要 rerank 的接口不会被阻塞
        pass

    @classmethod
    def _ensure_model(cls):
        if cls._model is None:
            logger.info(f"加载 Rerank 模型: {settings.RERANK_MODEL}")
            # 使用 sentence_transformers.CrossEncoder 替代 FlagEmbedding.FlagReranker。
            # 原因：FlagReranker 依赖 transformers 旧版 tokenizer 的 prepare_for_model 方法，
            # 该方法在 transformers 5.x 已被移除，导致 AttributeError。
            # CrossEncoder 接口稳定、维护活跃，且 bge-reranker-base 本身即兼容 CrossEncoder。
            from sentence_transformers import CrossEncoder
            cls._model = CrossEncoder(
                settings.RERANK_MODEL,
                max_length=512,
            )
            logger.info("Rerank 模型加载完成")

    def rerank(
        self,
        query: str,
        candidates: list[dict],
        top_n: int = 5,
    ) -> list[dict]:
        """对候选列表重排。

        candidates: [{chunk_id, content, ...}]，至少包含 content 字段
        返回 top_n 个候选，附带 rerank_score 字段。
        """
        if not candidates or not settings.RERANK_ENABLED:
            return candidates[:top_n]

        self._ensure_model()  # 首次调用时加载模型

        pairs = [[query, c["content"]] for c in candidates]
        # CrossEncoder.predict 返回 logits；对分数做 softmax 归一化以接近原 FlagReranker 的 normalize 行为
        import numpy as np
        raw_scores = self._model.predict(pairs, convert_to_numpy=True)
        # sigmoid 归一化到 (0,1)，语义稳定且无需关心类别数
        scores = 1.0 / (1.0 + np.exp(-np.asarray(raw_scores, dtype=np.float64)))

        # 归一化得分后排序
        for c, s in zip(candidates, scores):
            c["rerank_score"] = float(s)
        candidates.sort(key=lambda x: x["rerank_score"], reverse=True)
        return candidates[:top_n]
