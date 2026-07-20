"""文本清洗工具。"""
import re


def clean_text(text: str) -> str:
    """清洗文本：去除多余空白、异常字符、规范化。"""
    if not text:
        return ""

    # 1. 去除 NULL 等控制字符（保留换行）
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", text)

    # 2. 统一空白字符：全角空格 -> 半角，多个空格 -> 单个
    text = text.replace("\u3000", " ")
    text = re.sub(r"[^\S\n]+", " ", text)

    # 3. 行首行尾去空格
    lines = [line.strip() for line in text.splitlines()]
    text = "\n".join(lines)

    # 4. 三个以上连续换行 -> 两个
    text = re.sub(r"\n{3,}", "\n\n", text)

    # 5. 去除常见页眉页脚模式（连续出现 3 次以上的相同短行）
    _remove_repeated_headers(text)

    return text.strip()


def _remove_repeated_headers(text: str) -> str:
    """尝试移除重复出现的页眉/页脚（占位实现，复杂场景需结合 PDF 元信息）。"""
    # 此处保持简单：仅做最基础的清洗，实际页眉页脚由 PDF parser 基于版面处理
    return text


def truncate_for_display(text: str, max_chars: int = 200) -> str:
    """截断文本用于引用片段展示。"""
    if len(text) <= max_chars:
        return text
    return text[:max_chars].rsplit(" ", 1)[0] + "..."
