# Knowledge Base Agent - Re-implementation Plan

## 1. Goals

*   **Modernize Codebase:** Refactor using current best practices for Python, async programming, and project structure.
*   **Improve Modularity:** Clearly define responsibilities for each component, reducing coupling and improving testability.
*   **Enhance Maintainability:** Make the code easier to understand, debug, and extend with new features.
*   **Increase Robustness:** Improve error handling, state management, and data validation throughout the pipeline.
*   **Streamline Workflow:** Ensure a logical, efficient, and concurrent flow for processing tweets into knowledge base items.
*   **Eliminate Redundancy:** Remove duplicated logic and unused code.

## 2. Core Agent Workflow (High-Level)

The agent processes tweets (primarily from bookmarks) through a series of phases to generate structured knowledge base entries. The core processing phases (Caching, Interpretation, Categorization, Generation, DB Sync) are designed to run concurrently on multiple items where possible, managed by `asyncio` and concurrency controls (`asyncio.Semaphore`).

1.  **Initialization:** Load configuration, set up logging, initialize database connection (externally before pipeline start), load processing state from `StateManager`.
2.  **Input Acquisition (Optional):** If enabled (`fetch_bookmarks_enabled=true` and not skipped via runtime preference), fetch new bookmarks/tweet URLs using Playwright and add new tweet IDs to the `StateManager`.
3.  **State Loading:** `StateManager` loads existing tweet data, including status flags (`cache_complete`, `media_processed`, `categories_processed`, `kb_item_created`, `db_synced`, `error_message`). `AgentPipeline` retrieves the list of all known tweet IDs.
4.  **Phase 1: Caching & Validation:**
    *   Executed concurrently for tweets where `cache_complete` is false or `force_recache` runtime preference is set.
    *   Fetches core tweet data (text, author, media URLs, creation date) using `twscrape`.
    *   Expands shortened URLs.
    *   Verifies/Downloads associated media (images, videos) to `media_cache`.
    *   Updates `cache_complete` flag and saves state via `StateManager`.
5.  **Phase 2: Media Interpretation:**
    *   Executed concurrently for tweets where `cache_complete` is true and (`media_processed` is false or `force_reinterpret` runtime preference is set).
    *   Generates descriptions for images using the vision model (via Ollama interface).
    *   Updates `media_processed` flag and saves state via `StateManager`.
6.  **Phase 3: Content Categorization:**
    *   Executed concurrently for tweets where `cache_complete` and `media_processed` are true, and (`categories_processed` is false or `force_recategorize` runtime preference is set).
    *   Uses an LLM (via Ollama interface) to determine `main_category`, `sub_category`, and `item_name` based on text and media descriptions.
    *   Updates `categories_processed` flag and saves state via `StateManager`.
7.  **Phase 4: KB Item Generation:**
    *   Executed concurrently for tweets where `cache_complete`, `media_processed`, and `categories_processed` are true, and (`kb_item_created` is false or `force_regenerate` runtime preference is set).
    *   Generates detailed content for the KB item using an LLM (via Ollama interface).
    *   Creates the directory structure (`kb-generated/main/sub/item_name/`).
    *   Writes the generated content to `README.md`.
    *   Copies relevant media files from `media_cache` into the item directory.
    *   Appends media links/embeds to the `README.md`.
    *   Updates `kb_item_created` flag, `kb_item_path`, `kb_media_paths` and saves state via `StateManager`.
8.  **Phase 5: Database Synchronization:**
    *   Executed concurrently for tweets where `kb_item_created` is true and `db_synced` is false. (Runs idempotently to ensure DB reflects current KB state).
    *   Adds or updates the corresponding entry in the local SQLite database (`KnowledgeBaseItem` model) using `database.sync_kb_item_async`.
    *   Updates `db_synced` flag and saves state via `StateManager`.
9.  **Phase 6: Index Generation (Optional):**
    *   If not skipped via runtime preference (`skip_indexing=false`).
    *   Regenerates the root `kb-generated/README.md` summarizing the knowledge base structure.
    *   (Future) Generate static HTML files for GitHub Pages deployment.
10. **Phase 7: Git Synchronization (Optional):**
    *   If enabled (`git_enabled=true`) and not skipped via runtime preference (`skip_git=false`).
    *   Commits and pushes changes in the `kb-generated` directory to the configured remote Git repository using the Git interface.
11. **State Finalization:**
    *   Iterates through processed items. If all required flags (`cache_complete`, `media_processed`, `categories_processed`, `kb_item_created`, `db_synced`) are true and no `error_message` is set, the tweet ID is moved from the "unprocessed" tracking mechanism to the "processed" set within the `StateManager`.
12. **Statistics & Reporting:** Throughout the run, statistics (counts, timings, errors, LLM durations) are collected by `ProcessingStats`. Progress updates and ETA are emitted via SocketIO. A final report is logged.
13. **Cleanup:** (Future) Remove temporary files if any.

## 3. Proposed Module Structure

```text
knowledge-base_v2/
│
├── knowledge_base_agent/        # Main package
│   ├── __init__.py
│   ├── main_cli.py              # CLI entry point & argument parsing
│   ├── main_web.py              # Web server (Flask/SocketIO) entry point
│   ├── config.py                # Configuration loading (dotenv, Pydantic validation)
│   ├── log_setup.py             # Centralized logging configuration (file, console, websocket)
│   ├── exceptions.py            # Custom exception classes
│   ├── types.py                 # Core data types (Pydantic models: Config, TweetData, KBItemRecord)
│   ├── database.py              # SQLAlchemy models, db initialization, async sync function
│   │
│   ├── utils/                   # Utility functions
│   │   ├── __init__.py
│   │   ├── file_io.py           # Async file ops, atomic writes, JSON handling
│   │   ├── web_utils.py         # URL parsing, expansion, sanitization
│   │   └── markdown.py          # Markdown processing and rendering
│   │
│   ├── interfaces/              # External service interactions
│   │   ├── __init__.py
│   │   ├── http_client.py       # Base async HTTP client (httpx)
│   │   ├── ollama.py            # Ollama API interaction logic
│   │   ├── playwright_client.py # Playwright interaction logic
│   │   ├── git.py               # GitPython interaction logic
│   │   └── twscrape_client.py   # Placeholder if twscrape interaction needs wrapping (currently used directly in cacher)
│   │
│   ├── processing/              # Core agent processing logic
│   │   ├── __init__.py
│   │   ├── state.py             # State management (StateManager, TweetData)
│   │   ├── pipeline.py          # AgentPipeline: Orchestrates processing phases, concurrency, stats
│   │   ├── fetcher.py           # Handles bookmark fetching (Playwright)
│   │   ├── cacher.py            # Handles tweet data/media caching (twscrape), validation
│   │   ├── interpreter.py       # Media interpretation (Ollama vision)
│   │   ├── categorizer.py       # Content categorization and naming (Ollama text)
│   │   ├── generator.py         # Generates KB item content and writes files (Ollama text)
│   │   ├── indexer.py           # Generates root README and GitHub Pages
│   │   └── stats.py             # ProcessingStats class for tracking metrics
│   │
│   └── web/                     # Web interface components
│       ├── __init__.py
│       ├── routes.py            # Flask route definitions (main pages, KB browser)
│       ├── sockets.py           # SocketIO event handlers (logs, status, control)
│       ├── log_viewer.py        # Flask routes for log history page and API
│       └── persistence.py       # Handles persisting web UI state via API
│
├── scripts/                     # Standalone utility scripts (e.g., cache fixing, manual regeneration)
│   └── ...
│
├── templates/                   # Jinja2 HTML templates (base.html, index.html, etc.)
│   └── ...
│
├── static/                      # CSS, JavaScript files (style.css, main.js, log_viewer.js)
│   └── ...
│
├── logs/                        # Log files (runtime generated)
│   └── .gitkeep
│
├── data/                        # Data files (runtime generated)
│   ├── state.json               # Combined cache/state file managed by StateManager
│   └── media_cache/             # Cached media files
│       └── .gitkeep
│
├── kb-generated/                # Generated knowledge base output
│   └── .gitkeep
│
├── implementation_plan.md       # This file
├── .env.example                 # Example environment variables
├── requirements.txt             # Python dependencies
└── README.md                    # Project README
```

## 4. Module Responsibilities & Key Functions

*(Note: Illustrative primary functions/responsibilities)*

*   **`main_cli.py`**:
    *   `main()`: Parses CLI args, loads config, initializes DB engine, initializes pipeline (without SocketIO), runs pipeline.
*   **`main_web.py`**:
    *   Flask app setup, SocketIO setup, DB setup (`db.init_app`).
    *   Passes `socketio` instance to `AgentPipeline`.
    *   Manages agent execution thread/process via SocketIO commands (`start_agent`, `stop_agent`).
*   **`config.py`**:
    *   `Config` (Pydantic `BaseSettings`): Defines and validates all configuration values loaded from `.env`.
    *   `load_config()`: Loads and returns the validated `Config` object.
*   **`log_setup.py`**:
    *   `setup_logging(config, target)`: Configures logging handlers (file, console, websocket via SocketIO emitter).
*   **`database.py`**:
    *   Defines SQLAlchemy models (`KnowledgeBaseItem`).
    *   Provides `db` instance (Flask-SQLAlchemy).
    *   `sync_kb_item_async(tweet_data)`: Async function to add/update KB item in DB (used by pipeline).
*   **`utils/*`**: Contains pure utility functions.
*   **`interfaces/*`**: Classes encapsulating interactions with external services. Handles API calls, authentication, service-specific errors.
*   **`processing/state.py`**:
    *   `TweetData` (Pydantic `BaseModel`): Holds all data and status flags for a single tweet (`cache_complete`, `media_processed`, etc., `error_message`, `failed_phase`, `db_synced`). Includes `needs_processing(phase)` method.
    *   `StateManager` class:
        *   Manages the dictionary of `TweetData` objects.
        *   `load_state()`, `save_state()`: Handles atomic loading/saving of the combined state/cache to `state.json`.
        *   `get_tweet_data(tweet_id)`, `get_or_create_tweet_data(tweet_id)`, `update_tweet_data(tweet_id, data)`.
        *   `get_all_known_ids()`, `get_unprocessed_ids()`, `is_processed(tweet_id)`, `mark_processed(tweet_id)`.
*   **`processing/pipeline.py`**:
    *   `AgentPipeline` class:
        *   `__init__(config, state_manager, interfaces, socketio)`: Initializes with dependencies.
        *   `run(preferences)`: Main orchestration method. Handles overall workflow, concurrency (`asyncio.Semaphore`), calls phase methods, manages run preferences (force/skip flags), aggregates stats, emits progress/ETA via SocketIO.
        *   `_run_concurrent_phase(...)`: Helper to run phase tasks concurrently.
        *   `_run_single_item_phase(...)`: Wrapper for individual item processing with error handling and stats.
        *   `request_stop()`: Flags the pipeline to stop.
        *   `_emit_progress()`: Sends progress updates.
        *   `_calculate_eta()`: Estimates remaining time.
        *   `_finalize_state()`: Marks fully processed items.
*   **Processing Phase Modules (`fetcher.py`, `cacher.py`, `interpreter.py`, `categorizer.py`, `generator.py`, `indexer.py`)**:
    *   Each contains the primary async function for its phase (e.g., `cacher.run_cache_phase`).
    *   Accepts necessary arguments (often `tweet_data`, config, clients, `state_manager`).
    *   Performs the core logic for that phase.
    *   Updates the passed `tweet_data` object directly with results and status flags.
    *   Calls `state_manager.update_tweet_data()` to persist changes for the item.
    *   Returns success/failure or raises specific exceptions.
*   **`processing/stats.py`**:
    *   `ProcessingStats` class: Tracks counts (entered, success, failed per phase), timings (total run, per phase, LLM durations), errors. Provides methods like `get_report()`, `get_avg_llm_duration()`.
*   **`web/*`**: Standard Flask/SocketIO structure. `routes.py` includes KB browsing and uses a context processor. `log_viewer.py` handles the log history page and API. `sockets.py` handles agent control events. `persistence.py` manages UI state.

## 7. Implementation Order

*(Refined Order)*

0.  Environment Setup.
1.  Project Foundation (`config.py`, `exceptions.py`, `types.py`, `log_setup.py`).
2.  Utilities & Interfaces (`utils/*`, `interfaces/*`).
3.  Database Layer (`database.py`).
4.  State Management (`processing/state.py`).
5.  Statistics Tracking (`processing/stats.py`).
6.  Core Processing Modules (Implement phase logic: `fetcher`, `cacher`, `interpreter`, `categorizer`, `generator`, `indexer`). **Crucially, ensure these modules correctly update `TweetData` objects and call `StateManager.update_tweet_data()` internally.**
7.  Pipeline Orchestration (`processing/pipeline.py`): Integrate actual phase calls, concurrency, stats, progress emission.
8.  Command-Line Interface (`main_cli.py`).
9.  Web Server Foundation (`main_web.py`, `web/sockets.py`, base templates, JS).
10. Web Server Agent Integration (Start/Stop logic, status/log emission).
11. Web Application Features (Implement routes in `web/routes.py`, `web/log_viewer.py`, create remaining templates, implement `web/persistence.py`, refine JS).
12. Finalization & Documentation (Testing, `README.md`, `.env.example`, utility scripts).

## 8. Initial Requirements (`requirements.txt`)

*(Verified/Updated)*

```text
# Core Web Framework & Real-time Communication
flask
flask-socketio
# gevent-websocket # Not strictly needed if using 'threading' async_mode
python-dotenv    # For loading .env configuration

# Database ORM
flask-sqlalchemy
sqlalchemy
# Optional: DB driver if not using default SQLite (e.g., psycopg2-binary for PostgreSQL)

# HTTP Client (Async)
httpx[http2]     # For async HTTP requests (Ollama, potentially others)
aiofiles         # For async file operations

# Data Validation & Typing
pydantic         # For config validation and data types
pydantic-settings # For loading settings from .env

# Web Scraping / Automation (for Bookmarks)
playwright       # Browser automation library
# Note: Playwright requires browser binaries: `playwright install`

# Tweet Scraping
twscrape         # Library for interacting with Twitter/X API (unofficial)

# Markdown Processing
markdown         # For rendering markdown in web UI
python-markdown-math # Example extension for math rendering
Pygments         # For code highlighting in markdown

# Git Interaction (Optional)
GitPython        # If GIT_ENABLED=true

# Logging & Utilities
# (Standard library logging is sufficient initially)

# Note: An Ollama Python client library might exist or could be developed.
# If not, direct interaction via `httpx` within `interfaces/ollama.py` is needed.

# Note: Add testing libraries like pytest, pytest-asyncio later.
```

## 9. Environment Variables (`.env`)

*(Verified/Updated)*

```dotenv
# --- Ollama Configuration ---
OLLAMA_URL=http://localhost:11434
TEXT_MODEL=mistral:latest
FALLBACK_MODEL=llama3:latest
VISION_MODEL=llava:latest

# --- Filesystem Paths ---
KNOWLEDGE_BASE_DIR=./kb-generated
DATA_DIR=./data
LOG_DIR=./logs

# --- Playwright / X Bookmarks ---
FETCH_BOOKMARKS_ENABLED=true
X_USERNAME="your_x_username"
X_PASSWORD="your_x_password"
X_BOOKMARKS_URL="https://x.com/i/bookmarks"

# --- TWSCRAPE ---
# Add any necessary twscrape credentials or config here if needed for login
# Example (Consult twscrape docs - might use username/password from above or dedicated vars):
# TWSCRAPE_AUTH_TOKEN=... # Example placeholder

# --- Git Synchronization ---
GIT_ENABLED=false
GITHUB_TOKEN="your_github_pat"
GITHUB_USER_NAME="your_github_username"
GITHUB_USER_EMAIL="your_github_email@example.com"
GITHUB_REPO_URL="git@github.com:username/your-kb-repo.git"

# --- Web Server Configuration ---
FLASK_SECRET_KEY="a_very_secret_random_string_please_change"
DATABASE_URL="sqlite:///./data/knowledge_base.db"
FLASK_RUN_PORT=5001 # Default port if KBA_PORT env var not set at runtime

# --- Agent Behavior ---
# FORCE_RECACHE is now a runtime preference via UI/CLI, not an env var
# LOG_LEVEL is handled by log_setup based on context (CLI/Web)

# Optional: Timeouts (can be added to Config if needed)
# OLLAMA_TIMEOUT=300
# PLAYWRIGHT_TIMEOUT=120
```

## 10. Key Considerations

*(Updated)*

*   **Configuration:** Centralize settings in `config.py` (Pydantic `Config`), loaded via `.env`.
*   **Logging:** Implement robust logging via `log_setup.py` for CLI, web UI (via sockets), and file output.
*   **Error Handling:** Use custom exceptions (`exceptions.py`). Implement retries where appropriate (interfaces). Ensure pipeline/phases handle errors gracefully, record them (`ProcessingStats`, `TweetData.error_message`), and update state correctly.
*   **State Management:** `processing/state.py` (`StateManager` + `TweetData`) is the source of truth. Phases **must** update the `TweetData` object they receive and call `StateManager.update_tweet_data()` to persist changes atomicity. `state.json` holds the combined cache/state.
*   **Database Interaction:** Centralize DB model in `database.py`. `AgentPipeline` uses `database.sync_kb_item_async`. Ensure DB sessions/connections are handled correctly (Flask handles context for web routes; CLI/Pipeline needs explicit engine/session management if interacting directly outside Flask context).
*   **Async Operations:** Use `asyncio`, `httpx`, `aiofiles`. Employ `asyncio.Semaphore` within `AgentPipeline` to manage concurrency for different phase types (LLM, Cache, DB) preventing resource exhaustion.
*   **Testing:** Modular structure facilitates unit testing (mocks for interfaces/state) and integration testing. `pytest-asyncio` is recommended.
*   **Progress Reporting & ETA:** `AgentPipeline` emits progress (`processed_count`, `total_items`, `current_phase`, `eta`) via SocketIO (`progress_update` event) for the web UI. ETA calculation is based on average LLM phase timings (`ProcessingStats`).