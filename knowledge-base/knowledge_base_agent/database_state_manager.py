"""
Database-backed State Manager

This module provides a StateManager implementation that uses database operations
instead of JSON files while maintaining the same interface and validation phases
as the original StateManager.
"""

import asyncio
import logging
from typing import Dict, Any, List, Optional, Set
from datetime import datetime, timezone
from pathlib import Path

from .config import Config
from .exceptions import StateError, StateManagerError
from .repositories import (
    TweetCacheRepository, TweetProcessingQueueRepository,
    CategoryRepository, ProcessingStatisticsRepository, RuntimeStatisticsRepository
)
from .database import get_db_session_context
from .models import TweetCache, TweetProcessingQueue, CategoryHierarchy
from .task_progress import get_progress_manager


def check_knowledge_base_state(config) -> Dict[str, bool]:
    """
    Check the state of knowledge base items in the database.
    
    Args:
        config: Application configuration
        
    Returns:
        Dictionary with state information
    """
    try:
        with get_db_session_context() as session:
            # Count tweets and knowledge base items
            tweet_count = session.query(TweetCache).count()
            kb_items_count = session.query(TweetCache).filter(
                TweetCache.kb_item_created == True
            ).count()
            
            return {
                "has_tweets": tweet_count > 0,
                "has_kb_items": kb_items_count > 0,
                "tweet_count": tweet_count,
                "kb_items_count": kb_items_count
            }
    except Exception as e:
        logging.error(f"Error checking knowledge base state: {e}")
        return {
            "has_tweets": False,
            "has_kb_items": False,
            "tweet_count": 0,
            "kb_items_count": 0
        }


class DatabaseStateManager:
    """
    Database-backed StateManager implementation.
    
    Maintains the same interface as the original StateManager but uses
    database operations instead of JSON files. Preserves all validation
    phases and functionality while providing better performance and scalability.
    """
    
    def __init__(self, config: Config, task_id: Optional[str] = None):
        """
        Initialize the database state manager.
        
        Args:
            config: The application configuration object.
            task_id: The unique identifier for the Celery task, if this
                     instance is running within a task context.
        """
        self.config = config
        self.task_id = task_id
        
        # Initialize progress manager only if a task_id is provided
        self.progress_manager = get_progress_manager() if task_id else None
        
        # Initialize unified logging if task_id provided
        if task_id:
            from .unified_logging import get_unified_logger
            self.unified_logger = get_unified_logger(task_id, config)
        else:
            self.unified_logger = None
        
        self.logger = logging.getLogger(__name__)
        
        # Initialize repositories
        self.tweet_repo = TweetCacheRepository()
        self.queue_repo = TweetProcessingQueueRepository()
        self.category_repo = CategoryRepository()
        self.processing_stats_repo = ProcessingStatisticsRepository()
        self.runtime_stats_repo = RuntimeStatisticsRepository()
        
        # Initialize enhanced validation system
        from .enhanced_validation import EnhancedValidator
        self.validator = EnhancedValidator(config)
        
        # In-memory caching for frequently accessed data
        self._tweet_cache = {}
        self._cache_dirty = False
        self._initialized = False
        self._lock = asyncio.Lock()
        
        # Validation tracking
        self.validation_stats = {
            "initial_state_fixes": 0,
            "cache_phase_fixes": 0,
            "media_phase_fixes": 0,
            "category_phase_fixes": 0,
            "kb_item_phase_fixes": 0,
            "tweets_moved_to_unprocessed": 0,
            "tweets_moved_to_processed": 0
        }
    
    def update_task_progress(self, phase_id: str, status: str, message: str, progress: int = 0):
        """Update task progress through the progress manager."""
        if self.progress_manager:
            try:
                self.progress_manager.update_phase_progress(
                    self.task_id, phase_id, status, message, progress
                )
            except Exception as e:
                self.logger.warning(f"Failed to update task progress: {e}")
    
    async def initialize(self) -> None:
        """Initialize the state manager and run all validation phases."""
        if self._initialized:
            return
            
        self.logger.info("Starting DatabaseStateManager initialization...")
        
        # Reset validation stats
        for key in self.validation_stats:
            self.validation_stats[key] = 0
        
        # Load tweet cache from database
        await self._load_tweet_cache()
        
        # Run enhanced comprehensive validation
        try:
            self.logger.info("Running enhanced comprehensive validation...")
            validation_summary = await self.validator.run_comprehensive_validation(auto_fix=True)
            
            # Log validation results
            health_report = self.validator.generate_health_report(validation_summary)
            self.logger.info(f"System health score: {health_report['health_score']}% ({health_report['health_status']})")
            
            if validation_summary.total_issues > 0:
                self.logger.warning(f"Validation found {validation_summary.total_issues} issues, "
                                  f"applied {validation_summary.total_fixes} fixes")
            
        except Exception as e:
            self.logger.error(f"Enhanced validation failed, falling back to basic validation: {e}")
            # Fallback to original validation phases
            await self._run_initial_state_validation()
            await self._run_cache_phase_validation()
            await self._run_media_phase_validation()
            await self._run_category_phase_validation()
            await self._run_kb_item_phase_validation()
            await self._run_final_processing_validation()
        
        # Save any changes made during validation
        await self._save_cache_changes()
        
        self._initialized = True
        self.logger.info(f"DatabaseStateManager initialization complete. Validation stats: {self.validation_stats}")
    
    async def _load_tweet_cache(self) -> None:
        """Load tweet cache from database into memory."""
        try:
            # Get all tweets from database
            tweets = self.tweet_repo.get_all()
            
            # Convert to cache format
            self._tweet_cache = {}
            for tweet in tweets:
                self._tweet_cache[tweet.tweet_id] = {
                    "tweet_id": tweet.tweet_id,
                    "bookmarked_tweet_id": tweet.bookmarked_tweet_id,
                    "is_thread": tweet.is_thread,
                    "thread_tweets": tweet.thread_tweets or [],
                    "all_downloaded_media_for_thread": tweet.all_downloaded_media_for_thread or [],
                    
                    # Processing flags
                    "urls_expanded": tweet.urls_expanded,
                    "media_processed": tweet.media_processed,
                    "cache_complete": tweet.cache_complete,
                    "categories_processed": tweet.categories_processed,
                    "kb_item_created": tweet.kb_item_created,
                    
                    # Reprocessing controls
                    "force_reprocess_pipeline": tweet.force_reprocess_pipeline,
                    "force_recache": tweet.force_recache,
                    "reprocess_requested_at": tweet.reprocess_requested_at,
                    "reprocess_requested_by": tweet.reprocess_requested_by,
                    
                    # Categorization data
                    "main_category": tweet.main_category,
                    "sub_category": tweet.sub_category,
                    "item_name_suggestion": tweet.item_name_suggestion,
                    "categories": tweet.categories or {},
                    
                    # Knowledge base integration
                    "kb_item_path": tweet.kb_item_path,
                    "kb_media_paths": tweet.kb_media_paths or [],
                    
                    # Content and metadata
                    "raw_json_content": tweet.raw_json_content,
                    "display_title": tweet.display_title,
                    "source": tweet.source,
                    "image_descriptions": tweet.image_descriptions or [],
                    "full_text": tweet.full_text,
                    
                    # Processing metadata
                    "recategorization_attempts": tweet.recategorization_attempts,
                    "db_synced": tweet.db_synced,
                    
                    # Runtime flags
                    "cache_succeeded_this_run": getattr(tweet, 'cache_succeeded_this_run', False),
                    "media_succeeded_this_run": getattr(tweet, 'media_succeeded_this_run', False),
                    "llm_succeeded_this_run": getattr(tweet, 'llm_succeeded_this_run', False),
                    "kbitem_succeeded_this_run": getattr(tweet, 'kbitem_succeeded_this_run', False),
                    
                    # Error tracking
                    "kbitem_error": getattr(tweet, 'kbitem_error', None),
                    "llm_error": getattr(tweet, 'llm_error', None),
                }
            
            self._cache_dirty = False
            self.logger.info(f"Loaded {len(self._tweet_cache)} tweets from database")
            
        except Exception as e:
            self.logger.error(f"Failed to load tweet cache from database: {e}")
            self._tweet_cache = {}
    
    async def _save_cache_changes(self) -> None:
        """Save any cache changes back to the database."""
        if not self._cache_dirty:
            return
        
        try:
            # Update all modified tweets in database
            for tweet_id, tweet_data in self._tweet_cache.items():
                self.tweet_repo.update(tweet_id, tweet_data)
            
            self._cache_dirty = False
            self.logger.debug("Saved cache changes to database")
            
        except Exception as e:
            self.logger.error(f"Failed to save cache changes to database: {e}")
            raise StateManagerError(f"Failed to save cache changes: {e}")
    
    async def _run_initial_state_validation(self) -> None:
        """
        Phase 1: Initial State Validation
        Ensure all tweets have required basic fields.
        """
        self.logger.info("Running initial state validation...")
        
        fixes_made = 0
        
        for tweet_id, tweet_data in self._tweet_cache.items():
            modified = False
            
            # Ensure basic required fields exist
            if "tweet_id" not in tweet_data:
                tweet_data["tweet_id"] = tweet_id
                modified = True
            
            if "bookmarked_tweet_id" not in tweet_data:
                tweet_data["bookmarked_tweet_id"] = tweet_id
                modified = True
            
            # Ensure boolean fields exist with default values
            boolean_fields = {
                "is_thread": False,
                "urls_expanded": False,
                "media_processed": False,
                "cache_complete": False,
                "categories_processed": False,
                "kb_item_created": False,
                "force_reprocess_pipeline": False,
                "force_recache": False,
                "db_synced": False
            }
            
            for field, default_value in boolean_fields.items():
                if field not in tweet_data:
                    tweet_data[field] = default_value
                    modified = True
            
            # Ensure list fields exist
            list_fields = {
                "thread_tweets": [],
                "all_downloaded_media_for_thread": [],
                "kb_media_paths": [],
                "image_descriptions": []
            }
            
            for field, default_value in list_fields.items():
                if field not in tweet_data:
                    tweet_data[field] = default_value
                    modified = True
            
            # Ensure dict fields exist
            if "categories" not in tweet_data:
                tweet_data["categories"] = {}
                modified = True
            
            # Ensure integer fields exist
            if "recategorization_attempts" not in tweet_data:
                tweet_data["recategorization_attempts"] = 0
                modified = True
            
            if modified:
                fixes_made += 1
                self._cache_dirty = True
        
        self.validation_stats["initial_state_fixes"] = fixes_made
        self.logger.info(f"Initial state validation complete. Fixed {fixes_made} tweets.")
    
    async def _run_cache_phase_validation(self) -> None:
        """
        Phase 2: Tweet Cache Phase Validation
        Validate cache completeness and consistency.
        """
        self.logger.info("Running cache phase validation...")
        
        fixes_made = 0
        
        for tweet_id, tweet_data in self._tweet_cache.items():
            modified = False
            
            # Check cache_complete consistency
            has_thread_data = bool(tweet_data.get("thread_tweets"))
            cache_complete = tweet_data.get("cache_complete", False)
            
            # If we have thread data but cache_complete is False, fix it
            if has_thread_data and not cache_complete:
                tweet_data["cache_complete"] = True
                modified = True
            
            # Check if URLs are marked as expanded when we have expanded URLs
            if has_thread_data and not tweet_data.get("urls_expanded", False):
                # Check if any thread tweets have expanded URLs
                for thread_tweet in tweet_data.get("thread_tweets", []):
                    if thread_tweet.get("expanded_urls"):
                        tweet_data["urls_expanded"] = True
                        modified = True
                        break
            
            if modified:
                fixes_made += 1
                self._cache_dirty = True
        
        self.validation_stats["cache_phase_fixes"] = fixes_made
        self.logger.info(f"Cache phase validation complete. Fixed {fixes_made} tweets.")
    
    async def _run_media_phase_validation(self) -> None:
        """
        Phase 3: Media Processing Phase Validation
        Validate media processing status and files.
        """
        self.logger.info("Running media phase validation...")
        
        fixes_made = 0
        
        for tweet_id, tweet_data in self._tweet_cache.items():
            modified = False
            
            # Check if tweet has media
            has_media = self._tweet_has_media(tweet_data)
            media_processed = tweet_data.get("media_processed", False)
            
            # If tweet has no media but is marked as media_processed, that's correct
            # If tweet has media but media_processed is False, check if files exist
            if has_media and not media_processed:
                # Check if media files actually exist
                media_paths = tweet_data.get("all_downloaded_media_for_thread", [])
                if media_paths:
                    # Assume media is processed if we have media paths
                    tweet_data["media_processed"] = True
                    modified = True
            
            if modified:
                fixes_made += 1
                self._cache_dirty = True
        
        self.validation_stats["media_phase_fixes"] = fixes_made
        self.logger.info(f"Media phase validation complete. Fixed {fixes_made} tweets.")
    
    async def _run_category_phase_validation(self) -> None:
        """
        Phase 4: Category Processing Phase Validation
        Validate categorization data and consistency.
        """
        self.logger.info("Running category phase validation...")
        
        fixes_made = 0
        
        for tweet_id, tweet_data in self._tweet_cache.items():
            modified = False
            
            # Check category processing consistency
            has_categories = bool(tweet_data.get("main_category")) and bool(tweet_data.get("sub_category"))
            categories_processed = tweet_data.get("categories_processed", False)
            
            # If we have categories but not marked as processed, fix it
            if has_categories and not categories_processed:
                tweet_data["categories_processed"] = True
                modified = True
            
            # Ensure categories dict is consistent with main/sub category
            categories_dict = tweet_data.get("categories", {})
            main_category = tweet_data.get("main_category")
            sub_category = tweet_data.get("sub_category")
            
            if main_category and sub_category:
                if (categories_dict.get("main_category") != main_category or 
                    categories_dict.get("sub_category") != sub_category):
                    tweet_data["categories"]["main_category"] = main_category
                    tweet_data["categories"]["sub_category"] = sub_category
                    modified = True
            
            if modified:
                fixes_made += 1
                self._cache_dirty = True
        
        self.validation_stats["category_phase_fixes"] = fixes_made
        self.logger.info(f"Category phase validation complete. Fixed {fixes_made} tweets.")
    
    async def _run_kb_item_phase_validation(self) -> None:
        """
        Phase 5: KB Item Processing Phase Validation
        Validate knowledge base item creation and paths.
        """
        self.logger.info("Running KB item phase validation...")
        
        fixes_made = 0
        
        for tweet_id, tweet_data in self._tweet_cache.items():
            modified = False
            
            # Check KB item creation consistency
            has_kb_path = bool(tweet_data.get("kb_item_path"))
            kb_item_created = tweet_data.get("kb_item_created", False)
            
            # If we have a KB path but not marked as created, validate the path
            if has_kb_path and not kb_item_created:
                kb_path = tweet_data["kb_item_path"]
                if await self._validate_kb_item_path(tweet_id, kb_path):
                    tweet_data["kb_item_created"] = True
                    modified = True
            
            # If marked as created but no path, clear the flag
            elif kb_item_created and not has_kb_path:
                tweet_data["kb_item_created"] = False
                modified = True
            
            if modified:
                fixes_made += 1
                self._cache_dirty = True
        
        self.validation_stats["kb_item_phase_fixes"] = fixes_made
        self.logger.info(f"KB item phase validation complete. Fixed {fixes_made} tweets.")
    
    async def _run_final_processing_validation(self) -> None:
        """
        Phase 6: Final Processing Validation
        Move completed tweets to processed queue automatically.
        """
        self.logger.info("Running final processing validation...")
        
        moved_to_processed = 0
        moved_to_unprocessed = 0
        
        for tweet_id, tweet_data in self._tweet_cache.items():
            # Check if tweet is fully processed
            is_complete = (
                tweet_data.get("cache_complete", False) and
                tweet_data.get("media_processed", False) and
                tweet_data.get("categories_processed", False) and
                tweet_data.get("kb_item_created", False)
            )
            
            # Check current processing queue status
            queue_entry = self.queue_repo.get_by_tweet_id(tweet_id)
            
            if is_complete:
                # Move to processed if not already there
                if not queue_entry or queue_entry.status != "processed":
                    queue_data = {
                        "tweet_id": tweet_id,
                        "status": "processed",
                        "processed_at": datetime.now(timezone.utc)
                    }
                    if queue_entry:
                        self.queue_repo.update_status(tweet_id, "processed")
                    else:
                        self.queue_repo.create(queue_data)
                    moved_to_processed += 1
            else:
                # Move to unprocessed if not already there
                if not queue_entry or queue_entry.status == "processed":
                    queue_data = {
                        "tweet_id": tweet_id,
                        "status": "unprocessed"
                    }
                    if queue_entry:
                        self.queue_repo.update_status(tweet_id, "unprocessed")
                    else:
                        self.queue_repo.create(queue_data)
                    moved_to_unprocessed += 1
        
        self.validation_stats["tweets_moved_to_processed"] = moved_to_processed
        self.validation_stats["tweets_moved_to_unprocessed"] = moved_to_unprocessed
        
        self.logger.info(f"Final processing validation complete. "
                        f"Moved {moved_to_processed} to processed, {moved_to_unprocessed} to unprocessed.")
    
    def _tweet_has_media(self, tweet_data: Dict[str, Any]) -> bool:
        """Check if a tweet has media content."""
        # Check for downloaded media files
        if tweet_data.get("all_downloaded_media_for_thread"):
            return True
        
        # Check thread tweets for media
        for thread_tweet in tweet_data.get("thread_tweets", []):
            if thread_tweet.get("media_item_details"):
                return True
            if thread_tweet.get("downloaded_media_paths_for_segment"):
                return True
        
        return False
    
    async def _validate_kb_item_path(self, tweet_id: str, kb_item_path: str) -> bool:
        """Validate that a KB item path exists and is valid."""
        try:
            # Check if path exists relative to project root
            full_path = Path(self.config.project_root) / kb_item_path
            exists = full_path.exists() and full_path.is_file()
            
            if not exists:
                self.logger.warning(f"KB item path does not exist for tweet {tweet_id}: {kb_item_path}")
            
            return exists
        except Exception as e:
            self.logger.error(f"Error validating KB item path for tweet {tweet_id}: {e}")
            return False
    
    async def update_tweet_data(self, tweet_id: str, tweet_data: Dict[str, Any]) -> None:
        """Update tweet data in cache and database with transaction support."""
        async with self._lock:
            if not self._initialized:
                await self.initialize()
            
            # Validate tweet data structure
            validated_data = self._validate_and_normalize_tweet_data(tweet_id, tweet_data)
            
            try:
                # Update database with transaction support
                success = self.tweet_repo.update_with_transaction(tweet_id, validated_data)
                if not success:
                    raise StateManagerError(f"Failed to update tweet {tweet_id} in database")
                
                # Update in-memory cache only after successful DB update
                self._tweet_cache[tweet_id] = validated_data
                self._cache_dirty = False
                
                self.logger.debug(f"Successfully updated tweet {tweet_id} in cache and database")
                
            except Exception as e:
                self.logger.error(f"Failed to update tweet {tweet_id}: {e}")
                # Re-raise with more context
                raise StateManagerError(f"Failed to update tweet {tweet_id}: {e}")
    
    def _validate_and_normalize_tweet_data(self, tweet_id: str, tweet_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate and normalize tweet data before database update.
        
        Args:
            tweet_id: The tweet ID
            tweet_data: Raw tweet data
            
        Returns:
            Validated and normalized tweet data
        """
        # Start with a copy to avoid modifying original data
        normalized_data = tweet_data.copy()
        
        # Ensure tweet_id is set correctly
        normalized_data['tweet_id'] = tweet_id
        
        # Ensure required fields exist with proper defaults
        defaults = {
            'bookmarked_tweet_id': tweet_id,
            'is_thread': False,
            'thread_tweets': [],
            'all_downloaded_media_for_thread': [],
            'urls_expanded': False,
            'media_processed': False,
            'cache_complete': False,
            'categories_processed': False,
            'kb_item_created': False,
            'force_reprocess_pipeline': False,
            'force_recache': False,
            'db_synced': False,
            'categories': {},
            'kb_media_paths': [],
            'image_descriptions': [],
            'recategorization_attempts': 0,
            'source': 'unknown'
        }
        
        for field, default_value in defaults.items():
            if field not in normalized_data or normalized_data[field] is None:
                normalized_data[field] = default_value
        
        # Validate and convert data types
        self._validate_tweet_data_types(normalized_data)
        
        # Add/update timestamps
        if 'updated_at' not in normalized_data:
            normalized_data['updated_at'] = datetime.now(timezone.utc)
        else:
            normalized_data['updated_at'] = datetime.now(timezone.utc)
        
        return normalized_data
    
    def _validate_tweet_data_types(self, tweet_data: Dict[str, Any]) -> None:
        """
        Validate data types for tweet data fields.
        
        Args:
            tweet_data: Tweet data to validate
            
        Raises:
            StateManagerError: If validation fails
        """
        # Boolean fields
        boolean_fields = [
            'is_thread', 'urls_expanded', 'media_processed', 'cache_complete',
            'categories_processed', 'kb_item_created', 'force_reprocess_pipeline',
            'force_recache', 'db_synced'
        ]
        
        for field in boolean_fields:
            if field in tweet_data and not isinstance(tweet_data[field], bool):
                try:
                    tweet_data[field] = bool(tweet_data[field])
                except (ValueError, TypeError):
                    raise StateManagerError(f"Invalid boolean value for field {field}: {tweet_data[field]}")
        
        # List fields
        list_fields = ['thread_tweets', 'all_downloaded_media_for_thread', 'kb_media_paths', 'image_descriptions']
        for field in list_fields:
            if field in tweet_data and not isinstance(tweet_data[field], list):
                if tweet_data[field] is None:
                    tweet_data[field] = []
                else:
                    raise StateManagerError(f"Invalid list value for field {field}: {tweet_data[field]}")
        
        # Dict fields
        dict_fields = ['categories']
        for field in dict_fields:
            if field in tweet_data and not isinstance(tweet_data[field], dict):
                if tweet_data[field] is None:
                    tweet_data[field] = {}
                else:
                    raise StateManagerError(f"Invalid dict value for field {field}: {tweet_data[field]}")
        
        # Integer fields
        integer_fields = ['recategorization_attempts']
        for field in integer_fields:
            if field in tweet_data and tweet_data[field] is not None:
                try:
                    tweet_data[field] = int(tweet_data[field])
                except (ValueError, TypeError):
                    raise StateManagerError(f"Invalid integer value for field {field}: {tweet_data[field]}")
    
    async def create_tweet_with_full_defaults(self, tweet_id: str, initial_data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Create a new tweet entry with comprehensive defaults.
        
        Args:
            tweet_id: The tweet ID
            initial_data: Optional initial data to merge with defaults
            
        Returns:
            Complete tweet data with all defaults applied
        """
        async with self._lock:
            if not self._initialized:
                await self.initialize()
            
            # Comprehensive default tweet structure
            default_tweet_data = {
                # Basic identification
                'tweet_id': tweet_id,
                'bookmarked_tweet_id': tweet_id,
                'source': 'bookmark_fetch',
                
                # Thread structure
                'is_thread': False,
                'thread_tweets': [],
                'all_downloaded_media_for_thread': [],
                
                # Processing flags
                'urls_expanded': False,
                'media_processed': False,
                'cache_complete': False,
                'categories_processed': False,
                'kb_item_created': False,
                'db_synced': False,
                
                # Reprocessing controls
                'force_reprocess_pipeline': False,
                'force_recache': False,
                'reprocess_requested_at': None,
                'reprocess_requested_by': None,
                
                # Categorization data
                'main_category': None,
                'sub_category': None,
                'item_name_suggestion': None,
                'categories': {},
                'recategorization_attempts': 0,
                
                # Knowledge base integration
                'kb_item_path': None,
                'kb_media_paths': [],
                
                # Content and metadata
                'raw_json_content': None,
                'display_title': None,
                'full_text': None,
                'description': None,
                'markdown_content': None,
                'image_descriptions': [],
                
                # Error tracking (initialized as None to indicate no errors)
                'kbitem_error': None,
                'llm_error': None,
                
                # Runtime flags (reset for new runs)
                'cache_succeeded_this_run': False,
                'media_succeeded_this_run': False,
                'llm_succeeded_this_run': False,
                'kbitem_succeeded_this_run': False,
                
                # Retry management
                'retry_count': 0,
                'last_retry_attempt': None,
                'next_retry_after': None,
                'failure_type': None,
                
                # Timestamps
                'created_at': datetime.now(timezone.utc),
                'updated_at': datetime.now(timezone.utc)
            }
            
            # Merge with any provided initial data
            if initial_data:
                default_tweet_data.update(initial_data)
                # Ensure tweet_id is correct even if provided in initial_data
                default_tweet_data['tweet_id'] = tweet_id
            
            # Validate and normalize the data
            final_data = self._validate_and_normalize_tweet_data(tweet_id, default_tweet_data)
            
            # Create in database and cache
            await self.update_tweet_data(tweet_id, final_data)
            
            self.logger.info(f"Created new tweet entry with full defaults: {tweet_id}")
            return final_data
    
    async def initialize_tweet_cache(self, tweet_id: str, tweet_data: Dict[str, Any]) -> None:
        """Initialize tweet cache entry (alias for update_tweet_data)."""
        await self.update_tweet_data(tweet_id, tweet_data)
    
    async def mark_tweet_processed(self, tweet_id: str) -> None:
        """Mark tweet as processed in the processing queue."""
        queue_data = {
            "tweet_id": tweet_id,
            "status": "processed",
            "processed_at": datetime.now(timezone.utc)
        }
        
        # Update or create queue entry
        existing = self.queue_repo.get_by_tweet_id(tweet_id)
        if existing:
            self.queue_repo.update_status(tweet_id, "processed")
        else:
            self.queue_repo.create(queue_data)
    
    async def get_unprocessed_tweets(self) -> List[str]:
        """Get list of unprocessed tweet IDs from the processing queue."""
        try:
            unprocessed_entries = self.queue_repo.get_by_status("unprocessed")
            return [entry.tweet_id for entry in unprocessed_entries]
        except Exception as e:
            self.logger.error(f"Failed to get unprocessed tweets: {e}")
            return []
    
    async def get_processed_tweets(self) -> List[str]:
        """Get list of processed tweet IDs from the processing queue."""
        try:
            processed_entries = self.queue_repo.get_by_status("processed")
            return [entry.tweet_id for entry in processed_entries]
        except Exception as e:
            self.logger.error(f"Failed to get processed tweets: {e}")
            return []
    
    async def add_tweets_to_unprocessed(self, tweet_ids: List[str]) -> None:
        """Add tweet IDs to the unprocessed queue."""
        for tweet_id in tweet_ids:
            try:
                # Check if already exists
                existing = self.queue_repo.get_by_tweet_id(tweet_id)
                if not existing:
                    queue_data = {
                        "tweet_id": tweet_id,
                        "status": "unprocessed"
                    }
                    self.queue_repo.create(queue_data)
                elif existing.status != "unprocessed":
                    self.queue_repo.update_status(tweet_id, "unprocessed")
            except Exception as e:
                self.logger.error(f"Failed to add tweet {tweet_id} to unprocessed queue: {e}")
    
    async def get_processing_state(self, tweet_id: str) -> Dict[str, bool]:
        """Get the processing state flags for a specific tweet."""
        if not self._initialized:
            await self.initialize()
        
        tweet_data = self._tweet_cache.get(tweet_id, {})
        
        return {
            "cache_complete": tweet_data.get("cache_complete", False),
            "media_processed": tweet_data.get("media_processed", False),
            "categories_processed": tweet_data.get("categories_processed", False),
            "kb_item_created": tweet_data.get("kb_item_created", False),
            "urls_expanded": tweet_data.get("urls_expanded", False),
            "db_synced": tweet_data.get("db_synced", False),
        }
    
    async def run_validation_phase(self, phase: str) -> None:
        """Run a specific validation phase."""
        phase_methods = {
            "initial": self._run_initial_state_validation,
            "cache": self._run_cache_phase_validation,
            "media": self._run_media_phase_validation,
            "category": self._run_category_phase_validation,
            "kb_item": self._run_kb_item_phase_validation,
            "final": self._run_final_processing_validation,
        }
        
        if phase not in phase_methods:
            raise ValueError(f"Unknown validation phase: {phase}")
        
        await phase_methods[phase]()
        await self._save_cache_changes()
    
    async def get_validation_stats(self) -> Dict[str, int]:
        """Get validation statistics."""
        return self.validation_stats.copy()
    
    async def get_tweet(self, tweet_id: str) -> Optional[Dict[str, Any]]:
        """Get tweet data by ID."""
        if not self._initialized:
            await self.initialize()
        return self._tweet_cache.get(tweet_id)
    
    async def get_all_tweets(self) -> Dict[str, Dict[str, Any]]:
        """Get all tweet data from cache."""
        if not self._initialized:
            await self.initialize()
        return self._tweet_cache.copy()
    
    def initialize_with_events(self, task_id: str) -> Dict[str, Any]:
        """
        Initialize the StateManager with comprehensive event emission.
        
        This method creates a StateManagerEventIntegration wrapper and uses it
        to initialize the state manager with full event emission support.
        
        Args:
            task_id: The task ID for event emission
            
        Returns:
            Dict[str, Any]: Validation statistics
        """
        from .state_manager_event_integration import StateManagerEventIntegration
        
        # Create event integration wrapper
        event_integration = StateManagerEventIntegration(self, task_id, self.config)
        
        # Run initialization with events
        return event_integration.initialize_with_events()
    
    # Additional database-specific methods
    
    async def refresh_cache_from_database(self) -> None:
        """Refresh the in-memory cache from the database."""
        await self._load_tweet_cache()
    
    async def sync_processing_queue(self) -> None:
        """Synchronize processing queue with tweet processing states."""
        await self._run_final_processing_validation()
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        if not self._initialized:
            return {"cache_size": 0, "cache_dirty": False}
        
        return {
            "cache_size": len(self._tweet_cache),
            "cache_dirty": self._cache_dirty,
            "tweets_with_categories": len([
                t for t in self._tweet_cache.values() 
                if t.get("main_category") and t.get("sub_category")
            ]),
            "tweets_kb_created": len([
                t for t in self._tweet_cache.values() 
                if t.get("kb_item_created")
            ]),
            "tweets_fully_processed": len([
                t for t in self._tweet_cache.values() 
                if (t.get("cache_complete") and t.get("media_processed") and 
                    t.get("categories_processed") and t.get("kb_item_created"))
            ])
        } 