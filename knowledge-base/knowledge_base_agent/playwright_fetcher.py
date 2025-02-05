import asyncio
import logging
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError
from .exceptions import KnowledgeBaseError

async def fetch_tweet_data_playwright(tweet_id: str) -> dict:
    tweet_url = f"https://x.com/i/status/{tweet_id}"
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context()
            page = await context.new_page()

            # Navigate to the tweet page.
            await page.goto(tweet_url, timeout=60000)

            # Wait for the main tweet text to load.
            await page.wait_for_selector('article div[data-testid="tweetText"]', timeout=30000)
            tweet_text_elements = await page.query_selector_all('article div[data-testid="tweetText"]')
            tweet_text = " ".join([await el.inner_text() for el in tweet_text_elements])

            # Capture media URLs from the tweet (images, GIFs, and videos).
            media_urls = []
            image_elements = await page.query_selector_all('article div[data-testid="tweetPhoto"] img')
            for media in image_elements:
                src = await media.get_attribute('src')
                if src:
                    media_urls.append(src)
            
            # Capture videos (or GIFs) from the tweet.
            video_elements = await page.query_selector_all('article video')
            for media in video_elements:
                src = await media.get_attribute('src')
                if src:
                    media_urls.append(src)

            # Attempt to capture replies.
            replies = []
            try:
                # Wait for replies to load. If no replies appear, this will timeout.
                await page.wait_for_selector('div[data-testid="reply"]', timeout=30000)
                reply_elements = await page.query_selector_all('div[data-testid="reply"]')
                
                # Limit to top 10 replies.
                for reply in reply_elements[:10]:
                    # Get reply text.
                    reply_text_elements = await reply.query_selector_all('div[data-testid="tweetText"]')
                    reply_text = " ".join([await el.inner_text() for el in reply_text_elements])
                    
                    # Capture media in the reply.
                    reply_media_urls = []
                    # Images in reply.
                    reply_image_elements = await reply.query_selector_all('img')
                    for img in reply_image_elements:
                        src = await img.get_attribute('src')
                        if src:
                            reply_media_urls.append(src)
                    # Videos in reply.
                    reply_video_elements = await reply.query_selector_all('video')
                    for video in reply_video_elements:
                        src = await video.get_attribute('src')
                        if src:
                            reply_media_urls.append(src)
                    
                    replies.append({
                        "reply_text": reply_text,
                        "media_urls": reply_media_urls
                    })
                replies = replies[:10]  # enforce top 10 limit
            except PlaywrightTimeoutError:
                # If waiting for replies times out, assume there are no replies.
                logging.info(f"No replies found for tweet {tweet_id} within timeout; proceeding with empty replies.")
                replies = []

            await browser.close()

        return {
            "full_text": tweet_text,
            "extended_media": [{"media_url_https": url} for url in media_urls],
            "replies": replies
        }
    except Exception as e:
        logging.error(f"Playwright failed for Tweet ID {tweet_id}: {e}")
        raise KnowledgeBaseError(f"Failed to fetch tweet data for ID {tweet_id}") from e
