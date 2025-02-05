import asyncio
import datetime
import logging
from pathlib import Path
import requests

from knowledge_base_agent.config import Config
from knowledge_base_agent.logging_setup import setup_logging
from knowledge_base_agent.category_manager import CategoryManager
from knowledge_base_agent.tweet_utils import load_tweet_urls_from_links, parse_tweet_id_from_url
from knowledge_base_agent.playwright_fetcher import fetch_tweet_data_playwright
from knowledge_base_agent.image_interpreter import interpret_image
from knowledge_base_agent.ai_categorization import categorize_and_name_content
from knowledge_base_agent.markdown_writer import write_tweet_markdown, generate_root_readme
from knowledge_base_agent.state_manager import load_processed_tweets, save_processed_tweets
from knowledge_base_agent.cleanup import delete_knowledge_base_item, clean_untitled_directories
from knowledge_base_agent.git_helper import push_to_github
from knowledge_base_agent.reprocess import reprocess_existing_items
from knowledge_base_agent.cache_manager import load_cache, save_cache, get_cached_tweet, update_cache, clear_cache
from knowledge_base_agent.http_client import create_http_client
from knowledge_base_agent.fetch_bookmarks import scrape_x_bookmarks

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
    Iterate over the processed tweets state and verify that each tweet's corresponding
    knowledge base item folder exists. Returns a new dictionary containing only valid entries.
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
    Pre-fetch and cache tweet data (including media downloads and image interpretation).
    This function is similar to process_tweet(), but stops before generating the knowledge base item.
    It ensures that tweet data (with high-res media and image descriptions) is stored in the cache.
    """
    tweet_id = parse_tweet_id_from_url(tweet_url)
    if not tweet_id:
        logging.warning(f"Invalid tweet URL skipped during caching: {tweet_url}")
        return

    # If already cached, skip re-fetching.
    if get_cached_tweet(tweet_id, tweet_cache):
        logging.info(f"Tweet {tweet_id} already cached.")
        return

    logging.info(f"Caching data for tweet {tweet_id}")
    try:
        tweet_data = await fetch_tweet_data_playwright(tweet_id)
        tweet_data["downloaded_media"] = []  # initialize downloaded media list
    except Exception as e:
        logging.error(f"Failed to fetch tweet data for caching for {tweet_id}: {e}")
        return

    # Download media and process image data.
    image_descriptions = []
    image_files = []
    extended_media = tweet_data.get("extended_media", [])
    for i, media_obj in enumerate(extended_media):
        image_url = media_obj.get("media_url_https")
        if not image_url:
            continue

        local_img_path = Path(f"temp_image_{tweet_id}_{i}.jpg")
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
            desc = interpret_image(config.ollama_url, local_img_path, config.vision_model, http_client=http_client)
            image_descriptions.append(desc)
            image_files.append(local_img_path)
        except Exception as e:
            logging.error(f"Error processing image {image_url} for tweet {tweet_id}: {e}")
            continue

    downloaded_paths = [str(path.resolve()) for path in image_files]
    tweet_data["downloaded_media"] = downloaded_paths
    # Optionally, you can add image descriptions to the tweet_data if needed.
    tweet_data["image_descriptions"] = image_descriptions

    update_cache(tweet_id, tweet_data, tweet_cache)
    save_cache(tweet_cache)
    logging.info(f"Cached tweet data for {tweet_id}")

async def generate_knowledge_base_item(tweet_url: str, config: Config, category_manager: CategoryManager,
                                       http_client: requests.Session, tweet_cache: dict) -> None:
    """
    Generate the knowledge base item for a tweet using the cached tweet data.
    This function uses the cached tweet data (which should already include media and image descriptions)
    and then performs categorization and Markdown generation.
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
    # Use cached image descriptions if available; otherwise, reprocess media.
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
        write_tweet_markdown(
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

async def main_async():
    # 1. Prompt for bookmarks update.
    update_bookmarks_choice = input("Do you want to update bookmarks? (y/n): ").strip().lower()
    if update_bookmarks_choice == 'y':
        print("Updating bookmarks...")
        try:
            await scrape_x_bookmarks()
            print("Bookmarks updated successfully.")
        except Exception as e:
            logging.error(f"Error updating bookmarks: {e}")
            print("An error occurred while updating bookmarks. Proceeding with existing bookmarks.")

    # 2. Prompt for cache rebuild.
    tweet_cache = load_cache()
    if tweet_cache:
        rebuild_choice = input("Do you want to rebuild the tweet cache (force re-fetch all tweet data)? (y/n): ").strip().lower()
        if rebuild_choice == 'y':
            clear_cache()
            tweet_cache = {}
            print("Tweet cache cleared.")
        else:
            print(f"Using cached data for {len(tweet_cache)} tweets if available.")
    else:
        print("No tweet cache found; proceeding to fetch tweet data.")

    setup_logging()
    config = Config.from_env()
    try:
        config.verify()
    except Exception as e:
        logging.error(f"Configuration error: {e}")
        return

    category_manager = CategoryManager(config.categories_file)
    processed_tweets = load_processed_tweets(config.processed_tweets_file)
    processed_tweets = validate_processed_items(processed_tweets, config.knowledge_base_dir)
    
    tweet_urls = load_tweet_urls_from_links(config.bookmarks_file)
    total_urls = len(tweet_urls)
    already_processed_count = sum(1 for url in tweet_urls if parse_tweet_id_from_url(url) in processed_tweets)
    not_processed_count = total_urls - already_processed_count

    print(f"Total tweet URLs found in bookmarks: {total_urls}")
    print(f"Tweets already processed: {already_processed_count}")
    print(f"Tweets not yet processed: {not_processed_count}")

    # 3. Ask if reprocessing of already processed tweets is desired.
    user_choice = input("Reprocess already processed tweets? (This will delete existing items and re-create them.) (y/n): ").strip().lower()
    if user_choice == 'y':
        print("Reprocessing all tweets: deleting existing items...")
        for tweet_id in list(processed_tweets.keys()):
            delete_knowledge_base_item(tweet_id, processed_tweets, config.knowledge_base_dir)
            del processed_tweets[tweet_id]
        save_processed_tweets(config.processed_tweets_file, processed_tweets)
        print("Existing items deleted. All tweets will be reprocessed.")
    else:
        tweet_urls = filter_new_tweet_urls(tweet_urls, processed_tweets)
        print(f"Processing {len(tweet_urls)} new tweets...")

    # 4. Preprocessing Stage: Cache tweet data (with media & image interpretations) for all tweets.
    if tweet_urls:
        logging.info(f"Starting caching of tweet data for {len(tweet_urls)} tweets...")
        http_client = create_http_client()
        caching_tasks = [cache_tweet_data(url, config, tweet_cache, http_client) for url in tweet_urls]
        await asyncio.gather(*caching_tasks)
        print("Caching of tweet data complete.")
    else:
        print("No new tweet URLs to cache.")

    # 5. Processing Stage: Generate knowledge base items for each tweet using cached data.
    if tweet_urls:
        logging.info(f"Starting knowledge base generation for {len(tweet_urls)} tweets...")
        http_client = create_http_client()
        processing_tasks = [generate_knowledge_base_item(url, config, category_manager, http_client, tweet_cache)
                            for url in tweet_urls]
        await asyncio.gather(*processing_tasks)
        print("Knowledge base generation complete.")
    else:
        print("No tweet URLs to process for knowledge base generation.")

    # 6. Prompt for re-review of existing items for improved categorization.
    review_choice = input("Do you want to re-review existing knowledge base items for improved categorization? (y/n): ").strip().lower()
    if review_choice == 'y':
        reprocess_existing_items(config.knowledge_base_dir, category_manager)

    # 7. Prompt for README regeneration.
    regenerate_readme = input("Do you want to regenerate the root README? (y/n): ").strip().lower()
    if regenerate_readme == 'y' or not (config.knowledge_base_dir / "README.md").exists():
        generate_root_readme(config.knowledge_base_dir, category_manager)
        print("Root README regenerated.")
    else:
        print("Skipping regeneration of the root README.")

    # 8. Prompt for Git sync.
    force_push = input("Do you want to force sync (push) the local knowledge base to GitHub? (y/n): ").strip().lower()
    if force_push == 'y':
        if config.github_token:
            try:
                push_to_github(
                    knowledge_base_dir=config.knowledge_base_dir,
                    github_repo_url=config.github_repo_url,
                    github_token=config.github_token,
                    git_user_name=config.github_user_name,
                    git_user_email=config.github_user_email
                )
                print("Pushed changes to GitHub.")
            except Exception as e:
                logging.error(f"Failed to push changes to GitHub: {e}")
                print("Failed to push changes to GitHub.")
        else:
            print("GitHub token not found. Skipping GitHub push.")
    else:
        print("Skipping GitHub sync.")

def main():
    asyncio.run(main_async())

if __name__ == "__main__":
    main()
