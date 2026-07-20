"""API 依赖注入。"""
from fastapi import Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.repositories.chat_repo import ChatRepo
from app.repositories.document_repo import ChunkRepo, DocumentRepo
from app.repositories.index_repo import IndexRepo
from app.services.chat_service import ChatService
from app.services.document_service import DocumentService
from app.services.summary_service import SummaryService


def get_document_service(db: Session = Depends(get_db)) -> DocumentService:
    return DocumentService(db)


def get_chat_service(db: Session = Depends(get_db)) -> ChatService:
    return ChatService(db)


def get_summary_service(db: Session = Depends(get_db)) -> SummaryService:
    return SummaryService(db)


def get_document_repo(db: Session = Depends(get_db)) -> DocumentRepo:
    return DocumentRepo(db)


def get_chunk_repo(db: Session = Depends(get_db)) -> ChunkRepo:
    return ChunkRepo(db)
