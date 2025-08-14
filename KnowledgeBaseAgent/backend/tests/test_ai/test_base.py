"""
Tests for AI backend base classes and interfaces.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock
from typing import List, Optional, AsyncGenerator

from app.ai.base import (
    AIBackend, ModelType, ModelInfo, GenerationConfig, EmbeddingConfig,
    AIBackendError, ModelNotFoundError, GenerationError, EmbeddingError
)


class MockAIBackend(AIBackend):
    """Mock AI backend for testing."""
    
    def __init__(self, config=None):
        super().__init__(config or {})
        self.initialized = False
        self.models = [
            ModelInfo(
                name="test-text-model",
                type=ModelType.TEXT_GENERATION,
                context_length=2048,
                supports_streaming=True
            ),
            ModelInfo(
                name="test-embedding-model",
                type=ModelType.EMBEDDING,
                context_length=512,
                embedding_dimensions=768
            )
        ]
    
    async def initialize(self) -> None:
        self.initialized = True
    
    async def cleanup(self) -> None:
        self.initialized = False
    
    async def health_check(self) -> bool:
        return self.initialized
    
    async def list_models(self) -> List[ModelInfo]:
        return self.models
    
    async def generate_text(
        self,
        prompt: str,
        model: str,
        config: Optional[GenerationConfig] = None
    ) -> str:
        if not self.initialized:
            raise AIBackendError("Backend not initialized")
        return f"Generated text for: {prompt[:20]}..."
    
    async def generate_stream(
        self,
        prompt: str,
        model: str,
        config: Optional[GenerationConfig] = None
    ) -> AsyncGenerator[str, None]:
        if not self.initialized:
            raise AIBackendError("Backend not initialized")
        
        words = f"Generated streaming text for: {prompt[:20]}...".split()
        for word in words:
            yield word + " "
    
    async def generate_embeddings(
        self,
        texts: List[str],
        model: str,
        config: Optional[EmbeddingConfig] = None
    ) -> List[List[float]]:
        if not self.initialized:
            raise AIBackendError("Backend not initialized")
        
        # Return mock embeddings
        return [[0.1, 0.2, 0.3] for _ in texts]


class TestModelInfo:
    """Test ModelInfo dataclass."""
    
    def test_model_info_creation(self):
        """Test creating ModelInfo instances."""
        model = ModelInfo(
            name="test-model",
            type=ModelType.TEXT_GENERATION,
            context_length=2048
        )
        
        assert model.name == "test-model"
        assert model.type == ModelType.TEXT_GENERATION
        assert model.context_length == 2048
        assert model.embedding_dimensions is None
        assert model.supports_streaming is False
        assert model.supports_vision is False
    
    def test_embedding_model_info(self):
        """Test ModelInfo for embedding models."""
        model = ModelInfo(
            name="embedding-model",
            type=ModelType.EMBEDDING,
            context_length=512,
            embedding_dimensions=768
        )
        
        assert model.type == ModelType.EMBEDDING
        assert model.embedding_dimensions == 768


class TestGenerationConfig:
    """Test GenerationConfig dataclass."""
    
    def test_default_config(self):
        """Test default configuration values."""
        config = GenerationConfig()
        
        assert config.temperature == 0.7
        assert config.max_tokens is None
        assert config.top_p == 1.0
        assert config.top_k is None
        assert config.stop_sequences is None
        assert config.stream is False
    
    def test_custom_config(self):
        """Test custom configuration values."""
        config = GenerationConfig(
            temperature=0.5,
            max_tokens=100,
            top_p=0.9,
            top_k=50,
            stop_sequences=["END"],
            stream=True
        )
        
        assert config.temperature == 0.5
        assert config.max_tokens == 100
        assert config.top_p == 0.9
        assert config.top_k == 50
        assert config.stop_sequences == ["END"]
        assert config.stream is True


class TestEmbeddingConfig:
    """Test EmbeddingConfig dataclass."""
    
    def test_default_config(self):
        """Test default configuration values."""
        config = EmbeddingConfig()
        
        assert config.normalize is True
        assert config.batch_size == 32
    
    def test_custom_config(self):
        """Test custom configuration values."""
        config = EmbeddingConfig(normalize=False, batch_size=16)
        
        assert config.normalize is False
        assert config.batch_size == 16


class TestAIBackendExceptions:
    """Test AI backend exceptions."""
    
    def test_ai_backend_error(self):
        """Test AIBackendError exception."""
        error = AIBackendError("Test error")
        assert str(error) == "Test error"
        assert isinstance(error, Exception)
    
    def test_model_not_found_error(self):
        """Test ModelNotFoundError exception."""
        error = ModelNotFoundError("Model not found")
        assert str(error) == "Model not found"
        assert isinstance(error, AIBackendError)
    
    def test_generation_error(self):
        """Test GenerationError exception."""
        error = GenerationError("Generation failed")
        assert str(error) == "Generation failed"
        assert isinstance(error, AIBackendError)
    
    def test_embedding_error(self):
        """Test EmbeddingError exception."""
        error = EmbeddingError("Embedding failed")
        assert str(error) == "Embedding failed"
        assert isinstance(error, AIBackendError)


class TestAIBackendBase:
    """Test AIBackend base class functionality."""
    
    @pytest.fixture
    async def backend(self):
        """Create a mock backend for testing."""
        backend = MockAIBackend({"test": "config"})
        await backend.initialize()
        yield backend
        await backend.cleanup()
    
    def test_backend_initialization(self):
        """Test backend initialization."""
        backend = MockAIBackend({"key": "value"})
        assert backend.config == {"key": "value"}
        assert backend._models_cache is None
    
    async def test_backend_lifecycle(self):
        """Test backend initialization and cleanup."""
        backend = MockAIBackend()
        
        # Initially not initialized
        assert not backend.initialized
        assert not await backend.health_check()
        
        # Initialize
        await backend.initialize()
        assert backend.initialized
        assert await backend.health_check()
        
        # Cleanup
        await backend.cleanup()
        assert not backend.initialized
    
    async def test_list_models(self, backend):
        """Test listing models."""
        models = await backend.list_models()
        
        assert len(models) == 2
        assert models[0].name == "test-text-model"
        assert models[0].type == ModelType.TEXT_GENERATION
        assert models[1].name == "test-embedding-model"
        assert models[1].type == ModelType.EMBEDDING
    
    async def test_get_model_info(self, backend):
        """Test getting model information."""
        # Existing model
        model_info = await backend.get_model_info("test-text-model")
        assert model_info is not None
        assert model_info.name == "test-text-model"
        
        # Non-existing model
        model_info = await backend.get_model_info("non-existent")
        assert model_info is None
    
    async def test_validate_model_success(self, backend):
        """Test successful model validation."""
        # Should not raise exception
        await backend.validate_model("test-text-model", ModelType.TEXT_GENERATION)
        await backend.validate_model("test-embedding-model", ModelType.EMBEDDING)
    
    async def test_validate_model_not_found(self, backend):
        """Test model validation with non-existent model."""
        with pytest.raises(ModelNotFoundError, match="Model 'non-existent' not found"):
            await backend.validate_model("non-existent", ModelType.TEXT_GENERATION)
    
    async def test_validate_model_wrong_type(self, backend):
        """Test model validation with wrong type."""
        with pytest.raises(ModelNotFoundError, match="is type text_generation, but embedding was required"):
            await backend.validate_model("test-text-model", ModelType.EMBEDDING)
    
    async def test_generate_text(self, backend):
        """Test text generation."""
        result = await backend.generate_text("Test prompt", "test-text-model")
        assert result == "Generated text for: Test prompt..."
    
    async def test_generate_text_not_initialized(self):
        """Test text generation with uninitialized backend."""
        backend = MockAIBackend()
        
        with pytest.raises(AIBackendError, match="Backend not initialized"):
            await backend.generate_text("Test prompt", "test-text-model")
    
    async def test_generate_stream(self, backend):
        """Test streaming text generation."""
        chunks = []
        async for chunk in backend.generate_stream("Test prompt", "test-text-model"):
            chunks.append(chunk)
        
        result = "".join(chunks)
        assert "Generated streaming text for: Test prompt..." in result
    
    async def test_generate_embeddings(self, backend):
        """Test embedding generation."""
        texts = ["text1", "text2", "text3"]
        embeddings = await backend.generate_embeddings(texts, "test-embedding-model")
        
        assert len(embeddings) == 3
        assert all(len(emb) == 3 for emb in embeddings)
        assert all(emb == [0.1, 0.2, 0.3] for emb in embeddings)