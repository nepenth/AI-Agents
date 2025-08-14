"""
Simple integration test for AI backend system.
"""

import pytest
from unittest.mock import patch, AsyncMock
from fastapi.testclient import TestClient

from app.main import app
from app.services.ai_service import get_ai_service


class TestAIIntegrationSimple:
    """Simple tests for AI backend integration."""
    
    def test_app_creation(self):
        """Test that the app can be created with AI service."""
        # This tests that imports work correctly
        assert app is not None
    
    def test_ai_service_creation(self):
        """Test that AI service can be created."""
        service = get_ai_service()
        assert service is not None
        assert not service._initialized  # Should not be initialized yet
    
    @pytest.mark.asyncio
    async def test_ai_service_initialization_mock(self):
        """Test AI service initialization with mocked backends."""
        with patch('app.ai.ollama.OllamaBackend') as mock_ollama:
            # Configure mock
            mock_instance = AsyncMock()
            mock_instance.initialize = AsyncMock()
            mock_instance.health_check = AsyncMock(return_value=True)
            mock_ollama.return_value = mock_instance
            
            # Test initialization
            service = get_ai_service()
            await service.initialize()
            
            assert service._initialized
            
            # Test cleanup
            await service.cleanup()
            assert not service._initialized
    
    def test_system_endpoints_exist(self):
        """Test that system endpoints are available."""
        client = TestClient(app)
        
        # Test basic health endpoint
        response = client.get("/health")
        assert response.status_code == 200
        
        # Test system health endpoint
        response = client.get("/api/v1/system/health")
        assert response.status_code == 200
    
    @pytest.mark.asyncio
    async def test_ai_status_endpoint_mock(self):
        """Test AI status endpoint with mocked service."""
        with patch('app.services.ai_service.get_ai_service') as mock_get_service:
            # Configure mock service
            mock_service = AsyncMock()
            mock_service.get_backend_status = AsyncMock(return_value={
                "initialized": True,
                "default_backend": "ollama",
                "total_backends": 1,
                "backends": {
                    "ollama": {
                        "type": "OllamaBackend",
                        "healthy": True
                    }
                }
            })
            mock_get_service.return_value = mock_service
            
            # Test endpoint
            client = TestClient(app)
            response = client.get("/api/v1/system/ai/status")
            assert response.status_code == 200
            
            data = response.json()
            assert data["initialized"] is True
            assert data["default_backend"] == "ollama"
            assert "ollama" in data["backends"]
    
    def test_config_ai_backends_structure(self):
        """Test that configuration provides proper AI backends structure."""
        from app.config import get_settings
        
        settings = get_settings()
        ai_config = settings.get_ai_backends_config()
        
        assert "default_ai_backend" in ai_config
        assert "ai_backends" in ai_config
        assert "ollama" in ai_config["ai_backends"]
        assert "localai" in ai_config["ai_backends"]
        
        # Check ollama config structure
        ollama_config = ai_config["ai_backends"]["ollama"]
        assert ollama_config["type"] == "ollama"
        assert "base_url" in ollama_config
        assert "timeout" in ollama_config