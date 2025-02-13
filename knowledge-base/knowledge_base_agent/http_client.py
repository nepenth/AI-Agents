import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import httpx
from typing import Optional
import asyncio
from contextlib import asynccontextmanager
import logging
import aiohttp

# Initialize logger at module level
logger = logging.getLogger(__name__)

def create_http_client():
    """Create and return a new aiohttp ClientSession with a timeout."""
    timeout = aiohttp.ClientTimeout(total=30)
    return aiohttp.ClientSession(timeout=timeout)

def create_http_client():
    session = requests.Session()
    retries = Retry(total=5, backoff_factor=1, status_forcelist=[502, 503, 504])
    adapter = HTTPAdapter(max_retries=retries, pool_connections=10, pool_maxsize=10)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    return session

class OllamaClient:
    def __init__(self, base_url: str, timeout: int = 180, max_pool_size: int = 1):
        self.base_url = base_url
        self.timeout = timeout
        self._client: Optional[httpx.AsyncClient] = None
        self.limits = httpx.Limits(max_keepalive_connections=max_pool_size)
        self._lock = asyncio.Lock()  # Ensure single concurrent request

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                timeout=self.timeout,
                limits=self.limits,
                http2=True  # Enable HTTP/2 for better connection reuse
            )
        return self._client

    @asynccontextmanager
    async def request(self):
        client = await self._get_client()
        async with self._lock:  # Ensure one request at a time
            try:
                yield client
            except httpx.TimeoutException as e:
                logger.error(f"Request timed out after {self.timeout} seconds: {e}")
                raise
            except Exception as e:
                logger.error(f"Request failed: {e}")
                raise

    async def close(self):
        if self._client is not None:
            await self._client.aclose()
            self._client = None
