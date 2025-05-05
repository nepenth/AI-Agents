import logging
import re
from typing import Set, Optional

from ..config import Config
from ..interfaces.playwright_client import PlaywrightClient
from ..exceptions import FetcherError

logger = logging.getLogger(__name__)

# Regex to extract tweet ID from various Twitter/X URL formats
TWEET_ID_REGEX = re.compile(r".*/status(?:es)?/(\d+)")

def extract_tweet_id_from_url(url: str) -> Optional[str]:
    """Extracts the tweet ID from a URL string."""
    match = TWEET_ID_REGEX.search(url)
    if match:
        return match.group(1)
    logger.debug(f"Could not extract tweet ID from URL: {url}")
    return None

async def fetch_bookmark_tweet_ids(config: Config, playwright_client: PlaywrightClient) -> Set[str]:
    """
    Fetches bookmark URLs using Playwright and extracts tweet IDs.

    Args:
        config: The application configuration.
        playwright_client: An initialized PlaywrightClient instance.

    Returns:
        A set of unique tweet IDs found in bookmarks.

    Raises:
        FetcherError: If fetching or ID extraction fails significantly.
    """
    logger.info("Fetching bookmarks via Playwright...")
    if not playwright_client:
        raise FetcherError("Playwright client is required for fetching bookmarks but was not provided.")
    if not config.fetch_bookmarks_enabled:
        logger.info("Bookmark fetching is disabled in configuration.")
        return set()

    try:
        # Assuming PlaywrightClient handles login implicitly or has a separate login method called before this
        # bookmark_urls = await playwright_client.fetch_bookmark_urls(scroll_limit=10) # Adjust scroll limit as needed
        # Using the mock method name from the pipeline temporarily, replace with actual call
        bookmark_urls = await playwright_client.fetch_bookmark_urls(scroll_limit=10) # Use actual method

        tweet_ids: Set[str] = set()
        for url in bookmark_urls:
            tweet_id = extract_tweet_id_from_url(url)
            if tweet_id:
                tweet_ids.add(tweet_id)
            else:
                logger.warning(f"Could not extract tweet ID from bookmark URL: {url}")

        logger.info(f"Fetched {len(bookmark_urls)} bookmark URLs, extracted {len(tweet_ids)} unique tweet IDs.")
        return tweet_ids

    except Exception as e:
        logger.error(f"Failed to fetch bookmarks or extract tweet IDs: {e}", exc_info=True)
        raise FetcherError(f"Bookmark fetching failed: {e}", original_exception=e) from e

# Note: fetch_core_tweet_data mentioned in the plan seems better placed within the Cacher
# as it needs to happen *for each tweet* being cached, not as a separate bulk phase.
