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
    knowledge base folder exists. Returns a new dictionary containing only valid entries.
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

async def process_tweet(tweet_url: str, config: Config, category_manager: CategoryManager,
                        http_client: requests.Session, tweet_cache: dict) -> None:
    tweet_id = parse_tweet_id_from_url(tweet_url)
    if not tweet_id:
        logging.warning(f"Invalid tweet URL skipped: {tweet_url}")
        return

    # Check if this tweet is already cached.
    cached_data = get_cached_tweet(tweet_id, tweet_cache)
    if cached_data:
        logging.info(f"Using cached data for tweet {tweet_id}")
        tweet_data = cached_data
    else:
        logging.info(f"Fetching tweet data for tweet {tweet_id}")
        try:
            tweet_data = await fetch_tweet_data_playwright(tweet_id)
            # Initialize downloaded_media as empty list.
            tweet_data["downloaded_media"] = []
            update_cache(tweet_id, tweet_data, tweet_cache)
            save_cache(tweet_cache)  # persist the new cache entry
        except Exception as e:
            logging.error(f"Failed to fetch tweet data for {tweet_id}: {e}")
            return

    # Process media:
    image_descriptions = []
    image_files = []

    # Check if we already have downloaded media in cache.
    downloaded_media = tweet_data.get("downloaded_media", [])
    if downloaded_media:
        logging.info(f"Found {len(downloaded_media)} cached media files for tweet {tweet_id}.")
        for file_path_str in downloaded_media:
            local_img_path = Path(file_path_str)
            image_files.append(local_img_path)
            try:
                desc = interpret_image(config.ollama_url, local_img_path, config.vision_model,
                                       http_client=http_client)
                image_descriptions.append(desc)
            except Exception as e:
                logging.error(f"Error re-interpreting cached image {local_img_path} for tweet {tweet_id}: {e}")
    else:
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
                desc = interpret_image(config.ollama_url, local_img_path, config.vision_model,
                                       http_client=http_client)
                image_descriptions.append(desc)
                image_files.append(local_img_path)
            except Exception as e:
                logging.error(f"Error processing image {image_url} for tweet {tweet_id}: {e}")
                continue

        # Update cache with the local paths for downloaded media.
        downloaded_paths = [str(path.resolve()) for path in image_files]
        tweet_data["downloaded_media"] = downloaded_paths
        update_cache(tweet_id, tweet_data, tweet_cache)
        save_cache(tweet_cache)

    tweet_text = tweet_data.get("full_text", "")
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
        logging.error(f"Failed to categorize tweet {tweet_id}: {e}")
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
        logging.error(f"Failed to write markdown for tweet {tweet_id}: {e}")
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
    # Prompt to update bookmarks.
    update_bookmarks_choice = input("Do you want to update bookmarks? (y/n): ").strip().lower()
    if update_bookmarks_choice == 'y':
        print("Updating bookmarks...")
        try:
            await scrape_x_bookmarks()
            print("Bookmarks updated successfully.")
        except Exception as e:
            logging.error(f"Error updating bookmarks: {e}")
            print("An error occurred while updating bookmarks. Proceeding with existing bookmarks.")

    # Load the existing tweet cache.
    tweet_cache = load_cache()
    rebuild_choice = input("Do you want to rebuild the tweet cache (force re-fetch all tweet data)? (y/n): ").strip().lower()
    if rebuild_choice == 'y':
        clear_cache()
        tweet_cache = {}  # start with an empty cache
        print("Tweet cache cleared.")
    else:
        print(f"Using cached data for {len(tweet_cache)} tweets if available.")

    setup_logging()
    config = Config.from_env()
    try:
        config.verify()
    except Exception as e:
        logging.error(f"Configuration error: {e}")
        return

    category_manager = CategoryManager(config.categories_file)
    processed_tweets = load_processed_tweets(config.processed_tweets_file)
    # Validate that processed tweets have corresponding KB items.
    processed_tweets = validate_processed_items(processed_tweets, config.knowledge_base_dir)
    
    tweet_urls = load_tweet_urls_from_links(config.bookmarks_file)
    total_urls = len(tweet_urls)
    already_processed_count = sum(1 for url in tweet_urls if parse_tweet_id_from_url(url) in processed_tweets)
    not_processed_count = total_urls - already_processed_count

    print(f"Total tweet URLs found in bookmarks: {total_urls}")
    print(f"Tweets already processed: {already_processed_count}")
    print(f"Tweets not yet processed: {not_processed_count}")

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

    if tweet_urls:
        logging.info(f"Starting processing of {len(tweet_urls)} tweets...")
        http_client = create_http_client()
        tasks = [process_tweet(url, config, category_manager, http_client, tweet_cache)
                 for url in tweet_urls]
        await asyncio.gather(*tasks)
        print("All tweets have been processed.")
    else:
        print("No new tweet URLs to process.")

    user_choice = input("Do you want to re-review existing knowledge base items for improved categorization? (y/n): ").strip().lower()
    if user_choice == 'y':
        reprocess_existing_items(config.knowledge_base_dir, category_manager)

    regenerate_readme = input("Do you want to regenerate the root README? (y/n): ").strip().lower()
    if regenerate_readme == 'y':
        generate_root_readme(config.knowledge_base_dir, category_manager)
        print("Root README regenerated.")
    else:
        print("Skipping regeneration of the root README.")

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

def validate_processed_items(processed_tweets: dict, knowledge_base_dir: Path) -> dict:
    """
    Validate that for each tweet in the processed state, the corresponding knowledge base item folder exists.
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
                logging.warning(f"Processed tweet {tweet_id} is in state but folder {item_folder} does not exist.")
        else:
            logging.warning(f"Processed tweet {tweet_id} missing required metadata.")
    return valid_state

async def main_async():
    # Prompt to update bookmarks.
    update_bookmarks_choice = input("Do you want to update bookmarks? (y/n): ").strip().lower()
    if update_bookmarks_choice == 'y':
        print("Updating bookmarks...")
        try:
            await scrape_x_bookmarks()
            print("Bookmarks updated successfully.")
        except Exception as e:
            logging.error(f"Error updating bookmarks: {e}")
            print("An error occurred while updating bookmarks. Proceeding with existing bookmarks.")

    # Load the existing tweet cache.
    tweet_cache = load_cache()
    rebuild_choice = input("Do you want to rebuild the tweet cache (force re-fetch all tweet data)? (y/n): ").strip().lower()
    if rebuild_choice == 'y':
        clear_cache()
        tweet_cache = {}  # start with an empty cache
        print("Tweet cache cleared.")
    else:
        print(f"Using cached data for {len(tweet_cache)} tweets if available.")

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

    if tweet_urls:
        logging.info(f"Starting processing of {len(tweet_urls)} tweets...")
        http_client = create_http_client()
        tasks = [process_tweet(url, config, category_manager, http_client, tweet_cache)
                 for url in tweet_urls]
        await asyncio.gather(*tasks)
        print("All tweets have been processed.")
    else:
        print("No new tweet URLs to process.")

    user_choice = input("Do you want to re-review existing knowledge base items for improved categorization? (y/n): ").strip().lower()
    if user_choice == 'y':
        reprocess_existing_items(config.knowledge_base_dir, category_manager)

    regenerate_readme = input("Do you want to regenerate the root README? (y/n): ").strip().lower()
    if regenerate_readme == 'y':
        generate_root_readme(config.knowledge_base_dir, category_manager)
        print("Root README regenerated.")
    else:
        print("Skipping regeneration of the root README.")

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
