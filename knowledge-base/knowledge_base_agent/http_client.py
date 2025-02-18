import logging
import httpx
from typing import Optional, Any, Dict, List
import asyncio
from tenacity import retry, stop_after_attempt, wait_exponential
from knowledge_base_agent.config import Config
from knowledge_base_agent.exceptions import NetworkError, AIError, ModelInferenceError
import aiohttp
import aiofiles
from pathlib import Path
import base64

class HTTPClient:
    """Generic HTTP client with retry logic."""
    
    def __init__(self, config: Config):
        self.config = config
        self._client = None

    async def __aenter__(self):
        self._client = httpx.AsyncClient()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self._client:
            await self._client.aclose()

    async def ensure_client(self):
        """Ensure HTTP client is initialized."""
        if not self._client:
            self._client = httpx.AsyncClient()

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10)
    )
    async def get(self, url: str, **kwargs) -> httpx.Response:
        """Make GET request with retry logic."""
        try:
            response = await self._client.get(url, **kwargs)
            response.raise_for_status()
            return response
        except Exception as e:
            logging.error(f"HTTP GET failed for {url}: {str(e)}")
            raise NetworkError(f"Failed to fetch {url}") from e

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10)
    )
    async def post(self, url: str, **kwargs) -> httpx.Response:
        """Make POST request with retry logic."""
        try:
            response = await self._client.post(url, **kwargs)
            response.raise_for_status()
            return response
        except Exception as e:
            logging.error(f"HTTP POST failed for {url}: {str(e)}")
            raise NetworkError(f"Failed to post to {url}") from e

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10)
    )
    async def download_media(self, url: str, output_path: Path) -> None:
        """Download media from URL to specified path."""
        try:
            await self.ensure_client()  # Ensure client is initialized
            async with self._client.stream('GET', url) as response:
                response.raise_for_status()
                output_path.parent.mkdir(parents=True, exist_ok=True)
                async with aiofiles.open(output_path, 'wb') as f:
                    async for chunk in response.aiter_bytes():
                        await f.write(chunk)
        except Exception as e:
            logging.error(f"Failed to download media from {url}: {str(e)}")
            raise NetworkError(f"Failed to download media from {url}") from e

class OllamaClient:
    """Client for interacting with Ollama API."""
    
    def __init__(self, config: Config = None):
        """Initialize with config containing OLLAMA_URL."""
        if config:
            # Convert HttpUrl to string
            self.base_url = str(config.ollama_url)
        else:
            self.base_url = "http://localhost:11434"
        logging.debug(f"Initializing OllamaClient with base_url: {self.base_url}")
        self._client = httpx.AsyncClient(base_url=self.base_url, timeout=60.0)
        
    async def __aenter__(self):
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self._client.aclose()
        
    async def generate(self, model: str, prompt: str, images: List[str] = None) -> str:
        """Generate text from Ollama model."""
        try:
            # Prepare the payload
            payload = {
                "model": model,
                "prompt": prompt,
                "stream": False
            }

            # Add images if provided
            if images:
                # Convert images to base64
                image_data = []
                for image_path in images:
                    with open(image_path, 'rb') as f:
                        image_bytes = f.read()
                        image_base64 = base64.b64encode(image_bytes).decode('utf-8')
                        image_data.append(image_base64)
                payload["images"] = image_data

            logging.debug(f"Sending request to Ollama API with model {model}")
            response = await self._client.post("/api/generate", json=payload)
            response.raise_for_status()
            
            # Handle Ollama's response format
            try:
                data = response.json()
                if not isinstance(data, dict):
                    raise ValueError("Expected JSON object in response")
                return data.get('response', '')
            except ValueError as e:
                logging.error(f"Invalid JSON response from Ollama: {e}")
                raise ModelInferenceError(f"Failed to parse Ollama response: {e}")
            
        except Exception as e:
            logging.error(f"Ollama API call failed: {e}")
            raise ModelInferenceError(f"Failed to generate response: {e}")
