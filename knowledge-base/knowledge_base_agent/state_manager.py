"""
State management module for the Knowledge Base Agent.

This module handles the persistence and reconciliation of tweet processing states, ensuring data integrity
across processed and unprocessed tweets, as well as maintaining a cache of tweet data. It provides mechanisms
for atomic file operations to prevent data corruption and includes comprehensive validation to maintain consistency
between the state and the actual knowledge base content.
"""

import json
import asyncio
import aiofiles
from pathlib import Path
from typing import Set, Dict, Any, List, Optional
import logging
from datetime import datetime
import tempfile
import os
import shutil

from knowledge_base_agent.exceptions import StateError, StateManagerError
from knowledge_base_agent.config import Config
from knowledge_base_agent.file_utils import async_write_text, async_json_load, async_json_dump
from knowledge_base_agent.tweet_utils import parse_tweet_id_from_url, load_tweet_urls_from_links


class StateManager:
    """
    Manages the state of tweet processing for the Knowledge Base Agent.

    The StateManager class is responsible for tracking which tweets have been processed, which are pending,
    and maintaining a cache of tweet data. It ensures data consistency through atomic file operations and
    performs reconciliation to handle inconsistencies between state files and the actual knowledge base.

    Attributes:
        config (Config): Configuration object for file paths and settings.
        processed_file (str): Path to the file storing processed tweet IDs.
        unprocessed_file (str): Path to the file storing unprocessed tweet IDs.
        bookmarks_file (str): Path to the bookmarks file for tweet URLs.
        processed_tweets_file (Path): Path object for processed tweets file.
        tweet_cache_file (Path): Path object for tweet cache file.
        unprocessed_tweets_file (Path): Path object for unprocessed tweets file.
        _processed_tweets (Dict[str, Any]): In-memory store of processed tweets with timestamps.
        _tweet_cache (Dict[str, Any]): In-memory cache of tweet data.
        _unprocessed_tweets (List[str]): In-memory list of unprocessed tweet IDs.
        _initialized (bool): Flag indicating if the state manager is initialized.
        _lock (asyncio.Lock): Lock for thread-safe operations.
        validation_fixes (int): Counter for validation fixes performed during reconciliation.
    """

    def __init__(self, config: Config):
        """
        Initialize the state manager with configuration settings.

        Args:
            config (Config): Configuration object containing file paths and other settings.
        """
        self.config = config
        self.processed_file = config.processed_tweets_file
        self.unprocessed_file = config.unprocessed_tweets_file
        self.bookmarks_file = config.bookmarks_file
        self.processed_tweets_file = Path(config.processed_tweets_file)
        self.tweet_cache_file = Path(config.tweet_cache_file)
        self.unprocessed_tweets_file = Path(config.unprocessed_tweets_file)
        self._processed_tweets = {}
        self._tweet_cache = {}
        self._unprocessed_tweets = []
        self._initialized = False
        self._lock = asyncio.Lock()
        self.validation_fixes = 0  # Counter for validation fixes

    @property
    def processed_tweets(self) -> Dict[str, Any]:
        """
        Get the dictionary of processed tweets.

        Returns:
            Dict[str, Any]: A dictionary mapping tweet IDs to their processing timestamps.
        """
        return self._processed_tweets
        
    @property
    def unprocessed_tweets(self) -> List[str]:
        """
        Get the list of unprocessed tweet IDs.

        Returns:
            List[str]: A list of tweet IDs that are yet to be processed.
        """
        return self._unprocessed_tweets

    async def initialize(self) -> None:
        """
        Initialize the state manager by loading existing state and reconciling inconsistencies.

        This method loads state from files, ensures directory structures exist, and performs a thorough
        reconciliation of tweet states across processed, unprocessed, and cached data. It also validates
        the knowledge base items to ensure consistency.

        Raises:
            None: Exceptions are logged but not raised to allow partial initialization.
        """
        if self._initialized:
            return

        # Reset validation counter
        self.validation_fixes = 0

        # Ensure parent directories exist
        self.tweet_cache_file.parent.mkdir(parents=True, exist_ok=True)
        self.processed_tweets_file.parent.mkdir(parents=True, exist_ok=True)
        self.unprocessed_tweets_file.parent.mkdir(parents=True, exist_ok=True)

        # Load unprocessed tweets with validation
        if self.unprocessed_tweets_file.exists():
            try:
                async with aiofiles.open(self.unprocessed_tweets_file, 'r') as f:
                    content = await f.read()
                    tweet_ids = json.loads(content) if content.strip() else []
                    # Validate data structure
                    if not isinstance(tweet_ids, list):
                        logging.error("Unprocessed tweets file contains invalid data structure, resetting")
                        tweet_ids = []
                    else:
                        tweet_ids = [str(tid) for tid in tweet_ids if isinstance(tid, (str, int))]
                    self._unprocessed_tweets = tweet_ids
                logging.info(f"Loaded {len(self._unprocessed_tweets)} unprocessed tweets")
            except Exception as e:
                logging.error(f"Error loading unprocessed tweets: {e}")
                self._unprocessed_tweets = []
                # Attempt to backup corrupted file
                try:
                    backup_path = self.unprocessed_tweets_file.with_suffix('.backup_corrupted')
                    shutil.copy2(self.unprocessed_tweets_file, backup_path)
                    logging.info(f"Backed up corrupted unprocessed tweets file to {backup_path}")
                except Exception as backup_e:
                    logging.error(f"Failed to backup corrupted unprocessed tweets file: {backup_e}")

        # Load processed tweets with validation
        if self.processed_tweets_file.exists():
            try:
                async with aiofiles.open(self.processed_tweets_file, 'r') as f:
                    content = await f.read()
                    processed_data = json.loads(content) if content.strip() else {}
                    # Validate data structure
                    if not isinstance(processed_data, dict):
                        logging.error("Processed tweets file contains invalid data structure, resetting")
                        processed_data = {}
                    else:
                        processed_data = {str(k): v for k, v in processed_data.items()}
                    self._processed_tweets = processed_data
                logging.info(f"Loaded {len(self._processed_tweets)} processed tweets")
            except Exception as e:
                logging.error(f"Error loading processed tweets: {e}")
                self._processed_tweets = {}
                # Attempt to backup corrupted file
                try:
                    backup_path = self.processed_tweets_file.with_suffix('.backup_corrupted')
                    shutil.copy2(self.processed_tweets_file, backup_path)
                    logging.info(f"Backed up corrupted processed tweets file to {backup_path}")
                except Exception as backup_e:
                    logging.error(f"Failed to backup corrupted processed tweets file: {backup_e}")

        # Remove duplicates between processed and unprocessed at load time
        initial_unprocessed_count = len(self._unprocessed_tweets)
        self._unprocessed_tweets = [tid for tid in self._unprocessed_tweets if tid not in self._processed_tweets]
        if initial_unprocessed_count != len(self._unprocessed_tweets):
            logging.info(f"Removed {initial_unprocessed_count - len(self._unprocessed_tweets)} duplicates from unprocessed tweets during load")

        # Load tweet cache
        if self.tweet_cache_file.exists():
            try:
                async with aiofiles.open(self.tweet_cache_file, 'r') as f:
                    content = await f.read()
                    cache_data = json.loads(content) if content.strip() else {}
                    # Basic validation of cache structure
                    if not isinstance(cache_data, dict):
                        logging.error("Tweet cache file contains invalid data structure, resetting")
                        cache_data = {}
                    self._tweet_cache = cache_data
                logging.info(f"Loaded {len(self._tweet_cache)} cached tweets")
            except Exception as e:
                logging.error(f"Error loading tweet cache: {e}")
                self._tweet_cache = {}
                # Attempt to backup corrupted file
                try:
                    backup_path = self.tweet_cache_file.with_suffix('.backup_corrupted')
                    shutil.copy2(self.tweet_cache_file, backup_path)
                    logging.info(f"Backed up corrupted tweet cache file to {backup_path}")
                except Exception as backup_e:
                    logging.error(f"Failed to backup corrupted tweet cache file: {backup_e}")

        # Validate KB items first to ensure paths are correct
        logging.info("Validating tweet cache integrity...")
        await self.validate_kb_items()

        # Perform a more thorough reconciliation of tweet states
        logging.info("Reconciling tweet states across processed, unprocessed, and cached lists...")
        tweets_to_process = set()
        tweets_to_mark_processed = set()
        initial_unprocessed_count = len(self._unprocessed_tweets)
        initial_processed_count = len(self._processed_tweets)

        # Ensure all cached tweets are accounted for (basic check)
        for tweet_id in self._tweet_cache:
            if tweet_id not in self._processed_tweets and tweet_id not in self._unprocessed_tweets:
                logging.info(f"Tweet {tweet_id} found in cache but not in processed/unprocessed lists, adding to unprocessed")
                self._unprocessed_tweets.append(tweet_id)
                tweets_to_process.add(tweet_id)

        # Then validate each tweet's state from the cache using the comprehensive check
        for tweet_id, tweet_data in self._tweet_cache.items():
            if not tweet_data:
                logging.warning(f"Tweet {tweet_id} has null data in cache, skipping validation.")
                if tweet_id in self._processed_tweets:
                    logging.error(f"Tweet {tweet_id} with null data found in processed list!")
                continue

            is_fully_processed_and_valid = await self._validate_tweet_state_comprehensive(tweet_id, tweet_data)

            if is_fully_processed_and_valid:
                if tweet_id not in self._processed_tweets:
                    tweets_to_mark_processed.add(tweet_id)
                    self._processed_tweets[tweet_id] = datetime.now().isoformat()
                    logging.info(f"Tweet {tweet_id} validated as fully processed, adding to processed list")
                if tweet_id in self._unprocessed_tweets:
                    self._unprocessed_tweets.remove(tweet_id)
                    logging.debug(f"Removed now-valid tweet {tweet_id} from unprocessed list")
            else:
                if tweet_id in self._processed_tweets:
                    logging.warning(f"Tweet {tweet_id} was in processed list but failed validation. Moving to unprocessed.")
                    del self._processed_tweets[tweet_id]
                    tweets_to_process.add(tweet_id)
                    self.validation_fixes += 1

                if tweet_id not in self._unprocessed_tweets:
                    tweets_to_process.add(tweet_id)
                    self._unprocessed_tweets.append(tweet_id)
                    logging.debug(f"Ensured incomplete/invalid tweet {tweet_id} is in unprocessed list")

        processed_in_unprocessed = set(self._processed_tweets.keys()).intersection(set(self._unprocessed_tweets))
        if processed_in_unprocessed:
            logging.warning(f"Found {len(processed_in_unprocessed)} tweets that are still both processed and unprocessed after validation loop. Removing from unprocessed.")
            for tweet_id in processed_in_unprocessed:
                self._unprocessed_tweets.remove(tweet_id)
                tweets_to_process.add(tweet_id)

        logging.info("Reconciling knowledge base with tweet cache...")
        valid_kb_paths = set()
        tweet_to_path = {}
        duplicates = {}
        for tweet_id, tweet_data in self._tweet_cache.items():
            if tweet_data.get('kb_item_created', False):
                kb_path = Path(tweet_data.get('kb_item_path', ''))
                if kb_path.exists() and (kb_path / "README.md").exists():
                    valid_kb_paths.add(str(kb_path))
                    if tweet_id in tweet_to_path:
                        duplicates[tweet_id] = [tweet_to_path[tweet_id], str(kb_path)]
                    else:
                        tweet_to_path[tweet_id] = str(kb_path)
                else:
                    logging.debug(f"Tweet {tweet_id} kb_item_created but path invalid: {kb_path}")
                    tweet_data['kb_item_created'] = False
                    await self.update_tweet_data(tweet_id, tweet_data)

        logging.info(f"Found {len(valid_kb_paths)} valid KB paths in tweet_cache.json")
        if duplicates:
            logging.info(f"Found {len(duplicates)} tweets with duplicate KB paths")

        kb_dir = Path(self.config.knowledge_base_dir)
        all_kb_items = set()
        for readme_path in kb_dir.rglob("README.md"):
            kb_item_path = readme_path.parent
            if str(kb_item_path) != str(kb_dir):
                all_kb_items.add(str(kb_item_path))

        logging.info(f"Found {len(all_kb_items)} KB items in {kb_dir}")
        orphans = all_kb_items - valid_kb_paths

        quarantine_dir = kb_dir / "quarantine"
        quarantine_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        for tweet_id, paths in duplicates.items():
            old_path = [p for p in paths if p != tweet_to_path[tweet_id]][0]
            quarantine_path = quarantine_dir / f"duplicate_{tweet_id}_{timestamp}"
            logging.debug(f"Moving duplicate KB item for tweet {tweet_id} from {old_path} to quarantine {quarantine_path}")
            try:
                shutil.move(old_path, quarantine_path)
            except Exception as e:
                logging.error(f"Failed to move duplicate KB item {old_path} to quarantine: {e}")

        for orphan_path in orphans:
            quarantine_path = quarantine_dir / f"orphan_{Path(orphan_path).name}_{timestamp}"
            logging.debug(f"Moving orphaned KB item from {orphan_path} to quarantine {quarantine_path}")
            try:
                shutil.move(orphan_path, quarantine_path)
            except Exception as e:
                logging.error(f"Failed to move orphaned KB item {orphan_path} to quarantine: {e}")

        logging.info(f"Moved {len(orphans)} orphaned KB items and handled {len(duplicates)} duplicates to quarantine")
        if tweets_to_process or tweets_to_mark_processed or duplicates or orphans:
            await self._atomic_write_json(list(set(self._unprocessed_tweets)), self.unprocessed_tweets_file)
            await self._atomic_write_json(self._processed_tweets, self.processed_tweets_file)
            logging.info(f"Reconciliation results: {len(tweets_to_mark_processed)} added/confirmed processed, {len(tweets_to_process)} added/confirmed unprocessed.")

        await self.cleanup_unprocessed_tweets()

        self._initialized = True
        logging.info(f"StateManager initialization complete. Final state: {len(self._unprocessed_tweets)} unprocessed, {len(self._processed_tweets)} processed.")

    async def _atomic_write_json(self, data: Any, filepath: Path) -> None:
        """
        Write JSON data atomically using a temporary file to prevent corruption.

        Args:
            data (Any): Data to be written to the file.
            filepath (Path): Path to the file where data will be written.

        Raises:
            StateError: If writing to the file fails.
        """
        temp_file = None
        try:
            temp_fd, temp_path = tempfile.mkstemp(dir=filepath.parent)
            os.close(temp_fd)
            temp_file = Path(temp_path)
            async with aiofiles.open(temp_file, 'w') as f:
                await f.write(json.dumps(data, indent=2))
            shutil.move(str(temp_file), str(filepath))
            logging.debug(f"Updated state file: {filepath}")
        except Exception as e:
            if temp_file and temp_file.exists():
                temp_file.unlink()
            logging.error(f"Failed to write state file {filepath}: {e}")
            raise StateError(f"Failed to write state file: {filepath}") from e

    async def mark_tweet_processed(self, tweet_id: str, tweet_data: Dict[str, Any] = None) -> None:
        """
        Mark a tweet as processed and remove it from the unprocessed list.

        This method checks if all processing steps are complete before marking the tweet as processed.
        If not fully processed, it logs a warning and does not update the state.

        Args:
            tweet_id (str): The ID of the tweet to mark as processed.
            tweet_data (Dict[str, Any], optional): Tweet data to validate processing steps. Defaults to None.

        Raises:
            StateError: If updating the state files fails.
        """
        async with self._lock:
            try:
                if not tweet_data:
                    logging.warning(f"No tweet data provided for {tweet_id}, skipping mark as processed")
                    return
                
                if tweet_id in self._processed_tweets:
                    logging.debug(f"Tweet {tweet_id} already marked as processed, skipping")
                    return

                required_checks = [
                    tweet_data.get('media_processed', not bool(tweet_data.get('media', []))),
                    tweet_data.get('categories_processed', False),
                    tweet_data.get('kb_item_created', False),
                    tweet_data.get('kb_item_path', None) is not None
                ]
                
                if not all(required_checks):
                    missing_steps = [
                        "media_processed" if not required_checks[0] else "",
                        "categories_processed" if not required_checks[1] else "",
                        "kb_item_created" if not required_checks[2] else "",
                        "kb_item_path" if not required_checks[3] else ""
                    ]
                    logging.warning(f"Tweet {tweet_id} not fully processed. Missing steps: {', '.join(filter(None, missing_steps))}")
                    return

                self._processed_tweets[tweet_id] = datetime.now().isoformat()
                if tweet_id in self._unprocessed_tweets:
                    self._unprocessed_tweets.remove(tweet_id)
                    logging.debug(f"Removed tweet {tweet_id} from unprocessed list")
                else:
                    logging.debug(f"Tweet {tweet_id} not in unprocessed list")

                # Persist changes immediately
                await self._atomic_write_json(list(self._unprocessed_tweets), self.unprocessed_tweets_file)
                await self._atomic_write_json(self._processed_tweets, self.processed_tweets_file)
                logging.info(f"Marked tweet {tweet_id} as fully processed; unprocessed remaining: {len(self._unprocessed_tweets)}")

            except Exception as e:
                logging.error(f"Failed to mark tweet {tweet_id} as processed: {e}")
                if tweet_id not in self._unprocessed_tweets:
                    self._unprocessed_tweets.append(tweet_id)
                raise StateError(f"Failed to update processing state: {e}")

    async def get_unprocessed_tweets(self) -> List[str]:
        """
        Get the list of unprocessed tweet IDs, ensuring the state is initialized.

        Returns:
            List[str]: A list of tweet IDs that are yet to be processed.
        """
        if not self._initialized:
            await self.initialize()
        logging.debug(f"Returning {len(self._unprocessed_tweets)} unprocessed tweet IDs")
        return list(self._unprocessed_tweets)

    async def clear_state(self) -> None:
        """
        Clear all state data, useful for testing or reset purposes.

        This method clears in-memory state and writes empty state to files.
        """
        async with self._lock:
            self._processed_tweets.clear()
            self._unprocessed_tweets.clear()
            await self._atomic_write_json({}, self.processed_tweets_file)
            await self._atomic_write_json([], self.unprocessed_tweets_file)
            logging.info("Cleared all state")

    async def update_from_bookmarks(self) -> None:
        """
        Update the list of unprocessed tweets from the bookmarks file.

        This method reads tweet URLs from the bookmarks file, extracts IDs, and adds new ones to the unprocessed list.

        Raises:
            StateManagerError: If updating from bookmarks fails.
        """
        try:
            tweet_urls = load_tweet_urls_from_links(self.config.bookmarks_file)
            tweet_ids = [parse_tweet_id_from_url(url) for url in tweet_urls]
            valid_ids = [tid for tid in tweet_ids if tid]
            new_tweets = set(valid_ids) - set(self._processed_tweets.keys())
            
            async with self._lock:
                self._unprocessed_tweets.extend(new_tweets)
                await self.save_unprocessed()
                logging.info(f"Added {len(new_tweets)} new tweets to process from bookmarks")
                for tid in new_tweets:
                    logging.debug(f"Added tweet {tid} from bookmarks")
        except Exception as e:
            logging.error(f"Failed to update from bookmarks: {e}")
            raise StateManagerError(f"Failed to update from bookmarks: {e}")

    async def save_unprocessed(self) -> None:
        """
        Save the list of unprocessed tweets to file.

        Raises:
            StateManagerError: If saving the unprocessed state fails.
        """
        try:
            await self._atomic_write_json(list(self._unprocessed_tweets), self.unprocessed_tweets_file)
            logging.debug(f"Saved {len(self._unprocessed_tweets)} unprocessed tweets")
        except Exception as e:
            logging.error(f"Failed to save unprocessed tweets: {e}")
            raise StateManagerError(f"Failed to save unprocessed state: {e}")

    async def get_processing_state(self, tweet_id: str) -> Dict[str, bool]:
        """
        Get the processing state for a specific tweet.

        Args:
            tweet_id (str): The ID of the tweet to check.

        Returns:
            Dict[str, bool]: A dictionary with flags indicating the processing status of various steps.

        Raises:
            StateError: If retrieving the processing state fails.
        """
        try:
            tweet_data = await self.get_tweet(tweet_id)
            if not tweet_data:
                logging.debug(f"No processing state found for tweet {tweet_id}")
                return {}
            state = {
                'media_processed': tweet_data.get('media_processed', False),
                'categories_processed': tweet_data.get('categories_processed', False),
                'kb_item_created': tweet_data.get('kb_item_created', False),
                'fully_processed': tweet_id in self._processed_tweets
            }
            logging.debug(f"Processing state for tweet {tweet_id}: {state}")
            return state
        except Exception as e:
            logging.error(f"Failed to get processing state for tweet {tweet_id}: {e}")
            raise StateError(f"Failed to get processing state: {e}")

    async def get_tweet(self, tweet_id: str) -> Optional[Dict[str, Any]]:
        """
        Get tweet data from the cache.

        Args:
            tweet_id (str): The ID of the tweet to retrieve.

        Returns:
            Optional[Dict[str, Any]]: The tweet data if found in cache, None otherwise.
        """
        try:
            tweet_data = self._tweet_cache.get(tweet_id)
            logging.debug(f"Retrieved tweet {tweet_id} from cache: {'found' if tweet_data else 'not found'}")
            return tweet_data
        except Exception as e:
            logging.error(f"Failed to get tweet {tweet_id} from cache: {e}")
            return None

    async def update_tweet_data(self, tweet_id: str, tweet_data: Dict[str, Any]) -> None:
        """
        Update existing tweet data in the cache without overwriting the entire cache.

        Args:
            tweet_id (str): The ID of the tweet to update.
            tweet_data (Dict[str, Any]): The new data to update for the tweet.

        Raises:
            StateError: If updating the cache file fails.
        """
        if tweet_id in self._tweet_cache:
            if 'recategorization_attempts' not in tweet_data:
                tweet_data['recategorization_attempts'] = 0
            self._tweet_cache[tweet_id].update(tweet_data)
        else:
            tweet_data['recategorization_attempts'] = tweet_data.get('recategorization_attempts', 0)
            self._tweet_cache[tweet_id] = tweet_data
        
        try:
            await self._atomic_write_json(self._tweet_cache, self.tweet_cache_file)
        except Exception as e:
            logging.error(f"Failed to save updated tweet cache: {e}")
            raise StateError(f"Cache update failed: {e}")

    async def get_all_tweets(self) -> Dict[str, Dict[str, Any]]:
        """
        Get all cached tweet data.

        Returns:
            Dict[str, Dict[str, Any]]: A copy of the entire tweet cache.
        """
        logging.debug(f"Returning all {len(self._tweet_cache)} cached tweets")
        return self._tweet_cache.copy()

    async def save_tweet_cache(self, tweet_id: str, data: Dict[str, Any]) -> None:
        """
        Save tweet data to the cache without overwriting the entire cache.

        Args:
            tweet_id (str): The ID of the tweet to save.
            data (Dict[str, Any]): The tweet data to save.

        Raises:
            StateError: If saving to the cache file fails.
        """
        self._tweet_cache[tweet_id] = data
        try:
            await self._atomic_write_json(self._tweet_cache, self.tweet_cache_file)
            logging.debug(f"Saved tweet {tweet_id} to cache")
        except Exception as e:
            logging.error(f"Failed to save tweet cache for {tweet_id}: {e}")
            raise StateError(f"Cache save failed: {e}")

    async def get_tweet_cache(self, tweet_id: str) -> Optional[Dict[str, Any]]:
        """
        Get cached tweet data if available.

        Args:
            tweet_id (str): The ID of the tweet to retrieve.

        Returns:
            Optional[Dict[str, Any]]: The tweet data if found in cache, None otherwise.
        """
        tweet_data = self._tweet_cache.get(tweet_id)
        logging.debug(f"Retrieved tweet {tweet_id} from cache: {'found' if tweet_data else 'not found'}")
        return tweet_data

    async def verify_cache_status(self) -> List[str]:
        """
        Verify cache status for all unprocessed tweets.

        Returns:
            List[str]: A list of tweet IDs that need caching or cache updates.
        """
        tweets_needing_cache = []
        for tweet_id in self._unprocessed_tweets:
            cached_data = self._tweet_cache.get(tweet_id)
            if not cached_data or not cached_data.get('cache_complete', False):
                tweets_needing_cache.append(tweet_id)
                logging.debug(f"Tweet {tweet_id} needs cache update")
        logging.info(f"Verified cache status: {len(tweets_needing_cache)} tweets need caching")
        return tweets_needing_cache

    async def update_media_analysis(self, tweet_id: str, media_analysis: Dict[str, Any]) -> None:
        """
        Update tweet cache with media analysis results.

        Args:
            tweet_id (str): The ID of the tweet to update.
            media_analysis (Dict[str, Any]): The media analysis data to store.

        Raises:
            StateError: If the tweet is not found in cache or if updating fails.
        """
        if tweet_id not in self._tweet_cache:
            logging.error(f"Tweet {tweet_id} not found in cache for media analysis update")
            raise StateError(f"Tweet {tweet_id} not found in cache")
        
        self._tweet_cache[tweet_id].update({
            'media_analysis': media_analysis,
            'media_analysis_complete': True
        })
        await self._atomic_write_json(self._tweet_cache, self.tweet_cache_file)
        logging.debug(f"Updated media analysis for tweet {tweet_id}")

    async def update_categories(self, tweet_id: str, category_data: Dict[str, Any]) -> None:
        """
        Update tweet cache with categorization results.

        Args:
            tweet_id (str): The ID of the tweet to update.
            category_data (Dict[str, Any]): The categorization data to store.

        Raises:
            StateError: If the tweet is not found in cache or if updating fails.
        """
        if tweet_id not in self._tweet_cache:
            logging.error(f"Tweet {tweet_id} not found in cache for category update")
            raise StateError(f"Tweet {tweet_id} not found in cache")
        
        self._tweet_cache[tweet_id].update({
            'category': category_data.get('category'),
            'subcategory': category_data.get('subcategory'),
            'item_name': category_data.get('item_name'),
            'categories_processed': True
        })
        await self._atomic_write_json(self._tweet_cache, self.tweet_cache_file)
        logging.debug(f"Updated categories for tweet {tweet_id}")

    async def mark_kb_item_created(self, tweet_id: str, kb_item_path: str) -> None:
        """
        Mark a tweet as having a knowledge base item created and update the cache.

        Args:
            tweet_id (str): The ID of the tweet to update.
            kb_item_path (str): The path to the created knowledge base item.

        Raises:
            StateError: If the tweet is not found in cache or if updating fails.
        """
        if tweet_id not in self._tweet_cache:
            logging.error(f"Tweet {tweet_id} not found in cache for KB item creation")
            raise StateError(f"Tweet {tweet_id} not found in cache")
        
        self._tweet_cache[tweet_id].update({
            'kb_item_path': kb_item_path,
            'kb_item_created': True
        })
        await self._atomic_write_json(self._tweet_cache, self.tweet_cache_file)
        logging.debug(f"Marked KB item created for tweet {tweet_id} at {kb_item_path}")

    async def mark_media_processed(self, tweet_id: str) -> None:
        """
        Mark media as processed for a tweet.

        Args:
            tweet_id (str): The ID of the tweet to update.

        Raises:
            StateError: If updating the tweet data fails.
        """
        try:
            tweet_data = await self.get_tweet(tweet_id)
            if tweet_data:
                tweet_data['media_processed'] = True
                await self.update_tweet_data(tweet_id, tweet_data)
                logging.debug(f"Marked media as processed for tweet {tweet_id}")
        except Exception as e:
            logging.error(f"Failed to mark media as processed for tweet {tweet_id}: {e}")
            raise StateError(f"Failed to mark media as processed: {e}")

    async def mark_categories_processed(self, tweet_id: str) -> None:
        """
        Mark categories as processed for a tweet.

        Args:
            tweet_id (str): The ID of the tweet to update.

        Raises:
            StateError: If updating the tweet data fails.
        """
        try:
            tweet_data = await self.get_tweet(tweet_id)
            if tweet_data:
                tweet_data['categories_processed'] = True
                await self.update_tweet_data(tweet_id, tweet_data)
                logging.debug(f"Marked categories as processed for tweet {tweet_id}")
        except Exception as e:
            logging.error(f"Failed to mark categories as processed for tweet {tweet_id}: {e}")
            raise StateError(f"Failed to mark categories as processed: {e}")

    async def initialize_tweet_cache(self, tweet_id: str, tweet_data: Dict[str, Any]) -> None:
        """
        Initialize a new tweet in the cache with its basic data.

        Args:
            tweet_id (str): The ID of the tweet to initialize.
            tweet_data (Dict[str, Any]): The initial data for the tweet.
        """
        if tweet_id in self._tweet_cache:
            logging.debug(f"Tweet {tweet_id} already in cache, updating...")
        
        base_data = {
            'tweet_id': tweet_id,
            'full_text': tweet_data.get('full_text', ''),
            'created_at': tweet_data.get('created_at', ''),
            'author': tweet_data.get('author', ''),
            'media': tweet_data.get('media', []),
            'downloaded_media': tweet_data.get('downloaded_media', []),
            'media_analysis': {},
            'media_processed': False,
            'media_analysis_complete': False,
            'category': '',
            'subcategory': '',
            'item_name': '',
            'categories_processed': False,
            'kb_item_path': '',
            'kb_item_created': False,
            'cache_complete': False,
            'fully_processed': False
        }
        
        base_data.update(tweet_data)
        await self.update_tweet_data(tweet_id, base_data)
        logging.debug(f"Initialized cache for tweet {tweet_id}")

    async def mark_tweet_unprocessed(self, tweet_id: str) -> None:
        """
        Move a processed tweet back to the unprocessed state.

        Args:
            tweet_id (str): The ID of the tweet to mark as unprocessed.
        """
        if tweet_id in self._processed_tweets:
            self._unprocessed_tweets.append(tweet_id)
            del self._processed_tweets[tweet_id]
            await self.save_unprocessed()
            logging.debug(f"Marked tweet {tweet_id} as unprocessed")

    async def _validate_tweet_state_comprehensive(self, tweet_id: str, tweet_data: Dict[str, Any]) -> bool:
        """
        Comprehensively validate a tweet's state, updating flags if invalid.

        Args:
            tweet_id (str): The ID of the tweet to validate.
            tweet_data (Dict[str, Any]): The tweet data to validate against.

        Returns:
            bool: True if the tweet is fully processed and valid, False otherwise.
        """
        all_valid = True
        updates_needed = {}
        max_recategorization_attempts = 3
        default_category_tuples = [
            ("Uncategorized", "General"),
            ("Uncategorized", "Default"),
            ("software_engineering", "best_practices"),
            # Add any other known fallback/default category pairs here
        ]

        # Ensure recategorization_attempts exists
        if 'recategorization_attempts' not in tweet_data:
            updates_needed['recategorization_attempts'] = 0
            tweet_data['recategorization_attempts'] = 0 # Update local copy for subsequent checks

        # Check cache completion
        if not tweet_data.get('cache_complete', False):
            # Cache is considered incomplete if any previous step is not done
            all_valid = False

        # Validate media processing
        has_media = bool(tweet_data.get('media', []))
        media_paths = tweet_data.get('downloaded_media', [])
        media_processed = tweet_data.get('media_processed', False)

        if has_media:
            if not media_processed:
                all_valid = False
            elif not media_paths or not all(Path(p).exists() for p in media_paths):
                logging.warning(f"Tweet {tweet_id} marked media_processed but has missing files: {media_paths}")
                updates_needed['media_processed'] = False
                updates_needed['cache_complete'] = False # Invalidate cache if media files missing
                all_valid = False
        elif not media_processed:
            # No media, mark as processed if not already
            updates_needed['media_processed'] = True

        # Validate categories
        categories_processed = tweet_data.get('categories_processed', False)
        categories = tweet_data.get('categories', {})
        recategorization_attempts = tweet_data.get('recategorization_attempts', 0)

        if not categories_processed:
            all_valid = False
        else:
            required_fields = ['main_category', 'sub_category', 'item_name']
            if not categories or not all(categories.get(f) for f in required_fields):
                logging.warning(f"Tweet {tweet_id} categories_processed but missing category fields: {required_fields}")
                updates_needed['categories_processed'] = False
                updates_needed['cache_complete'] = False # Invalidate cache
                all_valid = False
            else:
                # Check if category is EXACTLY one of the default pairs
                current_main_cat = categories.get('main_category', '')
                current_sub_cat = categories.get('sub_category', '')
                current_item_name = categories.get('item_name', '') # Get item name

                # *** FIX: Check item_name specificity along with default pair ***
                is_default_pair = (current_main_cat, current_sub_cat) in default_category_tuples
                # Consider item name generic if it starts with 'Tweet-' or is very short (e.g., < 5 chars)
                is_generic_item_name = current_item_name.startswith('Tweet-') or len(current_item_name) < 5

                # Only trigger re-categorization if it's a default pair AND the item name looks generic
                if is_default_pair and is_generic_item_name and recategorization_attempts < max_recategorization_attempts:
                    logging.info(f"Tweet {tweet_id} has default category pair ({current_main_cat}, {current_sub_cat}) AND generic item name '{current_item_name}', marking for re-categorization (attempt {recategorization_attempts + 1}/{max_recategorization_attempts})")
                    updates_needed['categories_processed'] = False
                    updates_needed['categories'] = {}
                    updates_needed['recategorization_attempts'] = recategorization_attempts + 1
                    updates_needed['cache_complete'] = False
                    all_valid = False
                elif is_default_pair and not is_generic_item_name:
                     logging.debug(f"Tweet {tweet_id} has default category pair ({current_main_cat}, {current_sub_cat}) but specific item name '{current_item_name}', accepting as valid.")
                elif is_default_pair and is_generic_item_name and recategorization_attempts >= max_recategorization_attempts:
                     logging.warning(f"Tweet {tweet_id} reached max re-categorization attempts ({max_recategorization_attempts}) with default category pair ({current_main_cat}, {current_sub_cat}) and generic item name '{current_item_name}'")

        # Validate KB item
        kb_item_created = tweet_data.get('kb_item_created', False)
        kb_path_str = tweet_data.get('kb_item_path', '')

        if not kb_item_created:
            # Check if KB item exists but isn't marked as created
            found_path = await self._find_and_update_kb_item_path(tweet_id, tweet_data)
            if found_path:
                updates_needed['kb_item_path'] = found_path
                updates_needed['kb_item_created'] = True
                logging.info(f"Found existing KB item for tweet {tweet_id} at {found_path}, marking created.")
            else:
                all_valid = False # Still needs creation
        else:
            # kb_item_created is True, validate the path
            if not kb_path_str:
                logging.warning(f"Tweet {tweet_id} kb_item_created but path is empty")
                updates_needed['kb_item_created'] = False
                updates_needed['cache_complete'] = False # Invalidate cache
                all_valid = False
            else:
                # Validate existence of the README.md within the path
                try:
                    kb_base = Path(self.config.knowledge_base_dir)
                    # Handle potentially different path formats (relative/absolute) robustly
                    if kb_path_str.startswith('kb-generated/'):
                         # Assuming 'kb-generated' is sibling to the base dir parent? Adjust if needed.
                        relative_kb_path = Path(kb_path_str)
                        # This assumes kb_base.parent is the project root where kb-generated lives
                        kb_path = kb_base.parent / relative_kb_path
                    elif Path(kb_path_str).is_absolute():
                         # If it's absolute, check if it's within the expected KB structure
                        kb_path = Path(kb_path_str)
                        if not kb_path.is_relative_to(kb_base):
                             logging.warning(f"Tweet {tweet_id} KB path {kb_path_str} is absolute but outside base {kb_base}")
                             # Decide how to handle this - maybe try to find relative path? For now, invalidate.
                             updates_needed['kb_item_created'] = False
                             updates_needed['cache_complete'] = False
                             all_valid = False
                    else:
                         # Assume relative to knowledge_base_dir
                        kb_path = kb_base / kb_path_str

                    # Now check for README.md, ensuring kb_path was determined
                    if 'kb_item_created' not in updates_needed or updates_needed['kb_item_created']:
                        readme_path = kb_path / "README.md"
                        if not readme_path.exists():
                            logging.warning(f"Tweet {tweet_id} KB item README not found at {readme_path} (derived from {kb_path_str})")
                            updates_needed['kb_item_created'] = False
                            updates_needed['kb_item_path'] = '' # Clear invalid path
                            updates_needed['cache_complete'] = False # Invalidate cache
                            all_valid = False

                except Exception as e:
                    logging.error(f"Error validating KB item path '{kb_path_str}' for tweet {tweet_id}: {e}")
                    updates_needed['kb_item_created'] = False
                    updates_needed['kb_item_path'] = ''
                    updates_needed['cache_complete'] = False
                    all_valid = False

        # If any check failed, ensure cache_complete is false
        if not all_valid:
             updates_needed['cache_complete'] = False


        # Apply updates if any were identified
        if updates_needed:
            # Preserve existing data and update only the necessary fields
            current_data = self._tweet_cache.get(tweet_id, {})
            current_data.update(updates_needed)
            await self.update_tweet_data(tweet_id, current_data) # Use update_tweet_data to save atomically
            logging.debug(f"Updated tweet {tweet_id} state due to validation: {updates_needed}")
            self.validation_fixes += 1

        # Final decision based on potentially updated data
        final_data = self._tweet_cache.get(tweet_id, {})
        is_complete_and_valid = (
            final_data.get('cache_complete', False) and
            final_data.get('media_processed', False) and
            final_data.get('categories_processed', False) and
            final_data.get('kb_item_created', False) and
            bool(final_data.get('kb_item_path')) # Ensure path is not empty
        )

        return is_complete_and_valid

    async def _find_and_update_kb_item_path(self, tweet_id: str, tweet_data: Dict[str, Any]) -> Optional[str]:
        """
        Try to find an existing knowledge base item README for a tweet and return its relative path if found.

        Args:
            tweet_id (str): The ID of the tweet to search for.
            tweet_data (Dict[str, Any]): The tweet data to use for path construction hints.

        Returns:
            Optional[str]: The relative path string if found, otherwise None.
        """
        kb_base = Path(self.config.knowledge_base_dir)
        search_paths = []

        # Hint 1: Based on current/legacy category info in tweet_data
        cat_info = tweet_data.get('categories', {})
        main_cat = cat_info.get('main_category') or tweet_data.get('category')
        sub_cat = cat_info.get('sub_category') or tweet_data.get('subcategory')
        item_name = cat_info.get('item_name') or tweet_data.get('item_name')
        if main_cat and sub_cat and item_name:
             # Check both potential structures (relative to kb_base and relative to parent)
             search_paths.append(kb_base / main_cat / sub_cat / item_name)
             # If kb-generated is a standard prefix, check relative to parent
             if kb_base.parent:
                 search_paths.append(kb_base.parent / "kb-generated" / main_cat / sub_cat / item_name)


        # Hint 2: Search common locations by iterating if hints fail
        # (Avoid full recursive search unless necessary, it's slow)
        # For now, rely on hints. If hints fail, full validation scan might catch it later.

        # Check potential paths for README.md containing the tweet URL
        expected_url = f"https://twitter.com/i/web/status/{tweet_id}"
        for path in search_paths:
            if path and path.exists() and path.is_dir():
                readme_path = path / "README.md"
                if readme_path.exists():
                    try:
                        async with aiofiles.open(readme_path, 'r', encoding='utf-8') as f:
                            content = await f.read(2048) # Read first 2KB
                            if expected_url in content:
                                # Found it, return relative path from kb_base.parent
                                try:
                                    relative_path = path.relative_to(kb_base.parent)
                                    return str(relative_path)
                                except ValueError:
                                     # If not relative to parent, maybe relative to base?
                                     try:
                                         relative_path = path.relative_to(kb_base)
                                         # Prepend base dir name if returning relative to parent
                                         return str(kb_base.name / relative_path)
                                     except ValueError:
                                          logging.warning(f"Found README for {tweet_id} at {path}, but couldn't determine relative path from {kb_base.parent} or {kb_base}")
                                          return None # Or return absolute path as string? Decide policy.

                    except Exception as e:
                        logging.warning(f"Error reading potential README at {readme_path}: {e}")
                        continue
        return None

    async def _find_and_update_kb_item(self, tweet_id: str, tweet_data: Dict[str, Any], updates_needed: Dict[str, Any]) -> None:
        """
        Find a knowledge base item for a tweet and update state if found.
        DEPRECATED: Use _find_and_update_kb_item_path instead and apply updates in the caller.
        """
        # This method is now largely replaced by the logic within _validate_tweet_state_comprehensive
        # and _find_and_update_kb_item_path. Keeping stub for compatibility if called elsewhere,
        # but it should ideally be removed.
        logging.warning("_find_and_update_kb_item is deprecated. Validation logic moved.")
        found_path = await self._find_and_update_kb_item_path(tweet_id, tweet_data)
        if found_path:
             updates_needed['kb_item_path'] = found_path
             updates_needed['kb_item_created'] = True

    async def validate_kb_items(self) -> None:
        """
        Validate knowledge base items for all tweets and update paths if found.

        This method scans the knowledge base directory to map tweet IDs to their README files and updates
        the cache for tweets missing KB item paths.
        """
        logging.info("Validating KB items for all tweets...")
        kb_base = Path(self.config.knowledge_base_dir)
        
        # First, build a mapping of tweet IDs to README files
        tweet_id_to_readme = {}
        for readme_path in kb_base.rglob("README.md"):
            try:
                async with aiofiles.open(readme_path, 'r') as f:
                    content = await f.read()
                    # Extract tweet ID from content
                    for line in content.splitlines():
                        if "twitter.com/i/web/status/" in line:
                            tweet_id_match = line.split("twitter.com/i/web/status/")[1].split('"')[0].split("?")[0]
                            if tweet_id_match:
                                tweet_id_to_readme[tweet_id_match] = readme_path
                                break
            except Exception as e:
                logging.warning(f"Error reading README at {readme_path}: {e}")
                continue
        
        logging.info(f"Found {len(tweet_id_to_readme)} README files with tweet IDs")
        
        # Now check all tweets with null kb_item_path
        updates = 0
        for tweet_id, tweet_data in self._tweet_cache.items():
            if not tweet_data.get('kb_item_path') or not tweet_data.get('kb_item_created'):
                if tweet_id in tweet_id_to_readme:
                    readme_path = tweet_id_to_readme[tweet_id]
                    kb_item_path = readme_path.parent
                    relative_path = kb_item_path.relative_to(kb_base.parent)
                    
                    tweet_data['kb_item_path'] = str(relative_path)
                    tweet_data['kb_item_created'] = True
                    await self.update_tweet_data(tweet_id, tweet_data)
                    
                    logging.info(f"Updated tweet {tweet_id} with KB item path: {relative_path}")
                    updates += 1
        
        logging.info(f"Updated {updates} tweets with KB item paths")
        self.validation_fixes += updates

    async def finalize_processing(self) -> None:
        """
        Perform final validation and move completed tweets to the processed list.

        This method ensures that fully processed tweets are moved from unprocessed to processed state.
        """
        logging.info("Finalizing processing and validating tweet states...")
        
        moved_to_processed = 0
        for tweet_id in list(self._unprocessed_tweets):  # Use list to avoid modification during iteration
            tweet_data = self._tweet_cache.get(tweet_id)
            if not tweet_data:
                logging.warning(f"Tweet {tweet_id} in unprocessed list but not in cache, removing")
                self._unprocessed_tweets.remove(tweet_id)
                continue
            
            is_fully_processed = await self._validate_tweet_state_comprehensive(tweet_id, tweet_data)
            if is_fully_processed:
                self._processed_tweets[tweet_id] = datetime.now().isoformat()
                self._unprocessed_tweets.remove(tweet_id)
                moved_to_processed += 1
                logging.info(f"Finalized tweet {tweet_id} and moved to processed")
        
        if moved_to_processed > 0:
            await self._atomic_write_json(list(self._unprocessed_tweets), self.unprocessed_tweets_file)
            await self._atomic_write_json(self._processed_tweets, self.processed_tweets_file)
            logging.info(f"Finalization complete: moved {moved_to_processed} tweets to processed")

    async def cleanup_unprocessed_tweets(self) -> None:
        """
        Clean up the unprocessed tweets list by removing any that are already processed or don't exist in cache.

        This method ensures the unprocessed list is accurate by removing tweets that are either processed
        or missing from the cache.
        """
        logging.info("Cleaning up unprocessed tweets list...")
        
        initial_count = len(self._unprocessed_tweets)
        to_remove = []
        
        for tweet_id in self._unprocessed_tweets:
            # Remove if already in processed list
            if tweet_id in self._processed_tweets:
                to_remove.append(tweet_id)
                logging.debug(f"Tweet {tweet_id} is already in processed list, removing from unprocessed")
                continue
            
            # Remove if not in tweet cache
            if tweet_id not in self._tweet_cache:
                to_remove.append(tweet_id)
                logging.debug(f"Tweet {tweet_id} not found in cache, removing from unprocessed")
                continue
            
            # Check if it's fully processed
            tweet_data = self._tweet_cache[tweet_id]
            is_fully_processed = (
                tweet_data.get('cache_complete', False) and
                tweet_data.get('media_processed', False) and
                tweet_data.get('categories_processed', False) and
                tweet_data.get('kb_item_created', False) and
                tweet_data.get('kb_item_path')
            )
            
            if is_fully_processed:
                # Move to processed list
                self._processed_tweets[tweet_id] = datetime.now().isoformat()
                to_remove.append(tweet_id)
                logging.info(f"Tweet {tweet_id} is fully processed, moving to processed list")
        
        # Remove from unprocessed list
        for tweet_id in to_remove:
            self._unprocessed_tweets.remove(tweet_id)
        
        # Save changes
        if to_remove:
            await self._atomic_write_json(list(self._unprocessed_tweets), self.unprocessed_tweets_file)
            await self._atomic_write_json(self._processed_tweets, self.processed_tweets_file)
        
        removed_count = initial_count - len(self._unprocessed_tweets)
        logging.info(f"Cleaned up {removed_count} tweets from unprocessed list")

    async def is_tweet_processed(self, tweet_id: str) -> bool:
        """
        Check if a tweet has been processed.

        Args:
            tweet_id (str): The ID of the tweet to check.

        Returns:
            bool: True if the tweet is in the processed list, False otherwise.
        """
        if not self._initialized:
            await self.initialize()
        return tweet_id in self._processed_tweets
