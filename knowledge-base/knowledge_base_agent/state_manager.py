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
from datetime import datetime, timezone
import tempfile
import os
import shutil
import re
import copy

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
        processed_tweets_file (Path): Absolute path object for processed tweets file.
        tweet_cache_file (Path): Absolute path object for tweet cache file.
        unprocessed_tweets_file (Path): Absolute path object for unprocessed tweets file.
        bookmarks_file (Path): Absolute path object for bookmarks file.
        _processed_tweets (Dict[str, Any]): In-memory store of processed tweets with timestamps.
        _tweet_cache (Dict[str, Any]): In-memory cache of tweet data. Paths stored here (like kb_item_path, media paths) should be relative to project_root.
        _unprocessed_tweets (List[str]): In-memory list of unprocessed tweet IDs.
        _initialized (bool): Flag indicating if the state manager is initialized.
        _lock (asyncio.Lock): Lock for thread-safe operations.
        validation_fixes (int): Counter for validation fixes performed during reconciliation.
    """

    def __init__(self, config: Config):
        """
        Initialize the state manager with configuration settings.

        Args:
            config (Config): Configuration object containing file paths (which are absolute) and other settings.
        """
        self.config = config
        # Config paths are already absolute
        self.processed_tweets_file = config.processed_tweets_file
        self.unprocessed_tweets_file = config.unprocessed_tweets_file
        self.bookmarks_file = config.bookmarks_file 
        self.tweet_cache_file = config.tweet_cache_file
        
        self._processed_tweets = {}
        self._tweet_cache = {}
        self._unprocessed_tweets = []
        self._initialized = False
        self._lock = asyncio.Lock()
        self.validation_fixes = 0  

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

    async def get_all_processed_tweet_ids(self) -> List[str]:
        """Returns a list of all tweet IDs marked as processed."""
        async with self._lock:
            return list(self._processed_tweets.keys())

    async def initialize(self) -> None:
        """
        Initialize the state manager by loading existing state and reconciling inconsistencies.
        Also synchronizes existing knowledge base items to the local database.
        """
        if self._initialized:
            return

        self.validation_fixes = 0

        # Parent directories for state files are created by Config path resolution

        if self.unprocessed_tweets_file.exists():
            try:
                async with aiofiles.open(self.unprocessed_tweets_file, 'r') as f:
                    content = await f.read()
                    tweet_ids = json.loads(content) if content.strip() else []
                    if not isinstance(tweet_ids, list):
                        logging.error("Unprocessed tweets file contains invalid data structure, resetting")
                        tweet_ids = []
                    else:
                        tweet_ids = [str(tid) for tid in tweet_ids if isinstance(tid, (str, int))]
                    self._unprocessed_tweets = tweet_ids
                logging.info(f"Loaded {len(self._unprocessed_tweets)} unprocessed tweets from {self.unprocessed_tweets_file}")
            except Exception as e:
                logging.error(f"Error loading unprocessed tweets from {self.unprocessed_tweets_file}: {e}")
                self._unprocessed_tweets = []
                try:
                    backup_path = self.unprocessed_tweets_file.with_suffix('.backup_corrupted')
                    shutil.copy2(self.unprocessed_tweets_file, backup_path)
                    logging.info(f"Backed up corrupted unprocessed tweets file to {backup_path}")
                except Exception as backup_e:
                    logging.error(f"Failed to backup corrupted unprocessed tweets file: {backup_e}")

        if self.processed_tweets_file.exists():
            try:
                async with aiofiles.open(self.processed_tweets_file, 'r') as f:
                    content = await f.read()
                    processed_data = json.loads(content) if content.strip() else {}
                    if not isinstance(processed_data, dict):
                        logging.error("Processed tweets file contains invalid data structure, resetting")
                        processed_data = {}
                    else:
                        processed_data = {str(k): v for k, v in processed_data.items()}
                    self._processed_tweets = processed_data
                logging.info(f"Loaded {len(self._processed_tweets)} processed tweets from {self.processed_tweets_file}")
            except Exception as e:
                logging.error(f"Error loading processed tweets from {self.processed_tweets_file}: {e}")
                self._processed_tweets = {}
                try:
                    backup_path = self.processed_tweets_file.with_suffix('.backup_corrupted')
                    shutil.copy2(self.processed_tweets_file, backup_path)
                    logging.info(f"Backed up corrupted processed tweets file to {backup_path}")
                except Exception as backup_e:
                    logging.error(f"Failed to backup corrupted processed tweets file: {backup_e}")

        initial_unprocessed_count = len(self._unprocessed_tweets)
        self._unprocessed_tweets = [tid for tid in self._unprocessed_tweets if tid not in self._processed_tweets]
        if initial_unprocessed_count != len(self._unprocessed_tweets):
            logging.info(f"Removed {initial_unprocessed_count - len(self._unprocessed_tweets)} duplicates from unprocessed (already in processed) during load")

        if self.tweet_cache_file.exists():
            try:
                async with aiofiles.open(self.tweet_cache_file, 'r') as f:
                    content = await f.read()
                    cache_data = json.loads(content) if content.strip() else {}
                    if not isinstance(cache_data, dict):
                        logging.error("Tweet cache file contains invalid data structure, resetting")
                        cache_data = {}
                    self._tweet_cache = cache_data
                logging.info(f"Loaded {len(self._tweet_cache)} cached tweets from {self.tweet_cache_file}")
            except Exception as e:
                logging.error(f"Error loading tweet cache from {self.tweet_cache_file}: {e}")
                self._tweet_cache = {}
                try:
                    backup_path = self.tweet_cache_file.with_suffix('.backup_corrupted')
                    shutil.copy2(self.tweet_cache_file, backup_path)
                    logging.info(f"Backed up corrupted tweet cache file to {backup_path}")
                except Exception as backup_e:
                    logging.error(f"Failed to backup corrupted tweet cache file: {backup_e}")

        logging.info("Proactively checking tweet_bookmarks.json...")
        try:
            bookmarked_tweet_ids_to_consider = set()
            if self.bookmarks_file.exists():
                try:
                    async with aiofiles.open(self.bookmarks_file, 'r', encoding='utf-8') as f:
                        content = await f.read()
                    bookmarks_data = json.loads(content) if content.strip() else {}
                    if not isinstance(bookmarks_data, dict):
                        logging.error(f"Bookmarks file {self.bookmarks_file} is not a valid JSON object, treating as empty.")
                        bookmarks_data = {}
                except Exception as e:
                    logging.error(f"Error loading or parsing bookmarks file {self.bookmarks_file}: {e}")
                    bookmarks_data = {} 
                
                for tweet_id_key in bookmarks_data.keys(): 
                    if isinstance(tweet_id_key, str) and tweet_id_key.isdigit():
                        bookmarked_tweet_ids_to_consider.add(tweet_id_key)
                    else:
                        parsed_id = parse_tweet_id_from_url(str(tweet_id_key)) 
                        if parsed_id:
                            bookmarked_tweet_ids_to_consider.add(parsed_id)
                        else:
                            logging.warning(f"Could not extract a valid tweet ID from bookmark key: '{tweet_id_key}'")
                logging.info(f"Found {len(bookmarked_tweet_ids_to_consider)} unique tweet IDs in bookmarks file.")
            else:
                logging.info(f"Bookmarks file not found at {self.bookmarks_file}, skipping proactive bookmark check.")

            newly_added_from_bookmarks = 0
            current_unprocessed_set = set(self._unprocessed_tweets) 

            for tweet_id in bookmarked_tweet_ids_to_consider:
                if tweet_id not in self._processed_tweets and tweet_id not in current_unprocessed_set:
                    self._unprocessed_tweets.append(tweet_id)
                    current_unprocessed_set.add(tweet_id) 
                    newly_added_from_bookmarks += 1
                    logging.debug(f"Proactively added tweet {tweet_id} from bookmarks.json to unprocessed queue.")
                    if tweet_id not in self._tweet_cache:
                        logging.debug(f"Tweet {tweet_id} from bookmarks not in cache. Initializing basic cache entry.")
                        await self.initialize_tweet_cache(tweet_id, {'tweet_id': tweet_id, 'source': 'bookmark_init'})
            
            if newly_added_from_bookmarks > 0:
                logging.info(f"Proactively added {newly_added_from_bookmarks} tweets from bookmarks.json to the unprocessed queue.")
            else:
                logging.info("No new tweets from bookmarks.json needed to be added to the unprocessed queue at this stage.")

        except Exception as e:
            logging.error(f"Error during proactive check of tweet_bookmarks.json: {e}", exc_info=True)

        logging.info("Validating tweet cache integrity (KB item paths and existence)...")
        await self.validate_kb_items() # Uses self.config for path resolution

        logging.info("Reconciling tweet states across processed, unprocessed, and cached lists...")
        tweets_to_process = set() 
        tweets_to_mark_processed = set()
        initial_unprocessed_count_recon = len(self._unprocessed_tweets)
        initial_processed_count_recon = len(self._processed_tweets)

        # Counters for startup validation summary
        summary_stats = {
            "total_tweets_validated": 0,
            "fully_valid_and_complete": 0,
            "needs_cache_completion": 0,
            "needs_media_processing": 0,
            "needs_categorization": 0, # General counter for needing categorization
            "marked_for_recategorization": 0, # Specific counter for explicit re-categorization triggers
            "needs_kb_item_creation": 0,
            "kb_item_path_issues": 0, # README non-existent or path empty despite kb_item_created=True
        }

        processed_ids_copy = list(self._processed_tweets.keys()) 
        for tweet_id in processed_ids_copy:
            if tweet_id not in self._tweet_cache:
                logging.warning(f"Tweet {tweet_id} is in processed list but not in tweet_cache. Moving to unprocessed for full processing.")
                if tweet_id in self._processed_tweets: 
                    del self._processed_tweets[tweet_id]
                if tweet_id not in self._unprocessed_tweets:
                    self._unprocessed_tweets.append(tweet_id)
                tweets_to_process.add(tweet_id) 
                self.validation_fixes += 1

        cached_ids_copy = list(self._tweet_cache.keys()) 
        for tweet_id in cached_ids_copy:
            tweet_data_before_validation = copy.deepcopy(self._tweet_cache.get(tweet_id, {})) # Get a copy before validation
            
            if not tweet_data_before_validation:
                logging.warning(f"Tweet {tweet_id} key exists in cache but data is null during validation. Skipping.")
                continue

            summary_stats["total_tweets_validated"] += 1
            is_fully_processed_and_valid = await self._validate_tweet_state_comprehensive(tweet_id, tweet_data_before_validation) # Pass the copy

            # Update summary stats based on the final state of the tweet_data after validation
            final_tweet_data = self._tweet_cache.get(tweet_id, {}) # Re-fetch the (potentially modified) data

            if is_fully_processed_and_valid:
                summary_stats["fully_valid_and_complete"] += 1
                if tweet_id not in self._processed_tweets:
                    self._processed_tweets[tweet_id] = datetime.now(timezone.utc).isoformat()
                    logging.info(f"Tweet {tweet_id} validated as fully processed by comprehensive check, ensuring it is in processed list.")
                    tweets_to_mark_processed.add(tweet_id)
                if tweet_id in self._unprocessed_tweets:
                    self._unprocessed_tweets.remove(tweet_id)
                    logging.debug(f"Removed comprehensively validated tweet {tweet_id} from unprocessed list.")
            else: 
                # Increment specific counters if not fully valid
                if not final_tweet_data.get('cache_complete', False):
                    summary_stats["needs_cache_completion"] += 1
                if not final_tweet_data.get('media_processed', False):
                    summary_stats["needs_media_processing"] += 1
                
                current_categories_processed = final_tweet_data.get('categories_processed', False)
                if not current_categories_processed:
                     summary_stats["needs_categorization"] += 1
                
                # Check if it was marked for re-categorization
                # This happens if categories_processed is False AND recategorization_attempts increased.
                original_attempts = tweet_data_before_validation.get('recategorization_attempts', 0)
                final_attempts = final_tweet_data.get('recategorization_attempts', 0)
                if not current_categories_processed and final_attempts > original_attempts:
                    summary_stats["marked_for_recategorization"] += 1

                if not final_tweet_data.get('kb_item_created', False):
                    summary_stats["needs_kb_item_creation"] += 1
                elif final_tweet_data.get('kb_item_created', False): # kb_item_created is true
                    kb_path_rel = final_tweet_data.get('kb_item_path', '')
                    kb_readme_abs = self.config.resolve_path_from_project_root(kb_path_rel) if kb_path_rel else None
                    if not kb_path_rel or not (kb_readme_abs and kb_readme_abs.exists()):
                        summary_stats["kb_item_path_issues"] += 1
                
                if tweet_id in self._processed_tweets:
                    logging.warning(f"Tweet {tweet_id} was in processed list but failed comprehensive validation. Moving to unprocessed.")
                    del self._processed_tweets[tweet_id]
                    self.validation_fixes += 1
                
                if tweet_id not in self._unprocessed_tweets:
                    self._unprocessed_tweets.append(tweet_id)
                    logging.debug(f"Ensured tweet {tweet_id} (failed comprehensive validation) is in unprocessed list.")
                tweets_to_process.add(tweet_id)

        for tweet_id in self._tweet_cache:
            if tweet_id not in self._processed_tweets and tweet_id not in self._unprocessed_tweets:
                logging.info(f"Tweet {tweet_id} from cache wasn't assigned to processed/unprocessed by prior stages. Adding to unprocessed as default.")
                self._unprocessed_tweets.append(tweet_id)
                tweets_to_process.add(tweet_id)

        processed_in_unprocessed = set(self._processed_tweets.keys()).intersection(set(self._unprocessed_tweets))
        if processed_in_unprocessed:
            logging.warning(f"Found {len(processed_in_unprocessed)} tweets in both processed and unprocessed lists. Removing from processed: {processed_in_unprocessed}")
            for tweet_id_conflict in processed_in_unprocessed:
                if tweet_id_conflict in self._processed_tweets:
                    del self._processed_tweets[tweet_id_conflict]

        logging.info("Reconciling knowledge base with tweet cache...")
        valid_kb_paths_rel_project = set() # Store paths relative to project root
        tweet_to_path_rel_project = {}
        duplicates = {}
        for tweet_id, tweet_data in self._tweet_cache.items():
            if tweet_data.get('kb_item_created', False):
                kb_path_rel_project_str = tweet_data.get('kb_item_path', '') # Path to README.md relative to project_root
                if kb_path_rel_project_str:
                    kb_readme_abs_path = self.config.resolve_path_from_project_root(kb_path_rel_project_str)
                    # For this check, we need the directory containing README.md
                    kb_item_dir_abs_path = kb_readme_abs_path.parent
                    if kb_item_dir_abs_path.exists() and kb_readme_abs_path.exists(): # Check dir and README
                        # We store the KB *item directory path* (relative to project root) for valid_kb_paths set for orphan check
                        kb_item_dir_rel_project_str = str(self.config.get_relative_path(kb_item_dir_abs_path))
                        valid_kb_paths_rel_project.add(kb_item_dir_rel_project_str)
                        if tweet_id in tweet_to_path_rel_project:
                            duplicates[tweet_id] = [tweet_to_path_rel_project[tweet_id], kb_item_dir_rel_project_str]
                        else:
                            tweet_to_path_rel_project[tweet_id] = kb_item_dir_rel_project_str
                    else:
                        logging.debug(f"Tweet {tweet_id} kb_item_created but path invalid/missing: {kb_path_rel_project_str} (resolved to {kb_readme_abs_path})")
                        tweet_data['kb_item_created'] = False
                        # tweet_data['kb_item_path'] = '' # Don't clear yet, might be useful for debugging
                        await self.update_tweet_data(tweet_id, tweet_data) # Persist kb_item_created = False
                else:
                    logging.debug(f"Tweet {tweet_id} kb_item_created but kb_item_path is empty.")
                    tweet_data['kb_item_created'] = False
                    await self.update_tweet_data(tweet_id, tweet_data)

        logging.info(f"Found {len(valid_kb_paths_rel_project)} valid KB item directories (relative to project root) in tweet_cache.json")
        if duplicates:
            logging.info(f"Found {len(duplicates)} tweets with duplicate KB item directory paths (relative to project root)")

        # kb_dir is absolute path to knowledge_base_dir (e.g., /path/to/project/kb-generated)
        kb_dir_abs = self.config.knowledge_base_dir 
        all_kb_item_dirs_rel_project = set()
        for readme_abs_path in kb_dir_abs.rglob("README.md"):
            kb_item_dir_abs = readme_abs_path.parent
            # Exclude the root kb_dir itself if it accidentally has a README.md
            if kb_item_dir_abs != kb_dir_abs:
                all_kb_item_dirs_rel_project.add(str(self.config.get_relative_path(kb_item_dir_abs)))

        logging.info(f"Found {len(all_kb_item_dirs_rel_project)} KB item directories (relative to project root) by scanning {kb_dir_abs}")
        orphans_rel_project = all_kb_item_dirs_rel_project - valid_kb_paths_rel_project

        quarantine_dir_abs = kb_dir_abs / "quarantine"
        quarantine_dir_abs.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")

        for tweet_id, paths_rel_project in duplicates.items():
            # paths_rel_project is a list of duplicate dir paths relative to project root
            # tweet_to_path_rel_project[tweet_id] is the one we decided to keep (the first one encountered)
            path_to_move_rel = [p for p in paths_rel_project if p != tweet_to_path_rel_project[tweet_id]][0]
            path_to_move_abs = self.config.resolve_path_from_project_root(path_to_move_rel)
            quarantine_path_abs = quarantine_dir_abs / f"duplicate_{tweet_id}_{Path(path_to_move_rel).name}_{timestamp}"
            logging.debug(f"Moving duplicate KB item for tweet {tweet_id} from {path_to_move_abs} to quarantine {quarantine_path_abs}")
            try:
                if path_to_move_abs.exists(): shutil.move(str(path_to_move_abs), str(quarantine_path_abs))
            except Exception as e:
                logging.error(f"Failed to move duplicate KB item {path_to_move_abs} to quarantine: {e}")

        for orphan_path_rel_project in orphans_rel_project:
            orphan_path_abs = self.config.resolve_path_from_project_root(orphan_path_rel_project)
            quarantine_path_abs = quarantine_dir_abs / f"orphan_{Path(orphan_path_rel_project).name}_{timestamp}"
            logging.debug(f"Moving orphaned KB item from {orphan_path_abs} to quarantine {quarantine_path_abs}")
            try:
                if orphan_path_abs.exists(): shutil.move(str(orphan_path_abs), str(quarantine_path_abs))
            except Exception as e:
                logging.error(f"Failed to move orphaned KB item {orphan_path_abs} to quarantine: {e}")

        logging.info(f"Moved {len(orphans_rel_project)} orphaned KB items and handled {len(duplicates)} duplicates to quarantine")
        
        # Save state files if changes were made during reconciliation
        if (len(self._unprocessed_tweets) != initial_unprocessed_count_recon or 
            len(self._processed_tweets) != initial_processed_count_recon or 
            tweets_to_process or tweets_to_mark_processed or duplicates or orphans_rel_project or self.validation_fixes > 0):
            await self._atomic_write_json(list(set(self._unprocessed_tweets)), self.unprocessed_tweets_file)
            await self._atomic_write_json(self._processed_tweets, self.processed_tweets_file)
            # tweet_cache might have been modified by _validate_tweet_state_comprehensive or validate_kb_items
            await self._atomic_write_json(self._tweet_cache, self.tweet_cache_file) 
            logging.info(f"Reconciliation results: {len(tweets_to_mark_processed)} marked/confirmed processed, {len(tweets_to_process)} marked/confirmed unprocessed. State files saved.")

        await self.cleanup_unprocessed_tweets()

        try:
            await self.sync_knowledge_base_to_db()
        except Exception as e:
            logging.error(f"Failed to synchronize KB items to database during initialization: {e}")

        self._initialized = True
        logging.info(f"StateManager initialization complete. Validation fixes: {self.validation_fixes}. Final state: {len(self._unprocessed_tweets)} unprocessed, {len(self._processed_tweets)} processed.")

        # Log summary statistics
        logging.info("--- Tweet Data Validation Summary (on startup) ---")
        logging.info(f"Total tweets validated: {summary_stats['total_tweets_validated']}")
        logging.info(f"  Fully valid & complete: {summary_stats['fully_valid_and_complete']}")
        logging.info(f"  Tweets needing cache completion (media download/verify): {summary_stats['needs_cache_completion']}")
        logging.info(f"  Tweets needing media processing (e.g., alt text generation): {summary_stats['needs_media_processing']}")
        logging.info(f"  Tweets needing categorization (general): {summary_stats['needs_categorization']}")
        if summary_stats['marked_for_recategorization'] > 0: # Only show if relevant
            logging.info(f"    Specifically marked for re-categorization: {summary_stats['marked_for_recategorization']}")
        logging.info(f"  Tweets needing KB item creation: {summary_stats['needs_kb_item_creation']}")
        logging.info(f"  Tweets with KB item path issues (e.g. README missing): {summary_stats['kb_item_path_issues']}")
        logging.info("--------------------------------------------------")

        await self.save_unprocessed()
        await self._atomic_write_json(self._processed_tweets, self.processed_tweets_file)

    async def _atomic_write_json(self, data: Any, filepath: Path) -> None:
        """
        Write JSON data atomically using a temporary file to prevent corruption.
        Filepath is absolute.
        """
        temp_file = None
        try:
            # filepath.parent should already exist due to Config path resolution
            temp_fd, temp_path_str = tempfile.mkstemp(dir=filepath.parent, text=True) # text=True for string ops
            os.close(temp_fd) # Close file descriptor from mkstemp
            temp_file = Path(temp_path_str)
            async with aiofiles.open(temp_file, 'w', encoding='utf-8') as f:
                await f.write(json.dumps(data, indent=2))
            shutil.move(str(temp_file), str(filepath)) # Use shutil.move for atomicity if possible
            logging.debug(f"Updated state file: {filepath}")
        except Exception as e:
            if temp_file and temp_file.exists():
                try:
                    temp_file.unlink() 
                except OSError: pass
            logging.error(f"Failed to write state file {filepath}: {e}")
            raise StateError(f"Failed to write state file: {filepath}") from e

    async def mark_tweet_processed(self, tweet_id: str, tweet_data: Dict[str, Any] = None) -> None:
        """
        Mark a tweet as processed and remove it from the unprocessed list.
        Assumes tweet_data paths (like kb_item_path) are relative to project_root if provided.
        """
        async with self._lock:
            try:
                if not tweet_data:
                    logging.warning(f"No tweet data provided for {tweet_id} to validate before marking processed, skipping mark as processed")
                    # Or, fetch from cache if not provided?
                    # For now, require it to ensure validation against the data that led to this call.
                    return
                
                if tweet_id in self._processed_tweets:
                    logging.debug(f"Tweet {tweet_id} already marked as processed, skipping")
                    return
                
                # Validate based on tweet_data. kb_item_path in tweet_data is relative to project_root.
                kb_item_path_rel = tweet_data.get('kb_item_path')
                kb_item_abs_path = self.config.resolve_path_from_project_root(kb_item_path_rel) if kb_item_path_rel else None

                required_checks = [
                    # media_processed check can be complex if media files are relative in tweet_data
                    # Assuming media_processed flag is set correctly by cacher/processor
                    tweet_data.get('media_processed', not bool(tweet_data.get('media', []) or tweet_data.get('all_downloaded_media_for_thread',[]))),
                    tweet_data.get('categories_processed', False),
                    tweet_data.get('kb_item_created', False),
                    kb_item_path_rel is not None and (kb_item_abs_path.exists() if kb_item_abs_path else False)
                ]
                
                if not all(required_checks):
                    missing_steps = [
                        "media_processed" if not required_checks[0] else "",
                        "categories_processed" if not required_checks[1] else "",
                        "kb_item_created" if not required_checks[2] else "",
                        "kb_item_path_valid" if not required_checks[3] else ""
                    ]
                    logging.warning(f"Tweet {tweet_id} not fully processed or valid for marking. Missing/Invalid steps: {', '.join(filter(None, missing_steps))}. KB Path checked: {kb_item_abs_path}")
                    return

                self._processed_tweets[tweet_id] = datetime.now(timezone.utc).isoformat()
                if tweet_id in self._unprocessed_tweets:
                    self._unprocessed_tweets.remove(tweet_id)
                    logging.debug(f"Removed tweet {tweet_id} from unprocessed list")
                else:
                    logging.debug(f"Tweet {tweet_id} not in unprocessed list (or already removed)")

                await self._atomic_write_json(list(self._unprocessed_tweets), self.unprocessed_tweets_file)
                await self._atomic_write_json(self._processed_tweets, self.processed_tweets_file)
                logging.info(f"Marked tweet {tweet_id} as fully processed; unprocessed remaining: {len(self._unprocessed_tweets)}")

            except Exception as e:
                logging.error(f"Failed to mark tweet {tweet_id} as processed: {e}")
                if tweet_id not in self._unprocessed_tweets: # Ensure it goes back if error during marking
                    self._unprocessed_tweets.append(tweet_id)
                # Consider if _processed_tweets should be rolled back for this ID if error occurs after adding.
                if tweet_id in self._processed_tweets: del self._processed_tweets[tweet_id]
                raise StateError(f"Failed to update processing state for {tweet_id}: {e}")

    async def get_unprocessed_tweets(self) -> List[str]:
        """Get the list of unprocessed tweet IDs, ensuring the state is initialized."""
        if not self._initialized: await self.initialize()
        logging.debug(f"Returning {len(self._unprocessed_tweets)} unprocessed tweet IDs")
        return list(self._unprocessed_tweets)

    async def clear_state(self) -> None:
        """Clear all state data (processed, unprocessed). Tweet cache is NOT cleared here."""
        async with self._lock:
            self._processed_tweets.clear()
            self._unprocessed_tweets.clear()
            await self._atomic_write_json({}, self.processed_tweets_file)
            await self._atomic_write_json([], self.unprocessed_tweets_file)
            # Note: Tweet cache is not cleared by this method. 
            # User explicitly mentioned clearing tweet_cache.json separately.
            logging.info("Cleared processed and unprocessed tweet state files.")

    async def update_from_bookmarks(self) -> None:
        """Update unprocessed list from bookmarks. Bookmarks file path is absolute from config."""
        try:
            tweet_urls = load_tweet_urls_from_links(self.config.bookmarks_file)
            tweet_ids = [parse_tweet_id_from_url(url) for url in tweet_urls]
            valid_ids = [tid for tid in tweet_ids if tid]
            
            newly_added_count = 0
            async with self._lock:
                # Add to self._unprocessed_tweets only if not already processed and not already in unprocessed
                current_unprocessed_set = set(self._unprocessed_tweets)
                for tid in valid_ids:
                    if tid not in self._processed_tweets and tid not in current_unprocessed_set:
                        self._unprocessed_tweets.append(tid)
                        current_unprocessed_set.add(tid)
                        newly_added_count += 1
                        logging.debug(f"Added tweet {tid} from bookmarks to unprocessed list.")
                
                if newly_added_count > 0:
                    await self.save_unprocessed() # Save if changes were made
                    logging.info(f"Added {newly_added_count} new tweets to process from bookmarks: {self.config.bookmarks_file}")
                else:
                    logging.info(f"No new tweets from bookmarks {self.config.bookmarks_file} to add.")
        except Exception as e:
            logging.error(f"Failed to update from bookmarks: {e}")
            raise StateManagerError(f"Failed to update from bookmarks: {e}")

    async def save_unprocessed(self) -> None:
        """Save the list of unprocessed tweets to file (absolute path from config)."""
        try:
            await self._atomic_write_json(list(self._unprocessed_tweets), self.unprocessed_tweets_file)
            logging.debug(f"Saved {len(self._unprocessed_tweets)} unprocessed tweets to {self.unprocessed_tweets_file}")
        except Exception as e:
            logging.error(f"Failed to save unprocessed tweets: {e}")
            raise StateManagerError(f"Failed to save unprocessed state: {e}")

    async def get_processing_state(self, tweet_id: str) -> Dict[str, bool]:
        """Get processing state for a tweet. Assumes tweet_data paths are relative."""
        try:
            tweet_data = await self.get_tweet(tweet_id) # Fetches from self._tweet_cache
            if not tweet_data:
                logging.debug(f"No processing state found for tweet {tweet_id} (not in cache)")
                return { 'fully_processed': tweet_id in self._processed_tweets } # Basic check if not in cache
            
            kb_item_path_rel = tweet_data.get('kb_item_path')
            kb_item_exists = False
            if kb_item_path_rel:
                kb_item_abs_path = self.config.resolve_path_from_project_root(kb_item_path_rel)
                kb_item_exists = kb_item_abs_path.exists()

            state = {
                'media_processed': tweet_data.get('media_processed', False),
                'categories_processed': tweet_data.get('categories_processed', False),
                'kb_item_created': tweet_data.get('kb_item_created', False) and kb_item_exists, # Check existence too
                'fully_processed': tweet_id in self._processed_tweets
            }
            logging.debug(f"Processing state for tweet {tweet_id}: {state}")
            return state
        except Exception as e:
            logging.error(f"Failed to get processing state for tweet {tweet_id}: {e}")
            raise StateError(f"Failed to get processing state for {tweet_id}: {e}")

    async def get_tweet(self, tweet_id: str) -> Optional[Dict[str, Any]]:
        """Get tweet data from cache. Paths within are relative to project_root."""
        try:
            tweet_data = self._tweet_cache.get(tweet_id)
            # logging.debug(f"Retrieved tweet {tweet_id} from cache: {'found' if tweet_data else 'not found'}")
            return tweet_data
        except Exception as e:
            logging.error(f"Failed to get tweet {tweet_id} from cache: {e}")
            return None

    async def update_tweet_data(self, tweet_id: str, tweet_data: Dict[str, Any]) -> None:
        """Update tweet data in cache. Paths in tweet_data should be relative to project_root."""
        # Ensure all paths in tweet_data being saved are relative if they are path-like fields
        # This is implicitly handled by callers ensuring they store relative paths.
        if tweet_id in self._tweet_cache:
            self._tweet_cache[tweet_id].update(tweet_data)
        else:
            self._tweet_cache[tweet_id] = tweet_data
        
        try:
            await self._atomic_write_json(self._tweet_cache, self.tweet_cache_file)
            logging.debug(f"Updated tweet data for {tweet_id} in cache file: {self.tweet_cache_file}")
        except Exception as e:
            logging.error(f"Failed to save updated tweet cache: {e}")
            raise StateError(f"Cache update failed: {e}")

    async def get_all_tweets(self) -> Dict[str, Dict[str, Any]]:
        """Get all cached tweet data. Paths within are relative to project_root."""
        logging.debug(f"Returning all {len(self._tweet_cache)} cached tweets")
        return self._tweet_cache.copy()

    async def save_tweet_cache(self, tweet_id: str, data: Dict[str, Any]) -> None:
        """Save tweet data to cache. Paths in data should be relative to project_root."""
        # Callers are responsible for ensuring data paths are relative.
        self._tweet_cache[tweet_id] = data
        try:
            await self._atomic_write_json(self._tweet_cache, self.tweet_cache_file)
            logging.debug(f"Saved tweet {tweet_id} to cache file: {self.tweet_cache_file}")
        except Exception as e:
            logging.error(f"Failed to save tweet cache for {tweet_id}: {e}")
            raise StateError(f"Cache save failed: {e}")

    async def get_tweet_cache(self, tweet_id: str) -> Optional[Dict[str, Any]]:
        """Get cached tweet data. Paths within are relative to project_root."""
        return await self.get_tweet(tweet_id)

    async def verify_cache_status(self) -> List[str]:
        """Verify cache status. Unprocessed tweets are checked if their cache data (with relative paths) is complete."""
        tweets_needing_cache = []
        for tweet_id in self._unprocessed_tweets:
            cached_data = self._tweet_cache.get(tweet_id)
            if not cached_data or not cached_data.get('cache_complete', False):
                # Further checks could be added here if needed, e.g., if media files (relative paths)
                # actually resolve and exist, but cache_complete is the primary flag from cacher.
                tweets_needing_cache.append(tweet_id)
                logging.debug(f"Tweet {tweet_id} needs cache update (cache_complete is false or no data).")
        logging.info(f"Verified cache status: {len(tweets_needing_cache)} tweets need caching based on 'cache_complete' flag.")
        return tweets_needing_cache

    async def update_media_analysis(self, tweet_id: str, media_analysis: Dict[str, Any]) -> None:
        if tweet_id not in self._tweet_cache: raise StateError(f"Tweet {tweet_id} not found in cache for media analysis update")
        self._tweet_cache[tweet_id].update({'media_analysis': media_analysis, 'media_analysis_complete': True})
        await self._atomic_write_json(self._tweet_cache, self.tweet_cache_file)
        logging.debug(f"Updated media analysis for tweet {tweet_id}")

    async def update_categories(self, tweet_id: str, category_data: Dict[str, Any]) -> None:
        if tweet_id not in self._tweet_cache: raise StateError(f"Tweet {tweet_id} not found in cache for category update")
        self._tweet_cache[tweet_id].update({
            'main_category': category_data.get('main_category'), # Store directly in tweet_data
            'sub_category': category_data.get('sub_category'),
            'item_name_suggestion': category_data.get('item_name_suggestion'), # Use 'item_name_suggestion' consistent with ContentProcessor
            # 'categories' dict can still be used if detailed LLM output is stored there
            'categories': { 
                'main_category': category_data.get('main_category'),
                'sub_category': category_data.get('sub_category'),
                'item_name': category_data.get('item_name_suggestion')
            },
            'categories_processed': True
        })
        await self._atomic_write_json(self._tweet_cache, self.tweet_cache_file)
        logging.debug(f"Updated categories for tweet {tweet_id}")

    async def mark_kb_item_created(self, tweet_id: str, kb_item_path_rel_project: str) -> None:
        """kb_item_path_rel_project is path to README.md relative to project_root."""
        if tweet_id not in self._tweet_cache: raise StateError(f"Tweet {tweet_id} not found in cache for KB item creation")
        self._tweet_cache[tweet_id].update({'kb_item_path': kb_item_path_rel_project, 'kb_item_created': True})
        await self._atomic_write_json(self._tweet_cache, self.tweet_cache_file)
        logging.debug(f"Marked KB item created for tweet {tweet_id} at {kb_item_path_rel_project} (relative to project root)")
        # DB sync is handled by sync_knowledge_base_to_db or by ContentProcessor after this call.

    async def mark_media_processed(self, tweet_id: str) -> None:
        tweet_data = await self.get_tweet(tweet_id)
        if tweet_data: 
            tweet_data['media_processed'] = True
            await self.update_tweet_data(tweet_id, tweet_data)
            logging.debug(f"Marked media as processed for tweet {tweet_id}")
        else: logging.warning(f"Tweet {tweet_id} not found to mark media processed.")

    async def mark_categories_processed(self, tweet_id: str) -> None:
        tweet_data = await self.get_tweet(tweet_id)
        if tweet_data: 
            tweet_data['categories_processed'] = True
            await self.update_tweet_data(tweet_id, tweet_data)
            logging.debug(f"Marked categories as processed for tweet {tweet_id}")
        else: logging.warning(f"Tweet {tweet_id} not found to mark categories processed.")

    async def initialize_tweet_cache(self, tweet_id: str, tweet_data: Dict[str, Any]) -> None:
        """Initialize new tweet in cache. Paths in tweet_data should be relative if applicable."""
        if tweet_id in self._tweet_cache: logging.debug(f"Tweet {tweet_id} already in cache, updating with: {tweet_data}")
        else: logging.debug(f"Initializing cache for new tweet {tweet_id} with: {tweet_data}")
        
        # Make sure we use sensible defaults especially for category-related fields
        base_data = {
            'tweet_id': tweet_id,
            'bookmarked_tweet_id': tweet_data.get('bookmarked_tweet_id', tweet_id),
            'is_thread': tweet_data.get('is_thread', False),
            'thread_tweets': tweet_data.get('thread_tweets', []),
            'all_downloaded_media_for_thread': tweet_data.get('all_downloaded_media_for_thread', []), # Paths relative to project_root
            'urls_expanded': tweet_data.get('urls_expanded', False),
            'media_processed': tweet_data.get('media_processed', False),
            'cache_complete': tweet_data.get('cache_complete', False),
            'main_category': '', # Explicitly set empty to avoid propagating wrong values
            'sub_category': '', # Explicitly set empty to avoid propagating wrong values
            'item_name_suggestion': '', # Explicitly set empty to avoid propagating wrong values
            'categories': {}, # Empty dict instead of potentially copying from another tweet
            'categories_processed': False, # Explicitly set to False for new tweets
            'kb_item_path': '', # Empty path until properly created
            'kb_media_paths': '[]', # JSON string of paths relative to kb-generated
            'kb_item_created': False, # Explicitly set to False for new tweets
            'recategorization_attempts': 0, # Reset attempts count
            'raw_json_content': None,
            'display_title': None,
            'source': tweet_data.get('source', 'unknown') # e.g., 'bookmark_init', 'playwright_fetch'
        }

        # Only propagate category information from tweet_data if it's explicitly set
        # with values specific to this tweet
        if 'main_category' in tweet_data and tweet_data['main_category']:
            base_data['main_category'] = tweet_data['main_category']
        if 'sub_category' in tweet_data and tweet_data['sub_category']:
            base_data['sub_category'] = tweet_data['sub_category']
        if 'item_name_suggestion' in tweet_data and tweet_data['item_name_suggestion']:
            base_data['item_name_suggestion'] = tweet_data['item_name_suggestion']

        # Only use categories dict if it's actually populated properly
        if 'categories' in tweet_data and isinstance(tweet_data['categories'], dict) and tweet_data['categories']:
            if set(tweet_data['categories'].keys()) & {'main_category', 'sub_category', 'item_name'}:
                base_data['categories'] = tweet_data['categories']
                # If we're using their categories dict, also use their categorization flag
                if 'categories_processed' in tweet_data:
                    base_data['categories_processed'] = tweet_data['categories_processed']
        
        # Only accept kb_item created and path if they specifically belong to this tweet
        # This will be validated by state manager validation functions later
        if ('kb_item_created' in tweet_data and tweet_data['kb_item_created'] and
            'kb_item_path' in tweet_data and tweet_data['kb_item_path']):
            base_data['kb_item_created'] = tweet_data['kb_item_created']
            base_data['kb_item_path'] = tweet_data['kb_item_path']
            
        # If existing data in cache, update it, otherwise set base_data
        # This ensures that we don't overwrite existing correct data with defaults
        if tweet_id in self._tweet_cache:
            existing_data = self._tweet_cache[tweet_id].copy()
            
            # Special handling for categories to prevent corruption
            # Only accept existing categories if they appear to be properly set
            if ('categories' in existing_data and 
                'categories_processed' in existing_data and 
                existing_data['categories_processed'] is True and
                isinstance(existing_data['categories'], dict) and
                all(key in existing_data['categories'] for key in ['main_category', 'sub_category', 'item_name'])):
                # Keep existing categories if they seem valid
                base_data['categories'] = existing_data['categories']
                base_data['main_category'] = existing_data['main_category']
                base_data['sub_category'] = existing_data['sub_category']
                base_data['item_name_suggestion'] = existing_data['item_name_suggestion']
                base_data['categories_processed'] = existing_data['categories_processed']
            
            # Now update with base_data which includes carefully selected fields from tweet_data
            self._tweet_cache[tweet_id].update(base_data)
        else:
            # No existing data, so use our carefully constructed base_data
            self._tweet_cache[tweet_id] = base_data

        await self.update_tweet_data(tweet_id, self._tweet_cache[tweet_id])
        logging.debug(f"Initialized/Updated cache for tweet {tweet_id}")

    async def mark_tweet_unprocessed(self, tweet_id: str) -> None:
        """Move a processed tweet back to unprocessed state."""
        async with self._lock:
            if tweet_id in self._processed_tweets:
                if tweet_id not in self._unprocessed_tweets:
                    self._unprocessed_tweets.append(tweet_id)
                del self._processed_tweets[tweet_id]
                await self.save_unprocessed() # Save unprocessed list
                await self._atomic_write_json(self._processed_tweets, self.processed_tweets_file) # Save processed list
                logging.debug(f"Marked tweet {tweet_id} as unprocessed and saved state.")
            else:
                logging.debug(f"Tweet {tweet_id} not found in processed list to mark as unprocessed.")

    async def _validate_tweet_state_comprehensive(self, tweet_id: str, tweet_data: Dict[str, Any]) -> bool:
        """
        Comprehensively validate tweet state. Uses self.config for path resolution.
        Paths in tweet_data (media, kb_item_path) are relative to project_root.
        """
        all_valid = True 
        updates_needed = {} # This will store changes identified within this validation run
        max_recategorization_attempts = 3
        default_category_tuples = [("Uncategorized", "General"), ("Uncategorized", "Default"), ("software_engineering", "best_practices")]
        
        if 'recategorization_attempts' not in tweet_data:
            updates_needed['recategorization_attempts'] = 0
            tweet_data['recategorization_attempts'] = 0  

        cache_complete = tweet_data.get('cache_complete', False)
        # all_downloaded_media_for_thread contains paths relative to project_root
        media_list_rel = tweet_data.get('all_downloaded_media_for_thread', []) 
        has_media = bool(media_list_rel)
        media_files_exist = True

        if has_media:
            for media_path_rel_str in media_list_rel:
                media_path_abs = self.config.resolve_path_from_project_root(media_path_rel_str)
                if not media_path_abs.exists():
                    logging.warning(f"Tweet {tweet_id} cache references missing media file: {media_path_rel_str} (resolved to {media_path_abs})")
                    media_files_exist = False
                    break 

        if not media_files_exist:
            cache_complete = False
            updates_needed['cache_complete'] = False
            if tweet_data.get('media_processed', False): updates_needed['media_processed'] = False
            all_valid = False
        elif not cache_complete: # Media files might exist, but cache wasn't marked complete.
             all_valid = False
        
        media_processed = tweet_data.get('media_processed', False)
        # Assuming 'media_item_details' in each segment of 'thread_tweets' contains alt_text if processed.
        # This check is simplified; a more thorough check would iterate thread_tweets if structured that way.
        # For now, rely on 'media_processed' flag more directly or existence of 'image_descriptions' if that field is used.
        has_image_descriptions = bool(tweet_data.get('image_descriptions') and any(tweet_data.get('image_descriptions')))
        # Determine if there are images that would need descriptions
        # This is a simplified check based on typical media types in all_downloaded_media_for_thread
        has_images_needing_desc = False
        if has_media:
            for media_path_rel_str in media_list_rel:
                if Path(media_path_rel_str).suffix.lower() in ['.jpg', '.jpeg', '.png', '.webp']:
                    has_images_needing_desc = True
                    break
        
        if has_media:
            if media_files_exist and (not has_images_needing_desc or has_image_descriptions) and not media_processed:
                 updates_needed['media_processed'] = True
                 media_processed = True 
            elif media_files_exist and has_images_needing_desc and not has_image_descriptions:
                 if media_processed: updates_needed['media_processed'] = False
                 all_valid = False 
            elif not media_files_exist and media_processed:
                 updates_needed['media_processed'] = False
                 all_valid = False 
        elif not media_processed: # No media
            updates_needed['media_processed'] = True
            media_processed = True 

        categories_processed = tweet_data.get('categories_processed', False)
        # Use top-level main_category, sub_category, item_name_suggestion for validation
        main_cat = tweet_data.get('main_category')
        sub_cat = tweet_data.get('sub_category')
        item_name = tweet_data.get('item_name_suggestion')
        recategorization_attempts = tweet_data.get('recategorization_attempts', 0)

        if not categories_processed:
            all_valid = False
        else:
            if not (main_cat and sub_cat and item_name):
                logging.warning(f"Tweet {tweet_id} categories_processed but missing main fields: main='{main_cat}', sub='{sub_cat}', name='{item_name}'")
                updates_needed['categories_processed'] = False
                all_valid = False
            else:
                is_default_pair = (main_cat, sub_cat) in default_category_tuples
                is_generic_item_name = item_name.startswith(f'Tweet-{tweet_id}') or item_name.lower() == 'tweet' or len(item_name) < 5
                
                # Check if all tweets have identical categories, which suggests copying
                if 'categories' in tweet_data:
                    # Check if categories in tweet_data match fields in top level
                    cat_dict = tweet_data['categories']
                    if not (cat_dict.get('main_category') == main_cat and 
                           cat_dict.get('sub_category') == sub_cat and 
                           cat_dict.get('item_name') == item_name):
                        logging.warning(f"Tweet {tweet_id} has inconsistent categories between top-level fields and 'categories' dict")
                        updates_needed['categories_processed'] = False
                        all_valid = False
                
                # Check for the common error condition where all items are categorized the same
                api_design_count = sum(1 for tid, tdata in self._tweet_cache.items() 
                                  if tdata.get('main_category') == 'software_engineering' and 
                                     tdata.get('sub_category') == 'api_design' and
                                     tdata.get('item_name_suggestion') == 'restful_api_best_practices')
                
                # If there are more than 10 items with identical "api_design" categories, likely a bug
                if (main_cat == 'software_engineering' and 
                    sub_cat == 'api_design' and 
                    item_name == 'restful_api_best_practices' and
                    api_design_count > 10):
                    logging.warning(f"Tweet {tweet_id} has suspicious common 'api_design' categorization (found {api_design_count} instances)")
                    updates_needed['categories_processed'] = False
                    updates_needed['main_category'] = ''
                    updates_needed['sub_category'] = ''
                    updates_needed['item_name_suggestion'] = ''
                    updates_needed['categories'] = {}
                    all_valid = False

                if is_default_pair and is_generic_item_name and recategorization_attempts < max_recategorization_attempts:
                    logging.info(f"Tweet {tweet_id} has default/generic category/name ({main_cat}/{sub_cat}/{item_name}), marking for re-categorization (attempt {recategorization_attempts + 1})")
                    updates_needed['categories_processed'] = False
                    updates_needed['main_category'] = '' # Clear potentially bad categories
                    updates_needed['sub_category'] = ''
                    updates_needed['item_name_suggestion'] = ''
                    updates_needed['recategorization_attempts'] = recategorization_attempts + 1
                    all_valid = False
                elif is_default_pair and is_generic_item_name and recategorization_attempts >= max_recategorization_attempts:
                    logging.warning(f"Tweet {tweet_id} reached max re-categorization attempts with generic category/name.")
        
        kb_item_created = tweet_data.get('kb_item_created', False)
        kb_path_rel_project_str = tweet_data.get('kb_item_path', '') # Path to README.md relative to project_root

        if not kb_item_created:
            found_readme_rel_path = await self._find_and_update_kb_item_path(tweet_id, tweet_data)
            if found_readme_rel_path:
                updates_needed['kb_item_path'] = found_readme_rel_path
                updates_needed['kb_item_created'] = True
                kb_item_created = True 
                kb_path_rel_project_str = found_readme_rel_path 
                logging.info(f"Found existing KB item for tweet {tweet_id} at {found_readme_rel_path} (rel to project), marking created.")
            else:
                all_valid = False  

        if kb_item_created:
            if not kb_path_rel_project_str:
                logging.warning(f"Tweet {tweet_id} kb_item_created but kb_item_path is empty")
                updates_needed['kb_item_created'] = False
                all_valid = False
            else:
                readme_abs_path = self.config.resolve_path_from_project_root(kb_path_rel_project_str)
                if not readme_abs_path.exists():
                    logging.warning(f"Tweet {tweet_id} KB item README (rel path {kb_path_rel_project_str}) not found at resolved {readme_abs_path}")
                    updates_needed['kb_item_created'] = False
                    updates_needed['kb_item_path'] = ''  
                    all_valid = False
        
        if updates_needed:
            # Make a deepcopy of the original tweet_data if we are modifying it directly,
            # or fetch from cache and update if tweet_data is a copy.
            # Current logic: tweet_data is a reference to an item in self._tweet_cache, 
            # or a copy if called from elsewhere. For initialize(), it's a copy.
            # Let's assume self._tweet_cache is the source of truth and apply updates there.
            
            # Fetch the most current version from the cache to avoid overwriting concurrent changes (if any)
            # and to ensure we're applying updates_needed to the correct base.
            current_data_in_cache = self._tweet_cache.get(tweet_id, {})
            data_to_update = copy.deepcopy(current_data_in_cache) # Work on a copy
            data_to_update.update(updates_needed) # Apply changes found in this validation

            # data_to_update['_validation_updates_applied'] = updates_needed # Optional: for debugging what was changed by *this* call

            self._tweet_cache[tweet_id] = data_to_update # Put the modified copy back
            
            await self._atomic_write_json(self._tweet_cache, self.tweet_cache_file)
            logging.debug(f"Updated tweet {tweet_id} state due to validation: {updates_needed}")
            self.validation_fixes += 1

        # Re-fetch final_data from cache as it might have been updated by 'updates_needed'
        final_data = self._tweet_cache.get(tweet_id, {}) 
        final_media_processed = final_data.get('media_processed', False)
        final_kb_path_rel = final_data.get('kb_item_path', '')
        final_kb_readme_abs = self.config.resolve_path_from_project_root(final_kb_path_rel) if final_kb_path_rel else None

        is_complete_and_valid = (
            final_data.get('cache_complete', False) and
            final_media_processed and 
            final_data.get('categories_processed', False) and
            final_data.get('kb_item_created', False) and
            bool(final_kb_path_rel) and 
            (final_kb_readme_abs.exists() if final_kb_readme_abs else False)
        )

        logging.debug(f"Tweet {tweet_id} final validation result: {'Valid and Complete' if is_complete_and_valid else 'Incomplete or Invalid'} (cache_complete={final_data.get('cache_complete', False)}, media_processed={final_media_processed}, categories_processed={final_data.get('categories_processed', False)}, kb_item_created={final_data.get('kb_item_created', False)}, kb_readme_exists={(final_kb_readme_abs.exists() if final_kb_readme_abs else False)})")
        return is_complete_and_valid

    async def _find_and_update_kb_item_path(self, tweet_id: str, tweet_data: Dict[str, Any]) -> Optional[str]:
        """
        Try to find an existing KB item README for a tweet. 
        Returns path to README.md relative to project_root if found.
        """
        # kb_base_abs is absolute path to knowledge_base_dir (e.g., /path/to/project/kb-generated)
        kb_base_abs = self.config.knowledge_base_dir
        search_dirs_abs = []

        main_cat = tweet_data.get('main_category') or tweet_data.get('categories', {}).get('main_category')
        sub_cat = tweet_data.get('sub_category') or tweet_data.get('categories', {}).get('sub_category')
        item_name = tweet_data.get('item_name_suggestion') or tweet_data.get('categories', {}).get('item_name')
        
        if main_cat and sub_cat and item_name:
            # Path of item dir relative to kb_base_abs
            item_dir_rel_to_kb_base = Path(main_cat) / sub_cat / item_name 
            search_dirs_abs.append(kb_base_abs / item_dir_rel_to_kb_base)
        
        expected_url_base = "twitter.com/"
        status_segment = "/status/"

        for item_dir_abs_path_hint in search_dirs_abs:
            if item_dir_abs_path_hint.is_dir():
                readme_abs_path = item_dir_abs_path_hint / "README.md"
                if readme_abs_path.exists():
                    try:
                        async with aiofiles.open(readme_abs_path, 'r', encoding='utf-8') as f:
                            content_sample = await f.read(2048) 
                            if expected_url_base in content_sample:
                                return str(self.config.get_relative_path(readme_abs_path))
                    except Exception as e:
                        logging.warning(f"Error reading potential README at {readme_abs_path} for tweet {tweet_id}: {e}")
                        continue
        
        # Fallback: Scan all READMEs in kb_base_abs if hints failed
        # This is slower but more thorough if category/name info was bad or changed
        # The debug log below is the one identified by the user. It's fine at DEBUG level.
        logging.debug(f"KB item for {tweet_id} not found via hints, scanning all READMEs in {kb_base_abs}...")
        for readme_abs_path_scan in kb_base_abs.rglob("README.md"):
            try:
                async with aiofiles.open(readme_abs_path_scan, 'r', encoding='utf-8') as f:
                    content_sample = await f.read(2048)
                    if expected_url_base in content_sample:
                        logging.info(f"Found KB item for {tweet_id} via full scan at {readme_abs_path_scan}")
                        return str(self.config.get_relative_path(readme_abs_path_scan))
            except Exception as e:
                 logging.warning(f"Error reading potential README at {readme_abs_path_scan} during full scan for {tweet_id}: {e}")
        return None

    async def validate_kb_items(self) -> None:
        """
        Validate KB items. For tweets missing kb_item_path, try to find their README.md.
        Updates tweet_cache with path to README.md relative to project_root if found.
        """
        logging.info("Validating KB items for all tweets (find missing paths)... ")
        # kb_base_abs is absolute path (e.g., /path/to/project/kb-generated)
        kb_base_abs = self.config.knowledge_base_dir
        
        tweet_id_to_readme_rel_project = {}
        expected_url_base = "twitter.com/"
        status_segment = "/status/"

        for readme_abs_path in kb_base_abs.rglob("README.md"):
            try:
                async with aiofiles.open(readme_abs_path, 'r', encoding='utf-8') as f:
                    content_sample = await f.read(2048) # Read a sample to find the URL
                    # More robust URL parsing to find tweet ID
                    # Example: [https://twitter.com/user/status/1234567890?s=20](https://twitter.com/user/status/1234567890?s=20)
                    # or just https://twitter.com/user/status/1234567890
                    match = re.search(r"twitter\.com/[^/]+/status/(\d+)", content_sample)
                    if match:
                        tweet_id_match = match.group(1)
                        readme_rel_project_path = self.config.get_relative_path(readme_abs_path)
                        tweet_id_to_readme_rel_project[tweet_id_match] = str(readme_rel_project_path)
            except Exception as e:
                logging.warning(f"Error reading README at {readme_abs_path} during validate_kb_items: {e}")
                continue
        
        logging.info(f"Found {len(tweet_id_to_readme_rel_project)} README files with tweet IDs during scan.")
        
        updates = 0
        for tweet_id, tweet_data in list(self._tweet_cache.items()): # Iterate copy in case of modification
            # Check if kb_item_path is missing, empty, or if kb_item_created is false
            kb_path_in_cache_rel = tweet_data.get('kb_item_path')
            kb_created_in_cache = tweet_data.get('kb_item_created', False)
            
            needs_update = False
            if not kb_created_in_cache: # If not marked created, definitely try to find
                needs_update = True
            elif not kb_path_in_cache_rel: # Marked created but path is empty
                needs_update = True
            else: # Marked created and has a path, verify path leads to existing file
                kb_readme_abs = self.config.resolve_path_from_project_root(kb_path_in_cache_rel)
                if not kb_readme_abs.exists():
                    logging.warning(f"Tweet {tweet_id} has kb_item_path {kb_path_in_cache_rel} but {kb_readme_abs} does not exist. Will try to re-find.")
                    needs_update = True
                else:
                    # Verify that README contains this tweet ID and not another one
                    try:
                        async with aiofiles.open(kb_readme_abs, 'r', encoding='utf-8') as f:
                            content_sample = await f.read(2048)
                            match = re.search(r"twitter\.com/[^/]+/status/(\d+)", content_sample)
                            if match:
                                readme_tweet_id = match.group(1)
                                if readme_tweet_id != tweet_id:
                                    logging.warning(f"Tweet {tweet_id} has kb_item_path {kb_path_in_cache_rel} but README links to tweet {readme_tweet_id}. Marking for correction.")
                                    needs_update = True
                                    # Reset the kb_item_created flag and path to allow re-finding correct path
                                    tweet_data['kb_item_created'] = False
                                    tweet_data['kb_item_path'] = ''
                    except Exception as e:
                        logging.warning(f"Error verifying tweet ID in README at {kb_readme_abs}: {e}")
            
            if needs_update and tweet_id in tweet_id_to_readme_rel_project:
                found_readme_rel_path = tweet_id_to_readme_rel_project[tweet_id]
                if tweet_data.get('kb_item_path') != found_readme_rel_path or not tweet_data.get('kb_item_created'):
                    update_payload = {
                        'kb_item_path': found_readme_rel_path, 
                        'kb_item_created': True
                    }
                    # Directly update self._tweet_cache and then write atomically later if many updates
                    if tweet_id not in self._tweet_cache: self._tweet_cache[tweet_id] = {}
                    self._tweet_cache[tweet_id].update(update_payload)
                    logging.info(f"Updated tweet {tweet_id} with found KB item path (rel to project): {found_readme_rel_path}")
                    updates += 1
            elif needs_update and kb_created_in_cache:
                # This tweet was marked as created but we couldn't find its README
                # or the README had a different tweet ID
                tweet_data['kb_item_created'] = False
                tweet_data['kb_item_path'] = ''
                if tweet_id not in self._tweet_cache: self._tweet_cache[tweet_id] = {}
                self._tweet_cache[tweet_id].update({
                    'kb_item_created': False,
                    'kb_item_path': ''
                })
                logging.info(f"Reset kb_item_created flag for tweet {tweet_id} as no matching README was found")
                updates += 1
        
        if updates > 0:
            await self._atomic_write_json(self._tweet_cache, self.tweet_cache_file) # Save updated cache
            logging.info(f"Persisted {updates} tweet cache updates from validate_kb_items.")
        self.validation_fixes += updates

    async def finalize_processing(self) -> None:
        """Perform final validation and move completed tweets to processed list."""
        logging.info("Finalizing processing and validating tweet states...")
        moved_to_processed = 0
        # Iterate over a copy of unprocessed_tweets list as it might be modified
        for tweet_id in list(self._unprocessed_tweets):
            tweet_data = self._tweet_cache.get(tweet_id)
            if not tweet_data:
                logging.warning(f"Tweet {tweet_id} in unprocessed list but not in cache, removing from unprocessed.")
                if tweet_id in self._unprocessed_tweets: self._unprocessed_tweets.remove(tweet_id)
                self.validation_fixes +=1
                continue
            
            # _validate_tweet_state_comprehensive might modify tweet_cache, so get its result
            is_fully_processed = await self._validate_tweet_state_comprehensive(tweet_id, tweet_data)
            if is_fully_processed:
                if tweet_id not in self._processed_tweets: # Ensure not already marked
                    self._processed_tweets[tweet_id] = datetime.now(timezone.utc).isoformat()
                    moved_to_processed += 1
                    logging.info(f"Finalized tweet {tweet_id} and added to processed list.")
                if tweet_id in self._unprocessed_tweets: # Remove from unprocessed if validation passed
                    self._unprocessed_tweets.remove(tweet_id)
            # If not fully_processed, it remains in unprocessed (or was put there by _validate_tweet_state_comprehensive)
        
        if moved_to_processed > 0 or self.validation_fixes > 0: # Save if any changes occurred
            await self._atomic_write_json(list(self._unprocessed_tweets), self.unprocessed_tweets_file)
            await self._atomic_write_json(self._processed_tweets, self.processed_tweets_file)
            # tweet_cache may have been modified by _validate_tweet_state_comprehensive
            await self._atomic_write_json(self._tweet_cache, self.tweet_cache_file)
            logging.info(f"Finalization complete: moved {moved_to_processed} tweets to processed. Total validation fixes during this phase: {self.validation_fixes}")

    async def cleanup_unprocessed_tweets(self) -> None:
        """Clean up unprocessed list: remove if processed, not in cache, or validated as complete."""
        logging.info("Cleaning up unprocessed tweets list...")
        initial_count = len(self._unprocessed_tweets)
        to_remove_from_unprocessed = []
        made_changes = False
        
        for tweet_id in list(self._unprocessed_tweets): # Iterate copy
            if tweet_id in self._processed_tweets:
                to_remove_from_unprocessed.append(tweet_id)
                logging.debug(f"Tweet {tweet_id} is already in processed list, scheduling removal from unprocessed.")
                continue
            
            tweet_data = self._tweet_cache.get(tweet_id)
            if not tweet_data:
                to_remove_from_unprocessed.append(tweet_id)
                logging.debug(f"Tweet {tweet_id} not found in cache, scheduling removal from unprocessed.")
                continue
            
            # Re-validate state comprehensively. If it passes, it should be moved to processed.
            is_fully_processed_and_valid = await self._validate_tweet_state_comprehensive(tweet_id, tweet_data)
            if is_fully_processed_and_valid:
                if tweet_id not in self._processed_tweets: # Ensure not already marked
                    self._processed_tweets[tweet_id] = datetime.now(timezone.utc).isoformat()
                    logging.info(f"Tweet {tweet_id} validated as fully processed during cleanup, adding to processed list.")
                    made_changes = True # Processed list changed
                to_remove_from_unprocessed.append(tweet_id) # Remove from unprocessed if validation passed
        
        if to_remove_from_unprocessed:
            for tweet_id in to_remove_from_unprocessed:
                if tweet_id in self._unprocessed_tweets: self._unprocessed_tweets.remove(tweet_id)
            await self._atomic_write_json(list(self._unprocessed_tweets), self.unprocessed_tweets_file)
            made_changes = True # Unprocessed list changed
        
        if made_changes:
            await self._atomic_write_json(self._processed_tweets, self.processed_tweets_file)
            await self._atomic_write_json(self._tweet_cache, self.tweet_cache_file) # Cache might have been updated by validation
        
        removed_count = initial_count - len(self._unprocessed_tweets)
        logging.info(f"Cleaned up {removed_count} tweets from unprocessed list. Current unprocessed: {len(self._unprocessed_tweets)}")

    async def is_tweet_processed(self, tweet_id: str) -> bool:
        """Check if a tweet is in the processed list."""
        if not self._initialized: await self.initialize()
        return tweet_id in self._processed_tweets

    async def sync_knowledge_base_to_db(self, db_session=None):
        """
        Synchronize KB items from tweet cache to DB.
        Assumes kb_item_path in tweet_cache is path to README.md relative to project_root.
        kb_media_paths in tweet_cache is JSON string of paths relative to kb-generated dir.
        """
        try:
            logging.info("Starting DB sync from tweet cache. Paths are relative to project_root.")
            from flask import current_app
            from knowledge_base_agent.models import db, KnowledgeBaseItem # db is SQLAlchemy instance

            with current_app.app_context():
                # Use provided session or get from app context (db.session)
                actual_db_session = db_session if db_session else db.session
                if not actual_db_session:
                    logging.error("DB session not available for sync_knowledge_base_to_db")
                    raise StateManagerError("Cannot access database session for sync.")

                added_count = 0; updated_count = 0; skipped_count = 0; readme_read_error_count = 0; db_op_error_count = 0
                total_eligible_from_cache = 0
                sync_timestamp = datetime.now(timezone.utc)

                for tweet_id, tweet_data in self._tweet_cache.items():
                    if not (tweet_data and tweet_data.get('kb_item_created', False) and tweet_data.get('kb_item_path')):
                        continue # Skip if not marked as KB created or no path
                    
                    total_eligible_from_cache += 1
                    kb_readme_path_rel_project = tweet_data['kb_item_path'] # Path to README.md relative to project_root
                    kb_readme_abs_path = self.config.resolve_path_from_project_root(kb_readme_path_rel_project)

                    if not kb_readme_abs_path.exists():
                        logging.warning(f"DB Sync: README.md missing for tweet {tweet_id} at {kb_readme_abs_path} (from rel {kb_readme_path_rel_project}). Skipping DB entry.")
                        skipped_count += 1
                        continue

                    content = None
                    try:
                        async with aiofiles.open(kb_readme_abs_path, 'r', encoding='utf-8') as f:
                            content = await f.read()
                    except Exception as e:
                        logging.error(f"DB Sync: Failed to read README.md for tweet {tweet_id} at {kb_readme_abs_path}: {e}")
                        readme_read_error_count += 1; skipped_count += 1
                        continue

                    title = tweet_data.get('item_name_suggestion') or tweet_data.get('categories',{}).get('item_name')
                    if not title:
                         lines = content.splitlines()
                         title = lines[0].strip('# ').strip() if lines else f"Tweet {tweet_id}"
                    
                    lines = content.splitlines()
                    readme_desc_lines = [line.strip() for line in lines[1:4] if line.strip() and not line.startswith('**Source:**') and not line.startswith('**Author:**')]
                    description = " ".join(readme_desc_lines) if readme_desc_lines else tweet_data.get('raw_data',{}).get('text','No description available.')[:250]

                    main_category = tweet_data.get('main_category') or tweet_data.get('categories',{}).get('main_category', 'Uncategorized')
                    sub_category = tweet_data.get('sub_category') or tweet_data.get('categories',{}).get('sub_category', 'General')
                    
                    # file_path stored in DB is the path to README.md relative to project_root
                    file_path_to_store_in_db = kb_readme_path_rel_project 
                    source_url = tweet_data.get('url', f"https://twitter.com/i/web/status/{tweet_id}")
                    kb_media_paths_json = tweet_data.get('kb_media_paths', '[]') # Already JSON string of paths rel to kb-generated

                    try:
                        existing_item = actual_db_session.query(KnowledgeBaseItem).filter_by(tweet_id=tweet_id).first()
                        if existing_item:
                            existing_item.title = title
                            existing_item.description = description
                            # existing_item.content = content # Content field in DB might be large, consider if always updating
                            existing_item.main_category = main_category
                            existing_item.sub_category = sub_category
                            existing_item.file_path = file_path_to_store_in_db
                            existing_item.source_url = source_url
                            existing_item.kb_media_paths = kb_media_paths_json
                            existing_item.last_updated = sync_timestamp
                            updated_count += 1
                        else:
                            new_item = KnowledgeBaseItem(
                                tweet_id=tweet_id, title=title, description=description, content=content, 
                                main_category=main_category, sub_category=sub_category, 
                                file_path=file_path_to_store_in_db, source_url=source_url, 
                                kb_media_paths=kb_media_paths_json,
                                created_at=sync_timestamp, last_updated=sync_timestamp
                            )
                            actual_db_session.add(new_item)
                            added_count += 1
                    except Exception as e:
                        logging.error(f"DB Sync: DB operation (add/update) failed for tweet {tweet_id}: {e}")
                        db_op_error_count += 1; skipped_count += 1
                        continue
                
                if added_count > 0 or updated_count > 0:
                    try:
                        actual_db_session.commit()
                        logging.info(f"DB Sync: Commit successful. Added: {added_count}, Updated: {updated_count}.")
                    except Exception as e:
                        logging.error(f"DB Sync: Failed to commit DB changes: {e}")
                        actual_db_session.rollback()
                        logging.error("DB Sync: Rolled back DB session.")
                        raise StateManagerError(f"DB Sync: Failed to commit KB items to DB: {e}")
                else:
                    logging.info("DB Sync: No new items or updates to commit to DB.")

                logging.info(f"DB Sync Summary: Eligible from cache: {total_eligible_from_cache}, Added: {added_count}, Updated: {updated_count}, Skipped: {skipped_count} (Read Errors: {readme_read_error_count}, DB Op Errors: {db_op_error_count})")

        except ImportError:
            logging.warning("DB Sync: Flask or DB models not available. Skipping DB synchronization. This is normal if running outside Flask app context.")
        except Exception as e:
            logging.error(f"DB Sync: General failure: {e}", exc_info=True)
            # Attempt rollback if session was obtained and error occurred before commit block
            if 'actual_db_session' in locals() and actual_db_session:
                 try: actual_db_session.rollback(); logging.info("DB Sync: Rolled back session due to general error.")
                 except: pass # Ignore rollback error if session is bad
            # Do not raise StateManagerError if it's just ImportError
            if not isinstance(e, ImportError): raise StateManagerError(f"DB Sync: Failed: {e}")

    async def get_processed_tweets(self) -> List[str]:
        """
        Get the list of processed tweet IDs.
        
        Returns:
            List[str]: A list of tweet IDs that have been processed.
        """
        if not self._initialized: 
            await self.initialize()
        logging.debug(f"Returning {len(self._processed_tweets)} processed tweet IDs")
        return list(self._processed_tweets.keys())
