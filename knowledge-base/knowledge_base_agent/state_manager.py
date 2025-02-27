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
        """Initialize state manager and load existing state."""
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

        # Load existing tweet cache if file exists
        if self.tweet_cache_file.exists():
            try:
                async with aiofiles.open(self.tweet_cache_file, 'r') as f:
                    content = await f.read()
                    self._tweet_cache = json.loads(content) if content.strip() else {}
                logging.info(f"Loaded {len(self._tweet_cache)} cached tweets")
            except Exception as e:
                logging.error(f"Error loading tweet cache: {e}")
                self._tweet_cache = {}

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
            
        except Exception as e:
            if temp_file and temp_file.exists():
                temp_file.unlink()
            raise StateError(f"Failed to write state file: {filepath}") from e

    async def mark_tweet_processed(self, tweet_id: str, tweet_data: Dict[str, Any] = None) -> None:
        """Mark a tweet as processed and update both sets."""
        async with self._lock:
            try:
                if not tweet_data:
                    logging.warning(f"No tweet data provided for {tweet_id}, skipping mark as processed")
                    return
                
                # Check if already processed
                if tweet_id in self._processed_tweets:
                    logging.info(f"Tweet {tweet_id} already marked as processed, skipping")
                    return

                # Required checks for processing completion
                required_checks = [
                    tweet_data.get('media_processed', not bool(tweet_data.get('media', []))),  # Default True if no media
                    tweet_data.get('categories_processed', False),
                    tweet_data.get('kb_item_created', False),
                    tweet_data.get('kb_item_path', None) is not None  # Ensure path exists
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

                # Update state
                self._processed_tweets[tweet_id] = datetime.now().isoformat()
                self._unprocessed_tweets.remove(tweet_id)

                # Save both files atomically
                await self._atomic_write_json(list(self._unprocessed_tweets), self.unprocessed_tweets_file)
                await self._atomic_write_json(self._processed_tweets, self.processed_tweets_file)

                logging.info(f"Marked tweet {tweet_id} as fully processed")

            except Exception as e:
                logging.exception(f"Failed to mark tweet {tweet_id} as processed")
                self._unprocessed_tweets.append(tweet_id)  # Re-add on failure
                raise StateError(f"Failed to update processing state: {e}")

    async def get_unprocessed_tweets(self) -> List[str]:
        """Get list of unprocessed tweet IDs and reconcile with cache."""
        if not self._initialized:
            await self.initialize()
        
        # Create a copy of the set for iteration
        to_process = list(self._unprocessed_tweets)
        to_remove = []
        
        # Check each tweet in the copy
        for tweet_id in to_process:
            tweet_data = self._tweet_cache.get(tweet_id, {})
            if (tweet_data.get('media_processed', not bool(tweet_data.get('media', []))) and
                tweet_data.get('categories_processed', False) and
                tweet_data.get('kb_item_created', False) and
                tweet_data.get('kb_item_path', None)):
                await self.mark_tweet_processed(tweet_id, tweet_data)
                continue
        
        return list(self._unprocessed_tweets)

    async def clear_state(self) -> None:
        """Clear all state (useful for testing or reset)."""
        async with self._lock:
            self._processed_tweets.clear()
            self._unprocessed_tweets.clear()
            await self._atomic_write_json({}, self.processed_tweets_file)
            await self._atomic_write_json([], self.unprocessed_tweets_file)

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
                logging.info(f"Added {len(new_tweets)} new tweets to process")
        except Exception as e:
            logging.error(f"Failed to update from bookmarks: {e}")
            raise StateManagerError(f"Failed to update from bookmarks: {e}")

    async def save_unprocessed(self) -> None:
        """Save unprocessed tweets to file."""
        try:
            await self._atomic_write_json(list(self._unprocessed_tweets), self.unprocessed_tweets_file)
        except Exception as e:
            logging.error(f"Failed to save unprocessed tweets: {e}")
            raise StateManagerError(f"Failed to save unprocessed state: {e}")

    async def get_processing_state(self, tweet_id: str) -> Dict[str, bool]:
        """Get the processing state for a tweet."""
        try:
            tweet_data = await self.get_tweet(tweet_id)
            if not tweet_data:
                return {}
            return {
                'media_processed': tweet_data.get('media_processed', False),
                'categories_processed': tweet_data.get('categories_processed', False),
                'kb_item_created': tweet_data.get('kb_item_created', False),
                'fully_processed': tweet_id in self._processed_tweets
            }
        except Exception as e:
            logging.error(f"Failed to get processing state for tweet {tweet_id}: {e}")
            raise StateError(f"Failed to get processing state: {e}")

    async def get_tweet(self, tweet_id: str) -> Optional[Dict[str, Any]]:
        """Get tweet data from cache."""
        try:
            return self._tweet_cache.get(tweet_id)
        except Exception as e:
            logging.error(f"Failed to get tweet {tweet_id} from cache: {e}")
            return None

    async def update_tweet_data(self, tweet_id: str, tweet_data: Dict[str, Any]) -> None:
        """Update existing tweet data without overwriting the entire cache."""
        if tweet_id in self._tweet_cache:
            self._tweet_cache[tweet_id].update(tweet_data)
        else:
            self._tweet_cache[tweet_id] = tweet_data
        
        try:
            await self._atomic_write_json(self._tweet_cache, self.tweet_cache_file)
        except Exception as e:
            logging.error(f"Failed to save updated tweet cache: {e}")
            raise StateError(f"Cache update failed: {e}")

    async def get_all_tweets(self) -> Dict[str, Dict[str, Any]]:
        """Get all cached tweets."""
        return self._tweet_cache.copy()

    async def save_tweet_cache(self, tweet_id: str, data: Dict[str, Any]) -> None:
        """Save tweet data to cache without overwriting entire cache."""
        self._tweet_cache[tweet_id] = data
        try:
            await self._atomic_write_json(self._tweet_cache, self.tweet_cache_file)
        except Exception as e:
            logging.error(f"Failed to save tweet cache for {tweet_id}: {e}")
            raise StateError(f"Cache save failed: {e}")

    async def get_tweet_cache(self, tweet_id: str) -> Optional[Dict[str, Any]]:
        """Get cached tweet data if available."""
        return self._tweet_cache.get(tweet_id)

    async def verify_cache_status(self) -> List[str]:
        """Verify cache status for all unprocessed tweets."""
        tweets_needing_cache = []
        for tweet_id in self._unprocessed_tweets:
            cached_data = self._tweet_cache.get(tweet_id)
            if not cached_data or not cached_data.get('cache_complete', False):
                tweets_needing_cache.append(tweet_id)
                logging.info(f"Tweet {tweet_id} needs cache update")
        return tweets_needing_cache

    async def update_media_analysis(self, tweet_id: str, media_analysis: Dict[str, Any]) -> None:
        """Update tweet cache with media analysis results."""
        if tweet_id not in self._tweet_cache:
            raise StateError(f"Tweet {tweet_id} not found in cache")
        
        self._tweet_cache[tweet_id].update({
            'media_analysis': media_analysis,
            'media_analysis_complete': True
        })
        await self._atomic_write_json(self._tweet_cache, self.tweet_cache_file)
        logging.info(f"Updated media analysis for tweet {tweet_id}")

    async def update_categories(self, tweet_id: str, category_data: Dict[str, Any]) -> None:
        """Update tweet cache with categorization results."""
        if tweet_id not in self._tweet_cache:
            raise StateError(f"Tweet {tweet_id} not found in cache")
        
        self._tweet_cache[tweet_id].update({
            'category': category_data.get('category'),
            'subcategory': category_data.get('subcategory'),
            'item_name': category_data.get('item_name'),
            'categories_processed': True
        })
        await self._atomic_write_json(self._tweet_cache, self.tweet_cache_file)
        logging.info(f"Updated categories for tweet {tweet_id}")

    async def mark_kb_item_created(self, tweet_id: str, kb_item_path: str) -> None:
        """Mark tweet as having KB item created and update cache."""
        if tweet_id not in self._tweet_cache:
            raise StateError(f"Tweet {tweet_id} not found in cache")
        
        self._tweet_cache[tweet_id].update({
            'kb_item_path': kb_item_path,
            'kb_item_created': True
        })
        await self._atomic_write_json(self._tweet_cache, self.tweet_cache_file)
        logging.info(f"Marked KB item created for tweet {tweet_id}")

    async def mark_media_processed(self, tweet_id: str) -> None:
        """Mark media as processed for a tweet."""
        try:
            tweet_data = await self.get_tweet(tweet_id)
            if tweet_data:
                tweet_data['media_processed'] = True
                await self.update_tweet_data(tweet_id, tweet_data)
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
        logging.info(f"Initialized cache for tweet {tweet_id}")

    async def mark_tweet_unprocessed(self, tweet_id: str) -> None:
        """Move a processed tweet back to unprocessed state."""
        if tweet_id in self._processed_tweets:
            self._unprocessed_tweets.append(tweet_id)
            del self._processed_tweets[tweet_id]
            await self.save_unprocessed()
            logging.info(f"Marked tweet {tweet_id} as unprocessed")