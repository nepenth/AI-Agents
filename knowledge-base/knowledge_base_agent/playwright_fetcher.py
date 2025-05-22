import asyncio
import logging
import re
from playwright.async_api import async_playwright, Page, Browser, TimeoutError as PlaywrightTimeout, ElementHandle
from knowledge_base_agent.exceptions import KnowledgeBaseError, FetchError
from typing import Dict, Any, Optional, List, Tuple, Set
from pathlib import Path
import aiohttp
from knowledge_base_agent.config import Config
from knowledge_base_agent.tweet_utils import parse_tweet_id_from_url

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

    async def _extract_tweet_details_from_article(self, article_element: ElementHandle, is_main_tweet: bool = False) -> Optional[Dict[str, Any]]:
        """Helper function to extract details from a single tweet article element."""
        try:
            tweet_id_element = await article_element.query_selector('a[href*="/status/"]')
            tweet_permalink = await tweet_id_element.get_attribute('href') if tweet_id_element else None
            
            if not tweet_permalink:
                logging.warning("Could not find permalink for a tweet article.")
                return None
            
            # Extract the tweet ID from its permalink
            tweet_id_in_thread = parse_tweet_id_from_url(tweet_permalink)
            if not tweet_id_in_thread:
                 logging.warning(f"Could not parse tweet ID from permalink: {tweet_permalink}")
                 # Fallback: try to find ID in a different way if necessary, or skip
                 # For now, we'll rely on the permalink containing the ID.
                 
            # Extract author handle
            # This selector needs to be robust, e.g., from the user profile link within the tweet
            author_handle_element = await article_element.query_selector('div[data-testid="User-Name"] span:has-text("@")')
            author_handle = await author_handle_element.inner_text() if author_handle_element else "unknown_author"
            author_handle = author_handle.strip('@')


            text_elem = await article_element.query_selector('div[data-testid="tweetText"]') or \
                        await article_element.query_selector('div[lang]') # Broader selector for text
            tweet_text = await text_elem.inner_text() if text_elem else ""

            media_set: Set[Tuple[str, str, str]] = set()
            # Scope image/video search within the current article
            image_elems = await article_element.query_selector_all('img[src*="twimg.com"]')
            for img in image_elems:
                src = await img.get_attribute('src')
                if src and not any(skip in src.lower() for skip in ['profile_images', 'emoji', 'card_img']): # Exclude card_img for now, might be ads
                    high_quality_url = get_high_res_url(src)
                    alt_text = await img.get_attribute('alt') or ""
                    media_set.add((high_quality_url, 'image', alt_text))
            
            video_elems = await article_element.query_selector_all('div[data-testid="videoPlayer"] video') # More specific video selector
            for video in video_elems:
                src = await video.get_attribute('src')
                poster = await video.get_attribute('poster')
                if src: # Actual video file
                    media_set.add((src, 'video', ''))
                elif poster: # Use poster if video src isn't directly available (common for HLS streams)
                    high_quality_poster = get_high_res_url(poster)
                    media_set.add((high_quality_poster, 'image', 'video_poster'))


            url_set: Set[str] = set()
            # Scope link search within the current article
            link_elems = await article_element.query_selector_all('a[href^="http"]')
            for elem in link_elems:
                href = await elem.get_attribute('href')
                # Filter out links to other tweets, user profiles, or known non-content links
                if href and "t.co/" in href and not ("twitter.com/" in href and ("/status/" in href or "/i/web/status/" in href or "/home" in href or "/explore" in href or "/notifications" in href or "/messages" in href)):
                    if not any(x in href for x in ["/analytics", "/i/bookmarks", "/settings", "/logout"]): # more filters
                        url_set.add(href)
            
            # Raw media items for later processing if needed (alt text generation, etc.)
            raw_media_items = [{"url": url, "type": m_type, "alt_text": alt} for url, m_type, alt in media_set]

            return {
                "original_tweet_id_in_thread": tweet_id_in_thread or "unknown", # ID of this specific part of the thread
                "tweet_permalink": tweet_permalink,
                "author_handle": author_handle,
                "full_text": tweet_text.strip(),
                "media_item_details": raw_media_items, # Keep raw details
                "urls": list(url_set), # URLs embedded in this specific tweet part
            }
        except Exception as e:
            logging.error(f"Error extracting details from a tweet article: {e}", exc_info=True)
            return None

    async def fetch_tweet_data(self, tweet_url: str) -> List[Dict[str, Any]]:
        """
        Fetch data for a tweet and its full thread if it's part of one by the original author.
        
        Args:
            tweet_url: URL of the initially bookmarked tweet.
            
        Returns:
            List of dictionaries, where each dictionary contains data for one tweet in the thread.
            The first item is the bookmarked tweet. Returns empty list on failure to fetch main tweet.
        """
        async with self._lock:
            all_thread_tweets_data: List[Dict[str, Any]] = []
            main_tweet_author_handle: Optional[str] = None

            try:
                logging.info(f"Navigating to tweet URL: {tweet_url}")
                await self.page.goto(tweet_url, wait_until="networkidle", timeout=self.config.selenium_timeout * 1000)
                
                # Wait for the main tweet article to ensure it's loaded
                # The main tweet is usually in an article that might be distinct or the first one
                main_tweet_article_selector = 'article[data-testid="tweet"]' # Adjust if X changes this
                await self.page.wait_for_selector(main_tweet_article_selector, timeout=self.config.selenium_timeout * 1000) # Use configured selenium_timeout
                
                # Locate the primary tweet article. This can be tricky if the page shows other tweets above/below.
                # We might need to find the one that matches the tweet_url's ID if possible, or assume the first prominent one.
                # For now, let's assume the first `article[data-testid="tweet"]` is our target.
                # A more robust way would be to find the article whose permalink matches `tweet_url`.
                
                main_article_element = await self.page.query_selector(main_tweet_article_selector)
                if not main_article_element:
                    logging.error(f"Could not find the main tweet article for {tweet_url}")
                    return []

                logging.info("Extracting details from the main tweet...")
                main_tweet_details = await self._extract_tweet_details_from_article(main_article_element, is_main_tweet=True)
                
                if not main_tweet_details:
                    logging.error(f"Failed to extract details from the main tweet at {tweet_url}")
                    return []

                main_tweet_author_handle = main_tweet_details.get("author_handle")
                all_thread_tweets_data.append(main_tweet_details)
                logging.info(f"Fetched main tweet: ID {main_tweet_details.get('original_tweet_id_in_thread')}, Author: {main_tweet_author_handle}")

                # --- Thread Expansion and Fetching ---
                # This is a simplified placeholder. X.com's thread display is complex.
                # Selectors for "Show this thread", "Show more replies" are highly volatile.
                # This part will likely need significant refinement and robust selectors.
                
                # Try to find and click a "Show this thread" or "Show more in this conversation" button
                # These selectors are examples and WILL need verification/adjustment
                thread_expansion_selectors = [
                    'div[data-testid="revealConversationLink"] button',  # Common for "Show this thread"
                    'div[role="button"]:has-text("Show more replies")',
                    'div[role="button"]:has-text("Show more")' 
                    # Add more potential selectors here
                ]
                
                for selector in thread_expansion_selectors:
                    try:
                        expansion_button = await self.page.query_selector(selector)
                        if expansion_button:
                            logging.info(f"Found thread expansion button with selector: {selector}. Clicking...")
                            await expansion_button.click()
                            await self.page.wait_for_timeout(5000) # Wait for content to load after click
                            logging.info("Thread expansion attempted.")
                            break # Stop trying other selectors if one worked
                    except Exception as e:
                        logging.debug(f"Could not click expansion button {selector}: {e}")
                
                # After attempting expansion, or even if no button was found (for short threads already visible)
                # Re-query all tweet articles on the page.
                # The challenge is distinguishing thread replies by the original author from other replies.
                
                all_article_elements = await self.page.query_selector_all('article[data-testid="tweet"]')
                logging.info(f"Found {len(all_article_elements)} tweet articles on the page after potential expansion.")

                processed_article_permalinks = {main_tweet_details["tweet_permalink"]}

                for article_element in all_article_elements:
                    # Skip the main tweet article if it's encountered again
                    temp_permalink_element = await article_element.query_selector('a[href*="/status/"]')
                    temp_permalink = await temp_permalink_element.get_attribute('href') if temp_permalink_element else None
                    
                    if not temp_permalink or temp_permalink in processed_article_permalinks:
                        continue # Already processed or no permalink

                    details = await self._extract_tweet_details_from_article(article_element)
                    if details:
                        # Check if it's by the main author and not already added
                        if details["author_handle"] == main_tweet_author_handle:
                            all_thread_tweets_data.append(details)
                            processed_article_permalinks.add(details["tweet_permalink"])
                            logging.info(f"Added reply to thread: ID {details.get('original_tweet_id_in_thread')}, Author: {details.get('author_handle')}")
                        else:
                            logging.debug(f"Skipping reply by different author: {details.get('author_handle')}")
                
                # Ensure no duplicates and maintain some order (Playwright usually returns in DOM order)
                # A more robust ordering might involve sorting by tweet ID if they are sequential, but DOM order is a good start.
                # The current logic re-adds the main tweet if not careful, `processed_article_permalinks` handles this.


            except PlaywrightTimeout:
                logging.error(f"Timeout while fetching tweet or thread for {tweet_url}")
                # Return whatever was fetched for the main tweet if it succeeded before timeout
                if not all_thread_tweets_data and main_tweet_details: # If main tweet was fetched but thread timed out
                     all_thread_tweets_data.append(main_tweet_details) # Ensure main tweet is returned
                # else, if all_thread_tweets_data is empty, it will be returned as such
            except Exception as e:
                logging.error(f"Failed to fetch tweet/thread for {tweet_url}: {e}", exc_info=True)
                 # Return whatever was fetched for the main tweet if it succeeded
                if not all_thread_tweets_data and main_tweet_details:
                     all_thread_tweets_data.append(main_tweet_details)


            if not all_thread_tweets_data:
                 logging.warning(f"No tweet data could be fetched for {tweet_url}, returning empty list.")
                 return []
            
            # Remove duplicates based on original_tweet_id_in_thread, keeping the first occurrence
            final_thread_data = []
            seen_ids = set()
            for tweet_item in all_thread_tweets_data:
                item_id = tweet_item.get("original_tweet_id_in_thread")
                if item_id and item_id != "unknown" and item_id not in seen_ids:
                    final_thread_data.append(tweet_item)
                    seen_ids.add(item_id)
                elif not item_id or item_id == "unknown": # Should not happen if parsing is good
                    final_thread_data.append(tweet_item) # Add it anyway if ID is problematic

            logging.info(f"Fetched {len(final_thread_data)} tweets (including main) for the thread starting with {tweet_url}")
            return final_thread_data
                

async def fetch_tweet_data_playwright(tweet_url: str, config: Config) -> List[Dict[str, Any]]:
    """
    Convenience function to fetch tweet data using PlaywrightFetcher.
    
    Args:
        tweet_url: URL of the tweet to fetch
        config: Config instance containing settings
        
    Returns:
        List of dictionaries, where each dictionary contains data for one tweet in the thread.
        The first item is the bookmarked tweet. Returns empty list on failure to fetch main tweet.
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
                # Filename might need adjustment in tweet_cacher if this is directly used for threads
                # to avoid collisions if multiple tweets in a thread have media.
                # For now, assume tweet_cacher.py handles unique naming from aggregated list.
                file_extension_match = re.search(r'(\.\w+)(\?|$)', Path(url).name)
                file_extension = f"{file_extension_match.group(1)}" if file_extension_match else ".jpg" # Default to .jpg
                filename = f"{tweet_id}_media_{i}{file_extension}"
                media_path = media_cache_dir / filename
                
                if media_path.exists():
                    downloaded_paths.append(media_path)
                    continue
                    
                async with session.get(url) as response:
                    if response.status == 200:
                        content = await response.read()
                        media_path.write_bytes(content)
                        downloaded_paths.append(media_path)
                    else:
                        logging.warning(f"Failed to download {url}, status: {response.status}")
                        
            except Exception as e:
                logging.error(f"Failed to download media from {url}: {e}")
                continue
                
    return downloaded_paths