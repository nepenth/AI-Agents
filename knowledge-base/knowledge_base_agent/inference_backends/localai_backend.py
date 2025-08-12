"""
LocalAI Backend Implementation

This module provides the LocalAI backend implementation for the inference
backend system, using LocalAI's OpenAI-compatible API endpoints.
"""

import logging
import time
import asyncio
from typing import List, Dict, Any, Optional

from .base import InferenceBackend
from .errors import (
    BackendError, 
    BackendConnectionError, 
    BackendTimeoutError,
    BackendModelError,
    translate_http_error
)


class LocalAIBackend(InferenceBackend):
    """
    LocalAI backend implementation.
    
    This backend provides text generation, chat completion, and embedding
    functionality using LocalAI's OpenAI-compatible API endpoints.
    """
    
    def __init__(self, config, session_manager):
        """
        Initialize LocalAI backend.
        
        Args:
            config: Configuration object with LocalAI settings
            session_manager: HTTP session manager for API requests
        """
        super().__init__(config, session_manager)
        
        # LocalAI-specific configuration
        self._base_url = str(config.localai_api_url).rstrip('/')
        self.timeout = config.localai_timeout
        self.max_retries = config.localai_max_retries
        self.max_concurrent = config.localai_concurrent_requests
        
        # Create semaphore for controlling concurrency
        self._semaphore = asyncio.Semaphore(self.max_concurrent)
        
        self.logger.info(f"Initialized LocalAI backend with URL: {self._base_url}")
        self.logger.info(f"Settings: timeout={self.timeout}s, max_retries={self.max_retries}, "
                        f"max_concurrent={self.max_concurrent}")
    
    @property
    def backend_name(self) -> str:
        """Return the name of this backend."""
        return "localai"
    
    @property
    def base_url(self) -> str:
        """Return the base URL for this backend's API."""
        return self._base_url
    
    async def generate(
        self,
        model: str,
        prompt: str,
        temperature: float = 0.7,
        max_tokens: int = 50000,
        top_p: float = 0.9,
        timeout: Optional[int] = None,
        options: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Generate text completion using LocalAI API.
        
        LocalAI uses OpenAI-compatible endpoints, making this implementation
        straightforward and reliable.
        """
        return await self._localai_generate(
            model=model,
            prompt=prompt,
            temperature=temperature,
            max_tokens=max_tokens,
            top_p=top_p,
            timeout=timeout,
            options=options
        )
    
    async def chat(
        self,
        model: str,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        top_p: float = 0.9,
        timeout: Optional[int] = None,
        options: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Generate chat completion using LocalAI API.
        
        Uses the OpenAI-compatible /v1/chat/completions endpoint.
        """
        return await self._localai_chat(
            model=model,
            messages=messages,
            temperature=temperature,
            top_p=top_p,
            timeout=timeout,
            options=options
        )
    
    async def embed(
        self,
        model: str,
        text: str,
        timeout: Optional[int] = None
    ) -> List[float]:
        """
        Generate text embeddings using LocalAI API.
        
        Uses the OpenAI-compatible /v1/embeddings endpoint.
        """
        return await self._localai_embed(
            model=model,
            text=text,
            timeout=timeout
        )
    
    async def get_available_models(self) -> List[Dict[str, str]]:
        """
        Get list of available models from LocalAI API.
        
        Uses the OpenAI-compatible /v1/models endpoint.
        """
        try:
            async with self._semaphore:
                session = await self.session_manager._get_session()
                try:
                    api_endpoint = f"{self._base_url}/v1/models"
                    self.logger.debug(f"Fetching available models from {api_endpoint}")
                    
                    async with session.get(api_endpoint, timeout=10) as response:
                        if response.status != 200:
                            error_text = await response.text()
                            self.logger.error(f"LocalAI models API error: {response.status} - {error_text}")
                            raise BackendError(
                                f"Failed to fetch models: HTTP {response.status}",
                                self.backend_name,
                                error_code=f"HTTP_{response.status}"
                            )
                        
                        result = await response.json()
                        
                        # Extract models from OpenAI-compatible response
                        models = []
                        if 'data' in result:
                            for model_data in result['data']:
                                model_id = model_data.get('id', 'unknown')
                                models.append({
                                    'id': model_id,
                                    'name': f"LocalAI Model ({model_id})"
                                })
                        
                        self.logger.debug(f"Retrieved {len(models)} models from LocalAI")
                        return models
                        
                finally:
                    if session and not session.closed:
                        await session.close()
                        
        except Exception as e:
            self.logger.error(f"Error fetching LocalAI models: {e}", exc_info=True)
            raise translate_http_error(e, self.backend_name, "get_available_models")
    
    async def health_check(self) -> Dict[str, Any]:
        """
        Check the health status of the LocalAI backend.
        
        Returns:
            Dict containing health status information
        """
        try:
            # Test basic connectivity
            models = await self.get_available_models()
            
            # Test basic generation if models are available
            test_generation = None
            if models:
                try:
                    test_response = await self.generate(
                        model=models[0]['id'],
                        prompt="Test",
                        max_tokens=5,
                        timeout=10
                    )
                    test_generation = "success"
                except Exception as e:
                    test_generation = f"failed: {str(e)}"
            
            return {
                "status": "healthy",
                "backend": self.backend_name,
                "api_url": self._base_url,
                "available_models": len(models),
                "test_generation": test_generation,
                "configuration": {
                    "timeout": self.timeout,
                    "max_retries": self.max_retries,
                    "max_concurrent": self.max_concurrent
                }
            }
            
        except Exception as e:
            self.logger.error(f"LocalAI health check failed: {e}", exc_info=True)
            return {
                "status": "unhealthy",
                "backend": self.backend_name,
                "api_url": self._base_url,
                "error": str(e),
                "configuration": {
                    "timeout": self.timeout,
                    "max_retries": self.max_retries,
                    "max_concurrent": self.max_concurrent
                }
            }
    
    async def _localai_generate(
        self,
        model: str,
        prompt: str,
        temperature: float = 0.7,
        max_tokens: int = 50000,
        top_p: float = 0.9,
        timeout: Optional[int] = None,
        options: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Implementation of LocalAI text generation using OpenAI-compatible API.
        """
        request_timeout = timeout or self.timeout
        
        async with self._semaphore:
            for attempt in range(self.max_retries):
                try:
                    api_endpoint = f"{self._base_url}/v1/completions"
                    self.logger.debug(f"LocalAI generate request to {api_endpoint} (attempt {attempt + 1})")
                    self.logger.debug(f"Using model: {model}")
                    self.logger.debug(f"Prompt preview: {prompt[:200]}...")
                    
                    # OpenAI-compatible request format
                    payload = {
                        "model": model,
                        "prompt": prompt,
                        "max_tokens": max_tokens,
                        "temperature": temperature,
                        "top_p": top_p,
                        "stream": False
                    }
                    
                    # Handle additional options
                    if options:
                        # Map common options to OpenAI format
                        if 'stop' in options:
                            payload['stop'] = options['stop']
                        if 'seed' in options:
                            payload['seed'] = options['seed']
                        if 'frequency_penalty' in options:
                            payload['frequency_penalty'] = options['frequency_penalty']
                        if 'presence_penalty' in options:
                            payload['presence_penalty'] = options['presence_penalty']
                        if 'top_k' in options:
                            # LocalAI may support top_k as an extension
                            payload['top_k'] = options['top_k']
                    
                    self.logger.debug(f"LocalAI payload: {payload}")
                    
                    start_time = time.time()
                    session = await self.session_manager._get_session()
                    
                    try:
                        async with session.post(
                            api_endpoint,
                            json=payload,
                            timeout=request_timeout
                        ) as response:
                            if response.status != 200:
                                error_text = await response.text()
                                self.logger.error(f"LocalAI API error: {response.status} - {error_text}")
                                raise BackendError(
                                    f"LocalAI API returned status {response.status}",
                                    self.backend_name,
                                    error_code=f"HTTP_{response.status}"
                                )
                            
                            result = await response.json()
                            elapsed = time.time() - start_time
                            
                            # Extract response from OpenAI-compatible format
                            if 'choices' not in result or len(result['choices']) == 0:
                                raise BackendError(
                                    "LocalAI API returned no choices",
                                    self.backend_name
                                )
                            
                            response_text = result['choices'][0].get('text', '').strip()
                            
                            if not response_text:
                                raise BackendError(
                                    "Empty response from LocalAI API",
                                    self.backend_name
                                )
                            
                            self.logger.debug(f"Received response of length: {len(response_text)} in {elapsed:.2f}s")
                            return response_text
                            
                    finally:
                        if session and not session.closed:
                            await session.close()
                
                except Exception as e:
                    if attempt == self.max_retries - 1:
                        # Last attempt failed, raise the error
                        self.logger.error(f"LocalAI generate failed after {self.max_retries} attempts: {e}")
                        raise translate_http_error(e, self.backend_name, "generate", request_timeout)
                    else:
                        # Retry with exponential backoff
                        wait_time = 2 ** attempt
                        self.logger.warning(f"LocalAI generate attempt {attempt + 1} failed, retrying in {wait_time}s: {e}")
                        await asyncio.sleep(wait_time)
        
        # This should never be reached due to the retry logic above
        raise BackendError("Unexpected error in LocalAI generate", self.backend_name)
    
    async def _localai_chat(
        self,
        model: str,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        top_p: float = 0.9,
        timeout: Optional[int] = None,
        options: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Implementation of LocalAI chat completion using OpenAI-compatible API.
        """
        request_timeout = timeout or self.timeout
        
        async with self._semaphore:
            for attempt in range(self.max_retries):
                try:
                    api_endpoint = f"{self._base_url}/v1/chat/completions"
                    self.logger.debug(f"LocalAI chat request to {api_endpoint} (attempt {attempt + 1})")
                    self.logger.debug(f"Using model: {model}")
                    self.logger.debug(f"Messages preview: {str(messages)[:200]}...")
                    
                    # OpenAI-compatible chat request format
                    payload = {
                        "model": model,
                        "messages": messages,
                        "temperature": temperature,
                        "top_p": top_p,
                        "stream": False
                    }
                    
                    # Handle additional options
                    if options:
                        if 'max_tokens' in options:
                            payload['max_tokens'] = options['max_tokens']
                        if 'stop' in options:
                            payload['stop'] = options['stop']
                        if 'seed' in options:
                            payload['seed'] = options['seed']
                        if 'frequency_penalty' in options:
                            payload['frequency_penalty'] = options['frequency_penalty']
                        if 'presence_penalty' in options:
                            payload['presence_penalty'] = options['presence_penalty']
                        if 'tools' in options:
                            payload['tools'] = options['tools']
                        if 'tool_choice' in options:
                            payload['tool_choice'] = options['tool_choice']
                    
                    self.logger.debug(f"LocalAI chat payload: {str(payload)[:500]}...")
                    
                    start_time = time.time()
                    session = await self.session_manager._get_session()
                    
                    try:
                        async with session.post(
                            api_endpoint,
                            json=payload,
                            timeout=request_timeout
                        ) as response:
                            if response.status != 200:
                                error_text = await response.text()
                                self.logger.error(f"LocalAI chat API error: {response.status} - {error_text}")
                                raise BackendError(
                                    f"LocalAI chat API returned status {response.status}",
                                    self.backend_name,
                                    error_code=f"HTTP_{response.status}"
                                )
                            
                            result = await response.json()
                            elapsed = time.time() - start_time
                            
                            # Extract response from OpenAI-compatible format
                            if 'choices' not in result or len(result['choices']) == 0:
                                raise BackendError(
                                    "LocalAI chat API returned no choices",
                                    self.backend_name
                                )
                            
                            choice = result['choices'][0]
                            message = choice.get('message', {})
                            response_text = message.get('content', '').strip()
                            
                            # Handle tool calls if present
                            if 'tool_calls' in message and message['tool_calls']:
                                tool_calls = message['tool_calls']
                                self.logger.debug(f"Received {len(tool_calls)} tool calls from LocalAI")
                                if not response_text:
                                    response_text = f"[Tool calls: {len(tool_calls)} functions requested]"
                            
                            if not response_text:
                                raise BackendError(
                                    "Empty response from LocalAI chat API",
                                    self.backend_name
                                )
                            
                            self.logger.debug(f"Received chat response of length: {len(response_text)} in {elapsed:.2f}s")
                            return response_text
                            
                    finally:
                        if session and not session.closed:
                            await session.close()
                
                except Exception as e:
                    if attempt == self.max_retries - 1:
                        # Last attempt failed, raise the error
                        self.logger.error(f"LocalAI chat failed after {self.max_retries} attempts: {e}")
                        raise translate_http_error(e, self.backend_name, "chat", request_timeout)
                    else:
                        # Retry with exponential backoff
                        wait_time = 2 ** attempt
                        self.logger.warning(f"LocalAI chat attempt {attempt + 1} failed, retrying in {wait_time}s: {e}")
                        await asyncio.sleep(wait_time)
        
        # This should never be reached due to the retry logic above
        raise BackendError("Unexpected error in LocalAI chat", self.backend_name)
    
    async def _localai_embed(
        self,
        model: str,
        text: str,
        timeout: Optional[int] = None
    ) -> List[float]:
        """
        Implementation of LocalAI embedding generation using OpenAI-compatible API.
        """
        request_timeout = timeout or self.timeout
        
        async with self._semaphore:
            for attempt in range(self.max_retries):
                try:
                    # Validate input text
                    if not text or not text.strip():
                        raise BackendError(
                            "Cannot generate embedding for empty or whitespace-only content",
                            self.backend_name
                        )
                    
                    api_endpoint = f"{self._base_url}/v1/embeddings"
                    self.logger.debug(f"LocalAI embed request to {api_endpoint} (attempt {attempt + 1})")
                    self.logger.debug(f"Using model: {model}")
                    
                    text_length = len(text)
                    text_preview = text[:200] + "..." if len(text) > 200 else text
                    self.logger.debug(f"Generating embedding for content (length={text_length}): {text_preview}")
                    
                    # OpenAI-compatible embedding request format
                    payload = {
                        "model": model,
                        "input": text
                    }
                    
                    start_time = time.time()
                    session = await self.session_manager._get_session()
                    
                    try:
                        async with session.post(
                            api_endpoint,
                            json=payload,
                            timeout=request_timeout
                        ) as response:
                            if response.status != 200:
                                error_text = await response.text()
                                self.logger.error(f"LocalAI embedding API error: {response.status} - {error_text}")
                                raise BackendError(
                                    f"LocalAI embedding API returned status {response.status}",
                                    self.backend_name,
                                    error_code=f"HTTP_{response.status}"
                                )
                            
                            result = await response.json()
                            elapsed = time.time() - start_time
                            
                            # Extract embedding from OpenAI-compatible format
                            if 'data' not in result or len(result['data']) == 0:
                                raise BackendError(
                                    "LocalAI embedding API returned no data",
                                    self.backend_name
                                )
                            
                            embedding_data = result['data'][0]
                            embedding = embedding_data.get('embedding', [])
                            
                            if not embedding or len(embedding) == 0:
                                raise BackendError(
                                    "LocalAI API returned empty embedding",
                                    self.backend_name
                                )
                            
                            # Validate embedding dimensionality
                            if len(embedding) < 100:  # Most embedding models have at least 100 dimensions
                                raise BackendError(
                                    f"LocalAI embedding dimension too small: {len(embedding)}",
                                    self.backend_name
                                )
                            
                            self.logger.debug(f"Received embedding of dimension {len(embedding)} in {elapsed:.2f}s")
                            return embedding
                            
                    finally:
                        if session and not session.closed:
                            await session.close()
                
                except Exception as e:
                    if attempt == self.max_retries - 1:
                        # Last attempt failed, raise the error
                        self.logger.error(f"LocalAI embed failed after {self.max_retries} attempts: {e}")
                        raise translate_http_error(e, self.backend_name, "embed", request_timeout)
                    else:
                        # Retry with exponential backoff
                        wait_time = 2 ** attempt
                        self.logger.warning(f"LocalAI embed attempt {attempt + 1} failed, retrying in {wait_time}s: {e}")
                        await asyncio.sleep(wait_time)
        
        # This should never be reached due to the retry logic above
        raise BackendError("Unexpected error in LocalAI embed", self.backend_name)