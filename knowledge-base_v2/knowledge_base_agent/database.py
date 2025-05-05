# knowledge_base_agent/database.py

import asyncio
import logging
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Generator

from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import create_engine, String, DateTime, Text, Index, inspect
from sqlalchemy.orm import sessionmaker, Session as SyncSession # Rename Session to avoid Pydantic clash
from sqlalchemy.exc import SQLAlchemyError

from .config import Config
from .exceptions import DBSyncError
from .types import TweetData, KnowledgeBaseItemRecord # Pydantic type for data transfer

logger = logging.getLogger(__name__)

# Initialize Flask-SQLAlchemy. This instance can be used by both Flask app and potentially CLI.
# We don't initialize it with an app here; that happens in main_web.py.
db = SQLAlchemy()

# --- SQLAlchemy Model Definition ---

class KnowledgeBaseItem(db.Model):
    """SQLAlchemy model for items in the knowledge base index."""
    __tablename__ = 'knowledge_base_item'

    # Core Fields
    id = db.Column(db.Integer, primary_key=True)
    tweet_id = db.Column(db.String(30), unique=True, nullable=False, index=True) # Twitter IDs are numeric strings
    item_name = db.Column(db.String(255), nullable=False) # Filesystem-safe name used in path
    main_category = db.Column(db.String(100), nullable=False, index=True)
    sub_category = db.Column(db.String(100), nullable=False, index=True)
    kb_item_path = db.Column(db.String(512), nullable=False) # Store relative path as string

    # Denormalized/Cached Fields from TweetData (for UI display/search)
    source_url = db.Column(db.String(1024)) # Store as String
    author_handle = db.Column(db.String(100))
    text_preview = db.Column(db.Text) # Store combined_text preview

    # Timestamps
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow) # When the DB record was created
    tweet_created_at = db.Column(db.DateTime, nullable=True) # Original tweet creation time
    last_updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Add table-level index (optional, but good for common queries)
    __table_args__ = (
        Index('ix_kbitem_category_path', 'main_category', 'sub_category', 'kb_item_path'),
    )

    def __repr__(self):
        return f"<KnowledgeBaseItem(id={self.id}, tweet_id='{self.tweet_id}', path='{self.kb_item_path}')>"

    @classmethod
    def from_tweet_data(cls, tweet_data: TweetData) -> 'KnowledgeBaseItem':
        """Creates a KnowledgeBaseItem instance from TweetData."""
        if not all([tweet_data.kb_item_path, tweet_data.main_category, tweet_data.sub_category, tweet_data.item_name]):
             raise ValueError("Cannot create KnowledgeBaseItem: Missing required fields (path, category, item_name) in TweetData.")

        # Truncate text preview if needed
        preview = tweet_data.combined_text or tweet_data.text or ""
        max_preview_len = 1000 # Adjust as needed
        text_preview = (preview[:max_preview_len] + '...') if len(preview) > max_preview_len else preview

        return cls(
            tweet_id=tweet_data.tweet_id,
            item_name=tweet_data.item_name,
            main_category=tweet_data.main_category,
            sub_category=tweet_data.sub_category,
            kb_item_path=str(tweet_data.kb_item_path), # Store Path as string
            source_url=str(tweet_data.source_url) if tweet_data.source_url else None,
            author_handle=tweet_data.author_handle,
            text_preview=text_preview,
            tweet_created_at=tweet_data.created_at,
            # created_at and last_updated_at handled by default/onupdate
        )

# --- Database Initialization and Session Management (for non-Flask contexts) ---

# Global engine and session factory for non-Flask use (e.g., CLI)
_engine = None
_SessionFactory = None

def init_engine_and_session(database_url: str):
    """Initializes the SQLAlchemy engine and session factory for non-Flask use."""
    global _engine, _SessionFactory
    if _engine is None:
        try:
            logger.info(f"Initializing SQLAlchemy engine for non-Flask context: {database_url.split('@')[-1]}") # Hide credentials
            _engine = create_engine(database_url) # echo=True for debugging SQL
            _SessionFactory = sessionmaker(bind=_engine)
            # Create tables if they don't exist (won't modify existing)
            # Use inspect to check before calling metadata.create_all
            inspector = inspect(_engine)
            if not inspector.has_table(KnowledgeBaseItem.__tablename__):
                 logger.info(f"Table '{KnowledgeBaseItem.__tablename__}' not found. Creating tables...")
                 # This assumes db.metadata contains our model definition
                 db.metadata.create_all(_engine)
                 logger.info("Tables created successfully.")
            else:
                 logger.debug(f"Table '{KnowledgeBaseItem.__tablename__}' already exists.")

        except SQLAlchemyError as e:
            logger.exception(f"Failed to initialize SQLAlchemy engine or session: {e}", exc_info=True)
            raise ConfigurationError(f"Database initialization failed: {e}", original_exception=e) from e


@contextmanager
def get_sync_session() -> Generator[SyncSession, None, None]:
    """Provides a transactional scope around a series of operations for sync contexts."""
    if _SessionFactory is None:
        raise StateManagementError("Database session factory not initialized. Call init_engine_and_session first.")

    session = _SessionFactory()
    logger.debug(f"Created sync DB session {id(session)}")
    try:
        yield session
        session.commit()
        logger.debug(f"Committed sync DB session {id(session)}")
    except SQLAlchemyError as e:
        logger.error(f"SQLAlchemyError in session {id(session)}, rolling back: {e}", exc_info=True)
        session.rollback()
        raise # Re-raise the original SQLAlchemyError
    except Exception:
        logger.exception(f"Exception in session {id(session)}, rolling back.", exc_info=True)
        session.rollback()
        raise # Re-raise other exceptions
    finally:
        logger.debug(f"Closing sync DB session {id(session)}")
        session.close()


# --- Async DB Operations (using sync session in thread) ---

async def _sync_db_operation_in_thread(func, *args, **kwargs):
     """Runs a synchronous DB operation using get_sync_session within asyncio.to_thread."""
     def wrapper():
         with get_sync_session() as session:
             # Automatically pass the session as the first argument to the sync function
             return func(session, *args, **kwargs)
     try:
         return await asyncio.to_thread(wrapper)
     except SQLAlchemyError as e:
          logger.error(f"SQLAlchemyError during async thread operation: {e}", exc_info=False) # Already logged in context manager
          # Wrap in our specific error type if desired
          raise DBSyncError(f"Database operation failed: {e}", original_exception=e) from e
     except Exception as e:
          logger.error(f"Unexpected error during async thread operation: {e}", exc_info=True)
          raise DBSyncError(f"Unexpected database error: {e}", original_exception=e) from e

def _add_or_update_kb_item_sync(session: SyncSession, tweet_data: TweetData):
    """Synchronous function to add or update a KnowledgeBaseItem."""
    logger.debug(f"Syncing tweet {tweet_data.tweet_id} to database...")
    existing_item = session.query(KnowledgeBaseItem).filter_by(tweet_id=tweet_data.tweet_id).one_or_none()

    if existing_item:
        logger.debug(f"Found existing DB item for tweet {tweet_data.tweet_id}. Updating.")
        # Update existing item fields from tweet_data
        # Be specific about which fields to update to avoid overwriting unintended data
        update_data = KnowledgeBaseItem.from_tweet_data(tweet_data) # Create new object to get data easily
        existing_item.item_name = update_data.item_name
        existing_item.main_category = update_data.main_category
        existing_item.sub_category = update_data.sub_category
        existing_item.kb_item_path = update_data.kb_item_path
        existing_item.source_url = update_data.source_url
        existing_item.author_handle = update_data.author_handle
        existing_item.text_preview = update_data.text_preview
        existing_item.tweet_created_at = update_data.tweet_created_at
        # last_updated_at updates automatically via onupdate
        logger.info(f"Updated DB record for tweet {tweet_data.tweet_id}.")
    else:
        logger.debug(f"No existing DB item for tweet {tweet_data.tweet_id}. Creating new.")
        new_item = KnowledgeBaseItem.from_tweet_data(tweet_data)
        session.add(new_item)
        logger.info(f"Created DB record for tweet {tweet_data.tweet_id}.")
    # Commit happens in the context manager wrapper

async def sync_kb_item_async(tweet_data: TweetData):
    """
    Asynchronously adds or updates a knowledge base item in the database
    based on the provided TweetData.
    """
    if not tweet_data.kb_item_created:
         logger.warning(f"Attempted to sync tweet {tweet_data.tweet_id} to DB, but kb_item_created flag is false.")
         return # Or raise error?

    if not all([tweet_data.kb_item_path, tweet_data.main_category, tweet_data.sub_category, tweet_data.item_name]):
        raise DBSyncError(tweet_id=tweet_data.tweet_id, message="Missing required fields (path, category, item_name) for DB sync.")

    logger.info(f"Queueing DB sync for tweet {tweet_data.tweet_id}...")
    await _sync_db_operation_in_thread(_add_or_update_kb_item_sync, tweet_data)
    logger.info(f"DB sync task completed for tweet {tweet_data.tweet_id}.")


# --- Add other async DB query functions as needed ---

def _get_all_items_sync(session: SyncSession) -> List[KnowledgeBaseItemRecord]:
     """Synchronous function to get all items."""
     logger.debug("Fetching all KB items from DB (sync)...")
     items = session.query(KnowledgeBaseItem).order_by(
         KnowledgeBaseItem.main_category,
         KnowledgeBaseItem.sub_category,
         KnowledgeBaseItem.item_name
     ).all()
     # Convert SQLAlchemy models to Pydantic models for return
     return [KnowledgeBaseItemRecord.model_validate(item, from_attributes=True) for item in items]

async def get_all_kb_items_async() -> List[KnowledgeBaseItemRecord]:
     """Asynchronously retrieves all knowledge base items from the DB."""
     logger.info("Fetching all KB items from DB...")
     return await _sync_db_operation_in_thread(_get_all_items_sync)


# Import ConfigurationError and StateManagementError used above
from .exceptions import ConfigurationError, StateManagementError
