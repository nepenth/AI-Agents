"""
Repository for synthesis document operations.
"""
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import SynthesisDocument
from .base import BaseRepository


class SynthesisDocumentRepository(BaseRepository[SynthesisDocument]):
    """Repository for synthesis document operations."""
    
    def __init__(self, session: AsyncSession):
        super().__init__(SynthesisDocument, session)


_synthesis_repo_singleton = None

def get_synthesis_repository() -> SynthesisDocumentRepository:  # type: ignore[name-defined]
    global _synthesis_repo_singleton
    if _synthesis_repo_singleton is None:
        from app.database.connection import get_session_factory
        session_factory = get_session_factory()
        _synthesis_repo_singleton = SynthesisDocumentRepository(session_factory())  # type: ignore[arg-type]
    return _synthesis_repo_singleton