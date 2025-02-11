import asyncio
import logging
import re
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError
from knowledge_base_agent.exceptions import KnowledgeBaseError

def get_high_res_url(url: str) -> str:
    """
    Convert a Twitter media URL to request the highest available resolution.
    For example, if the URL contains 'name=small' or 'name=900x900', replace it with 'name=orig'.
    """
    if "name=" in url:
        return re.sub(r"name=\w+", "name=orig", url)
    return url

async def fetch_tweet_data_playwright(tweet_id: str) -> dict:
    tweet_url = f"https://x.com/i/status/{tweet_id}"
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context()
            page = await context.new_page()
            await page.goto(tweet_url, timeout=60000, wait_until="networkidle")
            await page.wait_for_selector('article div[data-testid="tweetText"]', timeout=30000)
            tweet_text_elements = await page.query_selector_all('article div[data-testid="tweetText"]')
            tweet_text = " ".join([await el.inner_text() for el in tweet_text_elements])

            media_urls = []
            # Process image elements
            image_elements = await page.query_selector_all('article div[data-testid="tweetPhoto"] img')
            for media in image_elements:
                src = await media.get_attribute('src')
                if src:
                    high_res_src = get_high_res_url(src)
                    media_urls.append(high_res_src)
            # Process video elements (and potentially GIFs)
            video_elements = await page.query_selector_all('article video')
            for media in video_elements:
                src = await media.get_attribute('src')
                if src:
                    high_res_src = get_high_res_url(src)
                    media_urls.append(high_res_src)

            # Attempt to capture replies
            replies = []
            try:
                await page.wait_for_selector('div[data-testid="reply"]', timeout=30000)
                reply_elements = await page.query_selector_all('div[data-testid="reply"]')
                for reply in reply_elements[:10]:
                    reply_text_elements = await reply.query_selector_all('div[data-testid="tweetText"]')
                    reply_text = " ".join([await el.inner_text() for el in reply_text_elements])
                    
                    reply_media_urls = []
                    # Check for images in the reply
                    reply_image_elements = await reply.query_selector_all('img')
                    for img in reply_image_elements:
                        src = await img.get_attribute('src')
                        if src:
                            high_res_src = get_high_res_url(src)
                            reply_media_urls.append(high_res_src)
                    # Check for video/GIF elements in the reply
                    reply_video_elements = await reply.query_selector_all('video')
                    for video in reply_video_elements:
                        src = await video.get_attribute('src')
                        if src:
                            high_res_src = get_high_res_url(src)
                            reply_media_urls.append(high_res_src)
                    
                    replies.append({
                        "reply_text": reply_text,
                        "media_urls": reply_media_urls
                    })
                replies = replies[:10]
            except PlaywrightTimeoutError:
                logging.info(f"No replies found for tweet {tweet_id} within timeout; proceeding with empty replies.")
                replies = []

            await browser.close()

        return {
            "full_text": tweet_text,
            "extended_media": [{"media_url_https": url} for url in media_urls],
            "replies": replies
        }
    except PlaywrightTimeoutError as e:
        logging.error(f"Timeout error fetching tweet {tweet_id}: {e}")
        raise KnowledgeBaseError(f"Timeout fetching tweet {tweet_id}") from e
    except Exception as e:
        logging.error(f"Playwright failed for Tweet ID {tweet_id}: {e}")
        raise KnowledgeBaseError(f"Failed to fetch tweet data for ID {tweet_id}") from e
    