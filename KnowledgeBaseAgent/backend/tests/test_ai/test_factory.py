"""
Tests for AI backend factory and management.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from typing import Dict, Any

from app.ai.factory import (
    BackendRegistry, AIBackendFactory, AIBackendManager,
    get_backend_manager, initialize_backend_manager, cleanup_backend_manager
)
from app.ai.base import AIBackend, ModelType, ModelInfo
from .test_base import MockAIBackend


class TestBackendRegistry:
    """Test BackendRegistry functionality."""
    
    def test_default_backends_registered(self):
        """Test that default backends are registered."""
        backends = BackendRegistry.list_backends()
        
        assert "ollama" in backends
        assert "localai" in backends
        assert "openai" in backends
        assert "openai_compatible" in backends
    
    def test_register_custom_backend(self):
        """Test registering a custom backend."""
        class CustomBackend(AIBackend):
            pass
        
        BackendRegistry.register("custom", CustomBackend)
        
        assert "custom" in BackendRegistry.list_backends()
        assert BackendRegistry.get_backend_class("custom") == CustomBackend
    
    def test_get_backend_class(self):
        """Test getting backend classes."""
        from app.ai.ollama import OllamaBackend
        
        backend_class = BackendRegistry.get_backend_class("ollama")
        assert backend_class == OllamaBackend
        
        # Non-existent backend
        backend_class = BackendRegistry.get_backend_class("non-existent")
        assert backend_class is None


class TestAIBackendFactory:
    """Test AIBackendFactory functionality."""
    
    @pytest.fixture
    def factory(self):
        """Create a factory for testing."""
        return AIBackendFactory()
    
    @pytest.fixture
    def mock_backend_class(self):
        """Create a mock backend class."""
        with patch.object(BackendRegistry, 'get_backend_class') as mock:
            mock.return_value = MockAIBackend
            yield mock
    
    async def test_create_backend_success(self, factory, mock_backend_class):
        """Test successful backend creation."""
        config = {"test": "config"}
        
        backend = await factory.create_backend("mock", config, "test-instance")
        
        assert isinstance(backend, MockAIBackend)
        assert backend.initialized
        assert "test-instance" in factory._instances
    
    async def test_create_backend_unknown_type(self, factory):
        """Test creating backend with unknown type."""
        with pytest.raises(ValueError, match="Unknown backend type: unknown"):
            await factory.create_backend("unknown", {})
    
    async def test_create_backend_duplicate_instance(self, factory, mock_backend_class):
        """Test creating duplicate backend instance."""
        config = {"test": "config"}
        
        # Create first instance
        backend1 = await factory.create_backend("mock", config, "test-instance")
        
        # Create duplicate - should return existing
        backend2 = await factory.create_backend("mock", config, "test-instance")
        
        assert backend1 is backend2
        assert len(factory._instances) == 1
    
    async def test_create_backend_default_name(self, factory, mock_backend_class):
        """Test creating backend with default instance name."""
        backend = await factory.create_backend("mock", {})
        
        assert "mock" in factory._instances
        assert factory._instances["mock"] is backend
    
    async def test_get_backend(self, factory, mock_backend_class):
        """Test getting existing backend."""
        config = {"test": "config"}
        
        # Create backend
        created_backend = await factory.create_backend("mock", config, "test-instance")
        
        # Get backend
        retrieved_backend = await factory.get_backend("test-instance")
        
        assert retrieved_backend is created_backend
        
        # Get non-existent backend
        non_existent = await factory.get_backend("non-existent")
        assert non_existent is None
    
    async def test_remove_backend(self, factory, mock_backend_class):
        """Test removing backend."""
        config = {"test": "config"}
        
        # Create backend
        await factory.create_backend("mock", config, "test-instance")
        assert "test-instance" in factory._instances
        
        # Remove backend
        result = await factory.remove_backend("test-instance")
        assert result is True
        assert "test-instance" not in factory._instances
        
        # Remove non-existent backend
        result = await factory.remove_backend("non-existent")
        assert result is False
    
    async def test_cleanup_all(self, factory, mock_backend_class):
        """Test cleaning up all backends."""
        config = {"test": "config"}
        
        # Create multiple backends
        await factory.create_backend("mock", config, "backend1")
        await factory.create_backend("mock", config, "backend2")
        
        assert len(factory._instances) == 2
        
        # Cleanup all
        await factory.cleanup_all()
        
        assert len(factory._instances) == 0
    
    def test_list_instances(self, factory):
        """Test listing backend instances."""
        # Empty initially
        instances = factory.list_instances()
        assert instances == {}
    
    async def test_health_check_all(self, factory, mock_backend_class):
        """Test health check for all backends."""
        config = {"test": "config"}
        
        # Create backends
        await factory.create_backend("mock", config, "backend1")
        await factory.create_backend("mock", config, "backend2")
        
        # Health check all
        results = await factory.health_check_all()
        
        assert len(results) == 2
        assert results["backend1"] is True
        assert results["backend2"] is True


class TestAIBackendManager:
    """Test AIBackendManager functionality."""
    
    @pytest.fixture
    def config(self):
        """Create test configuration."""
        return {
            "ai_backends": {
                "primary": {
                    "type": "mock",
                    "base_url": "http://localhost:8080"
                },
                "secondary": {
                    "type": "mock",
                    "base_url": "http://localhost:8081"
                }
            },
            "default_ai_backend": "primary"
        }
    
    @pytest.fixture
    def mock_backend_class(self):
        """Create a mock backend class."""
        with patch.object(BackendRegistry, 'get_backend_class') as mock:
            mock.return_value = MockAIBackend
            yield mock
    
    async def test_initialize_from_config(self, config, mock_backend_class):
        """Test initializing manager from configuration."""
        manager = AIBackendManager(config)
        
        await manager.initialize_from_config()
        
        # Check backends were created
        primary = await manager.get_backend("primary")
        secondary = await manager.get_backend("secondary")
        
        assert primary is not None
        assert secondary is not None
        assert manager._default_backend == "primary"
    
    async def test_initialize_empty_config(self):
        """Test initializing with empty configuration."""
        manager = AIBackendManager({})
        
        await manager.initialize_from_config()
        
        assert manager._default_backend is None
    
    async def test_get_backend_default(self, config, mock_backend_class):
        """Test getting default backend."""
        manager = AIBackendManager(config)
        await manager.initialize_from_config()
        
        # Get default backend
        backend = await manager.get_backend()
        assert backend is not None
        
        # Should be the primary backend
        primary = await manager.get_backend("primary")
        assert backend is primary
    
    async def test_get_backend_specific(self, config, mock_backend_class):
        """Test getting specific backend."""
        manager = AIBackendManager(config)
        await manager.initialize_from_config()
        
        # Get specific backend
        backend = await manager.get_backend("secondary")
        assert backend is not None
        
        # Should be different from primary
        primary = await manager.get_backend("primary")
        assert backend is not primary
    
    async def test_get_backend_no_default(self):
        """Test getting backend when no default is set."""
        manager = AIBackendManager({})
        
        backend = await manager.get_backend()
        assert backend is None
    
    async def test_get_text_generation_backend(self, config, mock_backend_class):
        """Test getting text generation backend."""
        manager = AIBackendManager(config)
        await manager.initialize_from_config()
        
        backend = await manager.get_text_generation_backend()
        assert backend is not None
        
        # Verify it has text generation models
        models = await backend.list_models()
        text_models = [m for m in models if m.type == ModelType.TEXT_GENERATION]
        assert len(text_models) > 0
    
    async def test_get_embedding_backend(self, config, mock_backend_class):
        """Test getting embedding backend."""
        manager = AIBackendManager(config)
        await manager.initialize_from_config()
        
        backend = await manager.get_embedding_backend()
        assert backend is not None
        
        # Verify it has embedding models
        models = await backend.list_models()
        embedding_models = [m for m in models if m.type == ModelType.EMBEDDING]
        assert len(embedding_models) > 0
    
    async def test_cleanup(self, config, mock_backend_class):
        """Test manager cleanup."""
        manager = AIBackendManager(config)
        await manager.initialize_from_config()
        
        # Verify backends exist
        assert len(manager.factory._instances) == 2
        
        # Cleanup
        await manager.cleanup()
        
        # Verify backends are cleaned up
        assert len(manager.factory._instances) == 0
    
    def test_get_status(self, config):
        """Test getting manager status."""
        manager = AIBackendManager(config)
        
        status = manager.get_status()
        
        assert "default_backend" in status
        assert "instances" in status
        assert "total_backends" in status
        assert status["total_backends"] == 0


class TestGlobalBackendManager:
    """Test global backend manager functions."""
    
    def test_initialize_backend_manager(self):
        """Test initializing global backend manager."""
        config = {"test": "config"}
        
        manager = initialize_backend_manager(config)
        
        assert isinstance(manager, AIBackendManager)
        assert manager.config == config
        assert get_backend_manager() is manager
    
    async def test_cleanup_backend_manager(self):
        """Test cleaning up global backend manager."""
        config = {"test": "config"}
        
        # Initialize manager
        manager = initialize_backend_manager(config)
        assert get_backend_manager() is not None
        
        # Cleanup
        await cleanup_backend_manager()
        assert get_backend_manager() is None
    
    def test_get_backend_manager_none(self):
        """Test getting backend manager when none is set."""
        # Ensure no global manager
        import app.ai.factory
        app.ai.factory._backend_manager = None
        
        manager = get_backend_manager()
        assert manager is None