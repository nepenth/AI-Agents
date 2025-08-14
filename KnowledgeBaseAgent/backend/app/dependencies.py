"""
FastAPI dependency injection utilities.
"""
from typing import AsyncGenerator, Optional
from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi.security import HTTPAuthorizationCredentials

from app.database import get_db_session
from app.config import get_settings, Settings
from app.models.auth import User


async def get_database() -> AsyncGenerator[AsyncSession, None]:
    """Database session dependency."""
    async for session in get_db_session():
        yield session


def get_app_settings() -> Settings:
    """Application settings dependency."""
    return get_settings()


# Import authentication dependencies from security module
from app.security import (
    get_current_user,
    get_current_user_optional,
    get_current_user_or_api_key,
    get_api_key_user,
    require_permissions,
    require_roles,
    admin_required,
    Permissions,
    Roles
)

# Re-export for convenience
__all__ = [
    "get_database",
    "get_app_settings",
    "get_current_user",
    "get_current_user_optional", 
    "get_current_user_or_api_key",
    "get_api_key_user",
    "require_permissions",
    "require_roles",
    "admin_required",
    "Permissions",
    "Roles"
]