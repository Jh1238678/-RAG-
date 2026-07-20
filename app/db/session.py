"""数据库连接管理。

提供 engine 和 sessionmaker，并对 SQLite 开启 WAL 模式和外键约束。
"""
from collections.abc import Generator

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import settings


def _build_engine() -> Engine:
    """根据 DATABASE_URL 创建 engine，并对 SQLite 做特殊配置。"""
    url = settings.DATABASE_URL
    connect_args = {}
    is_sqlite = url.startswith("sqlite")

    if is_sqlite:
        # SQLite 需要允许同线程多连接（FastAPI 下 check_same_thread=False）
        connect_args["check_same_thread"] = False

    engine = create_engine(url, echo=settings.DEBUG, connect_args=connect_args, future=True)

    if is_sqlite:
        @event.listens_for(engine, "connect")
        def _sqlite_pragma(dbapi_conn, _):
            cursor = dbapi_conn.cursor()
            # WAL 模式：提升并发读写
            cursor.execute("PRAGMA journal_mode=WAL")
            # 开启外键约束（SQLite 默认关闭）
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

    return engine


engine: Engine = _build_engine()
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)


def get_db() -> Generator[Session, None, None]:
    """FastAPI 依赖注入：提供数据库 session。"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
