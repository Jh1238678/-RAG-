"""PDF 解析器。使用 PyMuPDF。

保留页码信息，处理空页、页眉页脚。
"""
from app.core.logger import logger
from app.parsers.base import BaseParser, PageInfo, ParsedDocument, merge_pages_to_text


class PDFParser(BaseParser):
    """PDF 文档解析器。"""

    def parse(self, file_path: str) -> ParsedDocument:
        import fitz  # PyMuPDF，延迟导入
        logger.info(f"开始解析 PDF: {file_path}")
        pages: list[PageInfo] = []

        doc = fitz.open(file_path)
        try:
            for page_num, page in enumerate(doc, start=1):
                text = page.get_text("text")
                if text:
                    text = text.strip()
                pages.append(PageInfo(page_num=page_num, text=text or ""))
        finally:
            doc.close()

        full_text = merge_pages_to_text(pages)
        logger.info(f"PDF 解析完成: {len(pages)} 页, {len(full_text)} 字符")
        return ParsedDocument(
            text=full_text,
            pages=pages,
            metadata={"page_count": len(pages), "parser": "PyMuPDF"},
        )
