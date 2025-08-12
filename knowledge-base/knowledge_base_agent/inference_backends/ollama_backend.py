"""
Ollama Backend Implementation

This module provides the Ollama backend implementation that wraps the existing
Ollama functionality in the new backend interface for consistency.
"""

import logging
import time
import asyncio
from typing import List, Dict, Any, Optional
import aiohttp

from .base import InferenceBackend
from .errors import (
    BackendError, 
    BackendConnectionError, 
    BackendTimeoutError,
    BackendModelError,
    translate_http_error
)


class OllamaBackend(InferenceBackend):
    """
    Ollama backend implementation.
    
    This backend wraps the existing Ollama functionality to provide
    a consistent interface with other backends while maintaining
    full compatibility and performance.
    """
    
    def __init__(self, config, session_manager):
        """
        Initialize Ollama backend.
        
        Args:
            config: Configuration object with Ollama settings
            session_manager: HTTP session manager for API requests
        """
        super().__init__(config, session_manager)
        
        # Ollama-specific configuration
        self._base_url = str(config.ollama_url).rstrip('/')
        self.timeout = config.request_timeout
        self.max_retries = config.max_retries
        self.max_concurrent = config.max_concurrent_requests
        
        # Create semaphore for controlling concurrency
        self._semaphore = asyncio.Semaphore(self.max_concurrent)
        
        self.logger.info(f"Initialized Ollama backend with URL: {self._base_url}")
        self.logger.info(f"Settings: timeout={self.timeout}s, max_retries={self.max_retries}, "
                        f"max_concurrent={self.max_concurrent}")
    
    @property
    def backend_name(self) -> str:
        """Return the name of this backend."""
        return "ollama"
    
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
        Generate text completion using Ollama API.
        
        This method delegates to the existing Ollama implementation
        to maintain full compatibility and performance.
        """
        return await self._ollama_generate(
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
        Generate chat completion using Ollama API.
        
        This method delegates to the existing Ollama implementation
        to maintain full compatibility and performance.
        """
        return await self._ollama_chat(
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
        Generate text embeddings using Ollama API.
        
        This method delegates to the existing Ollama implementation
        to maintain full compatibility and performance.
        """
        return await self._ollama_embed(
            model=model,
            prompt=text,  # Ollama uses 'prompt' parameter
            timeout=timeout
        )
    
    async def get_available_models(self) -> List[Dict[str, str]]:
        """
        Get list of available models from Ollama API.
        
        Returns:
            List of model dictionaries with 'id' and 'name' keys
        """
        try:
            async with self._semaphore:
                session = await self.session_manager._get_session()
                try:
                    api_endpoint = f"{self._base_url}/api/tags"
                    self.logger.debug(f"Fetching available models from {api_endpoint}")
                    
                    async with session.get(api_endpoint, timeout=10) as response:
                        if response.status != 200:
                            error_text = await response.text()
                            self.logger.error(f"Ollama models API error: {response.status} - {error_text}")
                            raise BackendError(
                                f"Failed to fetch models: HTTP {response.status}",
                                self.backend_name,
                                error_code=f"HTTP_{response.status}"
                            )
                        
                        result = await response.json()
                        
                        # Extract models from Ollama response
                        models = []
                        if 'models' in result:
                            for model_data in result['models']:
                                model_name = model_data.get('name', 'unknown')
                                models.append({
                                    'id': model_name,
                                    'name': f"Ollama Model ({model_name})"
                                })
                        
                        self.logger.debug(f"Retrieved {len(models)} models from Ollama")
                        return models
                        
                finally:
                    if session and not session.closed:
                        await session.close()
                        
        except Exception as e:
            self.logger.error(f"Error fetching Ollama models: {e}", exc_info=True)
            raise translate_http_error(e, self.backend_name, "get_available_models")
    
    async def health_check(self) -> Dict[str, Any]:
        """
        Check the health status of the Ollama backend.
        
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
            self.logger.error(f"Ollama health check failed: {e}", exc_info=True)
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
    
    # ===== EXISTING OLLAMA IMPLEMENTATION =====
    # These methods contain the existing Ollama functionality
    
    async def _ollama_generate(
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
        Generate text using Ollama API with consistent parameters.
        
        This is the existing Ollama implementation moved into the backend.
        """
        request_timeout = timeout or self.timeout
        
        async with self._semaphore:
            try:
                api_endpoint = f"{self._base_url}/api/generate"
                self.logger.debug(f"Sending Ollama request to {api_endpoint}")
                self.logger.debug(f"Using model: {model}")
                self.logger.debug(f"Prompt preview: {prompt[:200]}...")

                payload = {
                    "model": model,
                    "prompt": prompt,
                    "stream": False,
                    "options": {
                        "temperature": temperature,
                        "top_p": top_p,
                        "num_predict": max_tokens
                    }
                }
                
                # Add options from the function parameters
                if options:
                    # Handle JSON mode if enabled
                    if options.get("json_mode") is True:
                        if hasattr(self.config, 'ollama_supports_json_mode') and self.config.ollama_supports_json_mode:
                            payload["format"] = "json"
                            self.logger.info(f"Ollama JSON mode enabled for model {model} due to options and config.")
                        else:
                            self.logger.warning(f"JSON mode requested for Ollama model {model}, but not enabled in config (ollama_supports_json_mode=False). Sending as plain text.")
                    
                    # Add standard Ollama parameters
                    standard_params = [
                        'seed', 'stop', 'num_keep', 'num_ctx', 'num_batch', 'num_gpu', 'main_gpu',
                        'low_vram', 'vocab_only', 'use_mmap', 'use_mlock', 'num_thread', 'repeat_last_n',
                        'repeat_penalty', 'presence_penalty', 'frequency_penalty', 'mirostat', 
                        'mirostat_tau', 'mirostat_eta', 'penalize_newline', 'tfs_z', 'typical_p',
                        'top_k', 'min_p'
                    ]
                    
                    for param in standard_params:
                        if param in options:
                            payload["options"][param] = options[param]
                    
                    # Handle special parameters at top level
                    if "keep_alive" in options:
                        payload["keep_alive"] = options["keep_alive"]
                    
                    if "system" in options:
                        payload["system"] = options["system"]
                    
                    if "template" in options:
                        payload["template"] = options["template"]
                    
                    if "context" in options:
                        payload["context"] = options["context"]
                    
                    if "raw" in options:
                        payload["raw"] = options["raw"]
                    
                    # Handle images for multimodal models
                    if "images" in options:
                        payload["images"] = options["images"]
                
                # Log the complete payload for debugging
                self.logger.debug(f"Complete Ollama payload: {payload}")
                
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
                            self.logger.error(f"Ollama API error: {response.status} - {error_text}")
                            self.logger.error(f"Request URL: {api_endpoint}, Payload: {payload}")
                            raise BackendError(f"Ollama API returned status {response.status}", self.backend_name)
                        
                        result = await response.json()
                        elapsed = time.time() - start_time
                        
                        response_text = result.get("response", "").strip()
                        if not response_text:
                            if payload.get("format") == "json":
                                 self.logger.error(f"Ollama API returned empty 'response' field in JSON mode. Full result: {result}")
                                 raise BackendError("Empty 'response' field from Ollama API in JSON mode.", self.backend_name)
                            else:
                                 raise BackendError("Empty response from Ollama API", self.backend_name)
                        
                        self.logger.debug(f"Received response of length: {len(response_text)} in {elapsed:.2f}s. Model: {model}. JSON mode: {payload.get('format') == 'json'}")
                        
                        return response_text
                finally:
                    # Always close the session
                    if session and not session.closed:
                        await session.close()
                    
            except Exception as e:
                self.logger.error(f"Error in ollama_generate with model {model}: {str(e)}", exc_info=True)
                raise translate_http_error(e, self.backend_name, "generate", request_timeout)
    
    async def _ollama_chat(
        self,
        model: str,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        top_p: float = 0.9,
        timeout: Optional[int] = None,
        options: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Generate text using Ollama chat API with messages format for reasoning models.
        
        This is the existing Ollama chat implementation moved into the backend.
        """
        request_timeout = timeout or self.timeout
        
        async with self._semaphore:
            try:
                api_endpoint = f"{self._base_url}/api/chat"
                self.logger.debug(f"Sending Ollama chat request to {api_endpoint}")
                self.logger.debug(f"Using model: {model}")
                self.logger.debug(f"Messages preview: {str(messages)[:200]}...")

                payload = {
                    "model": model,
                    "messages": messages,
                    "stream": False,
                    "options": {
                        "temperature": temperature,
                        "top_p": top_p
                    }
                }

                # Add options from the function parameters
                if options:
                    # Handle JSON mode if enabled
                    if options.get("json_mode") is True:
                        if hasattr(self.config, 'ollama_supports_json_mode') and self.config.ollama_supports_json_mode:
                            payload["format"] = "json"
                            self.logger.info(f"Ollama JSON mode enabled for chat with model {model}")
                        else:
                            self.logger.warning(f"JSON mode requested for Ollama chat model {model}, but not enabled in config")
                    
                    # Handle tools for function calling
                    if "tools" in options:
                        payload["tools"] = options["tools"]
                        # Tools require stream=false, which we already set
                        self.logger.debug(f"Added {len(options['tools'])} tools to chat request")
                    
                    # Add standard Ollama parameters to options
                    standard_params = [
                        'seed', 'num_keep', 'num_ctx', 'num_batch', 'num_gpu', 'main_gpu',
                        'low_vram', 'vocab_only', 'use_mmap', 'use_mlock', 'num_thread', 'repeat_last_n',
                        'repeat_penalty', 'presence_penalty', 'frequency_penalty', 'mirostat', 
                        'mirostat_tau', 'mirostat_eta', 'penalize_newline', 'tfs_z', 'typical_p',
                        'top_k', 'min_p', 'stop', 'num_predict'
                    ]
                    
                    for param in standard_params:
                        if param in options:
                            payload["options"][param] = options[param]
                    
                    # Handle top-level parameters
                    if "keep_alive" in options:
                        payload["keep_alive"] = options["keep_alive"]
                
                # Log the complete payload for debugging
                self.logger.debug(f"Complete Ollama chat payload: {str(payload)[:500]}...")
                
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
                            self.logger.error(f"Ollama chat API error: {response.status} - {error_text}")
                            self.logger.error(f"Request URL: {api_endpoint}, Payload: {str(payload)[:500]}")
                            raise BackendError(f"Ollama chat API returned status {response.status}", self.backend_name)
                        
                        result = await response.json()
                        elapsed = time.time() - start_time
                        
                        # Chat API returns a different format
                        if "message" not in result or not isinstance(result.get("message"), dict):
                            self.logger.error(f"Ollama chat API returned unexpected response format: {result}")
                            raise BackendError("Unexpected response format from Ollama chat API", self.backend_name)
                        
                        response_message = result.get("message", {})
                        
                        # Handle tool calls if present
                        if "tool_calls" in response_message:
                            # For tool calls, we might want to return structured data
                            # but for now, return the content if available
                            response_text = response_message.get("content", "").strip()
                            if not response_text:
                                # If no content but has tool calls, return a structured response
                                tool_calls = response_message["tool_calls"]
                                self.logger.debug(f"Received {len(tool_calls)} tool calls from model")
                                response_text = f"[Tool calls: {len(tool_calls)} functions requested]"
                        else:
                            response_text = response_message.get("content", "").strip()
                        
                        if not response_text:
                            self.logger.error(f"Ollama chat API returned empty response: {result}")
                            raise BackendError("Empty response from Ollama chat API", self.backend_name)
                        
                        self.logger.debug(f"Received chat response of length: {len(response_text)} in {elapsed:.2f}s. Model: {model}")
                        
                        return response_text
                finally:
                    # Always close the session
                    if session and not session.closed:
                        await session.close()
                    
            except Exception as e:
                self.logger.error(f"Error in ollama_chat with model {model}: {str(e)}", exc_info=True)
                raise translate_http_error(e, self.backend_name, "chat", request_timeout)
    
    async def _ollama_embed(
        self,
        model: str,
        prompt: str,
        timeout: Optional[int] = None
    ) -> List[float]:
        """
        Generate embeddings using Ollama's /api/embed endpoint.
        
        This is the existing Ollama embed implementation moved into the backend.
        """
        request_timeout = timeout or self.timeout
        async with self._semaphore:
            try:
                # Validate input prompt
                if not prompt or not prompt.strip():
                    self.logger.error(f"Empty or whitespace-only prompt provided for embedding: '{prompt}'")
                    raise BackendError("Cannot generate embedding for empty or whitespace-only content", self.backend_name)
                
                # Log prompt details for debugging
                prompt_length = len(prompt)
                prompt_preview = prompt[:200] + "..." if len(prompt) > 200 else prompt
                self.logger.debug(f"Generating embedding for content (length={prompt_length}): {prompt_preview}")
                
                api_endpoint = f"{self._base_url}/api/embed"
                self.logger.debug(f"Sending Ollama embedding request to {api_endpoint} for model {model}")

                # Updated payload to match Ollama API specification
                payload = {
                    "model": model,
                    "input": prompt  # Changed from "prompt" to "input"
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
                            self.logger.error(f"Ollama embedding API error: {response.status} - {error_text}")
                            raise BackendError(f"Ollama embedding API returned status {response.status}: {error_text}", self.backend_name)

                        result = await response.json()
                        elapsed = time.time() - start_time
                        
                        # Log the full response for debugging
                        self.logger.debug(f"Raw Ollama embedding response: {result}")
                        
                        # Updated to match new API response format
                        embeddings = result.get("embeddings")
                        if embeddings is None:
                            self.logger.error(f"Ollama API returned None for embeddings. Full response: {result}")
                            raise BackendError("Ollama API returned None for embeddings field", self.backend_name)
                        
                        if not isinstance(embeddings, list) or len(embeddings) == 0:
                            self.logger.error(f"Ollama API returned invalid embeddings format: {type(embeddings)} - {embeddings}")
                            raise BackendError(f"Ollama API returned invalid embeddings format: {type(embeddings)}", self.backend_name)
                        
                        # Extract the first embedding from the array
                        embedding = embeddings[0]
                        if not isinstance(embedding, list):
                            self.logger.error(f"Ollama API returned non-list embedding: {type(embedding)} - {embedding}")
                            raise BackendError(f"Ollama API returned non-list embedding: {type(embedding)}", self.backend_name)
                        
                        if len(embedding) == 0:
                            self.logger.error(f"Ollama API returned empty embedding list. Full response: {result}")
                            raise BackendError("Ollama API returned empty embedding list", self.backend_name)

                        self.logger.debug(f"Received embedding of dimension {len(embedding)} in {elapsed:.2f}s. Model: {model}")
                        return embedding
                finally:
                    # Always close the session
                    if session and not session.closed:
                        await session.close()

            except Exception as e:
                self.logger.error(f"Error in ollama_embed with model {model}: {str(e)}", exc_info=True)
                raise translate_http_error(e, self.backend_name, "embed", request_timeout)