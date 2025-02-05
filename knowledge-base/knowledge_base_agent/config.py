import os
import json
from dataclasses import dataclass
from pathlib import Path
from dotenv import load_dotenv

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
            max_retries=int(os.getenv("MAX_RETRIES", "3"))
        )

    def verify(self):
        import dataclasses
        missing_vars = []
        for field in dataclasses.fields(self):
            if field.name not in ['log_level', 'batch_size', 'max_retries'] and not getattr(self, field.name):
                missing_vars.append(field.name)
        if missing_vars:
            raise ValueError(f"Missing configuration values: {', '.join(missing_vars)}")
