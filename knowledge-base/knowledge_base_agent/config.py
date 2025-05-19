import sys
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional
from pydantic_settings import BaseSettings
from pydantic import HttpUrl, Field, field_validator, model_validator
from knowledge_base_agent.exceptions import ConfigurationError
import os
from dotenv import load_dotenv

# This will be set by main.py or web.py at startup
PROJECT_ROOT: Optional[Path] = None

def get_project_root() -> Path:
    """Get the project root. Must be set before Config is fully initialized if paths are relative."""
    if PROJECT_ROOT is None:
        # Fallback if not set explicitly, assuming script is run from project root or similar
        # A more robust approach is to set it explicitly at app start.
        # For now, try to infer from current file's location if running within the agent structure
        try:
            # Assuming config.py is in knowledge_base_agent/
            # Then project root is parent of knowledge_base_agent/
             inferred_root = Path(__file__).resolve().parent.parent
             if (inferred_root / ".env").exists() or (inferred_root / "knowledge_base_agent").is_dir():
                logging.debug(f"Inferred project root: {inferred_root}")
                return inferred_root
        except Exception:
            pass # Fall through to CWD
        
        # Default to current working directory if PROJECT_ROOT hasn't been set
        # This requires running scripts from the project's root directory.
        logging.warning("PROJECT_ROOT not explicitly set. Defaulting to CWD. Ensure scripts are run from project root.")
        return Path(os.getcwd()).resolve()
    return PROJECT_ROOT

class Config(BaseSettings):
    project_root: Path = Field(default_factory=get_project_root, validate_default=True)

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
    
    # File paths (will be resolved to absolute paths)
    # These should be defined as relative paths in .env or defaults
    data_processing_dir_rel: Path = Field(..., alias="DATA_PROCESSING_DIR")
    knowledge_base_dir_rel: Path = Field(..., alias="KNOWLEDGE_BASE_DIR")
    categories_file_rel: Path = Field(..., alias="CATEGORIES_FILE")
    bookmarks_file_rel: Path = Field(default_factory=lambda: Path("data/tweet_bookmarks.json"), alias="BOOKMARKS_FILE")
    processed_tweets_file_rel: Path = Field(..., alias="PROCESSED_TWEETS_FILE")
    media_cache_dir_rel: Path = Field(..., alias="MEDIA_CACHE_DIR")
    tweet_cache_file_rel: Path = Field(..., alias="TWEET_CACHE_FILE")
    log_file_rel: Path = Field(..., alias="LOG_FILE") # Can include {timestamp}
    unprocessed_tweets_file_rel: Path = Field(..., alias="UNPROCESSED_TWEETS_FILE")
    log_dir_rel: Path = Field(..., alias="LOG_DIR")

    # Resolved absolute paths (properties)
    data_processing_dir: Path
    knowledge_base_dir: Path
    categories_file: Path
    bookmarks_file: Path
    processed_tweets_file: Path
    media_cache_dir: Path
    tweet_cache_file: Path
    log_file: Path
    unprocessed_tweets_file: Path
    log_dir: Path
    
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
    enable_gpu_stats_monitoring: bool = Field(False, alias="ENABLE_GPU_STATS_MONITORING", description="Enable periodic GPU statistics monitoring")
    gpu_stats_interval: int = Field(5, alias="GPU_STATS_INTERVAL", description="Interval in seconds for GPU stats collection")
    
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
    process_videos: bool = Field(True, alias="PROCESS_VIDEOS", description="Whether to process video files with the vision model")
    
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
    
    # New attribute for force_recache
    force_recache: bool = Field(False, alias="FORCE_RECACHE_TWEETS")
    ollama_supports_json_mode: bool = Field(False, alias="OLLAMA_SUPPORTS_JSON_MODE", description="Whether the Ollama instance supports JSON mode for formatted output.")

    @model_validator(mode='after')
    def resolve_paths(cls, values: 'Config') -> 'Config':
        root = values.project_root
        
        values.data_processing_dir = (root / values.data_processing_dir_rel).resolve()
        values.knowledge_base_dir = (root / values.knowledge_base_dir_rel).resolve()
        values.categories_file = (root / values.categories_file_rel).resolve()
        values.bookmarks_file = (root / values.bookmarks_file_rel).resolve()
        values.processed_tweets_file = (root / values.processed_tweets_file_rel).resolve()
        values.media_cache_dir = (root / values.media_cache_dir_rel).resolve()
        values.tweet_cache_file = (root / values.tweet_cache_file_rel).resolve()
        
        # Handle timestamp in log_file name before resolving
        log_file_str = str(values.log_file_rel)
        if '{timestamp}' in log_file_str:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            log_file_str = log_file_str.replace('{timestamp}', timestamp)
        
        values.log_file = (root / Path(log_file_str)).resolve()
        values.unprocessed_tweets_file = (root / values.unprocessed_tweets_file_rel).resolve()
        values.log_dir = (root / values.log_dir_rel).resolve()
        
        # Ensure directories for these resolved absolute paths
        # This replaces the old field_validator for paths
        paths_to_ensure_parent_exists = [
            values.data_processing_dir, values.knowledge_base_dir, values.categories_file,
            values.bookmarks_file, values.processed_tweets_file, values.media_cache_dir,
            values.tweet_cache_file, values.log_file, values.unprocessed_tweets_file, values.log_dir
        ]
        for p in paths_to_ensure_parent_exists:
            p.parent.mkdir(parents=True, exist_ok=True)
            
        return values
    
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

    # This method is still useful to ensure the top-level directories themselves exist,
    # not just their parents. Called after path resolution.
    def ensure_directories(self) -> None:
        """Ensure all required directories exist (after paths are resolved)."""
        self.knowledge_base_dir.mkdir(parents=True, exist_ok=True)
        self.data_processing_dir.mkdir(parents=True, exist_ok=True)
        self.media_cache_dir.mkdir(parents=True, exist_ok=True)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        # Parent dirs for files like categories_file, bookmarks_file etc.,
        # are handled in resolve_paths or should already exist if they are under data_dir.

    # init_log_file is effectively replaced by logic in resolve_paths for log_file
    # def init_log_file(self) -> None:
    #     """Initialize the log file path with the current timestamp if needed."""
    #     if '{timestamp}' in str(self.log_file): # self.log_file is now absolute
    #         # This logic is now handled during path resolution
    #         pass
    #     self.log_file.parent.mkdir(parents=True, exist_ok=True)


    def setup_logging(self) -> None:
        """Configure logging with proper formatting for long messages."""
        # self.log_file is already resolved and parent dir created by resolve_paths
        
        root_logger = logging.getLogger()
        root_logger.handlers.clear()
        
        file_handler = logging.FileHandler(self.log_file, mode='a', encoding='utf-8')
        file_handler.setLevel(logging.DEBUG) # Use self.log_level here? Pydantic usually converts string to Enum/correct type
        file_formatter = logging.Formatter(
            '%(asctime)s - %(levelname)s - %(message).1000s', # Truncate long messages
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        file_handler.setFormatter(file_formatter)
        
        console_handler = logging.StreamHandler()
        # Use self.log_level for console handler too
        console_handler.setLevel(self.log_level.upper() if isinstance(self.log_level, str) else logging.INFO) 
        console_formatter = logging.Formatter('%(levelname)s - %(message)s')
        console_handler.setFormatter(console_formatter)
        
        root_logger.setLevel(self.log_level.upper() if isinstance(self.log_level, str) else logging.DEBUG)
        root_logger.addHandler(file_handler)
        root_logger.addHandler(console_handler)
        
        logging.getLogger('git.cmd').setLevel(logging.INFO)
        logging.getLogger('git.util').setLevel(logging.INFO)
        logging.getLogger('httpx').setLevel(logging.WARNING)
        logging.getLogger('playwright').setLevel(logging.WARNING) # Added playwright
        
        logging.debug("Logging configured with file: %s and level: %s", self.log_file, self.log_level)

    @classmethod
    def from_env(cls, project_root_path: Optional[Path] = None) -> "Config":
        """Create Config from environment variables."""
        global PROJECT_ROOT
        if project_root_path:
            PROJECT_ROOT = project_root_path
            logging.info(f"PROJECT_ROOT explicitly set to: {PROJECT_ROOT}")
        else:
            # Ensure get_project_root is called to infer if not provided
            # This will use the inferred root if PROJECT_ROOT is still None
            if PROJECT_ROOT is None:
                PROJECT_ROOT = get_project_root() # Infer if not set
            logging.info(f"Using project_root: {PROJECT_ROOT}")

        load_dotenv(dotenv_path= Path(PROJECT_ROOT) / ".env" if PROJECT_ROOT else ".env")
        
        # Logging before full config setup might be basic
        logging.info("Loading environment variables for Config...")
        
        # Construct with project_root passed explicitly to avoid factory if already known
        # Pydantic will use the default_factory for project_root if not passed.
        # If project_root_path is passed here, it should directly initialize the field.
        
        instance = cls(project_root=PROJECT_ROOT) # Pass the determined project_root
        
        # The resolve_paths model_validator will handle resolving and creating directories
        # instance.ensure_directories() # Call after paths are resolved

        return instance

    def get_relative_path(self, absolute_path: Path) -> Path:
        """Converts an absolute path to a path relative to the project root."""
        if not absolute_path.is_absolute():
            raise ValueError(f"Path {absolute_path} is not absolute, cannot make it relative to project root.")
        return absolute_path.relative_to(self.project_root)

    def resolve_path_from_project_root(self, relative_path: Path | str) -> Path:
        """Resolves a path relative to the project root to an absolute path."""
        return (self.project_root / relative_path).resolve()

async def load_config(project_root_override: Optional[Path] = None) -> Config:
    """
    Loads environment variables, initializes the Config object, 
    sets up directories, and configures logging.
    PROJECT_ROOT is crucial and needs to be determined correctly.
    """
    global PROJECT_ROOT
    
    determined_project_root: Optional[Path] = None

    if project_root_override:
        determined_project_root = project_root_override.resolve()
        logging.info(f"Using provided project root override: {determined_project_root}")
    else:
        # Try to determine from environment variable first
        env_project_root = os.getenv("KNOWLEDGE_BASE_PROJECT_ROOT")
        if env_project_root:
            determined_project_root = Path(env_project_root).resolve()
            logging.info(f"Using KNOWLEDGE_BASE_PROJECT_ROOT env var: {determined_project_root}")
        else:
            # Fallback to inferring (e.g., for local dev without .env in parent or specific run contexts)
            # This inference is a bit fragile; explicit setting is better.
            try:
                # Assuming config.py is in knowledge_base_agent/
                # Then project root is parent of knowledge_base_agent/
                inferred_root = Path(__file__).resolve().parent.parent
                # Check for a common marker like .env or the main package folder
                if (inferred_root / ".env").exists() or \
                   (inferred_root / "knowledge_base_agent").is_dir() or \
                   (inferred_root / "pyproject.toml").exists(): # Added pyproject.toml as another marker
                    determined_project_root = inferred_root
                    logging.info(f"Inferred project root: {determined_project_root}")
                else: # Last resort CWD
                    determined_project_root = Path(os.getcwd()).resolve()
                    logging.warning(f"Could not reliably infer project root. Defaulting to CWD: {determined_project_root}. Ensure scripts are run from project root or KNOWLEDGE_BASE_PROJECT_ROOT is set.")
            except Exception as e:
                logging.error(f"Error during project root inference: {e}. Defaulting to CWD.")
                determined_project_root = Path(os.getcwd()).resolve()

    if not determined_project_root:
        # This should not happen if logic above is sound, but as a safeguard
        raise ConfigurationError("Project root could not be determined. Please set KNOWLEDGE_BASE_PROJECT_ROOT environment variable or run from the project's root directory.")

    PROJECT_ROOT = determined_project_root
    logging.info(f"Final PROJECT_ROOT set to: {PROJECT_ROOT}")

    # Load .env file from the determined project root
    dotenv_path = PROJECT_ROOT / ".env"
    if dotenv_path.exists():
        load_dotenv(dotenv_path=dotenv_path, override=True)
        logging.info(f"Loaded .env file from: {dotenv_path}")
    else:
        logging.warning(f".env file not found at {dotenv_path}. Relying on environment variables or defaults.")

    try:
        # Pydantic will use PROJECT_ROOT via get_project_root factory for the project_root field
        # if it's not explicitly passed or found in env vars for `project_root` itself.
        # The Config model will handle path resolutions based on this.
        config_instance = Config() 
        
        # Ensure directories (like log_dir, data_dir etc.) are created based on resolved paths
        config_instance.ensure_directories()
        
        # Setup logging based on the loaded configuration
        config_instance.setup_logging() 
        
        logging.info("Configuration loaded and logging configured successfully.")
        return config_instance
    except Exception as e:
        logging.exception("Failed to initialize Config object or setup.")
        raise ConfigurationError(f"Configuration loading failed: {e}") from e