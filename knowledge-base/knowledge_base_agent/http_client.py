import logging
import httpx
from typing import Optional, Any, Dict
import asyncio
from tenacity import retry, stop_after_attempt, wait_exponential
from knowledge_base_agent.config import Config
from knowledge_base_agent.exceptions import NetworkError
import aiohttp
import aiofiles
from pathlib import Path

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
    
    def __init__(self, config: Config):
        self.config = config
        self.base_url = str(config.ollama_url)
        self.http_client = HTTPClient(config)

    async def generate(self, prompt: str, model: str) -> str:
        """Generate text using specified model."""
        try:
            async with self.http_client as client:
                response = await client.post(
                    f"{self.base_url}/api/generate",
                    json={"prompt": prompt, "model": model}
                )
                return response.json()["response"]
        except Exception as e:
            logging.error(f"Ollama generation failed: {str(e)}")
            raise NetworkError("Failed to generate response from Ollama") from e
