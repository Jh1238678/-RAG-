"""索引映射数据访问层。

维护 chunk_id ↔ FAISS 内部 vector_id 的映射关系。
SQLite 中用一张独立的 index_mapping 表存储。
"""
from typing import Optional

from sqlalchemy import Column, Integer, String, Table, select, delete
from sqlalchemy.orm import Session

from app.db.base import Base


# 模块级单例 Table 定义（避免重复定义）
_index_mapping_table = Table(
    "index_mapping",
    Base.metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("chunk_id", String(36), nullable=False, index=True),
    Column("document_id", String(36), nullable=False, index=True),
    Column("faiss_id", Integer, nullable=False),
    extend_existing=True,
)


class IndexRepo:
    """索引映射关系维护。"""

    def __init__(self, db: Session):
        self.db = db
        self.table = _index_mapping_table
        # 确保表存在
        Base.metadata.create_all(bind=db.bind, tables=[self.table])

    def add_batch(self, mappings: list[dict]) -> None:
        """批量添加映射。mappings: [{chunk_id, document_id, faiss_id}]"""
        if not mappings:
            return
        self.db.execute(self.table.insert(), mappings)
        self.db.commit()

    def get_faiss_ids_by_document(self, document_id: str) -> list[int]:
        """获取某文档对应的所有 FAISS vector_id。"""
        stmt = select(self.table.c.faiss_id).where(self.table.c.document_id == document_id)
        return [row[0] for row in self.db.execute(stmt)]

    def get_chunk_id_by_faiss_id(self, faiss_id: int) -> Optional[str]:
        stmt = select(self.table.c.chunk_id).where(self.table.c.faiss_id == faiss_id)
        return self.db.execute(stmt).scalar_one_or_none()

    def get_all_mappings(self) -> list[dict]:
        """获取全部映射，用于重建索引。"""
        stmt = select(self.table.c.chunk_id, self.table.c.document_id, self.table.c.faiss_id)
        return [
            {"chunk_id": r[0], "document_id": r[1], "faiss_id": r[2]}
            for r in self.db.execute(stmt)
        ]

    def delete_by_document(self, document_id: str) -> int:
        """删除某文档的全部映射，返回删除数。"""
        from sqlalchemy import func
        count_stmt = select(func.count()).select_from(self.table).where(
            self.table.c.document_id == document_id
        )
        count = self.db.execute(count_stmt).scalar() or 0
        self.db.execute(delete(self.table).where(self.table.c.document_id == document_id))
        self.db.commit()
        return count

    def get_max_faiss_id(self) -> int:
        """获取当前最大 faiss_id，用于新增时分配 ID。"""
        from sqlalchemy import func
        stmt = select(func.max(self.table.c.faiss_id))
        result = self.db.execute(stmt).scalar()
        return result if result is not None else -1
