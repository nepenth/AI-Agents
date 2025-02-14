import sys
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional
from pydantic_settings import BaseSettings
from pydantic import HttpUrl, Field, field_validator
from knowledge_base_agent.exceptions import ConfigurationError

def setup_logging(log_file: Path) -> None:
    """Setup logging configuration."""
    logging.basicConfig(
        filename=str(log_file),
        level=logging.DEBUG,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )

class Config(BaseSettings):
    # API endpoints and models
    ollama_url: HttpUrl = Field(..., alias="OLLAMA_URL")
    vision_model: str = Field("llava", alias="VISION_MODEL")
    text_model: str = Field("mistral", alias="TEXT_MODEL")
    
    # GitHub settings
    github_token: str = Field(..., alias="GITHUB_TOKEN")
    github_user_name: str = Field(..., alias="GITHUB_USER_NAME")
    github_repo_url: HttpUrl = Field(..., alias="GITHUB_REPO_URL")
    github_user_email: str = Field(..., alias="GITHUB_USER_EMAIL")
    
    # File paths
    data_processing_dir: Path = Field(default=Path("data"), alias="DATA_PROCESSING_DIR")
    knowledge_base_dir: Path = Field(default=Path("kb-generated"), alias="KNOWLEDGE_BASE_DIR")
    categories_file: Path = Field(default=Path("data/categories.json"), alias="CATEGORIES_FILE")
    bookmarks_file: Path = Field("data/bookmarks_links.txt", alias="BOOKMARKS_FILE")
    processed_tweets_file: Path = Field("data/processed_tweets.json", alias="PROCESSED_TWEETS_FILE")
    media_cache_dir: Path = Field(default=Path("data/media_cache"), alias="MEDIA_CACHE_DIR")
    tweet_cache_file: Path = Field("data/tweet_cache.json", alias="TWEET_CACHE_FILE")
    log_file: Path = Field("data/logs/kb_agent_{timestamp}.log", alias="LOG_FILE")
    unprocessed_tweets_file: Path = Field(default=Path("data/unprocessed_tweets.json"), alias="UNPROCESSED_TWEETS_FILE")
    log_dir: Path = Field(default=Path("logs"), alias="LOG_DIR")
    
    # X/Twitter credentials
    x_username: str = Field(..., alias="X_USERNAME")
    x_password: str = Field(..., alias="X_PASSWORD")
    x_bookmarks_url: HttpUrl = Field(..., alias="X_BOOKMARKS_URL")
    
    # Logging and performance
    log_level: str = Field(default="DEBUG", alias="LOG_LEVEL")
    max_pool_size: int = Field(default=1, alias="MAX_POOL_SIZE")
    rate_limit_requests: int = Field(default=100, alias="RATE_LIMIT_REQUESTS")
    rate_limit_period: int = Field(
        default=3600,
        alias="RATE_LIMIT_PERIOD",
        description="Rate limit period in seconds"
    )
    
    # Browser settings
    selenium_timeout: int = Field(default=30, alias="SELENIUM_TIMEOUT")
    selenium_headless: bool = Field(default=True, alias="SELENIUM_HEADLESS")
    
    # Content settings
    max_content_length: int = Field(default=5000, alias="MAX_CONTENT_LENGTH")
    summary_length: int = Field(default=280, alias="SUMMARY_LENGTH")
    
    # Request settings
    batch_size: int = Field(default=1, alias="BATCH_SIZE")
    max_retries: int = Field(default=5, alias="MAX_RETRIES")
    max_concurrent_requests: int = Field(default=1, alias="MAX_CONCURRENT_REQUESTS")
    request_timeout: int = Field(default=180, alias="REQUEST_TIMEOUT")
    retry_backoff: bool = Field(default=True, alias="RETRY_BACKOFF")
    
    @field_validator(
        "data_processing_dir", "knowledge_base_dir", "categories_file", "bookmarks_file",
        "processed_tweets_file", "media_cache_dir", "tweet_cache_file", "log_file", 
        mode='before'
    )
    def convert_to_path(cls, v):
        return v if isinstance(v, Path) else Path(v)
    
    @field_validator('rate_limit_period', mode='before')
    def validate_rate_limit_period(cls, v):
        logging.debug(f"Raw rate_limit_period value: '{v}', type: {type(v)}")
        if isinstance(v, str):
            # Remove any inline comments (split on '#' and trim whitespace)
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
        """Configure logging system."""
        log_dir = self.data_processing_dir / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        log_file = log_dir / f"kb_agent_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
        
        logging.basicConfig(
            level=self.log_level,
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            handlers=[logging.FileHandler(log_file)]
        )
        
        # Add custom success level
        logging.addLevelName(25, "SUCCESS")
        def success(self, message, *args, **kwargs):
            self._log(25, message, args, **kwargs)
        logging.Logger.success = success
