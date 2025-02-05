import os
from pathlib import Path
from dotenv import load_dotenv
from dataclasses import dataclass

# Load Environment Variables
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
    agent_prompt_categorization: str
    agent_prompt_reprocess: str
    log_level: str = "INFO"
    batch_size: int = 5
    max_retries: int = 3

    @classmethod
    def from_env(cls) -> 'Config':
        return cls(
            ollama_url=os.getenv("OLLAMA_URL"),
            vision_model=os.getenv("VISION_MODEL"),
            text_model=os.getenv("TEXT_MODEL"),
            github_token=os.getenv("GITHUB_TOKEN"),
            github_user_name=os.getenv("GITHUB_USER_NAME"),
            github_user_email=os.getenv("GITHUB_USER_EMAIL"),
            github_repo_url=os.getenv("GITHUB_REPO_URL"),
            knowledge_base_dir=Path("knowledge-base"),
            categories_file=Path("data/categories.json"),
            bookmarks_file=Path("data/bookmarks_links.txt"),
            processed_tweets_file=Path("data/processed_tweets.json"),
            agent_prompt_categorization=os.getenv("AGENT_PROMPT_CATEGORIZATION"),
            agent_prompt_reprocess=os.getenv("AGENT_PROMPT_REPROCESS"),
        )

    def verify(self):
        import dataclasses
        missing_vars = [field.name for field in dataclasses.fields(self) if not getattr(self, field.name)]
        if missing_vars:
            raise ValueError(f"Missing configuration values: {', '.join(missing_vars)}")

config = Config.from_env()
