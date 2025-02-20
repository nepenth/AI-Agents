import logging
import httpx
from typing import Optional, Any, Dict, List
import asyncio
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from knowledge_base_agent.config import Config
from knowledge_base_agent.exceptions import NetworkError, AIError, ModelInferenceError
import aiohttp
import aiofiles
from pathlib import Path
import base64
import time

class HTTPClient:
    """HTTP client for making requests to external services."""
    
    def __init__(self, config: Config):
        self.config = config
        self.session = None
        self.initialized = False
        self.base_url = str(self.config.ollama_url).rstrip('/')
        self.timeout = config.request_timeout
        self.max_retries = self.config.max_retries
        self.batch_size = self.config.batch_size
        self.max_concurrent = self.config.max_concurrent_requests
        self._semaphore = asyncio.Semaphore(self.max_concurrent)
        logging.info(f"Initializing HTTPClient with Ollama URL: {self.base_url}")
        logging.info(f"Settings: timeout={self.timeout}s, max_retries={self.max_retries}, "
                    f"batch_size={self.batch_size}, max_concurrent={self.max_concurrent}")
        
    async def initialize(self):
        """Initialize the HTTP client session."""
        if not self.initialized:
            self.session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=self.timeout)
            )
            self.initialized = True
            logging.info("HTTPClient session initialized")
        
    async def close(self):
        """Close the HTTP client session."""
        if self.session and not self.session.closed:
            await self.session.close()
            self.initialized = False
            logging.info("HTTPClient session closed")
            
    async def ensure_session(self):
        """Ensure a session exists."""
        if not self.initialized:
            await self.initialize()
            
    @retry(
        stop=stop_after_attempt(3),  # Use config.max_retries
        wait=wait_exponential(multiplier=1, min=4, max=10),
        retry=retry_if_exception_type((asyncio.TimeoutError, aiohttp.ClientError))
    )
    async def ollama_generate(
        self,
        model: str,
        prompt: str,
        temperature: float = 0.7,
        max_tokens: int = 2000,
        top_p: float = 0.9,
        timeout: Optional[int] = None
    ) -> str:
        """
        Generate text using Ollama API with consistent parameters.
        
        Args:
            model: The model to use for generation (from config.text_model)
            prompt: The prompt text
            temperature: Controls randomness (0.0-1.0)
            max_tokens: Maximum tokens to generate
            top_p: Nucleus sampling parameter
            timeout: Request timeout in seconds (defaults to config.request_timeout)
        
        Returns:
            str: Generated text response
            
        Raises:
            AIError: If the API request fails or returns invalid response
            TimeoutError: If the request exceeds the timeout period
        """
        timeout = timeout or self.timeout
        
        # Use semaphore to limit concurrent requests
        async with self._semaphore:
            await self.ensure_session()
            
            try:
                api_endpoint = f"{self.base_url}/api/generate"
                logging.debug(f"Sending Ollama request to {api_endpoint}")
                logging.debug(f"Using model: {model}")
                logging.debug(f"Prompt preview: {prompt[:200]}...")
                
                start_time = time.time()
                async with self.session.post(
                    api_endpoint,
                    json={
                        "model": model,
                        "prompt": prompt,
                        "stream": False,
                        "temperature": temperature,
                        "max_tokens": max_tokens,
                        "top_p": top_p
                    },
                    timeout=timeout
                ) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        logging.error(f"Ollama API error: {response.status} - {error_text}")
                        logging.error(f"Request URL: {api_endpoint}")
                        logging.error(f"Request model: {model}")
                        raise AIError(f"Ollama API returned status {response.status}")
                    
                    result = await response.json()
                    elapsed = time.time() - start_time
                    
                    response_text = result.get("response", "").strip()
                    if not response_text:
                        raise AIError("Empty response from Ollama API")
                    
                    logging.debug(f"Received response of length: {len(response_text)} in {elapsed:.2f}s")
                    
                    # Add delay between requests based on batch size
                    if self.batch_size > 1:
                        await asyncio.sleep(1.0)  # Basic rate limiting
                        
                    return response_text
                    
            except asyncio.TimeoutError:
                logging.error(f"Ollama request timed out after {timeout} seconds")
                logging.error(f"Model: {model}")
                logging.error(f"Endpoint: {api_endpoint}")
                raise AIError(f"Request timed out after {timeout} seconds")
                
            except aiohttp.ClientError as e:
                logging.error(f"HTTP client error: {str(e)}")
                logging.error(f"Request URL: {api_endpoint}")
                raise AIError(f"HTTP client error: {str(e)}")
                
            except Exception as e:
                logging.error(f"Unexpected error in ollama_generate: {str(e)}")
                raise AIError(f"Failed to generate text with Ollama: {str(e)}")
            
    async def __aenter__(self):
        await self.initialize()
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()

    def __del__(self):
        """Ensure resources are cleaned up."""
        if self.session and not self.session.closed:
            logging.warning("HTTPClient session was not properly closed")
            if asyncio.get_event_loop().is_running():
                asyncio.create_task(self.close())

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10)
    )
    async def get(self, url: str, **kwargs) -> Any:
        """Make GET request with retry logic."""
        try:
            await self.ensure_session()
            async with self.session.get(url, **kwargs) as response:
                response.raise_for_status()
                return await response.json()
        except Exception as e:
            logging.error(f"HTTP GET failed for {url}: {str(e)}")
            raise NetworkError(f"Failed to fetch {url}") from e

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10)
    )
    async def post(self, url: str, **kwargs) -> Any:
        """Make POST request with retry logic."""
        try:
            await self.ensure_session()
            async with self.session.post(url, **kwargs) as response:
                response.raise_for_status()
                return await response.json()
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
            await self.ensure_session()
            async with self.session.get(url) as response:
                response.raise_for_status()
                output_path.parent.mkdir(parents=True, exist_ok=True)
                async with aiofiles.open(output_path, 'wb') as f:
                    async for chunk in response.content.iter_chunked(8192):
                        await f.write(chunk)
        except Exception as e:
            logging.error(f"Failed to download media from {url}: {str(e)}")
            raise NetworkError(f"Failed to download media from {url}") from e

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        retry=retry_if_exception_type((asyncio.TimeoutError, aiohttp.ClientError))
    )
    async def get_final_url(self, url: str) -> str:
        """Follow redirects to get the final URL."""
        try:
            await self.ensure_session()
            async with self.session.get(url, allow_redirects=True) as response:
                response.raise_for_status()
                final_url = str(response.url)
                logging.debug(f"Expanded URL {url} to {final_url}")
                return final_url
        except Exception as e:
            logging.error(f"Failed to expand URL {url}: {str(e)}")
            raise NetworkError(f"Failed to get final URL for {url}") from e
        
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
                    try:
                        logging.debug(f"Reading image file: {image_path}")
                        with open(image_path, 'rb') as f:
                            image_bytes = f.read()
                            image_base64 = base64.b64encode(image_bytes).decode('utf-8')
                            image_data.append(image_base64)
                            logging.debug(f"Successfully encoded image: {image_path} ({len(image_base64)} bytes)")
                    except Exception as e:
                        logging.error(f"Failed to read/encode image {image_path}: {e}")
                        raise ModelInferenceError(f"Failed to process image {image_path}: {e}")
                
                payload["images"] = image_data
                logging.debug(f"Added {len(image_data)} images to payload")

            logging.debug(f"Sending request to Ollama API with model {model}")
            logging.debug(f"Request payload size: {len(str(payload))} bytes")
            
            response = await self._client.post("/api/generate", json=payload)
            response.raise_for_status()
            
            # Log raw response for debugging
            raw_response = response.text
            logging.debug(f"Raw Ollama response: {raw_response[:200]}...")  # First 200 chars
            
            # Handle Ollama's response format
            try:
                data = response.json()
                logging.debug(f"Parsed response data: {data}")
                
                if not isinstance(data, dict):
                    raise ValueError(f"Expected JSON object in response, got: {type(data)}")
                
                response_text = data.get('response', '')
                if not response_text:
                    raise ValueError(f"Empty response from Ollama API: {data}")
                    
                logging.debug(f"Received valid response from Ollama API: {response_text[:100]}...")
                return response_text
                
            except ValueError as e:
                logging.error(f"Invalid JSON response from Ollama: {e}")
                raise ModelInferenceError(f"Failed to parse Ollama response: {e}")
            
        except Exception as e:
            logging.error(f"Ollama API call failed: {str(e)}")
            raise ModelInferenceError(f"Failed to generate response: {str(e)}")
