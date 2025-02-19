import asyncio
import logging
import re
from playwright.async_api import async_playwright, Page, Browser, TimeoutError as PlaywrightTimeout
from knowledge_base_agent.exceptions import KnowledgeBaseError, FetchError
from typing import Dict, Any, Optional, List
from pathlib import Path
import aiohttp
from knowledge_base_agent.config import Config

async def expand_url(url: str) -> str:
    """Expand t.co URLs to their final destination."""
    if not url.startswith("https://t.co/"):
        return url
    async with aiohttp.ClientSession() as session:
        try:
            async with session.head(url, allow_redirects=True) as response:
                return str(response.url)
        except Exception as e:
            logging.warning(f"Could not expand {url}: {e}")
            return url

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
    # Ensure proper URL format
    if tweet_url.isdigit():
        tweet_url = f"https://twitter.com/i/web/status/{tweet_url}"
        
    try:
        logging.info(f"Starting Playwright fetch for tweet {tweet_url}")
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            
            await page.goto(tweet_url, timeout=30000)
            
            # Wait for content with shorter timeout
            tweet_selector = 'article div[data-testid="tweetText"]'
            logging.info("Waiting for tweet content...")
            try:
                await page.wait_for_selector(tweet_selector, timeout=10000)  # 10 second timeout
            except Exception as e:
                logging.warning(f"Timeout waiting for tweet content: {e}")
                return {"full_text": "", "media": [], "downloaded_media": [], "image_descriptions": [], "urls": []}
            
            # Extract text content
            text_element = await page.wait_for_selector('article div[data-testid="tweetText"]', timeout=10000)
            text = await text_element.inner_text() if text_element else ""

            # Extract media with multiple selectors
            media_urls = []
            
            # Look for all types of tweet images (added 'article picture img')
            image_selectors = [
                'article img[src*="https://pbs.twimg.com/media/"]',
                'article [data-testid="tweetPhoto"] img',
                'article div[data-testid="tweet"] img[src*="/media/"]',
                'article picture img'  # Newly added to catch images within <picture> elements
            ]
            
            for selector in image_selectors:
                images = await page.query_selector_all(selector)
                for img in images:
                    src = await img.get_attribute('src')
                    if src and not src.endswith('profile_images'):
                        high_quality_url = re.sub(r'\?.*$', '?format=jpg&name=large', src)
                        if high_quality_url not in media_urls:  # Avoid duplicates
                            media_urls.append(high_quality_url)
                            logging.info(f"Found media URL: {high_quality_url}")

            # Extract URLs - both from link elements and from tweet inner HTML
            found_urls = []
            
            # Get URLs from link elements (use expand_url for t.co links)
            link_elements = await page.query_selector_all('article a[role="link"]')
            for link in link_elements:
                href = await link.get_attribute('href')
                if href and href.startswith('http'):
                    if href.startswith("https://t.co/"):
                        href = await expand_url(href)
                    if href not in found_urls:
                        found_urls.append(href)
                        logging.info(f"Found URL from anchor: {href}")

            # Additional extraction from tweet inner HTML (to catch any missed links)
            tweet_html = await page.inner_html('article div[data-testid="tweetText"]')
            html_urls = re.findall(r'href="(https?://[^"]+)"', tweet_html)
            for href in html_urls:
                if href.startswith("https://t.co/"):
                    href = await expand_url(href)
                if href not in found_urls:
                    found_urls.append(href)
                    logging.info(f"Found URL from tweet HTML: {href}")

            tweet_data = {
                'full_text': text,
                'media': media_urls,
                'urls': found_urls,
                'downloaded_media': [],
                'tweet_url': tweet_url,
                'cache_complete': False
            }

            logging.info(f"Found {len(media_urls)} media items and {len(found_urls)} URLs")
            return tweet_data
            
    except Exception as e:
        logging.error(f"Failed to fetch tweet data: {e}")
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
    