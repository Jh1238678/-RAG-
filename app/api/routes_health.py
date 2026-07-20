"""健康检查路由。"""
from fastapi import APIRouter

from app.config import settings
from app.core.response import success_response
from app.db.session import engine

router = APIRouter()


@router.get("/health")
async def health_check():
    """服务健康检查。"""
    # 检查数据库
    db_ok = "connected"
    try:
        from sqlalchemy import text
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except Exception:
        db_ok = "disconnected"

    # 检查 FAISS（延迟导入，避免未安装时启动失败）
    faiss_loaded = False
    try:
        from app.services.vector_service import VectorService
        faiss_loaded = VectorService().is_loaded
    except Exception:
        pass

    return success_response({
        "status": "ok",
        "version": settings.APP_VERSION,
        "db": db_ok,
        "faiss_loaded": faiss_loaded,
    })
