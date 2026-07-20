"""Token 估算工具。

使用 tiktoken 估算 token 数（用于控制 chunk 大小和 prompt 长度）。
对于中文，tiktoken 会略微高估，但作为 chunk 切分参考足够。
"""

_encoding = None


def _get_encoding():
    global _encoding
    if _encoding is None:
        import tiktoken
        try:
            _encoding = tiktoken.get_encoding("cl100k_base")
        except Exception:
            # 退化方案：用 gpt2 编码
            _encoding = tiktoken.get_encoding("gpt2")
    return _encoding


def count_tokens(text: str) -> int:
    """估算文本的 token 数。"""
    if not text:
        return 0
    enc = _get_encoding()
    return len(enc.encode(text))


def count_chars(text: str) -> int:
    """字符数。"""
    return len(text) if text else 0


def truncate_by_tokens(text: str, max_tokens: int) -> str:
    """按 token 数截断文本。"""
    if not text:
        return ""
    enc = _get_encoding()
    tokens = enc.encode(text)
    if len(tokens) <= max_tokens:
        return text
    return enc.decode(tokens[:max_tokens])
