import json
import logging
from pathlib import Path
from .file_utils import safe_read_json, safe_write_json

def load_processed_tweets(file_path: Path) -> dict:
    data = safe_read_json(file_path)
    processed = {}
    for tweet_id, entry in data.items():
        if all(entry.get(k) for k in ["item_name", "main_category", "sub_category"]):
            processed[tweet_id] = entry
    return processed

def save_processed_tweets(file_path: Path, processed_tweets: dict) -> None:
    safe_write_json(file_path, processed_tweets)
