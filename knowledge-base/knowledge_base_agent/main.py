import asyncio
import datetime
import logging
from pathlib import Path
import requests
from dotenv import load_dotenv
from typing import List

from knowledge_base_agent.config import Config, setup_logging
from knowledge_base_agent.category_manager import CategoryManager
from knowledge_base_agent.tweet_utils import load_tweet_urls_from_links, parse_tweet_id_from_url
from knowledge_base_agent.playwright_fetcher import fetch_tweet_data_playwright
from knowledge_base_agent.image_interpreter import interpret_image
from knowledge_base_agent.ai_categorization import categorize_and_name_content
from knowledge_base_agent.markdown_writer import write_tweet_markdown, generate_root_readme
from knowledge_base_agent.state_manager import load_processed_tweets, save_processed_tweets
from knowledge_base_agent.cleanup import delete_knowledge_base_item, clean_untitled_directories, clean_duplicate_folders
from knowledge_base_agent.git_helper import push_to_github
from knowledge_base_agent.reprocess import reprocess_existing_items
from knowledge_base_agent.cache_manager import load_cache, save_cache, get_cached_tweet, update_cache, clear_cache
from .cache_manager import cache_tweet_data
from knowledge_base_agent.http_client import create_http_client
from knowledge_base_agent.fetch_bookmarks import fetch_bookmarks
from knowledge_base_agent.migration import migrate_content_to_readme, check_and_prompt_migration
from knowledge_base_agent.agent import KnowledgeBaseAgent
from .tweet_processor import process_tweets

# Load environment variables at the start
load_dotenv()

def filter_new_tweet_urls(tweet_urls: list, processed_tweets: dict) -> list:
    """Return only the URLs whose tweet IDs are not already processed."""
    new_urls = []
    for url in tweet_urls:
        tweet_id = parse_tweet_id_from_url(url)
        if tweet_id and tweet_id not in processed_tweets:
            new_urls.append(url)
    return new_urls

def validate_processed_items(processed_tweets: dict, knowledge_base_dir: Path) -> dict:
    """
    Validate that for each tweet in the processed state, the corresponding
    knowledge base item folder exists.
    Returns a new dictionary containing only the valid entries.
    """
    valid_state = {}
    for tweet_id, entry in processed_tweets.items():
        main_cat = entry.get("main_category")
        sub_cat = entry.get("sub_category")
        item_name = entry.get("item_name")
        if main_cat and sub_cat and item_name:
            item_folder = knowledge_base_dir / main_cat / sub_cat / item_name
            if item_folder.exists() and item_folder.is_dir():
                valid_state[tweet_id] = entry
            else:
                logging.warning(f"Processed tweet {tweet_id} marked in state, but folder {item_folder} does not exist.")
        else:
            logging.warning(f"Processed tweet {tweet_id} missing required metadata.")
    return valid_state

async def cache_tweet_data(tweet_url: str, config: Config, tweet_cache: dict, http_client: requests.Session) -> None:
    """
    Pre-fetch and cache tweet data for a tweet URL.
    Downloads all associated media to the media cache directory and stores
    high-resolution URLs and local file paths in the tweet cache.
    """
    tweet_id = parse_tweet_id_from_url(tweet_url)
    if not tweet_id:
        logging.warning(f"Invalid tweet URL skipped during caching: {tweet_url}")
        return

    if get_cached_tweet(tweet_id, tweet_cache):
        logging.info(f"Tweet {tweet_id} already cached.")
        return

    logging.info(f"Caching data for tweet {tweet_id}")
    try:
        tweet_data = await fetch_tweet_data_playwright(tweet_id)
        tweet_data["downloaded_media"] = []  # initialize list for local media paths
    except Exception as e:
        logging.error(f"Failed to fetch tweet data for caching for {tweet_id}: {e}")
        return

    image_descriptions = []
    image_files = []
    extended_media = tweet_data.get("extended_media", [])
    # Ensure media cache directory exists.
    config.media_cache_dir.mkdir(parents=True, exist_ok=True)
    for i, media_obj in enumerate(extended_media):
        image_url = media_obj.get("media_url_https")
        if not image_url:
            continue

        local_img_path = config.media_cache_dir / f"{tweet_id}_{i}.jpg"
        try:
            resp = http_client.get(image_url, stream=True, timeout=60)
            resp.raise_for_status()
            with local_img_path.open("wb") as f:
                for chunk in resp.iter_content(chunk_size=8192):
                    f.write(chunk)
            from PIL import Image
            with Image.open(local_img_path) as img:
                if img.format not in ['JPEG', 'PNG']:
                    raise ValueError(f"Invalid image format: {img.format}")
            logging.info(f"Downloaded image {i+1} for tweet {tweet_id}: {image_url}")
            desc = interpret_image(config.ollama_url, local_img_path, config.vision_model,
                                   http_client=http_client)
            image_descriptions.append(desc)
            image_files.append(local_img_path)
        except Exception as e:
            logging.error(f"Error processing image {image_url} for tweet {tweet_id}: {e}")
            continue

    downloaded_paths = [str(path.resolve()) for path in image_files]
    tweet_data["downloaded_media"] = downloaded_paths
    tweet_data["image_descriptions"] = image_descriptions
    update_cache(tweet_id, tweet_data, tweet_cache)
    save_cache(tweet_cache)
    logging.info(f"Cached tweet data for {tweet_id}")

async def generate_knowledge_base_item(tweet_url: str, config: Config, category_manager: CategoryManager,
                                       http_client: requests.Session, tweet_cache: dict) -> None:
    """
    Generate the knowledge base item for a tweet using the cached tweet data.
    """
    tweet_id = parse_tweet_id_from_url(tweet_url)
    if not tweet_id:
        logging.warning(f"Invalid tweet URL skipped during KB generation: {tweet_url}")
        return

    cached_data = get_cached_tweet(tweet_id, tweet_cache)
    if not cached_data:
        logging.error(f"No cached data for tweet {tweet_id}; skipping KB generation.")
        return

    tweet_data = cached_data
    tweet_text = tweet_data.get("full_text", "")
    image_descriptions = tweet_data.get("image_descriptions", [])
    downloaded_media = tweet_data.get("downloaded_media", [])
    image_files = [Path(path) for path in downloaded_media]

    combined_text = tweet_text.strip()
    if tweet_text:
        combined_text += f"\nTweet text: {tweet_text}\n\n"
    for idx, desc in enumerate(image_descriptions):
        combined_text += f"Image {idx+1} interpretation: {desc}\n\n"

    try:
        main_cat, sub_cat, item_name = await categorize_and_name_content(
            config.ollama_url,
            combined_text,
            config.text_model,
            tweet_id,
            category_manager,
            http_client=http_client
        )
    except Exception as e:
        logging.error(f"Failed to categorize tweet {tweet_id} during KB generation: {e}")
        return

    try:
        await write_tweet_markdown(
            root_dir=config.knowledge_base_dir,
            tweet_id=tweet_id,
            main_category=main_cat,
            sub_category=sub_cat,
            item_name=item_name,
            tweet_text=tweet_text,
            image_files=image_files,
            image_descriptions=image_descriptions,
            tweet_url=tweet_url
        )
    except Exception as e:
        logging.error(f"Failed to write markdown for tweet {tweet_id} during KB generation: {e}")
        return

    processed_tweets = load_processed_tweets(config.processed_tweets_file)
    processed_tweets[tweet_id] = {
        "item_name": item_name,
        "main_category": main_cat,
        "sub_category": sub_cat,
        "timestamp": datetime.datetime.now().isoformat()
    }
    save_processed_tweets(config.processed_tweets_file, processed_tweets)
    logging.info(f"Successfully processed tweet {tweet_id} -> {main_cat}/{sub_cat}/{item_name}")

async def cache_tweets(urls: List[str], config: Config, tweet_cache: dict, http_client) -> None:
    """Pre-fetch and cache tweet data for a list of URLs."""
    for url in urls:
        try:
            await cache_tweet_data(url, config, tweet_cache, http_client)
        except Exception as e:
            logging.error(f"Failed to cache tweet data for {url}: {e}")
            continue

def load_config() -> Config:
    """Load configuration with default values."""
    return Config.from_env()

async def main_async():
    """Main async function for the Knowledge Base Agent."""
    config = Config.from_env()
    setup_logging(config.log_file.parent)
    
    print("\n=== Knowledge Base Agent ===\n")
    
    try:
        # 1. Migration check (if needed)
        await check_and_prompt_migration(config.knowledge_base_dir)
        
        # 2. Initialize managers
        category_manager = CategoryManager(config.categories_file)
        http_client = create_http_client()
        tweet_cache = load_cache()

        # 3. Bookmarks update
        if prompt_yes_no("Update bookmarks?"):
            success = fetch_bookmarks(config)
            if not success:
                print("Failed to update bookmarks. Proceeding with existing bookmarks.")

        # 4. Load and filter tweets
        tweet_urls = load_tweet_urls_from_links(config.bookmarks_file)
        processed_tweets = load_processed_tweets(config.processed_tweets_file)
        new_urls = filter_new_tweet_urls(tweet_urls, processed_tweets)

        if new_urls:
            # 5. Cache tweet data
            if prompt_yes_no("Cache tweet data for new tweets?"):
                await cache_tweets(new_urls, config, tweet_cache, http_client)
            
            # 6. Process tweets
            await process_tweets(new_urls, config, category_manager, http_client, tweet_cache)

        # 7. Maintenance operations
        await perform_maintenance_operations(config, category_manager)

    except Exception as e:
        logging.error(f"Error in main process: {e}")
        raise

async def perform_maintenance_operations(config: Config, category_manager: CategoryManager):
    """Handle maintenance operations with proper prompts."""
    operations = [
        ("Re-review existing items?", lambda: reprocess_existing_items(config.knowledge_base_dir, category_manager)),
        ("Regenerate root README?", lambda: generate_root_readme(config.knowledge_base_dir, category_manager)),
        ("Push changes to GitHub?", lambda: push_to_github(
            knowledge_base_dir=config.knowledge_base_dir,
            github_repo_url=config.github_repo_url,
            github_token=config.github_token,
            git_user_name=config.github_user_name,
            git_user_email=config.github_user_email
        ))
    ]

    for prompt, operation in operations:
        if prompt_yes_no(prompt):
            try:
                operation()
            except Exception as e:
                logging.error(f"Operation failed: {e}")
                print(f"Operation failed: {e}")

def prompt_yes_no(question: str) -> bool:
    """Standardized yes/no prompt."""
    return input(f"{question} (y/n): ").strip().lower() == 'y'

if __name__ == "__main__":
    asyncio.run(main_async())
