"""项目主入口。

负责创建 FastAPI 应用、注册路由、注册异常处理器、配置跨域中间件。
"""
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import settings
from app.core.exceptions import AppException, app_exception_handler
from app.core.logger import setup_logging
from app.core.response import error_response
from app.db.base import Base
from app.db.session import engine


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期：启动时建表、配置日志、确保目录。"""
    # 设置 HuggingFace 镜像（必须在加载任何 HF 模型前设置）
    if settings.HF_ENDPOINT:
        os.environ["HF_ENDPOINT"] = settings.HF_ENDPOINT
    settings.ensure_dirs()
    setup_logging()
    # 自动建表（开发期；生产环境用 alembic 迁移）
    Base.metadata.create_all(bind=engine)
    yield


def create_app() -> FastAPI:
    """创建并配置 FastAPI 应用。"""
    app = FastAPI(
        title=settings.APP_NAME,
        version=settings.APP_VERSION,
        lifespan=lifespan,
    )

    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # 异常处理
    app.add_exception_handler(AppException, app_exception_handler)

    # 注册路由
    from app.api import routes_health, routes_upload, routes_docs, routes_chat

    app.include_router(routes_health.router)
    app.include_router(routes_upload.router, prefix="/api", tags=["upload"])
    app.include_router(routes_docs.router, prefix="/api", tags=["docs"])
    app.include_router(routes_chat.router, prefix="/api", tags=["chat"])

    return app


app = create_app()
