"""导入演示文档。

批量导入 data/demo 目录下的文档，便于演示。
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.logger import setup_logging, logger
from app.db.session import SessionLocal
from app.services.document_service import DocumentService


DEMO_DIR = Path(__file__).parent.parent / "data" / "demo"


def import_demo_docs():
    """导入演示文档。"""
    setup_logging()

    if not DEMO_DIR.exists():
        logger.warning(f"演示目录不存在: {DEMO_DIR}")
        logger.info("请将演示文档放到 data/demo/ 目录下后重试")
        return

    files = [f for f in DEMO_DIR.iterdir() if f.is_file() and f.suffix.lower() in (".pdf", ".docx", ".md", ".txt")]
    if not files:
        logger.warning(f"演示目录无支持的文档: {DEMO_DIR}")
        return

    logger.info(f"发现 {len(files)} 个演示文档")

    db = SessionLocal()
    try:
        doc_service = DocumentService(db)
        for f in files:
            try:
                content = f.read_bytes()
                document = doc_service.ingest(content, f.name)
                logger.info(f"导入成功: {f.name} -> {document.id} ({document.chunk_count} chunks)")
            except Exception as e:
                logger.error(f"导入失败: {f.name}, error={e}")
    finally:
        db.close()


if __name__ == "__main__":
    import_demo_docs()
