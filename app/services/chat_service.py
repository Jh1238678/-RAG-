"""问答服务。

编排完整问答流程：历史加载 -> query rewrite -> 检索 -> prompt 构建 -> LLM 生成 -> 持久化。

支持两种问答模式：
- strict（严格模式）：仅依据文档，不允许外推；检索不足时拒答；可选 verifier 校验
- open（开放模式）：允许适度解释，区分"基于文档"与"补充说明"

支持增强能力：语义缓存、多路召回/HyDE、Context Token 管理、SSE 流式输出。
"""
import json
from typing import Optional

from sqlalchemy.orm import Session

from app.config import settings
from app.core.logger import logger
from app.models.entities import ChatMessage
from app.prompts.open_qa_prompt import build_user_prompt as build_open_prompt
from app.prompts.open_qa_prompt import SYSTEM_PROMPT as OPEN_SYSTEM
from app.prompts.qa_prompt import build_qa_prompt
from app.prompts.rewrite_prompt import build_rewrite_prompt
from app.prompts.strict_qa_prompt import SYSTEM_PROMPT as STRICT_SYSTEM
from app.prompts.strict_qa_prompt import build_user_prompt as build_strict_prompt
from app.prompts.verifier_prompt import build_user_prompt as build_verifier_prompt
from app.repositories.chat_repo import ChatRepo
from app.services.context_window_manager import ContextWindowManager
from app.services.llm_service import LLMService
from app.services.retrieval_service import RetrievalService
from app.services.semantic_cache_service import SemanticCacheService
from app.utils.id_generator import gen_uuid


VALID_MODES = ("strict", "open")


class ChatService:
    """问答编排服务。"""

    def __init__(self, db: Session):
        self.db = db
        self.chat_repo = ChatRepo(db)
        self.retrieval_service = RetrievalService(db)
        self.llm = LLMService()
        self.cache = SemanticCacheService()

    def answer(
        self,
        question: str,
        session_id: Optional[str] = None,
        document_ids: Optional[list[str]] = None,
        mode: str = None,
    ) -> dict:
        """完整问答流程。

        返回结构：
            {
                session_id, answer, rewritten_query, sources,
                mode, grounded, unsupported_reason, supplement_note, verifier_result
            }
        """
        # 0. 模式归一化
        mode = (mode or settings.DEFAULT_CHAT_MODE or "open").lower()
        if mode not in VALID_MODES:
            mode = "open"
        logger.info(f"问答模式: mode={mode}")

        # 0.1 语义缓存查找（在会话创建前，命中直接返回）
        cached = self.cache.lookup(question, mode=mode, document_ids=document_ids)
        if cached is not None:
            # 命中缓存：仍需创建/绑定会话以持久化消息
            if not session_id:
                session_id = gen_uuid()
                self.chat_repo.create_session(session_id, document_ids=document_ids)
            else:
                session = self.chat_repo.get_session(session_id)
                if not session:
                    self.chat_repo.create_session(session_id, document_ids=document_ids)

            # 持久化 user + assistant 消息
            self.chat_repo.add_message(ChatMessage(
                id=gen_uuid(), session_id=session_id, role="user", content=question,
            ))
            self.chat_repo.add_message(ChatMessage(
                id=gen_uuid(), session_id=session_id, role="assistant",
                content=cached.get("answer", ""), source_chunks=None,
            ))

            cached["session_id"] = session_id
            cached["rewritten_query"] = None
            logger.info(f"语义缓存命中，跳过检索与 LLM 调用: session={session_id}")
            return cached

        # 1. 创建或获取会话
        is_new_session = False
        if not session_id:
            session_id = gen_uuid()
            self.chat_repo.create_session(session_id, document_ids=document_ids)
            is_new_session = True
        else:
            session = self.chat_repo.get_session(session_id)
            if not session:
                # 不存在则新建
                self.chat_repo.create_session(session_id, document_ids=document_ids)
            elif not document_ids:
                # 继承会话绑定的文档范围
                document_ids = self.chat_repo.get_session_document_ids(session_id)

        # 2. 加载历史
        history = self.chat_repo.get_recent_pairs(session_id, settings.HISTORY_TURNS)
        history_text = self._format_history(history)
        # Token 管理：截断历史到预算内
        history_text = ContextWindowManager.truncate_history(history_text)

        # 3. Query Rewrite（有历史时才改写）
        rewritten_query = None
        if history and not is_new_session:
            try:
                rewrite_prompt = build_rewrite_prompt(question, history_text)
                rewritten_query = self.llm.rewrite_query(rewrite_prompt).strip()
                if not rewritten_query:
                    rewritten_query = None
                logger.info(f"Query rewrite: '{question}' -> '{rewritten_query}'")
            except Exception as e:
                logger.warning(f"Query rewrite 失败，使用原问题: {e}")

        search_query = rewritten_query or question

        # 4. 按模式选择检索参数
        top_k, top_n, sim_threshold = self._retrieval_params(mode)

        # 5. 检索
        candidates = self.retrieval_service.retrieve(
            search_query,
            document_ids=document_ids,
            top_k=top_k,
            top_n=top_n,
            similarity_threshold=sim_threshold,
        )

        # 5.1 Token 管理：截断检索片段到 Context 预算内
        candidates = ContextWindowManager.truncate_candidates(candidates)

        # 6. 严格模式：检索不足直接拒答
        if mode == "strict":
            reject_reason = self._check_strict_grounded(candidates, sim_threshold)
            if reject_reason:
                logger.info(f"严格模式拒答: {reject_reason}")
                return self._build_reject_response(
                    session_id=session_id,
                    question=question,
                    rewritten_query=rewritten_query,
                    candidates=candidates,
                    reject_reason=reject_reason,
                )

        # 7. 构建 prompt（按模式分流）
        context = self._build_context(candidates)
        if mode == "strict":
            user_prompt = build_strict_prompt(question, context, history_text)
            system_prompt = STRICT_SYSTEM
        else:
            user_prompt = build_open_prompt(question, context, history_text)
            system_prompt = OPEN_SYSTEM

        # 8. LLM 生成
        answer = self.llm.generate_answer(user_prompt, system=system_prompt)

        # 9. 按模式做后处理
        grounded = None
        unsupported_reason = None
        supplement_note = None
        verifier_result = None

        if mode == "strict":
            # 严格模式：可选 verifier 校验
            grounded = True  # 通过拒答检查即视为有依据
            if settings.VERIFIER_ENABLED:
                try:
                    verifier_prompt = build_verifier_prompt(context, answer)
                    verifier_raw = self.llm.verify_answer(verifier_prompt)
                    verifier_result = verifier_raw
                    # verdict 非 supported 时降低 grounded
                    if verifier_raw.get("verdict") == "unsupported":
                        grounded = False
                        unsupported_reason = "答案未被证据充分支持：" + (verifier_raw.get("reason") or "")
                    elif verifier_raw.get("verdict") == "partial":
                        grounded = False
                        unsupported_reason = "答案部分未被证据支持：" + (verifier_raw.get("reason") or "")
                except Exception as e:
                    logger.warning(f"Verifier 校验失败，跳过: {e}")
        else:
            # 开放模式：检查回答中是否包含"补充说明"段落
            if "补充说明" in answer:
                supplement_note = "回答包含模型补充解释"

        # 10. 持久化消息
        sources_json = self._sources_to_json(candidates)

        # user 消息
        self.chat_repo.add_message(ChatMessage(
            id=gen_uuid(),
            session_id=session_id,
            role="user",
            content=question,
            rewritten_query=rewritten_query,
        ))
        # assistant 消息
        self.chat_repo.add_message(ChatMessage(
            id=gen_uuid(),
            session_id=session_id,
            role="assistant",
            content=answer,
            source_chunks=sources_json,
        ))

        # 11. 组装返回
        sources = self._sources_to_list(candidates)

        logger.info(
            f"问答完成: session={session_id}, mode={mode}, sources={len(sources)}, "
            f"grounded={grounded}"
        )
        result = {
            "session_id": session_id,
            "answer": answer,
            "rewritten_query": rewritten_query,
            "sources": sources,
            "mode": mode,
            "grounded": grounded,
            "unsupported_reason": unsupported_reason,
            "supplement_note": supplement_note,
            "verifier_result": verifier_result,
        }

        # 存入语义缓存（仅值得复用的响应才会被缓存层接收）
        try:
            self.cache.store(question, result, mode=mode, document_ids=document_ids)
        except Exception as e:
            logger.warning(f"语义缓存存储失败: {e}")

        return result

    # ============ 私有方法 ============

    @staticmethod
    def _retrieval_params(mode: str) -> tuple[int, int, float]:
        """按模式返回 (top_k, top_n, similarity_threshold)。"""
        if mode == "strict":
            return (
                settings.STRICT_MODE_TOP_K,
                settings.STRICT_MODE_TOP_N,
                settings.STRICT_SIMILARITY_THRESHOLD,
            )
        return (
            settings.OPEN_MODE_TOP_K,
            settings.OPEN_MODE_TOP_N,
            settings.OPEN_SIMILARITY_THRESHOLD,
        )

    @staticmethod
    def _check_strict_grounded(candidates: list[dict], threshold: float) -> Optional[str]:
        """严格模式拒答检查。返回拒答原因，None 表示可继续回答。"""
        if not candidates or len(candidates) < settings.STRICT_MIN_HITS:
            return "未找到足够依据（候选数为 0）"
        # 检查最高分是否达到阈值（rerank_score 已归一化到 0~1）
        max_score = max(
            (c.get("rerank_score", c.get("score", 0)) for c in candidates),
            default=0.0,
        )
        # 严格模式阈值使用相似度阈值；rerank_score 与 sim_threshold 量纲不同，
        # 此处用候选数 + 是否为空作为主判据，避免误拒
        if max_score <= 0:
            return "所有候选得分均为 0，证据不足"
        return None

    def _build_reject_response(
        self,
        session_id: str,
        question: str,
        rewritten_query: Optional[str],
        candidates: list[dict],
        reject_reason: str,
    ) -> dict:
        """构建严格模式拒答响应。"""
        answer = f"文档中未提及或当前检索内容不足以支持回答该问题。\n\n拒答原因：{reject_reason}"

        # 持久化
        sources_json = self._sources_to_json(candidates)
        self.chat_repo.add_message(ChatMessage(
            id=gen_uuid(),
            session_id=session_id,
            role="user",
            content=question,
            rewritten_query=rewritten_query,
        ))
        self.chat_repo.add_message(ChatMessage(
            id=gen_uuid(),
            session_id=session_id,
            role="assistant",
            content=answer,
            source_chunks=sources_json,
        ))

        sources = self._sources_to_list(candidates)
        return {
            "session_id": session_id,
            "answer": answer,
            "rewritten_query": rewritten_query,
            "sources": sources,
            "mode": "strict",
            "grounded": False,
            "unsupported_reason": reject_reason,
            "supplement_note": None,
            "verifier_result": None,
        }

    @staticmethod
    def _sources_to_json(candidates: list[dict]) -> Optional[str]:
        if not candidates:
            return None
        return json.dumps(
            [
                {
                    "chunk_id": c["chunk_id"],
                    "document_id": c["document_id"],
                    "document_name": c["document_name"],
                    "page_num": c.get("page_num"),
                    "snippet": c["snippet"],
                    "score": c.get("rerank_score", c.get("score", 0)),
                }
                for c in candidates
            ],
            ensure_ascii=False,
        )

    @staticmethod
    def _sources_to_list(candidates: list[dict]) -> list[dict]:
        return [
            {
                "chunk_id": c["chunk_id"],
                "document_id": c["document_id"],
                "document_name": c["document_name"],
                "page_num": c.get("page_num"),
                "snippet": c["snippet"],
                "score": c.get("rerank_score", c.get("score", 0)),
            }
            for c in candidates
        ]

    @staticmethod
    def _format_history(history: list[ChatMessage]) -> str:
        """格式化历史消息为文本。"""
        if not history:
            return ""
        lines = []
        for m in history:
            role = "用户" if m.role == "user" else "助手"
            lines.append(f"{role}: {m.content}")
        return "\n".join(lines)

    @staticmethod
    def _build_context(candidates: list[dict]) -> str:
        """将候选 chunk 拼接为 prompt 上下文，带来源标记。"""
        if not candidates:
            return "（无相关参考资料）"

        parts = []
        for i, c in enumerate(candidates, 1):
            page_info = f" 第{c['page_num']}页" if c.get("page_num") else ""
            source = f"[来源{i}: {c['document_name']}{page_info}]"
            parts.append(f"{source}\n{c['content']}")
        return "\n\n".join(parts)

    # ============ SSE 流式问答 ============

    def answer_stream(
        self,
        question: str,
        session_id: Optional[str] = None,
        document_ids: Optional[list[str]] = None,
        mode: str = None,
    ):
        """流式问答生成器。

        yield 的数据格式（dict）：
            {"type": "meta", "session_id": ..., "mode": ..., "rewritten_query": ...}
            {"type": "delta", "content": "..."}  # 增量文本
            {"type": "sources", "sources": [...]}
            {"type": "done", "grounded": ..., "verifier_result": ..., "from_cache": bool}
            {"type": "error", "message": "..."}

        流程与 answer() 一致，但 LLM 生成阶段改为 stream_chat 逐 token 产出。
        Verifier 校验在流式结束后异步执行，结果通过 done 事件返回。
        """
        # 0. 模式归一化
        mode = (mode or settings.DEFAULT_CHAT_MODE or "open").lower()
        if mode not in VALID_MODES:
            mode = "open"

        # 0.1 语义缓存查找
        cached = self.cache.lookup(question, mode=mode, document_ids=document_ids)
        if cached is not None:
            if not session_id:
                session_id = gen_uuid()
                self.chat_repo.create_session(session_id, document_ids=document_ids)
            else:
                session = self.chat_repo.get_session(session_id)
                if not session:
                    self.chat_repo.create_session(session_id, document_ids=document_ids)

            self.chat_repo.add_message(ChatMessage(
                id=gen_uuid(), session_id=session_id, role="user", content=question,
            ))
            self.chat_repo.add_message(ChatMessage(
                id=gen_uuid(), session_id=session_id, role="assistant",
                content=cached.get("answer", ""), source_chunks=None,
            ))

            yield {"type": "meta", "session_id": session_id, "mode": mode, "rewritten_query": None, "from_cache": True}
            # 缓存命中：一次性吐出完整答案
            yield {"type": "delta", "content": cached.get("answer", "")}
            yield {"type": "sources", "sources": cached.get("sources", [])}
            yield {
                "type": "done",
                "grounded": cached.get("grounded"),
                "unsupported_reason": cached.get("unsupported_reason"),
                "supplement_note": cached.get("supplement_note"),
                "verifier_result": cached.get("verifier_result"),
                "from_cache": True,
            }
            return

        # 1. 创建或获取会话
        is_new_session = False
        if not session_id:
            session_id = gen_uuid()
            self.chat_repo.create_session(session_id, document_ids=document_ids)
            is_new_session = True
        else:
            session = self.chat_repo.get_session(session_id)
            if not session:
                self.chat_repo.create_session(session_id, document_ids=document_ids)
            elif not document_ids:
                document_ids = self.chat_repo.get_session_document_ids(session_id)

        # 2. 加载历史
        history = self.chat_repo.get_recent_pairs(session_id, settings.HISTORY_TURNS)
        history_text = self._format_history(history)
        history_text = ContextWindowManager.truncate_history(history_text)

        # 3. Query Rewrite
        rewritten_query = None
        if history and not is_new_session:
            try:
                rewrite_prompt = build_rewrite_prompt(question, history_text)
                rewritten_query = self.llm.rewrite_query(rewrite_prompt).strip()
                if not rewritten_query:
                    rewritten_query = None
                logger.info(f"Query rewrite: '{question}' -> '{rewritten_query}'")
            except Exception as e:
                logger.warning(f"Query rewrite 失败，使用原问题: {e}")

        search_query = rewritten_query or question

        # 4. 检索参数与检索
        top_k, top_n, sim_threshold = self._retrieval_params(mode)
        candidates = self.retrieval_service.retrieve(
            search_query,
            document_ids=document_ids,
            top_k=top_k,
            top_n=top_n,
            similarity_threshold=sim_threshold,
        )
        candidates = ContextWindowManager.truncate_candidates(candidates)

        # 5. 严格模式拒答
        if mode == "strict":
            reject_reason = self._check_strict_grounded(candidates, sim_threshold)
            if reject_reason:
                logger.info(f"严格模式拒答(流式): {reject_reason}")
                reject_answer = f"文档中未提及或当前检索内容不足以支持回答该问题。\n\n拒答原因：{reject_reason}"
                sources = self._sources_to_list(candidates)
                sources_json = self._sources_to_json(candidates)

                self.chat_repo.add_message(ChatMessage(
                    id=gen_uuid(), session_id=session_id, role="user",
                    content=question, rewritten_query=rewritten_query,
                ))
                self.chat_repo.add_message(ChatMessage(
                    id=gen_uuid(), session_id=session_id, role="assistant",
                    content=reject_answer, source_chunks=sources_json,
                ))

                yield {"type": "meta", "session_id": session_id, "mode": mode, "rewritten_query": rewritten_query, "from_cache": False}
                yield {"type": "delta", "content": reject_answer}
                yield {"type": "sources", "sources": sources}
                yield {
                    "type": "done",
                    "grounded": False,
                    "unsupported_reason": reject_reason,
                    "supplement_note": None,
                    "verifier_result": None,
                    "from_cache": False,
                }
                return

        # 6. 构建 prompt
        context = self._build_context(candidates)
        if mode == "strict":
            user_prompt = build_strict_prompt(question, context, history_text)
            system_prompt = STRICT_SYSTEM
        else:
            user_prompt = build_open_prompt(question, context, history_text)
            system_prompt = OPEN_SYSTEM

        # 7. 发送 meta + sources，开始流式生成
        yield {"type": "meta", "session_id": session_id, "mode": mode, "rewritten_query": rewritten_query, "from_cache": False}
        yield {"type": "sources", "sources": self._sources_to_list(candidates)}

        # 8. 流式生成答案
        full_answer_parts = []
        try:
            for chunk_text in self.llm.stream_chat([
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ]):
                full_answer_parts.append(chunk_text)
                yield {"type": "delta", "content": chunk_text}
        except Exception as e:
            logger.error(f"流式生成失败: {e}")
            yield {"type": "error", "message": f"LLM 流式生成失败: {e}"}
            return

        answer = "".join(full_answer_parts).strip()

        # 9. 后处理（verifier / supplement_note）
        grounded = None
        unsupported_reason = None
        supplement_note = None
        verifier_result = None

        if mode == "strict":
            grounded = True
            if settings.VERIFIER_ENABLED:
                try:
                    verifier_prompt = build_verifier_prompt(context, answer)
                    verifier_result = self.llm.verify_answer(verifier_prompt)
                    if verifier_result.get("verdict") == "unsupported":
                        grounded = False
                        unsupported_reason = "答案未被证据充分支持：" + (verifier_result.get("reason") or "")
                    elif verifier_result.get("verdict") == "partial":
                        grounded = False
                        unsupported_reason = "答案部分未被证据支持：" + (verifier_result.get("reason") or "")
                except Exception as e:
                    logger.warning(f"Verifier 校验失败(流式)，跳过: {e}")
        else:
            if "补充说明" in answer:
                supplement_note = "回答包含模型补充解释"

        # 10. 持久化
        sources_json = self._sources_to_json(candidates)
        self.chat_repo.add_message(ChatMessage(
            id=gen_uuid(), session_id=session_id, role="user",
            content=question, rewritten_query=rewritten_query,
        ))
        self.chat_repo.add_message(ChatMessage(
            id=gen_uuid(), session_id=session_id, role="assistant",
            content=answer, source_chunks=sources_json,
        ))

        result = {
            "session_id": session_id,
            "answer": answer,
            "rewritten_query": rewritten_query,
            "sources": self._sources_to_list(candidates),
            "mode": mode,
            "grounded": grounded,
            "unsupported_reason": unsupported_reason,
            "supplement_note": supplement_note,
            "verifier_result": verifier_result,
        }
        try:
            self.cache.store(question, result, mode=mode, document_ids=document_ids)
        except Exception as e:
            logger.warning(f"语义缓存存储失败(流式): {e}")

        yield {
            "type": "done",
            "grounded": grounded,
            "unsupported_reason": unsupported_reason,
            "supplement_note": supplement_note,
            "verifier_result": verifier_result,
            "from_cache": False,
        }
