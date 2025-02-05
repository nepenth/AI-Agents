import os
import json
from dataclasses import dataclass
from pathlib import Path
from dotenv import load_dotenv

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
            log_level=os.getenv("LOG_LEVEL", "INFO"),
            batch_size=int(os.getenv("BATCH_SIZE", "5")),
            max_retries=int(os.getenv("MAX_RETRIES", "3"))
        )

    @classmethod
    def from_json(cls, json_file: Path) -> 'Config':
        with json_file.open('r', encoding='utf-8') as f:
            data = json.load(f)
        return cls(
            ollama_url=data.get("ollama_url"),
            vision_model=data.get("vision_model"),
            text_model=data.get("text_model"),
            github_token=data.get("github_token"),
            github_user_name=data.get("github_user_name"),
            github_user_email=data.get("github_user_email"),
            github_repo_url=data.get("github_repo_url"),
            knowledge_base_dir=Path(data.get("knowledge_base_dir", "knowledge-base")),
            categories_file=Path(data.get("categories_file", "data/categories.json")),
            bookmarks_file=Path(data.get("bookmarks_file", "data/bookmarks_links.txt")),
            processed_tweets_file=Path(data.get("processed_tweets_file", "data/processed_tweets.json")),
            log_level=data.get("log_level", "INFO"),
            batch_size=int(data.get("batch_size", 5)),
            max_retries=int(data.get("max_retries", 3))
        )

    def verify(self):
        import dataclasses
        missing_vars = []
        for field in dataclasses.fields(self):
            if field.name not in ['log_level', 'batch_size', 'max_retries'] and not getattr(self, field.name):
                missing_vars.append(field.name)
        if missing_vars:
            raise ValueError(f"Missing configuration values: {', '.join(missing_vars)}")
