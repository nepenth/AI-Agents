"""
LocalAI backend implementation for local AI inference.
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


class LocalAIBackend(AIBackend):
    """LocalAI backend for local AI inference with OpenAI-compatible API."""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.base_url = config.get("base_url", "http://localhost:8080")
        self.api_key = config.get("api_key", "")  # LocalAI may not require API key
        self.timeout = config.get("timeout", 300)  # 5 minutes default
        self.session: Optional[aiohttp.ClientSession] = None
    
    async def initialize(self) -> None:
        """Initialize the LocalAI backend."""
        headers = {}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        
        self.session = aiohttp.ClientSession(
            headers=headers,
            timeout=aiohttp.ClientTimeout(total=self.timeout)
        )
        
        # Test connection
        if not await self.health_check():
            raise AIBackendError("Failed to connect to LocalAI server")
        
        logger.info(f"LocalAI backend initialized at {self.base_url}")
    
    async def cleanup(self) -> None:
        """Clean up resources."""
        if self.session:
            await self.session.close()
            self.session = None
    
    async def health_check(self) -> bool:
        """Check if LocalAI is healthy."""
        try:
            if not self.session:
                return False
            
            async with self.session.get(f"{self.base_url}/v1/models") as response:
                return response.status == 200
        except Exception as e:
            logger.warning(f"LocalAI health check failed: {e}")
            return False
    
    async def list_models(self) -> List[ModelInfo]:
        """List available LocalAI models."""
        if self._models_cache:
            return self._models_cache
        
        try:
            if not self.session:
                raise AIBackendError("Backend not initialized")
            
            async with self.session.get(f"{self.base_url}/v1/models") as response:
                if response.status != 200:
                    raise AIBackendError(f"Failed to list models: {response.status}")
                
                data = await response.json()
                models = []
                
                for model_data in data.get("data", []):
                    name = model_data["id"]
                    
                    # Determine model type based on name patterns
                    model_type = self._determine_model_type(name)
                    
                    models.append(ModelInfo(
                        name=name,
                        type=model_type,
                        context_length=self._get_context_length(name),
                        embedding_dimensions=self._get_embedding_dimensions(name) if model_type == ModelType.EMBEDDING else None,
                        supports_streaming=model_type == ModelType.TEXT_GENERATION,
                        supports_vision="vision" in name.lower() or "gpt-4-vision" in name.lower()
                    ))
                
                self._models_cache = models
                return models
                
        except Exception as e:
            logger.error(f"Failed to list LocalAI models: {e}")
            raise AIBackendError(f"Failed to list models: {e}")
    
    async def generate_text(
        self,
        prompt: str,
        model: str,
        config: Optional[GenerationConfig] = None
    ) -> str:
        """Generate text using LocalAI."""
        await self.validate_model(model, ModelType.TEXT_GENERATION)
        
        if not self.session:
            raise AIBackendError("Backend not initialized")
        
        config = config or GenerationConfig()
        
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
                choices = data.get("choices", [])
                if not choices:
                    raise GenerationError("No response generated")
                
                return choices[0]["message"]["content"]
                
        except Exception as e:
            logger.error(f"LocalAI text generation failed: {e}")
            raise GenerationError(f"Text generation failed: {e}")
    
    async def generate_stream(
        self,
        prompt: str,
        model: str,
        config: Optional[GenerationConfig] = None
    ) -> AsyncGenerator[str, None]:
        """Generate streaming text using LocalAI."""
        await self.validate_model(model, ModelType.TEXT_GENERATION)
        
        if not self.session:
            raise AIBackendError("Backend not initialized")
        
        config = config or GenerationConfig()
        
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
            logger.error(f"LocalAI streaming generation failed: {e}")
            raise GenerationError(f"Streaming generation failed: {e}")
    
    async def generate_embeddings(
        self,
        texts: List[str],
        model: str,
        config: Optional[EmbeddingConfig] = None
    ) -> List[List[float]]:
        """Generate embeddings using LocalAI."""
        await self.validate_model(model, ModelType.EMBEDDING)
        
        if not self.session:
            raise AIBackendError("Backend not initialized")
        
        config = config or EmbeddingConfig()
        
        payload = {
            "model": model,
            "input": texts
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
                embeddings_data = data.get("data", [])
                
                # Sort by index to maintain order
                embeddings_data.sort(key=lambda x: x.get("index", 0))
                
                embeddings = []
                for item in embeddings_data:
                    embedding = item.get("embedding", [])
                    
                    if config.normalize and embedding:
                        # Normalize the embedding vector
                        norm = sum(x * x for x in embedding) ** 0.5
                        if norm > 0:
                            embedding = [x / norm for x in embedding]
                    
                    embeddings.append(embedding)
                
                return embeddings
                
        except Exception as e:
            logger.error(f"LocalAI embedding generation failed: {e}")
            raise EmbeddingError(f"Embedding generation failed: {e}")
    
    def _determine_model_type(self, model_name: str) -> ModelType:
        """Determine model type based on name patterns."""
        name_lower = model_name.lower()
        
        # Common embedding model patterns
        if any(pattern in name_lower for pattern in [
            "embed", "embedding", "text-embedding", "sentence", "all-minilm", "bge", "e5"
        ]):
            return ModelType.EMBEDDING
        
        # Vision model patterns
        if any(pattern in name_lower for pattern in [
            "vision", "gpt-4-vision", "llava", "clip"
        ]):
            return ModelType.VISION
        
        # Default to text generation
        return ModelType.TEXT_GENERATION
    
    def _get_context_length(self, model_name: str) -> int:
        """Get context length based on model name patterns."""
        name_lower = model_name.lower()
        
        # Common context lengths for known models
        if "gpt-4" in name_lower:
            return 8192
        elif "gpt-3.5" in name_lower:
            return 4096
        elif "llama" in name_lower:
            if "70b" in name_lower or "65b" in name_lower:
                return 4096
            else:
                return 2048
        elif "mistral" in name_lower:
            return 8192
        elif "codellama" in name_lower:
            return 16384
        
        # Default context length
        return 2048
    
    def _get_embedding_dimensions(self, model_name: str) -> int:
        """Get embedding dimensions based on model name patterns."""
        name_lower = model_name.lower()
        
        # Common embedding dimensions
        if "text-embedding-ada-002" in name_lower:
            return 1536
        elif "text-embedding-3-small" in name_lower:
            return 1536
        elif "text-embedding-3-large" in name_lower:
            return 3072
        elif "all-minilm" in name_lower:
            return 384
        elif "bge-large" in name_lower:
            return 1024
        elif "bge-base" in name_lower:
            return 768
        elif "e5-large" in name_lower:
            return 1024
        elif "e5-base" in name_lower:
            return 768
        
        # Default embedding dimension
        return 768