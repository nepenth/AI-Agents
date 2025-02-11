from typing import AsyncGenerator, Optional
import httpx
import logging

logger = logging.getLogger(__name__)

class APIClient:
    def __init__(self, base_url: str, timeout: int = 120):
        self.base_url = base_url
        self.timeout = timeout
        self._client: Optional[httpx.AsyncClient] = None

    async def __aenter__(self) -> 'APIClient':
        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=self.timeout
        )
        return self

    async def __aexit__(self, *args):
        if self._client:
            await self._client.aclose()
            self._client = None

    async def post(self, endpoint: str, json: dict) -> dict:
        if not self._client:
            raise RuntimeError("Client not initialized. Use as async context manager.")
        try:
            response = await self._client.post(endpoint, json=json)
            response.raise_for_status()
            return response.json()
        except httpx.TimeoutException as e:
            logger.error(f"Request timed out after {self.timeout} seconds: {e}")
            raise 
        