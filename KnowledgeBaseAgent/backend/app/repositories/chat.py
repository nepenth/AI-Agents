"""
Repository for chat session and message operations.
"""
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ChatSession, ChatMessage
from .base import BaseRepository


class ChatSessionRepository(BaseRepository[ChatSession]):
    """Repository for chat session operations."""
    
    def __init__(self, session: AsyncSession):
        super().__init__(ChatSession, session)


class ChatMessageRepository(BaseRepository[ChatMessage]):
    """Repository for chat message operations."""
    
    def __init__(self, session: AsyncSession):
        super().__init__(ChatMessage, session)


# Factory helpers
_chat_session_repo_singleton = None
_chat_message_repo_singleton = None

def get_chat_repository():
    """Return tuple of (ChatSessionRepository, ChatMessageRepository)."""
    global _chat_session_repo_singleton, _chat_message_repo_singleton
    if _chat_session_repo_singleton is None or _chat_message_repo_singleton is None:
        from app.database.connection import get_session_factory
        session_factory = get_session_factory()
        session = session_factory()
        _chat_session_repo_singleton = ChatSessionRepository(session)  # type: ignore[arg-type]
        _chat_message_repo_singleton = ChatMessageRepository(session)  # type: ignore[arg-type]
    return _chat_session_repo_singleton, _chat_message_repo_singleton