"""文档上传路由。"""
from fastapi import APIRouter, Depends, UploadFile, File

from app.core.exceptions import AppException, ErrorCode
from app.core.response import success_response
from app.models.schemas import UploadResponse
from app.services.document_service import DocumentService
from app.api.deps import get_document_service

router = APIRouter()


@router.post("/upload")
async def upload_document(
    file: UploadFile = File(...),
    doc_service: DocumentService = Depends(get_document_service),
):
    """上传文档并自动入库。"""
    # 读取文件内容
    content = await file.read()
    file_size = len(content)

    # 校验大小
    from app.config import settings
    if file_size > settings.max_file_size_bytes:
        raise AppException(
            ErrorCode.FILE_TOO_LARGE,
            f"文件过大: {file_size / 1024 / 1024:.1f}MB，上限 {settings.MAX_FILE_SIZE_MB}MB",
        )

    # 入库
    document = doc_service.ingest(content, file.filename or "unknown")

    return success_response(UploadResponse(
        document_id=document.id,
        file_name=document.file_name,
        status=document.status,
        chunk_count=document.chunk_count,
    ).model_dump())
