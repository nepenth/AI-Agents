# knowledge_base_agent/interfaces/playwright_client.py

import asyncio
import logging
from typing import Optional, List, Dict, Any
from contextlib import contextmanager # For sync context manager
import re # For extracting t.co links and potentially tweet ID from URL

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
from playwright.async_api import async_playwright, Playwright, Browser, Page, BrowserContext

from ..config import Config
from ..exceptions import PlaywrightError
from pathlib import Path
from datetime import datetime


logger = logging.getLogger(__name__)

class PlaywrightClient:
    """
    Manages Playwright browser interactions using the **asynchronous** API.
    Maintains a logged-in state internally after successful login.
    """

    def __init__(self, config: Config, headless: bool = True):
        self.config = config
        self.headless = headless
        self._playwright: Optional[Playwright] = None
        self._browser: Optional[Browser] = None
        self._authenticated_context: Optional[BrowserContext] = None
        self._is_logged_in = False
        self._login_timeout_ms = config.playwright_login_timeout_ms
        self._nav_timeout_ms = config.playwright_nav_timeout_ms
        logger.info(f"PlaywrightClient (Async API) initialized. Headless: {headless}")

    async def initialize(self):
        """Initializes the Playwright instance and browser."""
        if not self._playwright:
            self._playwright = await async_playwright().start()
            self._browser = await self._playwright.chromium.launch(headless=self.headless)
            logger.info("Playwright async instance and browser initialized.")
        return self._playwright

    async def login_to_x(self):
        """Logs into X using the async API."""
        if not self.config.x_username or not self.config.x_password:
            raise PlaywrightError("X credentials not configured. Cannot login.")
        
        if self._is_logged_in:
            logger.info("(Async) Already logged in to X. Skipping login attempt.")
            return
        
        if not self._playwright or not self._browser:
            await self.initialize()
        
        try:
            logger.info("Attempting X login via Playwright (async)...")
            self._authenticated_context = await self._browser.new_context(
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            )
            page = await self._authenticated_context.new_page()
            await page.goto("https://x.com/login", timeout=self._nav_timeout_ms, wait_until="domcontentloaded")
            logger.info("(Async) Navigating to X login page: https://x.com/login")
            await page.wait_for_timeout(3000)  # Static wait, consider if can be dynamic

            logger.info("(Async) Entering username...")
            username_selector = 'input[name="text"]'
            await page.wait_for_selector(username_selector, timeout=self.config.playwright_action_timeout_ms)
            await page.locator(username_selector).fill(self.config.x_username)
            await page.locator(username_selector).press('Enter')
            await page.wait_for_timeout(3000)

            password_selector = 'input[name="password"]'
            try:
                await page.wait_for_selector(password_selector, timeout=self.config.playwright_action_timeout_ms)
            except PlaywrightTimeoutError:
                logger.warning("(Async) Password field not immediately available. Checking for intermediate step...")
                intermediate_input_selector = 'input[data-testid="ocfEnterTextTextInput"]'
                if await page.locator(intermediate_input_selector).is_visible(timeout=5000):  # Shorter timeout for visibility check
                    logger.info("(Async) Intermediate input field found. Entering username/email again.")
                    verification_input = self.config.x_email or self.config.x_username
                    await page.locator(intermediate_input_selector).fill(verification_input)
                    await page.locator(intermediate_input_selector).press('Enter')
                    await page.wait_for_timeout(3000)
                    await page.wait_for_selector(password_selector, timeout=self.config.playwright_action_timeout_ms)
                else:
                    await self._screenshot_on_error(page, "x_login_password_field_missing")
                    raise PlaywrightError("Password field did not appear after username. Login flow may have changed or an error occurred.")
            
            logger.info("(Async) Entering password...")
            await page.locator(password_selector).fill(self.config.x_password.get_secret_value())
            await page.locator(password_selector).press('Enter')

            logger.info("(Async) Waiting for login confirmation (e.g., navigation to home)...")
            await page.wait_for_url("https://x.com/home", timeout=self.config.playwright_nav_timeout_ms, wait_until="domcontentloaded")
            logger.info("(Async) X Login successful.")
            
            self._is_logged_in = True
            
            if self.config.playwright_use_auth_state:
                auth_file_path = Path(self.config.data_dir) / self.config.playwright_auth_state_filename
                logger.info(f"(Async) Playwright auth state persistence enabled. File: {auth_file_path}")
                try:
                    # Ensure parent directory exists for auth state file
                    await asyncio.to_thread(auth_file_path.parent.mkdir, parents=True, exist_ok=True)
                    await self._authenticated_context.storage_state(path=str(auth_file_path))
                    logger.info(f"(Async) Playwright authentication state saved to {auth_file_path}")
                except Exception as save_err:
                    logger.error(f"(Async) Failed to save Playwright authentication state: {save_err}")

        except PlaywrightTimeoutError as e:
            logger.error(f"(Async) Timeout during X login process: {e}")
            self._is_logged_in = False
            raise PlaywrightError(f"Timeout waiting during async login: {e}", original_exception=e)
        except PlaywrightErrorBase as e:
            logger.error(f"(Async) Playwright error during X login: {e}")
            self._is_logged_in = False
            raise PlaywrightError(f"Playwright error during async login: {e}", original_exception=e)
        except Exception as e:
            logger.error(f"(Async) Unexpected error during X login: {e}", exc_info=True)
            self._is_logged_in = False
            raise PlaywrightError(f"Unexpected error during async login: {e}", original_exception=e)
        finally:
            if page:
                await page.close()

    async def get_bookmark_urls(self) -> List[str]:
        """
        Fetches bookmark URLs from X.com using the async API.
        Handles login if not already performed.
        Uses configured timeouts and scroll parameters.
        """
        logger.info("Attempting to get bookmark URLs via Playwright (async)...")
        if not self._is_logged_in:
            logger.warning("Not logged in. Attempting login before fetching bookmarks.")
            try:
                await self.login_to_x()
                if not self._is_logged_in:
                    raise PlaywrightError("Automatic login attempt failed before fetching bookmarks.")
            except Exception as login_err:
                raise PlaywrightError(f"Failed to login before fetching bookmarks: {login_err}", original_exception=login_err) from login_err

        try:
            if not self._authenticated_context:
                raise PlaywrightError("Not logged in or no authenticated context available. Call login_to_x() first.")
            
            if not self.config.x_bookmarks_url:
                raise PlaywrightError("X Bookmarks URL not configured.")

            page = await self._authenticated_context.new_page()
            bookmarks_url_str = str(self.config.x_bookmarks_url)
            logger.info(f"(Async) Navigating to X Bookmarks page: {bookmarks_url_str}")
            await page.goto(bookmarks_url_str, timeout=self.config.playwright_nav_timeout_ms, wait_until='domcontentloaded')
            
            try:
                not_now_button_selector = 'div[role="dialog"] button:has-text("Not now")'
                if await page.locator(not_now_button_selector).is_visible(timeout=5000):  # Shorter timeout for this optional element
                    await page.locator(not_now_button_selector).click()
                    logger.info("(Async) Dismissed 'Not now' dialog.")
                    await page.wait_for_timeout(1000)
            except PlaywrightTimeoutError:
                logger.debug("(Async) 'Not now' dialog not found or not visible within timeout.")
            except Exception as e:
                logger.warning(f"(Async) Error trying to dismiss 'Not now' dialog: {e}")

            logger.info("(Async) Waiting for initial tweet content to load...")
            tweet_article_selector = 'article[data-testid="tweet"], article[role="article"]'
            await page.wait_for_selector(tweet_article_selector, timeout=self.config.playwright_action_timeout_ms)
            await page.wait_for_timeout(self.config.playwright_scroll_delay_ms // 2)  # Wait a bit for content to settle

            collected_urls = set()
            tweet_link_selector = f'{tweet_article_selector} a[href*="/status/"]'

            logger.info(f"(Async) Scrolling bookmarks page. Scroll pixels: 1000. Wait after scroll: {self.config.playwright_scroll_delay_ms}ms. No change tries: {self.config.playwright_max_no_change_scrolls}. Max scroll attempts: {self.config.playwright_max_scroll_attempts}.")
            
            previous_height = await page.evaluate("() => document.body.scrollHeight")
            no_change_tries = 0
            
            for scroll_attempt in range(self.config.playwright_max_scroll_attempts):
                current_links_on_page = await page.locator(tweet_link_selector).all()
                new_urls_this_pass = set()
                for link_handle in current_links_on_page:
                    try:
                        href = await link_handle.get_attribute('href', timeout=self.config.playwright_action_timeout_ms // 3)  # Shorter timeout for attribute
                        if href:
                            new_urls_this_pass.add(href)
                    except PlaywrightTimeoutError:
                        logger.warning(f"(Async) Timeout getting href for one link on scroll {scroll_attempt+1}. Skipping this link.")
                        continue
                    except Exception as e_link:
                        logger.warning(f"(Async) Error getting href for a link: {e_link}. Skipping.")
                        continue
                
                newly_added_count = len(new_urls_this_pass - collected_urls)
                collected_urls.update(new_urls_this_pass)

                logger.info(f"(Async) Scroll attempt {scroll_attempt + 1}/{self.config.playwright_max_scroll_attempts}. Found {newly_added_count} new links this pass. Total unique raw: {len(collected_urls)}.")

                await page.evaluate('window.scrollBy(0, 1000)')
                await page.wait_for_timeout(self.config.playwright_scroll_delay_ms)
                
                current_height = await page.evaluate("() => document.body.scrollHeight")
                
                if current_height == previous_height:
                    no_change_tries += 1
                    logger.info(f"(Async) Scroll height unchanged ({current_height}px). No change streak: {no_change_tries}/{self.config.playwright_max_no_change_scrolls}.")
                    if no_change_tries >= self.config.playwright_max_no_change_scrolls:
                        logger.info("(Async) No new content after multiple scroll attempts with no height change. Assuming end of dynamic content.")
                        break
                else:
                    no_change_tries = 0
                    previous_height = current_height
                    logger.debug(f"(Async) Scroll height changed to {current_height}px.")

            final_links_on_page = await page.locator(tweet_link_selector).all()
            for link_handle in final_links_on_page:
                try:
                    href = await link_handle.get_attribute('href', timeout=self.config.playwright_action_timeout_ms // 3)
                    if href:
                        collected_urls.add(href)
                except PlaywrightTimeoutError:
                    logger.warning("(Async) Timeout getting href for one link during final collection. Skipping.")
                    continue
                except Exception as e_link_final:
                    logger.warning(f"(Async) Error getting href for a link during final collection: {e_link_final}. Skipping.")
                    continue

            logger.info(f"(Async) --- STARTING FILTERING --- Raw links collected: {len(collected_urls)}")
            if logger.level == logging.DEBUG:  # Only log all raw URLs if debug is on
                for i, url in enumerate(list(collected_urls)[:200]):  # Log first 200 raw
                    logger.debug(f"  Raw URL {i+1}: {url}")

            valid_links = [link for link in collected_urls if isinstance(link, str)]
            logger.info(f"(Async) Filtering: After string type check: {len(valid_links)} links remain.")
            if len(collected_urls) - len(valid_links) > 0:
                logger.debug(f"  Removed non-string items: {collected_urls - set(valid_links)}")

            no_analytics_initial_count = len(valid_links)
            no_analytics = [link for link in valid_links if "/analytics" not in link]
            logger.info(f"(Async) Filtering: After removing '/analytics': {len(no_analytics)} links remain.")
            if no_analytics_initial_count - len(no_analytics) > 0:
                logger.debug(f"  Analytics links removed: {set(valid_links) - set(no_analytics)}")
            
            # Process directly from no_analytics now
            clean_links_input_count = len(no_analytics)  # Changed from no_photos_videos
            clean_links = []
            removed_by_aux_filter = set()
            malformed_links = set()

            for link in no_analytics:  # Changed from no_photos_videos
                base_link = link.split('?')[0]
                is_aux_link = any(aux in base_link for aux in ['/media_tags', '/retweets', '/likes', '/quotes', '/replies'])
                
                # Keep links with /photo/ or /video/ if they are part of a /status/ URL
                # The main check is that it's a /status/ link and not an auxiliary engagement link.
                if '/status/' in base_link and not is_aux_link:
                    if base_link.startswith("/"):
                        full_url = f"https://x.com{base_link}"
                        clean_links.append(full_url)
                    elif base_link.startswith("https://x.com") or base_link.startswith("https://twitter.com"):
                        clean_links.append(base_link)
                    else:
                        malformed_links.add(link)
                else:
                    if is_aux_link:
                        removed_by_aux_filter.add(link)
                    elif '/status/' not in base_link:  # Explicitly log links not containing /status/
                        logger.debug(f"  Link filtered out (not a /status/ link): {link}")
                        removed_by_aux_filter.add(link)  # Add to this set for summary logging
                    # Links that are /photo/ or /video/ but NOT part of a /status/ structure will be implicitly dropped here,
                    # which is usually correct as they aren't standalone "tweets" in the typical sense of a bookmark to a post.
                    # If a bookmark is literally just `x.com/username/status/123/video/1`, this logic should keep `x.com/username/status/123`.

            logger.info(f"(Async) Filtering: After removing auxiliary links (e.g. /replies, /likes) and ensuring it's a status link: {len(clean_links)} links remain.")
            if clean_links_input_count - len(clean_links) - len(malformed_links) > 0:
                logger.debug(f"  Auxiliary/non-status links removed: {removed_by_aux_filter}")
            if malformed_links:
                logger.debug(f"  Malformed/unexpected-prefix links skipped: {malformed_links}")

            final_unique_bookmarks = sorted(list(set(clean_links)))
            logger.info(f"(Async) --- FILTERING COMPLETE --- Final unique bookmark URLs: {len(final_unique_bookmarks)}.")
            if logger.level == logging.DEBUG and final_unique_bookmarks:
                for i, url in enumerate(final_unique_bookmarks[:20]):
                    logger.debug(f"  Final URL {i+1}: {url}")
            return final_unique_bookmarks

        except PlaywrightTimeoutError as e:
            logger.error(f"(Async) Timeout during bookmark fetching: {e}")
            await self._screenshot_on_error(page, "x_bookmarks_timeout")
            raise PlaywrightError(f"Timeout during async bookmark fetch: {e}", original_exception=e)
        except PlaywrightErrorBase as e:
            logger.error(f"(Async) Playwright error during bookmark fetching: {e}")
            await self._screenshot_on_error(page, "x_bookmarks_error")
            raise PlaywrightError(f"Playwright error during async bookmark fetch: {e}", original_exception=e)
        except Exception as e:
            logger.error(f"(Async) Unexpected error during bookmark fetching: {e}", exc_info=True)
            await self._screenshot_on_error(page, "x_bookmarks_unexpected_error")
            raise PlaywrightError(f"Unexpected error during async bookmark fetch: {e}", original_exception=e)
        finally:
            if page:
                await page.close()

    def _get_v1_like_high_res_url(self, url: str) -> str:
        """
        Converts a Twitter media URL to request a higher resolution version,
        inspired by V1 agent's get_high_res_url.
        Example: if URL has name=small, replace with name=orig.
        """
        if not url:
            return ""
        
        if "pbs.twimg.com/media/" in url:
            if "?name=" in url: # Checks if 'name' query param exists
                return re.sub(r"name=\w+", "name=orig", url)
            elif "?" in url: # Has other query params, append &name=orig
                return f"{url}&name=orig"
            else: # No query params, add ?name=orig
                return f"{url}?name=orig"
        # Basic handling for card images if they appear, similar to V1
        # This might need more specific selectors if card images are a primary target
        elif "card_img_url" in url and "pbs.twimg.com" in url: 
             return re.sub(r"\?.*$", "?format=jpg&name=orig", url)
        return url

    async def get_tweet_details_via_playwright(self, tweet_url: str) -> dict:
        """
        Fetches detailed information about a tweet from its URL using Playwright async API.
        Returns a list of media items with url, type, and alt_text.
        """
        page: Optional[Page] = None # Ensure page is defined for finally block
        if not self._playwright or not self._browser: # Essential check
            await self.initialize()
            if not self._playwright or not self._browser:
                logger.error("(Async) Playwright browser not initialized. Cannot scrape tweet details.")
                return {}

        context_to_use = self._browser # Default to a new context from the browser
        if self._is_logged_in and self._authenticated_context:
            logger.debug("(Async) Using authenticated context for tweet details.")
            context_to_use = self._authenticated_context
        elif not self._is_logged_in:
             logger.warning("(Async) Not logged in. Attempting to fetch tweet details using a fresh browser context. Details may be limited or fail.")
             # If not logged in, we'll create a new incognito-like context from the main browser instance.
             # This is implicitly handled if context_to_use remains self._browser for new_page().

        try:
            page = await context_to_use.new_page()
            tweet_url_str = str(tweet_url)
            await page.goto(tweet_url_str, timeout=self._nav_timeout_ms, wait_until="domcontentloaded")
            
            await page.wait_for_selector('article[data-testid="tweet"]', timeout=self.config.playwright_action_timeout_ms + 10000) 
            primary_tweet_element = page.locator('article[data-testid="tweet"]').first

            author_handle = ""
            author_name = ""
            author_id_from_url = None

            user_name_block = primary_tweet_element.locator('div[data-testid="User-Name"]')
            if await user_name_block.count() > 0:
                user_link_element = user_name_block.locator('a[href^="/"][dir="ltr"]')
                if await user_link_element.count() > 0:
                    user_link = user_link_element.first
                    href_attr = await user_link.get_attribute("href")
                    if href_attr:
                        author_id_from_url = href_attr.split('/')[-1]
                    
                    spans_in_user_link = await user_link.locator('span').all()
                    text_parts = [await span.inner_text() for span in spans_in_user_link if await span.is_visible()]
                    parsed_name = ""
                    parsed_handle = ""
                    for part in text_parts:
                        if part.startswith("@"):
                            parsed_handle = part[1:]
                        elif part.strip() and not parsed_name and "·" not in part and "Follow" not in part:
                            parsed_name = part.strip()
                    author_handle = parsed_handle
                    author_name = parsed_name or (author_handle or "")
                if not author_handle:
                    full_text_content = await user_name_block.first.inner_text()
                    lines = full_text_content.split('\n')
                    if lines:
                        author_name = lines[0].strip()
                        for line in lines:
                            if line.strip().startswith("@"):
                                author_handle = line.strip()[1:]
                                break
            logger.debug(f"(Async) Scraped Author - Handle: {author_handle}, Name: {author_name}")

            tweet_text = ""
            tweet_text_element = primary_tweet_element.locator('div[data-testid="tweetText"]')
            if await tweet_text_element.count() > 0:
                tweet_text = await tweet_text_element.first.inner_text()
            if not tweet_text:
                logger.debug("(Async) Primary text selector failed. Trying fallback 'div[lang].")
                tweet_text_lang_element = primary_tweet_element.locator('div[lang]')
                if await tweet_text_lang_element.count() > 0:
                    all_text_parts = [await tweet_text_lang_element.nth(i).inner_text() for i in range(await tweet_text_lang_element.count())]
                    tweet_text = "\n".join(all_text_parts).strip()
            logger.debug(f"(Async) Scraped Text (first 100 chars): {tweet_text[:100]}")

            scraped_media_items: List[Dict[str, Any]] = []
            image_elements = primary_tweet_element.locator('div[data-testid="photos"] img[src^="https://pbs.twimg.com/media/"], figure[data-testid="tweetPhoto"] img[src^="https://pbs.twimg.com/media/"]')
            for i in range(await image_elements.count()):
                img_element = image_elements.nth(i)
                src = await img_element.get_attribute("src")
                alt_text = await img_element.get_attribute("alt") or ""
                if src:
                    high_res_src = self._get_v1_like_high_res_url(src)
                    scraped_media_items.append({"url": high_res_src, "type": "image", "alt_text": alt_text})
            
            video_player_elements = primary_tweet_element.locator('div[data-testid="videoPlayer"]')
            for i in range(await video_player_elements.count()):
                video_container = video_player_elements.nth(i)
                video_tag = video_container.locator('video[src]')
                poster_url = None
                if await video_tag.count() > 0:
                    poster_url = await video_tag.first.get_attribute("poster")
                    video_src = await video_tag.first.get_attribute("src")
                    if video_src:
                         scraped_media_items.append({"url": video_src, "type": "video", "alt_text": None})
                if poster_url:
                    high_res_poster = self._get_v1_like_high_res_url(poster_url)
                    scraped_media_items.append({"url": high_res_poster, "type": "image", "alt_text": "Video poster"})
            logger.debug(f"(Async) Scraped {len(scraped_media_items)} media items.")

            original_text_urls = []
            if tweet_text:
                original_text_urls = list(set(re.findall(r'https?://t\.co/\w+', tweet_text)))
            logger.debug(f"(Async) Scraped {len(original_text_urls)} t.co URLs from text.")
            
            time_element = primary_tweet_element.locator('time[datetime]')
            created_at_iso = None
            if await time_element.count() > 0:
                datetime_attr = await time_element.first.get_attribute('datetime')
                if datetime_attr:
                    created_at_iso = datetime_attr
            logger.debug(f"(Async) Scraped Created At: {created_at_iso}")

            thread_tweets_data: List[Dict[str, Any]] = []
            
            tweet_id_match = re.search(r"/status/(\d+)", tweet_url_str)
            tweet_id = tweet_id_match.group(1) if tweet_id_match else tweet_url_str.split("/")[-1].split("?")[0]

            scraped_data = {
                "tweet_id": tweet_id, "text": tweet_text,
                "author_id": author_id_from_url or author_handle, 
                "author_handle": author_handle, "author_name": author_name,
                "created_at": created_at_iso, 
                "media_items": scraped_media_items,
                "urls": original_text_urls, 
                "source_url": tweet_url_str,
                "thread_tweets": thread_tweets_data,
            }
            if page: await page.close() # Close page after successful processing
            return scraped_data

        except PlaywrightTimeoutError as e:
            logger.error(f"(Async) Timeout scraping tweet page {tweet_url_str}: {e}")
            if page: await self._screenshot_on_error(page, f"tweet_scrape_timeout_{tweet_url_str.split('/')[-1]}")
            return {}
        except PlaywrightErrorBase as e: # Catch specific Playwright errors
            logger.error(f"(Async) Playwright error scraping tweet page {tweet_url_str}: {e}")
            if page: await self._screenshot_on_error(page, f"tweet_scrape_playwright_error_{tweet_url_str.split('/')[-1]}")
            return {}
        except Exception as e:
            logger.error(f"(Async) Unexpected error scraping tweet page {tweet_url_str}: {e}", exc_info=True)
            if page: await self._screenshot_on_error(page, f"tweet_scrape_unexpected_{tweet_url_str.split('/')[-1]}")
            return {}
        finally:
            if page and not page.is_closed(): # Ensure page is closed if not already
                await page.close()

    async def _screenshot_on_error(self, page: Page, screenshot_name: str):
        """Takes a screenshot on error for debugging."""
        try:
            screenshot_dir = self.config.data_dir / "debug_screenshots"
            await asyncio.to_thread(screenshot_dir.mkdir, parents=True, exist_ok=True)
            screenshot_path = screenshot_dir / f"{screenshot_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
            await page.screenshot(path=str(screenshot_path), full_page=True)
            logger.info(f"Screenshot saved to {screenshot_path} due to error.")
        except Exception as screenshot_e:
            logger.warning(f"Failed to save screenshot: {screenshot_e}")

    async def close(self):
        """Closes the Playwright browser and stops the Playwright instance if running."""
        logger.info("Closing PlaywrightClient resources (async)...")
        await asyncio.to_thread(self._sync_close)

    def _sync_close(self):
        """Synchronous close logic."""
        if self._authenticated_context:
            try:
                self._authenticated_context.close()
                logger.debug("Authenticated Playwright context closed.")
            except Exception as e:
                logger.warning(f"Error closing authenticated Playwright context: {e}")
            self._authenticated_context = None
        
        if self._browser:
            try:
                self._browser.close()
                logger.debug("Playwright browser closed.")
            except Exception as e:
                logger.warning(f"Error closing Playwright browser: {e}")
            self._browser = None

        if self._playwright:
            try:
                # self._playwright.stop() # stop() is not an async method on the async Playwright object.
                # For async, playwright instance doesn't need explicit stop usually,
                # browser context & browser closure is key.
                pass
            except Exception as e:
                logger.warning(f"Error stopping Playwright instance: {e}")
            self._playwright = None
        self._is_logged_in = False
        logger.info("PlaywrightClient resources closed.")
