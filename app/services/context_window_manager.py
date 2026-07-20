"""Context Window 管理器。

根据 LLM 上下文窗口大小动态截断检索片段与历史对话，
避免超出模型 context window 导致 API 报错或"中间遗忘"。
"""
from typing import Optional

from app.config import settings
from app.core.logger import logger
from app.utils.tokenizer_helper import count_tokens, truncate_by_tokens


class ContextWindowManager:
    """上下文 token 预算管理。"""

    @staticmethod
    def truncate_candidates(
        candidates: list[dict],
        max_context_tokens: Optional[int] = None,
        reserve_for_prompt: int = 800,
    ) -> list[dict]:
        """按 rerank_score 由高到低累加，超预算时截断低分片段的内容。

        Args:
            candidates: 检索候选 [{content, rerank_score/score, ...}]
            max_context_tokens: Context 最大 token 数；None 则用 settings.CONTEXT_MAX_TOKENS
            reserve_for_prompt: 为 prompt 模板、问题、历史预留的 token 数

        Returns:
            截断后的候选列表（可能减少条数，或最后一条内容被截断）
        """
        if not candidates:
            return candidates

        budget = (max_context_tokens or settings.CONTEXT_MAX_TOKENS) - reserve_for_prompt
        if budget <= 0:
            budget = 500  # 兜底

        # 按 rerank_score 降序排列（高分优先保留）
        sorted_candidates = sorted(
            candidates,
            key=lambda c: c.get("rerank_score", c.get("score", 0)),
            reverse=True,
        )

        kept: list[dict] = []
        used_tokens = 0

        for c in sorted_candidates:
            content = c.get("content", "") or ""
            content_tokens = count_tokens(content)

            if used_tokens + content_tokens <= budget:
                # 完整保留
                kept.append(c)
                used_tokens += content_tokens
            else:
                # 剩余预算 > 200 token 才截断保留，否则丢弃
                remaining = budget - used_tokens
                if remaining > 200:
                    truncated_content = truncate_by_tokens(content, remaining)
                    truncated = dict(c)
                    truncated["content"] = truncated_content
                    # snippet 不变（仍展示原文前 200 字）
                    kept.append(truncated)
                    used_tokens = budget
                break  # 预算用尽

        if len(kept) < len(candidates):
            logger.info(
                f"Context 截断: {len(candidates)} -> {len(kept)} 片段, "
                f"used_tokens={used_tokens}/{budget + reserve_for_prompt}"
            )

        return kept

    @staticmethod
    def truncate_history(history_text: str, max_tokens: Optional[int] = None) -> str:
        """截断历史对话文本到预算内。"""
        budget = max_tokens or settings.HISTORY_MAX_TOKENS
        if not history_text:
            return ""
        if count_tokens(history_text) <= budget:
            return history_text
        # 保留末尾（最近对话更相关）
        truncated = truncate_by_tokens(history_text, budget)
        logger.info(f"历史对话截断: -> {count_tokens(truncated)} tokens")
        return truncated
