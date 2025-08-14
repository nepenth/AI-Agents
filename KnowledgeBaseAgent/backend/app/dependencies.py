"""
FastAPI dependency injection utilities.
"""
from typing import AsyncGenerator
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db_session
from app.config import get_settings, Settings


async def get_database() -> AsyncGenerator[AsyncSession, None]:
    """Database session dependency."""
    async for session in get_db_session():
        yield session


def get_app_settings() -> Settings:
    """Application settings dependency."""
    return get_settings()