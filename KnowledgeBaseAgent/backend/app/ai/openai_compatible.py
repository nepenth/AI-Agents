"""
OpenAI-compatible backend implementation for external API services.
"""

import asyncio
import json
from typing import Dict, Any, AsyncGenerator, List, Optional
import aiohttp
import logging

from .base import (
    AIBackend, GenerationConfig, EmbeddingConfig, ModelInfo, ModelType,
    AIBackendError, ModelNotFoundError, GenerationError, EmbeddingError
)

logger = logging.getLogger(__name__)


class OpenAICompatibleBackend(AIBackend):
    """OpenAI-compatible backend for external API services."""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.base_url = config.get("base_url", "https://api.openai.com")
        self.api_key = config["api_key"]  # Required for external APIs
        self.organization = config.get("organization")
        self.timeout = config.get("timeout", 300)  # 5 minutes default
        self.session: Optional[aiohttp.ClientSession] = None
        
        # Rate limiting configuration
        self.max_requests_per_minute = config.get("max_requests_per_minute", 60)
        self.max_tokens_per_minute = config.get("max_tokens_per_minute", 150000)
        
        # Request tracking for rate limiting
        self._request_times: List[float] = []
        self._token_usage: List[tuple[float, int]] = []  # (timestamp, tokens)
    
    async def initialize(self) -> None:
        """Initialize the OpenAI-compatible backend."""
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        if self.organization:
            headers["OpenAI-Organization"] = self.organization
        
        self.session = aiohttp.ClientSession(
            headers=headers,
            timeout=aiohttp.ClientTimeout(total=self.timeout)
        )
        
        # Test connection
        if not await self.health_check():
            raise AIBackendError("Failed to connect to OpenAI-compatible API")
        
        logger.info(f"OpenAI-compatible backend initialized at {self.base_url}")
    
    async def cleanup(self) -> None:
        """Clean up resources."""
        if self.session:
            await self.session.close()
            self.session = None
    
    async def health_check(self) -> bool:
        """Check if the API is healthy."""
        try:
            if not self.session:
                return False
            
            async with self.session.get(f"{self.base_url}/v1/models") as response:
                return response.status == 200
        except Exception as e:
            logger.warning(f"OpenAI-compatible API health check failed: {e}")
            return False
    
    async def list_models(self) -> List[ModelInfo]:
        """List available models from the API."""
        if self._models_cache:
            return self._models_cache
        
        try:
            if not self.session:
                raise AIBackendError("Backend not initialized")
            
            await self._check_rate_limits()
            
            async with self.session.get(f"{self.base_url}/v1/models") as response:
                if response.status != 200:
                    raise AIBackendError(f"Failed to list models: {response.status}")
                
                data = await response.json()
                models = []
                
                for model_data in data.get("data", []):
                    name = model_data["id"]
                    
                    # Determine model type and properties
                    model_info = self._analyze_model(name, model_data)
                    models.append(model_info)
                
                self._models_cache = models
                return models
                
        except Exception as e:
            logger.error(f"Failed to list OpenAI-compatible models: {e}")
            raise AIBackendError(f"Failed to list models: {e}")
    
    async def generate_text(
        self,
        prompt: str,
        model: str,
        config: Optional[GenerationConfig] = None
    ) -> str:
        """Generate text using the OpenAI-compatible API."""
        await self.validate_model(model, ModelType.TEXT_GENERATION)
        
        if not self.session:
            raise AIBackendError("Backend not initialized")
        
        config = config or GenerationConfig()
        
        await self._check_rate_limits()
        
        payload = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": config.temperature,
            "top_p": config.top_p,
            "stream": False
        }
        
        if config.max_tokens:
            payload["max_tokens"] = config.max_tokens
        if config.stop_sequences:
            payload["stop"] = config.stop_sequences
        
        try:
            async with self.session.post(
                f"{self.base_url}/v1/chat/completions",
                json=payload
            ) as response:
                if response.status != 200:
                    error_text = await response.text()
                    raise GenerationError(f"Generation failed: {error_text}")
                
                data = await response.json()
                
                # Track token usage for rate limiting
                usage = data.get("usage", {})
                total_tokens = usage.get("total_tokens", 0)
                self._track_token_usage(total_tokens)
                
                choices = data.get("choices", [])
                if not choices:
                    raise GenerationError("No response generated")
                
                return choices[0]["message"]["content"]
                
        except Exception as e:
            logger.error(f"OpenAI-compatible text generation failed: {e}")
            raise GenerationError(f"Text generation failed: {e}")
    
    async def generate_stream(
        self,
        prompt: str,
        model: str,
        config: Optional[GenerationConfig] = None
    ) -> AsyncGenerator[str, None]:
        """Generate streaming text using the OpenAI-compatible API."""
        await self.validate_model(model, ModelType.TEXT_GENERATION)
        
        if not self.session:
            raise AIBackendError("Backend not initialized")
        
        config = config or GenerationConfig()
        
        await self._check_rate_limits()
        
        payload = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": config.temperature,
            "top_p": config.top_p,
            "stream": True
        }
        
        if config.max_tokens:
            payload["max_tokens"] = config.max_tokens
        if config.stop_sequences:
            payload["stop"] = config.stop_sequences
        
        try:
            async with self.session.post(
                f"{self.base_url}/v1/chat/completions",
                json=payload
            ) as response:
                if response.status != 200:
                    error_text = await response.text()
                    raise GenerationError(f"Streaming generation failed: {error_text}")
                
                async for line in response.content:
                    if line:
                        line_str = line.decode('utf-8').strip()
                        if line_str.startswith('data: '):
                            data_str = line_str[6:]  # Remove 'data: ' prefix
                            
                            if data_str == '[DONE]':
                                break
                            
                            try:
                                data = json.loads(data_str)
                                choices = data.get("choices", [])
                                if choices and "delta" in choices[0]:
                                    delta = choices[0]["delta"]
                                    if "content" in delta:
                                        yield delta["content"]
                            except json.JSONDecodeError:
                                continue
                            
        except Exception as e:
            logger.error(f"OpenAI-compatible streaming generation failed: {e}")
            raise GenerationError(f"Streaming generation failed: {e}")
    
    async def generate_embeddings(
        self,
        texts: List[str],
        model: str,
        config: Optional[EmbeddingConfig] = None
    ) -> List[List[float]]:
        """Generate embeddings using the OpenAI-compatible API."""
        await self.validate_model(model, ModelType.EMBEDDING)
        
        if not self.session:
            raise AIBackendError("Backend not initialized")
        
        config = config or EmbeddingConfig()
        
        # Process in batches to respect API limits
        all_embeddings = []
        
        for i in range(0, len(texts), config.batch_size):
            batch = texts[i:i + config.batch_size]
            
            await self._check_rate_limits()
            
            payload = {
                "model": model,
                "input": batch
            }
            
            try:
                async with self.session.post(
                    f"{self.base_url}/v1/embeddings",
                    json=payload
                ) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        raise EmbeddingError(f"Embedding generation failed: {error_text}")
                    
                    data = await response.json()
                    
                    # Track token usage
                    usage = data.get("usage", {})
                    total_tokens = usage.get("total_tokens", 0)
                    self._track_token_usage(total_tokens)
                    
                    embeddings_data = data.get("data", [])
                    
                    # Sort by index to maintain order
                    embeddings_data.sort(key=lambda x: x.get("index", 0))
                    
                    batch_embeddings = []
                    for item in embeddings_data:
                        embedding = item.get("embedding", [])
                        
                        if config.normalize and embedding:
                            # Normalize the embedding vector
                            norm = sum(x * x for x in embedding) ** 0.5
                            if norm > 0:
                                embedding = [x / norm for x in embedding]
                        
                        batch_embeddings.append(embedding)
                    
                    all_embeddings.extend(batch_embeddings)
                    
            except Exception as e:
                logger.error(f"OpenAI-compatible embedding generation failed: {e}")
                raise EmbeddingError(f"Embedding generation failed: {e}")
        
        return all_embeddings
    
    def _analyze_model(self, name: str, model_data: Dict[str, Any]) -> ModelInfo:
        """Analyze model data to determine type and capabilities."""
        name_lower = name.lower()
        
        # Determine model type
        if any(pattern in name_lower for pattern in [
            "embed", "embedding", "text-embedding"
        ]):
            model_type = ModelType.EMBEDDING
            embedding_dims = self._get_embedding_dimensions(name)
        else:
            model_type = ModelType.TEXT_GENERATION
            embedding_dims = None
        
        # Determine capabilities
        supports_vision = any(pattern in name_lower for pattern in [
            "vision", "gpt-4-vision", "gpt-4o"
        ])
        
        supports_streaming = model_type == ModelType.TEXT_GENERATION
        
        # Get context length
        context_length = self._get_context_length(name)
        
        return ModelInfo(
            name=name,
            type=model_type,
            context_length=context_length,
            embedding_dimensions=embedding_dims,
            supports_streaming=supports_streaming,
            supports_vision=supports_vision
        )
    
    def _get_context_length(self, model_name: str) -> int:
        """Get context length based on model name."""
        name_lower = model_name.lower()
        
        # OpenAI model context lengths
        if "gpt-4-turbo" in name_lower or "gpt-4o" in name_lower:
            return 128000
        elif "gpt-4" in name_lower:
            return 8192
        elif "gpt-3.5-turbo" in name_lower:
            if "16k" in name_lower:
                return 16384
            else:
                return 4096
        elif "text-davinci" in name_lower:
            return 4096
        elif "claude-3" in name_lower:
            return 200000
        elif "claude-2" in name_lower:
            return 100000
        
        # Default context length
        return 4096
    
    def _get_embedding_dimensions(self, model_name: str) -> int:
        """Get embedding dimensions based on model name."""
        name_lower = model_name.lower()
        
        if "text-embedding-3-large" in name_lower:
            return 3072
        elif "text-embedding-3-small" in name_lower or "text-embedding-ada-002" in name_lower:
            return 1536
        elif "text-embedding-ada-001" in name_lower:
            return 1024
        
        # Default embedding dimension
        return 1536
    
    async def _check_rate_limits(self) -> None:
        """Check and enforce rate limits."""
        import time
        
        current_time = time.time()
        
        # Clean old entries (older than 1 minute)
        self._request_times = [t for t in self._request_times if current_time - t < 60]
        self._token_usage = [(t, tokens) for t, tokens in self._token_usage if current_time - t < 60]
        
        # Check request rate limit
        if len(self._request_times) >= self.max_requests_per_minute:
            sleep_time = 60 - (current_time - self._request_times[0])
            if sleep_time > 0:
                logger.info(f"Rate limit reached, sleeping for {sleep_time:.2f} seconds")
                await asyncio.sleep(sleep_time)
        
        # Check token rate limit
        total_tokens = sum(tokens for _, tokens in self._token_usage)
        if total_tokens >= self.max_tokens_per_minute:
            sleep_time = 60 - (current_time - self._token_usage[0][0])
            if sleep_time > 0:
                logger.info(f"Token rate limit reached, sleeping for {sleep_time:.2f} seconds")
                await asyncio.sleep(sleep_time)
        
        # Record this request
        self._request_times.append(current_time)
    
    def _track_token_usage(self, tokens: int) -> None:
        """Track token usage for rate limiting."""
        import time
        self._token_usage.append((time.time(), tokens))