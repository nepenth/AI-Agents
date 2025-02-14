import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import httpx
from typing import Optional, Any, Dict
import asyncio
from contextlib import asynccontextmanager
import logging
import aiohttp
import base64
from pathlib import Path
from tenacity import retry, stop_after_attempt, wait_exponential
from .config import Config  # Add this import

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

class HTTPClient:
    def __init__(self, config: Config):
        self.config = config
        self.client = httpx.AsyncClient(
            base_url=str(config.ollama_url),  # Convert HttpUrl to string
            timeout=config.request_timeout,
            limits=httpx.Limits(
                max_connections=config.max_concurrent_requests,
                max_keepalive_connections=config.max_concurrent_requests
            )
        )
        
    async def __aenter__(self):
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.client.aclose()

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        reraise=True
    )
    async def get(self, url: str, **kwargs) -> httpx.Response:
        """GET request with retry logic"""
        response = await self.client.get(url, **kwargs)
        response.raise_for_status()
        return response

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        reraise=True
    )
    async def post(self, url: str, **kwargs) -> httpx.Response:
        """POST request with retry logic"""
        response = await self.client.post(url, **kwargs)
        response.raise_for_status()
        return response

class OllamaClient:
    def __init__(self, config: Config):
        self.config = config
        self.base_url = str(config.ollama_url).rstrip('/')  # Convert HttpUrl to string before rstrip
        self.vision_model = config.vision_model
        self.text_model = config.text_model
        self.timeout = config.request_timeout
        self.max_pool_size = config.max_concurrent_requests
        self.session = None
        self._client: Optional[httpx.AsyncClient] = None
        self.limits = httpx.Limits(max_keepalive_connections=self.max_pool_size)
        self._lock = asyncio.Lock()  # Ensure single concurrent request
        self.client = HTTPClient(config=config)

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
            # Convert image_path to Path if it's a string
            if isinstance(image_path, str):
                image_path = Path(image_path)
                
            # Clean up the path (remove URL parameters)
            clean_path = Path(str(image_path).split('?')[0])
            
            if not clean_path.exists():
                raise FileNotFoundError(f"Image file not found: {clean_path}")
                
            # Read image as base64
            with open(clean_path, "rb") as image_file:
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

    async def generate(self, model: str, prompt: str, **kwargs) -> Dict[str, Any]:
        """Generate text with retry logic"""
        try:
            response = await self.client.post(
                "/api/generate",
                json={"model": model, "prompt": prompt, **kwargs}
            )
            return response.json()
        except Exception as e:
            logging.exception(f"Ollama generation failed for model {model}")
            raise

    async def analyze_image(self, model: str, image_data: bytes, prompt: str) -> Dict[str, Any]:
        """Analyze image with retry logic"""
        try:
            response = await self.client.post(
                "/api/analyze",
                json={
                    "model": model,
                    "image": image_data.decode('utf-8'),
                    "prompt": prompt
                }
            )
            return response.json()
        except Exception as e:
            logging.exception(f"Image analysis failed for model {model}")
            raise
