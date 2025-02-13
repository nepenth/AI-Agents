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
        if not config.x_username or not config.x_password:
            raise ConfigurationError("X/Twitter credentials not provided")
        
        self.config = config
        self.login_url = "https://x.com/login"
        self.selectors = {
            'username': 'input[name="text"]',
            'password': 'input[name="password"]',
            'tweet': 'article[data-testid="tweet"], article[role="article"], article'
        }
        self.scroll_settings = {
            'pixels': 1000,
            'pause': 5,
            'max_iterations': 100,
            'max_no_change_tries': 3
        }

    async def fetch_bookmarks(self, headless: bool = True) -> bool:
        """
        Main method to fetch bookmarks from X/Twitter.
        Returns True if successful, False otherwise.
        """
        try:
            # Ensure necessary directories exist
            self.config.bookmarks_file.parent.mkdir(parents=True, exist_ok=True)
            archive_dir = self.config.bookmarks_file.parent / "archive_bookmarks"
            archive_dir.mkdir(parents=True, exist_ok=True)

            logging.info("Starting bookmark fetch process...")
            
            async with async_playwright() as p:
                browser = await self._setup_browser(p, headless)
                page = await browser.new_page()

                try:
                    await self._perform_login(page)
                    await self._navigate_to_bookmarks(page)
                    bookmarks = await self._scroll_and_collect_bookmarks(page)
                    await self._save_bookmarks(bookmarks)
                    return True
                except PlaywrightTimeoutError as e:
                    raise FetchError(f"Timeout during bookmark fetching: {e}")
                except Exception as e:
                    raise FetchError(f"Error during bookmark fetching: {e}")
                finally:
                    await browser.close()
                    logging.info("Browser closed.")
        except Exception as e:
            logging.error(f"Bookmark fetching failed: {e}")
            return False

    async def _setup_browser(self, playwright, headless: bool):
        """Setup and return a browser instance with appropriate settings"""
        return await playwright.chromium.launch(
            headless=headless,
            args=[
                '--no-sandbox',
                '--disable-setuid-sandbox',
                '--disable-dev-shm-usage',
                '--disable-gpu',
                '--disable-software-rasterizer'
            ]
        )

    async def _perform_login(self, page) -> None:
        """Handle the login process."""
        try:
            logging.info("Navigating to login page...")
            await page.goto(self.login_url, wait_until="networkidle")
            
            # Enter username
            await page.wait_for_selector(self.selectors['username'], timeout=30000)
            await page.type(self.selectors['username'], self.config.x_username, delay=100)
            await page.keyboard.press('Enter')
            await page.wait_for_timeout(3000)

            # Enter password
            await page.wait_for_selector(self.selectors['password'], timeout=30000)
            await page.type(self.selectors['password'], self.config.x_password, delay=100)
            await page.keyboard.press('Enter')

            # Wait for navigation and verify login
            try:
                await page.wait_for_navigation(timeout=30000, wait_until="domcontentloaded")
            except Exception as e:
                raise FetchError(f"Navigation error after login: {e}")

            if self.login_url in page.url:
                raise FetchError("Login failed: still on login page")
            
            logging.info("Login successful")
        except Exception as e:
            raise FetchError(f"Login failed: {e}")

    async def _navigate_to_bookmarks(self, page):
        """Navigate to the bookmarks page"""
        logging.info("Navigating to bookmarks page...")
        await page.goto(self.config.x_bookmarks_url, wait_until="domcontentloaded", timeout=60000)
        await page.wait_for_timeout(10000)  # Wait for dynamic content

        # Verify navigation
        if self.login_url in page.url:
            raise Exception("Navigation to bookmarks failed")

    async def _scroll_and_collect_bookmarks(self, page) -> List[str]:
        """Scroll through the page and collect bookmark links."""
        try:
            logging.info("Starting bookmark collection...")
            previous_height = await page.evaluate("() => document.body.scrollHeight")
            no_change_tries = 0
            all_bookmarks = set()

            for i in range(1, self.scroll_settings['max_iterations'] + 1):
                # Collect links
                links = await page.query_selector_all(f'{self.selectors["tweet"]} a[href*="/status/"]')
                current_links = [await link.get_attribute("href") for link in links if link]
                all_bookmarks.update([link for link in current_links if link])

                logging.info(f"Scroll #{i}. Found {len(all_bookmarks)} unique links.")

                # Scroll
                await page.evaluate(f"window.scrollBy(0, {self.scroll_settings['pixels']});")
                await asyncio.sleep(self.scroll_settings['pause'])

                # Check for new content
                current_height = await page.evaluate("() => document.body.scrollHeight")
                if current_height == previous_height:
                    no_change_tries += 1
                    if no_change_tries >= self.scroll_settings['max_no_change_tries']:
                        break
                else:
                    no_change_tries = 0
                    previous_height = current_height

            return [link for link in all_bookmarks 
                    if "/analytics" not in link and "/photo/" not in link]
        except Exception as e:
            raise FetchError(f"Error collecting bookmarks: {e}")

    async def _save_bookmarks(self, bookmarks: List[str]) -> None:
        """Save collected bookmarks to file."""
        try:
            if self.config.bookmarks_file.exists():
                timestamp = time.strftime("%Y%m%d-%H%M%S")
                archive_file = self.config.bookmarks_file.parent / "archive_bookmarks" / f"bookmarks_links_{timestamp}.txt"
                self.config.bookmarks_file.rename(archive_file)
                logging.info(f"Archived existing bookmarks to: {archive_file}")

            with self.config.bookmarks_file.open('w', encoding='utf8') as f:
                f.write("\n".join(bookmarks))
            logging.info(f"Saved {len(bookmarks)} bookmarks to {self.config.bookmarks_file}")
        except Exception as e:
            raise StorageError(f"Failed to save bookmarks: {e}")

async def fetch_bookmarks(config: Config) -> bool:
    """
    Main entry point for fetching bookmarks.
    Returns True if successful, False otherwise.
    """
    try:
        fetcher = BookmarksFetcher(config)
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch(headless=True)
            page = await browser.new_page()
            await fetcher.fetch_bookmarks(page)
            await browser.close()
        return True
    except Exception as e:
        logging.error(f"Failed to fetch bookmarks: {e}")
        return False

if __name__ == "__main__":
    config = Config.from_env()
    success = fetch_bookmarks(config)
    if not success:
        print("An error occurred while updating bookmarks. Proceeding with existing bookmarks.")
