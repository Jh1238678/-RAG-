"""自定义业务异常与错误码。"""


class ErrorCode:
    """错误码枚举。"""
    # 通用成功
    SUCCESS = 0
    # 参数错误 1xxx
    INVALID_PARAM = 1001
    UNSUPPORTED_FILE_TYPE = 1002
    FILE_TOO_LARGE = 1003
    # 文档相关 2xxx
    DOCUMENT_NOT_FOUND = 2001
    DOCUMENT_PROCESSING = 2002
    DOCUMENT_FAILED = 2003
    # LLM 相关 3xxx
    LLM_CALL_FAILED = 3001
    LLM_TIMEOUT = 3002
    # 服务器 5xxx
    INTERNAL_ERROR = 5000


# 错误码 -> HTTP 状态码
ERROR_HTTP_STATUS = {
    ErrorCode.SUCCESS: 200,
    ErrorCode.INVALID_PARAM: 400,
    ErrorCode.UNSUPPORTED_FILE_TYPE: 400,
    ErrorCode.FILE_TOO_LARGE: 413,
    ErrorCode.DOCUMENT_NOT_FOUND: 404,
    ErrorCode.DOCUMENT_PROCESSING: 409,
    ErrorCode.DOCUMENT_FAILED: 422,
    ErrorCode.LLM_CALL_FAILED: 502,
    ErrorCode.LLM_TIMEOUT: 504,
    ErrorCode.INTERNAL_ERROR: 500,
}


class AppException(Exception):
    """业务异常基类。携带错误码和消息。"""

    def __init__(self, code: int = ErrorCode.INTERNAL_ERROR, message: str = ""):
        self.code = code
        self.message = message or "服务器内部错误"
        super().__init__(self.message)


class InvalidParamError(AppException):
    def __init__(self, message: str = "参数错误"):
        super().__init__(ErrorCode.INVALID_PARAM, message)


class UnsupportedFileTypeError(AppException):
    def __init__(self, file_type: str = ""):
        msg = f"不支持的文件类型: {file_type}" if file_type else "不支持的文件类型"
        super().__init__(ErrorCode.UNSUPPORTED_FILE_TYPE, msg)


class FileTooLargeError(AppException):
    def __init__(self, size_mb: float = 0, limit_mb: int = 0):
        super().__init__(
            ErrorCode.FILE_TOO_LARGE,
            f"文件过大: {size_mb:.1f}MB，上限 {limit_mb}MB",
        )


class DocumentNotFoundError(AppException):
    def __init__(self, document_id: str = ""):
        msg = f"文档不存在: {document_id}" if document_id else "文档不存在"
        super().__init__(ErrorCode.DOCUMENT_NOT_FOUND, msg)


class DocumentProcessingError(AppException):
    def __init__(self, message: str = "文档处理中"):
        super().__init__(ErrorCode.DOCUMENT_PROCESSING, message)


class DocumentFailedError(AppException):
    def __init__(self, message: str = "文档处理失败"):
        super().__init__(ErrorCode.DOCUMENT_FAILED, message)


class LLMCallError(AppException):
    def __init__(self, message: str = "LLM 调用失败"):
        super().__init__(ErrorCode.LLM_CALL_FAILED, message)


class LLMTimeoutError(AppException):
    def __init__(self, message: str = "LLM 调用超时"):
        super().__init__(ErrorCode.LLM_TIMEOUT, message)


# ============ 异常处理器 ============
async def app_exception_handler(request, exc: AppException):
    """FastAPI 异常处理器：将 AppException 转为统一 JSON 响应。"""
    from app.core.response import make_json_response
    return make_json_response(exc.code, exc.message)
