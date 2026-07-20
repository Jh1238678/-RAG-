"""文档数据访问层。"""
import json
from typing import Optional

from sqlalchemy import select, update, func
from sqlalchemy.orm import Session

from app.models.entities import Chunk, Document


class DocumentRepo:
    """documents 表 CRUD。"""

    def __init__(self, db: Session):
        self.db = db

    def create(self, document: Document) -> Document:
        self.db.add(document)
        self.db.commit()
        self.db.refresh(document)
        return document

    def get_by_id(self, document_id: str) -> Optional[Document]:
        return self.db.get(Document, document_id)

    def list_documents(
        self, status: Optional[str] = None, page: int = 1, page_size: int = 20
    ) -> tuple[list[Document], int]:
        """分页查询文档列表。返回 (items, total)。"""
        stmt = select(Document)
        if status:
            stmt = stmt.where(Document.status == status)
        # 总数
        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = self.db.execute(count_stmt).scalar() or 0
        # 分页
        stmt = stmt.order_by(Document.created_at.desc())
        stmt = stmt.offset((page - 1) * page_size).limit(page_size)
        items = list(self.db.execute(stmt).scalars().all())
        return items, total

    def update_status(
        self, document_id: str, status: str,
        chunk_count: Optional[int] = None,
        summary: Optional[str] = None,
        error_msg: Optional[str] = None,
    ) -> None:
        """更新文档状态。"""
        values: dict = {"status": status}
        if chunk_count is not None:
            values["chunk_count"] = chunk_count
        if summary is not None:
            values["summary"] = summary
        if error_msg is not None:
            values["error_msg"] = error_msg
        self.db.execute(
            update(Document).where(Document.id == document_id).values(**values)
        )
        self.db.commit()

    def delete(self, document_id: str) -> bool:
        """删除文档（chunks 通过外键 cascade 级联删除）。"""
        doc = self.get_by_id(document_id)
        if not doc:
            return False
        self.db.delete(doc)
        self.db.commit()
        return True


class ChunkRepo:
    """chunks 表 CRUD。"""

    def __init__(self, db: Session):
        self.db = db

    def batch_create(self, chunks: list[Chunk]) -> None:
        self.db.add_all(chunks)
        self.db.commit()

    def list_by_document(self, document_id: str) -> list[Chunk]:
        stmt = (
            select(Chunk)
            .where(Chunk.document_id == document_id)
            .order_by(Chunk.chunk_index)
        )
        return list(self.db.execute(stmt).scalars().all())

    def get_by_ids(self, chunk_ids: list[str]) -> list[Chunk]:
        if not chunk_ids:
            return []
        stmt = select(Chunk).where(Chunk.id.in_(chunk_ids))
        return list(self.db.execute(stmt).scalars().all())

    def list_by_documents(self, document_ids: list[str]) -> list[Chunk]:
        """多文档联合查询所有 chunk。"""
        if not document_ids:
            return []
        stmt = select(Chunk).where(Chunk.document_id.in_(document_ids))
        return list(self.db.execute(stmt).scalars().all())

    def delete_by_document(self, document_id: str) -> int:
        """删除某文档的全部 chunk，返回删除数。"""
        chunks = self.list_by_document(document_id)
        for c in chunks:
            self.db.delete(c)
        self.db.commit()
        return len(chunks)
