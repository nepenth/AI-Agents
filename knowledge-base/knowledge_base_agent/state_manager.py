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
        """Initialize StateManager with config."""
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

        # Reconcile tweet states
        logging.info("Reconciling tweet states across processed and unprocessed lists...")
        tweets_to_process = set()
        tweets_to_mark_processed = set()
        for tweet_id, tweet_data in self._tweet_cache.items():
            is_fully_processed = await self._validate_tweet_state_comprehensive(tweet_id, tweet_data)
            if is_fully_processed:
                if tweet_id not in self._processed_tweets:
                    tweets_to_mark_processed.add(tweet_id)
                    self._processed_tweets[tweet_id] = datetime.now().isoformat()
                    if tweet_id in self._unprocessed_tweets:
                        self._unprocessed_tweets.remove(tweet_id)
                        logging.debug(f"Tweet {tweet_id} validated as fully processed, moved to processed")
            else:
                if tweet_id not in self._unprocessed_tweets:
                    tweets_to_process.add(tweet_id)
                    self._unprocessed_tweets.append(tweet_id)
                    if tweet_id in self._processed_tweets:
                        del self._processed_tweets[tweet_id]
                    logging.debug(f"Tweet {tweet_id} incomplete, moved to unprocessed")

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
        """Mark a tweet as processed and update both sets."""
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

        media_list = tweet_data.get('media', [])
        downloaded_media = tweet_data.get('downloaded_media', [])
        logging.debug(f"Tweet {tweet_id} media: {media_list}, downloaded_media: {downloaded_media}")

        if tweet_data.get('cache_complete', False) or tweet_data.get('media_processed', False):
            media_paths = tweet_data.get('downloaded_media', [])
            has_media = bool(tweet_data.get('media', []))
            if has_media and (not media_paths or not all(Path(p).exists() for p in media_paths)):
                logging.warning(f"Tweet {tweet_id} has media but missing files: {media_paths}")
                updates_needed['cache_complete'] = False
                updates_needed['media_processed'] = False
                all_valid = False

        if tweet_data.get('categories_processed', False):
            categories = tweet_data.get('categories', {})
            required_fields = ['main_category', 'sub_category', 'item_name']
            if not categories or not all(categories.get(f) for f in required_fields):
                logging.warning(f"Tweet {tweet_id} categories_processed but missing fields: {required_fields}")
                updates_needed['categories_processed'] = False
                all_valid = False

        if tweet_data.get('kb_item_created', False):
            kb_path = tweet_data.get('kb_item_path', '')
            if not kb_path or not Path(kb_path).exists() or not (Path(kb_path) / "README.md").exists():
                logging.warning(f"Tweet {tweet_id} kb_item_created but path invalid: {kb_path}")
                updates_needed['kb_item_created'] = False
                all_valid = False

        if updates_needed:
            tweet_data.update(updates_needed)
            await self.update_tweet_data(tweet_id, tweet_data)
            logging.debug(f"Updated tweet {tweet_id} state due to validation: {updates_needed}")

        return (all_valid and 
                tweet_data.get('cache_complete', False) and 
                tweet_data.get('media_processed', False) and 
                tweet_data.get('categories_processed', False) and 
                tweet_data.get('kb_item_created', False))