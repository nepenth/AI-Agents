"""
Tests for database connectivity and configuration.
"""
import pytest
from sqlalchemy import text

from app.database import get_engine, get_session_factory, init_db


@pytest.mark.asyncio
async def test_database_engine_creation(test_settings):
    """Test that database engine can be created."""
    # Mock the get_settings function to return test settings
    from unittest.mock import patch
    
    with patch('app.database.get_settings', return_value=test_settings):
        engine = get_engine()
        assert engine is not None
        
        # Test connection
        async with engine.begin() as conn:
            result = await conn.execute(text("SELECT 1"))
            assert result.scalar() == 1


@pytest.mark.asyncio
async def test_session_factory_creation(test_settings):
    """Test that session factory can be created."""
    from unittest.mock import patch
    
    with patch('app.database.get_settings', return_value=test_settings):
        session_factory = get_session_factory()
        assert session_factory is not None
        
        # Test session creation
        async with session_factory() as session:
            result = await session.execute(text("SELECT 1"))
            assert result.scalar() == 1


@pytest.mark.asyncio
async def test_database_session_dependency(test_db_session):
    """Test database session dependency."""
    # Test that we can execute queries with the session
    result = await test_db_session.execute(text("SELECT 1 as test_value"))
    row = result.fetchone()
    assert row.test_value == 1


@pytest.mark.asyncio
async def test_init_db_function(test_settings):
    """Test database initialization function."""
    from unittest.mock import patch, AsyncMock
    
    # Mock the database operations
    mock_engine = AsyncMock()
    mock_conn = AsyncMock()
    mock_engine.begin.return_value.__aenter__.return_value = mock_conn
    
    with patch('app.database.get_engine', return_value=mock_engine):
        with patch('app.database.get_settings', return_value=test_settings):
            await init_db()
            
            # Verify that the engine.begin() was called
            mock_engine.begin.assert_called_once()
            
            # Verify that pgvector extension creation was attempted
            mock_conn.execute.assert_called()
            mock_conn.run_sync.assert_called()