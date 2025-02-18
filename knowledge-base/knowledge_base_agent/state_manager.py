import json
import asyncio
import aiofiles
from pathlib import Path
from typing import Set, Dict, Any
import logging
from knowledge_base_agent.exceptions import StateError
import tempfile
import os
import shutil
from knowledge_base_agent.config import Config
from knowledge_base_agent.utils import async_write_text, async_json_load

class StateManager:
    def __init__(self, config: Config):
        self.config = config
        self._initialized = False
        self.processed_tweets = set()
        self.unprocessed_tweets: Set[str] = set()
        self._lock = asyncio.Lock()
        
    async def initialize(self) -> None:
        """Initialize the state manager."""
        try:
            logging.info("Starting state manager initialization")
            
            # Ensure unprocessed tweets file exists
            try:
                if not self.config.unprocessed_tweets_file.parent.exists():
                    logging.debug(f"Creating directory: {self.config.unprocessed_tweets_file.parent}")
                    self.config.unprocessed_tweets_file.parent.mkdir(parents=True, exist_ok=True)
                
                if not self.config.unprocessed_tweets_file.exists():
                    logging.debug(f"Creating file at: {self.config.unprocessed_tweets_file}")
                    filepath = str(self.config.unprocessed_tweets_file)
                    logging.debug(f"Writing to filepath: {filepath}")
                    await async_write_text("[]", filepath)
                
                # Ensure processed tweets file exists
                if not self.config.processed_tweets_file.exists():
                    logging.debug(f"Creating file at: {self.config.processed_tweets_file}")
                    filepath = str(self.config.processed_tweets_file)
                    logging.debug(f"Writing to filepath: {filepath}")
                    await async_write_text("[]", filepath)
                
            except Exception as e:
                logging.exception("Failed during file creation")
                raise StateError(f"Failed to create state files: {str(e)}")
            
            # Load processed tweets
            try:
                logging.debug("Loading processed tweets")
                self.processed_tweets = await self.load_processed_tweets()
            except Exception as e:
                logging.exception("Failed to load processed tweets")
                raise StateError(f"Failed to load processed tweets: {str(e)}")
            
            self._initialized = True
            logging.info("State manager initialization complete")
            
        except Exception as e:
            logging.exception("State manager initialization failed")
            raise StateError(f"Failed to initialize state manager: {str(e)}")

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
                    self.processed_tweets = set(json.loads(content))
        except Exception as e:
            logging.error(f"Failed to load processed tweets: {e}")
            self.processed_tweets = set()

    async def mark_tweet_processed(self, tweet_id: str) -> None:
        """Mark a tweet as processed with atomic write."""
        async with self._lock:
            try:
                self.processed_tweets.add(tweet_id)
                await self._atomic_write_json(
                    list(self.processed_tweets),
                    self.config.processed_tweets_file
                )
                logging.info(f"Marked tweet {tweet_id} as processed")
            except Exception as e:
                logging.exception(f"Failed to mark tweet {tweet_id} as processed")
                raise StateError(f"Failed to update processed state for tweet {tweet_id}") from e

    async def is_processed(self, tweet_id: str) -> bool:
        """Check if a tweet has been processed."""
        async with self._lock:
            return tweet_id in self.processed_tweets

    async def get_unprocessed_tweets(self, all_tweets: Set[str]) -> Set[str]:
        """Get set of unprocessed tweets."""
        async with self._lock:
            return all_tweets - self.processed_tweets

    async def clear_state(self) -> None:
        """Clear all state (useful for testing or reset)."""
        async with self._lock:
            self.processed_tweets.clear()
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
