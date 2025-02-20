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
        self._unprocessed_tweets = set()
        self._initialized = False
        self._lock = asyncio.Lock()

    async def initialize(self) -> None:
        """Initialize state manager and load existing state."""
        if self._initialized:
            return

        # Ensure parent directories exist
        self.tweet_cache_file.parent.mkdir(parents=True, exist_ok=True)
        self.processed_tweets_file.parent.mkdir(parents=True, exist_ok=True)

        # Load unprocessed tweets
        if self.unprocessed_tweets_file.exists():
            try:
                async with aiofiles.open(self.unprocessed_tweets_file, 'r') as f:
                    content = await f.read()
                    tweet_ids = json.loads(content) if content.strip() else []
                    self._unprocessed_tweets = set(tweet_ids)
                logging.info(f"Loaded {len(self._unprocessed_tweets)} unprocessed tweets")
            except Exception as e:
                logging.error(f"Error loading unprocessed tweets: {e}")
                self._unprocessed_tweets = set()

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

    async def _atomic_write_json(self, data: Dict[str, Any], filepath: Path) -> None:
        """Write JSON data atomically using a temporary file."""
        temp_file = None
        try:
            # Create temporary file in the same directory
            temp_fd, temp_path = tempfile.mkstemp(dir=filepath.parent)
            os.close(temp_fd)
            temp_file = Path(temp_path)
            
            # Write to temporary file
            async with aiofiles.open(temp_file, 'w') as f:
                await f.write(json.dumps(data, indent=2))
            
            # Atomic rename
            shutil.move(str(temp_file), str(filepath))
            
        except Exception as e:
            if temp_file and temp_file.exists():
                temp_file.unlink()
            raise StateError(f"Failed to write state file: {filepath}") from e

    async def _load_processed_tweets(self) -> None:
        """Load processed tweets from state file."""
        try:
            if self.config.processed_tweets_file.exists():
                async with aiofiles.open(self.config.processed_tweets_file, 'r') as f:
                    content = await f.read()
                    self._processed_tweets = dict.fromkeys(json.loads(content), True)
        except Exception as e:
            logging.error(f"Failed to load processed tweets: {e}")
            self._processed_tweets = {}

    async def mark_tweet_processed(self, tweet_id: str, tweet_data: Dict[str, Any] = None) -> None:
        """Mark a tweet as processed and update both sets."""
        async with self._lock:
            try:
                # Verify tweet has been fully processed
                if not tweet_data:
                    logging.warning(f"No tweet data provided for {tweet_id}, skipping mark as processed")
                    return
                
                # Check for required processing steps
                if not all([
                    # Media processing check (True if no media present)
                    tweet_data.get('media_processed', not bool(tweet_data.get('media'))),
                    # Category processing check
                    tweet_data.get('categories_processed', False),
                    # Knowledge base item creation check
                    tweet_data.get('kb_item_created', False),
                    tweet_data.get('kb_item_path', None)
                ]):
                    logging.warning(f"Tweet {tweet_id} has not completed all processing steps")
                    missing_steps = []
                    if not tweet_data.get('media_processed', True) and tweet_data.get('media'):
                        missing_steps.append("media processing")
                    if not tweet_data.get('categories_processed'):
                        missing_steps.append("category processing")
                    if not tweet_data.get('kb_item_created'):
                        missing_steps.append("knowledge base item creation")
                    logging.warning(f"Missing steps: {', '.join(missing_steps)}")
                    return
                
                # If all checks pass, mark as processed
                self._processed_tweets[tweet_id] = True
                self._unprocessed_tweets.discard(tweet_id)
                
                # Save both states
                await self._atomic_write_json(
                    list(self._processed_tweets.keys()),
                    self.config.processed_tweets_file
                )
                await self._atomic_write_json(
                    list(self._unprocessed_tweets),
                    self.unprocessed_file
                )
                logging.info(f"Marked tweet {tweet_id} as fully processed")
                
            except Exception as e:
                logging.exception(f"Failed to mark tweet {tweet_id} as processed")
                raise StateError(f"Failed to update processing state: {e}")

    async def get_unprocessed_tweets(self, all_tweets: Set[str]) -> Set[str]:
        """Get set of unprocessed tweets."""
        async with self._lock:
            return all_tweets - set(self._processed_tweets.keys())

    async def clear_state(self) -> None:
        """Clear all state (useful for testing or reset)."""
        async with self._lock:
            self._processed_tweets.clear()
            await self._atomic_write_json([], self.config.processed_tweets_file)

    async def load_processed_tweets(self) -> set:
        """Load processed tweets from state file."""
        try:
            if self.config.processed_tweets_file.exists():
                data = await async_json_load(str(self.config.processed_tweets_file))
                return set(data)
            return set()
        except Exception as e:
            logging.error(f"Failed to load processed tweets: {e}")
            return set()

    async def update_from_bookmarks(self) -> None:
        """Update unprocessed tweets from bookmarks file."""
        try:
            # Read bookmarks file using correct function name
            bookmark_urls = load_tweet_urls_from_links(self.config.bookmarks_file)
            
            # Extract tweet IDs and filter out already processed ones
            new_unprocessed = set()
            for url in bookmark_urls:
                tweet_id = parse_tweet_id_from_url(url)
                if tweet_id and tweet_id not in self._processed_tweets:
                    new_unprocessed.add(tweet_id)
            
            # Update unprocessed set and save
            if new_unprocessed:
                self._unprocessed_tweets.update(new_unprocessed)
                await self.save_unprocessed()
                logging.info(f"Added {len(new_unprocessed)} new tweets to process")
            else:
                logging.info("No new tweets to process")

        except Exception as e:
            logging.error(f"Failed to update from bookmarks: {e}")
            raise StateManagerError(f"Failed to update from bookmarks: {e}")

    async def save_unprocessed(self) -> None:
        """Save unprocessed tweets to file."""
        try:
            await async_json_dump(list(self._unprocessed_tweets), self.unprocessed_file)
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
                'fully_processed': tweet_data.get('processed', False)
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
            # Update existing tweet data while preserving other fields
            self._tweet_cache[tweet_id].update(tweet_data)
        else:
            self._tweet_cache[tweet_id] = tweet_data

        # Save the updated cache
        try:
            async with aiofiles.open(self.tweet_cache_file, 'w') as f:
                await f.write(json.dumps(self._tweet_cache, indent=2))
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
            async with aiofiles.open(self.tweet_cache_file, 'w') as f:
                await f.write(json.dumps(self._tweet_cache, indent=2))
        except Exception as e:
            logging.error(f"Failed to save tweet cache for {tweet_id}: {e}")
            raise StateError(f"Cache save failed: {e}")

    async def get_tweet_cache(self, tweet_id: str) -> Optional[Dict[str, Any]]:
        """Get cached tweet data if available."""
        return self._tweet_cache.get(tweet_id)

    async def verify_cache_status(self) -> List[str]:
        """
        Verify cache status for all unprocessed tweets.
        Returns list of tweet IDs needing cache updates.
        """
        tweets_needing_cache = []
        
        for tweet_id in self._unprocessed_tweets:
            # Check if tweet exists in cache
            cached_data = self._tweet_cache.get(tweet_id)
            if not cached_data or not cached_data.get('cache_complete', False):
                tweets_needing_cache.append(tweet_id)
                logging.info(f"Tweet {tweet_id} needs cache update")
            
        return tweets_needing_cache

    async def update_media_analysis(self, tweet_id: str, media_analysis: Dict[str, Any]) -> None:
        """
        Update tweet cache with media analysis results.
        """
        if tweet_id not in self._tweet_cache:
            raise StateError(f"Tweet {tweet_id} not found in cache")
        
        # Update existing tweet data with media analysis
        self._tweet_cache[tweet_id].update({
            'media_analysis': media_analysis,
            'media_analysis_complete': True
        })
        
        # Save updated cache
        await self._atomic_write_json(self._tweet_cache, self.tweet_cache_file)
        logging.info(f"Updated media analysis for tweet {tweet_id}")

    async def update_categories(self, tweet_id: str, category_data: Dict[str, Any]) -> None:
        """
        Update tweet cache with categorization results.
        """
        if tweet_id not in self._tweet_cache:
            raise StateError(f"Tweet {tweet_id} not found in cache")
        
        # Update existing tweet data with categories
        self._tweet_cache[tweet_id].update({
            'category': category_data.get('category'),
            'subcategory': category_data.get('subcategory'),
            'item_name': category_data.get('item_name'),
            'categories_processed': True
        })
        
        # Save updated cache
        await self._atomic_write_json(self._tweet_cache, self.tweet_cache_file)
        logging.info(f"Updated categories for tweet {tweet_id}")

    async def mark_kb_item_created(self, tweet_id: str, kb_item_path: str) -> None:
        """
        Mark tweet as having KB item created and update cache.
        """
        if tweet_id not in self._tweet_cache:
            raise StateError(f"Tweet {tweet_id} not found in cache")
        
        # Update cache with KB item info
        self._tweet_cache[tweet_id].update({
            'kb_item_path': kb_item_path,
            'kb_item_created': True
        })
        
        # Save updated cache
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

