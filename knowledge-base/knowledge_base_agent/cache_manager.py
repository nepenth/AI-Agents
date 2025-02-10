import json
import logging
from pathlib import Path
from typing import Optional, Dict, Any
from .file_utils import safe_read_json, safe_write_json
import time

# Default location for the tweet cache file
DEFAULT_CACHE_FILE = Path("data/tweet_cache.json")

def load_cache(cache_file: Optional[Path] = None) -> Dict[str, Any]:
    """
    Load the tweet cache from disk. Returns a dictionary mapping tweet IDs to cached data.
    If the file does not exist or is empty, return an empty dict.
    """
    cache_file = cache_file or DEFAULT_CACHE_FILE
    return safe_read_json(cache_file)

def save_cache(cache: Dict[str, Any], cache_file: Optional[Path] = None) -> None:
    """
    Save the tweet cache dictionary to disk.
    """
    cache_file = cache_file or DEFAULT_CACHE_FILE
    safe_write_json(cache_file, cache)

def get_cached_tweet(tweet_id: str, cache: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Return the cached data for a given tweet_id, or None if not found.
    """
    return cache.get(tweet_id)

def update_cache(tweet_id: str, tweet_data: Dict[str, Any], cache: Dict[str, Any]) -> None:
    """
    Update the cache with new tweet data for the given tweet_id.
    """
    cache[tweet_id] = tweet_data
    logging.info(f"Updated cache for tweet ID {tweet_id}.")

def clear_cache(cache_file: Optional[Path] = None) -> None:
    """
    Clear the entire cache by writing an empty dictionary.
    """
    save_cache({}, cache_file)
    logging.info("Cache cleared.")

class CacheManager:
    def __init__(self, cache_file: Path, expiry: int = 86400):
        self.cache_file = cache_file
        self.expiry = expiry
        self._cache = {}
        self._load_cache()

    def is_cached(self, key: str) -> bool:
        if key not in self._cache:
            return False
        timestamp = self._cache[key].get('timestamp', 0)
        return (time.time() - timestamp) < self.expiry

    async def get_or_fetch(self, key: str, fetch_func) -> Any:
        if self.is_cached(key):
            return self._cache[key]['data']
        data = await fetch_func()
        self._cache[key] = {
            'data': data,
            'timestamp': time.time()
        }
        await self._save_cache()
        return data
