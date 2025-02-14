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
        self.browser = None
        self.context = None
        self.page = None
        self.timeout = 30000  # 30 seconds in ms
        
    async def __aenter__(self):
        await self.initialize()
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.cleanup()

    async def initialize(self) -> None:
        """Initialize browser with retry logic."""
        try:
            playwright = await async_playwright().start()
            self.browser = await playwright.chromium.launch(headless=True)
            self.context = await self.browser.new_context()
            self.page = await self.context.new_page()
        except Exception as e:
            logging.exception("Failed to initialize browser")
            raise BookmarksFetchError("Browser initialization failed") from e

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        retry=retry_if_exception_type((PlaywrightTimeout, PlaywrightError))
    )
    async def login(self) -> None:
        """Handle X.com login with retry logic."""
        try:
            await self.page.goto('https://x.com/login', timeout=self.timeout)
            
            # Wait for and fill username
            await self.page.wait_for_selector('input[name="username"]', timeout=self.timeout)
            await self.page.fill('input[name="username"]', self.config.x_username)
            await self.page.click('text=Next')
            
            # Wait for and fill password
            await self.page.wait_for_selector('input[name="password"]', timeout=self.timeout)
            await self.page.fill('input[name="password"]', self.config.x_password)
            await self.page.click('text=Log in')
            
            # Wait for login completion
            await self.page.wait_for_selector('[data-testid="AppTabBar_Home_Link"]', timeout=self.timeout)
            
        except PlaywrightTimeout as e:
            logging.error(f"Timeout during login: {str(e)}")
            raise
        except Exception as e:
            logging.exception("Login failed")
            raise BookmarksFetchError("Failed to login to X.com") from e

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        retry=retry_if_exception_type((PlaywrightTimeout, PlaywrightError))
    )
    async def fetch_bookmarks(self) -> List[str]:
        """Fetch bookmarks with retry logic."""
        try:
            await self.page.goto(f"https://x.com/{self.config.x_username}/bookmarks", timeout=self.timeout)
            
            # Wait for bookmarks to load
            await self.page.wait_for_selector('[data-testid="tweet"]', timeout=self.timeout)
            
            # Scroll to load more bookmarks
            previous_height = 0
            while True:
                current_height = await self.page.evaluate('document.body.scrollHeight')
                if current_height == previous_height:
                    break
                await self.page.evaluate('window.scrollTo(0, document.body.scrollHeight)')
                await asyncio.sleep(2)  # Wait for content to load
                previous_height = current_height
            
            # Extract bookmark links
            links = await self.page.eval_on_selector_all(
                '[data-testid="tweet"] a[href*="/status/"]',
                'elements => elements.map(el => el.href)'
            )
            
            # Filter and clean links
            bookmark_links = list(set(link for link in links if '/status/' in link))
            
            if not bookmark_links:
                raise BookmarksFetchError("No bookmarks found")
                
            return bookmark_links
            
        except PlaywrightTimeout as e:
            logging.error(f"Timeout while fetching bookmarks: {str(e)}")
            raise
        except Exception as e:
            logging.exception("Failed to fetch bookmarks")
            raise BookmarksFetchError("Failed to fetch bookmarks from X.com") from e

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
                await self.login()
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
