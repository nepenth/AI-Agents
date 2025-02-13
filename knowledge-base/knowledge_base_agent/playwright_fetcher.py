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

async def fetch_tweet_data_playwright(tweet_id: str, timeout: int = 60000) -> Dict[str, Any]:
    """Fetch tweet data using Playwright."""
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            
            # Go to tweet URL
            await page.goto(f"https://twitter.com/i/web/status/{tweet_id}", wait_until="networkidle")
            
            # Wait for tweet content with increased timeout
            tweet_selector = 'article div[data-testid="tweetText"]'
            await page.wait_for_selector(tweet_selector, timeout=timeout)
            
            # Get first matching tweet text element
            tweet_text = await page.locator(tweet_selector).first.inner_text()
            
            # Get images if any
            images = await page.locator('article img[src*="/media/"]').all()
            image_urls = []
            for img in images:
                src = await img.get_attribute('src')
                if src:
                    image_urls.append(src)
            
            await browser.close()
            
            return {
                "full_text": tweet_text,
                "extended_media": [{"media_url_https": url} for url in image_urls]
            }
            
    except Exception as e:
        logging.error(f"Error fetching tweet {tweet_id}: {e}")
        raise
    