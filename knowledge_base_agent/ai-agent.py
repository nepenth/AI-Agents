import asyncio
from config import config
from categorizer import categorize_and_name_content
from utils import load_json_file, save_json_file, delete_directory, safe_directory_name, format_links_in_text
from playwright.async_api import async_playwright
import shutil
import uuid
from pathlib import Path

def write_tweet_markdown(
    root_dir: Path,
    tweet_id: str,
    main_category: str,
    sub_category: str,
    item_name: str,
    tweet_text: str,
    image_files: list,
    image_descriptions: list,
    tweet_url: str
):
    safe_item_name = safe_directory_name(item_name)
    tweet_folder = root_dir / main_category / sub_category / safe_item_name
    temp_folder = tweet_folder.with_suffix('.temp')
    temp_folder.mkdir(parents=True, exist_ok=True)

    try:
        formatted_tweet_text = format_links_in_text(tweet_text)
        lines = [
            f"# {item_name}",
            f"**Tweet URL:** [{tweet_url}]({tweet_url})",
            f"**Tweet Text:** {formatted_tweet_text}",
            ""
        ]
        for i, desc in enumerate(image_descriptions):
            img_name = f"image_{i+1}.jpg"
            lines.append(f"**Image {i+1} Description:** {desc}")
            lines.append(f"![Image {i+1}](./{img_name})")
            lines.append("")

        content_md_path = temp_folder / "content.md"
        content_md_path.write_text("\n".join(lines), encoding="utf-8")

        for i, img_path in enumerate(image_files):
            if img_path.exists():
                shutil.copy2(img_path, temp_folder / f"image_{i+1}.jpg")

        temp_folder.rename(tweet_folder)

    except Exception as e:
        shutil.rmtree(temp_folder)
        raise RuntimeError(f"Failed to write tweet markdown: {e}")

async def fetch_tweet_data_playwright(tweet_id: str) -> dict:
    """Fetches tweet text and media using Playwright."""
    tweet_url = f"https://x.com/i/status/{tweet_id}"
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context()
            page = await context.new_page()
            await page.goto(tweet_url, timeout=60000)
            await page.wait_for_selector('article div[data-testid="tweetText"]', timeout=30000)
            tweet_text_elements = await page.query_selector_all('article div[data-testid="tweetText"]')
            tweet_text = " ".join([await el.inner_text() for el in tweet_text_elements])

            media_urls = []
            image_elements = await page.query_selector_all('article div[data-testid="tweetPhoto"] img')
            for media in image_elements:
                src = await media.get_attribute('src')
                if src:
                    media_urls.append(src)

            await browser.close()

        return {"full_text": tweet_text, "extended_media": [{"media_url_https": url} for url in media_urls]}
    except Exception as e:
        return {"error": f"Playwright error: {e}"}

async def reprocess_existing_items():
    """ Allows users to reprocess existing knowledge base items with AI refinement. """
    print("\n=== Reprocessing Existing Knowledge Base Items ===")

    processed_tweets = load_json_file(config.processed_tweets_file)

    for tweet_id, entry in processed_tweets.items():
        print(f"\nExisting Item: {entry['main_category']}/{entry['sub_category']}/{entry['item_name']}")
        user_input = input("Reprocess this entry for better categorization/title? (y/n): ").strip().lower()
        if user_input == 'y':
            prompt_text = config.agent_prompt_reprocess.replace("{content}", entry['tweet_text'])

            response = requests.post(
                f"{config.ollama_url}/api/generate",
                json={"prompt": prompt_text, "model": config.text_model, "stream": False},
                timeout=120
            )
            response.raise_for_status()
            new_response = response.json().get("response", "").strip()
            new_main_cat, new_sub_cat, new_item_name = new_response.split('|')

            print(f"\nNew Suggestion => Category: {new_main_cat}/{new_sub_cat}, Title: {new_item_name}")
            confirm = input("Apply this re-categorization? (y/n): ").strip().lower()
            if confirm == 'y':
                delete_directory(config.knowledge_base_dir / entry["main_category"] / entry["sub_category"] / entry["item_name"])
                processed_tweets[tweet_id] = {"main_category": new_main_cat, "sub_category": new_sub_cat, "item_name": new_item_name}
                save_json_file(config.processed_tweets_file, processed_tweets)

async def main():
    """ Main async function to process and optionally reprocess content. """
    processed_tweets = load_json_file(config.processed_tweets_file)

    # Process New Tweets
    print("Processing tweets...")
    for tweet in load_json_file(config.bookmarks_file).get("tweets", []):
        tweet_id = tweet.get("id_str")
        if tweet_id in processed_tweets:
            continue
        main_category, sub_category, item_name = await categorize_and_name_content(tweet["full_text"], tweet_id)
        processed_tweets[tweet_id] = {"main_category": main_category, "sub_category": sub_category, "item_name": item_name}
        save_json_file(config.processed_tweets_file, processed_tweets)

    # Offer Reprocessing
    if input("\nReprocess existing knowledge base items? (y/n): ").strip().lower() == 'y':
        await reprocess_existing_items()

if __name__ == "__main__":
    asyncio.run(main())
