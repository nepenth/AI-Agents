"""
AI Backend Abstraction Layer

This module provides a unified interface for different AI backends including
Ollama, LocalAI, and OpenAI-compatible APIs.
"""

from .base import (
    AIBackend,
    ModelType,
    ModelInfo,
    GenerationConfig,
    EmbeddingConfig,
    AIBackendError,
    ModelNotFoundError,
    GenerationError,
    EmbeddingError,
)

from .factory import (
    AIBackendFactory,
    AIBackendManager,
    BackendRegistry,
    get_backend_manager,
    initialize_backend_manager,
    cleanup_backend_manager,
)

from .ollama import OllamaBackend
from .localai import LocalAIBackend
from .openai_compatible import OpenAICompatibleBackend

__all__ = [
    # Base classes and types
    "AIBackend",
    "ModelType",
    "ModelInfo",
    "GenerationConfig",
    "EmbeddingConfig",
    
    # Exceptions
    "AIBackendError",
    "ModelNotFoundError",
    "GenerationError",
    "EmbeddingError",
    
    # Factory and management
    "AIBackendFactory",
    "AIBackendManager",
    "BackendRegistry",
    "get_backend_manager",
    "initialize_backend_manager",
    "cleanup_backend_manager",
    
    # Backend implementations
    "OllamaBackend",
    "LocalAIBackend",
    "OpenAICompatibleBackend",
]