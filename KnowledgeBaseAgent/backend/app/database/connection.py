"""
Database connection management and session handling.
"""
import logging
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy import text

from app.config import get_settings
from .base import Base

logger = logging.getLogger(__name__)


# Global database engine and session factory
engine = None
async_session_factory = None


def get_engine():
    """Get the database engine, creating it if necessary."""
    global engine
    if engine is None:
        settings = get_settings()
        engine = create_async_engine(
            settings.DATABASE_URL,
            echo=settings.DATABASE_ECHO,
            future=True,
            pool_pre_ping=True,
            pool_recycle=300,
        )
    return engine


def get_session_factory():
    """Get the async session factory, creating it if necessary."""
    global async_session_factory
    if async_session_factory is None:
        async_session_factory = async_sessionmaker(
            bind=get_engine(),
            class_=AsyncSession,
            expire_on_commit=False,
        )
    return async_session_factory


async def get_db_session() -> AsyncSession:
    """Dependency to get database session."""
    async_session = get_session_factory()
    async with async_session() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db():
    """Initialize database connection and create tables."""
    try:
        # Import all models to ensure they're registered with SQLAlchemy
        from app.models import (
            ContentItem,
            KnowledgeItem,
            Embedding,
            SynthesisDocument,
            Task,
            ChatSession,
            ChatMessage,
        )
        
        engine = get_engine()
        
        # Test database connection
        async with engine.begin() as conn:
            # Enable pgvector extension
            await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
            logger.info("pgvector extension enabled")
            
            # Create all tables
            await conn.run_sync(Base.metadata.create_all)
            logger.info("Database tables created successfully")
            
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
        raise


async def close_db():
    """Close database connections."""
    global engine
    if engine:
        await engine.dispose()
        logger.info("Database connections closed")