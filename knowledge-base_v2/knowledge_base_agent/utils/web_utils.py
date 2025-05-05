import logging
from typing import Optional
from urllib.parse import urlparse, ParseResult

import httpx

from ..exceptions import HttpClientError

logger = logging.getLogger(__name__)

# Maintain a reusable client for efficiency? Consider lifecycle management.
# For simplicity here, we create one per call or expect one passed in.

async def expand_url_async(
    short_url: str,
    client: Optional[httpx.AsyncClient] = None,
    timeout: int = 10,
    max_redirects: int = 5
) -> Optional[str]:
    """
    Expands a shortened URL by following redirects using httpx.

    Args:
        short_url: The URL to expand.
        client: An optional existing httpx.AsyncClient instance.
        timeout: Request timeout in seconds.
        max_redirects: Maximum number of redirects to follow.

    Returns:
        The expanded URL string, or the original URL if no redirection occurs,
        or None if an error occurs or the URL is invalid.
    """
    if not is_valid_url(short_url):
        logger.warning(f"Attempted to expand invalid URL: {short_url}")
        return None

    close_client = False
    if client is None:
        # Create a temporary client if none is provided
        # Consider security implications of default verify=True
        client = httpx.AsyncClient(follow_redirects=True, timeout=timeout, max_redirects=max_redirects)
        close_client = True

    logger.debug(f"Attempting to expand URL: {short_url} (Max redirects: {max_redirects})")
    try:
        # Use GET request to follow redirects naturally
        # Using HEAD can sometimes be blocked or not trigger all redirects
        response = await client.get(short_url)
        response.raise_for_status() # Check for HTTP errors 4xx/5xx

        final_url = str(response.url)
        if final_url != short_url:
            logger.info(f"Expanded URL {short_url} -> {final_url}")
        else:
            logger.debug(f"URL {short_url} did not redirect.")
        return final_url

    except httpx.TooManyRedirects as e:
        logger.error(f"Too many redirects for URL {short_url}: {e}")
        # Raise a specific exception or return None/original URL? Returning None for now.
        # Re-raising might be better for the caller to handle.
        # raise HttpClientError(url=short_url, message="Too many redirects", original_exception=e)
        return None
    except httpx.RequestError as e:
        # Includes network errors, DNS errors, timeout errors etc.
        logger.error(f"HTTP request error expanding URL {short_url}: {type(e).__name__} - {e}")
        # Re-raise as HttpClientError or return None?
        # raise HttpClientError(url=short_url, message=str(e), original_exception=e)
        return None
    except httpx.HTTPStatusError as e:
        # Handle 4xx/5xx errors specifically if needed
        logger.error(f"HTTP status error {e.response.status_code} for URL {short_url}: {e}")
        # raise HttpClientError(url=short_url, status_code=e.response.status_code, message=str(e), original_exception=e)
        return None # Treat HTTP errors as expansion failure
    except Exception as e:
        # Catch any other unexpected errors
        logger.error(f"Unexpected error expanding URL {short_url}: {type(e).__name__} - {e}", exc_info=True)
        # raise HttpClientError(url=short_url, message="Unexpected error during expansion", original_exception=e)
        return None
    finally:
        # Close the client only if it was created within this function
        if close_client and client:
            await client.aclose()


def parse_url(url: str) -> Optional[ParseResult]:
    """
    Parses a URL string into components using urllib.parse.

    Returns:
        A ParseResult object or None if parsing fails minimally
        (e.g., empty string). More robust validation might be needed.
    """
    if not url:
        return None
    try:
        parsed = urlparse(url)
        return parsed
    except Exception as e: # urlparse is generally robust, but catch potential issues
        logger.warning(f"Could not parse URL '{url}': {e}")
        return None


def is_valid_url(url: str) -> bool:
    """
    Performs basic validation checks on a URL string.
    Checks for scheme and netloc presence.
    """
    if not isinstance(url, str) or not url:
        return False
    try:
        parsed = urlparse(url)
        # Check if scheme and netloc (domain) are present
        return bool(parsed.scheme and parsed.netloc)
    except ValueError:
        # urlparse can raise ValueError for certain invalid inputs (e.g., excessive brackets)
        return False

def sanitize_url(url: str) -> Optional[str]:
    """
    Basic URL sanitization. Returns the URL if it looks valid, otherwise None.
    (Further sanitization might involve encoding control characters, etc.,
    depending on the use case).
    """
    if is_valid_url(url):
        # Potentially add more checks or normalization here if needed
        return url
    logger.warning(f"Sanitization check failed for URL: {url}")
    return None
