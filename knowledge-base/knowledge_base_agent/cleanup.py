import shutil
import logging
from pathlib import Path
import re
import aiofiles

def delete_knowledge_base_item(tweet_id: str, processed_tweets: dict, knowledge_base_dir: Path):
    if tweet_id not in processed_tweets:
        return
    entry = processed_tweets[tweet_id]
    main_category = entry.get("main_category")
    sub_category = entry.get("sub_category")
    item_name = entry.get("item_name")
    tweet_folder = knowledge_base_dir / main_category / sub_category / item_name
    if tweet_folder.exists() and tweet_folder.is_dir():
        try:
            shutil.rmtree(tweet_folder)
            logging.info(f"Deleted knowledge base item: {tweet_folder}")
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

def clean_duplicate_folders(root_dir: Path) -> None:
    """Clean up duplicate folders that end with (n) or _n pattern."""
    try:
        for main_category in root_dir.iterdir():
            if not main_category.is_dir() or main_category.name.startswith('.'):
                continue
            for sub_category in main_category.iterdir():
                if not sub_category.is_dir() or sub_category.name.startswith('.'):
                    continue
                
                # Group items by their base name (without _n or (n) suffix)
                items_by_base = {}
                for item in sub_category.iterdir():
                    if not item.is_dir():
                        continue
                    base_name = re.sub(r'[_\(]\d+[\)]?$', '', item.name)
                    if base_name not in items_by_base:
                        items_by_base[base_name] = []
                    items_by_base[base_name].append(item)
                
                # For each group of similar names, keep the oldest and remove others
                for base_name, items in items_by_base.items():
                    if len(items) > 1:
                        # Sort by creation time
                        items.sort(key=lambda x: x.stat().st_ctime)
                        # Keep the oldest, remove others
                        for item in items[1:]:
                            logging.info(f"Removing duplicate folder: {item}")
                            shutil.rmtree(str(item))
                            
    except Exception as e:
        logging.error(f"Error cleaning duplicate directories in {root_dir}: {e}")

async def cleanup_orphaned_media(knowledge_base_dir: Path) -> None:
    """Remove media files that aren't referenced in any content.md"""
    referenced_media = set()
    for content_file in knowledge_base_dir.rglob('content.md'):
        text = await aiofiles.open(content_file, 'r').read()
        referenced_media.update(re.findall(r'!\[.*?\]\((.*?)\)', text))
    
    for media_file in knowledge_base_dir.rglob('*.jpg'):
        if media_file.name not in referenced_media:
            media_file.unlink()
