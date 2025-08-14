"""
Integration tests for AI backend system.
"""

import pytest
from unittest.mock import patch, AsyncMock

from app.ai import (
    initialize_backend_manager, get_backend_manager, cleanup_backend_manager,
    ModelType, GenerationConfig, EmbeddingConfig
)
from app.config import get_settings


class TestAIBackendIntegration:
    """Test AI backend integration with the application."""
    
    @pytest.fixture
    def ai_config(self):
        """Create AI backend configuration."""
        return {
            "ai_backends": {
                "ollama": {
                    "type": "ollama",
                    "base_url": "http://localhost:11434",
                    "timeout": 60
                },
                "openai": {
                    "type": "openai_compatible",
                    "base_url": "https://api.openai.com",
                    "api_key": "test-key",
                    "timeout": 120
                }
            },
            "default_ai_backend": "ollama"
        }
    
    async def test_backend_manager_initialization(self, ai_config):
        """Test initializing backend manager with configuration."""
        # Mock backend classes to avoid actual network calls
        with patch('app.ai.ollama.OllamaBackend') as mock_ollama, \
             patch('app.ai.openai_compatible.OpenAICompatibleBackend') as mock_openai:
            
            # Configure mocks
            mock_ollama_instance = AsyncMock()
            mock_ollama_instance.initialize = AsyncMock()
            mock_ollama_instance.health_check = AsyncMock(return_value=True)
            mock_ollama.return_value = mock_ollama_instance
            
            mock_openai_instance = AsyncMock()
            mock_openai_instance.initialize = AsyncMock()
            mock_openai_instance.health_check = AsyncMock(return_value=True)
            mock_openai.return_value = mock_openai_instance
            
            # Initialize manager
            manager = initialize_backend_manager(ai_config)
            await manager.initialize_from_config()
            
            # Verify backends were created
            assert mock_ollama.called
            assert mock_openai.called
            
            # Verify initialization was called
            mock_ollama_instance.initialize.assert_called_once()
            mock_openai_instance.initialize.assert_called_once()
            
            # Test getting backends
            ollama_backend = await manager.get_backend("ollama")
            openai_backend = await manager.get_backend("openai")
            default_backend = await manager.get_backend()
            
            assert ollama_backend is mock_ollama_instance
            assert openai_backend is mock_openai_instance
            assert default_backend is mock_ollama_instance  # Default backend
            
            # Cleanup
            await cleanup_backend_manager()
    
    async def test_text_generation_workflow(self, ai_config):
        """Test complete text generation workflow."""
        with patch('app.ai.ollama.OllamaBackend') as mock_ollama:
            # Configure mock
            mock_instance = AsyncMock()
            mock_instance.initialize = AsyncMock()
            mock_instance.health_check = AsyncMock(return_value=True)
            mock_instance.list_models = AsyncMock(return_value=[
                AsyncMock(name="llama2:7b", type=ModelType.TEXT_GENERATION)
            ])
            mock_instance.validate_model = AsyncMock()
            mock_instance.generate_text = AsyncMock(return_value="Generated response")
            mock_ollama.return_value = mock_instance
            
            # Initialize and test
            manager = initialize_backend_manager(ai_config)
            await manager.initialize_from_config()
            
            # Get text generation backend
            backend = await manager.get_text_generation_backend()
            assert backend is not None
            
            # Generate text
            config = GenerationConfig(temperature=0.7, max_tokens=100)
            result = await backend.generate_text("Test prompt", "llama2:7b", config)
            
            assert result == "Generated response"
            mock_instance.generate_text.assert_called_once_with(
                "Test prompt", "llama2:7b", config
            )
            
            await cleanup_backend_manager()
    
    async def test_embedding_generation_workflow(self, ai_config):
        """Test complete embedding generation workflow."""
        with patch('app.ai.ollama.OllamaBackend') as mock_ollama:
            # Configure mock
            mock_instance = AsyncMock()
            mock_instance.initialize = AsyncMock()
            mock_instance.health_check = AsyncMock(return_value=True)
            mock_instance.list_models = AsyncMock(return_value=[
                AsyncMock(name="all-minilm:l6-v2", type=ModelType.EMBEDDING)
            ])
            mock_instance.validate_model = AsyncMock()
            mock_instance.generate_embeddings = AsyncMock(return_value=[
                [0.1, 0.2, 0.3], [0.4, 0.5, 0.6]
            ])
            mock_ollama.return_value = mock_instance
            
            # Initialize and test
            manager = initialize_backend_manager(ai_config)
            await manager.initialize_from_config()
            
            # Get embedding backend
            backend = await manager.get_embedding_backend()
            assert backend is not None
            
            # Generate embeddings
            texts = ["text1", "text2"]
            config = EmbeddingConfig(normalize=True, batch_size=16)
            embeddings = await backend.generate_embeddings(texts, "all-minilm:l6-v2", config)
            
            assert len(embeddings) == 2
            assert embeddings[0] == [0.1, 0.2, 0.3]
            assert embeddings[1] == [0.4, 0.5, 0.6]
            
            mock_instance.generate_embeddings.assert_called_once_with(
                texts, "all-minilm:l6-v2", config
            )
            
            await cleanup_backend_manager()
    
    async def test_backend_fallback(self, ai_config):
        """Test backend fallback when primary fails."""
        with patch('app.ai.ollama.OllamaBackend') as mock_ollama, \
             patch('app.ai.openai_compatible.OpenAICompatibleBackend') as mock_openai:
            
            # Configure Ollama to fail initialization
            mock_ollama_instance = AsyncMock()
            mock_ollama_instance.initialize = AsyncMock(side_effect=Exception("Connection failed"))
            mock_ollama.return_value = mock_ollama_instance
            
            # Configure OpenAI to succeed
            mock_openai_instance = AsyncMock()
            mock_openai_instance.initialize = AsyncMock()
            mock_openai_instance.health_check = AsyncMock(return_value=True)
            mock_openai_instance.list_models = AsyncMock(return_value=[
                AsyncMock(name="gpt-3.5-turbo", type=ModelType.TEXT_GENERATION)
            ])
            mock_openai.return_value = mock_openai_instance
            
            # Initialize manager
            manager = initialize_backend_manager(ai_config)
            await manager.initialize_from_config()
            
            # Ollama should have failed, but OpenAI should work
            ollama_backend = await manager.get_backend("ollama")
            openai_backend = await manager.get_backend("openai")
            
            assert ollama_backend is None  # Failed to initialize
            assert openai_backend is mock_openai_instance  # Succeeded
            
            # Can still get text generation from OpenAI
            text_backend = await manager.get_text_generation_backend("openai")
            assert text_backend is mock_openai_instance
            
            await cleanup_backend_manager()
    
    async def test_multiple_model_types(self, ai_config):
        """Test backend with multiple model types."""
        with patch('app.ai.ollama.OllamaBackend') as mock_ollama:
            # Configure mock with both text and embedding models
            mock_instance = AsyncMock()
            mock_instance.initialize = AsyncMock()
            mock_instance.health_check = AsyncMock(return_value=True)
            mock_instance.list_models = AsyncMock(return_value=[
                AsyncMock(name="llama2:7b", type=ModelType.TEXT_GENERATION),
                AsyncMock(name="all-minilm:l6-v2", type=ModelType.EMBEDDING)
            ])
            mock_ollama.return_value = mock_instance
            
            # Initialize manager
            manager = initialize_backend_manager(ai_config)
            await manager.initialize_from_config()
            
            # Should be able to get both types from same backend
            text_backend = await manager.get_text_generation_backend()
            embedding_backend = await manager.get_embedding_backend()
            
            assert text_backend is mock_instance
            assert embedding_backend is mock_instance
            
            await cleanup_backend_manager()
    
    def test_configuration_validation(self):
        """Test configuration validation."""
        # Missing backend type
        invalid_config = {
            "ai_backends": {
                "invalid": {
                    "base_url": "http://localhost:8080"
                    # Missing "type"
                }
            }
        }
        
        manager = initialize_backend_manager(invalid_config)
        # Should not raise exception during creation, only during initialization
        assert manager is not None
    
    async def test_backend_status_monitoring(self, ai_config):
        """Test backend status monitoring."""
        with patch('app.ai.ollama.OllamaBackend') as mock_ollama:
            # Configure mock
            mock_instance = AsyncMock()
            mock_instance.initialize = AsyncMock()
            mock_instance.health_check = AsyncMock(return_value=True)
            mock_ollama.return_value = mock_instance
            
            # Initialize manager
            manager = initialize_backend_manager(ai_config)
            await manager.initialize_from_config()
            
            # Check status
            status = manager.get_status()
            
            assert status["default_backend"] == "ollama"
            assert "ollama" in status["instances"]
            assert status["total_backends"] > 0
            
            # Check health
            health_results = await manager.factory.health_check_all()
            assert "ollama" in health_results
            assert health_results["ollama"] is True
            
            await cleanup_backend_manager()