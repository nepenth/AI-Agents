"""
AI Service for managing AI backends and providing high-level AI operations.
"""

import logging
from typing import List, Optional, Dict, Any, AsyncGenerator
from contextlib import asynccontextmanager

from app.ai import (
    initialize_backend_manager, get_backend_manager, cleanup_backend_manager,
    AIBackend, ModelType, GenerationConfig, EmbeddingConfig,
    AIBackendError, ModelNotFoundError, GenerationError, EmbeddingError
)
from app.config import get_settings

logger = logging.getLogger(__name__)


class AIService:
    """High-level AI service for the application."""
    
    def __init__(self):
        self.settings = get_settings()
        self._initialized = False
    
    async def initialize(self) -> None:
        """Initialize the AI service and backends."""
        if self._initialized:
            logger.warning("AI service already initialized")
            return
        
        try:
            # Get AI backends configuration
            ai_config = self.settings.get_ai_backends_config()
            
            # Initialize backend manager
            manager = initialize_backend_manager(ai_config)
            await manager.initialize_from_config()
            
            self._initialized = True
            logger.info("AI service initialized successfully")
            
            # Log available backends
            status = manager.get_status()
            logger.info(f"Available AI backends: {list(status['instances'].keys())}")
            logger.info(f"Default backend: {status['default_backend']}")
            
        except Exception as e:
            logger.error(f"Failed to initialize AI service: {e}")
            raise AIBackendError(f"AI service initialization failed: {e}")
    
    async def cleanup(self) -> None:
        """Cleanup the AI service."""
        if not self._initialized:
            return
        
        try:
            await cleanup_backend_manager()
            self._initialized = False
            logger.info("AI service cleaned up successfully")
        except Exception as e:
            logger.error(f"Error during AI service cleanup: {e}")
    
    async def get_backend(self, backend_name: Optional[str] = None) -> Optional[AIBackend]:
        """Get an AI backend instance."""
        if not self._initialized:
            raise AIBackendError("AI service not initialized")
        
        manager = get_backend_manager()
        if not manager:
            raise AIBackendError("Backend manager not available")
        
        return await manager.get_backend(backend_name)
    
    async def generate_text(
        self,
        prompt: str,
        model: str,
        backend_name: Optional[str] = None,
        config: Optional[GenerationConfig] = None
    ) -> str:
        """Generate text using the specified model and backend."""
        manager = get_backend_manager()
        if not manager:
            raise AIBackendError("Backend manager not available")
        
        backend = await manager.get_text_generation_backend(backend_name)
        if not backend:
            raise AIBackendError(f"No text generation backend available: {backend_name}")
        
        try:
            return await backend.generate_text(prompt, model, config)
        except Exception as e:
            logger.error(f"Text generation failed: {e}")
            raise GenerationError(f"Text generation failed: {e}")
    
    async def generate_stream(
        self,
        prompt: str,
        model: str,
        backend_name: Optional[str] = None,
        config: Optional[GenerationConfig] = None
    ) -> AsyncGenerator[str, None]:
        """Generate streaming text using the specified model and backend."""
        manager = get_backend_manager()
        if not manager:
            raise AIBackendError("Backend manager not available")
        
        backend = await manager.get_text_generation_backend(backend_name)
        if not backend:
            raise AIBackendError(f"No text generation backend available: {backend_name}")
        
        try:
            async for chunk in backend.generate_stream(prompt, model, config):
                yield chunk
        except Exception as e:
            logger.error(f"Streaming generation failed: {e}")
            raise GenerationError(f"Streaming generation failed: {e}")
    
    async def generate_embeddings(
        self,
        texts: List[str],
        model: str,
        backend_name: Optional[str] = None,
        config: Optional[EmbeddingConfig] = None
    ) -> List[List[float]]:
        """Generate embeddings using the specified model and backend."""
        manager = get_backend_manager()
        if not manager:
            raise AIBackendError("Backend manager not available")
        
        backend = await manager.get_embedding_backend(backend_name)
        if not backend:
            raise AIBackendError(f"No embedding backend available: {backend_name}")
        
        try:
            return await backend.generate_embeddings(texts, model, config)
        except Exception as e:
            logger.error(f"Embedding generation failed: {e}")
            raise EmbeddingError(f"Embedding generation failed: {e}")
    
    async def list_models(
        self,
        backend_name: Optional[str] = None,
        model_type: Optional[ModelType] = None
    ) -> List[Dict[str, Any]]:
        """List available models from the specified backend."""
        backend = await self.get_backend(backend_name)
        if not backend:
            raise AIBackendError(f"Backend not available: {backend_name}")
        
        try:
            models = await backend.list_models()
            
            # Filter by model type if specified
            if model_type:
                models = [m for m in models if m.type == model_type]
            
            # Convert to dictionaries for JSON serialization
            return [
                {
                    "name": model.name,
                    "type": model.type.value,
                    "context_length": model.context_length,
                    "embedding_dimensions": model.embedding_dimensions,
                    "supports_streaming": model.supports_streaming,
                    "supports_vision": model.supports_vision
                }
                for model in models
            ]
        except Exception as e:
            logger.error(f"Failed to list models: {e}")
            raise AIBackendError(f"Failed to list models: {e}")
    
    async def get_backend_status(self) -> Dict[str, Any]:
        """Get status of all AI backends."""
        if not self._initialized:
            return {"initialized": False, "backends": {}}
        
        manager = get_backend_manager()
        if not manager:
            return {"initialized": False, "backends": {}}
        
        try:
            status = manager.get_status()
            health_results = await manager.factory.health_check_all()
            
            return {
                "initialized": True,
                "default_backend": status["default_backend"],
                "total_backends": status["total_backends"],
                "backends": {
                    name: {
                        "type": backend_type,
                        "healthy": health_results.get(name, False)
                    }
                    for name, backend_type in status["instances"].items()
                }
            }
        except Exception as e:
            logger.error(f"Failed to get backend status: {e}")
            return {"initialized": True, "error": str(e)}
    
    async def health_check(self) -> bool:
        """Perform health check on the AI service."""
        if not self._initialized:
            return False
        
        try:
            manager = get_backend_manager()
            if not manager:
                return False
            
            # Check if at least one backend is healthy
            health_results = await manager.factory.health_check_all()
            return any(health_results.values())
        except Exception as e:
            logger.error(f"AI service health check failed: {e}")
            return False


# Global AI service instance
_ai_service: Optional[AIService] = None


def get_ai_service() -> AIService:
    """Get the global AI service instance."""
    global _ai_service
    if _ai_service is None:
        _ai_service = AIService()
    return _ai_service


@asynccontextmanager
async def ai_service_lifespan():
    """Context manager for AI service lifecycle."""
    service = get_ai_service()
    try:
        await service.initialize()
        yield service
    finally:
        await service.cleanup()


async def initialize_ai_service() -> AIService:
    """Initialize the global AI service."""
    service = get_ai_service()
    await service.initialize()
    return service


async def cleanup_ai_service() -> None:
    """Cleanup the global AI service."""
    global _ai_service
    if _ai_service:
        await _ai_service.cleanup()
        _ai_service = None