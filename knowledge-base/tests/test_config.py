import asyncio
import datetime
import logging
from pathlib import Path
from knowledge_base_agent.config import Config
from logging_setup import setup_logging
from category_manager import CategoryManager
from tweet_utils import load_tweet_urls_from_links, parse_tweet_id_from_url
from playwright_fetcher import fetch_tweet_data_playwright
from image_interpreter import interpret_image
from ai_categorization import categorize_and_name_content
from markdown_writer import write_tweet_markdown, generate_root_readme, clean_text_for_categorization
from state_manager import load_processed_tweets, save_processed_tweets
from cleanup import delete_knowledge_base_item, clean_untitled_directories
from git_helper import push_to_github
from reprocess import reprocess_existing_items

def main():
    setup_logging()
    config = Config.from_env()
    try:
        config.verify()
    except Exception as e:
        logging.error(f"Configuration error: {e}")
        return

    category_manager = CategoryManager(config.categories_file)
    processed_tweets = load_processed_tweets(config.processed_tweets_file)

    user_input = input(
        f"Found {len(processed_tweets)} previously processed tweets. Reprocess them from scratch? (y/n): "
    ).strip().lower()
    if user_input == 'y':
        for tweet_id in list(processed_tweets.keys()):
            delete_knowledge_base_item(tweet_id, processed_tweets, config.knowledge_base_dir)
            del processed_tweets[tweet_id]
        save_processed_tweets(config.processed_tweets_file, processed_tweets)
        print("All previously processed tweets will be reprocessed from scratch.")
    else:
        print("Skipping reprocessing of previously processed tweets.")

    clean_untitled_directories(config.knowledge_base_dir)
    tweet_urls = load_tweet_urls_from_links(config.bookmarks_file)
    if not tweet_urls:
        print("No valid tweet URLs found. Exiting.")
        return

    print(f"Starting processing of {len(tweet_urls)} tweets...\n")
    for idx, tweet_url in enumerate(tweet_urls, start=1):
        tweet_id = parse_tweet_id_from_url(tweet_url)
        if not tweet_id:
            print(f"Skipping invalid tweet URL: {tweet_url}")
            continue
        if tweet_id in processed_tweets:
            print(f"Skipping already processed tweet ID {tweet_id}.\n")
            continue

        print(f"Processing tweet #{idx}: ID {tweet_id}")
        try:
            tweet_data = asyncio.run(fetch_tweet_data_playwright(tweet_id))
            if not tweet_data:
                print(f"Skipping tweet ID {tweet_id} due to missing data.\n")
                continue

            tweet_text = tweet_data.get("full_text", "")
            extended_media = tweet_data.get("extended_media", [])
            image_descriptions = []
            image_files = []
            for i, media_obj in enumerate(extended_media):
                image_url = media_obj.get("media_url_https")
                if not image_url:
                    continue
                local_img_path = Path(f"temp_image_{i}.jpg")
                try:
                    import requests
                    resp = requests.get(image_url, stream=True, timeout=60)
                    resp.raise_for_status()
                    with local_img_path.open("wb") as f:
                        for chunk in resp.iter_content(chunk_size=8192):
                            f.write(chunk)
                    from PIL import Image
                    with Image.open(local_img_path) as img:
                        if img.format not in ['JPEG', 'PNG']:
                            raise ValueError(f"Invalid image format: {img.format}")
                    print(f"Downloaded image {i+1}: {image_url}")
                    desc = interpret_image(config.ollama_url, local_img_path, config.vision_model)
                    image_descriptions.append(desc)
                    image_files.append(local_img_path)
                except Exception as e:
                    logging.error(f"Error processing image {image_url}: {e}")
                    continue

            combined_text = clean_text_for_categorization(tweet_text)
            if tweet_text:
                combined_text += f"\nTweet text: {tweet_text}\n\n"
            for idx_img, desc in enumerate(image_descriptions):
                combined_text += f"Image {idx_img+1} interpretation: {desc}\n\n"

            main_category, sub_category, item_name = asyncio.run(
                categorize_and_name_content(
                    config.ollama_url, combined_text, config.text_model, tweet_id, category_manager
                )
            )

            write_tweet_markdown(
                root_dir=config.knowledge_base_dir,
                tweet_id=tweet_id,
                main_category=main_category,
                sub_category=sub_category,
                item_name=item_name,
                tweet_text=tweet_text,
                image_files=image_files,
                image_descriptions=image_descriptions,
                tweet_url=tweet_url
            )

            processed_tweets[tweet_id] = {
                "item_name": item_name,
                "main_category": main_category,
                "sub_category": sub_category,
                "timestamp": datetime.datetime.now().isoformat()
            }
            print(f"Successfully processed tweet #{idx} => {main_category}/{sub_category}/{item_name}\n")
        except Exception as e:
            logging.error(f"Unexpected error processing tweet ID {tweet_id}: {e}")
            print(f"Unexpected error processing tweet ID {tweet_id}: {e}\n")

    save_processed_tweets(config.processed_tweets_file, processed_tweets)
    print("All tweets have been processed.\n")

    user_input = input("Do you want to re-review existing knowledge base items for improved categorization? (y/n): ").strip().lower()
    if user_input == 'y':
        reprocess_existing_items(config.knowledge_base_dir, category_manager)

    generate_root_readme(config.knowledge_base_dir, category_manager)

    if config.github_token:
        push_to_github(
            knowledge_base_dir=config.knowledge_base_dir,
            github_repo_url=config.github_repo_url,
            github_token=config.github_token,
            git_user_name=config.github_user_name,
            git_user_email=config.github_user_email
        )
    else:
        print("GitHub token not found. Skipping GitHub push.")

if __name__ == "__main__":
    main()
