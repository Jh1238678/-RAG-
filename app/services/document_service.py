"""文档处理服务。

编排文档入库主流程：保存 -> 解析 -> 清洗 -> 分块 -> 向量化 -> 索引 -> 持久化。
"""
import json
import tempfile
from pathlib import Path
from typing import Optional

from sqlalchemy.orm import Session

from app.config import settings
from app.core.exceptions import DocumentFailedError
from app.core.logger import logger
from app.models.entities import Chunk, Document
from app.parsers.base import BaseParser
from app.repositories.document_repo import ChunkRepo, DocumentRepo
from app.repositories.index_repo import IndexRepo
from app.services.chunk_service import ChunkService
from app.services.embedding_service import EmbeddingService
from app.services.vector_service import VectorService
from app.utils.file_loader import delete_file, save_upload_file, validate_file_type
from app.utils.id_generator import gen_uuid
from app.utils.text_cleaner import clean_text


# 解析器工厂（延迟导入，避免重依赖未安装时启动失败）
def _get_parser_cls(file_type: str) -> type[BaseParser]:
    if file_type == "pdf":
        from app.parsers.pdf_parser import PDFParser
        return PDFParser
    elif file_type == "docx":
        from app.parsers.docx_parser import DocxParser
        return DocxParser
    elif file_type == "md":
        from app.parsers.markdown_parser import MarkdownParser
        return MarkdownParser
    elif file_type == "txt":
        from app.parsers.txt_parser import TxtParser
        return TxtParser
    raise ValueError(f"不支持的文件类型: {file_type}")


def get_parser(file_type: str) -> BaseParser:
    """根据文件类型获取解析器实例。"""
    return _get_parser_cls(file_type)()


class DocumentService:
    """文档处理服务：编排入库主流程。"""

    def __init__(self, db: Session):
        self.db = db
        self.doc_repo = DocumentRepo(db)
        self.chunk_repo = ChunkRepo(db)
        self.index_repo = IndexRepo(db)

    def ingest(self, file_bytes: bytes, original_filename: str) -> Document:
        """完整入库流程。返回最终 Document。"""
        # 1. 校验类型
        file_type = validate_file_type(original_filename)

        # 2. 保存原始文件
        with tempfile.NamedTemporaryFile(delete=False, suffix=f".{file_type}") as tmp:
            tmp.write(file_bytes)
            tmp_path = tmp.name
        rel_path, abs_path = save_upload_file(tmp_path, original_filename)
        file_size = len(file_bytes)

        # 3. 创建文档记录
        document = Document(
            id=gen_uuid(),
            file_name=original_filename,
            file_type=file_type,
            file_path=rel_path,
            file_size=file_size,
            status="parsing",
        )
        self.doc_repo.create(document)
        document_id = document.id

        try:
            # 4. 解析
            parser = get_parser(file_type)
            parsed = parser.parse(abs_path)

            # 5. 清洗
            cleaned_text = clean_text(parsed.text)

            # 6. 分块
            chunk_service = ChunkService()
            chunk_datas = chunk_service.split(cleaned_text, parsed.pages)
            if not chunk_datas:
                raise DocumentFailedError("文档内容为空或解析后无可分块文本")

            # 7. 向量化
            embedding_service = EmbeddingService()
            vectors = embedding_service.embed_batch([c.content for c in chunk_datas])

            # 8. 写入 FAISS
            vector_service = VectorService()
            start_id = vector_service.next_faiss_id()
            faiss_ids = list(range(start_id, start_id + len(chunk_datas)))
            vector_service.add(vectors, faiss_ids)

            # 9. 记录索引映射
            mappings = [
                {
                    "chunk_id": "",  # 稍后填充
                    "document_id": document_id,
                    "faiss_id": faiss_ids[i],
                }
                for i in range(len(chunk_datas))
            ]

            # 10. 持久化 chunk
            chunk_entities = []
            for i, cd in enumerate(chunk_datas):
                chunk_id = gen_uuid()
                mappings[i]["chunk_id"] = chunk_id
                chunk_entities.append(
                    Chunk(
                        id=chunk_id,
                        document_id=document_id,
                        chunk_index=cd.chunk_index,
                        content=cd.content,
                        page_num=cd.page_num,
                        char_count=cd.char_count,
                        token_count=cd.token_count,
                        meta=json.dumps(cd.metadata, ensure_ascii=False) if cd.metadata else None,
                    )
                )
            self.chunk_repo.batch_create(chunk_entities)
            self.index_repo.add_batch(mappings)

            # 11. 更新文档状态
            self.doc_repo.update_status(
                document_id, "indexed", chunk_count=len(chunk_datas)
            )
            logger.info(
                f"文档入库成功: id={document_id}, chunks={len(chunk_datas)}"
            )

        except Exception as e:
            logger.error(f"文档入库失败: id={document_id}, error={e}")
            self.doc_repo.update_status(
                document_id, "failed", error_msg=str(e)[:500]
            )
            raise DocumentFailedError(str(e))

        # 重新加载返回
        return self.doc_repo.get_by_id(document_id)

    def delete(self, document_id: str) -> bool:
        """删除文档：DB + FAISS + 原始文件。"""
        document = self.doc_repo.get_by_id(document_id)
        if not document:
            return False

        # 1. 删除 FAISS 向量
        faiss_ids = self.index_repo.get_faiss_ids_by_document(document_id)
        if faiss_ids:
            VectorService().remove_ids(faiss_ids)

        # 2. 删除索引映射
        self.index_repo.delete_by_document(document_id)

        # 3. 删除 chunks（cascade 会自动删，但显式删更安全）
        self.chunk_repo.delete_by_document(document_id)

        # 4. 删除文档记录
        self.doc_repo.delete(document_id)

        # 5. 删除原始文件
        delete_file(document.file_path)

        logger.info(f"文档删除完成: id={document_id}")
        return True
