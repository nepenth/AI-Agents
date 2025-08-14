"""
Repository for knowledge item and embedding operations.
"""
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import KnowledgeItem, Embedding
from .base import BaseRepository


class KnowledgeItemRepository(BaseRepository[KnowledgeItem]):
    """Repository for knowledge item operations."""
    
    def __init__(self, session: AsyncSession):
        super().__init__(KnowledgeItem, session)


# Factory helpers used by task modules
_knowledge_repo_singleton = None

def get_knowledge_repository() -> KnowledgeItemRepository:  # type: ignore[name-defined]
    global _knowledge_repo_singleton
    if _knowledge_repo_singleton is None:
        from app.database.connection import get_session_factory
        session_factory = get_session_factory()
        _knowledge_repo_singleton = KnowledgeItemRepository(session_factory())  # type: ignore[arg-type]
    return _knowledge_repo_singleton


class EmbeddingRepository(BaseRepository[Embedding]):
    """Repository for embedding operations."""
    
    def __init__(self, session: AsyncSession):
        super().__init__(Embedding, session)