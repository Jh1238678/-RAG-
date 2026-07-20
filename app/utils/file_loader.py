"""文件加载与类型校验工具。"""
import os
import shutil
from pathlib import Path

from app.config import settings
from app.core.exceptions import FileTooLargeError, UnsupportedFileTypeError
from app.utils.id_generator import gen_uuid


def get_file_ext(filename: str) -> str:
    """获取文件扩展名（小写，不含点）。"""
    return Path(filename).suffix.lower().lstrip(".")


def validate_file_type(filename: str) -> str:
    """校验文件类型，返回扩展名。不支持则抛异常。"""
    ext = get_file_ext(filename)
    if ext not in settings.supported_file_types:
        raise UnsupportedFileTypeError(ext)
    return ext


def validate_file_size(size: int) -> None:
    """校验文件大小。"""
    if size > settings.max_file_size_bytes:
        raise FileTooLargeError(size / 1024 / 1024, settings.MAX_FILE_SIZE_MB)


def save_upload_file(src_path: str, original_filename: str) -> tuple[str, str]:
    """保存上传文件到 UPLOAD_DIR，返回 (相对路径, 绝对路径)。

    文件名用 uuid 重命名，避免冲突和路径注入。
    """
    ext = validate_file_type(original_filename)
    new_name = f"{gen_uuid()}.{ext}"
    abs_path = Path(settings.UPLOAD_DIR) / new_name
    rel_path = f"{settings.UPLOAD_DIR}/{new_name}"

    shutil.move(src_path, abs_path)
    return rel_path, str(abs_path)


def delete_file(rel_path: str) -> None:
    """删除文件，不存在不报错。"""
    try:
        Path(rel_path).unlink(missing_ok=True)
    except Exception:
        pass
