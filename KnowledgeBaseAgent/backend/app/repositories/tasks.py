"""
Repository for task operations.
"""
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Task
from .base import BaseRepository


class TaskRepository(BaseRepository[Task]):
    """Repository for task operations."""
    
    def __init__(self, session: AsyncSession):
        super().__init__(Task, session)


_task_repo_singleton = None

def get_task_repository() -> TaskRepository:  # type: ignore[name-defined]
    global _task_repo_singleton
    if _task_repo_singleton is None:
        from app.database.connection import get_session_factory
        session_factory = get_session_factory()
        _task_repo_singleton = TaskRepository(session_factory())  # type: ignore[arg-type]
    return _task_repo_singleton