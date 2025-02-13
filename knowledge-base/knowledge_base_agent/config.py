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
    data_processing_dir: Path
    knowledge_base_dir: Path
    categories_file: Path
    bookmarks_file: Path
    processed_tweets_file: Path
    media_cache_dir: Path
    tweet_cache_file: Path
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

    def __init__(
        self,
        data_processing_dir: Optional[Path] = None,
        knowledge_base_dir: Optional[Path] = None,
        bookmarks_file: Optional[Path] = None,
        github_token: Optional[str] = None,
        github_repo_url: Optional[str] = None,
        github_user_name: Optional[str] = None,
        github_user_email: Optional[str] = None,
        x_username: Optional[str] = None,
        x_password: Optional[str] = None,
        ollama_url: Optional[str] = None,
        text_model: Optional[str] = None,
        vision_model: Optional[str] = None,
        log_file: Optional[str] = None,
        log_level: Optional[str] = None,
        request_timeout: Optional[int] = None,
        max_pool_size: Optional[int] = None
    ):
        # Data directories setup
        self.data_processing_dir = Path(data_processing_dir or os.getenv('DATA_PROCESSING_DIR', 'data'))
        self.knowledge_base_dir = Path(knowledge_base_dir or os.getenv('KNOWLEDGE_BASE_DIR', 'kb-generated'))
        
        # Update paths to use data_processing_dir
        self.tweet_cache_file = self.data_processing_dir / 'tweet_cache.json'
        self.categories_file = self.data_processing_dir / 'categories.json'
        self.media_cache_dir = Path(os.getenv('MEDIA_CACHE_DIR', self.data_processing_dir / 'media_cache'))
        self.processed_tweets_file = self.data_processing_dir / 'processed_tweets.json'
        self.bookmarks_file = self.data_processing_dir / 'bookmarks.json'
        self.log_file = self.data_processing_dir / 'logs' / f"kb_agent_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
        
        # Logging configuration from environment
        self.log_level = log_level or os.getenv('LOG_LEVEL', 'INFO')
        
        # GitHub configuration
        self.github_token = github_token
        self.github_repo_url = github_repo_url
        self.github_user_name = github_user_name
        self.github_user_email = github_user_email
        
        # X/Twitter configuration
        self.x_username = x_username
        self.x_password = x_password
        
        # AI model configuration
        self.ollama_url = ollama_url or "http://localhost:11434"
        self.text_model = text_model or "mistral"
        self.vision_model = vision_model or "llava"
        
        # Request timeout configuration
        self.request_timeout = request_timeout or int(os.getenv('REQUEST_TIMEOUT', '30'))
        self.max_pool_size = max_pool_size or int(os.getenv('MAX_POOL_SIZE', '10'))
        
        # Rest of the config initialization...

    @classmethod
    def from_env(cls) -> 'Config':
        """Create Config instance from environment variables."""
        try:
            return cls(
                knowledge_base_dir=os.getenv('KNOWLEDGE_BASE_DIR'),
                bookmarks_file=os.getenv('BOOKMARKS_FILE'),
                github_token=os.getenv('GITHUB_TOKEN'),
                github_repo_url=os.getenv('GITHUB_REPO_URL'),
                github_user_name=os.getenv('GITHUB_USER_NAME'),
                github_user_email=os.getenv('GITHUB_USER_EMAIL'),
                x_username=os.getenv('X_USERNAME'),
                x_password=os.getenv('X_PASSWORD'),
                ollama_url=os.getenv('OLLAMA_URL'),
                text_model=os.getenv('TEXT_MODEL'),
                vision_model=os.getenv('VISION_MODEL'),
                log_file=os.getenv('LOG_FILE'),
                log_level=os.getenv('LOG_LEVEL'),
                request_timeout=os.getenv('REQUEST_TIMEOUT'),
                max_pool_size=os.getenv('MAX_POOL_SIZE')
            )
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
