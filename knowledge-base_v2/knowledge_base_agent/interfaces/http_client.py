import logging
from typing import Optional, Dict, Any

import httpx

# Assuming exceptions are in the parent directory relative to interfaces
from ..exceptions import HttpClientError

logger = logging.getLogger(__name__)

# Default timeout settings (can be overridden)
DEFAULT_TIMEOUT = httpx.Timeout(10.0, connect=5.0, read=10.0, write=10.0)
DEFAULT_MAX_REDIRECTS = 5

class HttpClientManager:
    """
    Manages a shared httpx.AsyncClient instance for making HTTP requests.

    Provides a central point for configuring timeouts, headers, base URLs,
    and handles common HTTP request errors, wrapping them in HttpClientError.
    Supports use as an async context manager.
    """

    def __init__(
        self,
        base_url: str = "",
        headers: Optional[Dict[str, str]] = None,
        timeout: httpx.Timeout = DEFAULT_TIMEOUT,
        max_redirects: int = DEFAULT_MAX_REDIRECTS,
    ):
        """
        Initializes the HttpClientManager.

        Args:
            base_url: An optional base URL for all requests.
            headers: Optional default headers to include in all requests.
            timeout: An httpx.Timeout object configuring request timeouts.
            max_redirects: Maximum number of redirects to follow.
        """
        self._base_url = base_url
        self._headers = headers or {}
        self._timeout = timeout
        self._max_redirects = max_redirects
        self._client: Optional[httpx.AsyncClient] = None
        logger.info(
            f"HttpClientManager initialized. Base URL: '{base_url or 'None'}', Timeout: {timeout.read}s Read"
        )

    async def get_client(self) -> httpx.AsyncClient:
        """
        Returns the shared httpx.AsyncClient instance, creating it if necessary.

        Ensures that a single client instance is reused for efficiency
        (e.g., connection pooling).
        """
        if self._client is None or self._client.is_closed:
            logger.debug("Creating new httpx.AsyncClient instance.")
            self._client = httpx.AsyncClient(
                base_url=self._base_url,
                headers=self._headers,
                timeout=self._timeout,
                follow_redirects=True, # Default to following redirects
                max_redirects=self._max_redirects,
            )
            # Log the transport details once upon creation for debugging network issues
            logger.debug(f"httpx.AsyncClient created with transport: {type(self._client._transport).__name__}")
        return self._client

    async def request(
        self,
        method: str,
        url: str,
        params: Optional[Dict[str, Any]] = None,
        json: Optional[Any] = None,
        data: Optional[Dict[str, Any]] = None,
        custom_headers: Optional[Dict[str, str]] = None,
        raise_for_status: bool = True,
        **kwargs # Allow passing other httpx options like files, content etc.
    ) -> httpx.Response:
        """
        Performs an HTTP request using the managed client.

        Args:
            method: HTTP method (GET, POST, PUT, DELETE, etc.).
            url: URL path (relative to base_url if set) or an absolute URL.
            params: Dictionary of URL query parameters.
            json: JSON payload for the request body. Auto-sets 'Content-Type'.
            data: Form data payload for the request body.
            custom_headers: Dictionary of headers specific to this request,
                            merged with default headers.
            raise_for_status: If True (default), raises HttpClientError for 4xx/5xx responses.
                              If False, returns the response object even for errors.
            **kwargs: Additional arguments passed directly to httpx.AsyncClient.request
                      (e.g., `files`, `content`).

        Returns:
            The httpx.Response object.

        Raises:
            HttpClientError: If an HTTP request error occurs (network, timeout,
                             or status code error if raise_for_status is True).
        """
        client = await self.get_client()
        request_headers = self._headers.copy()
        if custom_headers:
            request_headers.update(custom_headers)

        # Log request details (avoid logging sensitive data in production)
        logger.debug(f"Making HTTP {method} request to '{url}' (Client ID: {id(client)})")
        # Consider logging params/json structure safely if needed for debugging
        # logger.debug(f" Params: {params}, JSON keys: {list(json.keys()) if json else None}")


        try:
            response = await client.request(
                method=method.upper(), # Ensure method is uppercase
                url=url,
                params=params,
                json=json,
                data=data,
                headers=request_headers,
                **kwargs
            )

            # Optionally raise exception for bad status codes
            if raise_for_status:
                response.raise_for_status() # Raises httpx.HTTPStatusError

            logger.debug(f"HTTP {method} request to '{url}' completed with status {response.status_code}")
            return response

        # --- Specific Exception Handling ---
        except httpx.TimeoutException as e:
            logger.error(f"HTTP request timeout for {method} {url}: {e}")
            raise HttpClientError(url=str(e.request.url), message="Request timed out", original_exception=e) from e
        except httpx.RequestError as e:
            # Covers connection errors, DNS errors, etc. (but not status errors)
            logger.error(f"HTTP request error for {method} {url}: {type(e).__name__} - {e}")
            raise HttpClientError(url=str(e.request.url), message=f"Request failed: {e}", original_exception=e) from e
        except httpx.HTTPStatusError as e:
            # This is caught only if raise_for_status=True
            # Log the response body if possible for debugging server errors
            try:
                 error_body = e.response.text
                 # Limit length to avoid flooding logs
                 log_body = (error_body[:200] + '...') if len(error_body) > 200 else error_body
            except Exception:
                 log_body = "(Could not read error body)"

            logger.error(
                 f"HTTP status error {e.response.status_code} for {method} {url}. Response: {log_body}"
            )
            # Re-raise as our custom exception
            raise HttpClientError(
                url=str(e.request.url),
                status_code=e.response.status_code,
                message=f"HTTP Error: {e.response.status_code} {e.response.reason_phrase}",
                original_exception=e
            ) from e
        except Exception as e:
            # Catch any other unexpected errors during the request attempt
            logger.exception(f"Unexpected error during HTTP request for {method} {url}", exc_info=True) # Use logger.exception for stack trace
            # Attempt to get URL if possible, otherwise use the input 'url'
            err_url = url
            if hasattr(e, 'request') and hasattr(e.request, 'url'):
                 err_url = str(e.request.url)
            raise HttpClientError(url=err_url, message=f"Unexpected request error: {type(e).__name__}", original_exception=e) from e

    async def close(self):
        """Closes the underlying shared httpx.AsyncClient, if it exists."""
        if self._client and not self._client.is_closed:
            logger.info("Closing shared httpx.AsyncClient.")
            await self._client.aclose()
            self._client = None
        else:
            logger.debug("Shared httpx.AsyncClient already closed or not initialized.")

    # --- Async Context Manager Support ---
    async def __aenter__(self):
        """Enter the async context manager, ensuring the client is initialized."""
        await self.get_client() # Ensure client is created and ready
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Exit the async context manager, closing the client."""
        await self.close()
