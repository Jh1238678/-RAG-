"""语义缓存服务（Semantic Cache）。

基于内存 + 向量相似度匹配的问答缓存层。
当新问题与历史缓存问题的向量相似度 >= 阈值时，直接返回缓存的答案，
跳过检索与 LLM 调用，显著降低高频提问的延迟与成本。

特点：
- 进程内单例，LRU 淘汰
- 使用与主检索相同的 EmbeddingService，避免重复加载模型
- 仅缓存"正常回答"（拒答、verifier unsupported 不缓存）
- 线程安全（RLock 保护）
"""
import threading
import time
from collections import OrderedDict
from typing import Optional

from app.config import settings
from app.core.logger import logger


class _CacheEntry:
    """单条缓存。"""
    __slots__ = ("query", "query_vec", "response", "mode", "created_at", "hit_count")

    def __init__(self, query: str, query_vec: list[float], response: dict, mode: str):
        self.query = query
        self.query_vec = query_vec
        self.response = response
        self.mode = mode
        self.created_at = time.time()
        self.hit_count = 0


class SemanticCacheService:
    """语义缓存单例。"""

    _instance = None
    _instance_lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._instance_lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self._cache: OrderedDict[str, _CacheEntry] = OrderedDict()
        self._lock = threading.RLock()
        self._embedding_service = None  # 懒加载，与主检索共用模型
        logger.info(
            f"语义缓存初始化: max_size={settings.SEMANTIC_CACHE_MAX_SIZE}, "
            f"threshold={settings.SEMANTIC_CACHE_THRESHOLD}"
        )

    @property
    def embedding_service(self):
        """懒加载 embedding 服务。"""
        if self._embedding_service is None:
            from app.services.embedding_service import EmbeddingService
            self._embedding_service = EmbeddingService()
        return self._embedding_service

    def lookup(
        self,
        query: str,
        mode: str,
        document_ids: Optional[list[str]] = None,
    ) -> Optional[dict]:
        """查找语义缓存。

        Args:
            query: 用户问题
            mode: 问答模式（strict/open），不同模式不共享缓存
            document_ids: 文档范围（None 与空列表视为"全部"，可互通）

        Returns:
            命中时返回缓存的响应 dict（已深拷贝，调用方可安全修改）；
            未命中返回 None
        """
        if not settings.SEMANTIC_CACHE_ENABLED:
            return None
        if not query.strip():
            return None

        # 文档范围归一化为可比较的 key
        doc_key = self._doc_ids_key(document_ids)
        cache_key_scope = f"{mode}:{doc_key}"

        try:
            query_vec = self.embedding_service.embed_query(query)
        except Exception as e:
            logger.warning(f"语义缓存 embed 失败，跳过查找: {e}")
            return None

        threshold = settings.SEMANTIC_CACHE_THRESHOLD

        with self._lock:
            best_entry: Optional[_CacheEntry] = None
            best_score = 0.0

            for entry in self._cache.values():
                # 不同模式/不同文档范围不互通
                entry_scope = f"{entry.mode}:{self._doc_ids_key_from_response(entry.response)}"
                if entry_scope != cache_key_scope:
                    continue
                score = self._cosine(query_vec, entry.query_vec)
                if score > best_score:
                    best_score = score
                    best_entry = entry

            if best_entry is not None and best_score >= threshold:
                best_entry.hit_count += 1
                import copy
                cached = copy.deepcopy(best_entry.response)
                # 标记为缓存命中
                cached["from_cache"] = True
                cached["cache_score"] = round(best_score, 4)
                logger.info(
                    f"语义缓存命中: query='{query[:30]}...', score={best_score:.4f}, "
                    f"hit_count={best_entry.hit_count}"
                )
                return cached

        return None

    def store(
        self,
        query: str,
        response: dict,
        mode: str,
        document_ids: Optional[list[str]] = None,
    ) -> None:
        """存入语义缓存。

        仅缓存"值得复用"的响应：有答案、未拒答、verifier 非 unsupported。
        """
        if not settings.SEMANTIC_CACHE_ENABLED:
            return
        if not query.strip():
            return

        # 过滤不值得缓存的响应
        answer = (response.get("answer") or "").strip()
        if not answer:
            return
        # 严格模式拒答不缓存
        if response.get("grounded") is False and response.get("unsupported_reason"):
            return
        # verifier 判定为 unsupported 不缓存
        vr = response.get("verifier_result")
        if isinstance(vr, dict) and vr.get("verdict") == "unsupported":
            return

        try:
            query_vec = self.embedding_service.embed_query(query)
        except Exception as e:
            logger.warning(f"语义缓存 embed 失败，跳过存储: {e}")
            return

        # 把文档范围信息附在 response 副本里（用于查找时比对 scope）
        import copy
        response_copy = copy.deepcopy(response)
        response_copy["_cache_doc_ids"] = self._doc_ids_key(document_ids)

        entry = _CacheEntry(query=query, query_vec=query_vec, response=response_copy, mode=mode)
        cache_key = f"{mode}:{self._doc_ids_key(document_ids)}:{query}"

        with self._lock:
            # LRU：超容量时淘汰最旧
            while len(self._cache) >= settings.SEMANTIC_CACHE_MAX_SIZE:
                self._cache.popitem(last=False)
            self._cache[cache_key] = entry
            logger.debug(f"语义缓存存入: query='{query[:30]}...', size={len(self._cache)}")

    def clear(self) -> int:
        """清空缓存，返回清空的条目数。"""
        with self._lock:
            n = len(self._cache)
            self._cache.clear()
            logger.info(f"语义缓存已清空: {n} 条")
            return n

    def stats(self) -> dict:
        """返回缓存统计。"""
        with self._lock:
            return {
                "size": len(self._cache),
                "max_size": settings.SEMANTIC_CACHE_MAX_SIZE,
                "threshold": settings.SEMANTIC_CACHE_THRESHOLD,
                "enabled": settings.SEMANTIC_CACHE_ENABLED,
            }

    # ============ 私有方法 ============

    @staticmethod
    def _doc_ids_key(document_ids: Optional[list[str]]) -> str:
        """文档范围归一化为可比较字符串。"""
        if not document_ids:
            return "all"
        return ",".join(sorted(document_ids))

    @staticmethod
    def _doc_ids_key_from_response(response: dict) -> str:
        """从缓存的 response 提取文档范围 key。"""
        return response.get("_cache_doc_ids", "all")

    @staticmethod
    def _cosine(a, b) -> float:
        """计算余弦相似度。a/b 可能为 list 或 numpy array。"""
        import math
        # 转为 list 以便统一处理（numpy array 不能直接 bool 判断）
        try:
            a_list = list(a) if a is not None else []
            b_list = list(b) if b is not None else []
        except TypeError:
            return 0.0
        if not a_list or not b_list or len(a_list) != len(b_list):
            return 0.0
        dot = sum(x * y for x, y in zip(a_list, b_list))
        norm_a = math.sqrt(sum(x * x for x in a_list))
        norm_b = math.sqrt(sum(y * y for y in b_list))
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return dot / (norm_a * norm_b)
