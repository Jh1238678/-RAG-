"""会话数据访问层。"""
import json
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.entities import ChatMessage, ChatSession


class ChatRepo:
    """chat_sessions + chat_messages 表 CRUD。"""

    def __init__(self, db: Session):
        self.db = db

    # ---- 会话 ----
    def create_session(
        self, session_id: str, title: Optional[str] = None, document_ids: list[str] | None = None
    ) -> ChatSession:
        session = ChatSession(
            id=session_id,
            title=title,
            document_ids=json.dumps(document_ids, ensure_ascii=False) if document_ids else None,
        )
        self.db.add(session)
        self.db.commit()
        self.db.refresh(session)
        return session

    def get_session(self, session_id: str) -> Optional[ChatSession]:
        return self.db.get(ChatSession, session_id)

    def get_session_document_ids(self, session_id: str) -> list[str]:
        """获取会话绑定的文档 ID 列表。"""
        session = self.get_session(session_id)
        if not session or not session.document_ids:
            return []
        return json.loads(session.document_ids)

    def list_sessions(self, limit: int = 100) -> list[ChatSession]:
        """列出所有会话，按创建时间倒序。"""
        stmt = (
            select(ChatSession)
            .order_by(ChatSession.created_at.desc())
            .limit(limit)
        )
        return list(self.db.execute(stmt).scalars().all())

    def delete_session(self, session_id: str) -> bool:
        """删除会话及其所有消息（级联删除）。

        Returns:
            True 若找到并删除了会话；False 若会话不存在。
        """
        session = self.get_session(session_id)
        if not session:
            return False
        # 依赖 relationship cascade="all, delete-orphan" 级联删除消息
        self.db.delete(session)
        self.db.commit()
        return True

    def update_session_title(self, session_id: str, title: str) -> Optional[ChatSession]:
        """更新会话标题。

        Returns:
            更新后的 ChatSession；若会话不存在返回 None。
        """
        session = self.get_session(session_id)
        if not session:
            return None
        session.title = title
        self.db.commit()
        self.db.refresh(session)
        return session

    def count_messages(self, session_id: str) -> int:
        """统计会话消息数。"""
        from sqlalchemy import func
        stmt = select(func.count(ChatMessage.id)).where(ChatMessage.session_id == session_id)
        return int(self.db.execute(stmt).scalar() or 0)

    # ---- 消息 ----
    def add_message(self, message: ChatMessage) -> ChatMessage:
        self.db.add(message)
        self.db.commit()
        self.db.refresh(message)
        return message

    def get_history(self, session_id: str, limit: int = 20) -> list[ChatMessage]:
        """获取会话历史消息，按时间正序。"""
        stmt = (
            select(ChatMessage)
            .where(ChatMessage.session_id == session_id)
            .order_by(ChatMessage.created_at.desc())
            .limit(limit)
        )
        msgs = list(self.db.execute(stmt).scalars().all())
        msgs.reverse()  # 反转为正序
        return msgs

    def get_recent_pairs(self, session_id: str, turns: int) -> list[ChatMessage]:
        """获取最近 N 轮（2*N 条）消息用于多轮上下文。"""
        return self.get_history(session_id, limit=turns * 2)
