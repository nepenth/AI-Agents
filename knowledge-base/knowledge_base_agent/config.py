import sys
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional, List
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
    embedding_model: str = Field(..., alias="EMBEDDING_MODEL", description="The model to use for generating embeddings.")
    chat_model: Optional[str] = Field(None, alias="CHAT_MODEL", description="Dedicated model for chat, defaults to text_model if not set")
    available_chat_models: List[str] = Field([], alias="AVAILABLE_CHAT_MODELS", description="JSON array of chat models available for selection in the UI.")
    fallback_model: str = Field(..., alias="FALLBACK_MODEL")
    categorization_model: str = Field("", alias="CATEGORIZATION_MODEL", description="Dedicated model for AI categorization, defaults to text_model if not set")
    gpu_total_memory: int = Field(0, alias="GPU_TOTAL_MEM", description="Total GPU memory available in MB for parallelization decisions")
    num_gpus_available: int = Field(1, alias="NUM_GPUS_AVAILABLE", description="Number of GPUs available for parallel processing")
    text_model_thinking: bool = Field(False, alias="TEXT_MODEL_THINKING", description="Whether the text model supports reasoning/thinking subroutines (e.g., Cogito)")
    enable_categorization_thinking: bool = Field(False, alias="ENABLE_CATEGORIZATION_THINKING", description="Whether to use a specific thinking model for categorization and synthesis tasks")
    categorization_thinking_model_name: Optional[str] = Field(None, alias="CATEGORIZATION_THINKING_MODEL_NAME", description="The name of the thinking model to use for categorization/synthesis if enable_categorization_thinking is true")
    
    # New fields specifically for Synthesis model configuration
    synthesis_model: Optional[str] = Field(None, alias="SYNTHESIS_MODEL", description="Dedicated model for synthesis generation, defaults to text_model if not set")
    enable_synthesis_thinking: bool = Field(False, alias="ENABLE_SYNTHESIS_THINKING", description="Whether to use a specific thinking model for synthesis tasks")
    synthesis_thinking_model_name: Optional[str] = Field(None, alias="SYNTHESIS_THINKING_MODEL_NAME", description="The name of the thinking model to use for synthesis if enable_synthesis_thinking is true")
    synthesis_min_sub_syntheses: int = Field(2, alias="SYNTHESIS_MIN_SUB_SYNTHESES", description="Minimum number of subcategory syntheses required before generating a main category synthesis")
    
    # GitHub settings
    github_token: str = Field(..., alias="GITHUB_TOKEN", min_length=1)
    github_user_name: str = Field(..., alias="GITHUB_USER_NAME", min_length=1)
    github_repo_url: HttpUrl = Field(..., alias="GITHUB_REPO_URL")
    github_user_email: str = Field(..., alias="GITHUB_USER_EMAIL", min_length=1)
    # File paths (will be resolved to absolute paths)
    # These should be defined as relative paths in .env or defaults
    data_processing_dir_rel: Path = Field(..., alias="DATA_PROCESSING_DIR")
    knowledge_base_dir_rel: Path = Field(..., alias="KNOWLEDGE_BASE_DIR")
    categories_file_rel: Path = Field(..., alias="CATEGORIES_FILE")
    bookmarks_file_rel: Path = Field(default_factory=lambda: Path("data/tweet_bookmarks.json"), alias="BOOKMARKS_FILE")
    processed_tweets_file_rel: Path = Field(..., alias="PROCESSED_TWEETS_FILE")
    media_cache_dir_rel: Path = Field(..., alias="MEDIA_CACHE_DIR")
    tweet_cache_file_rel: Path = Field(..., alias="TWEET_CACHE_FILE")
    log_file_rel: Path = Field(default_factory=lambda: Path("logs/agent_{timestamp}.log"), alias="LOG_FILE") # Can include {timestamp}
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
    log_format: str = Field("%(asctime)s - %(levelname)s - %(message)s", alias="LOG_FORMAT")
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
    
    # X/Twitter specific settings
    x_login_timeout: int = Field(60, alias="X_LOGIN_TIMEOUT", description="Timeout in seconds for X/Twitter login process")
    
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
    def resolve_paths(self):
        """Resolve relative paths to absolute paths based on project_root."""
        
        # Ensure that the project_root has been set by something valid
        if self.project_root is None:
            logging.error("Project root is None. This should not happen as default_factory should be called.")
            raise ConfigurationError("Project root is None.")
        
        self.data_processing_dir = (self.project_root / self.data_processing_dir_rel).resolve()
        self.knowledge_base_dir = (self.project_root / self.knowledge_base_dir_rel).resolve()
        self.categories_file = (self.project_root / self.categories_file_rel).resolve()
        self.bookmarks_file = (self.project_root / self.bookmarks_file_rel).resolve()
        self.processed_tweets_file = (self.project_root / self.processed_tweets_file_rel).resolve()
        self.unprocessed_tweets_file = (self.project_root / self.unprocessed_tweets_file_rel).resolve()
        self.media_cache_dir = (self.project_root / self.media_cache_dir_rel).resolve()
        self.tweet_cache_file = (self.project_root / self.tweet_cache_file_rel).resolve()
        
        # Handle timestamp in log_file name before resolving
        log_file_str = str(self.log_file_rel)
        if '{timestamp}' in log_file_str:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            log_file_str = log_file_str.replace('{timestamp}', timestamp)
        
        self.log_file = (self.project_root / Path(log_file_str)).resolve()
        self.log_dir = (self.project_root / self.log_dir_rel).resolve()
        
        # Ensure directories for these resolved absolute paths
        # This replaces the old field_validator for paths
        paths_to_ensure_parent_exists = [
            self.data_processing_dir, self.knowledge_base_dir, self.categories_file,
            self.bookmarks_file, self.processed_tweets_file, self.media_cache_dir,
            self.tweet_cache_file, self.log_file, self.unprocessed_tweets_file, self.log_dir
        ]
        for p in paths_to_ensure_parent_exists:
            p.parent.mkdir(parents=True, exist_ok=True)
            
        # If categorization_model is empty, use text_model
        if not self.categorization_model:
            self.categorization_model = self.text_model
            logging.info(f"No specific CATEGORIZATION_MODEL set. Using TEXT_MODEL ({self.text_model}) for categorization.")
        
        # If chat_model is empty, use text_model
        if not self.chat_model:
            self.chat_model = self.text_model
            logging.info(f"No specific CHAT_MODEL set. Using TEXT_MODEL ({self.text_model}) for chat.")
        
        # If synthesis_model is empty, use text_model
        if not self.synthesis_model:
            self.synthesis_model = self.text_model
            logging.info(f"No specific SYNTHESIS_MODEL set. Using TEXT_MODEL ({self.text_model}) for synthesis.")
        
        # Log GPU memory information
        if self.gpu_total_memory > 0:
            logging.info(f"GPU memory configuration: {self.gpu_total_memory}MB available for parallel processing")
        else:
            logging.warning("No GPU memory information available (GPU_TOTAL_MEM=0 or not set). Parallel LLM processing will be limited.")
        
        # Validate Git configuration - now always validated since pipeline allows skipping via UI
        required_git_fields = [
            ('github_token', 'GITHUB_TOKEN'),
            ('github_user_name', 'GITHUB_USER_NAME'), 
            ('github_user_email', 'GITHUB_USER_EMAIL'),
            ('github_repo_url', 'GITHUB_REPO_URL')
        ]
        
        missing_fields = []
        for field_name, env_name in required_git_fields:
            field_value = getattr(self, field_name, None)
            if not field_value or (isinstance(field_value, str) and not field_value.strip()):
                missing_fields.append(env_name)
        
        if missing_fields:
            missing_list = ', '.join(missing_fields)
            error_msg = f"Git sync configuration incomplete - required environment variables are missing or empty: {missing_list}"
            logging.error(error_msg)
            raise ConfigurationError(error_msg)
        
        return self
    
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
            if PROJECT_ROOT is None:
                PROJECT_ROOT = get_project_root()
            logging.info(f"Using project_root: {PROJECT_ROOT}")

        # Drop inherited AVAILABLE_CHAT_MODELS env var so Pydantic Settings can read the JSON array from .env
        os.environ.pop("AVAILABLE_CHAT_MODELS", None)
        logging.info("Loading environment variables for Config via Pydantic .env settings file")

        # Instantiate and return the settings; Pydantic will JSON-decode AVAILABLE_CHAT_MODELS
        return cls(project_root=PROJECT_ROOT)

    def get_relative_path(self, absolute_path: Path) -> Path:
        """Converts an absolute path to a path relative to the project root."""
        if not absolute_path.is_absolute():
            raise ValueError(f"Path {absolute_path} is not absolute, cannot make it relative to project root.")
        return absolute_path.relative_to(self.project_root)

    def resolve_path_from_project_root(self, relative_path: Path | str) -> Path:
        """Resolves a path relative to the project root to an absolute path."""
        return (self.project_root / relative_path).resolve()