import os
from pathlib import Path
from typing import Optional

from pydantic import (
    BaseModel,
    DirectoryPath,
    EmailStr,
    Field,
    HttpUrl,
    SecretStr,
    ValidationError,
    field_validator,
    model_validator,
    AnyHttpUrl,
    validator,
)
from pydantic_settings import BaseSettings, SettingsConfigDict


class Config(BaseSettings):
    """
    Agent Configuration Model loaded from .env file and environment variables.
    """

    # --- Ollama Configuration ---
    ollama_url: HttpUrl = Field(..., description="URL of the Ollama instance")
    text_model: str = Field(..., description="Primary LLM for text generation")
    fallback_model: str = Field(..., description="Fallback LLM")
    vision_model: str = Field(..., description="Vision LLM for image descriptions")
    ollama_request_timeout_seconds: int = Field(default=60, description="Timeout for Ollama API requests in seconds (connect, read, write).")
    # ollama_timeout: int = Field(300, description="Timeout for Ollama requests in seconds")

    # --- Filesystem Paths ---
    # We resolve paths relative to the project root (assuming .env is there)
    # or allow absolute paths.
    project_root: Path = Path(__file__).parent.parent.parent # Assumes config.py is in knowledge_base_agent/
    knowledge_base_dir: Path = Field(default="./kb-generated", description="Base directory for generated knowledge base items")
    data_dir: Path = Field(default="./data", description="Directory for storing intermediate data files")
    log_dir: Path = Field(default="./logs", description="Directory for storing log files")

    # --- Playwright / X Bookmarks ---
    # fetch_bookmarks_enabled: bool = Field(False, description="Enable bookmark fetching") # REMOVED
    x_username: Optional[str] = Field(None, description="Twitter/X username")
    x_password: Optional[SecretStr] = Field(None, description="Twitter/X password")
    x_email: Optional[EmailStr] = Field(None, description="X/Twitter login email (required by twscrape).") # ADDED x_email
    x_bookmarks_url: Optional[HttpUrl] = Field(None, description="Direct URL to X Bookmarks page")

    # --- Git Synchronization ---
    git_enabled: bool = Field(False, description="Enable pushing kb-generated to Git repository")
    github_token: Optional[SecretStr] = Field(None, description="GitHub Personal Access Token")
    github_user_name: Optional[str] = Field(None, description="GitHub username")
    github_user_email: Optional[EmailStr] = Field(None, description="Email associated with GitHub account")
    github_repo_url: Optional[str] = Field(None, description="SSH or HTTPS URL of the target Git repository") # Could be HttpUrl or specific Git URL type if needed

    # --- Web Server Configuration ---
    flask_secret_key: SecretStr = Field(..., validation_alias='FLASK_SECRET_KEY')
    database_url: str = Field(..., validation_alias='DATABASE_URL') # Keep as string for SQLAlchemy
    flask_run_port: int = Field(5000, validation_alias='FLASK_RUN_PORT')

    # --- Agent Behavior ---
    force_recache: bool = Field(False, description="Force re-caching of all tweets")
    # playwright_timeout: int = Field(120, description="Timeout for Playwright operations in seconds")
    # log_level: str = Field("INFO", description="Logging level") # Usually handled by log_setup

    # --- Concurrency Settings ---
    max_concurrent_llm_tasks: int = Field(default=2, description="Max concurrent LLM tasks")
    max_concurrent_caching_tasks: int = Field(default=5, description="Max concurrent twscrape/caching tasks")
    max_concurrent_db_sync_tasks: int = Field(default=3, description="Max concurrent database synchronization tasks")

    # --- Playwright Client Configuration ---
    playwright_login_timeout_ms: int = Field(default=90000, validation_alias='PLAYWRIGHT_LOGIN_TIMEOUT_MS')
    playwright_nav_timeout_ms: int = Field(default=90000, validation_alias='PLAYWRIGHT_NAV_TIMEOUT_MS')
    playwright_action_timeout_ms: int = Field(default=30000, validation_alias='PLAYWRIGHT_ACTION_TIMEOUT_MS')
    playwright_scroll_delay_ms: int = Field(default=5000, validation_alias='PLAYWRIGHT_SCROLL_DELAY_MS')
    playwright_max_scroll_attempts: int = Field(default=100, validation_alias='PLAYWRIGHT_MAX_SCROLL_ATTEMPTS')
    playwright_max_no_change_scrolls: int = Field(default=3, validation_alias='PLAYWRIGHT_MAX_NO_CHANGE_SCROLLS')
    playwright_use_auth_state: bool = Field(default=False, validation_alias='PLAYWRIGHT_USE_AUTH_STATE')
    playwright_auth_state_filename: str = Field(default="playwright_auth_state.json", validation_alias='PLAYWRIGHT_AUTH_STATE_FILENAME')

    # --- Media Download Retry Configuration ---
    media_download_max_retries: int = Field(default=3, validation_alias='MEDIA_DOWNLOAD_MAX_RETRIES', description="Maximum number of retries for media downloads")
    media_download_retry_delay_ms: int = Field(default=2000, validation_alias='MEDIA_DOWNLOAD_RETRY_DELAY_MS', description="Delay between media download retries in milliseconds")
    media_max_size_bytes: int = Field(default=50 * 1024 * 1024, validation_alias='MEDIA_MAX_SIZE_BYTES', description="Maximum size for a single media file download in bytes (default: 50MB)")

    # --- Pydantic Settings Configuration ---
    model_config = SettingsConfigDict(
        env_file=".env",          # Load from .env file
        env_file_encoding="utf-8",
        extra="ignore",           # Ignore extra fields found in the environment
        case_sensitive=False,     # Environment variable names are case-insensitive
    )

    # --- Custom Validators ---

    @field_validator("knowledge_base_dir", "data_dir", "log_dir", mode="before")
    @classmethod
    def make_path_absolute(cls, v: str | Path, info) -> Path:
        """Ensure specified directory paths are absolute or relative to project root."""
        if isinstance(v, str):
            path = Path(v)
        else:
            path = v

        if not path.is_absolute():
            # Assuming .env is at project root, which is parent of knowledge_base_agent/
            project_root = Path(__file__).parent.parent
            return (project_root / path).resolve()
        return path.resolve()

    @validator("data_dir", "log_dir", "knowledge_base_dir", pre=True, always=True)
    def make_paths_absolute_and_resolve(cls, v: str | Path) -> Path:
        """Ensure specified directory paths are absolute or resolved relative to project root."""
        if isinstance(v, str):
            path = Path(v)
        else:
            path = v # Already a Path object

        if not path.is_absolute():
            # Assuming .env is at project root, which is parent of knowledge_base_agent/
            # This path resolution needs to be robust.
            # If Config class is in knowledge_base_agent/config.py,
            # then Path(__file__).parent is knowledge_base_agent/
            # then Path(__file__).parent.parent is the project root.
            project_root = Path(__file__).resolve().parent.parent
            path = (project_root / path).resolve()
        else:
            path = path.resolve()
        
        # Ensure the directory exists, creating if necessary
        # path.mkdir(parents=True, exist_ok=True) # Moved to main_cli and main_web for strategic creation
        return path

    @model_validator(mode="after")
    def check_conditional_requirements(self) -> "Config":
        """Validate fields that are required based on the value of other fields."""
        # Check X/Twitter credential completeness if any one of them is provided,
        # as they are typically used together for bookmark fetching.
        x_creds_provided = [self.x_username, self.x_password, self.x_email, self.x_bookmarks_url]
        if any(x_creds_provided) and not all(x_creds_provided):
            missing_x_fields = []
            if not self.x_username: missing_x_fields.append("X_USERNAME")
            if not self.x_password: missing_x_fields.append("X_PASSWORD")
            if not self.x_email: missing_x_fields.append("X_EMAIL")
            if not self.x_bookmarks_url: missing_x_fields.append("X_BOOKMARKS_URL")
            raise ValueError(
                f"If any X/Twitter credentials (username, password, email, bookmarks_url) are provided, all must be set. "
                f"Missing: {', '.join(missing_x_fields)}"
            )

        if self.git_enabled:
            if not self.github_token:
                raise ValueError("GITHUB_TOKEN must be set if GIT_ENABLED is true.")
            if not self.github_user_name:
                raise ValueError("GITHUB_USER_NAME must be set if GIT_ENABLED is true.")
            if not self.github_user_email:
                raise ValueError("GITHUB_USER_EMAIL must be set if GIT_ENABLED is true.")
            if not self.github_repo_url:
                raise ValueError("GITHUB_REPO_URL must be set if GIT_ENABLED is true.")

        # Ensure directories exist after resolving paths
        # It might be better to create these directories at runtime if they don't exist,
        # rather than failing config load, depending on desired behavior.
        # For now, let's just check they are valid paths after resolution.
        # os.makedirs(self.data_dir, exist_ok=True)
        # os.makedirs(self.log_dir, exist_ok=True)
        # os.makedirs(self.knowledge_base_dir, exist_ok=True)

        return self

def load_config() -> Config:
    """Loads the application configuration from environment variables and .env file."""
    try:
        config = Config()
        print("Config object being returned by load_config:", config.model_dump_json(indent=2))
        # You could add a log message here confirming successful load
        # print(f"Configuration loaded successfully from {config.model_config['env_file']}")
        return config
    except ValidationError as e:
        print(f"Error loading configuration: {e}")
        # Potentially raise a custom configuration error or exit
        raise SystemExit("Configuration validation failed.") from e

# Example usage (optional, for testing)
if __name__ == "__main__":
    # Create a dummy .env file for testing if it doesn't exist
    if not Path(".env").exists():
         print("Creating dummy .env file for testing...")
         Path(".env").write_text(
             """
 OLLAMA_URL=http://localhost:11434
 TEXT_MODEL=mistral:latest
 FALLBACK_MODEL=llama3:latest
 VISION_MODEL=llava:latest
 KNOWLEDGE_BASE_DIR=./kb-generated-test
 DATA_DIR=./data-test
 LOG_DIR=./logs-test
 FETCH_BOOKMARKS_ENABLED=false
 GIT_ENABLED=false
 FLASK_SECRET_KEY='test-secret-key'
 DATABASE_URL='sqlite:///./data-test/test.db'
 FLASK_RUN_PORT=5000
 """
         )

    try:
        loaded_config = load_config()
        print("Configuration loaded successfully!")
        print("Ollama URL:", loaded_config.ollama_url)
        print("KB Dir:", loaded_config.knowledge_base_dir)
        print("Data Dir:", loaded_config.data_dir)
        print("Log Dir:", loaded_config.log_dir)
        print("Git Enabled:", loaded_config.git_enabled)
        # Example of accessing a secret
        if loaded_config.flask_secret_key:
            print("Flask Secret Key (masked):", loaded_config.flask_secret_key.get_secret_value())
        # Clean up dummy files if created
        if Path("./kb-generated-test").exists():
             Path("./kb-generated-test").rmdir()
        if Path("./data-test").exists():
             import shutil
             shutil.rmtree("./data-test")
        if Path("./logs-test").exists():
             Path("./logs-test").rmdir()
        if Path(".env").read_text().strip().endswith("test.db'"): # basic check if it's the dummy file
             Path(".env").unlink()


    except SystemExit as err:
        print(err)
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
