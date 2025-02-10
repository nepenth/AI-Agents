import os
import json
from dataclasses import dataclass
from pathlib import Path
from dotenv import load_dotenv
import logging
import sys
from datetime import datetime
from pydantic import BaseModel, validator
from typing import Optional

load_dotenv()

@dataclass
class Config:
    ollama_url: str
    vision_model: str
    text_model: str
    github_token: str
    github_user_name: str
    github_user_email: str
    github_repo_url: str
    knowledge_base_dir: Path
    categories_file: Path
    bookmarks_file: Path
    processed_tweets_file: Path
    media_cache_dir: Path
    log_level: str = "INFO"
    batch_size: int = 5
    max_retries: int = 3
    max_concurrent_requests: int = 5
    retry_attempts: int = 3
    cache_dir: Optional[Path] = None
    log_dir: Optional[Path] = None
    request_timeout: int = 60
    concurrent_downloads: int = 5
    image_quality: str = "high"
    cache_expiry: int = 86400  # 24 hours in seconds

    @classmethod
    def from_env(cls) -> 'Config':
        load_dotenv()
        return cls(
            ollama_url=os.getenv("OLLAMA_URL"),
            vision_model=os.getenv("VISION_MODEL"),
            text_model=os.getenv("TEXT_MODEL"),
            github_token=os.getenv("GITHUB_TOKEN"),
            github_user_name=os.getenv("GITHUB_USER_NAME"),
            github_user_email=os.getenv("GITHUB_USER_EMAIL"),
            github_repo_url=os.getenv("GITHUB_REPO_URL"),
            knowledge_base_dir=Path(os.getenv("KNOWLEDGE_BASE_DIR", "knowledge-base")),
            categories_file=Path(os.getenv("CATEGORIES_FILE", "data/categories.json")),
            bookmarks_file=Path(os.getenv("BOOKMARKS_FILE", "data/bookmarks_links.txt")),
            processed_tweets_file=Path(os.getenv("PROCESSED_TWEETS_FILE", "data/processed_tweets.json")),
            media_cache_dir=Path(os.getenv("MEDIA_CACHE_DIR", "data/media_cache")),
            log_level=os.getenv("LOG_LEVEL", "INFO"),
            batch_size=int(os.getenv("BATCH_SIZE", "5")),
            max_retries=int(os.getenv("MAX_RETRIES", "3")),
            max_concurrent_requests=int(os.getenv("MAX_CONCURRENT_REQUESTS", "5")),
            retry_attempts=int(os.getenv("RETRY_ATTEMPTS", "3")),
            cache_dir=Path(os.getenv("CACHE_DIR")) if os.getenv("CACHE_DIR") else None,
            log_dir=Path(os.getenv("LOG_DIR")) if os.getenv("LOG_DIR") else None,
            request_timeout=int(os.getenv("REQUEST_TIMEOUT", "60")),
            concurrent_downloads=int(os.getenv("CONCURRENT_DOWNLOADS", "5")),
            image_quality=os.getenv("IMAGE_QUALITY", "high"),
            cache_expiry=int(os.getenv("CACHE_EXPIRY", "86400"))
        )

    def verify(self):
        import dataclasses
        missing_vars = []
        for field in dataclasses.fields(self):
            if field.name not in ['log_level', 'batch_size', 'max_retries', 'max_concurrent_requests', 'retry_attempts', 'cache_dir', 'log_dir'] and not getattr(self, field.name):
                missing_vars.append(field.name)
        if missing_vars:
            raise ValueError(f"Missing configuration values: {', '.join(missing_vars)}")

    def validate(self) -> None:
        if self.request_timeout <= 0:
            raise ValueError("request_timeout must be positive")
        if self.max_retries < 0:
            raise ValueError("max_retries cannot be negative")

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
