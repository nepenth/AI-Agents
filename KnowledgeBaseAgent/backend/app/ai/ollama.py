"""
Ollama backend implementation for local AI inference.
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


class OllamaBackend(AIBackend):
    """Ollama backend for local AI inference."""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.base_url = config.get("base_url", "http://localhost:11434")
        self.timeout = config.get("timeout", 300)  # 5 minutes default
        self.session: Optional[aiohttp.ClientSession] = None
    
    async def initialize(self) -> None:
        """Initialize the Ollama backend."""
        self.session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=self.timeout)
        )
        
        # Test connection
        if not await self.health_check():
            raise AIBackendError("Failed to connect to Ollama server")
        
        logger.info(f"Ollama backend initialized at {self.base_url}")
    
    async def cleanup(self) -> None:
        """Clean up resources."""
        if self.session:
            await self.session.close()
            self.session = None
    
    async def health_check(self) -> bool:
        """Check if Ollama is healthy."""
        try:
            if not self.session:
                return False
            
            async with self.session.get(f"{self.base_url}/api/tags") as response:
                return response.status == 200
        except Exception as e:
            logger.warning(f"Ollama health check failed: {e}")
            return False
    
    async def list_models(self) -> List[ModelInfo]:
        """List available Ollama models."""
        if self._models_cache:
            return self._models_cache
        
        try:
            if not self.session:
                raise AIBackendError("Backend not initialized")
            
            async with self.session.get(f"{self.base_url}/api/tags") as response:
                if response.status != 200:
                    raise AIBackendError(f"Failed to list models: {response.status}")
                
                data = await response.json()
                models = []
                
                for model_data in data.get("models", []):
                    name = model_data["name"]
                    
                    # Determine model type based on name patterns
                    model_type = self._determine_model_type(name)
                    
                    # Get model details
                    details = await self._get_model_details(name)
                    
                    models.append(ModelInfo(
                        name=name,
                        type=model_type,
                        context_length=details.get("context_length", 2048),
                        embedding_dimensions=details.get("embedding_dimensions"),
                        supports_streaming=model_type == ModelType.TEXT_GENERATION,
                        supports_vision="vision" in name.lower() or "llava" in name.lower()
                    ))
                
                self._models_cache = models
                return models
                
        except Exception as e:
            logger.error(f"Failed to list Ollama models: {e}")
            raise AIBackendError(f"Failed to list models: {e}")
    
    async def generate_text(
        self,
        prompt: str,
        model: str,
        config: Optional[GenerationConfig] = None
    ) -> str:
        """Generate text using Ollama."""
        await self.validate_model(model, ModelType.TEXT_GENERATION)
        
        if not self.session:
            raise AIBackendError("Backend not initialized")
        
        config = config or GenerationConfig()
        
        payload = {
            "model": model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": config.temperature,
                "top_p": config.top_p,
            }
        }
        
        if config.max_tokens:
            payload["options"]["num_predict"] = config.max_tokens
        if config.top_k:
            payload["options"]["top_k"] = config.top_k
        if config.stop_sequences:
            payload["options"]["stop"] = config.stop_sequences
        
        try:
            async with self.session.post(
                f"{self.base_url}/api/generate",
                json=payload
            ) as response:
                if response.status != 200:
                    error_text = await response.text()
                    raise GenerationError(f"Generation failed: {error_text}")
                
                data = await response.json()
                return data.get("response", "")
                
        except Exception as e:
            logger.error(f"Ollama text generation failed: {e}")
            raise GenerationError(f"Text generation failed: {e}")
    
    async def generate_stream(
        self,
        prompt: str,
        model: str,
        config: Optional[GenerationConfig] = None
    ) -> AsyncGenerator[str, None]:
        """Generate streaming text using Ollama."""
        await self.validate_model(model, ModelType.TEXT_GENERATION)
        
        if not self.session:
            raise AIBackendError("Backend not initialized")
        
        config = config or GenerationConfig()
        
        payload = {
            "model": model,
            "prompt": prompt,
            "stream": True,
            "options": {
                "temperature": config.temperature,
                "top_p": config.top_p,
            }
        }
        
        if config.max_tokens:
            payload["options"]["num_predict"] = config.max_tokens
        if config.top_k:
            payload["options"]["top_k"] = config.top_k
        if config.stop_sequences:
            payload["options"]["stop"] = config.stop_sequences
        
        try:
            async with self.session.post(
                f"{self.base_url}/api/generate",
                json=payload
            ) as response:
                if response.status != 200:
                    error_text = await response.text()
                    raise GenerationError(f"Streaming generation failed: {error_text}")
                
                async for line in response.content:
                    if line:
                        try:
                            data = json.loads(line.decode('utf-8'))
                            if "response" in data:
                                yield data["response"]
                            if data.get("done", False):
                                break
                        except json.JSONDecodeError:
                            continue
                            
        except Exception as e:
            logger.error(f"Ollama streaming generation failed: {e}")
            raise GenerationError(f"Streaming generation failed: {e}")
    
    async def generate_embeddings(
        self,
        texts: List[str],
        model: str,
        config: Optional[EmbeddingConfig] = None
    ) -> List[List[float]]:
        """Generate embeddings using Ollama."""
        await self.validate_model(model, ModelType.EMBEDDING)
        
        if not self.session:
            raise AIBackendError("Backend not initialized")
        
        config = config or EmbeddingConfig()
        embeddings = []
        
        # Process in batches
        for i in range(0, len(texts), config.batch_size):
            batch = texts[i:i + config.batch_size]
            batch_embeddings = await self._generate_embeddings_batch(batch, model, config)
            embeddings.extend(batch_embeddings)
        
        return embeddings
    
    async def _generate_embeddings_batch(
        self,
        texts: List[str],
        model: str,
        config: EmbeddingConfig
    ) -> List[List[float]]:
        """Generate embeddings for a batch of texts."""
        embeddings = []
        
        for text in texts:
            payload = {
                "model": model,
                "prompt": text
            }
            
            try:
                async with self.session.post(
                    f"{self.base_url}/api/embeddings",
                    json=payload
                ) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        raise EmbeddingError(f"Embedding generation failed: {error_text}")
                    
                    data = await response.json()
                    embedding = data.get("embedding", [])
                    
                    if config.normalize and embedding:
                        # Normalize the embedding vector
                        norm = sum(x * x for x in embedding) ** 0.5
                        if norm > 0:
                            embedding = [x / norm for x in embedding]
                    
                    embeddings.append(embedding)
                    
            except Exception as e:
                logger.error(f"Ollama embedding generation failed for text: {text[:50]}...")
                raise EmbeddingError(f"Embedding generation failed: {e}")
        
        return embeddings
    
    def _determine_model_type(self, model_name: str) -> ModelType:
        """Determine model type based on name patterns."""
        name_lower = model_name.lower()
        
        # Common embedding model patterns
        if any(pattern in name_lower for pattern in [
            "embed", "sentence", "all-minilm", "bge", "e5"
        ]):
            return ModelType.EMBEDDING
        
        # Vision model patterns
        if any(pattern in name_lower for pattern in [
            "vision", "llava", "clip"
        ]):
            return ModelType.VISION
        
        # Default to text generation
        return ModelType.TEXT_GENERATION
    
    async def _get_model_details(self, model_name: str) -> Dict[str, Any]:
        """Get detailed information about a model."""
        try:
            if not self.session:
                return {}
            
            async with self.session.post(
                f"{self.base_url}/api/show",
                json={"name": model_name}
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    
                    # Extract useful information from model details
                    details = {}
                    
                    # Try to get context length from parameters
                    if "parameters" in data:
                        params = data["parameters"]
                        if "num_ctx" in params:
                            details["context_length"] = int(params["num_ctx"])
                    
                    # For embedding models, try to determine dimensions
                    model_type = self._determine_model_type(model_name)
                    if model_type == ModelType.EMBEDDING:
                        # Common embedding dimensions based on model names
                        if "all-minilm" in model_name.lower():
                            details["embedding_dimensions"] = 384
                        elif "bge" in model_name.lower():
                            details["embedding_dimensions"] = 1024
                        else:
                            details["embedding_dimensions"] = 768  # Default
                    
                    return details
                    
        except Exception as e:
            logger.warning(f"Failed to get model details for {model_name}: {e}")
        
        return {}