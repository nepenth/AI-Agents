import json
import logging
from pathlib import Path
from typing import Optional, Dict, Any

# Default location for the tweet cache file
DEFAULT_CACHE_FILE = Path("data/tweet_cache.json")

def load_cache(cache_file: Optional[Path] = None) -> Dict[str, Any]:
    """
    Load the tweet cache from disk. Returns a dictionary mapping tweet IDs to cached data.
    If the file does not exist or is empty, return an empty dict.
    """
    cache_file = cache_file or DEFAULT_CACHE_FILE
    if not cache_file.exists():
        logging.info(f"Cache file {cache_file} does not exist. Initializing new cache.")
        return {}
    try:
        with cache_file.open('r', encoding='utf-8') as f:
            cache = json.load(f)
        logging.info(f"Loaded cache from {cache_file} with {len(cache)} entries.")
        return cache
    except Exception as e:
        logging.error(f"Error loading cache from {cache_file}: {e}")
        return {}

def save_cache(cache: Dict[str, Any], cache_file: Optional[Path] = None) -> None:
    """
    Save the tweet cache dictionary to disk.
    """
    cache_file = cache_file or DEFAULT_CACHE_FILE
    try:
        cache_file.parent.mkdir(parents=True, exist_ok=True)
        with cache_file.open('w', encoding='utf-8') as f:
            json.dump(cache, f, indent=4)
        logging.info(f"Saved cache with {len(cache)} entries to {cache_file}.")
    except Exception as e:
        logging.error(f"Error saving cache to {cache_file}: {e}")

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
