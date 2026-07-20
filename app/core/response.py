"""统一响应封装。"""
from typing import Any, Optional

from fastapi.responses import JSONResponse

from app.core.exceptions import ERROR_HTTP_STATUS, ErrorCode
from app.models.schemas import ApiResponse


def success_response(data: Any = None, message: str = "success") -> dict:
    """成功响应 dict。"""
    return {"code": ErrorCode.SUCCESS, "message": message, "data": data}


def error_response(code: int, message: str) -> dict:
    """错误响应 dict。"""
    return {"code": code, "message": message, "data": None}


def make_json_response(code: int, message: str, data: Any = None) -> JSONResponse:
    """构造 JSONResponse，HTTP 状态码由错误码决定。"""
    http_status = ERROR_HTTP_STATUS.get(code, 200)
    return JSONResponse(
        status_code=http_status,
        content={"code": code, "message": message, "data": data},
    )
