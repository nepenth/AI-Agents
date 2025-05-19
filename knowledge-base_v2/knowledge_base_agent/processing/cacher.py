import asyncio
import logging
import mimetypes
import os # Import os for pathsplitext
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, Tuple, List, TYPE_CHECKING, Set
from urllib.parse import urlparse
import aiohttp # Import for URL expansion
import time
import uuid
import re 
import aiofiles
import aiofiles.os

from ..config import Config
from ..exceptions import CacherError, FileOperationError, HttpClientError
from ..interfaces.http_client import HttpClientManager
from ..interfaces.playwright_client import PlaywrightClient # Ensure this is imported
from ..types import TweetData, MediaItem
from ..utils import web_utils, file_io
from .state import StateManager

logger = logging.getLogger(__name__)

# --- URL Expansion Helper ---
async def _expand_url(url: str, session: aiohttp.ClientSession) -> str:
    """Expand t.co URLs to their final destination using a shared session."""
    if not url or (not url.startswith("https://t.co/") and not url.startswith("http://t.co/")):
        return url
    try:
        # Use HEAD request for efficiency, follow redirects
        async with session.head(url, allow_redirects=True, timeout=10) as response: 
            final_url = str(response.url)
            logger.debug(f"Expanded {url} -> {final_url}")
            return final_url
    except asyncio.TimeoutError:
        logger.warning(f"Timeout expanding URL {url}")
        return url
    except aiohttp.ClientError as e:
        logger.warning(f"Could not expand {url}: {type(e).__name__}")
        return url
    except Exception as e:
        logger.warning(f"Unexpected error expanding URL {url}: {e}")
        return url

# Add imports needed by download function
import httpx
import aiofiles.os


async def validate_cache(tweet_data: TweetData, config: Config) -> bool:
    """Validates if the necessary data and media files exist for a cached tweet."""
    # Check core data fields - use combined_text and author_id
    if not all([tweet_data.tweet_id, tweet_data.combined_text, tweet_data.created_at, tweet_data.source_url, tweet_data.author_id]):
        logger.warning(f"Cache validation failed for {tweet_data.tweet_id}: Missing core data fields (ID, combined_text, created_at, source_url, author_id).")
        return False

    base_media_cache_dir = config.data_dir / "media_cache"
    for item in tweet_data.media_items:
        if not item.local_path:
            logger.warning(f"Cache validation failed for {tweet_data.tweet_id}: Media item {item.original_url} has no local path.")
            return False
        
        # item.local_path is now expected to be relative like "tweet_id/filename.ext"
        full_path = (base_media_cache_dir / item.local_path).resolve()

        if not await aiofiles.os.path.exists(full_path):
            logger.warning(f"Cache validation failed for {tweet_data.tweet_id}: Media file not found at {full_path} (from original URL {item.original_url}, relative path: {item.local_path})")
            return False

    logger.debug(f"Cache validation passed for tweet {tweet_data.tweet_id}")
    return True


async def _download_media(
    media_url: str,
    # download_dir is specific to the tweet (e.g., .../media_cache/tweet_id)
    download_dir: Path, 
    http_client_manager: HttpClientManager,
    # base_media_cache_dir is the root (e.g., .../media_cache)
    base_media_cache_dir: Path, 
    max_size_bytes: int = 50 * 1024 * 1024  # Max 50MB per media file
) -> Optional[Tuple[Path, str]]: # Returns RELATIVE path and content_type
    """
    Downloads a media file from a URL to a specified directory.
    Includes a fallback for pbs.twimg.com URLs if initial download with query params fails.

    Args:
        media_url: The URL of the media to download.
        download_dir: The tweet-specific directory Path object where the file should be saved.
        http_client_manager: Instance of HttpClientManager to make requests.
        base_media_cache_dir: The base media cache directory (used to make the returned path relative).
        max_size_bytes: Maximum allowed size for the download.

    Returns:
        A tuple (Path, str) of the downloaded file's RELATIVE Path (to base_media_cache_dir) 
        and its determined media type (e.g., 'image/jpeg'),
        or None if the download fails or the file is too large.
    """
    if not media_url:
        logger.warning("Download attempt_download_media with empty URL.")
        return None

    original_media_url_for_logging = media_url # Store for final error logging if all attempts fail

    async def attempt_download(current_url: str) -> Tuple[Optional[Path], Optional[str], Optional[httpx.Response]]:
        # Helper to avoid code duplication for download attempt
        # Returns: (ABSOLUTE file_path, content_type, response_object)
        try:
            await file_io.ensure_dir_async(download_dir) # download_dir is absolute tweet-specific path
            client = await http_client_manager.get_client()
            response = await client.get(current_url, timeout=30.0, follow_redirects=True)
            
            if response.status_code >= 400:
                logger.debug(f"HTTP status {response.status_code} for {current_url}. Will be handled by caller for potential fallback.")
                return None, None, response

            content_length = response.headers.get("Content-Length")
            if content_length and int(content_length) > max_size_bytes:
                logger.warning(f"Media file {current_url} is too large ({content_length} bytes > {max_size_bytes}). Skipping download.")
                return None, None, response

            parsed_url = urlparse(current_url)
            original_filename_from_path = Path(parsed_url.path).name
            
            content_type = response.headers.get("Content-Type", "application/octet-stream")
            extension_from_mime = mimetypes.guess_extension(content_type) or ""
            
            if original_filename_from_path:
                base, orig_ext_from_path = os.path.splitext(original_filename_from_path)
                safe_base = "".join(c if c.isalnum() or c in ['-', '_'] else '_' for c in base)
                final_extension = extension_from_mime if extension_from_mime and extension_from_mime != ".jpe" else (orig_ext_from_path or extension_from_mime or ".dat")
                if final_extension == ".jpe": final_extension = ".jpg"
            else:
                safe_base = f"media_{current_url[-20:].replace('/', '_').replace('?', '_').replace('&', '_')}"
                final_extension = extension_from_mime or ".dat"

            safe_base = safe_base[:100] 
            download_filename = f"{safe_base}{final_extension}"
            absolute_file_path = download_dir / download_filename # This is the absolute path
            
            counter = 0
            temp_path = absolute_file_path
            while await aiofiles.os.path.exists(temp_path):
                counter += 1
                temp_path = download_dir / f"{safe_base}_{counter}{final_extension}"
            absolute_file_path = temp_path

            downloaded_size = len(response.content)
            if downloaded_size == 0:
                logger.warning(f"Media file {current_url} downloaded with zero size. Skipping save.")
                return None, None, response
            if downloaded_size > max_size_bytes:
                logger.warning(f"Media file {current_url} exceeded max size ({max_size_bytes} bytes) after download. Skipping save.")
                return None, None, response 
            
            async with aiofiles.open(absolute_file_path, "wb") as f:
                await f.write(response.content)
            
            logger.info(f"Successfully downloaded {current_url} to {absolute_file_path} ({downloaded_size} bytes). Content-Type: {content_type}")
            return absolute_file_path, content_type, response
        except httpx.RequestError as e:
            logger.error(f"Request error downloading {current_url}: {type(e).__name__} - {e}")
            return None, None, None
        except FileOperationError as e:
            logger.error(f"File operation error during media download for {current_url}: {e}")
            return None, None, None
        except Exception as e:
            logger.error(f"Unexpected error during attempt_download for {current_url}: {e}", exc_info=True)
            return None, None, None

    # --- Main download logic with fallback ---
    # attempt_download returns absolute_file_path
    absolute_file_path, content_type, response_obj = await attempt_download(media_url)

    if absolute_file_path and content_type:
        relative_file_path = absolute_file_path.relative_to(base_media_cache_dir)
        return relative_file_path, content_type # Success on first try

    if response_obj and response_obj.status_code >= 400 and "pbs.twimg.com/media/" in media_url:
        parsed_url_for_fallback = urlparse(media_url)
        if parsed_url_for_fallback.query and any(qp in parsed_url_for_fallback.query for qp in ["format=", "name="]):
            base_pbs_url = parsed_url_for_fallback._replace(query="").geturl()
            
            if base_pbs_url != media_url:
                logger.info(f"Initial download for {media_url} failed (status {response_obj.status_code}). "
                            f"Attempting fallback with base URL: {base_pbs_url}")
                # Fallback also returns absolute_file_path
                absolute_file_path_fallback, content_type_fallback, response_obj_fallback = await attempt_download(base_pbs_url)
                
                if absolute_file_path_fallback and content_type_fallback:
                    relative_file_path_fallback = absolute_file_path_fallback.relative_to(base_media_cache_dir)
                    return relative_file_path_fallback, content_type_fallback # Success on fallback
                
                if response_obj_fallback and response_obj_fallback.status_code >= 400:
                     logger.warning(f"Fallback download for {base_pbs_url} also failed with status {response_obj_fallback.status_code}.")
                elif not response_obj_fallback and not absolute_file_path_fallback:
                     logger.warning(f"Fallback download for {base_pbs_url} also failed (request/file error). Logging original error for {original_media_url_for_logging}.")
            else:
                logger.debug(f"Skipping fallback for {media_url} as base URL is the same or no relevant query params to strip.")

    if response_obj and response_obj.status_code >=400:
         logger.error(f"HTTP error downloading {original_media_url_for_logging}: {response_obj.status_code} - {response_obj.reason_phrase} (after any fallbacks). URL was: {media_url}")
    
    return None


async def cache_tweet(
    tweet_id: str,
    tweet_data: TweetData,
    config: Config,
    http_client: HttpClientManager,
    state_manager: StateManager,
    playwright_client: PlaywrightClient,
    run_only_phase: str = 'Full',
    is_fetching_bookmarks: bool = False
):
    """
    Processes a single tweet: fetches details, expands URLs, downloads media,
    and updates the TweetData object. Uses PlaywrightClient for tweet details.
    """
    logger.info(f"Caching tweet ID: {tweet_id}. Current cache_complete: {tweet_data.cache_complete}")
    tweet_successfully_cached_this_run = True

    # 1. Fetch Core Tweet Data (if needed) using PlaywrightClient
    raw_details_dict: Optional[Dict[str, Any]] = tweet_data.raw_tweet_details 
    
    if not raw_details_dict: 
        logger.debug(f"Fetching raw details for tweet {tweet_id} via PlaywrightClient.")
        if not tweet_data.source_url:
            # Infer URL from tweet_id if not available
            inferred_url = f"https://x.com/unknown/status/{tweet_id}"
            logger.info(f"Inferring URL for tweet {tweet_id} as {inferred_url} since source_url is missing.")
            tweet_data.source_url = inferred_url
            # Do not mark as failed; proceed with inferred URL
        if not is_fetching_bookmarks and run_only_phase == 'Caching' and not playwright_client._is_logged_in:
            logger.info(f"Skipping Playwright fetch for tweet {tweet_id} as operation does not involve fetching bookmarks and client is not logged in. Proceeding with available data or inferred URL.")
            # Attempt to fetch only if client is logged in or during bookmark fetching
        else:
            try:
                # Call Playwright client with the full source_url
                logger.info(f"Attempting to fetch details for tweet {tweet_id} from {tweet_data.source_url}.")
                tweet_page_details = await playwright_client.get_tweet_details_via_playwright(tweet_url=tweet_data.source_url)

                if tweet_page_details and tweet_page_details.get("text"):
                    raw_details_dict = tweet_page_details 
                    tweet_data.raw_tweet_details = raw_details_dict

                    tweet_data.text = raw_details_dict.get("text")
                    # Prefer author_id from playwright if available, else fallback to handle
                    tweet_data.author_id = raw_details_dict.get("author_id") or raw_details_dict.get("author_handle")
                    tweet_data.author_handle = raw_details_dict.get("author_handle")
                    tweet_data.author_name = raw_details_dict.get("author_name")
                    
                    # Use "created_at" key for timestamp, consistent with playwright_client scraping
                    raw_timestamp = raw_details_dict.get("created_at") 
                    if isinstance(raw_timestamp, datetime):
                        tweet_data.created_at = raw_timestamp.isoformat()
                    elif isinstance(raw_timestamp, str):
                        tweet_data.created_at = raw_timestamp 
                    else: 
                        logger.warning(f"Timestamp for {tweet_id} from Playwright is in unexpected format: {type(raw_timestamp)}. Setting to None.")
                        tweet_data.created_at = None

                    # Ensure source_url from Playwright (which should be the input tweet_url) is stored if it wasn't already the same
                    fetched_source_url = raw_details_dict.get("source_url")
                    if fetched_source_url and fetched_source_url != tweet_data.source_url:
                        logger.debug(f"Updating source_url for {tweet_id} from {tweet_data.source_url} to {fetched_source_url} based on Playwright result.")
                        tweet_data.source_url = fetched_source_url
                    
                    tweet_data.thread_tweets = [] 

                    # Process new media_items structure from PlaywrightClient
                    scraped_media_list = raw_details_dict.get("media_items", [])
                    new_media_items_list = []
                    for m_data in scraped_media_list:
                        if m_data.get("url"):
                            new_media_items_list.append(
                                MediaItem(
                                    original_url=m_data.get("url"),
                                    type=m_data.get("type"),
                                    alt_text=m_data.get("alt_text")
                                )
                            )
                    tweet_data.media_items = new_media_items_list
                    
                    tweet_data.original_urls = [] 
                    # Use "urls" key from Playwright details for t.co links, fallback to regex on text
                    tco_links_from_playwright = raw_details_dict.get("urls", [])
                    if tco_links_from_playwright:
                         tweet_data.original_urls.extend(list(set(tco_links_from_playwright)))
                    elif tweet_data.text: # Fallback if playwright didn't provide "urls"
                        found_tco = re.findall(r'https?://t\.co/\w+', tweet_data.text)
                        tweet_data.original_urls.extend(list(set(found_tco))) 

                    tweet_data = tweet_data.model_validate(tweet_data.model_dump()) 
                    logger.info(f"Successfully fetched raw details for tweet {tweet_id} (URL: {tweet_data.source_url}) via Playwright.")
                else:
                    logger.warning(f"Failed to fetch sufficient raw details for tweet {tweet_id} (URL: {tweet_data.source_url}) via Playwright (no details or no text).")
                    tweet_data.mark_failed("Caching", f"Failed to fetch tweet details for {tweet_id} (URL: {tweet_data.source_url}) via Playwright.")
                    tweet_successfully_cached_this_run = False
            except Exception as fetch_err:
                logger.error(f"Error during Playwright fetch for {tweet_id} (URL: {tweet_data.source_url}): {fetch_err}", exc_info=True)
                tweet_data.mark_failed("Caching", f"Playwright fetch error for {tweet_data.source_url}: {fetch_err}")
                tweet_successfully_cached_this_run = False
    
    elif raw_details_dict and not tweet_data.text: 
        logger.debug(f"Populating TweetData from existing raw_details_dict for {tweet_id}")
        tweet_data.text = raw_details_dict.get("text")
        tweet_data.author_id = str(raw_details_dict.get("author_id")) or raw_details_dict.get("author_handle") 
        tweet_data.author_handle = raw_details_dict.get("author_handle")
        tweet_data.author_name = raw_details_dict.get("author_name")
        raw_timestamp = raw_details_dict.get("created_at") # Corrected key
        if isinstance(raw_timestamp, datetime):
            tweet_data.created_at = raw_timestamp.isoformat()
        elif isinstance(raw_timestamp, str):
            tweet_data.created_at = raw_timestamp
        
        # Ensure source_url is populated if it was in raw_details and somehow missing on tweet_data
        if not tweet_data.source_url and raw_details_dict.get("source_url"):
            tweet_data.source_url = raw_details_dict.get("source_url")
        
        tweet_data.thread_tweets = raw_details_dict.get("thread_tweets", []) 
        
        # Process new media_items structure if populating from existing raw_details
        if not tweet_data.media_items and "media_items" in raw_details_dict:
             scraped_media_list_existing = raw_details_dict.get("media_items", [])
             new_media_items_list_existing = []
             for m_data_existing in scraped_media_list_existing:
                 if m_data_existing.get("url"):
                     new_media_items_list_existing.append(
                         MediaItem(
                             original_url=m_data_existing.get("url"),
                             type=m_data_existing.get("type"),
                             alt_text=m_data_existing.get("alt_text")
                         )
                     )
             tweet_data.media_items = new_media_items_list_existing
        
        # Use "urls" key from Playwright details for t.co links
        if not tweet_data.original_urls and "urls" in raw_details_dict: 
            tweet_data.original_urls = raw_details_dict.get("urls", [])
        elif not tweet_data.original_urls and tweet_data.text: 
            found_tco = re.findall(r'https?://t\.co/\w+', tweet_data.text)
            tweet_data.original_urls.extend(list(set(found_tco)))
        
        tweet_data = tweet_data.model_validate(tweet_data.model_dump())
        logger.info(f"Populated TweetData from existing details for {tweet_id}.")

    if not tweet_successfully_cached_this_run:
        # If fetching failed but we have some data, still attempt to proceed with caching
        if tweet_data.text or tweet_data.media_items or tweet_data.original_urls:
            logger.info(f"Proceeding with caching for tweet {tweet_id} using available data despite fetch failure.")
            tweet_successfully_cached_this_run = True
        else:
            state_manager.update_tweet_data(tweet_data.tweet_id, tweet_data)
            return

    # 2. Expand URLs (like example)
    needs_url_expansion = bool(tweet_data.original_urls) and not tweet_data.urls_expanded
    if needs_url_expansion:
        logger.info(f"Expanding {len(tweet_data.original_urls)} URLs for tweet {tweet_id}")
        async with aiohttp.ClientSession() as session: # Create session for expansion
             expand_tasks = [_expand_url(url, session) for url in tweet_data.original_urls]
             expanded_results = await asyncio.gather(*expand_tasks, return_exceptions=True)
        
        final_expanded_urls = {}
        expansion_failed = False
        for i, result in enumerate(expanded_results):
            original = tweet_data.original_urls[i]
            if isinstance(result, Exception):
                logger.warning(f"Expansion task failed for {original}: {result}")
                final_expanded_urls[original] = original # Keep original on task error
                expansion_failed = True
            elif isinstance(result, str):
                final_expanded_urls[original] = result
                if result == original and 't.co' in original: # Check if expansion actually failed vs. no redirect
                     logger.debug(f"URL {original} did not expand.")
                     # Decide if this counts as a failure - maybe not critical?
            else:
                logger.error(f"Unexpected result type during URL expansion for {original}: {type(result)}")
                final_expanded_urls[original] = original
                expansion_failed = True
        
        tweet_data.expanded_urls = final_expanded_urls
        tweet_data.urls_expanded = True # Mark as attempted
        # If expansion failure should block cache_complete, set flag:
        # if expansion_failed: tweet_successfully_cached_this_run = False
        logger.info(f"Finished URL expansion for tweet {tweet_id}. Success rate depends on definition.")


    # 3. Download Media if needed
    media_download_succeeded_for_all_items = True # Initialize flag

    if tweet_successfully_cached_this_run and tweet_data.media_items: # Only proceed if initial fetch was okay AND there are media items
        logger.info(f"Verifying/downloading {len(tweet_data.media_items)} media items for tweet {tweet_id}")
        
        # base_media_cache_dir is like 'data/media_cache'
        base_media_cache_dir = config.data_dir / "media_cache"
        # tweet_specific_media_dir is like 'data/media_cache/tweet_id'
        tweet_specific_media_dir = base_media_cache_dir / tweet_id
        await file_io.ensure_dir_async(tweet_specific_media_dir)
        
        missing_media_items_to_download: List[MediaItem] = []
        for item in tweet_data.media_items:
            item.download_error = None # Clear previous download error before validation/attempt
            
            # item.local_path should be relative, e.g., "tweet_id/filename.ext"
            # To check existence, we need the absolute path.
            absolute_local_path_to_check = None
            if item.local_path:
                # Assuming item.local_path is already relative to base_media_cache_dir
                # e.g. "12345/media.jpg"
                path_obj = Path(item.local_path)
                if path_obj.is_absolute(): # Should not happen if logic is correct
                    logger.warning(f"MediaItem {item.original_url} for tweet {tweet_id} has an absolute local_path '{item.local_path}' which is unexpected. Trying to use it directly.")
                    absolute_local_path_to_check = path_obj
                else:
                    absolute_local_path_to_check = (base_media_cache_dir / item.local_path).resolve()
            
            if not absolute_local_path_to_check or not await aiofiles.os.path.exists(absolute_local_path_to_check):
                potential_filename_log = Path(str(item.original_url)).name if item.original_url else "unknown_original_url"
                logger.info(f"Media file {potential_filename_log} missing or path not set for {item.original_url} (current local_path: {item.local_path}). Scheduling download...")
                missing_media_items_to_download.append(item)
            elif absolute_local_path_to_check and item.local_path: # File exists and local_path is set
                # Ensure item.local_path is relative if it somehow became absolute
                current_local_path_obj = Path(item.local_path)
                if current_local_path_obj.is_absolute():
                     try:
                        item.local_path = current_local_path_obj.relative_to(base_media_cache_dir)
                        logger.debug(f"Converted an absolute local_path back to relative: {item.local_path} for existing media {item.original_url}")
                     except ValueError:
                        logger.error(f"Could not make absolute path {current_local_path_obj} relative to {base_media_cache_dir} for {item.original_url}. Keeping absolute.")
                        # This case is problematic for portability.
                logger.debug(f"Media file already exists: {absolute_local_path_to_check} (local_path: {item.local_path})")
        
        if missing_media_items_to_download:
            logger.info(f"Attempting to download {len(missing_media_items_to_download)} missing media items.")
            for item_to_download in missing_media_items_to_download:
                try:
                    logger.debug(f"Accessing config.media_max_size_bytes for {item_to_download.original_url}, value: {config.media_max_size_bytes}")
                except AttributeError as ae:
                    logger.error(f"CRITICAL: AttributeError accessing config.media_max_size_bytes for {item_to_download.original_url}. Error: {ae}", exc_info=True)
                    item_to_download.download_error = f"Configuration error: media_max_size_bytes missing. {ae}"
                    media_download_succeeded_for_all_items = False
                    continue # Skip download for this item

                download_result = await _download_media(
                    media_url=str(item_to_download.original_url),
                    download_dir=tweet_specific_media_dir, # Pass the specific dir for this tweet's media
                    http_client_manager=http_client,
                    base_media_cache_dir=base_media_cache_dir, # Pass base for relative path calculation
                    max_size_bytes=config.media_max_size_bytes
                )
                if download_result:
                    relative_file_path, content_type = download_result
                    # The returned path is already relative to base_media_cache_dir
                    item_to_download.local_path = relative_file_path 
                    if not item_to_download.type:
                        item_to_download.type = content_type.split('/')[0] if '/' in content_type else content_type
                    logger.info(f"Successfully downloaded and stored media for {item_to_download.original_url} at relative path {item_to_download.local_path}")
                else:
                    logger.error(f"Download attempt ultimately failed for {item_to_download.original_url} after retries (if any).")
                    item_to_download.download_error = item_to_download.download_error or f"Download failed for {item_to_download.original_url}"
                    media_download_succeeded_for_all_items = False
        else:
            logger.debug(f"No missing media items to download for tweet {tweet_id}.")
        
        # After all download attempts, final check for success for all media items
        if tweet_data.media_items: # Only if there were media items to begin with
            any_media_failed = False
            for item in tweet_data.media_items:
                if not item.local_path or item.download_error:
                    any_media_failed = True
                    if not item.download_error: # If no specific error, but path is missing
                        item.download_error = "Media item has no local_path after processing."
                    logger.warning(f"Media item {item.original_url} for tweet {tweet_id} is not successfully cached. Error: {item.download_error}, Path: {item.local_path}")
            if any_media_failed:
                media_download_succeeded_for_all_items = False

    elif not tweet_data.media_items and tweet_successfully_cached_this_run:
        logger.info(f"No media items were listed for tweet {tweet_id}.")
        # media_download_succeeded_for_all_items remains True
    
    if not media_download_succeeded_for_all_items and tweet_data.media_items: # If there was media, and it failed
        tweet_successfully_cached_this_run = False
        logger.warning(f"Marking tweet {tweet_id} as not successfully cached this run due to media download failures.")

    # 4. Finalize cache status
    if tweet_data.text and tweet_data.author_id and tweet_data.source_url and tweet_successfully_cached_this_run:
        tweet_data.cache_complete = True
        tweet_data.cache_error = None 
        logger.info(f"Tweet {tweet_id} marked as cache_complete.")
    else:
        tweet_data.cache_complete = False
        current_error = tweet_data.cache_error or ""
        new_errors = []

        if not (tweet_data.text and tweet_data.author_id and tweet_data.source_url):
            new_errors.append("Missing essential tweet data (text, author, or source_url).")
        
        # Check if the overall run failure was due to media, if other core data was present
        if not media_download_succeeded_for_all_items and tweet_data.media_items and \
           (tweet_data.text and tweet_data.author_id and tweet_data.source_url):
            new_errors.append("One or more media items failed to download or are missing.")
        elif not tweet_successfully_cached_this_run and not new_errors: # General failure not yet specified
            new_errors.append("One or more caching steps failed this run.")

        if new_errors:
            # Combine new errors with existing, avoiding full duplicates
            unique_new_errors = [ne for ne in new_errors if ne not in current_error]
            if unique_new_errors:
                if current_error:
                    tweet_data.cache_error = f"{current_error}; {'; '.join(unique_new_errors)}"
                else:
                    tweet_data.cache_error = '; '.join(unique_new_errors)
            elif not current_error and not tweet_data.cache_error : # If no new unique and no prior error
                 tweet_data.cache_error = "Caching failed due to unspecified reasons."

        elif not tweet_data.cache_error : # If somehow not complete but no errors logged yet
            tweet_data.cache_error = "Tweet not cache-complete for unspecified reasons."
        
        logger.warning(f"Tweet {tweet_id} NOT marked cache_complete. Reason: {tweet_data.cache_error or 'Incomplete data/steps.'}")
    
    tweet_data.last_cached_at = datetime.utcnow()
    # Final save happens in pipeline after phase finishes
    state_manager.update_tweet_data(tweet_data.tweet_id, tweet_data)


async def run_cache_phase(
    tweet_id: str,
    tweet_data: TweetData,
    config: Config,
    http_manager: HttpClientManager, 
    state_manager: StateManager,
    playwright_client: PlaywrightClient,
    force_recache: bool = False,
    run_only_phase: str = 'Full',
    is_fetching_bookmarks: bool = False,
    **kwargs 
):
    """
    Phase function for caching a single tweet. Called by the AgentPipeline.
    Now incorporates logic inspired by cache_tweets example.
    """
    logger.debug(f"Running cache phase for tweet ID: {tweet_id}. Force recache: {force_recache}")

    should_process = False
    # Store the original error message if it exists, to see if it changes.
    original_cache_error = tweet_data.cache_error 

    if force_recache:
        logger.info(f"Force re-cache enabled for tweet {tweet_id}.")
        should_process = True
        # Clear previous status flags relevant to caching to ensure reprocessing
        tweet_data.cache_complete = False
        tweet_data.urls_expanded = False 
        tweet_data.media_processed = False 
        # tweet_data.cache_error = None # Will be cleared below if should_process is true
    elif not tweet_data.cache_complete:
        logger.info(f"Tweet {tweet_id} is not cache-complete. Processing.")
        should_process = True
    elif tweet_data.cache_error: 
        logger.info(f"Tweet {tweet_id} has a previous cache error: '{tweet_data.cache_error}'. Re-processing.")
        should_process = True
        # tweet_data.cache_error = None # Will be cleared below
    elif not await validate_cache(tweet_data, config): 
        logger.warning(f"Tweet {tweet_data.tweet_id} failed cache validation. Re-processing.")
        should_process = True
        tweet_data.cache_complete = False 
        tweet_data.media_processed = False
    else:
        logger.info(f"Tweet {tweet_id} is already cache-complete and validated. Skipping caching.")

    if should_process:
        # Crucially, clear any pre-existing cache_error before calling cache_tweet
        # so that cache_tweet can set a fresh status based on the current attempt.
        if tweet_data.cache_error:
            logger.debug(f"Clearing previous cache error ('{tweet_data.cache_error}') for tweet {tweet_id} before re-caching attempt.")
            tweet_data.cache_error = None
            
        try:
            logger.debug(f"Config object about to be passed to cache_tweet for {tweet_id}: {config.model_dump_json(indent=2)}")
            await cache_tweet(
                tweet_id=tweet_id,
                tweet_data=tweet_data, 
                config=config,
                http_client=http_manager, 
                state_manager=state_manager,
                playwright_client=playwright_client,
                run_only_phase=run_only_phase,
                is_fetching_bookmarks=is_fetching_bookmarks
            )
            # cache_tweet updates tweet_data.cache_complete and tweet_data.cache_error internally
            if tweet_data.cache_error:
                 logger.warning(f"Caching attempt for {tweet_id} resulted in new error: '{tweet_data.cache_error}'")
            elif original_cache_error and not tweet_data.cache_error:
                 logger.info(f"Caching attempt for {tweet_id} cleared a previous error ('{original_cache_error}'). Current status: cache_complete={tweet_data.cache_complete}")
            else:
                 logger.info(f"Caching attempt for {tweet_id} completed. Current status: cache_complete={tweet_data.cache_complete}, cache_error={tweet_data.cache_error}")

        except Exception as e:
            logger.error(f"Unhandled exception during cache_tweet call for {tweet_id}: {e}", exc_info=True)
            tweet_data.mark_failed("Caching", f"Outer cache error: {e}")
            # StateManager will save this updated tweet_data.
    else:
        logger.debug(f"Skipping actual caching logic for {tweet_id}.")

    # The pipeline will save the state_manager state after the phase completes.
    # The error that gets logged by the pipeline for the item's phase completion
    # will be based on the final tweet_data.cache_error or tweet_data.failed_phase.
