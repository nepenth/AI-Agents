import sys
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any
from pydantic_settings import BaseSettings
from pydantic import HttpUrl, Field, field_validator, model_validator
from knowledge_base_agent.exceptions import ConfigurationError
import os
from dotenv import load_dotenv

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
    categorization_model_thinking: bool = Field(False, alias="CATEGORIZATION_MODEL_THINKING", description="Whether the categorization model supports reasoning/thinking subroutines (e.g., Cogito)")
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
    media_cache_dir_rel: Path = Field(..., alias="MEDIA_CACHE_DIR")
    log_file_rel: Path = Field(default_factory=lambda: Path("logs/agent_{timestamp}.log"), alias="LOG_FILE") # Can include {timestamp}
    log_dir_rel: Path = Field(..., alias="LOG_DIR")

    # Resolved absolute paths (properties)
    data_processing_dir: Path
    knowledge_base_dir: Path
    media_cache_dir: Path
    log_file: Path
    log_dir: Path
    
    # X/Twitter credentials
    x_username: str = Field(..., alias="X_USERNAME")
    x_password: str = Field(..., alias="X_PASSWORD")
    x_bookmarks_url: str = Field(..., alias="X_BOOKMARKS_URL")
    
    # Web Server Settings
    web_server_host: str = Field("0.0.0.0", alias="WEB_SERVER_HOST", description="Host for the Flask development server")
    web_server_port: int = Field(5000, alias="WEB_SERVER_PORT", description="Port for the Flask development server")

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
    synthesis_timeout: int = Field(600, alias="SYNTHESIS_TIMEOUT", description="Timeout for synthesis generation in seconds (default: 10 minutes)")
    
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

    # Vector store configuration
    vector_store_path: str = Field("./data/vector_store", alias="VECTOR_STORE_PATH", description="Path to the vector store database directory")
    vector_collection_name: str = Field("knowledge_base", alias="VECTOR_COLLECTION_NAME", description="Name of the vector collection in the database")

    # === New Ollama Performance & GPU Optimization Configuration ===
    # GPU and Performance Optimization
    ollama_num_gpu: int = Field(-1, alias="OLLAMA_NUM_GPU", description="Number of GPU layers to load (-1 for auto, 0 for CPU only)")
    ollama_main_gpu: int = Field(0, alias="OLLAMA_MAIN_GPU", description="Main GPU device to use for processing")
    ollama_low_vram: bool = Field(False, alias="OLLAMA_LOW_VRAM", description="Enable low VRAM mode for memory-constrained GPUs")
    ollama_gpu_split: str = Field("", alias="OLLAMA_GPU_SPLIT", description="GPU memory split configuration for multi-GPU setups (e.g., '50,50')")

    # Model Loading & Memory Management
    ollama_keep_alive: str = Field("5m", alias="OLLAMA_KEEP_ALIVE", description="How long to keep models loaded in memory (e.g., '5m', '1h', '0' for immediately unload)")
    ollama_use_mmap: bool = Field(True, alias="OLLAMA_USE_MMAP", description="Use memory mapping for faster model loading")
    ollama_use_mlock: bool = Field(False, alias="OLLAMA_USE_MLOCK", description="Lock model in memory to prevent swapping")
    ollama_num_threads: int = Field(0, alias="OLLAMA_NUM_THREADS", description="Number of CPU threads to use (0 for auto)")

    # Context and Batch Optimization  
    ollama_num_ctx: int = Field(0, alias="OLLAMA_NUM_CTX", description="Context window size (0 for model default, larger = more context but slower)")
    ollama_num_batch: int = Field(0, alias="OLLAMA_NUM_BATCH", description="Batch size for processing (0 for auto, larger = faster but more memory)")
    ollama_num_keep: int = Field(0, alias="OLLAMA_NUM_KEEP", description="Number of tokens to keep from prompt when context exceeds limit")

    # Advanced Performance Options
    ollama_seed: int = Field(-1, alias="OLLAMA_SEED", description="Random seed for reproducible outputs (-1 for random)")
    ollama_rope_frequency_base: float = Field(0.0, alias="OLLAMA_ROPE_FREQUENCY_BASE", description="RoPE frequency base for extended context")
    ollama_rope_frequency_scale: float = Field(0.0, alias="OLLAMA_ROPE_FREQUENCY_SCALE", description="RoPE frequency scale for extended context")

    # Quality and Output Control
    ollama_stop_sequences: List[str] = Field([], alias="OLLAMA_STOP_SEQUENCES", description="Global stop sequences to prevent unwanted output patterns")
    ollama_repeat_penalty: float = Field(1.1, alias="OLLAMA_REPEAT_PENALTY", description="Penalty for repeating tokens (1.0 = no penalty, higher = less repetition)")
    ollama_repeat_last_n: int = Field(64, alias="OLLAMA_REPEAT_LAST_N", description="Number of previous tokens to consider for repeat penalty")
    ollama_top_k: int = Field(40, alias="OLLAMA_TOP_K", description="Limit sampling to top K tokens (0 = disabled)")
    ollama_min_p: float = Field(0.05, alias="OLLAMA_MIN_P", description="Minimum probability threshold for token sampling")

    # Batch Processing & Concurrency Optimization
    ollama_concurrent_requests_per_model: int = Field(1, alias="OLLAMA_CONCURRENT_REQUESTS_PER_MODEL", description="Max concurrent requests per model instance")
    ollama_enable_model_preloading: bool = Field(True, alias="OLLAMA_ENABLE_MODEL_PRELOADING", description="Pre-load models at startup for faster first requests")
    ollama_adaptive_batch_size: bool = Field(True, alias="OLLAMA_ADAPTIVE_BATCH_SIZE", description="Dynamically adjust batch size based on GPU memory")

    # Model-Specific Optimization Profiles
    ollama_vision_model_gpu_layers: int = Field(-1, alias="OLLAMA_VISION_MODEL_GPU_LAYERS", description="GPU layers for vision model (-1 for auto)")
    ollama_text_model_gpu_layers: int = Field(-1, alias="OLLAMA_TEXT_MODEL_GPU_LAYERS", description="GPU layers for text model (-1 for auto)")
    ollama_embedding_model_gpu_layers: int = Field(-1, alias="OLLAMA_EMBEDDING_MODEL_GPU_LAYERS", description="GPU layers for embedding model (-1 for auto)")

    # === Database Configuration ===
    database_url: str = Field(f"sqlite:///{get_project_root() / 'instance' / 'knowledge_base.db'}", alias="DATABASE_URL", description="Database connection string")

    # === Celery Configuration (NEW) ===
    # Celery Feature Flag
    use_celery: bool = Field(True, alias="USE_CELERY", description="Enable Celery task queue for asynchronous processing")
    
    # Celery Broker and Backend
    celery_broker_url: str = Field("redis://localhost:6379/0", alias="CELERY_BROKER_URL", description="Celery broker URL for task queue")
    celery_result_backend: str = Field("redis://localhost:6379/0", alias="CELERY_RESULT_BACKEND", description="Celery result backend for storing task results")
    celery_task_serializer: str = Field("json", alias="CELERY_TASK_SERIALIZER", description="Serializer for task payloads")
    celery_accept_content: List[str] = Field(["json"], alias="CELERY_ACCEPT_CONTENT", description="Accepted content types for tasks")
    celery_result_serializer: str = Field("json", alias="CELERY_RESULT_SERIALIZER", description="Serializer for task results")
    
    # Redis Configuration for Progress/Logs
    redis_progress_url: str = Field("redis://localhost:6379/1", alias="REDIS_PROGRESS_URL", description="Redis URL for progress tracking")
    redis_logs_url: str = Field("redis://localhost:6379/2", alias="REDIS_LOGS_URL", description="Redis URL for log streaming")
    
    # Enhanced Task Configuration
    celery_task_track_started: bool = Field(True, alias="CELERY_TASK_TRACK_STARTED", description="Track when tasks are started")
    celery_task_time_limit: int = Field(14400, alias="CELERY_TASK_TIME_LIMIT", description="Maximum task execution time in seconds (4 hours)")
    celery_worker_prefetch_multiplier: int = Field(1, alias="CELERY_WORKER_PREFETCH_MULTIPLIER", description="Number of tasks worker prefetches")

    @property
    def celery_config(self) -> Dict[str, Any]:
        """Returns a dictionary of Celery configuration settings."""
        return {
            'broker_url': self.celery_broker_url,
            'result_backend': self.celery_result_backend,
            'task_serializer': self.celery_task_serializer,
            'accept_content': self.celery_accept_content,
            'result_serializer': self.celery_result_serializer,
            'timezone': 'UTC',
            'enable_utc': True,
            'task_track_started': self.celery_task_track_started,
            'task_time_limit': self.celery_task_time_limit,
            'worker_prefetch_multiplier': self.celery_worker_prefetch_multiplier,
            'task_routes': {
                'knowledge_base_agent.tasks.agent.*': {'queue': 'agent'},
                'knowledge_base_agent.tasks.processing.*': {'queue': 'processing'},
                'knowledge_base_agent.tasks.chat.*': {'queue': 'chat'},
            },
            'result_expires': 3600,
            'task_ignore_result': False,
            'worker_max_tasks_per_child': 1000,
            'worker_disable_rate_limits': True,
            'broker_connection_retry_on_startup': True,
        }

    @model_validator(mode='after')
    def resolve_paths(self):
        """Resolve all relative path configurations to absolute paths based on project_root."""
        
        # Ensure that the project_root has been set by something valid
        if self.project_root is None:
            logging.error("Project root is None. This should not happen as default_factory should be called.")
            raise ConfigurationError("Project root is None.")
        
        self.data_processing_dir = (self.project_root / self.data_processing_dir_rel).resolve()
        self.knowledge_base_dir = (self.project_root / self.knowledge_base_dir_rel).resolve()
        self.media_cache_dir = (self.project_root / self.media_cache_dir_rel).resolve()
        
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
            self.data_processing_dir, self.knowledge_base_dir, self.media_cache_dir,
            self.log_file, self.log_dir
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

    @field_validator('available_chat_models', mode='before')
    def parse_json_string(cls, v):
        if isinstance(v, str):
            import json
            try:
                return json.loads(v)
            except json.JSONDecodeError:
                raise ValueError("AVAILABLE_CHAT_MODELS is not a valid JSON string")
        return v

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
        """Create Config from environment variables with dynamic project root detection."""
        global PROJECT_ROOT
        
        if project_root_path:
            # Legacy support: if explicitly provided, use it
            PROJECT_ROOT = project_root_path
            logging.info(f"PROJECT_ROOT explicitly set to: {PROJECT_ROOT}")
        else:
            # Dynamic detection for portability
            if PROJECT_ROOT is None:
                current_file_dir = Path(__file__).parent  # knowledge_base_agent/
                potential_roots = [
                    current_file_dir.parent,  # Parent of knowledge_base_agent/
                    Path.cwd(),  # Current working directory
                ]
                
                for root_candidate in potential_roots:
                    # Check for project indicators
                    if (root_candidate / '.env').exists() and (root_candidate / 'knowledge_base_agent').is_dir():
                        PROJECT_ROOT = root_candidate
                        break
                
                # Fallback if no clear indicators found
                if PROJECT_ROOT is None:
                    PROJECT_ROOT = current_file_dir.parent
                    logging.warning(f"Could not detect project root from indicators. Using fallback: {PROJECT_ROOT}")
                
                logging.info(f"PROJECT_ROOT dynamically detected: {PROJECT_ROOT}")

        # Drop inherited AVAILABLE_CHAT_MODELS env var so Pydantic Settings can read the JSON array from .env
        os.environ.pop("AVAILABLE_CHAT_MODELS", None)
        logging.info("Loading environment variables for Config via Pydantic .env settings file")

        # Instantiate and return the settings; Pydantic will JSON-decode AVAILABLE_CHAT_MODELS
        # The Config constructor will automatically load from environment variables and .env file
        return cls()  # type: ignore[call-arg]  # BaseSettings loads from env automatically

    def get_relative_path(self, absolute_path: Path) -> Path:
        """Converts an absolute path to a path relative to the project root."""
        if not absolute_path.is_absolute():
            raise ValueError(f"Path {absolute_path} is not absolute, cannot make it relative to project root.")
        return absolute_path.relative_to(self.project_root)

    def resolve_path_from_project_root(self, relative_path: Path | str) -> Path:
        """Resolve a relative path against the project root to get an absolute path."""
        return (self.project_root / Path(relative_path)).resolve()

    @classmethod
    def auto_configure_ollama_optimization(cls, workload_type: str = "balanced", 
                                         apply_to_env: bool = False) -> Dict[str, str]:
        """
        Auto-configure Ollama optimization settings based on detected hardware.
        
        Args:
            workload_type: Optimization profile ("performance", "balanced", "memory_efficient")
            apply_to_env: Whether to automatically apply settings to environment
            
        Returns:
            Dictionary of environment variables to set
        """
        try:
            from .hardware_detector import HardwareDetector
            
            detector = HardwareDetector()
            system_info = detector.detect_system_info()
            config = detector.generate_ollama_config(system_info, workload_type)
            
            # Convert to environment variables dictionary
            env_vars = {
                "OLLAMA_NUM_GPU": str(config.num_gpu),
                "OLLAMA_MAIN_GPU": str(config.main_gpu),
                "OLLAMA_LOW_VRAM": str(config.low_vram).lower(),
                "OLLAMA_GPU_SPLIT": config.gpu_split,
                "OLLAMA_NUM_THREADS": str(config.num_threads),
                "OLLAMA_KEEP_ALIVE": config.keep_alive,
                "OLLAMA_USE_MMAP": str(config.use_mmap).lower(),
                "OLLAMA_USE_MLOCK": str(config.use_mlock).lower(),
                "OLLAMA_NUM_CTX": str(config.num_ctx),
                "OLLAMA_NUM_BATCH": str(config.num_batch),
                "OLLAMA_ADAPTIVE_BATCH_SIZE": str(config.adaptive_batch_size).lower(),
                "OLLAMA_REPEAT_PENALTY": str(config.repeat_penalty),
                "OLLAMA_REPEAT_LAST_N": str(config.repeat_last_n),
                "OLLAMA_TOP_K": str(config.top_k),
                "OLLAMA_MIN_P": str(config.min_p),
                "MAX_CONCURRENT_REQUESTS": str(config.max_concurrent_requests),
                "OLLAMA_ENABLE_MODEL_PRELOADING": str(config.enable_model_preloading).lower(),
                "OLLAMA_VISION_MODEL_GPU_LAYERS": str(config.vision_model_gpu_layers),
                "OLLAMA_TEXT_MODEL_GPU_LAYERS": str(config.text_model_gpu_layers),
                "OLLAMA_EMBEDDING_MODEL_GPU_LAYERS": str(config.embedding_model_gpu_layers),
            }
            
            # Apply to environment if requested
            if apply_to_env:
                for key, value in env_vars.items():
                    os.environ[key] = value
                logging.info(f"Applied {len(env_vars)} auto-configured Ollama optimization settings")
            
            # Log the configuration reasoning
            logging.info("Hardware-based Ollama optimization generated:")
            for key, reason in config.reasoning.items():
                logging.info(f"  {key}: {reason}")
                
            return env_vars
            
        except ImportError as e:
            logging.warning(f"Hardware detection not available (missing dependencies): {e}")
            return {}
        except Exception as e:
            logging.error(f"Failed to auto-configure Ollama optimization: {e}")
            return {}