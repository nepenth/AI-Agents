"""
Database Connection Management and Utilities

This module provides comprehensive database connection management, health checks,
and utilities for the Knowledge Base Agent following modern AI agent architecture patterns.
"""

import logging
import time
from contextlib import contextmanager
from typing import Optional, Dict, Any, Generator
from urllib.parse import urlparse
import sqlalchemy as sa
from sqlalchemy import create_engine, text, event
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError, OperationalError
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import QueuePool, StaticPool
from flask import current_app, g
from flask_sqlalchemy import SQLAlchemy

from .config import Config
from .models import db

logger = logging.getLogger(__name__)


class DatabaseConnectionManager:
    """
    Advanced database connection management with health checks, pooling,
    and performance monitoring for AI agent workloads.
    """
    
    def __init__(self, config: Config):
        self.config = config
        self.database_url = config.database_url
        self.is_postgresql = self._is_postgresql()
        self.engine: Optional[Engine] = None
        self.session_factory: Optional[sessionmaker] = None
        self._health_check_cache = {'last_check': 0, 'is_healthy': False}
        self._connection_stats = {
            'total_connections': 0,
            'active_connections': 0,
            'failed_connections': 0,
            'avg_connection_time': 0.0
        }
        
    def _is_postgresql(self) -> bool:
        """Check if the database URL is for PostgreSQL."""
        parsed = urlparse(self.database_url)
        return parsed.scheme in ('postgresql', 'postgresql+psycopg2', 'postgres')
    
    def _get_engine_config(self) -> Dict[str, Any]:
        """Get database engine configuration optimized for the database type."""
        base_config = {
            'echo': False,  # Set to True for SQL debugging
            'future': True,  # Use SQLAlchemy 2.0 style
        }
        
        if self.is_postgresql:
            # PostgreSQL configuration with connection pooling
            base_config.update({
                'poolclass': QueuePool,
                'pool_size': 10,  # Number of connections to maintain
                'max_overflow': 20,  # Additional connections beyond pool_size
                'pool_pre_ping': True,  # Validate connections before use
                'pool_recycle': 3600,  # Recycle connections after 1 hour
                'pool_timeout': 30,  # Timeout for getting connection from pool
                'connect_args': {
                    'connect_timeout': 10,
                    'application_name': 'knowledge_base_agent',
                    'options': '-c default_transaction_isolation=read_committed'
                }
            })
        else:
            # SQLite configuration
            base_config.update({
                'poolclass': StaticPool,
                'pool_pre_ping': True,
                'connect_args': {
                    'check_same_thread': False,
                    'timeout': 20,
                    'isolation_level': None  # Enable autocommit mode
                }
            })
            
        return base_config
    
    def initialize_engine(self) -> Engine:
        """Initialize the database engine with proper configuration."""
        if self.engine is not None:
            return self.engine
            
        try:
            start_time = time.time()
            engine_config = self._get_engine_config()
            
            self.engine = create_engine(self.database_url, **engine_config)
            
            # Add event listeners for monitoring
            self._setup_event_listeners(self.engine)
            
            # Create session factory
            self.session_factory = sessionmaker(bind=self.engine)
            
            connection_time = time.time() - start_time
            self._connection_stats['avg_connection_time'] = connection_time
            
            logger.info(f"✅ Database engine initialized successfully ({self.database_url.split('://')[0]}) in {connection_time:.3f}s")
            return self.engine
            
        except Exception as e:
            self._connection_stats['failed_connections'] += 1
            logger.error(f"❌ Failed to initialize database engine: {e}", exc_info=True)
            raise
    
    def _setup_event_listeners(self, engine: Engine) -> None:
        """Set up SQLAlchemy event listeners for monitoring and optimization."""
        
        @event.listens_for(engine, "connect")
        def set_sqlite_pragma(dbapi_connection, connection_record):
            """Configure SQLite for optimal performance."""
            if not self.is_postgresql:
                cursor = dbapi_connection.cursor()
                # Enable WAL mode for better concurrency
                cursor.execute("PRAGMA journal_mode=WAL")
                # Set synchronous mode for better performance
                cursor.execute("PRAGMA synchronous=NORMAL")
                # Enable foreign key constraints
                cursor.execute("PRAGMA foreign_keys=ON")
                # Set cache size (negative value = KB)
                cursor.execute("PRAGMA cache_size=-64000")  # 64MB cache
                cursor.close()
        
        @event.listens_for(engine, "checkout")
        def receive_checkout(dbapi_connection, connection_record, connection_proxy):
            """Track connection checkouts."""
            self._connection_stats['active_connections'] += 1
            self._connection_stats['total_connections'] += 1
        
        @event.listens_for(engine, "checkin")
        def receive_checkin(dbapi_connection, connection_record):
            """Track connection checkins."""
            self._connection_stats['active_connections'] = max(0, self._connection_stats['active_connections'] - 1)
    
    def get_session(self) -> Session:
        """Get a new database session."""
        if self.session_factory is None:
            self.initialize_engine()
        
        return self.session_factory()
    
    @contextmanager
    def get_session_context(self) -> Generator[Session, None, None]:
        """Get a database session with automatic cleanup."""
        session = self.get_session()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()
    
    def health_check(self, force_check: bool = False) -> Dict[str, Any]:
        """
        Perform comprehensive database health check.
        
        Args:
            force_check: Force a new health check, bypassing cache
            
        Returns:
            Dictionary with health check results
        """
        current_time = time.time()
        
        # Use cached result if recent (within 30 seconds) and not forced
        if not force_check and (current_time - self._health_check_cache['last_check']) < 30:
            return {
                'healthy': self._health_check_cache['is_healthy'],
                'cached': True,
                'timestamp': self._health_check_cache['last_check']
            }
        
        health_result = {
            'healthy': False,
            'database_type': 'postgresql' if self.is_postgresql else 'sqlite',
            'connection_stats': self._connection_stats.copy(),
            'checks': {},
            'timestamp': current_time,
            'cached': False
        }
        
        try:
            # Test basic connectivity
            start_time = time.time()
            with self.get_session_context() as session:
                result = session.execute(text("SELECT 1")).scalar()
                health_result['checks']['connectivity'] = {
                    'status': 'pass' if result == 1 else 'fail',
                    'response_time': time.time() - start_time
                }
            
            # Test table existence
            start_time = time.time()
            with self.get_session_context() as session:
                # Check if core tables exist
                if self.is_postgresql:
                    table_check = session.execute(text("""
                        SELECT COUNT(*) FROM information_schema.tables 
                        WHERE table_name IN ('knowledge_base_item', 'agent_state', 'celery_task_state')
                    """)).scalar()
                else:
                    table_check = session.execute(text("""
                        SELECT COUNT(*) FROM sqlite_master 
                        WHERE type='table' AND name IN ('knowledge_base_item', 'agent_state', 'celery_task_state')
                    """)).scalar()
                
                health_result['checks']['tables'] = {
                    'status': 'pass' if table_check >= 3 else 'fail',
                    'tables_found': table_check,
                    'response_time': time.time() - start_time
                }
            
            # Test write capability
            start_time = time.time()
            with self.get_session_context() as session:
                # Try to insert/update a setting
                session.execute(text("""
                    INSERT OR REPLACE INTO settings (key, value) 
                    VALUES ('health_check', :timestamp)
                """), {'timestamp': str(current_time)})
                
                health_result['checks']['write_access'] = {
                    'status': 'pass',
                    'response_time': time.time() - start_time
                }
            
            # Overall health status
            all_checks_passed = all(
                check['status'] == 'pass' 
                for check in health_result['checks'].values()
            )
            health_result['healthy'] = all_checks_passed
            
            # Update cache
            self._health_check_cache = {
                'last_check': current_time,
                'is_healthy': all_checks_passed
            }
            
            if all_checks_passed:
                logger.debug("✅ Database health check passed")
            else:
                logger.warning("⚠️ Database health check failed")
                
        except Exception as e:
            health_result['checks']['error'] = {
                'status': 'fail',
                'error': str(e),
                'error_type': type(e).__name__
            }
            self._connection_stats['failed_connections'] += 1
            logger.error(f"❌ Database health check failed: {e}", exc_info=True)
        
        return health_result
    
    def get_connection_stats(self) -> Dict[str, Any]:
        """Get current connection statistics."""
        stats = self._connection_stats.copy()
        
        if self.engine and hasattr(self.engine.pool, 'size'):
            stats.update({
                'pool_size': self.engine.pool.size(),
                'checked_in': self.engine.pool.checkedin(),
                'checked_out': self.engine.pool.checkedout(),
                'overflow': getattr(self.engine.pool, 'overflow', 0),
                'invalid': getattr(self.engine.pool, 'invalid', 0)
            })
        
        return stats
    
    def close_all_connections(self) -> None:
        """Close all database connections and clean up resources."""
        try:
            if self.engine:
                self.engine.dispose()
                logger.info("✅ Database connections closed successfully")
        except Exception as e:
            logger.error(f"❌ Error closing database connections: {e}", exc_info=True)
        finally:
            self.engine = None
            self.session_factory = None


# Global database connection manager instance
_db_manager: Optional[DatabaseConnectionManager] = None


def get_db_manager() -> DatabaseConnectionManager:
    """Get the global database connection manager instance."""
    global _db_manager
    
    if _db_manager is None:
        config = current_app.config.get('APP_CONFIG')
        if config is None:
            raise RuntimeError("Application configuration not found")
        _db_manager = DatabaseConnectionManager(config)
    
    return _db_manager


def get_db_session() -> Session:
    """Get a database session for the current request context."""
    if 'db_session' not in g:
        db_manager = get_db_manager()
        g.db_session = db_manager.get_session()
    
    return g.db_session


@contextmanager
def get_db_session_context() -> Generator[Session, None, None]:
    """Get a database session with automatic cleanup (context manager)."""
    db_manager = get_db_manager()
    with db_manager.get_session_context() as session:
        yield session


def init_database_manager(app) -> None:
    """Initialize database manager with Flask app."""
    
    @app.teardown_appcontext
    def close_db_session(error):
        """Close database session at the end of request."""
        session = g.pop('db_session', None)
        if session is not None:
            try:
                if error:
                    session.rollback()
                else:
                    session.commit()
            except Exception as e:
                logger.error(f"Error during session cleanup: {e}")
                session.rollback()
            finally:
                session.close()
    
    @app.teardown_appcontext
    def close_db_manager(error):
        """Clean up database manager on app shutdown."""
        global _db_manager
        if _db_manager:
            _db_manager.close_all_connections()


def execute_with_retry(
    operation,
    max_retries: int = 3,
    retry_delay: float = 1.0,
    exponential_backoff: bool = True
) -> Any:
    """
    Execute a database operation with retry logic.
    
    Args:
        operation: Callable that performs the database operation
        max_retries: Maximum number of retry attempts
        retry_delay: Initial delay between retries (seconds)
        exponential_backoff: Whether to use exponential backoff
        
    Returns:
        Result of the operation
        
    Raises:
        Last exception if all retries fail
    """
    last_exception = None
    
    for attempt in range(max_retries + 1):
        try:
            return operation()
        except (OperationalError, SQLAlchemyError) as e:
            last_exception = e
            
            if attempt == max_retries:
                logger.error(f"❌ Database operation failed after {max_retries} retries: {e}")
                break
            
            delay = retry_delay * (2 ** attempt) if exponential_backoff else retry_delay
            logger.warning(f"⚠️ Database operation failed (attempt {attempt + 1}/{max_retries + 1}), retrying in {delay}s: {e}")
            time.sleep(delay)
    
    raise last_exception


def validate_database_schema() -> Dict[str, Any]:
    """
    Validate that the database schema matches expected structure.
    
    Returns:
        Dictionary with validation results
    """
    validation_result = {
        'valid': False,
        'missing_tables': [],
        'missing_columns': {},
        'errors': []
    }
    
    try:
        db_manager = get_db_manager()
        
        # Expected tables and their key columns
        expected_schema = {
            'knowledge_base_item': ['id', 'tweet_id', 'title', 'content', 'main_category', 'sub_category'],
            'agent_state': ['id', 'is_running', 'current_phase_message'],
            'celery_task_state': ['id', 'task_id', 'task_type', 'status'],
            'tweet_cache': ['id', 'tweet_id', 'force_reprocess_pipeline', 'force_recache'],  # New table
            'tweet_processing_queue': ['id', 'tweet_id', 'status', 'processing_phase'],  # New table
            'category_hierarchy': ['id', 'main_category', 'sub_category'],  # New table
        }
        
        with db_manager.get_session_context() as session:
            for table_name, expected_columns in expected_schema.items():
                # Check if table exists
                if db_manager.is_postgresql:
                    table_exists = session.execute(text("""
                        SELECT EXISTS (
                            SELECT FROM information_schema.tables 
                            WHERE table_name = :table_name
                        )
                    """), {'table_name': table_name}).scalar()
                else:
                    table_exists = session.execute(text("""
                        SELECT COUNT(*) FROM sqlite_master 
                        WHERE type='table' AND name = :table_name
                    """), {'table_name': table_name}).scalar() > 0
                
                if not table_exists:
                    validation_result['missing_tables'].append(table_name)
                    continue
                
                # Check columns (simplified check)
                missing_columns = []
                for column in expected_columns:
                    try:
                        if db_manager.is_postgresql:
                            column_exists = session.execute(text(f"""
                                SELECT EXISTS (
                                    SELECT FROM information_schema.columns 
                                    WHERE table_name = '{table_name}' AND column_name = '{column}'
                                )
                            """)).scalar()
                        else:
                            # For SQLite, we'll use a simpler approach
                            session.execute(text(f"SELECT {column} FROM {table_name} LIMIT 0"))
                            column_exists = True
                    except:
                        column_exists = False
                    
                    if not column_exists:
                        missing_columns.append(column)
                
                if missing_columns:
                    validation_result['missing_columns'][table_name] = missing_columns
        
        # Overall validation status
        validation_result['valid'] = (
            len(validation_result['missing_tables']) == 0 and
            len(validation_result['missing_columns']) == 0
        )
        
        if validation_result['valid']:
            logger.info("✅ Database schema validation passed")
        else:
            logger.warning("⚠️ Database schema validation failed")
            
    except Exception as e:
        validation_result['errors'].append(str(e))
        logger.error(f"❌ Database schema validation error: {e}", exc_info=True)
    
    return validation_result