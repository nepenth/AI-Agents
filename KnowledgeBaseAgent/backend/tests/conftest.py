"""
Pytest configuration and fixtures.
"""
import pytest
import asyncio
from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.config import Settings


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def test_settings():
    """Test settings with in-memory database."""
    return Settings(
        DATABASE_URL="sqlite+aiosqlite:///:memory:",
        DATABASE_ECHO=False,
        REDIS_URL="redis://localhost:6379",
        CELERY_BROKER_URL="redis://localhost:6379/0",
        CELERY_RESULT_BACKEND="redis://localhost:6379/0",
        SECRET_KEY="test-secret-key",
        DEBUG=True,
        LOG_LEVEL="INFO"
    )


@pytest.fixture
async def test_db_engine(test_settings):
    """Create test database engine."""
    engine = create_async_engine(
        test_settings.DATABASE_URL,
        echo=test_settings.DATABASE_ECHO,
        poolclass=StaticPool,
        connect_args={"check_same_thread": False}
    )
    
    # Create all tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    yield engine
    
    # Clean up
    await engine.dispose()


@pytest.fixture
async def test_db_session(test_db_engine):
    """Create test database session."""
    # Import models to ensure they're registered
    from app.models import (
        ContentItem,
        KnowledgeItem,
        Embedding,
        SynthesisDocument,
        Task,
        ChatSession,
        ChatMessage,
    )
    
    # Create all tables for this test session
    from app.database.base import Base
    async with test_db_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    async_session = async_sessionmaker(
        bind=test_db_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    
    session = async_session()
    try:
        yield session
    finally:
        await session.close()
        # Clean up after test
        async with test_db_engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)