"""重建 FAISS 索引。

从数据库读取所有 chunk，重新生成向量并重建索引。
用于索引损坏或更换 embedding 模型后恢复。
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import numpy as np
from app.core.logger import setup_logging, logger
from app.db.session import SessionLocal
from app.repositories.document_repo import ChunkRepo
from app.repositories.index_repo import IndexRepo
from app.services.embedding_service import EmbeddingService
from app.services.vector_service import VectorService


def rebuild_index():
    """全量重建 FAISS 索引。"""
    setup_logging()
    logger.info("开始重建 FAISS 索引...")

    db = SessionLocal()
    try:
        # 取所有 chunk
        from app.models.entities import Chunk
        from sqlalchemy import select
        stmt = select(Chunk).order_by(Chunk.created_at)
        chunks = list(db.execute(stmt).scalars().all())

        if not chunks:
            logger.warning("数据库无 chunk，跳过重建")
            return

        logger.info(f"共 {len(chunks)} 个 chunk 需要重新向量化")

        # 向量化
        embedding_service = EmbeddingService()
        texts = [c.content for c in chunks]
        vectors = embedding_service.embed_batch(texts)

        # 分配 faiss_id
        faiss_ids = list(range(len(chunks)))

        # 重建索引
        vector_service = VectorService()
        vector_service.rebuild(vectors, faiss_ids)

        # 清空并重建映射表
        from app.repositories.index_repo import _index_mapping_table
        from sqlalchemy import delete
        table = _index_mapping_table
        db.execute(delete(table))

        mappings = [
            {
                "chunk_id": c.id,
                "document_id": c.document_id,
                "faiss_id": faiss_ids[i],
            }
            for i, c in enumerate(chunks)
        ]
        index_repo = IndexRepo(db)
        index_repo.add_batch(mappings)

        logger.info(f"索引重建完成: {len(chunks)} 个向量, 维度={vectors.shape[1]}")
    finally:
        db.close()


if __name__ == "__main__":
    rebuild_index()
