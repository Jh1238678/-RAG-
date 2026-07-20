"""Markdown 解析器。使用 markdown-it-py。

保留标题层级。
"""
from app.core.logger import logger
from app.parsers.base import BaseParser, PageInfo, ParsedDocument


class MarkdownParser(BaseParser):
    """Markdown 文档解析器。

    策略：保留原始 Markdown 文本（标题层级天然存在），
    同时用 markdown-it 校验语法并统计标题数。
    """

    def parse(self, file_path: str) -> ParsedDocument:
        from markdown_it import MarkdownIt  # 延迟导入
        logger.info(f"开始解析 Markdown: {file_path}")
        with open(file_path, "r", encoding="utf-8") as f:
            text = f.read()

        # 用 markdown-it 解析 token，统计标题
        md = MarkdownIt()
        try:
            tokens = md.parse(text)
            heading_count = sum(1 for t in tokens if t.type == "heading_open")
        except Exception:
            heading_count = 0

        full_text = text.strip()
        pages = [PageInfo(page_num=1, text=full_text)] if full_text else []

        logger.info(f"Markdown 解析完成: {len(full_text)} 字符, {heading_count} 个标题")
        return ParsedDocument(
            text=full_text,
            pages=pages,
            metadata={"heading_count": heading_count, "parser": "markdown-it-py"},
        )
