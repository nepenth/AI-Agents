"""
Tests for Ollama backend implementation.
"""

import pytest
import json
from unittest.mock import AsyncMock, MagicMock, patch
from aiohttp import ClientSession, ClientResponse
from aiohttp.test_utils import make_mocked_coro

from app.ai.ollama import OllamaBackend
from app.ai.base import (
    ModelType, GenerationConfig, EmbeddingConfig,
    AIBackendError, ModelNotFoundError, GenerationError, EmbeddingError
)


class TestOllamaBackend:
    """Test OllamaBackend functionality."""
    
    @pytest.fixture
    def config(self):
        """Create test configuration."""
        return {
            "base_url": "http://localhost:11434",
            "timeout": 60
        }
    
    @pytest.fixture
    def backend(self, config):
        """Create OllamaBackend instance."""
        return OllamaBackend(config)
    
    @pytest.fixture
    def mock_session(self):
        """Create mock aiohttp session."""
        session = AsyncMock(spec=ClientSession)
        return session
    
    def test_backend_initialization(self, config):
        """Test backend initialization with config."""
        backend = OllamaBackend(config)
        
        assert backend.base_url == "http://localhost:11434"
        assert backend.timeout == 60
        assert backend.session is None
    
    def test_backend_default_config(self):
        """Test backend with default configuration."""
        backend = OllamaBackend({})
        
        assert backend.base_url == "http://localhost:11434"
        assert backend.timeout == 300
    
    async def test_initialize_success(self, backend, mock_session):
        """Test successful backend initialization."""
        # Mock successful health check
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_session.get.return_value.__aenter__.return_value = mock_response
        
        with patch('aiohttp.ClientSession', return_value=mock_session):
            await backend.initialize()
        
        assert backend.session is mock_session
        mock_session.get.assert_called_once_with("http://localhost:11434/api/tags")
    
    async def test_initialize_failure(self, backend, mock_session):
        """Test backend initialization failure."""
        # Mock failed health check
        mock_response = AsyncMock()
        mock_response.status = 500
        mock_session.get.return_value.__aenter__.return_value = mock_response
        
        with patch('aiohttp.ClientSession', return_value=mock_session):
            with pytest.raises(AIBackendError, match="Failed to connect to Ollama server"):
                await backend.initialize()
    
    async def test_cleanup(self, backend, mock_session):
        """Test backend cleanup."""
        backend.session = mock_session
        
        await backend.cleanup()
        
        mock_session.close.assert_called_once()
        assert backend.session is None
    
    async def test_health_check_success(self, backend, mock_session):
        """Test successful health check."""
        backend.session = mock_session
        
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_session.get.return_value.__aenter__.return_value = mock_response
        
        result = await backend.health_check()
        
        assert result is True
        mock_session.get.assert_called_once_with("http://localhost:11434/api/tags")
    
    async def test_health_check_failure(self, backend, mock_session):
        """Test health check failure."""
        backend.session = mock_session
        
        mock_response = AsyncMock()
        mock_response.status = 500
        mock_session.get.return_value.__aenter__.return_value = mock_response
        
        result = await backend.health_check()
        
        assert result is False
    
    async def test_health_check_no_session(self, backend):
        """Test health check without session."""
        result = await backend.health_check()
        assert result is False
    
    async def test_list_models_success(self, backend, mock_session):
        """Test successful model listing."""
        backend.session = mock_session
        
        # Mock API response
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = make_mocked_coro({
            "models": [
                {"name": "llama2:7b"},
                {"name": "codellama:13b"},
                {"name": "all-minilm:l6-v2"}
            ]
        })
        mock_session.get.return_value.__aenter__.return_value = mock_response
        
        # Mock model details
        with patch.object(backend, '_get_model_details', return_value={"context_length": 2048}):
            models = await backend.list_models()
        
        assert len(models) == 3
        assert models[0].name == "llama2:7b"
        assert models[0].type == ModelType.TEXT_GENERATION
        assert models[2].name == "all-minilm:l6-v2"
        assert models[2].type == ModelType.EMBEDDING
    
    async def test_list_models_failure(self, backend, mock_session):
        """Test model listing failure."""
        backend.session = mock_session
        
        mock_response = AsyncMock()
        mock_response.status = 500
        mock_session.get.return_value.__aenter__.return_value = mock_response
        
        with pytest.raises(AIBackendError, match="Failed to list models"):
            await backend.list_models()
    
    async def test_generate_text_success(self, backend, mock_session):
        """Test successful text generation."""
        backend.session = mock_session
        backend._models_cache = [
            MagicMock(name="llama2:7b", type=ModelType.TEXT_GENERATION)
        ]
        
        # Mock API response
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = make_mocked_coro({
            "response": "Generated text response"
        })
        mock_session.post.return_value.__aenter__.return_value = mock_response
        
        result = await backend.generate_text("Test prompt", "llama2:7b")
        
        assert result == "Generated text response"
        
        # Verify API call
        mock_session.post.assert_called_once()
        call_args = mock_session.post.call_args
        assert call_args[0][0] == "http://localhost:11434/api/generate"
        
        payload = call_args[1]["json"]
        assert payload["model"] == "llama2:7b"
        assert payload["prompt"] == "Test prompt"
        assert payload["stream"] is False
    
    async def test_generate_text_with_config(self, backend, mock_session):
        """Test text generation with custom config."""
        backend.session = mock_session
        backend._models_cache = [
            MagicMock(name="llama2:7b", type=ModelType.TEXT_GENERATION)
        ]
        
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = make_mocked_coro({"response": "Generated text"})
        mock_session.post.return_value.__aenter__.return_value = mock_response
        
        config = GenerationConfig(
            temperature=0.5,
            max_tokens=100,
            top_k=50,
            stop_sequences=["END"]
        )
        
        await backend.generate_text("Test prompt", "llama2:7b", config)
        
        # Verify config was used
        call_args = mock_session.post.call_args
        payload = call_args[1]["json"]
        options = payload["options"]
        
        assert options["temperature"] == 0.5
        assert payload["options"]["num_predict"] == 100
        assert options["top_k"] == 50
        assert options["stop"] == ["END"]
    
    async def test_generate_text_failure(self, backend, mock_session):
        """Test text generation failure."""
        backend.session = mock_session
        backend._models_cache = [
            MagicMock(name="llama2:7b", type=ModelType.TEXT_GENERATION)
        ]
        
        mock_response = AsyncMock()
        mock_response.status = 500
        mock_response.text = make_mocked_coro("Server error")
        mock_session.post.return_value.__aenter__.return_value = mock_response
        
        with pytest.raises(GenerationError, match="Generation failed"):
            await backend.generate_text("Test prompt", "llama2:7b")
    
    async def test_generate_stream_success(self, backend, mock_session):
        """Test successful streaming generation."""
        backend.session = mock_session
        backend._models_cache = [
            MagicMock(name="llama2:7b", type=ModelType.TEXT_GENERATION)
        ]
        
        # Mock streaming response
        mock_response = AsyncMock()
        mock_response.status = 200
        
        # Mock content chunks
        chunks = [
            b'{"response": "Hello", "done": false}\n',
            b'{"response": " world", "done": false}\n',
            b'{"response": "!", "done": true}\n'
        ]
        mock_response.content.__aiter__.return_value = chunks
        mock_session.post.return_value.__aenter__.return_value = mock_response
        
        # Collect streaming results
        results = []
        async for chunk in backend.generate_stream("Test prompt", "llama2:7b"):
            results.append(chunk)
        
        assert results == ["Hello", " world", "!"]
    
    async def test_generate_embeddings_success(self, backend, mock_session):
        """Test successful embedding generation."""
        backend.session = mock_session
        backend._models_cache = [
            MagicMock(name="all-minilm:l6-v2", type=ModelType.EMBEDDING)
        ]
        
        # Mock API response
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = make_mocked_coro({
            "embedding": [0.1, 0.2, 0.3, 0.4]
        })
        mock_session.post.return_value.__aenter__.return_value = mock_response
        
        texts = ["text1", "text2"]
        embeddings = await backend.generate_embeddings(texts, "all-minilm:l6-v2")
        
        assert len(embeddings) == 2
        assert embeddings[0] == [0.1, 0.2, 0.3, 0.4]
        assert embeddings[1] == [0.1, 0.2, 0.3, 0.4]
        
        # Verify API calls
        assert mock_session.post.call_count == 2
    
    async def test_generate_embeddings_with_normalization(self, backend, mock_session):
        """Test embedding generation with normalization."""
        backend.session = mock_session
        backend._models_cache = [
            MagicMock(name="all-minilm:l6-v2", type=ModelType.EMBEDDING)
        ]
        
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = make_mocked_coro({
            "embedding": [3.0, 4.0]  # Norm = 5.0
        })
        mock_session.post.return_value.__aenter__.return_value = mock_response
        
        config = EmbeddingConfig(normalize=True)
        embeddings = await backend.generate_embeddings(["text"], "all-minilm:l6-v2", config)
        
        # Should be normalized: [3/5, 4/5] = [0.6, 0.8]
        assert len(embeddings) == 1
        assert abs(embeddings[0][0] - 0.6) < 1e-6
        assert abs(embeddings[0][1] - 0.8) < 1e-6
    
    async def test_generate_embeddings_failure(self, backend, mock_session):
        """Test embedding generation failure."""
        backend.session = mock_session
        backend._models_cache = [
            MagicMock(name="all-minilm:l6-v2", type=ModelType.EMBEDDING)
        ]
        
        mock_response = AsyncMock()
        mock_response.status = 500
        mock_response.text = make_mocked_coro("Server error")
        mock_session.post.return_value.__aenter__.return_value = mock_response
        
        with pytest.raises(EmbeddingError, match="Embedding generation failed"):
            await backend.generate_embeddings(["text"], "all-minilm:l6-v2")
    
    def test_determine_model_type(self, backend):
        """Test model type determination."""
        # Embedding models
        assert backend._determine_model_type("all-minilm:l6-v2") == ModelType.EMBEDDING
        assert backend._determine_model_type("sentence-transformers/all-MiniLM-L6-v2") == ModelType.EMBEDDING
        assert backend._determine_model_type("bge-large-en") == ModelType.EMBEDDING
        
        # Vision models
        assert backend._determine_model_type("llava:7b") == ModelType.VISION
        assert backend._determine_model_type("vision-model") == ModelType.VISION
        
        # Text generation models (default)
        assert backend._determine_model_type("llama2:7b") == ModelType.TEXT_GENERATION
        assert backend._determine_model_type("codellama:13b") == ModelType.TEXT_GENERATION
        assert backend._determine_model_type("mistral:7b") == ModelType.TEXT_GENERATION
    
    async def test_get_model_details_success(self, backend, mock_session):
        """Test getting model details."""
        backend.session = mock_session
        
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = make_mocked_coro({
            "parameters": {
                "num_ctx": 4096
            }
        })
        mock_session.post.return_value.__aenter__.return_value = mock_response
        
        details = await backend._get_model_details("llama2:7b")
        
        assert details["context_length"] == 4096
        
        # Verify API call
        mock_session.post.assert_called_once_with(
            "http://localhost:11434/api/show",
            json={"name": "llama2:7b"}
        )
    
    async def test_get_model_details_failure(self, backend, mock_session):
        """Test getting model details failure."""
        backend.session = mock_session
        
        mock_response = AsyncMock()
        mock_response.status = 404
        mock_session.post.return_value.__aenter__.return_value = mock_response
        
        details = await backend._get_model_details("non-existent")
        
        assert details == {}
    
    async def test_get_model_details_embedding_dimensions(self, backend, mock_session):
        """Test getting embedding dimensions for embedding models."""
        backend.session = mock_session
        
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = make_mocked_coro({})
        mock_session.post.return_value.__aenter__.return_value = mock_response
        
        # Test known embedding models
        details = await backend._get_model_details("all-minilm:l6-v2")
        assert details["embedding_dimensions"] == 384
        
        details = await backend._get_model_details("bge-large-en")
        assert details["embedding_dimensions"] == 1024
        
        details = await backend._get_model_details("unknown-embed")
        assert details["embedding_dimensions"] == 768  # Default