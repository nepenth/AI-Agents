from typing import List, Optional
import asyncio
import os
import time
import logging
from pathlib import Path
from dotenv import load_dotenv
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError
from knowledge_base_agent.config import Config
from knowledge_base_agent.exceptions import FetchError, ConfigurationError, StorageError
import aiofiles

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
        self.login_url = "https://twitter.com/i/flow/login"

    async def fetch_bookmarks(self, page) -> bool:
        """Fetch bookmarks from X/Twitter."""
        try:
            logging.info("Navigating to login page...")
            await page.goto(self.login_url)
            
            logging.info("Attempting login...")
            await self._login(page)
            
            logging.info("Navigating to bookmarks...")
            await page.goto("https://twitter.com/i/bookmarks")
            
            logging.info("Collecting bookmarks...")
            bookmark_links = await self._scroll_and_collect_bookmarks(page)
            
            if bookmark_links:
                logging.info(f"Found {len(bookmark_links)} bookmarks")
                await self._save_bookmarks(bookmark_links)
                return True
            else:
                logging.warning("No bookmarks found")
                return False
                
        except Exception as e:
            logging.error(f"Error in fetch_bookmarks: {str(e)}", exc_info=True)
            return False

    async def _login(self, page) -> None:
        """Handle Twitter login."""
        try:
            # Wait for username field and enter username
            username_selector = 'input[autocomplete="username"]'
            await page.wait_for_selector(username_selector)
            await page.fill(username_selector, self.config.x_username)
            await page.keyboard.press('Enter')
            
            # Wait for password field and enter password
            password_selector = 'input[name="password"]'
            await page.wait_for_selector(password_selector)
            await page.fill(password_selector, self.config.x_password)
            await page.keyboard.press('Enter')
            
            # Wait for navigation to complete
            await page.wait_for_load_state('networkidle')
            
        except Exception as e:
            logging.error(f"Login failed: {e}")
            raise

    async def _scroll_and_collect_bookmarks(self, page) -> List[str]:
        """Scroll through the page and collect bookmark links."""
        bookmark_links = set()
        last_height = await page.evaluate('document.body.scrollHeight')
        
        while True:
            # Get all tweet links
            links = await page.eval_all(
                'article a[href*="/status/"]',
                'elements => elements.map(el => el.href)'
            )
            bookmark_links.update(links)
            
            # Scroll down
            await page.evaluate('window.scrollTo(0, document.body.scrollHeight)')
            await page.wait_for_timeout(1000)  # Wait for content to load
            
            # Check if we've reached the bottom
            new_height = await page.evaluate('document.body.scrollHeight')
            if new_height == last_height:
                break
            last_height = new_height
            
        return list(bookmark_links)

    async def _save_bookmarks(self, links: List[str]) -> None:
        """Save bookmark links to file."""
        try:
            async with aiofiles.open(self.config.bookmarks_file, 'w', encoding='utf-8') as f:
                await f.write('\n'.join(links))
            logging.info(f"Saved {len(links)} bookmarks to {self.config.bookmarks_file}")
        except Exception as e:
            logging.error(f"Failed to save bookmarks: {e}")
            raise

async def fetch_bookmarks(config: Config) -> bool:
    """
    Main entry point for fetching bookmarks.
    Returns True if successful, False otherwise.
    """
    try:
        logging.info("Starting bookmarks fetch process...")
        fetcher = BookmarksFetcher(config)
        
        if not config.x_username or not config.x_password:
            logging.error("X/Twitter credentials not configured")
            return False
            
        logging.info("Launching browser...")
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch(headless=True)
            page = await browser.new_page()
            
            logging.info("Attempting to fetch bookmarks...")
            await fetcher.fetch_bookmarks(page)
            
            logging.info("Closing browser...")
            await browser.close()
            
        logging.info("Bookmarks fetch completed successfully")
        return True
        
    except Exception as e:
        logging.error(f"Failed to fetch bookmarks: {str(e)}", exc_info=True)
        return False

if __name__ == "__main__":
    config = Config.from_env()
    success = fetch_bookmarks(config)
    if not success:
        print("An error occurred while updating bookmarks. Proceeding with existing bookmarks.")
