"""
Tests for application configuration.
"""
import pytest
from unittest.mock import patch
import os

from app.config import Settings, get_settings


def test_settings_default_values():
    """Test that settings have correct default values."""
    with patch.dict(os.environ, {
        "DATABASE_URL": "postgresql://test",
        "REDIS_URL": "redis://test",
        "CELERY_BROKER_URL": "redis://test",
        "CELERY_RESULT_BACKEND": "redis://test",
        "SECRET_KEY": "test-key"
    }):
        settings = Settings()
        
        assert settings.APP_NAME == "AI Agent Backend"
        assert settings.DEBUG is False
        assert settings.LOG_LEVEL == "INFO"
        assert settings.DEFAULT_AI_BACKEND == "ollama"
        assert settings.OLLAMA_BASE_URL == "http://localhost:11434"
        assert settings.DATA_DIR == "./data"


def test_settings_from_environment():
    """Test that settings are loaded from environment variables."""
    test_env = {
        "DATABASE_URL": "postgresql://test_user:test_pass@test_host:5432/test_db",
        "REDIS_URL": "redis://test_host:6379",
        "CELERY_BROKER_URL": "redis://test_host:6379/1",
        "CELERY_RESULT_BACKEND": "redis://test_host:6379/2",
        "SECRET_KEY": "test-secret-key",
        "DEBUG": "true",
        "LOG_LEVEL": "DEBUG",
        "DEFAULT_AI_BACKEND": "openai",
        "DATA_DIR": "/custom/data/path"
    }
    
    with patch.dict(os.environ, test_env):
        settings = Settings()
        
        assert settings.DATABASE_URL == test_env["DATABASE_URL"]
        assert settings.REDIS_URL == test_env["REDIS_URL"]
        assert settings.SECRET_KEY == test_env["SECRET_KEY"]
        assert settings.DEBUG is True
        assert settings.LOG_LEVEL == "DEBUG"
        assert settings.DEFAULT_AI_BACKEND == "openai"
        assert settings.DATA_DIR == "/custom/data/path"


def test_get_settings_caching():
    """Test that get_settings returns cached instance."""
    with patch.dict(os.environ, {
        "DATABASE_URL": "postgresql://test",
        "REDIS_URL": "redis://test",
        "CELERY_BROKER_URL": "redis://test",
        "CELERY_RESULT_BACKEND": "redis://test",
        "SECRET_KEY": "test-key"
    }):
        settings1 = get_settings()
        settings2 = get_settings()
        
        # Should return the same cached instance
        assert settings1 is settings2


def test_settings_validation():
    """Test that required settings raise validation errors when missing."""
    with pytest.raises(ValueError):
        # Missing required DATABASE_URL
        Settings(
            REDIS_URL="redis://test",
            CELERY_BROKER_URL="redis://test",
            CELERY_RESULT_BACKEND="redis://test",
            SECRET_KEY="test-key"
        )