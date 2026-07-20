"""文本清洗工具单元测试。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.utils.text_cleaner import clean_text, truncate_for_display


def test_clean_text_removes_control_chars():
    """测试去除控制字符。"""
    text = "hello\x00world\x07"
    # 控制字符被删除（不是替换为空格）
    assert clean_text(text) == "helloworld"


def test_clean_text_normalizes_whitespace():
    """测试空白规范化。"""
    text = "hello   world\t\tend"
    assert clean_text(text) == "hello world end"


def test_clean_text_collapses_newlines():
    """测试多换行折叠。"""
    text = "line1\n\n\n\n\nline2"
    assert clean_text(text) == "line1\n\nline2"


def test_clean_text_full_width_space():
    """测试全角空格转半角。"""
    text = "hello\u3000world"
    assert clean_text(text) == "hello world"


def test_clean_text_empty():
    """测试空字符串。"""
    assert clean_text("") == ""
    assert clean_text(None) == ""


def test_truncate_for_display_short():
    """测试短文本不截断。"""
    text = "short text"
    assert truncate_for_display(text, 200) == "short text"


def test_truncate_for_display_long():
    """测试长文本截断。"""
    text = "a" * 300
    result = truncate_for_display(text, 100)
    assert len(result) <= 103  # 100 + "..."
    assert result.endswith("...")
