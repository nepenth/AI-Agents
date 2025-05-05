import logging
import json
from typing import Optional, Dict, Any, AsyncGenerator

from ..config import Config
from ..exceptions import OllamaError
from .http_client import HttpClientManager

logger = logging.getLogger(__name__)

class OllamaClient:
    """
    Client for interacting with an Ollama API instance.
    """
    def __init__(self, config: Config, http_manager: Optional[HttpClientManager] = None):
        """
        Initializes the OllamaClient.

        Args:
            config: Application configuration object.
            http_manager: Optional shared HttpClientManager. If None, creates its own.
        """
        self.config = config
        self._http_manager = http_manager or HttpClientManager(base_url=str(config.ollama_url))
        # Flag to track if we created the manager internally (and thus should close it)
        self._owns_http_manager = http_manager is None
        logger.info(f"OllamaClient initialized for URL: {config.ollama_url}")

    async def _request(
        self,
        endpoint: str,
        payload: Dict[str, Any],
        stream: bool = False
    ) -> Dict[str, Any] | AsyncGenerator[Dict[str, Any], None]:
        """
        Makes a request to a specific Ollama API endpoint.

        Args:
            endpoint: The API endpoint path (e.g., '/api/generate').
            payload: The JSON payload for the request.
            stream: Whether to stream the response.

        Returns:
            The parsed JSON response if stream=False, or an async generator
            yielding response chunks if stream=True.

        Raises:
            OllamaError: If the API request fails.
        """
        logger.debug(f"Requesting Ollama endpoint '{endpoint}'. Stream: {stream}")
        try:
            client = await self._http_manager.get_client() # Use the managed client

            async with client.stream("POST", endpoint, json=payload) as response:
                # Always check status even for stream
                if response.status_code != 200:
                     # Consume body to get error details if possible
                     error_body = await response.aread()
                     logger.error(f"Ollama API error {response.status_code} at {endpoint}: {error_body.decode()}")
                     raise OllamaError(f"API Error {response.status_code}: {error_body.decode()}")

                if not stream:
                    # Read the entire response if not streaming
                    response_data = await response.aread()
                    logger.debug(f"Ollama endpoint '{endpoint}' non-stream response received.")
                    return response_data.json()
                else:
                    # Return the async generator directly
                    logger.debug(f"Ollama endpoint '{endpoint}' stream response initiated.")
                    async def stream_generator():
                         async for line in response.aiter_lines():
                             if line:
                                 try:
                                     yield json.loads(line)
                                 except json.JSONDecodeError:
                                     logger.warning(f"Failed to decode JSON line from Ollama stream: {line}")
                    return stream_generator()

        except Exception as e:
            if isinstance(e, OllamaError): # Re-raise specific Ollama errors
                raise e
            logger.error(f"Error communicating with Ollama endpoint {endpoint}: {e}", exc_info=True)
            raise OllamaError(f"Failed to communicate with Ollama at {endpoint}", original_exception=e) from e


    async def generate(
        self,
        prompt: str,
        model: Optional[str] = None,
        system_prompt: Optional[str] = None,
        stream: bool = False,
        **kwargs # Allow passing other Ollama params like temperature, etc.
    ) -> Dict[str, Any] | AsyncGenerator[Dict[str, Any], None]:
        """
        Generates text using the '/api/generate' endpoint.

        Args:
            prompt: The main input prompt.
            model: The model to use (defaults to config.text_model).
            system_prompt: An optional system prompt.
            stream: Whether to stream the response chunks.
            **kwargs: Additional parameters for the Ollama API.

        Returns:
            Parsed JSON response or async generator of chunks.
        """
        payload = {
            "model": model or self.config.text_model,
            "prompt": prompt,
            "stream": stream,
            **kwargs
        }
        if system_prompt:
            payload["system"] = system_prompt

        logger.info(f"Generating text with model '{payload['model']}'. Stream: {stream}")
        return await self._request("/api/generate", payload, stream=stream)

    async def generate_image_description(
        self,
        image_bytes: bytes,
        prompt: str = "Describe this image in detail.",
        model: Optional[str] = None,
        stream: bool = False,
        **kwargs
    ) -> Dict[str, Any] | AsyncGenerator[Dict[str, Any], None]:
        """
        Generates text based on an image using a multimodal model (e.g., llava).

        Args:
            image_bytes: The image content as bytes.
            prompt: The text prompt to accompany the image.
            model: The vision model to use (defaults to config.vision_model).
            stream: Whether to stream the response.
            **kwargs: Additional parameters for the Ollama API.

        Returns:
            Parsed JSON response or async generator of chunks.
        """
        import base64
        encoded_image = base64.b64encode(image_bytes).decode('utf-8')

        payload = {
            "model": model or self.config.vision_model,
            "prompt": prompt,
            "images": [encoded_image],
            "stream": stream,
            **kwargs
        }
        logger.info(f"Generating image description with model '{payload['model']}'. Stream: {stream}")
        # Uses the same /api/generate endpoint which handles multimodal input
        return await self._request("/api/generate", payload, stream=stream)


    async def close(self):
        """Closes the underlying HTTP client if owned by this instance."""
        if self._owns_http_manager and self._http_manager:
            await self._http_manager.close()

    async def __aenter__(self):
        # Ensure HTTP manager is initialized if needed
        await self._http_manager.get_client()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()
