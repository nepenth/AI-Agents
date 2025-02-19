import asyncio
import logging
import re
from playwright.async_api import async_playwright, Page, Browser, TimeoutError as PlaywrightTimeout
from knowledge_base_agent.exceptions import KnowledgeBaseError, FetchError
from typing import Dict, Any, Optional, List
from pathlib import Path
import aiohttp
from knowledge_base_agent.config import Config

def get_high_res_url(url: str) -> str:
    """
    Convert a Twitter media URL to request the highest available resolution.
    For example, if the URL contains 'name=small' or 'name=900x900', replace it with 'name=orig'.
    """
    if "name=" in url:
        return re.sub(r"name=\w+", "name=orig", url)
    return url

async def fetch_tweet_data_playwright(tweet_url: str, config: Config) -> Dict[str, Any]:
    """Fetch tweet data using Playwright."""
    try:
        logging.info(f"Starting Playwright fetch for tweet {tweet_url}")
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            
            logging.info(f"Navigating to {tweet_url}")
            
            # Set shorter timeout for navigation
            await page.goto(tweet_url, timeout=30000)
            
            # Wait for content with shorter timeout
            tweet_selector = 'article div[data-testid="tweetText"]'
            logging.info("Waiting for tweet content...")
            try:
                await page.wait_for_selector(tweet_selector, timeout=10000)  # 10 second timeout
            except Exception as e:
                logging.warning(f"Timeout waiting for tweet content: {e}")
                return {"full_text": "", "media": [], "downloaded_media": [], "image_descriptions": [], "urls": []}
            
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
            logging.info(f"Successfully fetched tweet {tweet_url}")
            
            tweet_data = {
                "full_text": tweet_text,
                "media": image_urls,
                "downloaded_media": [],
                "image_descriptions": [],
                "urls": []  # Initialize urls list
            }

            # Extract URLs from tweet text using regex
            url_pattern = r'https?://[^\s<>"]+|www\.[^\s<>"]+' 
            found_urls = re.findall(url_pattern, tweet_text)
            if found_urls:
                tweet_data['urls'] = found_urls
                logging.info(f"Found URLs in tweet: {found_urls}")

            return tweet_data
            
    except Exception as e:
        logging.error(f"Error in Playwright fetch for tweet {tweet_url}: {e}")
        raise

class PlaywrightFetcher:
    """Handles tweet data fetching using Playwright."""
    
    def __init__(self, config: Config):
        self.config = config
        self.browser: Optional[Browser] = None
        self.page: Optional[Page] = None
        self._lock = asyncio.Lock()  # Ensure single concurrent fetch
        
    async def __aenter__(self):
        """Initialize browser for context manager."""
        await self.initialize()
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Cleanup browser resources."""
        await self.cleanup()

    async def initialize(self) -> None:
        """Initialize Playwright browser."""
        try:
            playwright = await async_playwright().start()
            self.browser = await playwright.chromium.launch(headless=True)
            self.page = await self.browser.new_page()
            await self.page.set_viewport_size({"width": 1280, "height": 1024})
        except Exception as e:
            logging.error(f"Failed to initialize Playwright: {e}")
            raise FetchError(f"Playwright initialization failed: {e}")

    async def cleanup(self) -> None:
        """Clean up Playwright resources."""
        try:
            if self.page:
                await self.page.close()
            if self.browser:
                await self.browser.close()
        except Exception as e:
            logging.error(f"Failed to cleanup Playwright resources: {e}")

    async def fetch_tweet_data(self, tweet_url: str) -> Dict[str, Any]:
        """
        Fetch tweet data including text and media URLs.
        
        Args:
            tweet_url: URL of the tweet to fetch
            
        Returns:
            Dict containing tweet text and media information
        """
        async with self._lock:  # Ensure single concurrent fetch
            try:
                await self.page.goto(tweet_url, wait_until="networkidle")
                
                # Wait for tweet content
                await self.page.wait_for_selector('article[data-testid="tweet"]', timeout=30000)
                
                # Get tweet text
                text_element = await self.page.query_selector('div[data-testid="tweetText"]')
                tweet_text = await text_element.inner_text() if text_element else ""
                
                # Get media items
                media_elements = await self.page.query_selector_all('img[src*="/media/"]')
                media_urls = []
                
                for media in media_elements:
                    src = await media.get_attribute('src')
                    if src and not src.endswith(('thumb', 'small')):
                        media_urls.append(src)
                
                return {
                    "full_text": tweet_text,
                    "media": media_urls,
                    "downloaded_media": [],  # Will be populated during media download
                    "urls": []  # Initialize urls list
                }
                
            except PlaywrightTimeout:
                raise FetchError(f"Timeout while fetching tweet {tweet_url}")
            except Exception as e:
                raise FetchError(f"Failed to fetch tweet {tweet_url}: {e}")

async def fetch_tweet_data_playwright(tweet_url: str, config: Config) -> Dict[str, Any]:
    """
    Convenience function to fetch tweet data using PlaywrightFetcher.
    
    Args:
        tweet_url: URL of the tweet to fetch
        config: Config instance containing settings
        
    Returns:
        Dict containing tweet text and media information
    """
    async with PlaywrightFetcher(config) as fetcher:
        return await fetcher.fetch_tweet_data(tweet_url)

async def download_media_playwright(
    media_urls: List[str],
    tweet_id: str,
    media_cache_dir: Path
) -> List[Path]:
    """
    Download media files from URLs to cache directory.
    
    Args:
        media_urls: List of media URLs to download
        tweet_id: ID of the tweet (for filename)
        media_cache_dir: Directory to store downloaded media
        
    Returns:
        List of paths to downloaded media files
    """
    media_cache_dir.mkdir(parents=True, exist_ok=True)
    downloaded_paths = []
    
    async with aiohttp.ClientSession() as session:
        for i, url in enumerate(media_urls):
            try:
                filename = f"{tweet_id}_media_{i}{Path(url).suffix}"
                media_path = media_cache_dir / filename
                
                if media_path.exists():
                    downloaded_paths.append(media_path)
                    continue
                    
                async with session.get(url) as response:
                    if response.status == 200:
                        content = await response.read()
                        media_path.write_bytes(content)
                        downloaded_paths.append(media_path)
                        
            except Exception as e:
                logging.error(f"Failed to download media from {url}: {e}")
                continue
                
    return downloaded_paths
    