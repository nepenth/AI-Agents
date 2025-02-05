import json
import logging
from pathlib import Path

def load_processed_tweets(file_path: Path) -> dict:
    if not file_path.exists():
        return {}
    try:
        with file_path.open('r', encoding='utf-8') as f:
            data = json.load(f)
        processed = {}
        for tweet_id, entry in data.items():
            item_name = entry.get("item_name", "")
            main_category = entry.get("main_category", "")
            sub_category = entry.get("sub_category", "")
            if main_category and sub_category and item_name:
                processed[tweet_id] = entry
        return processed
    except Exception as e:
        logging.error(f"Failed to load processed tweets from {file_path}: {e}")
        return {}

def save_processed_tweets(file_path: Path, processed_tweets: dict):
    try:
        file_path.parent.mkdir(parents=True, exist_ok=True)
        with file_path.open('w', encoding='utf-8') as f:
            json.dump(processed_tweets, f, indent=4)
    except Exception as e:
        logging.error(f"Failed to save processed tweets to {file_path}: {e}")
