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
import os

class HTTPClient:
    """HTTP client for making requests to external services."""
    
    def __init__(self, config: Config):
        self.config = config
        self.session = None
        self.initialized = False
        self.base_url = str(self.config.ollama_url).rstrip('/')
        self.timeout = self.config.request_timeout
        self.max_retries = self.config.max_retries
        self.batch_size = self.config.batch_size
        self.max_concurrent = self.config.max_concurrent_requests
        
        # Create semaphore for controlling concurrency
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
        stop=stop_after_attempt(lambda self: self.max_retries),
        wait=wait_exponential(multiplier=2, min=5, max=30),
        retry=retry_if_exception_type((asyncio.TimeoutError, aiohttp.ClientError))
    )
    async def ollama_generate(
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
        
        Args:
            model: The model to use for generation (from config.text_model)
            prompt: The prompt text
            temperature: Controls randomness (0.0-1.0)
            max_tokens: Maximum tokens to generate
            top_p: Nucleus sampling parameter
            timeout: Request timeout in seconds (defaults to config.request_timeout)
            options: Additional options, e.g., {"json_mode": True, "seed": 42, "stop": ["\\n"]}
        
        Returns:
            str: Generated text response
            
        Raises:
            AIError: If the API request fails or returns invalid response
            TimeoutError: If the request exceeds the timeout period
        """
        request_timeout = timeout or self.timeout
        
        async with self._semaphore:
            await self.ensure_session()
            
            try:
                api_endpoint = f"{self.base_url}/api/generate"
                logging.debug(f"Sending Ollama request to {api_endpoint}")
                logging.debug(f"Using model: {model}")
                logging.debug(f"Prompt preview: {prompt[:200]}...")

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
                            logging.info(f"Ollama JSON mode enabled for model {model} due to options and config.")
                        else:
                            logging.warning(f"JSON mode requested for Ollama model {model}, but not enabled in config (ollama_supports_json_mode=False). Sending as plain text.")
                    
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
                logging.debug(f"Complete Ollama payload: {payload}")
                
                start_time = time.time()
                async with self.session.post(
                    api_endpoint,
                    json=payload,
                    timeout=request_timeout
                ) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        logging.error(f"Ollama API error: {response.status} - {error_text}")
                        logging.error(f"Request URL: {api_endpoint}, Payload: {payload}")
                        raise AIError(f"Ollama API returned status {response.status}")
                    
                    result = await response.json()
                    elapsed = time.time() - start_time
                    
                    response_text = result.get("response", "").strip()
                    if not response_text:
                        if payload.get("format") == "json":
                             logging.error(f"Ollama API returned empty 'response' field in JSON mode. Full result: {result}")
                             raise AIError("Empty 'response' field from Ollama API in JSON mode.")
                        else:
                             raise AIError("Empty response from Ollama API")
                    
                    logging.debug(f"Received response of length: {len(response_text)} in {elapsed:.2f}s. Model: {model}. JSON mode: {payload.get('format') == 'json'}")
                    
                    if self.batch_size > 1:
                        await asyncio.sleep(0.1)
                        
                    return response_text
                    
            except asyncio.TimeoutError:
                logging.error(f"Ollama request timed out after {request_timeout} seconds for model {model}")
                raise AIError(f"Request timed out after {request_timeout} seconds")
            except aiohttp.ClientError as e:
                logging.error(f"HTTP client error with Ollama: {str(e)} for model {model}")
                raise AIError(f"HTTP client error: {str(e)}")
            except Exception as e:
                logging.error(f"Unexpected error in ollama_generate with model {model}: {str(e)}", exc_info=True)
                raise AIError(f"Failed to generate text with Ollama: {str(e)}")
            
    async def ollama_chat(
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
        
        Args:
            model: The model to use for generation (from config.text_model)
            messages: List of message objects with 'role' and 'content' keys
            temperature: Controls randomness (0.0-1.0)
            top_p: Nucleus sampling parameter
            timeout: Request timeout in seconds (defaults to config.request_timeout)
            options: Additional options, e.g., {"json_mode": True, "tools": [...], "keep_alive": "5m"}
        
        Returns:
            str: Generated text response
            
        Raises:
            AIError: If the API request fails or returns invalid response
            TimeoutError: If the request exceeds the timeout period
        """
        request_timeout = timeout or self.timeout
        
        async with self._semaphore:
            await self.ensure_session()
            
            try:
                api_endpoint = f"{self.base_url}/api/chat"
                logging.debug(f"Sending Ollama chat request to {api_endpoint}")
                logging.debug(f"Using model: {model}")
                logging.debug(f"Messages preview: {str(messages)[:200]}...")

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
                            logging.info(f"Ollama JSON mode enabled for chat with model {model}")
                        else:
                            logging.warning(f"JSON mode requested for Ollama chat model {model}, but not enabled in config")
                    
                    # Handle tools for function calling
                    if "tools" in options:
                        payload["tools"] = options["tools"]
                        # Tools require stream=false, which we already set
                        logging.debug(f"Added {len(options['tools'])} tools to chat request")
                    
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
                logging.debug(f"Complete Ollama chat payload: {str(payload)[:500]}...")
                
                start_time = time.time()
                async with self.session.post(
                    api_endpoint,
                    json=payload,
                    timeout=request_timeout
                ) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        logging.error(f"Ollama chat API error: {response.status} - {error_text}")
                        logging.error(f"Request URL: {api_endpoint}, Payload: {str(payload)[:500]}")
                        raise AIError(f"Ollama chat API returned status {response.status}")
                    
                    result = await response.json()
                    elapsed = time.time() - start_time
                    
                    # Chat API returns a different format
                    if "message" not in result or not isinstance(result.get("message"), dict):
                        logging.error(f"Ollama chat API returned unexpected response format: {result}")
                        raise AIError("Unexpected response format from Ollama chat API")
                    
                    response_message = result.get("message", {})
                    
                    # Handle tool calls if present
                    if "tool_calls" in response_message:
                        # For tool calls, we might want to return structured data
                        # but for now, return the content if available
                        response_text = response_message.get("content", "").strip()
                        if not response_text:
                            # If no content but has tool calls, return a structured response
                            tool_calls = response_message["tool_calls"]
                            logging.debug(f"Received {len(tool_calls)} tool calls from model")
                            response_text = f"[Tool calls: {len(tool_calls)} functions requested]"
                    else:
                        response_text = response_message.get("content", "").strip()
                    
                    if not response_text:
                        logging.error(f"Ollama chat API returned empty response: {result}")
                        raise AIError("Empty response from Ollama chat API")
                    
                    logging.debug(f"Received chat response of length: {len(response_text)} in {elapsed:.2f}s. Model: {model}")
                    
                    if self.batch_size > 1:
                        await asyncio.sleep(0.1)
                        
                    return response_text
                    
            except asyncio.TimeoutError:
                logging.error(f"Ollama chat request timed out after {request_timeout} seconds for model {model}")
                raise AIError(f"Chat request timed out after {request_timeout} seconds")
            except aiohttp.ClientError as e:
                logging.error(f"HTTP client error with Ollama chat: {str(e)} for model {model}")
                raise AIError(f"HTTP client error in chat: {str(e)}")
            except Exception as e:
                logging.error(f"Unexpected error in ollama_chat with model {model}: {str(e)}", exc_info=True)
                raise AIError(f"Failed to generate text with Ollama chat: {str(e)}")
            
    async def ollama_embed(
        self,
        model: str,
        prompt: str,
        timeout: Optional[int] = None
    ) -> List[float]:
        """
        Generate embeddings using Ollama's /api/embed endpoint.

        Args:
            model: The embedding model to use.
            prompt: The text to embed.
            timeout: Request timeout in seconds.

        Returns:
            List[float]: The generated embedding vector.

        Raises:
            AIError: If the API request fails.
        """
        request_timeout = timeout or self.timeout
        async with self._semaphore:
            await self.ensure_session()
            try:
                # Validate input prompt
                if not prompt or not prompt.strip():
                    logging.error(f"Empty or whitespace-only prompt provided for embedding: '{prompt}'")
                    raise AIError("Cannot generate embedding for empty or whitespace-only content")
                
                # Log prompt details for debugging
                prompt_length = len(prompt)
                prompt_preview = prompt[:200] + "..." if len(prompt) > 200 else prompt
                logging.debug(f"Generating embedding for content (length={prompt_length}): {prompt_preview}")
                
                api_endpoint = f"{self.base_url}/api/embed"
                logging.debug(f"Sending Ollama embedding request to {api_endpoint} for model {model}")

                # Updated payload to match Ollama API specification
                payload = {
                    "model": model,
                    "input": prompt  # Changed from "prompt" to "input"
                }

                start_time = time.time()
                async with self.session.post(
                    api_endpoint,
                    json=payload,
                    timeout=request_timeout
                ) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        logging.error(f"Ollama embedding API error: {response.status} - {error_text}")
                        raise AIError(f"Ollama embedding API returned status {response.status}: {error_text}")

                    result = await response.json()
                    elapsed = time.time() - start_time
                    
                    # Log the full response for debugging
                    logging.debug(f"Raw Ollama embedding response: {result}")
                    
                    # Updated to match new API response format
                    embeddings = result.get("embeddings")
                    if embeddings is None:
                        logging.error(f"Ollama API returned None for embeddings. Full response: {result}")
                        raise AIError("Ollama API returned None for embeddings field")
                    
                    if not isinstance(embeddings, list) or len(embeddings) == 0:
                        logging.error(f"Ollama API returned invalid embeddings format: {type(embeddings)} - {embeddings}")
                        raise AIError(f"Ollama API returned invalid embeddings format: {type(embeddings)}")
                    
                    # Extract the first embedding from the array
                    embedding = embeddings[0]
                    if not isinstance(embedding, list):
                        logging.error(f"Ollama API returned non-list embedding: {type(embedding)} - {embedding}")
                        raise AIError(f"Ollama API returned non-list embedding: {type(embedding)}")
                    
                    if len(embedding) == 0:
                        logging.error(f"Ollama API returned empty embedding list. Full response: {result}")
                        raise AIError("Ollama API returned empty embedding list")

                    logging.debug(f"Received embedding of dimension {len(embedding)} in {elapsed:.2f}s. Model: {model}")
                    return embedding

            except asyncio.TimeoutError:
                logging.error(f"Ollama embedding request timed out after {request_timeout} seconds for model {model}")
                raise AIError(f"Embedding request timed out after {request_timeout} seconds")
            except aiohttp.ClientError as e:
                logging.error(f"HTTP client error with Ollama embeddings: {str(e)} for model {model}")
                raise AIError(f"HTTP client error for embeddings: {str(e)}")
            except Exception as e:
                logging.error(f"Unexpected error in ollama_embed with model {model}: {str(e)}", exc_info=True)
                raise AIError(f"Failed to generate embeddings with Ollama: {str(e)}")

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
        
    def _get_optimized_options(self, model: str, task_type: str = "general") -> Dict[str, Any]:
        """
        Get optimized Ollama options based on model type, task, and system configuration.
        
        Args:
            model: The model name being used
            task_type: Type of task ('text', 'vision', 'embedding', 'synthesis', 'categorization')
            
        Returns:
            Dict containing optimized options for the Ollama API call
        """
        options = {}
        
        # Base performance options from config
        if hasattr(self.config, 'ollama_num_gpu') and self.config.ollama_num_gpu != -1:
            options['num_gpu'] = self.config.ollama_num_gpu
            
        if hasattr(self.config, 'ollama_main_gpu'):
            options['main_gpu'] = self.config.ollama_main_gpu
            
        if hasattr(self.config, 'ollama_low_vram') and self.config.ollama_low_vram:
            options['low_vram'] = True
            
        if hasattr(self.config, 'ollama_use_mmap'):
            options['use_mmap'] = self.config.ollama_use_mmap
            
        if hasattr(self.config, 'ollama_use_mlock') and self.config.ollama_use_mlock:
            options['use_mlock'] = True
            
        if hasattr(self.config, 'ollama_num_threads') and self.config.ollama_num_threads > 0:
            options['num_thread'] = self.config.ollama_num_threads
            
        # Context and batch optimization
        if hasattr(self.config, 'ollama_num_ctx') and self.config.ollama_num_ctx > 0:
            options['num_ctx'] = self.config.ollama_num_ctx
            
        if hasattr(self.config, 'ollama_num_batch') and self.config.ollama_num_batch > 0:
            options['num_batch'] = self.config.ollama_num_batch
        elif hasattr(self.config, 'ollama_adaptive_batch_size') and self.config.ollama_adaptive_batch_size:
            # Adaptive batch sizing based on available GPU memory
            if hasattr(self.config, 'gpu_total_memory') and self.config.gpu_total_memory > 0:
                if self.config.gpu_total_memory >= 32000:  # 32GB+
                    options['num_batch'] = 2048
                elif self.config.gpu_total_memory >= 16000:  # 16GB+
                    options['num_batch'] = 1024
                elif self.config.gpu_total_memory >= 8000:   # 8GB+
                    options['num_batch'] = 512
                else:
                    options['num_batch'] = 256
                    
        if hasattr(self.config, 'ollama_num_keep') and self.config.ollama_num_keep > 0:
            options['num_keep'] = self.config.ollama_num_keep
            
        # Quality and output control
        if hasattr(self.config, 'ollama_repeat_penalty'):
            options['repeat_penalty'] = self.config.ollama_repeat_penalty
            
        if hasattr(self.config, 'ollama_repeat_last_n'):
            options['repeat_last_n'] = self.config.ollama_repeat_last_n
            
        if hasattr(self.config, 'ollama_top_k') and self.config.ollama_top_k > 0:
            options['top_k'] = self.config.ollama_top_k
            
        if hasattr(self.config, 'ollama_min_p') and self.config.ollama_min_p > 0:
            options['min_p'] = self.config.ollama_min_p
            
        # Stop sequences
        if hasattr(self.config, 'ollama_stop_sequences') and self.config.ollama_stop_sequences:
            options['stop'] = self.config.ollama_stop_sequences
            
        # Seed for reproducibility
        if hasattr(self.config, 'ollama_seed') and self.config.ollama_seed != -1:
            options['seed'] = self.config.ollama_seed
            
        # Task-specific optimizations
        if task_type == 'synthesis':
            # Synthesis benefits from longer context and higher quality
            options['temperature'] = 0.3  # More focused
            options['repeat_penalty'] = 1.2  # Reduce repetition
            if 'num_ctx' not in options:
                options['num_ctx'] = 8192  # Larger context for synthesis
                
        elif task_type == 'categorization':
            # Categorization needs consistency and speed
            options['temperature'] = 0.1  # Very focused
            options['top_k'] = 20  # Limit options
            if 'num_ctx' not in options:
                options['num_ctx'] = 4096  # Moderate context
                
        elif task_type == 'vision':
            # Vision models need more GPU memory and processing power
            if hasattr(self.config, 'ollama_vision_model_gpu_layers') and self.config.ollama_vision_model_gpu_layers != -1:
                options['num_gpu'] = self.config.ollama_vision_model_gpu_layers
                
        elif task_type == 'embedding':
            # Embeddings benefit from consistency and speed
            if hasattr(self.config, 'ollama_embedding_model_gpu_layers') and self.config.ollama_embedding_model_gpu_layers != -1:
                options['num_gpu'] = self.config.ollama_embedding_model_gpu_layers
                
        # Model loading optimization
        if hasattr(self.config, 'ollama_keep_alive'):
            options['keep_alive'] = self.config.ollama_keep_alive
            
        logging.debug(f"Optimized options for {task_type} task with model {model}: {options}")
        return options

    async def ollama_generate_optimized(
        self,
        model: str,
        prompt: str,
        task_type: str = "general",
        temperature: float = 0.7,
        max_tokens: int = 50000,
        top_p: float = 0.9,
        timeout: Optional[int] = None,
        additional_options: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Generate text using Ollama API with intelligent optimization based on task type.
        
        Args:
            model: The model to use for generation
            prompt: The prompt text
            task_type: Type of task for optimization ('synthesis', 'categorization', 'vision', 'general')
            temperature: Controls randomness (0.0-1.0)
            max_tokens: Maximum tokens to generate
            top_p: Nucleus sampling parameter
            timeout: Request timeout in seconds
            additional_options: Additional options to merge with optimized options
        
        Returns:
            str: Generated text response
        """
        # Get optimized options for this task type
        options = self._get_optimized_options(model, task_type)
        
        # Apply task-specific temperature if not overridden
        if task_type in ['synthesis', 'categorization']:
            temperature = options.get('temperature', temperature)
            
        # Merge with additional options
        if additional_options:
            options.update(additional_options)
            
        return await self.ollama_generate(
            model=model,
            prompt=prompt,
            temperature=temperature,
            max_tokens=max_tokens,
            top_p=top_p,
            timeout=timeout,
            options=options
        )

    async def ollama_chat_optimized(
        self,
        model: str,
        messages: List[Dict[str, str]],
        task_type: str = "general",
        temperature: float = 0.7,
        top_p: float = 0.9,
        timeout: Optional[int] = None,
        additional_options: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Generate text using Ollama chat API with intelligent optimization.
        
        Args:
            model: The model to use for generation
            messages: List of message objects with 'role' and 'content' keys
            task_type: Type of task for optimization
            temperature: Controls randomness (0.0-1.0)
            top_p: Nucleus sampling parameter
            timeout: Request timeout in seconds
            additional_options: Additional options to merge with optimized options
        
        Returns:
            str: Generated text response
        """
        # Get optimized options for this task type
        options = self._get_optimized_options(model, task_type)
        
        # Apply task-specific temperature if not overridden
        if task_type in ['synthesis', 'categorization']:
            temperature = options.get('temperature', temperature)
            
        # Merge with additional options
        if additional_options:
            options.update(additional_options)
            
        return await self.ollama_chat(
            model=model,
            messages=messages,
            temperature=temperature,
            top_p=top_p,
            timeout=timeout,
            options=options
        )

    async def preload_models(self) -> Dict[str, bool]:
        """
        Pre-load models specified in config to improve first-request performance.
        
        Returns:
            Dict mapping model names to success status
        """
        if not hasattr(self.config, 'ollama_enable_model_preloading') or not self.config.ollama_enable_model_preloading:
            logging.info("Model preloading disabled in config")
            return {}
            
        models_to_preload = []
        if hasattr(self.config, 'text_model'):
            models_to_preload.append(self.config.text_model)
        if hasattr(self.config, 'vision_model'):
            models_to_preload.append(self.config.vision_model)
        if hasattr(self.config, 'embedding_model'):
            models_to_preload.append(self.config.embedding_model)
        if hasattr(self.config, 'chat_model') and self.config.chat_model:
            models_to_preload.append(self.config.chat_model)
            
        # Remove duplicates
        models_to_preload = list(set(models_to_preload))
        
        results = {}
        logging.info(f"Pre-loading {len(models_to_preload)} models for improved performance")
        
        for model in models_to_preload:
            try:
                logging.info(f"Pre-loading model: {model}")
                # Send a minimal request to load the model into memory
                await self.ollama_generate(
                    model=model,
                    prompt="test",
                    max_tokens=1,
                    timeout=30,
                    options={
                        "keep_alive": self.config.ollama_keep_alive if hasattr(self.config, 'ollama_keep_alive') else "5m"
                    }
                )
                results[model] = True
                logging.info(f"Successfully pre-loaded model: {model}")
            except Exception as e:
                logging.error(f"Failed to pre-load model {model}: {e}")
                results[model] = False
                
        successful = sum(1 for success in results.values() if success)
        logging.info(f"Model pre-loading complete: {successful}/{len(models_to_preload)} models loaded successfully")
        return results

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
        self._client = httpx.AsyncClient(base_url=self.base_url, timeout=config.request_timeout if config else 60.0)
        
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
