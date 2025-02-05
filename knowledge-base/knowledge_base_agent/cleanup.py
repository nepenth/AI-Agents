import shutil
import logging
from pathlib import Path

def delete_knowledge_base_item(tweet_id: str, processed_tweets: dict, knowledge_base_dir: Path):
    if tweet_id not in processed_tweets:
        return
    entry = processed_tweets[tweet_id]
    main_category = entry["main_category"]
    sub_category = entry["sub_category"]
    item_name = entry["item_name"]
    tweet_folder = knowledge_base_dir / main_category / sub_category / item_name
    if tweet_folder.exists() and tweet_folder.is_dir():
        try:
            shutil.rmtree(tweet_folder)
        except Exception as e:
            logging.error(f"Failed to delete directory {tweet_folder}: {e}")

def clean_untitled_directories(root_dir: Path) -> None:
    try:
        for main_category in root_dir.iterdir():
            if not main_category.is_dir() or main_category.name.startswith('.'):
                continue
            for sub_category in main_category.iterdir():
                if not sub_category.is_dir() or sub_category.name.startswith('.'):
                    continue
                for item in sub_category.iterdir():
                    if item.is_dir() and item.name.startswith("untitled_"):
                        try:
                            shutil.rmtree(str(item))
                        except Exception as e:
                            logging.error(f"Failed to remove directory {item}: {e}")
    except Exception as e:
        logging.error(f"Error cleaning untitled directories in {root_dir}: {e}")
