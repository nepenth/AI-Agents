import logging
import re
from typing import Set, Optional, List, Dict, Any

from ..config import Config
from ..interfaces.playwright_client import PlaywrightClient
from ..exceptions import FetcherError
from ..types import TweetData

logger = logging.getLogger(__name__)

# Regex to find tweet IDs in URLs like https://x.com/username/status/1234567890
# Handles potential query parameters or fragments
TWEET_ID_REGEX = re.compile(r"/status/(\d+)")

class Fetcher:
    """
    Responsible for acquiring new tweet/item IDs for processing.
    Currently focuses on fetching tweet IDs from X/Twitter bookmarks via Playwright.
    """

    def __init__(
        self,
        config: Config,
        playwright_client: Optional[PlaywrightClient],
    ):
        self.config = config
        self.playwright_client = playwright_client
        logger.info("Fetcher initialized.")

    async def _fetch_tweet_sources_from_bookmarks(self) -> Dict[str, str]:
        """
        Uses Playwright to navigate to the X bookmarks page and extract tweet IDs
        and their full source URLs.
        Returns a dictionary mapping tweet_id to its source_url.
        """
        if not self.playwright_client:
            logger.warning("Playwright client is not available for Fetcher, cannot fetch bookmarks.")
            return {}

        logger.info(f"[Fetcher] Attempting to get bookmark URLs via Playwright client...")
        tweet_sources_found: Dict[str, str] = {}

        try:
            tweet_urls_from_playwright = await self.playwright_client.get_bookmark_urls()

            if not tweet_urls_from_playwright:
                logger.warning("[Fetcher] Playwright client returned no bookmark URLs.")
                return {}

            logger.info(f"[Fetcher] Found {len(tweet_urls_from_playwright)} potential bookmark links from Playwright. Extracting tweet IDs and URLs...")

            for full_url_to_parse in tweet_urls_from_playwright:
                if isinstance(full_url_to_parse, str):
                    match = TWEET_ID_REGEX.search(full_url_to_parse)
                    if match:
                        tweet_id = match.group(1)
                        if tweet_id not in tweet_sources_found:
                            tweet_sources_found[tweet_id] = full_url_to_parse
                        else:
                            logger.debug(f"[Fetcher] Tweet ID {tweet_id} already found with URL {tweet_sources_found[tweet_id]}. Skipping duplicate URL {full_url_to_parse}")
                    else:
                        logger.debug(f"[Fetcher] Did not extract tweet ID from potential bookmark URL: {full_url_to_parse}")
                else:
                    logger.warning(f"[Fetcher] Received unexpected data format for bookmark URL: {full_url_to_parse} (expected str).")

            logger.info(f"[Fetcher] Extracted {len(tweet_sources_found)} unique tweet_id-URL pairs from {len(tweet_urls_from_playwright)} potential links.")
            return tweet_sources_found

        except FetcherError:
            raise
        except Exception as e:
            logger.error(f"[Fetcher] Error calling Playwright client or parsing bookmark URLs: {e}", exc_info=True)
            raise FetcherError(f"Failed to get/parse bookmarks: {e}") from e

    async def get_tweet_sources_to_process(self, run_preferences: Dict[str, Any]) -> Dict[str, str]:
        """
        Main method to get all new tweet IDs and their source URLs that need processing.
        Considers run preferences (e.g., skip_fetch).
        Returns a dictionary mapping tweet_id to source_url.
        """
        new_tweet_sources: Dict[str, str] = {}

        if run_preferences.get('skip_fetch', False):
            logger.info("[Fetcher] Skipping fetch phase based on run preferences.")
            return new_tweet_sources

        if self.playwright_client and self.config.x_username and self.config.x_password and self.config.x_bookmarks_url:
            logger.info("[Fetcher] Attempting to fetch new tweet sources from X Bookmarks...")
            try:
                bookmark_sources = await self._fetch_tweet_sources_from_bookmarks()
                new_tweet_sources.update(bookmark_sources)
                logger.info(f"[Fetcher] Found {len(bookmark_sources)} tweet_id-URL pairs from X Bookmarks.")
            except FetcherError as e:
                logger.error(f"[Fetcher] Error fetching bookmarks: {e}")
            except Exception as e:
                logger.error(f"[Fetcher] Unexpected error during bookmark fetching: {e}", exc_info=True)
        else:
            logger.info("[Fetcher] Bookmark fetching skipped: Playwright client not available or X credentials/URL missing.")
        
        if not new_tweet_sources:
            logger.warning("[Fetcher] No new tweet sources found in this fetch cycle.")
        else:
            logger.info(f"[Fetcher] Total new unique tweet_id-URL pairs acquired for processing: {len(new_tweet_sources)}")

        return new_tweet_sources
