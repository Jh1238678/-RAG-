"""初始化数据库：建表。"""
import sys
from pathlib import Path

# 将项目根目录加入 sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.db.base import Base
from app.db.session import engine
from app.core.logger import setup_logging, logger


def init_db():
    """创建所有表。"""
    setup_logging()
    logger.info("开始初始化数据库...")

    # 导入所有实体以注册到 Base.metadata
    from app.models import entities  # noqa: F401
    from app.repositories.index_repo import _index_mapping_table  # noqa: F401

    Base.metadata.create_all(bind=engine)
    logger.info(f"数据库初始化完成: {engine.url}")


if __name__ == "__main__":
    init_db()
