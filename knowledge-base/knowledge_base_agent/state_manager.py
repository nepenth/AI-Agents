import json
import asyncio
import aiofiles
from pathlib import Path
from typing import Set, Dict, Any, List, Optional
import logging
from knowledge_base_agent.exceptions import StateError, StateManagerError
import tempfile
import os
import shutil
from knowledge_base_agent.config import Config
from knowledge_base_agent.file_utils import async_write_text, async_json_load, async_json_dump
from knowledge_base_agent.tweet_utils import parse_tweet_id_from_url, load_tweet_urls_from_links
from datetime import datetime

class StateManager:
    def __init__(self, config: Config):
        """Initialize the state manager."""
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
        self.validation_fixes = 0  # Add counter for validation fixes

    @property
    def processed_tweets(self) -> Dict[str, Any]:
        """Get processed tweets with proper encapsulation."""
        return self._processed_tweets
        
    @property
    def unprocessed_tweets(self) -> List[str]:
        """Get unprocessed tweet IDs."""
        return self._unprocessed_tweets

    async def initialize(self) -> None:
        """Initialize state manager, load existing state, and reconcile inconsistencies including knowledge base."""
        if self._initialized:
            return

        # Reset validation counter
        self.validation_fixes = 0

        # Ensure parent directories exist
        self.tweet_cache_file.parent.mkdir(parents=True, exist_ok=True)
        self.processed_tweets_file.parent.mkdir(parents=True, exist_ok=True)
        self.unprocessed_tweets_file.parent.mkdir(parents=True, exist_ok=True)

        # Load unprocessed tweets
        if self.unprocessed_tweets_file.exists():
            try:
                async with aiofiles.open(self.unprocessed_tweets_file, 'r') as f:
                    content = await f.read()
                    tweet_ids = json.loads(content) if content.strip() else []
                    self._unprocessed_tweets = tweet_ids
                logging.info(f"Loaded {len(self._unprocessed_tweets)} unprocessed tweets")
            except Exception as e:
                logging.error(f"Error loading unprocessed tweets: {e}")
                self._unprocessed_tweets = []

        # Load processed tweets
        if self.processed_tweets_file.exists():
            try:
                async with aiofiles.open(self.processed_tweets_file, 'r') as f:
                    content = await f.read()
                    processed_data = json.loads(content) if content.strip() else {}
                    self._processed_tweets = {k: v for k, v in processed_data.items()}
                logging.info(f"Loaded {len(self._processed_tweets)} processed tweets")
            except Exception as e:
                logging.error(f"Error loading processed tweets: {e}")
                self._processed_tweets = {}

        # Load tweet cache
        if self.tweet_cache_file.exists():
            try:
                async with aiofiles.open(self.tweet_cache_file, 'r') as f:
                    content = await f.read()
                    self._tweet_cache = json.loads(content) if content.strip() else {}
                logging.info(f"Loaded {len(self._tweet_cache)} cached tweets")
            except Exception as e:
                logging.error(f"Error loading tweet cache: {e}")
                self._tweet_cache = {}

        # Validate KB items first to ensure paths are correct
        logging.info("Validating tweet cache integrity...")
        await self.validate_kb_items()

        # Perform a more thorough reconciliation of tweet states
        logging.info("Reconciling tweet states across processed and unprocessed lists...")
        tweets_to_process = set()
        tweets_to_mark_processed = set()
        
        # First, ensure all cached tweets are either in processed or unprocessed
        for tweet_id in self._tweet_cache:
            if tweet_id not in self._processed_tweets and tweet_id not in self._unprocessed_tweets:
                logging.info(f"Tweet {tweet_id} found in cache but not in processed/unprocessed lists")
                self._unprocessed_tweets.append(tweet_id)
        
        # Then validate each tweet's state
        for tweet_id, tweet_data in self._tweet_cache.items():
            is_fully_processed = await self._validate_tweet_state_comprehensive(tweet_id, tweet_data)
            
            if is_fully_processed:
                if tweet_id not in self._processed_tweets:
                    tweets_to_mark_processed.add(tweet_id)
                    self._processed_tweets[tweet_id] = datetime.now().isoformat()
                    logging.info(f"Tweet {tweet_id} validated as fully processed, moving to processed")
                
                # Ensure it's removed from unprocessed list
                if tweet_id in self._unprocessed_tweets:
                    self._unprocessed_tweets.remove(tweet_id)
                    logging.debug(f"Removed tweet {tweet_id} from unprocessed list")
            else:
                # Only add to unprocessed if not already processed
                if tweet_id not in self._processed_tweets and tweet_id not in self._unprocessed_tweets:
                    tweets_to_process.add(tweet_id)
                    self._unprocessed_tweets.append(tweet_id)
                    logging.debug(f"Tweet {tweet_id} incomplete, added to unprocessed")
        
        # Remove any processed tweets that are still in unprocessed list
        processed_in_unprocessed = set(self._processed_tweets.keys()).intersection(set(self._unprocessed_tweets))
        if processed_in_unprocessed:
            logging.info(f"Found {len(processed_in_unprocessed)} tweets that are both processed and unprocessed")
            for tweet_id in processed_in_unprocessed:
                self._unprocessed_tweets.remove(tweet_id)
                logging.debug(f"Removed processed tweet {tweet_id} from unprocessed list")

        # Reconcile knowledge base with tweet cache
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

        for tweet_id, paths in duplicates.items():
            old_path = [p for p in paths if p != tweet_to_path[tweet_id]][0]
            logging.debug(f"Removing duplicate KB item for tweet {tweet_id}: {old_path}")
            shutil.rmtree(old_path, ignore_errors=True)

        for orphan_path in orphans:
            logging.debug(f"Removing orphaned KB item: {orphan_path}")
            shutil.rmtree(orphan_path, ignore_errors=True)

        logging.info(f"Removed {len(orphans)} orphaned KB items and handled {len(duplicates)} duplicates")
        if tweets_to_process or tweets_to_mark_processed or duplicates or orphans:
            await self._atomic_write_json(list(set(self._unprocessed_tweets)), self.unprocessed_tweets_file)
            await self._atomic_write_json(self._processed_tweets, self.processed_tweets_file)
            logging.info(f"Reconciliation results: {len(tweets_to_mark_processed)} moved to processed, {len(tweets_to_process)} moved to unprocessed")

        await self.cleanup_unprocessed_tweets()

        self._initialized = True

    async def _atomic_write_json(self, data: Any, filepath: Path) -> None:
        """Write JSON data atomically using a temporary file."""
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
        """Mark a tweet as processed and remove from unprocessed list."""
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
        """Get list of unprocessed tweet IDs and reconcile with cache."""
        if not self._initialized:
            await self.initialize()
        logging.debug(f"Returning {len(self._unprocessed_tweets)} unprocessed tweet IDs")
        return list(self._unprocessed_tweets)

    async def clear_state(self) -> None:
        """Clear all state (useful for testing or reset)."""
        async with self._lock:
            self._processed_tweets.clear()
            self._unprocessed_tweets.clear()
            await self._atomic_write_json({}, self.processed_tweets_file)
            await self._atomic_write_json([], self.unprocessed_tweets_file)
            logging.info("Cleared all state")

    async def update_from_bookmarks(self) -> None:
        """Update unprocessed tweets from bookmarks file."""
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
        """Save unprocessed tweets to file."""
        try:
            await self._atomic_write_json(list(self._unprocessed_tweets), self.unprocessed_tweets_file)
            logging.debug(f"Saved {len(self._unprocessed_tweets)} unprocessed tweets")
        except Exception as e:
            logging.error(f"Failed to save unprocessed tweets: {e}")
            raise StateManagerError(f"Failed to save unprocessed state: {e}")

    async def get_processing_state(self, tweet_id: str) -> Dict[str, bool]:
        """Get the processing state for a tweet."""
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
        """Get tweet data from cache."""
        try:
            tweet_data = self._tweet_cache.get(tweet_id)
            logging.debug(f"Retrieved tweet {tweet_id} from cache: {'found' if tweet_data else 'not found'}")
            return tweet_data
        except Exception as e:
            logging.error(f"Failed to get tweet {tweet_id} from cache: {e}")
            return None

    async def update_tweet_data(self, tweet_id: str, tweet_data: Dict[str, Any]) -> None:
        """Update existing tweet data without overwriting the entire cache."""
        if tweet_id in self._tweet_cache:
            self._tweet_cache[tweet_id].update(tweet_data)
            logging.debug(f"Updated tweet {tweet_id} data in cache")
        else:
            self._tweet_cache[tweet_id] = tweet_data
            logging.debug(f"Added tweet {tweet_id} to cache")
        
        try:
            await self._atomic_write_json(self._tweet_cache, self.tweet_cache_file)
        except Exception as e:
            logging.error(f"Failed to save updated tweet cache: {e}")
            raise StateError(f"Cache update failed: {e}")

    async def get_all_tweets(self) -> Dict[str, Dict[str, Any]]:
        """Get all cached tweets."""
        logging.debug(f"Returning all {len(self._tweet_cache)} cached tweets")
        return self._tweet_cache.copy()

    async def save_tweet_cache(self, tweet_id: str, data: Dict[str, Any]) -> None:
        """Save tweet data to cache without overwriting entire cache."""
        self._tweet_cache[tweet_id] = data
        try:
            await self._atomic_write_json(self._tweet_cache, self.tweet_cache_file)
            logging.debug(f"Saved tweet {tweet_id} to cache")
        except Exception as e:
            logging.error(f"Failed to save tweet cache for {tweet_id}: {e}")
            raise StateError(f"Cache save failed: {e}")

    async def get_tweet_cache(self, tweet_id: str) -> Optional[Dict[str, Any]]:
        """Get cached tweet data if available."""
        tweet_data = self._tweet_cache.get(tweet_id)
        logging.debug(f"Retrieved tweet {tweet_id} from cache: {'found' if tweet_data else 'not found'}")
        return tweet_data

    async def verify_cache_status(self) -> List[str]:
        """Verify cache status for all unprocessed tweets."""
        tweets_needing_cache = []
        for tweet_id in self._unprocessed_tweets:
            cached_data = self._tweet_cache.get(tweet_id)
            if not cached_data or not cached_data.get('cache_complete', False):
                tweets_needing_cache.append(tweet_id)
                logging.debug(f"Tweet {tweet_id} needs cache update")
        logging.info(f"Verified cache status: {len(tweets_needing_cache)} tweets need caching")
        return tweets_needing_cache

    async def update_media_analysis(self, tweet_id: str, media_analysis: Dict[str, Any]) -> None:
        """Update tweet cache with media analysis results."""
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
        """Update tweet cache with categorization results."""
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
        """Mark tweet as having KB item created and update cache."""
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
        """Mark media as processed for a tweet."""
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
        """Mark categories as processed for a tweet."""
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
        """Initialize a new tweet in the cache with its basic data."""
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
        """Move a processed tweet back to unprocessed state."""
        if tweet_id in self._processed_tweets:
            self._unprocessed_tweets.append(tweet_id)
            del self._processed_tweets[tweet_id]
            await self.save_unprocessed()
            logging.debug(f"Marked tweet {tweet_id} as unprocessed")

    async def _validate_tweet_state_comprehensive(self, tweet_id: str, tweet_data: Dict[str, Any]) -> bool:
        """Comprehensively validate a tweet's state, updating flags if invalid."""
        all_valid = True
        updates_needed = {}

        # Check cache completion
        if not tweet_data.get('cache_complete', False):
            # If media and categories are processed, mark cache as complete
            has_media = bool(tweet_data.get('media', []))
            media_processed = tweet_data.get('media_processed', not has_media)
            categories_processed = tweet_data.get('categories_processed', False)
            
            if media_processed and categories_processed:
                updates_needed['cache_complete'] = True
                logging.info(f"Tweet {tweet_id} has processed media and categories, marking cache complete")
            else:
                all_valid = False
        
        # Validate media processing
        if tweet_data.get('media_processed', False):
            media_paths = tweet_data.get('downloaded_media', [])
            has_media = bool(tweet_data.get('media', []))
            
            if has_media and (not media_paths or not all(Path(p).exists() for p in media_paths)):
                logging.warning(f"Tweet {tweet_id} has media but missing files: {media_paths}")
                updates_needed['cache_complete'] = False
                updates_needed['media_processed'] = False
                all_valid = False
        elif not tweet_data.get('media', []):
            # No media to process, mark as processed
            updates_needed['media_processed'] = True
        else:
            all_valid = False

        # Validate categories
        if tweet_data.get('categories_processed', False):
            categories = tweet_data.get('categories', {})
            required_fields = ['main_category', 'sub_category', 'item_name']
            
            if not categories or not all(categories.get(f) for f in required_fields):
                logging.warning(f"Tweet {tweet_id} categories_processed but missing fields: {required_fields}")
                updates_needed['categories_processed'] = False
                all_valid = False
        else:
            all_valid = False

        # Validate KB item
        if tweet_data.get('kb_item_created', False):
            kb_path_str = tweet_data.get('kb_item_path', '')
            if not kb_path_str:
                logging.warning(f"Tweet {tweet_id} kb_item_created but path is empty")
                updates_needed['kb_item_created'] = False
                all_valid = False
            else:
                # Check if KB item exists at the specified path
                kb_base = Path(self.config.knowledge_base_dir)
                kb_path = None
                
                # Handle different path formats
                if kb_path_str.startswith('kb-generated/'):
                    kb_path = kb_base.parent / kb_path_str
                elif not Path(kb_path_str).is_absolute():
                    kb_path = kb_base / kb_path_str
                else:
                    kb_path = Path(kb_path_str)
                    
                readme_path = kb_path / "README.md" if kb_path.is_dir() else kb_path.parent / "README.md"
                
                if not readme_path.exists():
                    logging.warning(f"Tweet {tweet_id} KB item README not found at {readme_path}")
                    updates_needed['kb_item_created'] = False
                    all_valid = False
        else:
            # Check if KB item exists but isn't marked as created
            await self._find_and_update_kb_item(tweet_id, tweet_data, updates_needed)
            if not updates_needed.get('kb_item_created', False):
                all_valid = False

        if updates_needed:
            tweet_data.update(updates_needed)
            await self.update_tweet_data(tweet_id, tweet_data)
            logging.debug(f"Updated tweet {tweet_id} state due to validation: {updates_needed}")
            self.validation_fixes += 1
            
            # Re-check if all valid after updates
            if 'kb_item_created' in updates_needed and updates_needed['kb_item_created']:
                all_valid = await self._validate_tweet_state_comprehensive(tweet_id, tweet_data)

        return (all_valid and 
                tweet_data.get('cache_complete', False) and 
                tweet_data.get('media_processed', False) and 
                tweet_data.get('categories_processed', False) and 
                tweet_data.get('kb_item_created', False))

    async def _find_and_update_kb_item(self, tweet_id: str, tweet_data: Dict[str, Any], updates_needed: Dict[str, Any]) -> None:
        """Find KB item for a tweet and update state if found."""
        kb_base = Path(self.config.knowledge_base_dir)
        possible_locations = [
            # Direct tweet ID path
            kb_base / str(tweet_id),
            # Categorized path
            kb_base / tweet_data.get('categories', {}).get('main_category', '') / 
                     tweet_data.get('categories', {}).get('sub_category', '') / 
                     tweet_data.get('categories', {}).get('item_name', ''),
            # Legacy category paths
            kb_base / tweet_data.get('category', '') / 
                     tweet_data.get('subcategory', '') / 
                     tweet_data.get('item_name', '')
        ]
        
        for path in possible_locations:
            if not path or str(path) == str(kb_base):
                continue
            
            if path.exists() and (path / "README.md").exists():
                try:
                    # Verify it's the correct KB item by checking content
                    async with aiofiles.open(path / "README.md", 'r') as f:
                        content = await f.read()
                        if f"https://twitter.com/i/web/status/{tweet_id}" in content:
                            # Found the correct KB item
                            relative_path = path.relative_to(kb_base.parent)
                            updates_needed['kb_item_path'] = str(relative_path)
                            updates_needed['kb_item_created'] = True
                            logging.info(f"Found existing KB item for tweet {tweet_id} at {path}")
                            return
                except Exception as e:
                    logging.warning(f"Error reading README for potential KB item at {path}: {e}")
                    continue

    async def validate_kb_items(self) -> None:
        """Validate KB items for all tweets and update paths if found."""
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
        """Perform final validation and move completed tweets to processed list."""
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
        """Clean up the unprocessed tweets list by removing any that are already processed or don't exist in cache."""
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
