"""
Configuration management using Pydantic settings.
"""
from functools import lru_cache
from typing import List, Dict, Any, Optional
from pydantic import Field
try:
    # Pydantic v2
    from pydantic import field_validator
except Exception:  # pragma: no cover - fallback for v1 if ever needed
    from pydantic import validator as field_validator  # type: ignore
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings with environment variable support."""
    
    # Application settings
    APP_NAME: str = "AI Agent Backend"
    DEBUG: bool = Field(default=False, env="DEBUG")
    LOG_LEVEL: str = Field(default="INFO", env="LOG_LEVEL")
    
    # Database settings
    DATABASE_URL: str = Field(..., env="DATABASE_URL")
    DATABASE_ECHO: bool = Field(default=False, env="DATABASE_ECHO")
    
    # Redis settings
    REDIS_URL: str = Field(..., env="REDIS_URL")
    
    # Celery settings
    CELERY_BROKER_URL: str = Field(..., env="CELERY_BROKER_URL")
    CELERY_RESULT_BACKEND: str = Field(..., env="CELERY_RESULT_BACKEND")
    
    # CORS settings
    ALLOWED_ORIGINS: List[str] = Field(
        default=["http://localhost:3000", "http://localhost:5173"],
        env="ALLOWED_ORIGINS"
    )
    
    # AI Backend settings
    DEFAULT_AI_BACKEND: str = Field(default="ollama", env="DEFAULT_AI_BACKEND")
    OLLAMA_BASE_URL: str = Field(default="http://localhost:11434", env="OLLAMA_BASE_URL")
    LOCALAI_BASE_URL: str = Field(default="http://localhost:8080", env="LOCALAI_BASE_URL")
    OPENAI_API_KEY: str = Field(default="", env="OPENAI_API_KEY")
    OPENAI_BASE_URL: str = Field(default="https://api.openai.com/v1", env="OPENAI_BASE_URL")
    
    # AI Backend timeout settings
    AI_BACKEND_TIMEOUT: int = Field(default=300, env="AI_BACKEND_TIMEOUT")
    AI_REQUEST_TIMEOUT: int = Field(default=60, env="AI_REQUEST_TIMEOUT")
    
    # Rate limiting for external APIs
    OPENAI_MAX_REQUESTS_PER_MINUTE: int = Field(default=60, env="OPENAI_MAX_REQUESTS_PER_MINUTE")
    OPENAI_MAX_TOKENS_PER_MINUTE: int = Field(default=150000, env="OPENAI_MAX_TOKENS_PER_MINUTE")
    
    # File storage settings
    DATA_DIR: str = Field(default="./data", env="DATA_DIR")
    MEDIA_DIR: str = Field(default="./data/media", env="MEDIA_DIR")
    KNOWLEDGE_BASE_DIR: str = Field(default="./data/knowledge_base", env="KNOWLEDGE_BASE_DIR")
    
    # Security settings
    SECRET_KEY: str = Field(..., env="SECRET_KEY")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(default=30, env="ACCESS_TOKEN_EXPIRE_MINUTES")
    
    # Twitter/X API settings
    X_API_KEY: str = Field(default="", env="X_API_KEY")
    X_API_SECRET: str = Field(default="", env="X_API_SECRET")
    X_BEARER_TOKEN: str = Field(default="", env="X_BEARER_TOKEN")
    X_BOOKMARK_URL: str = Field(default="https://api.twitter.com/2/users/me/bookmarks", env="X_BOOKMARK_URL")
    X_API_TIMEOUT: int = Field(default=30, env="X_API_TIMEOUT")
    X_API_MAX_RETRIES: int = Field(default=3, env="X_API_MAX_RETRIES")
    X_API_RATE_LIMIT_WINDOW: int = Field(default=900, env="X_API_RATE_LIMIT_WINDOW")  # 15 minutes
    X_API_RATE_LIMIT_REQUESTS: int = Field(default=75, env="X_API_RATE_LIMIT_REQUESTS")
    X_THREAD_DETECTION_ENABLED: bool = Field(default=True, env="X_THREAD_DETECTION_ENABLED")
    X_THREAD_MAX_DEPTH: int = Field(default=50, env="X_THREAD_MAX_DEPTH")
    X_THREAD_TIMEOUT: int = Field(default=60, env="X_THREAD_TIMEOUT")
    X_MEDIA_CACHE_ENABLED: bool = Field(default=True, env="X_MEDIA_CACHE_ENABLED")
    X_MEDIA_MAX_SIZE: int = Field(default=10485760, env="X_MEDIA_MAX_SIZE")  # 10MB
    X_MEDIA_ALLOWED_TYPES: List[str] = Field(
        default=["image/jpeg", "image/png", "image/gif", "video/mp4", "video/quicktime"],
        env="X_MEDIA_ALLOWED_TYPES"
    )
    
    # Pydantic v2 settings config
    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=True,
        extra="ignore",
    )


    # Normalize ALLOWED_ORIGINS from JSON or comma-separated strings
    @field_validator("ALLOWED_ORIGINS", mode="before")
    @classmethod
    def _coerce_allowed_origins(cls, value):  # type: ignore[override]
        if isinstance(value, str):
            text = value.strip()
            if not text:
                return []
            # Try JSON first
            try:
                import json
                parsed = json.loads(text)
                if isinstance(parsed, list):
                    return parsed
            except Exception:
                pass
            # Fallback: comma-separated list
            return [item.strip() for item in text.split(',') if item.strip()]
        return value

    # Normalize X_MEDIA_ALLOWED_TYPES from JSON or comma-separated strings
    @field_validator("X_MEDIA_ALLOWED_TYPES", mode="before")
    @classmethod
    def _coerce_media_types(cls, value):  # type: ignore[override]
        if isinstance(value, str):
            text = value.strip()
            if not text:
                return []
            # Try JSON first
            try:
                import json
                parsed = json.loads(text)
                if isinstance(parsed, list):
                    return parsed
            except Exception:
                pass
            # Fallback: comma-separated list
            return [item.strip() for item in text.split(',') if item.strip()]
        return value

    def get_ai_backends_config(self) -> Dict[str, Any]:
        """Get AI backends configuration dictionary."""
        config = {
            "default_ai_backend": self.DEFAULT_AI_BACKEND,
            "ai_backends": {}
        }
        
        # Ollama backend
        config["ai_backends"]["ollama"] = {
            "type": "ollama",
            "base_url": self.OLLAMA_BASE_URL,
            "timeout": self.AI_BACKEND_TIMEOUT
        }
        
        # LocalAI backend
        config["ai_backends"]["localai"] = {
            "type": "localai",
            "base_url": self.LOCALAI_BASE_URL,
            "timeout": self.AI_BACKEND_TIMEOUT
        }
        
        # OpenAI backend (only if API key is provided)
        if self.OPENAI_API_KEY:
            config["ai_backends"]["openai"] = {
                "type": "openai_compatible",
                "base_url": self.OPENAI_BASE_URL,
                "api_key": self.OPENAI_API_KEY,
                "timeout": self.AI_BACKEND_TIMEOUT,
                "max_requests_per_minute": self.OPENAI_MAX_REQUESTS_PER_MINUTE,
                "max_tokens_per_minute": self.OPENAI_MAX_TOKENS_PER_MINUTE
            }
        
        return config


@lru_cache()
def get_settings() -> Settings:
    """Get cached application settings."""
    return Settings()