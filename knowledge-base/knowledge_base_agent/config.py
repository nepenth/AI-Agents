import sys
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional
from pydantic_settings import BaseSettings
from pydantic import HttpUrl, Field, field_validator
from knowledge_base_agent.exceptions import ConfigurationError
import os
from dotenv import load_dotenv

class Config(BaseSettings):
    # API endpoints and models
    ollama_url: HttpUrl = Field(..., alias="OLLAMA_URL")
    vision_model: str = Field(..., alias="VISION_MODEL")
    text_model: str = Field(..., alias="TEXT_MODEL")
    fallback_model: str = Field(..., alias="FALLBACK_MODEL")
    
    # GitHub settings
    github_token: str = Field(..., alias="GITHUB_TOKEN")
    github_user_name: str = Field(..., alias="GITHUB_USER_NAME")
    github_repo_url: HttpUrl = Field(..., alias="GITHUB_REPO_URL")
    github_user_email: str = Field(..., alias="GITHUB_USER_EMAIL")
    git_enabled: bool = Field(..., alias="GIT_ENABLED")
    
    # File paths
    data_processing_dir: Path = Field(..., alias="DATA_PROCESSING_DIR")
    knowledge_base_dir: Path = Field(..., alias="KNOWLEDGE_BASE_DIR")
    categories_file: Path = Field(..., alias="CATEGORIES_FILE")
    bookmarks_file: Path = Field(..., alias="BOOKMARKS_FILE")
    processed_tweets_file: Path = Field(..., alias="PROCESSED_TWEETS_FILE")
    media_cache_dir: Path = Field(..., alias="MEDIA_CACHE_DIR")
    tweet_cache_file: Path = Field(..., alias="TWEET_CACHE_FILE")
    log_file: Path = Field(..., alias="LOG_FILE")
    unprocessed_tweets_file: Path = Field(..., alias="UNPROCESSED_TWEETS_FILE")
    log_dir: Path = Field(..., alias="LOG_DIR")
    
    # X/Twitter credentials
    x_username: str = Field(..., alias="X_USERNAME")
    x_password: str = Field(..., alias="X_PASSWORD")
    x_bookmarks_url: str = Field(..., alias="X_BOOKMARKS_URL")
    
    # Logging and performance
    log_level: str = Field("DEBUG", alias="LOG_LEVEL")
    max_pool_size: int = Field(1, alias="MAX_POOL_SIZE")
    rate_limit_requests: int = Field(100, alias="RATE_LIMIT_REQUESTS")
    rate_limit_period: int = Field(
        3600,
        alias="RATE_LIMIT_PERIOD",
        description="Rate limit period in seconds"
    )
    
    # Browser settings
    selenium_timeout: int = Field(30, alias="SELENIUM_TIMEOUT")
    selenium_headless: bool = Field(True, alias="SELENIUM_HEADLESS")
    
    # Content settings
    max_content_length: int = Field(5000, alias="MAX_CONTENT_LENGTH")
    summary_length: int = Field(280, alias="SUMMARY_LENGTH")
    min_content_length: int = Field(50, alias="MIN_CONTENT_LENGTH")
    content_generation_timeout: int = Field(300, alias="CONTENT_GENERATION_TIMEOUT")
    content_retries: int = Field(3, alias="CONTENT_RETRIES")
    
    # Processing phase settings
    process_media: bool = Field(True, alias="PROCESS_MEDIA")
    process_categories: bool = Field(True, alias="PROCESS_CATEGORIES")
    process_kb_items: bool = Field(True, alias="PROCESS_KB_ITEMS")
    regenerate_readme: bool = Field(True, alias="REGENERATE_README")
    
    # Request settings
    batch_size: int = Field(1, alias="BATCH_SIZE")
    max_retries: int = Field(5, alias="MAX_RETRIES")
    max_concurrent_requests: int = Field(1, alias="MAX_CONCURRENT_REQUESTS")
    request_timeout: int = Field(180, alias="REQUEST_TIMEOUT")
    retry_backoff: bool = Field(True, alias="RETRY_BACKOFF")
    
    # Reprocessing flags
    reprocess_media: bool = Field(
        False,
        description="Whether to reprocess media for all tweets"
    )
    reprocess_categories: bool = Field(
        False,
        description="Whether to reprocess categories for all tweets"
    )
    reprocess_kb_items: bool = Field(
        False,
        description="Whether to regenerate knowledge base items"
    )
    regenerate_root_readme: bool = Field(
        False,
        description="Whether to regenerate the root README.md"
    )
    
    @field_validator("*")
    def validate_paths(cls, v, field):
        if isinstance(v, Path):
            v.parent.mkdir(parents=True, exist_ok=True)
        return v
    
    @field_validator('rate_limit_period', mode='before')
    def validate_rate_limit_period(cls, v):
        logging.debug(f"Raw rate_limit_period value: '{v}', type: {type(v)}")
        if isinstance(v, str):
            v = v.split('#')[0].strip()
        try:
            return int(v)
        except (ValueError, TypeError) as e:
            logging.error(f"Failed to parse rate_limit_period: {e}")
            raise ValueError(f"Invalid rate_limit_period value: {v}")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        populate_by_name = True
        extra = "ignore"

    def ensure_directories(self) -> None:
        """Ensure all required directories exist."""
        self.knowledge_base_dir.mkdir(parents=True, exist_ok=True)
        self.data_processing_dir.mkdir(parents=True, exist_ok=True)
        self.media_cache_dir.mkdir(parents=True, exist_ok=True)
        self.categories_file.parent.mkdir(parents=True, exist_ok=True)
        self.bookmarks_file.parent.mkdir(parents=True, exist_ok=True)
        self.tweet_cache_file.parent.mkdir(parents=True, exist_ok=True)
        self.processed_tweets_file.parent.mkdir(parents=True, exist_ok=True)

    def init_log_file(self) -> None:
        """Initialize the log file path with the current timestamp if needed."""
        if '{timestamp}' in str(self.log_file):
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            self.log_file = Path(str(self.log_file).replace('{timestamp}', timestamp))
        self.log_file.parent.mkdir(parents=True, exist_ok=True)

    def setup_logging(self) -> None:
        """Configure logging with proper formatting for long messages."""
        # Initialize log file with timestamp
        self.init_log_file()
        
        # Clear any existing handlers to avoid duplicates
        root_logger = logging.getLogger()
        root_logger.handlers.clear()
        
        # File handler with timestamped log file
        file_handler = logging.FileHandler(self.log_file, mode='a', encoding='utf-8')
        file_handler.setLevel(logging.DEBUG)
        file_formatter = logging.Formatter(
            '%(asctime)s - %(levelname)s - %(message).1000s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        file_handler.setFormatter(file_formatter)
        
        # Console handler
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        console_formatter = logging.Formatter('%(levelname)s - %(message)s')
        console_handler.setFormatter(console_formatter)
        
        # Configure root logger
        root_logger.setLevel(logging.DEBUG)
        root_logger.addHandler(file_handler)
        root_logger.addHandler(console_handler)
        
        # Reduce noise from git operations
        logging.getLogger('git.cmd').setLevel(logging.INFO)
        logging.getLogger('git.util').setLevel(logging.INFO)
        
        logging.debug("Logging configured with file: %s", self.log_file)

    @classmethod
    def from_env(cls) -> "Config":
        """Create Config from environment variables."""
        load_dotenv()
        # Log environment variables for debugging
        logging.info("Loading environment variables for Config:")
        required_vars = [
            "TEXT_MODEL", "FALLBACK_MODEL", "VISION_MODEL", "OLLAMA_URL",
            "KNOWLEDGE_BASE_DIR", "DATA_PROCESSING_DIR", "MEDIA_CACHE_DIR",
            "GIT_ENABLED", "GITHUB_TOKEN", "GITHUB_USER_NAME", "GITHUB_REPO_URL",
            "GITHUB_USER_EMAIL", "X_USERNAME", "X_PASSWORD", "X_BOOKMARKS_URL",
            "CATEGORIES_FILE", "BOOKMARKS_FILE", "PROCESSED_TWEETS_FILE",
            "TWEET_CACHE_FILE", "LOG_FILE", "UNPROCESSED_TWEETS_FILE", "LOG_DIR"
        ]
        missing_vars = [var for var in required_vars if not os.getenv(var)]
        if missing_vars:
            raise ConfigurationError(f"Missing required environment variables: {', '.join(missing_vars)}")
        for env_var in required_vars:
            logging.info(f"{env_var}: {os.getenv(env_var) if env_var not in ['X_PASSWORD', 'GITHUB_TOKEN'] else '***REDACTED***'}")
        return cls()