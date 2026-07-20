"""API 请求与响应 Pydantic 模型。

定义所有接口的入参和出参结构，保持 API 契约清晰。
"""
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


# ============ 通用 ============
class ApiResponse(BaseModel):
    """统一响应包装。"""
    code: int = 0
    message: str = "success"
    data: Optional[Any] = None


# ============ 文档相关 ============
class DocumentOut(BaseModel):
    """文档列表/详情输出。"""
    id: str
    file_name: str
    file_type: str
    file_size: Optional[int] = None
    status: str
    chunk_count: int = 0
    summary: Optional[str] = None
    error_msg: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class DocumentListOut(BaseModel):
    """文档列表分页响应。"""
    total: int
    items: list[DocumentOut]


class ChunkPreview(BaseModel):
    """chunk 预览。"""
    id: str
    chunk_index: int
    content: str
    page_num: Optional[int] = None
    char_count: Optional[int] = None


class DocumentDetailOut(DocumentOut):
    """文档详情：包含 chunk 预览。"""
    chunks_preview: list[ChunkPreview] = []


class UploadResponse(BaseModel):
    """上传响应。"""
    document_id: str
    file_name: str
    status: str
    chunk_count: int = 0


class DeleteResponse(BaseModel):
    deleted: bool = True


# ============ 摘要 ============
class SummaryResponse(BaseModel):
    document_id: str
    summary: str
    segment_count: int = 1


# ============ 会话 ============
class SessionCreateRequest(BaseModel):
    title: Optional[str] = None
    document_ids: list[str] = Field(default_factory=list)


class SessionCreateResponse(BaseModel):
    session_id: str


class SessionOut(BaseModel):
    """会话列表项输出。"""
    id: str
    title: Optional[str] = None
    document_ids: Optional[list[str]] = None
    message_count: int = 0
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class SessionListOut(BaseModel):
    """会话列表响应。"""
    total: int
    items: list[SessionOut]


class SessionRenameRequest(BaseModel):
    """会话重命名请求。"""
    title: str = Field(..., min_length=1, max_length=100, description="新标题，1-100 字符")


# ============ 问答 ============
class ChatRequest(BaseModel):
    """问答请求。"""
    question: str = Field(..., min_length=1, max_length=2000)
    session_id: Optional[str] = None
    document_ids: list[str] = Field(default_factory=list)
    # 问答模式：strict（严格依据文档，不可外推） | open（允许适度解释）
    mode: str = Field(default="open", pattern="^(strict|open)$")


class SourceChunk(BaseModel):
    """引用来源。"""
    chunk_id: str
    document_id: str
    document_name: str
    page_num: Optional[int] = None
    snippet: str
    score: float


class VerifierResult(BaseModel):
    """答案支持性校验结果。"""
    verdict: str  # supported | partial | unsupported
    reason: Optional[str] = None
    unsupported_spans: list[str] = []


class ChatResponse(BaseModel):
    """问答响应。"""
    session_id: str
    answer: str
    rewritten_query: Optional[str] = None
    sources: list[SourceChunk] = []
    # 模式相关字段
    mode: str = "open"
    # 严格模式：答案是否被证据充分支持
    grounded: Optional[bool] = None
    # 严格模式：未命中拒答原因
    unsupported_reason: Optional[str] = None
    # 开放模式：补充说明标识
    supplement_note: Optional[str] = None
    # 严格模式可选：答案校验结果
    verifier_result: Optional[VerifierResult] = None
    # 是否来自语义缓存
    from_cache: Optional[bool] = None


class MessageOut(BaseModel):
    """历史消息。"""
    id: str
    role: str
    content: str
    source_chunks: Optional[list[SourceChunk]] = None
    rewritten_query: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class SessionHistoryOut(BaseModel):
    """会话历史响应。"""
    session_id: str
    messages: list[MessageOut]


# ============ 健康检查 ============
class HealthOut(BaseModel):
    status: str
    version: str
    db: str
    faiss_loaded: bool
