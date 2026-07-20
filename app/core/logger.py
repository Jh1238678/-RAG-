"""日志配置。基于 loguru。"""
import sys
from pathlib import Path

from loguru import logger

from app.config import settings


def setup_logging() -> None:
    """配置 loguru：控制台 + 文件输出。"""
    logger.remove()  # 移除默认 handler

    log_format = (
        "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
        "<level>{level: <8}</level> | "
        "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
        "<level>{message}</level>"
    )

    # 控制台
    logger.add(
        sys.stderr,
        format=log_format,
        level=settings.LOG_LEVEL,
        colorize=True,
    )

    # 文件（按天轮转，保留 7 天）
    log_dir = Path(settings.LOG_DIR)
    log_dir.mkdir(parents=True, exist_ok=True)
    logger.add(
        log_dir / "app_{time:YYYY-MM-DD}.log",
        format=log_format,
        level=settings.LOG_LEVEL,
        rotation="00:00",
        retention="7 days",
        encoding="utf-8",
    )


# 导出 logger 供其它模块使用
__all__ = ["logger", "setup_logging"]
