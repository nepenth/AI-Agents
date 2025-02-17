from typing import List, Optional
import asyncio
import os
import time
import logging
from pathlib import Path
from dotenv import load_dotenv
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeout
from knowledge_base_agent.config import Config
from knowledge_base_agent.exceptions import FetchError, ConfigurationError, StorageError, BookmarksFetchError
import aiofiles
from knowledge_base_agent.http_client import HTTPClient
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from playwright.async_api import Error as PlaywrightError

# Load environment variables
load_dotenv()

# Configure logging to our main log file.
logging.basicConfig(
    filename='agent_program.log',
    level=logging.DEBUG,  # DEBUG for detailed logs
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# Constants and selectors
LOGIN_URL = "https://x.com/login"
USERNAME_SELECTOR = 'input[name="text"]'
PASSWORD_SELECTOR = 'input[name="password"]'
TWEET_SELECTOR = 'article[data-testid="tweet"], article[role="article"], article'
SCROLL_PIXELS = 1000
SCROLL_PAUSE = 5  # seconds
MAX_SCROLL_ITERATIONS = 100
MAX_NO_CHANGE_TRIES = 3

# Update data directory to be relative to the project root
DATA_DIR = Path("data")  # This stays the same as it's for configuration
BOOKMARKS_FILE = DATA_DIR / "bookmarks_links.txt"
ARCHIVE_DIR = DATA_DIR / "archive_bookmarks"

class BookmarksFetcher:
    def __init__(self, config: Config):
        self.config = config
        self.timeout = 30000
        self.playwright = None
        self.browser = None
        self.context = None
        self.page = None
        
    async def __aenter__(self):
        await self.initialize()
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.cleanup()

    async def initialize(self) -> None:
        """Initialize the browser and page."""
        try:
            logging.info("Initializing browser...")
            self.playwright = await async_playwright().start()
            self.browser = await self.playwright.chromium.launch(
                headless=self.config.selenium_headless,
                args=[
                    '--no-sandbox',
                    '--disable-setuid-sandbox',
                    '--disable-dev-shm-usage',
                    '--disable-gpu',
                    '--disable-software-rasterizer'
                ]
            )
            self.context = await self.browser.new_context()
            self.page = await self.context.new_page()
            
            # Navigate to login page
            logging.info("Navigating to login page...")
            await self.page.goto('https://twitter.com/login', wait_until="networkidle")
            
            # Login
            await self.page.wait_for_selector('input[name="text"]', timeout=self.timeout)
            await self.page.type('input[name="text"]', self.config.x_username, delay=100)
            await self.page.keyboard.press('Enter')
            await self.page.wait_for_timeout(3000)

            await self.page.wait_for_selector('input[name="password"]', timeout=self.timeout)
            await self.page.type('input[name="password"]', self.config.x_password, delay=100)
            await self.page.keyboard.press('Enter')
            
            logging.info("Login submitted")
            
        except Exception as e:
            logging.error(f"Browser initialization failed: {str(e)}")
            await self.cleanup()
            raise BookmarksFetchError(f"Failed to initialize browser: {str(e)}") from e

    async def fetch_bookmarks(self) -> List[str]:
        """Fetch bookmarks from Twitter."""
        try:
            # Try to dismiss any modal dialog
            try:
                await self.page.wait_for_selector('div[role="dialog"] button', timeout=5000)
                buttons = await self.page.query_selector_all('div[role="dialog"] button')
                for btn in buttons:
                    btn_text = await btn.inner_text()
                    if "Not now" in btn_text:
                        await btn.click()
                        logging.info("Dismissed 'Not now' dialog.")
                        break
            except Exception as e:
                logging.debug("No modal dialog to dismiss.")

            # Navigate to bookmarks page
            logging.info("Navigating to bookmarks page...")
            await self.page.goto(str(self.config.x_bookmarks_url), wait_until="domcontentloaded", timeout=60000)
            await self.page.wait_for_timeout(10000)  # wait for dynamic content

            # Check current URL
            current_url = self.page.url
            logging.debug(f"After navigating to bookmarks, URL is: {current_url}")

            if "login" in current_url:
                raise BookmarksFetchError("Navigation to bookmarks page failed")

            # Log page content for debugging
            content = await self.page.content()
            logging.debug(f"Bookmarks page content length: {len(content)}")
            
            # Find tweet elements
            tweet_elements = await self.page.query_selector_all('article[data-testid="tweet"], article[role="article"], article')
            if tweet_elements:
                logging.info(f"Found {len(tweet_elements)} tweet elements")
            else:
                logging.warning("No tweet elements found")
            
            # Extract bookmark links
            all_bookmarks = set()
            links = await self.page.query_selector_all('article a[href*="/status/"]')
            for link in links:
                href = await link.get_attribute("href")
                if href:
                    all_bookmarks.add(href)
            
            # Filter unwanted links
            bookmarks = [link for link in all_bookmarks 
                        if isinstance(link, str) 
                        and "/analytics" not in link 
                        and "/photo/" not in link]
            
            logging.info(f"Extracted {len(bookmarks)} unique bookmark links")
            return bookmarks
            
        except Exception as e:
            logging.error(f"Timeout while fetching bookmarks: {str(e)}")
            raise BookmarksFetchError(f"Failed to fetch bookmarks: {str(e)}")

    async def cleanup(self) -> None:
        """Clean up browser resources."""
        try:
            if self.page:
                await self.page.close()
            if self.context:
                await self.context.close()
            if self.browser:
                await self.browser.close()
        except Exception as e:
            logging.exception("Failed to cleanup browser resources")

    async def run(self) -> List[str]:
        """Main execution flow with proper resource handling."""
        try:
            async with self:
                return await self.fetch_bookmarks()
        except Exception as e:
            logging.exception("Bookmark fetching failed")
            raise BookmarksFetchError("Failed to complete bookmark fetching process") from e

async def fetch_all_bookmarks(config: Config) -> List[str]:
    """Main entry point for fetching bookmarks."""
    try:
        logging.info("Starting bookmarks fetch process...")
        async with BookmarksFetcher(config) as fetcher:
            return await fetcher.run()
    except Exception as e:
        logging.error(f"Failed to fetch bookmarks: {str(e)}")
        raise BookmarksFetchError("Bookmark fetch process failed") from e

if __name__ == "__main__":
    config = Config.from_env()
    try:
        bookmarks = fetch_all_bookmarks(config)
        print("Bookmarks fetched successfully")
    except BookmarksFetchError as e:
        print(f"Error: {e}")
