"""
New State Manager with Organized Validation Phases.

This module provides a cleaner approach to state management with specific validation phases:
1. Initial State Validation - Ensure data structure integrity
2. Tweet Cache Phase Validation - Validate cache completeness
3. Media Processing Phase Validation - Validate media processing
4. Category Processing Phase Validation - Validate categorization
5. KB Item Processing Phase Validation - Validate knowledge base items
"""

import json
import asyncio
import aiofiles
from pathlib import Path
from typing import Set, Dict, Any, List, Optional, Tuple
import logging
from datetime import datetime, timezone
import tempfile
import os
import shutil
import re
import copy

from knowledge_base_agent.exceptions import StateError, StateManagerError
from knowledge_base_agent.config import Config
from knowledge_base_agent.file_utils import (
    async_write_text,
    async_json_load,
    async_json_dump,
)

# Celery Migration Imports
from flask import current_app
from datetime import datetime
from .task_progress import get_progress_manager
from .models import db, CeleryTaskState


class StateManager:
    """
    Enhanced StateManager with Celery task integration.
    
    Preserves all current validation phases while adding distributed
    task state management through Redis and a persistent database backend.
    """

    def __init__(self, config: Config, task_id: Optional[str] = None):
        """
        Initialize the state manager with configuration and an optional task ID.
        
        Args:
            config: The application configuration object.
            task_id: The unique identifier for the Celery task, if this
                     instance is running within a task context.
        """
        self.config = config
        self.task_id = task_id
        
        # Initialize progress manager only if a task_id is provided
        self.progress_manager = get_progress_manager() if task_id else None
        
        # State file paths (absolute)
        self.tweet_cache_file = config.tweet_cache_file
        self.unprocessed_tweets_file = config.unprocessed_tweets_file
        self.processed_tweets_file = config.processed_tweets_file
        self.bookmarks_file = config.bookmarks_file
        
        # In-memory state
        self._tweet_cache = {}
        self._unprocessed_tweets = []
        self._processed_tweets = {}
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
        """
        Update task progress in both Redis for real-time updates and the 
        database for persistent state tracking.
        
        This method should be called from within a Celery task context where
        `task_id` is available.
        """
        if not self.task_id:
            logging.warning("update_task_progress called without a task_id. Skipping.")
            return

        # 1. Update Redis for real-time frontend updates via RealtimeManager
        if self.progress_manager:
            self.progress_manager.update_progress(self.task_id, progress, phase_id, message)
            
        # 2. Update the persistent CeleryTaskState model in the database
        # This requires an active Flask application context to access the database.
        try:
            with current_app.app_context():
                task_state = CeleryTaskState.query.filter_by(task_id=self.task_id).first()
                if task_state:
                    task_state.current_phase_id = phase_id
                    task_state.current_phase_message = message
                    task_state.progress_percentage = progress
                    task_state.status = 'PROGRESS' # Or determine based on phase
                    task_state.updated_at = datetime.utcnow()
                    db.session.commit()
                else:
                    logging.warning(f"Could not find CeleryTaskState for task_id: {self.task_id}")
        except Exception as e:
            # This might happen if called outside of a request/app context.
            # The Redis update is more critical for real-time feedback, so we log
            # this as a non-fatal error.
            logging.error(f"Failed to update CeleryTaskState in DB for task {self.task_id}: {e}", exc_info=True)


    async def initialize(self) -> None:
        """Initialize the state manager and run all validation phases."""
        if self._initialized:
            return
            
        logging.info("Starting StateManager initialization...")
        
        # Reset validation stats
        for key in self.validation_stats:
            self.validation_stats[key] = 0
            
        # Load existing state files
        await self._load_state_files()
        
        # Run validation phases in order
        await self._run_initial_state_validation()
        await self._run_cache_phase_validation()
        await self._run_media_phase_validation()
        await self._run_category_phase_validation()
        await self._run_kb_item_phase_validation()
        await self._run_final_processing_validation()
        
        # Save any changes made during validation
        await self._save_state_files()
        
        self._initialized = True
        logging.info(f"StateManager initialization complete. Validation stats: {self.validation_stats}")

    async def _load_state_files(self) -> None:
        """Load state from JSON files."""
        # Load tweet cache
        if self.tweet_cache_file.exists():
            try:
                async with aiofiles.open(self.tweet_cache_file, "r") as f:
                    content = await f.read()
                    self._tweet_cache = json.loads(content) if content.strip() else {}
                logging.info(f"Loaded {len(self._tweet_cache)} tweets from cache")
            except Exception as e:
                logging.error(f"Error loading tweet cache: {e}")
                self._tweet_cache = {}
        
        # Load unprocessed tweets
        if self.unprocessed_tweets_file.exists():
            try:
                async with aiofiles.open(self.unprocessed_tweets_file, "r") as f:
                    content = await f.read()
                    self._unprocessed_tweets = json.loads(content) if content.strip() else []
                logging.info(f"Loaded {len(self._unprocessed_tweets)} unprocessed tweets")
            except Exception as e:
                logging.error(f"Error loading unprocessed tweets: {e}")
                self._unprocessed_tweets = []
        
        # Load processed tweets
        if self.processed_tweets_file.exists():
            try:
                async with aiofiles.open(self.processed_tweets_file, "r") as f:
                    content = await f.read()
                    self._processed_tweets = json.loads(content) if content.strip() else {}
                logging.info(f"Loaded {len(self._processed_tweets)} processed tweets")
            except Exception as e:
                logging.error(f"Error loading processed tweets: {e}")
                self._processed_tweets = {}

    async def _save_state_files(self) -> None:
        """Save state to JSON files atomically."""
        try:
            await self._atomic_write_json(self._tweet_cache, self.tweet_cache_file)
            await self._atomic_write_json(self._unprocessed_tweets, self.unprocessed_tweets_file)
            await self._atomic_write_json(self._processed_tweets, self.processed_tweets_file)
            logging.debug("State files saved successfully")
        except Exception as e:
            logging.error(f"Error saving state files: {e}")
            raise StateManagerError(f"Failed to save state files: {e}")

    async def _atomic_write_json(self, data: Any, filepath: Path) -> None:
        """Write JSON data atomically using a temporary file."""
        temp_file = None
        try:
            temp_fd, temp_path_str = tempfile.mkstemp(dir=filepath.parent, text=True)
            os.close(temp_fd)
            temp_file = Path(temp_path_str)
            
            async with aiofiles.open(temp_file, "w", encoding="utf-8") as f:
                await f.write(json.dumps(data, indent=2))
            
            shutil.move(str(temp_file), str(filepath))
            logging.debug(f"Atomically wrote {filepath}")
        except Exception as e:
            if temp_file and temp_file.exists():
                try:
                    temp_file.unlink()
                except OSError:
                    pass
            logging.error(f"Failed to write {filepath}: {e}")
            raise StateError(f"Failed to write state file: {filepath}") from e

    async def _run_initial_state_validation(self) -> None:
        """
        Phase 1: Initial State Validation
        Ensure all necessary key-value pairs exist with sane defaults.
        """
        logging.info("Running Initial State Validation...")
        
        required_keys = {
            "tweet_id": "",
            "bookmarked_tweet_id": "",
            "is_thread": False,
            "thread_tweets": [],
            "all_downloaded_media_for_thread": [],
            "urls_expanded": False,
            "media_processed": False,
            "cache_complete": False,
            "main_category": "",
            "sub_category": "",
            "item_name_suggestion": "",
            "categories": {},
            "categories_processed": False,
            "kb_item_path": "",
            "kb_media_paths": "[]",
            "kb_item_created": False,
            "recategorization_attempts": 0,
            "raw_json_content": None,
            "display_title": None,
            "source": "unknown",
            "image_descriptions": []
        }
        
        for tweet_id, tweet_data in self._tweet_cache.items():
            if not isinstance(tweet_data, dict):
                logging.warning(f"Tweet {tweet_id} data is not a dict, resetting to defaults")
                self._tweet_cache[tweet_id] = {"tweet_id": tweet_id}
                tweet_data = self._tweet_cache[tweet_id]
                self.validation_stats["initial_state_fixes"] += 1
            
            # Ensure tweet_id matches the key
            if tweet_data.get("tweet_id") != tweet_id:
                tweet_data["tweet_id"] = tweet_id
                self.validation_stats["initial_state_fixes"] += 1
            
            # Ensure bookmarked_tweet_id defaults to tweet_id if empty
            if not tweet_data.get("bookmarked_tweet_id"):
                tweet_data["bookmarked_tweet_id"] = tweet_id
                self.validation_stats["initial_state_fixes"] += 1
            
            # Add missing keys with defaults
            for key, default_value in required_keys.items():
                if key not in tweet_data:
                    tweet_data[key] = default_value
                    self.validation_stats["initial_state_fixes"] += 1
        
        logging.info(f"Initial state validation complete. Fixed {self.validation_stats['initial_state_fixes']} issues.")

    async def _run_cache_phase_validation(self) -> None:
        """
        Phase 2: Tweet Cache Phase Validation
        Ensure cache_complete flag is accurate and incomplete tweets are in unprocessed list.
        """
        logging.info("Running Cache Phase Validation...")
        
        current_unprocessed_set = set(self._unprocessed_tweets)
        
        for tweet_id, tweet_data in self._tweet_cache.items():
            cache_complete = tweet_data.get("cache_complete", False)
            
            # Basic cache validation - ensure required cache fields have data
            cache_requirements_met = all([
                tweet_data.get("tweet_id"),
                tweet_data.get("bookmarked_tweet_id"),
                "is_thread" in tweet_data,  # Boolean can be False, so check existence
                isinstance(tweet_data.get("thread_tweets", []), list)
            ])
            
            if not cache_requirements_met:
                cache_complete = False
                tweet_data["cache_complete"] = False
                self.validation_stats["cache_phase_fixes"] += 1
                logging.debug(f"Tweet {tweet_id}: cache requirements not met")
            
            # If not cache complete, ensure it's in unprocessed list
            if not cache_complete:
                if tweet_id not in current_unprocessed_set:
                    self._unprocessed_tweets.append(tweet_id)
                    current_unprocessed_set.add(tweet_id)
                    self.validation_stats["tweets_moved_to_unprocessed"] += 1
                    logging.debug(f"Added tweet {tweet_id} to unprocessed (cache incomplete)")
        
        logging.info(f"Cache phase validation complete. Fixed {self.validation_stats['cache_phase_fixes']} issues.")

    async def _run_media_phase_validation(self) -> None:
        """
        Phase 3: Media Processing Phase Validation
        Validate media processing for tweets with media.
        """
        logging.info("Running Media Phase Validation...")
        
        current_unprocessed_set = set(self._unprocessed_tweets)
        
        for tweet_id, tweet_data in self._tweet_cache.items():
            # Check if tweet has media
            has_media = self._tweet_has_media(tweet_data)
            media_processed = tweet_data.get("media_processed", False)
            
            if has_media:
                # If has media, check if it's properly processed
                image_descriptions = tweet_data.get("image_descriptions", [])
                
                # Media should be processed if it has descriptions (for images)
                should_be_processed = bool(image_descriptions)
                
                if not should_be_processed and media_processed:
                    # Media marked processed but no descriptions
                    tweet_data["media_processed"] = False
                    media_processed = False
                    self.validation_stats["media_phase_fixes"] += 1
                    logging.debug(f"Tweet {tweet_id}: media marked processed but no descriptions")
                
                # If media not processed, ensure in unprocessed list
                if not media_processed:
                    if tweet_id not in current_unprocessed_set:
                        self._unprocessed_tweets.append(tweet_id)
                        current_unprocessed_set.add(tweet_id)
                        self.validation_stats["tweets_moved_to_unprocessed"] += 1
                        logging.debug(f"Added tweet {tweet_id} to unprocessed (media not processed)")
            else:
                # No media, should be marked as processed
                if not media_processed:
                    tweet_data["media_processed"] = True
                    self.validation_stats["media_phase_fixes"] += 1
                    logging.debug(f"Tweet {tweet_id}: no media, marked as processed")
        
        logging.info(f"Media phase validation complete. Fixed {self.validation_stats['media_phase_fixes']} issues.")

    async def _run_category_phase_validation(self) -> None:
        """
        Phase 4: Category Processing Phase Validation
        Validate categorization data and flags.
        """
        logging.info("Running Category Phase Validation...")
        
        current_unprocessed_set = set(self._unprocessed_tweets)
        
        for tweet_id, tweet_data in self._tweet_cache.items():
            categories_processed = tweet_data.get("categories_processed", False)
            
            if categories_processed:
                # Verify category data exists
                main_category = tweet_data.get("main_category", "").strip()
                sub_category = tweet_data.get("sub_category", "").strip()
                item_name = tweet_data.get("item_name_suggestion", "").strip()
                
                if not (main_category and sub_category and item_name):
                    # Categories marked processed but data missing
                    tweet_data["categories_processed"] = False
                    categories_processed = False
                    self.validation_stats["category_phase_fixes"] += 1
                    logging.debug(f"Tweet {tweet_id}: categories marked processed but data missing")
            
            # If categories not processed, ensure in unprocessed list
            if not categories_processed:
                if tweet_id not in current_unprocessed_set:
                    self._unprocessed_tweets.append(tweet_id)
                    current_unprocessed_set.add(tweet_id)
                    self.validation_stats["tweets_moved_to_unprocessed"] += 1
                    logging.debug(f"Added tweet {tweet_id} to unprocessed (categories not processed)")
        
        logging.info(f"Category phase validation complete. Fixed {self.validation_stats['category_phase_fixes']} issues.")

    async def _run_kb_item_phase_validation(self) -> None:
        """
        Phase 5: KB Item Processing Phase Validation
        Validate knowledge base item creation and paths.
        """
        logging.info("Running KB Item Phase Validation...")
        
        current_unprocessed_set = set(self._unprocessed_tweets)
        
        for tweet_id, tweet_data in self._tweet_cache.items():
            kb_item_created = tweet_data.get("kb_item_created", False)
            
            if kb_item_created:
                kb_item_path = tweet_data.get("kb_item_path", "").strip()
                
                if not kb_item_path:
                    # KB item marked created but no path
                    tweet_data["kb_item_created"] = False
                    kb_item_created = False
                    self.validation_stats["kb_item_phase_fixes"] += 1
                    logging.debug(f"Tweet {tweet_id}: KB item marked created but no path")
                else:
                    # Validate the README exists and contains tweet ID
                    is_valid = await self._validate_kb_item_path(tweet_id, kb_item_path)
                    if not is_valid:
                        tweet_data["kb_item_created"] = False
                        tweet_data["kb_item_path"] = ""
                        tweet_data["kb_media_paths"] = "[]"
                        kb_item_created = False
                        self.validation_stats["kb_item_phase_fixes"] += 1
                        logging.debug(f"Tweet {tweet_id}: KB item validation failed, resetting")
            
            # If KB item not created, ensure in unprocessed list
            if not kb_item_created:
                if tweet_id not in current_unprocessed_set:
                    self._unprocessed_tweets.append(tweet_id)
                    current_unprocessed_set.add(tweet_id)
                    self.validation_stats["tweets_moved_to_unprocessed"] += 1
                    logging.debug(f"Added tweet {tweet_id} to unprocessed (KB item not created)")
        
        logging.info(f"KB item phase validation complete. Fixed {self.validation_stats['kb_item_phase_fixes']} issues.")

    async def _run_final_processing_validation(self) -> None:
        """
        Phase 6: Final Processing Validation
        Move tweets that have completed all phases to the processed list.
        Also clean up tweets that are in unprocessed queue but not cached.
        """
        logging.info("Running Final Processing Validation...")
        
        tweets_to_mark_processed = []
        tweets_to_remove_from_unprocessed = []
        
        for tweet_id in list(self._unprocessed_tweets):  # Use list() to avoid modification during iteration
            tweet_data = self._tweet_cache.get(tweet_id)
            if not tweet_data:
                # Tweet is in unprocessed queue but not cached - this shouldn't happen in normal flow
                # These tweets should be processed by cache phase first, not left in unprocessed queue
                logging.warning(f"Tweet {tweet_id} is in unprocessed queue but not in cache. Removing from unprocessed queue.")
                tweets_to_remove_from_unprocessed.append(tweet_id)
                self.validation_stats["tweets_moved_to_unprocessed"] -= 1  # Decrement since we're removing
                continue
                
            # Check if all required phases are complete
            all_phases_complete = all([
                tweet_data.get("cache_complete", False),
                tweet_data.get("media_processed", False),
                tweet_data.get("categories_processed", False),
                tweet_data.get("kb_item_created", False)
            ])
            
            if all_phases_complete:
                # Additional validation: ensure KB item path exists and is valid
                kb_item_path = tweet_data.get("kb_item_path", "").strip()
                if kb_item_path:
                    is_kb_valid = await self._validate_kb_item_path(tweet_id, kb_item_path)
                    if not is_kb_valid:
                        # KB validation failed, skip this tweet
                        logging.debug(f"Tweet {tweet_id}: KB item validation failed during final processing")
                        continue
                
                # All phases complete and validated, mark for processing
                tweets_to_mark_processed.append(tweet_id)
                logging.debug(f"Tweet {tweet_id}: all phases complete, marking as processed")
        
        # Remove tweets that shouldn't be in unprocessed queue
        for tweet_id in tweets_to_remove_from_unprocessed:
            if tweet_id in self._unprocessed_tweets:
                self._unprocessed_tweets.remove(tweet_id)
        
        # Move tweets to processed list
        for tweet_id in tweets_to_mark_processed:
            # Add to processed tweets with timestamp
            self._processed_tweets[tweet_id] = datetime.now(timezone.utc).isoformat()
            
            # Remove from unprocessed tweets
            if tweet_id in self._unprocessed_tweets:
                self._unprocessed_tweets.remove(tweet_id)
            
            self.validation_stats["tweets_moved_to_processed"] += 1
        
        if tweets_to_remove_from_unprocessed:
            logging.info(f"Final processing validation: removed {len(tweets_to_remove_from_unprocessed)} uncached tweets from unprocessed queue")
        
        if tweets_to_mark_processed:
            logging.info(f"Final processing validation: moved {len(tweets_to_mark_processed)} tweets to processed list")
        else:
            logging.info("Final processing validation: no tweets ready for processing")
        
        logging.info(f"Final processing validation complete. Moved {self.validation_stats['tweets_moved_to_processed']} tweets to processed.")

    def _tweet_has_media(self, tweet_data: Dict[str, Any]) -> bool:
        """Check if a tweet has associated media."""
        media_sources = [
            tweet_data.get("all_downloaded_media_for_thread", []),
            tweet_data.get("kb_media_paths", "[]")
        ]
        
        for source in media_sources:
            if isinstance(source, list) and source:
                return True
            elif isinstance(source, str) and source != "[]":
                try:
                    parsed = json.loads(source)
                    if isinstance(parsed, list) and parsed:
                        return True
                except (json.JSONDecodeError, TypeError):
                    continue
        
        # Check thread tweets for media
        thread_tweets = tweet_data.get("thread_tweets", [])
        if isinstance(thread_tweets, list):
            for segment in thread_tweets:
                if isinstance(segment, dict):
                    media_details = segment.get("media_item_details", [])
                    downloaded_paths = segment.get("downloaded_media_paths_for_segment", [])
                    if media_details or downloaded_paths:
                        return True
        
        return False

    async def _validate_kb_item_path(self, tweet_id: str, kb_item_path: str) -> bool:
        """Validate that a KB item path exists and contains the tweet ID."""
        try:
            # Resolve path from project root
            readme_abs_path = self.config.resolve_path_from_project_root(kb_item_path)
            
            if not readme_abs_path.exists():
                logging.debug(f"KB item README not found: {readme_abs_path}")
                return False
            
            # Check if tweet ID appears in the README content
            async with aiofiles.open(readme_abs_path, "r", encoding="utf-8") as f:
                content = await f.read(2048)  # Read first 2KB
            
            if tweet_id not in content:
                logging.debug(f"Tweet ID {tweet_id} not found in README: {readme_abs_path}")
                return False
            
            return True
            
        except Exception as e:
            logging.debug(f"Error validating KB item path for tweet {tweet_id}: {e}")
            return False

    async def update_tweet_data(self, tweet_id: str, tweet_data: Dict[str, Any]) -> None:
        """Update tweet data in cache."""
        async with self._lock:
            if tweet_id in self._tweet_cache:
                self._tweet_cache[tweet_id].update(tweet_data)
            else:
                self._tweet_cache[tweet_id] = tweet_data
            await self._atomic_write_json(self._tweet_cache, self.tweet_cache_file)

    async def initialize_tweet_cache(self, tweet_id: str, tweet_data: Dict[str, Any]) -> None:
        """Initialize tweet cache entry if it doesn't exist. Alias for update_tweet_data for backward compatibility."""
        await self.update_tweet_data(tweet_id, tweet_data)

    async def mark_tweet_processed(self, tweet_id: str) -> None:
        """Mark a tweet as fully processed."""
        async with self._lock:
            self._processed_tweets[tweet_id] = datetime.now(timezone.utc).isoformat()
            if tweet_id in self._unprocessed_tweets:
                self._unprocessed_tweets.remove(tweet_id)
            await self._save_state_files()

    async def get_unprocessed_tweets(self) -> List[str]:
        """Get the list of unprocessed tweet IDs."""
        if not self._initialized:
            await self.initialize()
        return list(self._unprocessed_tweets)

    async def get_processed_tweets(self) -> List[str]:
        """Get the list of processed tweet IDs."""
        if not self._initialized:
            await self.initialize()
        return list(self._processed_tweets.keys())

    async def add_tweets_to_unprocessed(self, tweet_ids: List[str]) -> None:
        """Add tweet IDs to the unprocessed list."""
        async with self._lock:
            if not self._initialized:
                await self.initialize()
            
            for tweet_id in tweet_ids:
                if tweet_id not in self._unprocessed_tweets:
                    self._unprocessed_tweets.append(tweet_id)
            
            await self._save_state_files()
            logging.info(f"Added {len(tweet_ids)} tweets to unprocessed list")

    async def get_processing_state(self, tweet_id: str) -> Dict[str, bool]:
        """Get processing state for a tweet."""
        tweet_data = await self.get_tweet(tweet_id)
        if not tweet_data:
            return {"fully_processed": False}
        
        return {
            "cache_complete": tweet_data.get("cache_complete", False),
            "media_processed": tweet_data.get("media_processed", False),
            "categories_processed": tweet_data.get("categories_processed", False),
            "kb_item_created": tweet_data.get("kb_item_created", False),
            "fully_processed": tweet_id in self._processed_tweets
        }

    async def run_validation_phase(self, phase: str) -> None:
        """Run a specific validation phase."""
        if not self._initialized:
            await self.initialize()
            return
        
        phase_methods = {
            "initial": self._run_initial_state_validation,
            "cache": self._run_cache_phase_validation,
            "media": self._run_media_phase_validation,
            "category": self._run_category_phase_validation,
            "kb_item": self._run_kb_item_phase_validation,
            "final": self._run_final_processing_validation
        }
        
        if phase in phase_methods:
            await phase_methods[phase]()
            await self._save_state_files()
            logging.info(f"Validation phase '{phase}' completed")
        else:
            raise ValueError(f"Unknown validation phase: {phase}")

    async def get_validation_stats(self) -> Dict[str, int]:
        """Get validation statistics."""
        return self.validation_stats.copy()

    # Public API methods
    async def get_tweet(self, tweet_id: str) -> Optional[Dict[str, Any]]:
        """Get tweet data from cache."""
        if not self._initialized:
            await self.initialize()
        return self._tweet_cache.get(tweet_id)

    async def get_all_tweets(self) -> Dict[str, Dict[str, Any]]:
        """Get all tweet data from cache."""
        if not self._initialized:
            await self.initialize()
        return self._tweet_cache.copy() 