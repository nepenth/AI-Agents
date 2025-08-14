"""
AI Backend Factory for configuration-based backend selection.
"""

from typing import Dict, Any, Optional, Type
import logging

from .base import AIBackend
from .ollama import OllamaBackend
from .localai import LocalAIBackend
from .openai_compatible import OpenAICompatibleBackend

logger = logging.getLogger(__name__)


class BackendRegistry:
    """Registry for AI backend implementations."""
    
    _backends: Dict[str, Type[AIBackend]] = {
        "ollama": OllamaBackend,
        "localai": LocalAIBackend,
        "openai": OpenAICompatibleBackend,
        "openai_compatible": OpenAICompatibleBackend,
    }
    
    @classmethod
    def register(cls, name: str, backend_class: Type[AIBackend]) -> None:
        """Register a new backend implementation."""
        cls._backends[name] = backend_class
        logger.info(f"Registered AI backend: {name}")
    
    @classmethod
    def get_backend_class(cls, name: str) -> Optional[Type[AIBackend]]:
        """Get a backend class by name."""
        return cls._backends.get(name)
    
    @classmethod
    def list_backends(cls) -> list[str]:
        """List all registered backend names."""
        return list(cls._backends.keys())


class AIBackendFactory:
    """Factory for creating AI backend instances."""
    
    def __init__(self):
        self._instances: Dict[str, AIBackend] = {}
    
    async def create_backend(
        self,
        backend_type: str,
        config: Dict[str, Any],
        instance_name: Optional[str] = None
    ) -> AIBackend:
        """Create and initialize an AI backend instance."""
        
        # Use backend_type as instance name if not provided
        if instance_name is None:
            instance_name = backend_type
        
        # Check if instance already exists
        if instance_name in self._instances:
            logger.warning(f"Backend instance '{instance_name}' already exists, returning existing instance")
            return self._instances[instance_name]
        
        # Get backend class
        backend_class = BackendRegistry.get_backend_class(backend_type)
        if not backend_class:
            raise ValueError(f"Unknown backend type: {backend_type}. Available: {BackendRegistry.list_backends()}")
        
        # Create and initialize backend
        try:
            backend = backend_class(config)
            await backend.initialize()
            
            # Store instance
            self._instances[instance_name] = backend
            
            logger.info(f"Created and initialized AI backend: {instance_name} ({backend_type})")
            return backend
            
        except Exception as e:
            logger.error(f"Failed to create backend '{instance_name}' ({backend_type}): {e}")
            raise
    
    async def get_backend(self, instance_name: str) -> Optional[AIBackend]:
        """Get an existing backend instance."""
        return self._instances.get(instance_name)
    
    async def remove_backend(self, instance_name: str) -> bool:
        """Remove and cleanup a backend instance."""
        if instance_name not in self._instances:
            return False
        
        backend = self._instances[instance_name]
        try:
            await backend.cleanup()
        except Exception as e:
            logger.error(f"Error cleaning up backend '{instance_name}': {e}")
        
        del self._instances[instance_name]
        logger.info(f"Removed AI backend: {instance_name}")
        return True
    
    async def cleanup_all(self) -> None:
        """Cleanup all backend instances."""
        for instance_name in list(self._instances.keys()):
            await self.remove_backend(instance_name)
    
    def list_instances(self) -> Dict[str, str]:
        """List all backend instances and their types."""
        return {
            name: backend.__class__.__name__
            for name, backend in self._instances.items()
        }
    
    async def health_check_all(self) -> Dict[str, bool]:
        """Perform health check on all backend instances."""
        results = {}
        for name, backend in self._instances.items():
            try:
                results[name] = await backend.health_check()
            except Exception as e:
                logger.error(f"Health check failed for backend '{name}': {e}")
                results[name] = False
        return results


class AIBackendManager:
    """High-level manager for AI backends with configuration support."""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.factory = AIBackendFactory()
        self._default_backend: Optional[str] = None
    
    async def initialize_from_config(self) -> None:
        """Initialize backends from configuration."""
        backends_config = self.config.get("ai_backends", {})
        
        if not backends_config:
            logger.warning("No AI backends configured")
            return
        
        # Initialize each configured backend
        for backend_name, backend_config in backends_config.items():
            backend_type = backend_config.get("type")
            if not backend_type:
                logger.error(f"Backend '{backend_name}' missing 'type' configuration")
                continue
            
            try:
                await self.factory.create_backend(
                    backend_type=backend_type,
                    config=backend_config,
                    instance_name=backend_name
                )
                
                # Set first backend as default if not set
                if self._default_backend is None:
                    self._default_backend = backend_name
                    
            except Exception as e:
                logger.error(f"Failed to initialize backend '{backend_name}': {e}")
        
        # Set explicit default if configured
        default_backend = self.config.get("default_ai_backend")
        if default_backend and default_backend in self.factory._instances:
            self._default_backend = default_backend
        
        logger.info(f"Initialized AI backends. Default: {self._default_backend}")
    
    async def get_backend(self, backend_name: Optional[str] = None) -> Optional[AIBackend]:
        """Get a backend instance, using default if name not provided."""
        if backend_name is None:
            backend_name = self._default_backend
        
        if backend_name is None:
            logger.error("No backend name provided and no default backend set")
            return None
        
        return await self.factory.get_backend(backend_name)
    
    async def get_text_generation_backend(self, backend_name: Optional[str] = None) -> Optional[AIBackend]:
        """Get a backend suitable for text generation."""
        backend = await self.get_backend(backend_name)
        if backend:
            # Verify backend has text generation models
            models = await backend.list_models()
            text_models = [m for m in models if m.type.value == "text_generation"]
            if text_models:
                return backend
            else:
                logger.warning(f"Backend '{backend_name}' has no text generation models")
        return None
    
    async def get_embedding_backend(self, backend_name: Optional[str] = None) -> Optional[AIBackend]:
        """Get a backend suitable for embeddings."""
        backend = await self.get_backend(backend_name)
        if backend:
            # Verify backend has embedding models
            models = await backend.list_models()
            embedding_models = [m for m in models if m.type.value == "embedding"]
            if embedding_models:
                return backend
            else:
                logger.warning(f"Backend '{backend_name}' has no embedding models")
        return None
    
    async def cleanup(self) -> None:
        """Cleanup all backends."""
        await self.factory.cleanup_all()
    
    def get_status(self) -> Dict[str, Any]:
        """Get status of all backends."""
        return {
            "default_backend": self._default_backend,
            "instances": self.factory.list_instances(),
            "total_backends": len(self.factory._instances)
        }


# Global backend manager instance
_backend_manager: Optional[AIBackendManager] = None


def get_backend_manager() -> Optional[AIBackendManager]:
    """Get the global backend manager instance."""
    return _backend_manager


def initialize_backend_manager(config: Dict[str, Any]) -> AIBackendManager:
    """Initialize the global backend manager."""
    global _backend_manager
    _backend_manager = AIBackendManager(config)
    return _backend_manager


async def cleanup_backend_manager() -> None:
    """Cleanup the global backend manager."""
    global _backend_manager
    if _backend_manager:
        await _backend_manager.cleanup()
        _backend_manager = None