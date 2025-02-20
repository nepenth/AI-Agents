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
    Also handles card images.
    """
    if "name=" in url:
        return re.sub(r"name=\w+", "name=orig", url)
    elif "card_img" in url:
        return re.sub(r"\?.*$", "?format=jpg&name=orig", url)
    return url

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
        Fetch tweet data including text, media URLs, and links.
        
        Args:
            tweet_url: URL of the tweet to fetch
            
        Returns:
            Dict containing tweet text, media, and URLs
        """
        async with self._lock:  # Ensure single concurrent fetch
            try:
                await self.page.goto(tweet_url, wait_until="networkidle")  # Wait for full load
                
                # Wait for tweet content
                await self.page.wait_for_selector('article[data-testid="tweet"]', timeout=30000)
                
                # Get tweet text
                text_elem = await self.page.query_selector('div[data-testid="tweetText"]') or \
                            await self.page.query_selector('article div[lang]')
                tweet_text = await text_elem.inner_text() if text_elem else ""
                
                # Get media (images, videos, GIFs)
                media = set()
                image_elems = await self.page.query_selector_all('article img[src*="twimg.com"]')
                for img in image_elems:
                    src = await img.get_attribute('src')
                    if src and not any(skip in src.lower() for skip in ['profile_images', 'emoji']):
                        high_quality_url = get_high_res_url(src)
                        media.add((high_quality_url, 'image', await img.get_attribute('alt') or ''))
                
                video_elems = await self.page.query_selector_all('article video[src], article div[data-testid="videoPlayer"] video')
                for video in video_elems:
                    src = await video.get_attribute('src')
                    poster = await video.get_attribute('poster')
                    if src:
                        media.add((src, 'video', ''))
                    if poster:
                        high_quality_poster = get_high_res_url(poster)
                        media.add((high_quality_poster, 'image', ''))
                
                # Get URLs
                url_elems = await self.page.query_selector_all('article a[href^="http"]')
                urls = set()
                for elem in url_elems:
                    href = await elem.get_attribute('href')
                    if href and "status" not in href and "t.co" in href:
                        urls.add(href)
                
                tweet_data = {
                    "full_text": tweet_text,
                    "media": [{"url": url, "type": m_type, "alt_text": alt} for url, m_type, alt in media],
                    "urls": list(urls),
                    "downloaded_media": []  # Will be populated during media download
                }
                logging.info(f"Fetched tweet {tweet_url}: {len(urls)} URLs, {len(media)} media items")
                return tweet_data
                
            except PlaywrightTimeout:
                logging.error(f"Timeout while fetching tweet {tweet_url}")
                raise FetchError(f"Timeout while fetching tweet {tweet_url}")
            except Exception as e:
                logging.error(f"Failed to fetch tweet {tweet_url}: {e}")
                raise FetchError(f"Failed to fetch tweet {tweet_url}: {e}")

async def fetch_tweet_data_playwright(tweet_url: str, config: Config) -> Dict[str, Any]:
    """
    Convenience function to fetch tweet data using PlaywrightFetcher.
    
    Args:
        tweet_url: URL of the tweet to fetch
        config: Config instance containing settings
        
    Returns:
        Dict containing tweet text, media, and URLs
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