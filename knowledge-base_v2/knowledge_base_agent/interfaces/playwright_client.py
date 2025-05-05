# knowledge_base_agent/interfaces/playwright_client.py

import asyncio
import logging
from typing import Optional, List
from contextlib import contextmanager # For sync context manager

# Import both sync and async playwright APIs
from playwright.sync_api import (
    sync_playwright,
    Browser as SyncBrowser,
    BrowserContext as SyncBrowserContext,
    Page as SyncPage,
    Playwright as SyncPlaywright,
    TimeoutError as PlaywrightTimeoutError,
    Error as PlaywrightErrorBase
)
# Keep async imports for type hints if needed elsewhere, or remove if not used async directly
# from playwright.async_api import async_playwright, Playwright, Browser, Page, BrowserContext

from ..config import Config
from ..exceptions import PlaywrightError
from pathlib import Path
from datetime import datetime


logger = logging.getLogger(__name__)

class PlaywrightClient:
    """
    Manages Playwright browser interactions using the **synchronous** API,
    but provides async wrappers using asyncio.to_thread for use in async contexts.
    """

    def __init__(self, config: Config, headless: bool = True):
        self.config = config
        self.headless = headless
        self._playwright: Optional[SyncPlaywright] = None
        self._browser: Optional[SyncBrowser] = None
        # No persistent context/page needed if methods manage them internally
        logger.info(f"PlaywrightClient (Sync API) initialized. Headless: {headless}")

    # Use a context manager for setup/teardown of sync playwright
    @contextmanager
    def _sync_context(self):
        """Provides a managed sync playwright instance and browser."""
        pw = None
        browser = None
        try:
            logger.debug("Starting sync Playwright...")
            pw = sync_playwright().start()
            # Consider making browser type configurable
            browser = pw.chromium.launch(headless=self.headless)
            logger.debug("Sync Playwright browser launched.")
            yield pw, browser # Yield the playwright instance and browser
        except PlaywrightErrorBase as e:
             logger.error(f"Sync Playwright startup failed: {e}")
             raise PlaywrightError(f"Playwright startup failed: {e}", original_exception=e) from e
        except Exception as e:
             logger.error(f"Unexpected error starting Playwright: {e}", exc_info=True)
             raise PlaywrightError(f"Unexpected error starting Playwright: {e}", original_exception=e) from e
        finally:
            if browser:
                try:
                    browser.close()
                    logger.debug("Sync Playwright browser closed.")
                except Exception as e:
                    logger.warning(f"Error closing sync browser: {e}")
            if pw:
                try:
                    pw.stop()
                    logger.debug("Sync Playwright stopped.")
                except Exception as e:
                    logger.warning(f"Error stopping sync Playwright: {e}")


    def _sync_login_to_x(self, pw: SyncPlaywright, browser: SyncBrowser, login_timeout: int = 60000):
        """Synchronous implementation of X login."""
        if not (self.config.x_username and self.config.x_password and self.config.x_bookmarks_url):
            raise PlaywrightError("X Username, Password, or Bookmarks URL not configured.")

        context = None
        page = None
        try:
            context = browser.new_context(
                 user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            )
            page = context.new_page()
            login_url = "https://x.com/login"
            logger.info(f"(Sync) Navigating to X login page: {login_url}")
            page.goto(login_url, timeout=login_timeout, wait_until='domcontentloaded')
            page.wait_for_timeout(2000) # Sync sleep

            # --- Login Steps (Selectors likely need updating) ---
            logger.info("(Sync) Entering username...")
            username_selector = 'input[name="text"]'
            page.locator(username_selector).fill(self.config.x_username)
            page.locator(username_selector).press('Enter')
            page.wait_for_timeout(1500)

            # Handle potential intermediate step (Needs testing/adjustment)
            # phone_email_selector = 'input[name="text"][type="text"]'
            # if page.locator(phone_email_selector).is_visible(timeout=5000):
            #     logger.info("(Sync) Handling intermediate verification step...")
            #     page.locator(phone_email_selector).fill(self.config.x_username) # Or phone
            #     page.locator(phone_email_selector).press('Enter')
            #     page.wait_for_timeout(1500)

            logger.info("(Sync) Entering password...")
            password_selector = 'input[name="password"]'
            page.locator(password_selector).fill(self.config.x_password.get_secret_value())
            page.locator(password_selector).press('Enter')

            logger.info("(Sync) Waiting for login confirmation...")
            page.wait_for_url(f"https://x.com/home", timeout=login_timeout)
            logger.info("(Sync) X Login successful.")
            # Return context state if we need to reuse it? Or just True.
            return True
        except PlaywrightTimeoutError as e:
             logger.error(f"(Sync) Timeout during X login process: {e}")
             self._sync_screenshot_on_error(page, "x_login_timeout")
             raise PlaywrightError(f"Timeout waiting during sync login: {e}", original_exception=e) from e
        except PlaywrightErrorBase as e:
             logger.error(f"(Sync) Playwright error during X login: {e}")
             self._sync_screenshot_on_error(page, "x_login_error")
             raise PlaywrightError(f"Playwright error during sync login: {e}", original_exception=e) from e
        except Exception as e:
             logger.error(f"(Sync) Unexpected error during X login: {e}", exc_info=True)
             self._sync_screenshot_on_error(page, "x_login_unexpected_error")
             raise PlaywrightError(f"Unexpected error during sync login: {e}", original_exception=e) from e
        finally:
             if context: context.close() # Close context and its pages

    def _sync_fetch_bookmark_urls(
        self, pw: SyncPlaywright, browser: SyncBrowser, scroll_limit: int, load_timeout: int, scroll_delay_ms: int
    ) -> List[str]:
        """Synchronous implementation of bookmark fetching."""
        if not self.config.x_bookmarks_url:
             raise PlaywrightError("X Bookmarks URL not configured.")

        # Requires login state - how to manage? Reuse context or log in again?
        # For now, let's assume login happens before this in a real scenario,
        # or modify login to return a usable context state.
        # This example will likely fail without prior login.
        # A better approach: login returns context state, load state here.
        context = None
        page = None
        try:
             logger.warning("(Sync) Bookmark fetching assumes prior login state exists (implementation detail).")
             # Simplified: Create new context, assume login cookies might exist if browser wasn't headless/new profile
             context = browser.new_context() # Might need user agent etc.
             page = context.new_page()
             bookmarks_url = str(self.config.x_bookmarks_url)
             logger.info(f"(Sync) Navigating to X Bookmarks page: {bookmarks_url}")
             page.goto(bookmarks_url, timeout=load_timeout, wait_until='domcontentloaded')
             page.locator('div[data-testid="primaryColumn"]').wait_for(timeout=load_timeout)
             page.wait_for_timeout(2000)

             collected_urls = set()
             tweet_link_selector = 'a[href*="/status/"]'

             logger.info(f"(Sync) Scrolling bookmarks page {scroll_limit} times...")
             for i in range(scroll_limit):
                 links = page.locator(tweet_link_selector).all()
                 for link_handle in links:
                     href = link_handle.get_attribute('href')
                     if href and "/status/" in href:
                         full_url = f"https://x.com{href.split('?')[0]}"
                         if '/photo/' not in full_url:
                             collected_urls.add(full_url)

                 page.evaluate('window.scrollBy(0, window.innerHeight * 2)')
                 logger.debug(f"(Sync) Scroll {i+1}/{scroll_limit}, collected {len(collected_urls)} URLs.")
                 page.wait_for_timeout(scroll_delay_ms)

             logger.info(f"(Sync) Finished scrolling. Found {len(collected_urls)} bookmark URLs.")
             return list(collected_urls)

        except PlaywrightTimeoutError as e:
             logger.error(f"(Sync) Timeout during bookmark fetching: {e}")
             self._sync_screenshot_on_error(page, "x_bookmarks_timeout")
             raise PlaywrightError(f"Timeout during sync bookmark fetch: {e}", original_exception=e) from e
        except PlaywrightErrorBase as e:
             logger.error(f"(Sync) Playwright error during bookmark fetching: {e}")
             self._sync_screenshot_on_error(page, "x_bookmarks_error")
             raise PlaywrightError(f"Playwright error during sync bookmark fetch: {e}", original_exception=e) from e
        except Exception as e:
             logger.error(f"(Sync) Unexpected error during bookmark fetching: {e}", exc_info=True)
             self._sync_screenshot_on_error(page, "x_bookmarks_unexpected_error")
             raise PlaywrightError(f"Unexpected error during sync bookmark fetch: {e}", original_exception=e) from e
        finally:
             if context: context.close()


    def _sync_screenshot_on_error(self, page: Optional[SyncPage], name: str = "error"):
        """Takes a screenshot using sync API if a page object exists."""
        if page and not page.is_closed():
             try:
                 log_dir = Path(self.config.log_dir)
                 log_dir.mkdir(exist_ok=True)
                 screenshot_path = log_dir / f"playwright_sync_{name}_{datetime.now():%Y%m%d_%H%M%S}.png"
                 page.screenshot(path=str(screenshot_path))
                 logger.info(f"(Sync) Screenshot saved to {screenshot_path}")
             except Exception as ss_err:
                 logger.error(f"(Sync) Failed to take error screenshot: {ss_err}")

    # --- Async Wrappers ---
    # These are the methods the async pipeline will call.

    async def login_to_x(self, login_timeout: int = 60000) -> bool:
         """Async wrapper for sync X login."""
         logger.info("Running sync login_to_x in thread...")
         try:
              with self._sync_context() as (pw, browser):
                   result = await asyncio.to_thread(
                        self._sync_login_to_x, pw, browser, login_timeout
                   )
                   return result
         except Exception as e:
              logger.error(f"Error running sync login in thread: {e}", exc_info=True)
              # Ensure specific error is raised if needed
              if not isinstance(e, PlaywrightError):
                   raise PlaywrightError(f"Thread execution failed for login: {e}", original_exception=e) from e
              else:
                   raise e

    async def fetch_bookmark_urls(
        self,
        scroll_limit: int = 10,
        load_timeout: int = 60000,
        scroll_delay_ms: int = 3000
    ) -> List[str]:
        """Async wrapper for sync bookmark fetching."""
        logger.info("Running sync fetch_bookmark_urls in thread...")
        try:
            with self._sync_context() as (pw, browser):
                # Note: This still relies on login state being implicitly available or handled separately
                # A robust solution would involve passing context state or ensuring login within the same browser instance.
                logger.warning("Bookmark fetching via sync API wrapper initiated. Assumes login state handled externally or implicitly.")
                urls = await asyncio.to_thread(
                     self._sync_fetch_bookmark_urls, pw, browser, scroll_limit, load_timeout, scroll_delay_ms
                )
                return urls
        except Exception as e:
             logger.error(f"Error running sync bookmark fetch in thread: {e}", exc_info=True)
             if not isinstance(e, PlaywrightError):
                  raise PlaywrightError(f"Thread execution failed for bookmark fetch: {e}", original_exception=e) from e
             else:
                  raise e

    # No explicit async close needed as context manager handles it
    # async def close(self): pass
    # No async context manager needed as methods manage context internally
    # async def __aenter__(self): return self
    # async def __aexit__(self, exc_type, exc_val, exc_tb): pass


# Example Usage (for testing) - Requires config setup
# async def main():
#     from ..config import load_config # Assuming load_config is available
#     config = load_config()
#     if not config.fetch_bookmarks_enabled:
#         print("Bookmark fetching disabled in config.")
#         return
#
#     async with PlaywrightClient(config, headless=False) as client: # Run non-headless for debug
#         try:
#             logged_in = await client.login_to_x()
#             if logged_in:
#                 urls = await client.fetch_bookmark_urls(scroll_limit=2)
#                 print("Fetched URLs:", urls)
#         except PlaywrightError as e:
#             print(f"Playwright operation failed: {e}")
#
# if __name__ == "__main__":
#     # Needs event loop setup if run directly
#     # import asyncio
#     # asyncio.run(main())
#     pass

# Import necessary Path and datetime for screenshot function
from pathlib import Path
from datetime import datetime
import json # Needed for Ollama stream decoding