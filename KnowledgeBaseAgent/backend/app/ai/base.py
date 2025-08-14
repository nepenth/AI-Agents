"""
Abstract base class for AI backends providing a unified interface.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, AsyncGenerator, List, Optional
from dataclasses import dataclass
from enum import Enum


class ModelType(str, Enum):
    """Types of AI models supported."""
    TEXT_GENERATION = "text_generation"
    EMBEDDING = "embedding"
    VISION = "vision"


@dataclass
class GenerationConfig:
    """Configuration for text generation."""
    temperature: float = 0.7
    max_tokens: Optional[int] = None
    top_p: float = 1.0
    top_k: Optional[int] = None
    stop_sequences: Optional[List[str]] = None
    stream: bool = False


@dataclass
class EmbeddingConfig:
    """Configuration for embedding generation."""
    normalize: bool = True
    batch_size: int = 32


@dataclass
class ModelInfo:
    """Information about an available model."""
    name: str
    type: ModelType
    context_length: int
    embedding_dimensions: Optional[int] = None
    supports_streaming: bool = False
    supports_vision: bool = False


class AIBackendError(Exception):
    """Base exception for AI backend errors."""
    pass


class ModelNotFoundError(AIBackendError):
    """Raised when a requested model is not available."""
    pass


class GenerationError(AIBackendError):
    """Raised when text generation fails."""
    pass


class EmbeddingError(AIBackendError):
    """Raised when embedding generation fails."""
    pass


class AIBackend(ABC):
    """Abstract base class for AI backends."""
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize the backend with configuration."""
        self.config = config
        self._models_cache: Optional[List[ModelInfo]] = None
    
    @abstractmethod
    async def initialize(self) -> None:
        """Initialize the backend connection and resources."""
        pass
    
    @abstractmethod
    async def cleanup(self) -> None:
        """Clean up backend resources."""
        pass
    
    @abstractmethod
    async def health_check(self) -> bool:
        """Check if the backend is healthy and responsive."""
        pass
    
    @abstractmethod
    async def list_models(self) -> List[ModelInfo]:
        """List available models."""
        pass
    
    @abstractmethod
    async def generate_text(
        self,
        prompt: str,
        model: str,
        config: Optional[GenerationConfig] = None
    ) -> str:
        """Generate text from a prompt."""
        pass
    
    @abstractmethod
    async def generate_stream(
        self,
        prompt: str,
        model: str,
        config: Optional[GenerationConfig] = None
    ) -> AsyncGenerator[str, None]:
        """Generate streaming text from a prompt."""
        pass
    
    @abstractmethod
    async def generate_embeddings(
        self,
        texts: List[str],
        model: str,
        config: Optional[EmbeddingConfig] = None
    ) -> List[List[float]]:
        """Generate embeddings for a list of texts."""
        pass
    
    async def get_model_info(self, model_name: str) -> Optional[ModelInfo]:
        """Get information about a specific model."""
        models = await self.list_models()
        return next((m for m in models if m.name == model_name), None)
    
    async def validate_model(self, model_name: str, model_type: ModelType) -> None:
        """Validate that a model exists and supports the required type."""
        model_info = await self.get_model_info(model_name)
        if not model_info:
            raise ModelNotFoundError(f"Model '{model_name}' not found")
        
        if model_info.type != model_type:
            raise ModelNotFoundError(
                f"Model '{model_name}' is type {model_info.type}, "
                f"but {model_type} was required"
            )