"""文档管理路由。"""
from fastapi import APIRouter, Depends, Query

from app.core.exceptions import DocumentNotFoundError
from app.core.response import success_response
from app.models.entities import Document
from app.models.schemas import (
    ChunkPreview,
    DeleteResponse,
    DocumentDetailOut,
    DocumentListOut,
    DocumentOut,
    SummaryResponse,
)
from app.repositories.document_repo import ChunkRepo, DocumentRepo
from app.api.deps import get_document_repo, get_chunk_repo
from app.services.document_service import DocumentService
from app.services.summary_service import SummaryService
from sqlalchemy.orm import Session
from app.db.session import get_db
from fastapi import Depends

router = APIRouter()


@router.get("/documents")
async def list_documents(
    status: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    doc_repo: DocumentRepo = Depends(get_document_repo),
):
    """获取文档列表。"""
    items, total = doc_repo.list_documents(status=status, page=page, page_size=page_size)
    return success_response(DocumentListOut(
        total=total,
        items=[DocumentOut.model_validate(d) for d in items],
    ).model_dump())


@router.get("/documents/{document_id}")
async def get_document(
    document_id: str,
    doc_repo: DocumentRepo = Depends(get_document_repo),
    chunk_repo: ChunkRepo = Depends(get_chunk_repo),
):
    """获取文档详情（含前 3 个 chunk 预览）。"""
    document = doc_repo.get_by_id(document_id)
    if not document:
        raise DocumentNotFoundError(document_id)

    chunks = chunk_repo.list_by_document(document_id)[:5]
    return success_response(DocumentDetailOut(
        **DocumentOut.model_validate(document).model_dump(),
        chunks_preview=[
            ChunkPreview(
                id=c.id,
                chunk_index=c.chunk_index,
                content=c.content[:200] + "..." if len(c.content) > 200 else c.content,
                page_num=c.page_num,
                char_count=c.char_count,
            )
            for c in chunks
        ],
    ).model_dump())


@router.delete("/documents/{document_id}")
async def delete_document(
    document_id: str,
    db: Session = Depends(get_db),
):
    """删除文档及其索引。"""
    doc_service = DocumentService(db)
    deleted = doc_service.delete(document_id)
    if not deleted:
        raise DocumentNotFoundError(document_id)
    return success_response(DeleteResponse(deleted=True).model_dump())


@router.post("/summary/{document_id}")
async def generate_summary(
    document_id: str,
    db: Session = Depends(get_db),
):
    """生成文档摘要。"""
    summary_service = SummaryService(db)
    result = summary_service.generate(document_id)
    return success_response(SummaryResponse(**result).model_dump())
