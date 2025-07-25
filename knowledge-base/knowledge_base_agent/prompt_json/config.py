"""
Configuration management for the JSON prompt system.

This module provides configuration classes and utilities for managing
JSON prompt system settings, directories, and runtime options.
"""

import os
from pathlib import Path
from typing import Optional, Dict, Any
from dataclasses import dataclass


@dataclass
class JsonPromptConfig:
    """Configuration for the JSON prompt system."""
    
    # Directory paths
    prompt_directory: Optional[Path] = None
    schema_directory: Optional[Path] = None
    cache_directory: Optional[Path] = None
    
    # Runtime settings
    enable_caching: bool = True
    cache_ttl: int = 3600  # Cache time-to-live in seconds
    validation_level: str = "strict"  # "strict", "lenient", "disabled"
    fallback_to_original: bool = True  # Fallback to original prompts if JSON fails
    
    # Performance settings
    max_cache_size: int = 1000
    concurrent_executions: int = 10
    timeout_seconds: int = 30
    
    # Logging settings
    log_level: str = "INFO"
    log_prompt_executions: bool = False
    log_validation_errors: bool = True
    
    def __post_init__(self):
        """Initialize default paths if not provided."""
        if self.prompt_directory is None:
            # Default to prompts subdirectory in the package
            package_dir = Path(__file__).parent
            self.prompt_directory = package_dir / "prompts"
        
        if self.schema_directory is None:
            self.schema_directory = Path(__file__).parent / "schemas"
        
        if self.cache_directory is None:
            self.cache_directory = Path.home() / ".cache" / "json_prompts"
    
    @classmethod
    def from_env(cls) -> 'JsonPromptConfig':
        """Create configuration from environment variables."""
        return cls(
            prompt_directory=Path(os.getenv("JSON_PROMPT_DIR", "")) if os.getenv("JSON_PROMPT_DIR") else None,
            enable_caching=os.getenv("JSON_PROMPT_CACHE", "true").lower() == "true",
            cache_ttl=int(os.getenv("JSON_PROMPT_CACHE_TTL", "3600")),
            validation_level=os.getenv("JSON_PROMPT_VALIDATION", "strict"),
            fallback_to_original=os.getenv("JSON_PROMPT_FALLBACK", "true").lower() == "true",
            log_level=os.getenv("JSON_PROMPT_LOG_LEVEL", "INFO"),
            log_prompt_executions=os.getenv("JSON_PROMPT_LOG_EXECUTIONS", "false").lower() == "true"
        )
    
    @classmethod
    def from_dict(cls, config_dict: Dict[str, Any]) -> 'JsonPromptConfig':
        """Create configuration from a dictionary."""
        # Convert string paths to Path objects
        if "prompt_directory" in config_dict and config_dict["prompt_directory"]:
            config_dict["prompt_directory"] = Path(config_dict["prompt_directory"])
        if "schema_directory" in config_dict and config_dict["schema_directory"]:
            config_dict["schema_directory"] = Path(config_dict["schema_directory"])
        if "cache_directory" in config_dict and config_dict["cache_directory"]:
            config_dict["cache_directory"] = Path(config_dict["cache_directory"])
        
        return cls(**config_dict)
    
    def ensure_directories(self) -> None:
        """Ensure all configured directories exist."""
        for directory in [self.prompt_directory, self.schema_directory, self.cache_directory]:
            if directory and not directory.exists():
                directory.mkdir(parents=True, exist_ok=True)


# Global configuration instance
_global_config: Optional[JsonPromptConfig] = None


def get_config() -> JsonPromptConfig:
    """Get the global JSON prompt configuration."""
    global _global_config
    if _global_config is None:
        _global_config = JsonPromptConfig.from_env()
    return _global_config


def set_config(config: JsonPromptConfig) -> None:
    """Set the global JSON prompt configuration."""
    global _global_config
    _global_config = config


def reset_config() -> None:
    """Reset the global configuration to defaults."""
    global _global_config
    _global_config = None