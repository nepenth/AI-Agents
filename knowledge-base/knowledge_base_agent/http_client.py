import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import httpx
from typing import Optional
import asyncio
from contextlib import asynccontextmanager
import logging
import aiohttp
import base64
from pathlib import Path

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
    def __init__(self, base_url: str, timeout: int = 60, max_pool_size: int = 10):
        self.base_url = base_url.rstrip('/')
        self.timeout = timeout
        self.max_pool_size = max_pool_size
        self.session = None
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

    async def analyze_image(self, image_path: Path, model: str) -> str:
        """
        Analyze an image using Ollama's vision model.
        
        Args:
            image_path: Path to the image file
            model: Name of the vision model to use
            
        Returns:
            String description of the image
        """
        try:
            # Read image as base64
            with open(image_path, "rb") as image_file:
                image_data = base64.b64encode(image_file.read()).decode('utf-8')
            
            # Prepare the prompt
            prompt = "Describe this image in detail, focusing on key elements and their significance."
            
            # Prepare the request payload
            payload = {
                "model": model,
                "prompt": prompt,
                "images": [image_data],
                "stream": False
            }
            
            # Make request to Ollama
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.base_url}/api/generate",
                    json=payload,
                    timeout=self.timeout
                ) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        raise Exception(f"Ollama API error: {error_text}")
                    
                    result = await response.json()
                    return result.get('response', '')
                    
        except Exception as e:
            logging.error(f"Failed to analyze image {image_path}: {e}")
            return f"Error analyzing image: {str(e)}"
