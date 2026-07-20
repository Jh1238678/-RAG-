"""对话问答路由。"""
import json

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.config import settings
from app.core.exceptions import InvalidParamError
from app.core.response import success_response
from app.db.session import get_db
from app.models.entities import ChatMessage
from app.models.schemas import (
    ChatRequest,
    ChatResponse,
    DeleteResponse,
    MessageOut,
    SessionCreateRequest,
    SessionCreateResponse,
    SessionHistoryOut,
    SessionListOut,
    SessionOut,
    SessionRenameRequest,
    SourceChunk,
)
from app.repositories.chat_repo import ChatRepo
from app.services.chat_service import ChatService
from app.utils.id_generator import gen_uuid

router = APIRouter()


@router.post("/chat/session")
async def create_session(
    req: SessionCreateRequest,
    db: Session = Depends(get_db),
):
    """新建会话。"""
    chat_repo = ChatRepo(db)
    session_id = gen_uuid()
    chat_repo.create_session(session_id, title=req.title, document_ids=req.document_ids)
    return success_response(SessionCreateResponse(session_id=session_id).model_dump())


@router.get("/chat/sessions")
async def list_sessions(
    limit: int = 100,
    db: Session = Depends(get_db),
):
    """列出所有会话（按创建时间倒序）。"""
    chat_repo = ChatRepo(db)
    sessions = chat_repo.list_sessions(limit=limit)

    items = []
    for s in sessions:
        # 解析 document_ids
        doc_ids = None
        if s.document_ids:
            try:
                doc_ids = json.loads(s.document_ids)
            except Exception:
                doc_ids = None
        items.append(SessionOut(
            id=s.id,
            title=s.title,
            document_ids=doc_ids,
            message_count=chat_repo.count_messages(s.id),
            created_at=s.created_at,
            updated_at=s.updated_at,
        ))

    return success_response(SessionListOut(total=len(items), items=items).model_dump())


@router.delete("/chat/session/{session_id}")
async def delete_session(
    session_id: str,
    db: Session = Depends(get_db),
):
    """删除会话及其所有消息。

    依赖 ChatSession.messages 的 cascade="all, delete-orphan"，
    删除会话时会自动级联删除其下所有 ChatMessage。
    """
    chat_repo = ChatRepo(db)
    deleted = chat_repo.delete_session(session_id)
    if not deleted:
        raise InvalidParamError("会话不存在或已删除")
    return success_response(DeleteResponse(deleted=True).model_dump())


@router.patch("/chat/session/{session_id}/title")
async def rename_session(
    session_id: str,
    req: SessionRenameRequest,
    db: Session = Depends(get_db),
):
    """重命名会话标题。

    Args:
        session_id: 会话 ID
        req.title: 新标题（1-100 字符）

    Returns:
        更新后的会话信息
    """
    chat_repo = ChatRepo(db)
    session = chat_repo.update_session_title(session_id, req.title)
    if not session:
        raise InvalidParamError("会话不存在")

    doc_ids = None
    if session.document_ids:
        try:
            doc_ids = json.loads(session.document_ids)
        except Exception:
            doc_ids = None

    return success_response(SessionOut(
        id=session.id,
        title=session.title,
        document_ids=doc_ids,
        message_count=chat_repo.count_messages(session.id),
        created_at=session.created_at,
        updated_at=session.updated_at,
    ).model_dump())


@router.post("/chat")
async def chat(
    req: ChatRequest,
    db: Session = Depends(get_db),
):
    """问答接口（非流式）。"""
    if not req.question.strip():
        raise InvalidParamError("问题不能为空")

    chat_service = ChatService(db)
    result = chat_service.answer(
        question=req.question,
        session_id=req.session_id,
        document_ids=req.document_ids or None,
        mode=req.mode,
    )
    return success_response(ChatResponse(**result).model_dump())


@router.post("/chat/stream")
async def chat_stream(
    req: ChatRequest,
    db: Session = Depends(get_db),
):
    """问答接口（SSE 流式）。

    返回 Server-Sent Events 流：
        data: {"type": "meta", "session_id": ..., "mode": ..., "rewritten_query": ..., "from_cache": bool}
        data: {"type": "sources", "sources": [...]}
        data: {"type": "delta", "content": "..."}
        data: {"type": "done", "grounded": ..., "verifier_result": ..., "from_cache": bool}
    """
    if not req.question.strip():
        raise InvalidParamError("问题不能为空")

    if not settings.SSE_ENABLED:
        # 未启用流式：退化为非流式接口
        chat_service = ChatService(db)
        result = chat_service.answer(
            question=req.question,
            session_id=req.session_id,
            document_ids=req.document_ids or None,
            mode=req.mode,
        )
        return success_response(ChatResponse(**result).model_dump())

    chat_service = ChatService(db)

    def event_generator():
        try:
            for event in chat_service.answer_stream(
                question=req.question,
                session_id=req.session_id,
                document_ids=req.document_ids or None,
                mode=req.mode,
            ):
                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
        except Exception as e:
            error_event = {"type": "error", "message": f"流式问答失败: {e}"}
            yield f"data: {json.dumps(error_event, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # 禁用 nginx 缓冲
        },
    )


@router.get("/chat/session/{session_id}")
async def get_session_history(
    session_id: str,
    limit: int = 50,
    db: Session = Depends(get_db),
):
    """获取会话历史。"""
    chat_repo = ChatRepo(db)
    messages = chat_repo.get_history(session_id, limit=limit)

    # 解析 source_chunks JSON
    out_msgs = []
    for m in messages:
        sources = None
        if m.source_chunks:
            try:
                raw = json.loads(m.source_chunks)
                sources = [SourceChunk(**s) for s in raw]
            except Exception:
                sources = None
        out_msgs.append(MessageOut(
            id=m.id,
            role=m.role,
            content=m.content,
            source_chunks=sources,
            rewritten_query=m.rewritten_query,
            created_at=m.created_at,
        ))

    return success_response(SessionHistoryOut(
        session_id=session_id,
        messages=out_msgs,
    ).model_dump())
