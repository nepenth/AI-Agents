import asyncio
import logging
import re
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError
from knowledge_base_agent.exceptions import KnowledgeBaseError
from typing import Dict, Any

def get_high_res_url(url: str) -> str:
    """
    Convert a Twitter media URL to request the highest available resolution.
    For example, if the URL contains 'name=small' or 'name=900x900', replace it with 'name=orig'.
    """
    if "name=" in url:
        return re.sub(r"name=\w+", "name=orig", url)
    return url

async def fetch_tweet_data_playwright(tweet_id: str, timeout: int = 30000) -> Dict[str, Any]:
    """Fetch tweet data using Playwright."""
    try:
        logging.info(f"Starting Playwright fetch for tweet {tweet_id}")
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            
            url = f"https://twitter.com/i/web/status/{tweet_id}"
            logging.info(f"Navigating to {url}")
            
            # Set shorter timeout for navigation
            await page.goto(url, timeout=timeout)
            
            # Wait for content with shorter timeout
            tweet_selector = 'article div[data-testid="tweetText"]'
            logging.info("Waiting for tweet content...")
            try:
                await page.wait_for_selector(tweet_selector, timeout=10000)  # 10 second timeout
            except Exception as e:
                logging.warning(f"Timeout waiting for tweet content: {e}")
                return {"full_text": "", "media": [], "downloaded_media": [], "image_descriptions": []}
            
            # Get tweet text with timeout
            try:
                tweet_text = await page.locator(tweet_selector).first.inner_text(timeout=5000)
            except Exception as e:
                logging.warning(f"Failed to get tweet text: {e}")
                tweet_text = ""
            
            # Get images with timeout
            image_urls = []
            try:
                images = await page.locator('article img[src*="/media/"]').all()
                for img in images:
                    src = await img.get_attribute('src', timeout=5000)
                    if src:
                        image_urls.append(src)
            except Exception as e:
                logging.warning(f"Failed to get images: {e}")
            
            await browser.close()
            logging.info(f"Successfully fetched tweet {tweet_id}")
            
            return {
                "full_text": tweet_text,
                "media": image_urls,
                "downloaded_media": [],
                "image_descriptions": []
            }
            
    except Exception as e:
        logging.error(f"Error in Playwright fetch for tweet {tweet_id}: {e}")
        return {
            "full_text": "",
            "media": [],
            "downloaded_media": [],
            "image_descriptions": []
        }
    