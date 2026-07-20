"""解析器单元测试。

注意：需要提供测试文件。此处用临时生成的 txt/md 文件测试。
PDF/DOCX 测试需要真实文件，标记为 skip。
"""
import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.parsers.txt_parser import TxtParser
from app.parsers.markdown_parser import MarkdownParser


def test_txt_parser_utf8():
    """测试 UTF-8 TXT 解析。"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8") as f:
        f.write("Hello 世界\n第二行")
        f.flush()
        result = TxtParser().parse(f.name)
    assert "Hello 世界" in result.text
    assert "第二行" in result.text
    assert len(result.pages) == 1
    assert result.pages[0].page_num == 1


def test_txt_parser_empty():
    """测试空文件。"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8") as f:
        f.write("")
        f.flush()
        result = TxtParser().parse(f.name)
    assert result.text == ""
    assert len(result.pages) == 0


def test_markdown_parser():
    """测试 Markdown 解析。"""
    content = """# 标题一

这是正文段落。

## 子标题

更多内容。
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False, encoding="utf-8") as f:
        f.write(content)
        f.flush()
        result = MarkdownParser().parse(f.name)
    assert "标题一" in result.text
    assert result.metadata.get("heading_count", 0) >= 2


def test_txt_parser_gbk_encoding():
    """测试 GBK 编码文件。"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="gbk") as f:
        f.write("中文内容测试")
        f.flush()
        result = TxtParser().parse(f.name)
    assert "中文内容测试" in result.text
