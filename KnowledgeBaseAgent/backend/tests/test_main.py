"""
Tests for the main FastAPI application.
"""
import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, AsyncMock

from app.main import create_app


@pytest.fixture
def test_app():
    """Create test FastAPI application."""
    with patch('app.main.init_db', new_callable=AsyncMock):
        app = create_app()
        return app


@pytest.fixture
def client(test_app):
    """Create test client."""
    return TestClient(test_app)


def test_health_endpoint(client):
    """Test the health check endpoint."""
    response = client.get("/health")
    
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["service"] == "ai-agent-backend"
    assert data["version"] == "1.0.0"


def test_api_documentation_endpoints(client):
    """Test that API documentation endpoints are available."""
    # Test OpenAPI docs
    response = client.get("/docs")
    assert response.status_code == 200
    
    # Test ReDoc
    response = client.get("/redoc")
    assert response.status_code == 200
    
    # Test OpenAPI JSON
    response = client.get("/openapi.json")
    assert response.status_code == 200
    data = response.json()
    assert data["info"]["title"] == "AI Agent Backend API"


def test_cors_headers(client):
    """Test that CORS headers are properly configured."""
    response = client.options("/health")
    assert response.status_code == 200


def test_api_router_inclusion(test_app):
    """Test that all API routers are included."""
    routes = [route.path for route in test_app.routes]
    
    # Check that main API endpoints are included
    assert any("/api/v1/agent" in route for route in routes)
    assert any("/api/v1/content" in route for route in routes)
    assert any("/api/v1/chat" in route for route in routes)
    assert any("/api/v1/knowledge" in route for route in routes)
    assert any("/api/v1/system" in route for route in routes)