"""TXT 解析器。统一编码读取。"""
from app.core.logger import logger
from app.parsers.base import BaseParser, PageInfo, ParsedDocument


class TxtParser(BaseParser):
    """纯文本解析器。自动处理编码。"""

    def parse(self, file_path: str) -> ParsedDocument:
        logger.info(f"开始解析 TXT: {file_path}")
        text = self._read_with_fallback(file_path)
        full_text = text.strip()
        pages = [PageInfo(page_num=1, text=full_text)] if full_text else []

        logger.info(f"TXT 解析完成: {len(full_text)} 字符")
        return ParsedDocument(
            text=full_text,
            pages=pages,
            metadata={"parser": "txt"},
        )

    @staticmethod
    def _read_with_fallback(file_path: str) -> str:
        """尝试多种编码读取。"""
        for encoding in ("utf-8", "gbk", "gb18030", "latin-1"):
            try:
                with open(file_path, "r", encoding=encoding) as f:
                    return f.read()
            except UnicodeDecodeError:
                continue
        # 兜底：utf-8 忽略错误字符
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            return f.read()
