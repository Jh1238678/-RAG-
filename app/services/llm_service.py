"""LLM 服务。

封装 OpenAI SDK 调用，支持 DeepSeek/Qwen/OpenAI 多厂商切换。
"""
import json
import re
import time
from typing import Optional

from app.config import settings
from app.core.exceptions import LLMCallError, LLMTimeoutError
from app.core.logger import logger


class LLMService:
    """大模型调用服务。"""

    _client = None

    def __init__(self):
        self._ensure_client()

    @classmethod
    def _ensure_client(cls):
        if cls._client is None:
            from openai import OpenAI
            if not settings.LLM_API_KEY:
                logger.warning("LLM_API_KEY 未配置，LLM 调用将失败")
            cls._client = OpenAI(
                api_key=settings.LLM_API_KEY or "empty",
                base_url=settings.LLM_BASE_URL,
                timeout=settings.LLM_TIMEOUT,
            )
            logger.info(
                f"LLM 客户端初始化: provider={settings.LLM_PROVIDER}, "
                f"model={settings.LLM_MODEL}"
            )

    def generate_answer(self, prompt: str, system: str = "") -> str:
        """生成问答回答。"""
        return self._chat([
            {"role": "system", "content": system or "你是一个严谨的文档问答助手。"},
            {"role": "user", "content": prompt},
        ])

    def generate_summary(self, prompt: str) -> str:
        """生成摘要。"""
        return self._chat([
            {"role": "system", "content": "你是一个专业的文档摘要生成助手。"},
            {"role": "user", "content": prompt},
        ])

    def rewrite_query(self, prompt: str) -> str:
        """问题改写。"""
        return self._chat([
            {"role": "system", "content": "你是一个问题改写助手，只输出改写后的问题，不要解释。"},
            {"role": "user", "content": prompt},
        ], temperature=0.0)

    def generate_multi_queries(self, prompt: str, count: int = 3) -> list[str]:
        """生成多个变种问题（Multi-Query Retrieval）。

        Args:
            prompt: multi_query_prompt 构建的 prompt
            count: 期望生成的变种数

        Returns:
            变种问题列表（已去重、去空、去除编号）
        """
        raw = self._chat([
            {"role": "system", "content": f"你是问题改写助手，请生成 {count} 个语义等价的变种问题，每行一个，不要编号。"},
            {"role": "user", "content": prompt},
        ], temperature=0.5)

        lines = []
        for line in raw.strip().split("\n"):
            line = line.strip()
            if not line:
                continue
            # 去除可能的编号前缀 "1." "1、" "1)" 等
            import re as _re
            cleaned = _re.sub(r"^\s*\d+[\.\)、]\s*", "", line).strip()
            if cleaned and cleaned not in lines:
                lines.append(cleaned)
        return lines[:count]

    def generate_hyde_document(self, prompt: str) -> str:
        """生成 HyDE 假设性文档。"""
        raw = self._chat([
            {"role": "system", "content": "你是一个文档生成助手，请直接输出假设性答案正文，不要解释。"},
            {"role": "user", "content": prompt},
        ], temperature=0.7)
        return raw.strip()

    def verify_answer(self, prompt: str) -> dict:
        """答案支持性校验。返回 {verdict, reason, unsupported_spans}。

        verdict: supported | partial | unsupported

        优先使用 JSON Mode 强制结构化输出；JSON Mode 不可用时退化到正则解析。
        """
        from app.prompts.verifier_prompt import SYSTEM_PROMPT

        if settings.VERIFIER_JSON_MODE:
            # 优先走 JSON Mode：强制模型输出标准 JSON
            try:
                raw = self._chat_json([
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ], temperature=0.0)
                parsed = self._parse_json_safe(raw)
                if parsed is not None:
                    return self._normalize_verifier_dict(parsed)
                # JSON 解析失败，退化到正则
                logger.warning("JSON Mode 输出解析失败，退化到正则解析")
            except Exception as e:
                # 网关不支持 JSON Mode 等场景，退化到普通调用
                logger.warning(f"JSON Mode 调用失败，退化到普通调用: {e}")

        # 退化路径：普通调用 + 正则解析
        raw = self._chat([
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ], temperature=0.0)
        return self._parse_verifier_output(raw)

    def _chat_json(self, messages: list[dict], temperature: Optional[float] = None) -> str:
        """使用 response_format json_object 强制 JSON 输出。"""
        temp = temperature if temperature is not None else settings.LLM_TEMPERATURE
        max_retries = 3

        for attempt in range(1, max_retries + 1):
            try:
                resp = self._client.chat.completions.create(
                    model=settings.LLM_MODEL,
                    messages=messages,
                    temperature=temp,
                    max_tokens=settings.LLM_MAX_TOKENS,
                    response_format={"type": "json_object"},
                )
                return resp.choices[0].message.content.strip()
            except Exception as e:
                err_str = str(e).lower()
                logger.warning(f"LLM JSON 调用失败 (第 {attempt} 次): {e}")
                # 不支持 response_format 的网关直接抛出，由上层退化
                if "response_format" in err_str or "unrecognized" in err_str or "not support" in err_str:
                    raise
                if "timeout" in err_str or "timed out" in err_str:
                    if attempt == max_retries:
                        raise LLMTimeoutError(f"LLM 调用超时: {e}")
                if attempt == max_retries:
                    raise LLMCallError(f"LLM 调用失败: {e}")
                time.sleep(2 ** attempt)

        return ""

    @staticmethod
    def _parse_json_safe(raw: str) -> Optional[dict]:
        """容错解析 JSON 文本。"""
        if not raw:
            return None
        # 去掉可能的 markdown 代码块包裹
        text = raw.strip()
        if text.startswith("```"):
            # 去掉首行 ```json 或 ```
            lines = text.split("\n")
            if lines:
                lines = lines[1:]  # 去首行
            if lines and lines[-1].strip().startswith("```"):
                lines = lines[:-1]  # 去末行
            text = "\n".join(lines).strip()
        try:
            parsed = json.loads(text)
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            # 尝试提取首个 JSON 对象
            m = re.search(r"\{[\s\S]*\}", text)
            if m:
                try:
                    return json.loads(m.group(0))
                except json.JSONDecodeError:
                    pass
        return None

    @staticmethod
    def _normalize_verifier_dict(d: dict) -> dict:
        """规范化 verifier JSON 字典。"""
        verdict = str(d.get("verdict", "partial")).lower().strip()
        if verdict not in ("supported", "partial", "unsupported"):
            verdict = "partial"
        reason = str(d.get("reason", "") or "").strip()
        spans_raw = d.get("unsupported_spans", [])
        if isinstance(spans_raw, list):
            unsupported_spans = [str(s) for s in spans_raw if s]
        else:
            unsupported_spans = []
        return {
            "verdict": verdict,
            "reason": reason,
            "unsupported_spans": unsupported_spans,
        }

    @staticmethod
    def _parse_verifier_output(raw: str) -> dict:
        """解析 verifier 输出，容错处理。"""
        verdict = "partial"
        reason = ""
        unsupported_spans: list[str] = []

        # 提取 verdict
        m = re.search(r"verdict\s*[:：]\s*(supported|partial|unsupported)", raw, re.IGNORECASE)
        if m:
            verdict = m.group(1).lower()

        # 提取 reason
        m = re.search(r"reason\s*[:：]\s*([^\n]*(?:\n(?!\s*(?:verdict|unsupported_spans)\s*[:：])[^\n]*)*)", raw, re.IGNORECASE)
        if m:
            reason = m.group(1).strip()

        # 提取 unsupported_spans：支持 JSON 数组或换行/逗号分隔的列表
        m = re.search(r"unsupported_spans\s*[:：]\s*(.+)", raw, re.IGNORECASE | re.DOTALL)
        if m:
            spans_text = m.group(1).strip()
            # 尝试 JSON 解析
            if spans_text.startswith("["):
                try:
                    parsed = json.loads(spans_text)
                    if isinstance(parsed, list):
                        unsupported_spans = [str(x) for x in parsed if x]
                except json.JSONDecodeError:
                    pass
            elif spans_text and spans_text.lower() not in ("[]", "无", "none", "-"):
                # 按换行或逗号分割
                parts = re.split(r"[\n,、]", spans_text)
                unsupported_spans = [p.strip("- •*").strip() for p in parts if p.strip() and p.strip() not in ("[]", "无")]

        return {
            "verdict": verdict,
            "reason": reason,
            "unsupported_spans": unsupported_spans,
        }

    def _chat(self, messages: list[dict], temperature: Optional[float] = None) -> str:
        """统一 chat 调用，带重试。"""
        temp = temperature if temperature is not None else settings.LLM_TEMPERATURE
        max_retries = 3

        for attempt in range(1, max_retries + 1):
            try:
                logger.debug(f"LLM 调用 (第 {attempt} 次): model={settings.LLM_MODEL}")
                resp = self._client.chat.completions.create(
                    model=settings.LLM_MODEL,
                    messages=messages,
                    temperature=temp,
                    max_tokens=settings.LLM_MAX_TOKENS,
                )
                content = resp.choices[0].message.content
                return content.strip()
            except Exception as e:
                err_str = str(e).lower()
                logger.warning(f"LLM 调用失败 (第 {attempt} 次): {e}")
                if "timeout" in err_str or "timed out" in err_str:
                    if attempt == max_retries:
                        raise LLMTimeoutError(f"LLM 调用超时: {e}")
                if attempt == max_retries:
                    raise LLMCallError(f"LLM 调用失败: {e}")
                # 指数退避
                time.sleep(2 ** attempt)

        return ""  # 不会执行到这里

    def stream_chat(self, messages: list[dict], temperature: Optional[float] = None):
        """流式 chat 调用，返回生成器逐 token 产出。

        用法：
            for chunk_text in llm.stream_chat(messages):
                # 处理增量文本
        """
        temp = temperature if temperature is not None else settings.LLM_TEMPERATURE
        max_retries = 3

        for attempt in range(1, max_retries + 1):
            try:
                logger.debug(f"LLM 流式调用 (第 {attempt} 次): model={settings.LLM_MODEL}")
                stream = self._client.chat.completions.create(
                    model=settings.LLM_MODEL,
                    messages=messages,
                    temperature=temp,
                    max_tokens=settings.LLM_MAX_TOKENS,
                    stream=True,
                )
                for chunk in stream:
                    if chunk.choices and chunk.choices[0].delta.content:
                        yield chunk.choices[0].delta.content
                return  # 正常结束
            except Exception as e:
                err_str = str(e).lower()
                logger.warning(f"LLM 流式调用失败 (第 {attempt} 次): {e}")
                if "timeout" in err_str or "timed out" in err_str:
                    if attempt == max_retries:
                        raise LLMTimeoutError(f"LLM 流式调用超时: {e}")
                if attempt == max_retries:
                    raise LLMCallError(f"LLM 流式调用失败: {e}")
                time.sleep(2 ** attempt)
