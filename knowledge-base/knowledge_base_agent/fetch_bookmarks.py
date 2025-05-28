from typing import List, Optional, Dict, Any
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
import json
from datetime import datetime, timezone
from knowledge_base_agent.tweet_utils import parse_tweet_id_from_url

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
SCROLL_PAUSE = 5 
MAX_SCROLL_ITERATIONS = 100
MAX_NO_CHANGE_TRIES = 3

# Update data directory to be relative to the project root
DATA_DIR = Path("data")  # This stays the same as it's for configuration
BOOKMARKS_FILE = DATA_DIR / "bookmarks_links.txt"
ARCHIVE_DIR = DATA_DIR / "archive_bookmarks"

# Constants for new JSON structure (archive dir remains same conceptually)
# BOOKMARKS_FILE is now managed by config.bookmarks_file
ARCHIVE_DIR_NAME = "archive_tweet_bookmarks"

class BookmarksFetcher:
    def __init__(self, config: Config):
        self.config = config
        self.timeout = self.config.selenium_timeout * 1000 # Use config value
        self.login_timeout = getattr(self.config, 'x_login_timeout', 60) * 1000  # Convert to milliseconds
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
            await self.page.goto('https://twitter.com/login', wait_until="networkidle", timeout=self.login_timeout)
            
            # Login
            await self.page.wait_for_selector(USERNAME_SELECTOR, timeout=self.login_timeout)
            await self.page.type(USERNAME_SELECTOR, self.config.x_username, delay=100)
            await self.page.keyboard.press('Enter')
            await self.page.wait_for_timeout(3000)

            await self.page.wait_for_selector(PASSWORD_SELECTOR, timeout=self.login_timeout)
            await self.page.type(PASSWORD_SELECTOR, self.config.x_password, delay=100)
            await self.page.keyboard.press('Enter')
            
            logging.info("Login submitted")
            
            # Wait for successful login with multiple possible outcomes
            try:
                # Try waiting for home page redirect first (30 seconds max)
                await self.page.wait_for_url("**/home", timeout=30000)  # Use longer timeout for redirect
                logging.info("Login successful, redirected to home.")
            except Exception as redirect_error:
                logging.warning(f"No redirect to home page within 15s: {redirect_error}")
                
                # Check if we're on a 2FA/verification page
                current_url = self.page.url
                logging.info(f"Current URL after login attempt: {current_url}")
                
                # Check for common post-login scenarios
                if "challenge" in current_url or "verification" in current_url or "authenticate" in current_url:
                    raise BookmarksFetchError(
                        "Login requires additional verification (2FA/CAPTCHA). "
                        "Please log in manually to X/Twitter in a regular browser first, "
                        "then try running the agent again."
                    )
                elif "suspended" in current_url or "locked" in current_url:
                    raise BookmarksFetchError(
                        "Account appears to be suspended or locked. "
                        "Please check your X/Twitter account status."
                    )
                elif "login" in current_url:
                    # Still on login page - credentials might be wrong
                    raise BookmarksFetchError(
                        "Login failed - still on login page. "
                        "Please check your X_USERNAME and X_PASSWORD in the .env file."
                    )
                else:
                    # Try to continue anyway - might be on a different valid page
                    logging.warning(f"Login may have succeeded but didn't redirect to home. Current URL: {current_url}")
                    
                    # Check if we can find indicators of successful login
                    try:
                        # Look for common elements that appear when logged in
                        await self.page.wait_for_selector('[data-testid="SideNav_AccountSwitcher_Button"]', timeout=5000)
                        logging.info("Found account switcher - login appears successful")
                    except:
                        try:
                            await self.page.wait_for_selector('a[href="/compose/tweet"]', timeout=5000)
                            logging.info("Found compose button - login appears successful")
                        except:
                            logging.warning("Could not confirm successful login, but continuing anyway...")
            
        except BookmarksFetchError:
            # Re-raise BookmarksFetchError with better messages as-is
            await self.cleanup()
            raise
        except Exception as e:
            logging.error(f"Browser initialization or login failed: {str(e)}", exc_info=True)
            await self.cleanup()
            
            # Provide more helpful error messages based on error type
            error_message = str(e)
            if "Timeout" in error_message and "home" in error_message:
                raise BookmarksFetchError(
                    "Login timeout: X/Twitter did not redirect to home page. "
                    "This often indicates 2FA/CAPTCHA is required. "
                    "Try logging into X/Twitter manually in a browser first."
                ) from e
            elif "net::ERR_" in error_message or "Navigation" in error_message:
                raise BookmarksFetchError(
                    "Network error during login. Check your internet connection and try again."
                ) from e
            else:
                raise BookmarksFetchError(f"Failed to initialize browser or login: {str(e)}") from e

    async def fetch_bookmarks(self) -> List[str]:
        """Fetch bookmarks from Twitter, save to JSON, and return a list of tweet IDs."""
        current_bookmarks_data: Dict[str, Dict[str, str]] = {}
        bookmarks_file_path = self.config.bookmarks_file # Path from config (e.g., data/tweet_bookmarks.json)
        
        # Ensure parent directory for bookmarks file exists
        bookmarks_file_path.parent.mkdir(parents=True, exist_ok=True)

        if bookmarks_file_path.exists():
            try:
                with open(bookmarks_file_path, 'r', encoding='utf-8') as f:
                    current_bookmarks_data = json.load(f)
                logging.info(f"Loaded {len(current_bookmarks_data)} existing bookmarks from {bookmarks_file_path}")
            except json.JSONDecodeError:
                logging.warning(f"Could not parse {bookmarks_file_path}, starting with empty bookmarks.")
            except Exception as e:
                logging.error(f"Error loading {bookmarks_file_path}: {e}, starting with empty bookmarks.")

        try:
            # Try to dismiss any modal dialog
            try:
                await self.page.wait_for_selector('div[role="dialog"] button', timeout=5000)
                buttons = await self.page.query_selector_all('div[role="dialog"] button')
                for btn in buttons:
                    btn_text = await btn.inner_text()
                    if "Not now" in btn_text or "Maybe later" in btn_text: # Added common alternative
                        await btn.click()
                        logging.info(f"Dismissed '{btn_text}' dialog.")
                        break
            except PlaywrightTimeout:
                logging.debug("No modal dialog to dismiss or timed out waiting.")
            except Exception as e:
                logging.debug(f"Error dismissing dialog: {e}")

            # Navigate to bookmarks page
            logging.info(f"Navigating to bookmarks page: {self.config.x_bookmarks_url}")
            await self.page.goto(str(self.config.x_bookmarks_url), wait_until="domcontentloaded", timeout=self.timeout)
            await self.page.wait_for_timeout(10000)  # wait for dynamic content

            # Check current URL
            current_url = self.page.url
            logging.debug(f"After navigating to bookmarks, URL is: {current_url}")

            if "login" in current_url.lower():
                raise BookmarksFetchError("Navigation to bookmarks page failed, ended up on login page.")

            # Log page content for debugging
            content = await self.page.content()
            logging.debug(f"Bookmarks page content length: {len(content)}")

            # START SCROLLING - for dynamic loading of bookmarks
            logging.info("Starting scroll to load bookmarks...")
            previous_height = await self.page.evaluate("() => document.body.scrollHeight")
            no_change_tries = 0
            # Using a set to store scraped hrefs to avoid immediate duplicates during scraping phase
            scraped_tweet_hrefs_set: set[str] = set()

            for scroll_iterations in range(MAX_SCROLL_ITERATIONS):
                links = await self.page.query_selector_all(f'{TWEET_SELECTOR} a[href*="/status/"]')
                for link_element in links:
                    href = await link_element.get_attribute("href")
                    if href:
                        scraped_tweet_hrefs_set.add(href)

                logging.info(f"Scroll iteration #{scroll_iterations + 1}. Found so far: {len(scraped_tweet_hrefs_set)} unique hrefs.")

                await self.page.evaluate(f"window.scrollBy(0, {SCROLL_PIXELS});")
                await self.page.wait_for_timeout(SCROLL_PAUSE * 1000)

                current_height = await self.page.evaluate("() => document.body.scrollHeight")
                if current_height == previous_height:
                    no_change_tries += 1
                    logging.info(f"No new content detected #{no_change_tries} time(s).")
                    if no_change_tries >= MAX_NO_CHANGE_TRIES:
                        logging.info("No new content after multiple attempts, ending scroll.")
                        break
                else:
                    no_change_tries = 0
                previous_height = current_height
            
            # One final collection after scrolling stops
            links = await self.page.query_selector_all(f'{TWEET_SELECTOR} a[href*="/status/"]')
            for link_element in links:
                href = await link_element.get_attribute("href")
                if href:
                    scraped_tweet_hrefs_set.add(href)

            logging.info(f"Extracted {len(scraped_tweet_hrefs_set)} unique bookmark hrefs after scrolling.")
            
            # Filter and process the scraped hrefs
            updated_count = 0
            added_count = 0
            fetch_timestamp = datetime.now(timezone.utc).isoformat()

            for raw_href in scraped_tweet_hrefs_set:
                if not isinstance(raw_href, str):
                    continue

                # Clean the href: remove query parameters
                url_path = raw_href.split('?')[0]

                # Apply filters for analytics, photos, and auxiliary links
                if "/analytics" in url_path or \
                    "/photo/" in url_path or \
                    any(aux_part in url_path for aux_part in ['/media_tags', '/retweets', '/likes', '/quotes', '/replies']):
                    continue

                if '/status/' not in url_path:
                    continue # Not a status link

                tweet_id = parse_tweet_id_from_url(url_path) # Use the helper from tweet_utils
                if not tweet_id:
                    logging.warning(f"Could not parse tweet ID from cleaned URL path: {url_path}")
                    continue
                
                full_url = f"https://twitter.com{url_path}" # Construct full URL

                if tweet_id in current_bookmarks_data:
                    # Existing bookmark, update last_seen
                    current_bookmarks_data[tweet_id]["last_seen_bookmarked_at"] = fetch_timestamp
                    current_bookmarks_data[tweet_id]["url_path"] = url_path # Update path in case it changed (rare)
                    current_bookmarks_data[tweet_id]["full_url"] = full_url
                    updated_count += 1
                else:
                    # New bookmark
                    current_bookmarks_data[tweet_id] = {
                        "url_path": url_path,
                        "full_url": full_url,
                        "first_fetched_at": fetch_timestamp,
                        "last_seen_bookmarked_at": fetch_timestamp
                    }
                    added_count += 1
            
            logging.info(f"Processed scraped bookmarks: Added {added_count} new, Updated {updated_count} existing.")

            # Archive old bookmarks file (if it exists and is different type or for safety)
            # This logic is simplified: if the target is JSON, old .txt is archived.
            # More robust: check if old file exists and is NOT the same as bookmarks_file_path before archiving.
            legacy_txt_bookmarks_file = bookmarks_file_path.with_suffix('.txt') # e.g. data/tweet_bookmarks.txt
            if legacy_txt_bookmarks_file.exists() and legacy_txt_bookmarks_file != bookmarks_file_path:
                archive_ts = time.strftime("%Y%m%d-%H%M%S")
                archive_file_name = f"{bookmarks_file_path.stem}_{archive_ts}{legacy_txt_bookmarks_file.suffix}"
                archive_path = self.config.data_processing_dir / ARCHIVE_DIR_NAME / archive_file_name
                archive_path.parent.mkdir(parents=True, exist_ok=True)
                try:
                    legacy_txt_bookmarks_file.rename(archive_path)
                    logging.info(f"Archived legacy bookmarks file {legacy_txt_bookmarks_file} to {archive_path}")
                except Exception as e:
                    logging.error(f"Could not archive legacy bookmarks file {legacy_txt_bookmarks_file}: {e}")
            
            # Write new/updated bookmarks to JSON file
            try:
                with open(bookmarks_file_path, 'w', encoding='utf-8') as f:
                    json.dump(current_bookmarks_data, f, indent=2)
                logging.info(f"Saved {len(current_bookmarks_data)} total bookmarks to {bookmarks_file_path}")
            except Exception as e:
                logging.error(f"Failed to save bookmarks to {bookmarks_file_path}: {e}", exc_info=True)
                raise BookmarksFetchError(f"Failed to save bookmarks JSON: {e}") from e

            # Return a list of all full tweet URLs for the agent to process
            return [data["full_url"] for data in current_bookmarks_data.values() if "full_url" in data]

        except Exception as e:
            logging.error(f"Error during fetching bookmarks: {str(e)}", exc_info=True)
            # Return existing full URLs if any were loaded, to allow processing of older data if fetch fails mid-way
            if current_bookmarks_data:
                 logging.warning("Returning already known bookmark URLs due to fetch error.")
                 return [data["full_url"] for data in current_bookmarks_data.values() if "full_url" in data]
            raise BookmarksFetchError(f"Failed to fetch bookmarks: {str(e)}") from e

    async def cleanup(self) -> None:
        """Clean up browser resources."""
        try:
            if self.page:
                await self.page.close()
            if self.context:
                await self.context.close()
            if self.browser:
                await self.browser.close()
            if self.playwright:
                await self.playwright.stop() # Gracefully stop playwright
        except Exception as e:
            logging.exception("Failed to cleanup browser resources")

    async def run(self) -> List[str]:
        """Main execution flow with proper resource handling."""
        try:
            async with self:
                return await self.fetch_bookmarks()
        except BookmarksFetchError as e:
            logging.error(f"Bookmark fetching run failed: {e}", exc_info=True)
            raise # Re-raise to be caught by caller
        except Exception as e:
            logging.error(f"Unexpected error in BookmarksFetcher run: {e}", exc_info=True)
            raise BookmarksFetchError(f"Unexpected error in bookmark fetching process: {e}") from e

async def fetch_all_bookmarks(config: Config) -> List[str]:
    """Main entry point for fetching bookmarks."""
    try:
        logging.info("Starting bookmarks fetch process...")
        fetcher = BookmarksFetcher(config) # Initialize outside async with if __aenter__ is complex
        return await fetcher.run() # run() handles aenter/aexit
    except BookmarksFetchError:
        raise # Propagate specific error
    except Exception as e:
        logging.error(f"Top-level error fetching all bookmarks: {e}", exc_info=True)
        raise BookmarksFetchError("Main bookmark fetch process failed catastrophically") from e

if __name__ == "__main__":
    # Basic logging for standalone script run
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    try:
        config = Config.from_env()
        # Ensure directories for config paths before running
        config.ensure_directories() 
        logging.info(f"Running {__file__} as a standalone script.")
        logging.info(f"Bookmarks will be saved to: {config.bookmarks_file}")
        
        tweet_ids_list = asyncio.run(fetch_all_bookmarks(config))
        logging.info(f"Script completed. Fetched {len(tweet_ids_list)} tweet IDs.")
        if tweet_ids_list:
            logging.info(f"Sample Tweet IDs: {tweet_ids_list[:5]}")
    except BookmarksFetchError as e:
        logging.error(f"Error in standalone script: {e}")
    except ConfigurationError as e:
        logging.error(f"Configuration error: {e}")
    except Exception as e:
        logging.error(f"An unexpected error occurred: {e}", exc_info=True)
