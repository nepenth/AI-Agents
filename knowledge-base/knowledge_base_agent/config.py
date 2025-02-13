import os
import json
from dataclasses import dataclass, field
from pathlib import Path
from dotenv import load_dotenv
import logging
import sys
from datetime import datetime
from pydantic import BaseModel, validator
from typing import Optional
from knowledge_base_agent.exceptions import ConfigurationError

load_dotenv()

@dataclass
class Config:
    # API endpoints and models
    ollama_url: str
    vision_model: str
    text_model: str
    
    # GitHub settings
    github_token: str
    github_user_name: str
    github_repo_url: str
    github_user_email: str
    
    # File paths
    knowledge_base_dir: Path
    categories_file: Path
    bookmarks_file: Path
    processed_tweets_file: Path
    media_cache_dir: Path
    log_file: Path
    
    # X/Twitter credentials
    x_username: str
    x_password: str
    x_bookmarks_url: str
    
    # Performance settings
    batch_size: int
    max_retries: int
    max_concurrent_requests: int
    request_timeout: int
    retry_backoff: bool
    max_pool_size: int

    @classmethod
    def from_env(cls) -> 'Config':
        """
        Create a Config instance from environment variables with validation.
        Raises ConfigurationError if required variables are missing or invalid.
        """
        try:
            # Required settings
            required_vars = {
                'GITHUB_TOKEN': os.getenv('GITHUB_TOKEN'),
                'GITHUB_USER_NAME': os.getenv('GITHUB_USER_NAME'),
                'GITHUB_REPO_URL': os.getenv('GITHUB_REPO_URL'),
                'X_USERNAME': os.getenv('X_USERNAME'),
                'X_PASSWORD': os.getenv('X_PASSWORD'),
            }

            # Check for missing required variables
            missing_vars = [k for k, v in required_vars.items() if not v]
            if missing_vars:
                raise ConfigurationError(f"Missing required environment variables: {', '.join(missing_vars)}")

            return cls(
                # API endpoints and models
                ollama_url=os.getenv('OLLAMA_URL', 'http://localhost:11434'),
                vision_model=os.getenv('VISION_MODEL', 'llama2-vision'),
                text_model=os.getenv('TEXT_MODEL', 'llama2'),
                
                # GitHub settings
                github_token=required_vars['GITHUB_TOKEN'],
                github_user_name=required_vars['GITHUB_USER_NAME'],
                github_repo_url=required_vars['GITHUB_REPO_URL'],
                github_user_email=os.getenv('GITHUB_USER_EMAIL', f"{required_vars['GITHUB_USER_NAME']}@users.noreply.github.com"),
                
                # File paths
                knowledge_base_dir=Path(os.getenv('KNOWLEDGE_BASE_DIR', 'kb-generated')),
                categories_file=Path(os.getenv('CATEGORIES_FILE', 'data/categories.json')),
                bookmarks_file=Path(os.getenv('BOOKMARKS_FILE', 'data/bookmarks_links.txt')),
                processed_tweets_file=Path(os.getenv('PROCESSED_TWEETS_FILE', 'data/processed_tweets.json')),
                media_cache_dir=Path(os.getenv('MEDIA_CACHE_DIR', 'data/media_cache')),
                log_file=Path(os.getenv('LOG_FILE', 'log/ai_agent.log')),
                
                # X/Twitter credentials
                x_username=required_vars['X_USERNAME'],
                x_password=required_vars['X_PASSWORD'],
                x_bookmarks_url=os.getenv('X_BOOKMARKS_URL', 'https://x.com/i/bookmarks'),
                
                # Performance settings
                batch_size=int(os.getenv('BATCH_SIZE', '1')),
                max_retries=int(os.getenv('MAX_RETRIES', '5')),
                max_concurrent_requests=int(os.getenv('MAX_CONCURRENT_REQUESTS', '1')),
                request_timeout=int(os.getenv('REQUEST_TIMEOUT', '180')),
                retry_backoff=os.getenv('RETRY_BACKOFF', 'True').lower() == 'true',
                max_pool_size=int(os.getenv('MAX_POOL_SIZE', '1')),
            )
        except ValueError as e:
            raise ConfigurationError(f"Invalid configuration value: {e}")
        except Exception as e:
            raise ConfigurationError(f"Configuration error: {e}")

    def validate_paths(self) -> None:
        """Ensure all required directories exist or can be created."""
        try:
            for path in [self.knowledge_base_dir, self.media_cache_dir]:
                path.mkdir(parents=True, exist_ok=True)
            
            # Ensure parent directories exist for files
            for path in [self.categories_file, self.bookmarks_file, 
                        self.processed_tweets_file, self.log_file]:
                path.parent.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            raise ConfigurationError(f"Failed to create required directories: {e}")

    def validate(self) -> None:
        """Validate the entire configuration."""
        self.validate_paths()
        
        # Validate URLs
        if not self.ollama_url.startswith(('http://', 'https://')):
            raise ConfigurationError(f"Invalid Ollama URL: {self.ollama_url}")
        
        if not self.github_repo_url.startswith(('http://', 'https://')):
            raise ConfigurationError(f"Invalid GitHub repo URL: {self.github_repo_url}")
        
        # Validate numeric values
        if self.batch_size < 1:
            raise ConfigurationError("batch_size must be at least 1")
        if self.max_retries < 0:
            raise ConfigurationError("max_retries cannot be negative")
        if self.request_timeout < 1:
            raise ConfigurationError("request_timeout must be at least 1 second")

def setup_logging(log_dir: Path) -> None:
    """Configure logging with both file and console handlers."""
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / f"kb_agent_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
    
    # Configure root logger
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler(sys.stdout)
        ]
    )

    # Add custom logging levels for different types of events
    logging.addLevelName(25, "SUCCESS")
    def success(self, message, *args, **kwargs):
        self._log(25, message, args, **kwargs)
    logging.Logger.success = success
