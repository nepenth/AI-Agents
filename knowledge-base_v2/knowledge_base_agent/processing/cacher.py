import asyncio
import logging
import mimetypes
import os # Import os for pathsplitext
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, Tuple, List, TYPE_CHECKING
from urllib.parse import urlparse

from ..config import Config
from ..exceptions import CacherError, FileOperationError, HttpClientError
from ..interfaces.http_client import HttpClientManager
# from ..interfaces.playwright_client import PlaywrightClient # Needed if scraping tweet pages
from ..types import TweetData, MediaItem
from ..utils import web_utils, file_io
from .state import StateManager

# Import twscrape components
try:
    from twscrape import Tweet as TwscrapeTweet, User, AccountsPool as TwscrapeAccountsPool, gather
    from twscrape.logger import set_log_level
    TWITTER_API_ENABLED = True
except ImportError:
    TwscrapeAccountsPool = None
    TwscrapeTweet = None # Assign None to the runtime alias
    User = None
    gather = None
    TWITTER_API_ENABLED = False
    logging.getLogger(__name__).warning(
        "twscrape library not found. Tweet fetching functionality will be disabled."
        " Install it using: pip install twscrape"
    )

# Guard the import for type checking
if TYPE_CHECKING:
    from twscrape import AccountsPool as AccountsPoolType
    from twscrape import Tweet as TweetType # Import Tweet under TYPE_CHECKING

logger = logging.getLogger(__name__)
set_log_level("ERROR") # Make twscrape less verbose by default

# --- Real Tweet Fetching Implementation ---
async def _fetch_tweet_details_with_thread(
    tweet_id: str,
    config: Config,
    pool: "AccountsPoolType" # Expect pool as argument
) -> Optional[Dict[str, Any]]:
    """
    Fetches core tweet details and its thread using twscrape.

    Returns:
        A dictionary containing tweet details and thread info, or None if fetch fails.
        Keys include: 'tweet', 'thread_tweets'
    """
    if not TWITTER_API_ENABLED or pool is None:
        logger.error("twscrape is not available or pool initialization failed.")
        return None

    logger.debug(f"Fetching details for tweet ID: {tweet_id} using twscrape...")
    main_tweet: Optional["TweetType"] = None
    thread_tweets_data: List[Dict] = []

    try:
        # 1. Fetch the main tweet
        main_tweet_runtime = await pool.tweet_details(int(tweet_id))
        if not main_tweet_runtime:
            logger.warning(f"twscrape: Tweet details not found for ID {tweet_id}")
            return None # Tweet might be deleted or private

        # Assign to the type-hinted variable (optional but can help linters)
        main_tweet = main_tweet_runtime # Type checker knows main_tweet is now TweetType

        logger.debug(f"twscrape: Found main tweet by @{main_tweet.user.username}")

        # 2. Fetch the conversation thread *by the same author*
        author_id = main_tweet.user.id
        author_handle = main_tweet.user.username
        query = f"conversation_id:{tweet_id} from:{author_handle}"
        logger.debug(f"twscrape: Searching for thread replies with query: {query}")

        # Use the TYPE_CHECKING hint for List[TweetType]
        thread_replies: List["TweetType"] = []
        try:
            # Use gather for potential pagination, limit reasonably
            thread_replies_runtime = await gather(pool.search(query, limit=50))
            thread_replies = thread_replies_runtime # Assign to type-hinted variable
        except Exception as search_err:
            # Often happens if conversation_id points to a very old tweet not in recent index
            logger.warning(f"twscrape: Failed to search for thread replies for conversation {tweet_id} (may be too old or search failed): {search_err}")
            # Proceed with just the main tweet


        if thread_replies:
            logger.debug(f"twscrape: Found {len(thread_replies)} potential replies in conversation.")
            # Filter replies: must be by the original author AND be a reply *to a tweet within the thread chain*
            # This simple implementation just checks author ID and sorts by time, assuming direct replies form the thread.
            # More robust logic might be needed to trace reply chains accurately.
            valid_thread_tweets = [
                t for t in thread_replies
                if t.user.id == author_id and t.id != main_tweet.id # Ensure it's by the author and not the original tweet itself
            ]

            # Sort by creation time to approximate thread order
            valid_thread_tweets.sort(key=lambda t: t.date)

            for tt in valid_thread_tweets:
                 # Store relevant info from the thread tweet
                 thread_tweets_data.append({
                      "id": tt.id,
                      "text": tt.text,
                      "created_at": tt.date, # Already datetime object
                      "url": tt.url
                 })
            logger.info(f"twscrape: Identified {len(thread_tweets_data)} subsequent thread tweets by @{author_handle}.")


        # 3. Format output
        media_urls = [m.url for m in main_tweet.media if hasattr(m, 'url')] # Simple URL list

        return {
            "tweet_id": str(main_tweet.id),
            "text": main_tweet.text,
            "author_id": str(main_tweet.user.id),
            "author_handle": main_tweet.user.username,
            "author_name": main_tweet.user.displayname,
            "created_at": main_tweet.date, # Already datetime object
            "media_urls": media_urls,
            "source_url": main_tweet.url,
            "thread_tweets": thread_tweets_data, # Include thread info
        }

    except Exception as e:
        logger.error(f"twscrape: Error fetching details or thread for tweet {tweet_id}: {e}", exc_info=True)
        # Optionally check error type (e.g., network, auth, not found)
        return None # Signal failure


async def _download_media(
    media_url: str,
    target_dir: Path,
    http_client: HttpClientManager
) -> Optional[Tuple[Path, str]]:
    """Downloads a media file from a URL to the target directory."""
    try:
        # --- Ensure target directory exists ---
        # Moved ensure_dir_async here as it's better to check before request
        await file_io.ensure_dir_async(target_dir)

        logger.debug(f"Attempting to download media from {media_url}")

        # --- Make Request ---
        # Use stream=True implicitly handled by aiter_bytes in httpx v0.19+
        response = await http_client.request("GET", media_url, raise_for_status=True, timeout=30.0) # Increase timeout for media?

        # --- Determine Filename ---
        # Try to get filename from Content-Disposition first
        content_disposition = response.headers.get('content-disposition')
        filename = None
        if content_disposition:
            # Simple parse, might need 'requests.utils.parse_header_links' logic for robustness
            parts = content_disposition.split('filename=')
            if len(parts) > 1:
                filename = parts[1].strip('" ')
        # Fallback to URL parsing
        if not filename:
             parsed_url = urlparse(media_url)
             filename = Path(parsed_url.path).name
             if not filename: # Handle URLs ending in / or no path name
                 # Try to generate from URL structure or a default
                 filename = media_url.split('?')[0].split('/')[-1] or f"media_{int(time.time())}"


        local_path = target_dir / filename

        # --- Write File ---
        logger.debug(f"Saving media to {local_path}")
        async with aiofiles.open(local_path, mode='wb') as f:
            async for chunk in response.aiter_bytes():
                await f.write(chunk)

        # --- Determine Type & Extension (Post-Download) ---
        content_type = response.headers.get('content-type')
        media_type = "unknown"
        current_ext = os.path.splitext(filename)[1]

        if content_type:
            media_type = content_type.split('/')[0]
            guessed_ext = mimetypes.guess_extension(content_type)

            if guessed_ext and guessed_ext.lower() != current_ext.lower():
                try:
                    new_path = local_path.with_suffix(guessed_ext)
                    # Avoid renaming if file with new extension already exists (rare case)
                    if not await aiofiles.os.path.exists(new_path):
                         logger.info(f"Renaming downloaded file based on Content-Type: {local_path.name} -> {new_path.name}")
                         await aiofiles.os.rename(local_path, new_path)
                         local_path = new_path
                    else:
                         logger.warning(f"Skipping rename, file already exists: {new_path}")
                except Exception as rename_err:
                    logger.warning(f"Failed to rename media file {local_path.name} to extension {guessed_ext}: {rename_err}")

        logger.info(f"Successfully downloaded media: {media_url} -> {local_path.name} (Type: {media_type})")
        return local_path, media_type

    # --- Error Handling ---
    except httpx.HTTPStatusError as e:
         # Log specific status errors differently
         logger.error(f"HTTP error {e.response.status_code} downloading media from {media_url}")
         return None # Don't cleanup local_path as write likely didn't happen
    except (HttpClientError, FileOperationError, OSError) as e:
        logger.error(f"Failed to download or save media from {media_url}: {e}")
        # Clean up potentially partially downloaded file
        if 'local_path' in locals() and await aiofiles.os.path.exists(local_path):
             try: await aiofiles.os.remove(local_path)
             except OSError: pass
        return None
    except Exception as e:
        logger.error(f"Unexpected error downloading media {media_url}: {e}", exc_info=True)
        if 'local_path' in locals() and await aiofiles.os.path.exists(local_path):
             try: await aiofiles.os.remove(local_path)
             except OSError: pass
        return None

# Add imports needed by download function
import httpx
import time
import aiofiles.os


async def validate_cache(tweet_data: TweetData, config: Config) -> bool:
    """Validates if the necessary data and media files exist for a cached tweet."""
    # Check core data fields - use combined_text and author_id
    if not all([tweet_data.tweet_id, tweet_data.combined_text, tweet_data.created_at, tweet_data.source_url, tweet_data.author_id]):
        logger.warning(f"Cache validation failed for {tweet_data.tweet_id}: Missing core data fields (ID, combined_text, created_at, source_url, author_id).")
        return False

    media_cache_dir = config.data_dir / "media_cache"
    for item in tweet_data.media_items:
        if not item.local_path:
            logger.warning(f"Cache validation failed for {tweet_data.tweet_id}: Media item {item.original_url} has no local path.")
            return False
        # Ensure path is absolute or resolve relative to media_cache_dir/tweet_id
        full_path = item.local_path
        if not full_path.is_absolute():
             full_path = (media_cache_dir / tweet_data.tweet_id / item.local_path).resolve()

        if not await aiofiles.os.path.exists(full_path):
            logger.warning(f"Cache validation failed for {tweet_data.tweet_id}: Media file not found at {full_path} (from original URL {item.original_url})")
            return False

    logger.debug(f"Cache validation passed for tweet {tweet_data.tweet_id}")
    return True


async def cache_tweet(
    tweet_id: str,
    tweet_data: TweetData,
    config: Config,
    http_client: HttpClientManager,
    state_manager: StateManager,
    # Add twscrape_pool parameter
    twscrape_pool: Optional["AccountsPoolType"] = None,
):
    """
    Performs the caching phase using twscrape: fetches details & thread,
    expands URLs, downloads media, and validates. Requires a pre-initialized
    twscrape_pool.
    """
    if not TWITTER_API_ENABLED:
         raise CacherError(tweet_id, "twscrape library not installed or failed to import.")
    # --- Check if pool was passed ---
    if not twscrape_pool:
        raise CacherError(tweet_id, "twscrape pool was not provided to cache_tweet function.")

    media_cache_dir = config.data_dir / "media_cache"
    tweet_detail = None

    try:
        # 1. Fetch Core Tweet Details & Thread (use passed pool)
        logger.info(f"Caching tweet: {tweet_id} using provided twscrape pool...")
        tweet_detail = await _fetch_tweet_details_with_thread(tweet_id, config, twscrape_pool)
        if not tweet_detail:
            raise CacherError(tweet_id=tweet_id, message="Failed to fetch core tweet details or thread via twscrape.")

        # --- Update TweetData ---
        tweet_data.text = tweet_detail.get("text")
        tweet_data.author_id = tweet_detail.get("author_id") # Added
        tweet_data.author_handle = tweet_detail.get("author_handle")
        tweet_data.author_name = tweet_detail.get("author_name")
        tweet_data.source_url = tweet_detail.get("source_url")
        tweet_data.thread_tweets = tweet_detail.get("thread_tweets", []) # Added

        if created_at_dt := tweet_detail.get("created_at"): # Already datetime
             tweet_data.created_at = created_at_dt
        else:
             logger.warning(f"Missing created_at timestamp for tweet {tweet_id}")
             tweet_data.created_at = None # Explicitly set None

        tweet_data.media_items = [] # Reset before adding potentially new ones

        # --- Calculate combined_text (or let validator handle it) ---
        # Trigger validator by creating a new instance or calling manually?
        # Pydantic v2 calls validators on assignment, so this should be okay.
        # Or call explicitly: tweet_data = tweet_data.compute_combined_text() # If validator doesn't run automatically

        # 2. Expand Shortened URLs (in combined text)
        # --- Improved URL Extraction ---
        all_text_content = tweet_data.text or ""
        for thread_part in tweet_data.thread_tweets:
             all_text_content += "\n" + thread_part.get("text", "")

        # Regex to find HTTP/HTTPS URLs (adjust if needed for more complex cases)
        url_pattern = re.compile(r'https?://[^\s<>"]+|www\.[^\s<>"]+')
        found_urls = url_pattern.findall(all_text_content)

        expansion_tasks = {}
        # Expand only potentially shortened URLs (e.g., t.co) or all? Let's try all for now.
        for url in set(found_urls): # Process unique URLs
             # Check if it looks like a shorten-able URL or one we haven't expanded
             # Basic check: if it doesn't have a long path, it *might* be shortened.
             parsed = urlparse(url)
             # Let's just try expanding any URL not already expanded for simplicity,
             # web_utils handles non-redirects gracefully.
             if url not in tweet_data.expanded_urls and web_utils.is_valid_url(url):
                  expansion_tasks[url] = web_utils.expand_url_async(
                       url, client=await http_client.get_client()
                  )

        if expansion_tasks:
             logger.debug(f"Attempting to expand {len(expansion_tasks)} URLs for {tweet_id}")
             results = await asyncio.gather(*expansion_tasks.values(), return_exceptions=True)
             expanded_count = 0
             for i, original_url in enumerate(expansion_tasks.keys()):
                  result = results[i]
                  if isinstance(result, str):
                       # Store expansion only if it's different from original
                       if result != original_url:
                            tweet_data.expanded_urls[original_url] = result
                            expanded_count += 1
                       # else: logger.debug(f"URL did not expand: {original_url}")
                  elif isinstance(result, Exception): # Log expansion errors
                       logger.warning(f"Failed to expand URL {original_url} for tweet {tweet_id}: {result}")
             if expanded_count > 0:
                  logger.info(f"Expanded {expanded_count} URLs for tweet {tweet_id}")


        # 3. Download Media
        media_urls = tweet_detail.get("media_urls", [])
        download_tasks = []
        tweet_media_dir = media_cache_dir / tweet_id # Store media in subdirs per tweet
        for media_url in media_urls:
            download_tasks.append(
                 _download_media(media_url, tweet_media_dir, http_client)
            )

        if download_tasks:
            logger.debug(f"Downloading {len(download_tasks)} media items for {tweet_id}")
            media_results = await asyncio.gather(*download_tasks, return_exceptions=True)
            for i, result in enumerate(media_results): # Iterate with original URL index
                 original_media_url = media_urls[i] # Get corresponding original URL
                 if isinstance(result, tuple) and result[0] is not None:
                     local_path, media_type = result
                     # Store path relative to media_cache_dir/tweet_id
                     relative_path = local_path.relative_to(tweet_media_dir)
                     tweet_data.media_items.append(MediaItem(original_url=original_media_url, local_path=relative_path, type=media_type))
                 elif result is not None: # Error occurred during download
                     logger.warning(f"Media download failed for {original_media_url} (Tweet {tweet_id}).") # Logged in _download_media

        # 4. Validate Cache
        # Trigger combined_text computation before validation if needed
        tweet_data = TweetData.model_validate(tweet_data.model_dump()) # Re-validate to run model validator

        is_valid = await validate_cache(tweet_data, config)
        tweet_data.cache_complete = is_valid

        if not is_valid:
             logger.warning(f"Caching completed for tweet {tweet_id}, but validation failed.")
             tweet_data.mark_failed("Caching", "Cache validation failed after processing.")
        else:
             logger.info(f"Caching successfully completed and validated for tweet {tweet_id}.")
             if tweet_data.failed_phase == "Caching": # Clear error if re-processing succeeded
                 tweet_data.error_message = None
                 tweet_data.failed_phase = None

    # --- Error Handling ---
    except Exception as e:
        logger.error(f"Error during caching phase for tweet {tweet_id}: {e}", exc_info=True)
        tweet_data.cache_complete = False
        if not isinstance(e, CacherError):
            tweet_data.mark_failed("Caching", e)
        else:
            tweet_data.mark_failed("Caching", str(e)) # Use message from CacherError

    # --- Cleanup ---
    finally:
        # Always update the state manager
        state_manager.update_tweet_data(tweet_id, tweet_data)
        # No pool cleanup needed here, handled by caller (pipeline runner)

# Import re for URL expansion regex
import re
