# Implementation Plan for Knowledge Base Agent

## Overview

The Knowledge Base Agent is an AI-driven system designed to automate the process of fetching, processing, categorizing, and generating content for a structured knowledge base. It primarily focuses on processing tweets from Twitter bookmarks, categorizing them using AI models, and generating markdown content for a knowledge repository. This document details the implementation plan, logical flow, and module functionalities to assist in extending, refining, or understanding the agent's design.

## Objectives

- **Automation**: Automate the fetching of Twitter bookmarks, processing of tweet content, and generation of structured knowledge base items.
- **Categorization**: Use AI models to categorize content into a hierarchical structure of main categories and subcategories.
- **Content Generation**: Generate detailed markdown content for each tweet, including text, media, and metadata.
- **State Management**: Maintain a persistent state to track processed and unprocessed content, avoiding redundant operations.
- **Integration**: Synchronize the knowledge base with a GitHub repository for version control and public access.
- **User Interface**: Provide a web interface for initiating agent runs, monitoring progress, and viewing generated content.
- **Portability**: Ensure paths are managed relatively for easier deployment and sharing.
- **Real-time Updates**: Offer real-time logging, phase updates, and agent status synchronization across multiple UI clients.

## Architectural Highlights

- **Relative Path Management**: The system uses a `PROJECT_ROOT` determined at startup. All internal path storage (e.g., in `tweet_cache.json`, database) and configuration path fields are handled relative to this root, ensuring portability. Absolute paths are resolved dynamically.
- **Multi-Client State Synchronization**: The agent backend (`agent.py`, `web.py`) maintains and communicates its operational state (running, idle, current phase) via SocketIO, allowing multiple web clients to have a consistent view.
- **Granular Real-time Feedback**: Detailed logs and processing phase updates are emitted via SocketIO for enhanced monitoring through the web UI.

## Logical Flow

The logical flow of the Knowledge Base Agent follows a phased approach to ensure systematic processing of content:

1. **Initialization**:
   - Determine and set `PROJECT_ROOT` for relative path resolution (via `main.py`/`web.py` startup, setting values in `config.py` and `shared_globals.py`).
   - Load configuration settings from environment variables (`config.py`).
   - Set up logging for debugging and monitoring (`config.py`, `web.py`).
   - Initialize core components: `KnowledgeBaseAgent` (passing SocketIO instance), `StateManager`, `CategoryManager`, `HTTPClient`. Database and Flask app are initialized in `web.py`.

2. **Content Fetching (if enabled)**:
   - Fetch Twitter bookmarks using Playwright for browser automation (`fetch_bookmarks.py`).
   - Extract tweet URLs and IDs from bookmarks.
   - Queue new, unprocessed tweets in `StateManager`.

3. **Content Processing (phase-by-phase via `ContentProcessor` for queued items)**:
   - **Phase 1: Tweet Caching**: Validate and cache full tweet data (text, media URLs, metadata) from URLs, storing results in `tweet_cache.json` managed by `StateManager`. Uses `tweets_data_map` for batch processing.
   - **Phase 2: LLM Processing (Categorization & Naming)**: For each tweet, use AI models (`ai_categorization.py`) to determine `main_category`, `sub_category`, and a filesystem-safe `item_name`. The AI interaction requests JSON output. `CategoryManager.ensure_category_exists()` is called.
   - **Phase 3: Knowledge Base Item Generation & Media Handling**:
     - For each tweet, `kb_item_generator.py`'s `create_knowledge_base_item` function is invoked. It prompts an LLM to generate a structured JSON object detailing the full knowledge base article (including fields like `suggested_display_title`, `meta_description`, `introduction`, structured `sections`, `key_takeaways`, etc.).
     - This JSON object is then converted into a complete Markdown string by `kb_item_generator.py`.
     - A `KnowledgeBaseItem` dataclass instance (from `types.py`) is populated. This object includes the generated Markdown, `raw_json_content`, `display_title`, `item_name`, categories, and media details.
     - `markdown_writer.py`'s `write_kb_item` method takes this `KnowledgeBaseItem` object. It creates the directory structure (e.g., `kb-generated/main_category/sub_category/item_name/` relative to `PROJECT_ROOT`), copies associated media files from the media cache into the item's dedicated `media/` subdirectory (renaming them if needed), and updates the Markdown to use relative links for this copied media. It returns the path to the item's directory (relative to `PROJECT_ROOT`) and a list of media paths relative to the item's directory (e.g., `['media/image1.png']`).
     - `content_processor.py` updates the tweet's entry in `tweet_cache.json` (via `StateManager`) with `kb_item_path` (path to `README.md` relative to `PROJECT_ROOT`) and `kb_media_paths` (JSON string of media paths relative to the item's directory).
   - **Phase 4: Database Synchronization**: `content_processor.py` iterates through successfully processed items. For each, it creates or updates an entry in the SQL database (`KnowledgeBaseItem` model from `models.py`), storing `kb_item_path`, `kb_media_paths`, `display_title`, `raw_json_content`, etc.
   - _(Note: Media processing for descriptions/alt-text is integrated within the KB item generation or earlier caching phases rather than a separate, later "Media Processing" phase mentioned in older plans)._

4. **README Generation (if enabled)**:
   - Update the root `README.md` of the knowledge base with an overview and links to categorized content (`readme_generator.py`).

5. **Synchronization (if enabled)**:
   - Commit changes to a GitHub repository (`git_helper.py`).

6. **Cleanup**:
   - Remove temporary files and close resources.

## Module Functionalities

### Core Components

- **`agent.py` (KnowledgeBaseAgent)**:
  - **Purpose**: Central orchestrator, managing the workflow, state, and communication.
  - **Key Attributes**: `config`, `http_client`, `state_manager`, `category_manager`, `content_processor`, `socketio` (SocketIO instance), `_is_running`, `_current_phase_id`, `_current_phase_message`, `_current_phase_status`, `_current_run_preferences`.
  - **Key Functions**:
    - `initialize()`: Sets up dependencies.
    - `run()`: Executes the main workflow, coordinating phases based on `UserPreferences`. Manages agent running state (`_is_running`, etc.) via `set_initial_run_state()` and `set_final_run_state()`.
    - `process_tweet()`: Processes a single tweet end-to-end. Uses `current_app.app_context()` for Flask context.
    - `socketio_emit_log()`: Helper to emit logs via SocketIO.
    - `socketio_emit_phase_update()`: Helper to emit phase updates and set internal agent phase.
    - Getter methods for agent state (e.g., `is_agent_running()`, `get_current_phase_info()`).
  - **Interaction**: Coordinates with most other modules. Passes `socketio` instance and `socketio_emit_phase_update` method to `ContentProcessor`.

- **`config.py` (Config)**:
  - **Purpose**: Manages system-wide configuration (Pydantic `BaseSettings`) loaded from `.env` and environment variables.
  - **Key Features**:
    - Defines `PROJECT_ROOT` (Path object), determined at startup and settable.
    - Path fields (e.g., `data_processing_dir_rel`) are defined as relative and resolved to absolute paths against `PROJECT_ROOT` via a `model_validator`.
    - Helper methods `resolve_path_from_project_root()` and `get_relative_path()`.
    - Includes flags like `enable_gpu_stats_monitoring`.
  - **Interaction**: Used by all modules. `PROJECT_ROOT` is also made available via `shared_globals.py`.

- **`state_manager.py` (StateManager)**:
  - **Purpose**: Manages the persistent state of tweets (`tweet_cache.json`) and unprocessed queues.
  - **Key Functions**:
    - `initialize()`: Loads and validates state.
    - `get_tweet()`, `update_tweet_data()`: Manages individual tweet entries in `tweet_cache.json`. This cache now stores `kb_item_path` (path to `README.md` relative to project root), `kb_media_paths` (JSON string of media paths relative to the item's directory), `display_title`, and `raw_json_content`.
    - Tracks processed/unprocessed tweets.
  - **Interaction**: Crucial for `ContentProcessor` and `KnowledgeBaseAgent`.

- **`content_processor.py` (ContentProcessor)**:
  - **Purpose**: Handles the detailed, phased processing of tweet content.
  - **Key Functions**:
    - `process_all_tweets()`: Orchestrates phase-by-phase processing (cache, LLM, KB item gen, DB sync) using a `tweets_data_map`. Emits granular progress.
    - Calls `kb_item_generator.create_knowledge_base_item()` and `markdown_writer.write_kb_item()`.
    - Updates `tweet_cache.json` via `StateManager` with paths. Synchronizes to SQL DB (`KnowledgeBaseItem` model).
  - **Interaction**: Uses `socketio` instance and `phase_emitter_func` from `KnowledgeBaseAgent`. Interacts heavily with `StateManager`, `CategoryManager`, `HTTPClient`, `kb_item_generator.py`, `markdown_writer.py`.

- **`category_manager.py` (CategoryManager)**:
  - **Purpose**: Manages categories and subcategories.
  - **Key Functions**: `initialize()`, `get_all_categories()`, `ensure_category_exists()`.
  - **Interaction**: Used by `ContentProcessor` during AI categorization.

- **`kb_item_generator.py`**:
  - **Purpose**: Generates structured JSON content for a KB article using an LLM, then converts it to Markdown, and populates a `KnowledgeBaseItem` dataclass.
  - **Key Functions**:
    - `create_knowledge_base_item()`: Takes tweet data. Prompts an LLM for structured JSON content (title, intro, sections, etc.). Converts JSON to Markdown. Returns a populated `KnowledgeBaseItem` (from `types.py`) with this Markdown, `raw_json_content`, `display_title`, etc.
  - **Interaction**: Used by `ContentProcessor`.

- **`markdown_writer.py`**:
  - **Purpose**: Handles filesystem operations for KB items: directory creation, media file copying/linking, and writing the final Markdown.
  - **Key Functions**:
    - `write_kb_item()`: Takes a `KnowledgeBaseItem` object. Creates `kb-generated/main_cat/sub_cat/item_name/` directory. Copies media from cache to item's `media/` subfolder, renames media, updates Markdown with relative media links. Writes final Markdown to `README.md`. Returns KB item directory path and relative media paths.
  - **Interaction**: Used by `ContentProcessor`.

- **`readme_generator.py`**: (No major changes noted in recent history, but ensure consistency with path handling).
- **`pages_generator.py`**: (No major changes noted).

### Utility Modules

- **`http_client.py` (HTTPClient)**: (No major changes noted).
- **`playwright_fetcher.py` / `fetch_bookmarks.py`**: (No major changes noted).
- **`tweet_cacher.py` (TweetCacheValidator)**: Updated to accept `config: Config` in constructor.
- **`media_processor.py`**: (Role clarified: media download, image description. `mark_media_processed` in `state_manager.py` is set by this or if no media).
- **`text_processor.py`**: (Unused functions removed. `categorize_and_name_content()` may have moved mostly to `ai_categorization.py`).
- **`ai_categorization.py`**: Corrected key mismatches for accessing tweet text/alt text.
- **`image_interpreter.py`**: (No major changes noted).
- **`git_helper.py` (GitSyncHandler)**: (No major changes noted).
- **`progress.py` (ProcessingStats)**: (No major changes noted, local `ProcessingStats` removed from `content_processor.py` as it uses the one from `agent.py`).
- **`exceptions.py`**: (No major changes noted).

- **`web.py`**:
  - **Purpose**: Flask/SocketIO web application for UI, agent control, and content viewing.
  - **Key Features**:
    - Initializes Flask app, SocketIO, SQLAlchemy (`db.init_app(app)`), and Flask-Migrate (`migrate.init_app(app, db)`).
    - New templates: `sidebar_content.html`, `item_detail.html`.
    - Routes:
        - `/`: Main page with sidebar item listing.
        - `/item/<int:item_id>`: Displays KB item details, parses `kb_media_paths` from DB to generate media URLs using `serve_kb_media` route.
        - `/serve_kb_media/<path:path>`: Serves media from `kb-generated` directory.
    - SocketIO Handlers:
        - `connect`: Emits `initial_status_and_git_config` with current agent state (running status, phase, preferences) for multi-client UI sync.
        - `run_agent`, `stop_agent`.
    - GPU Stats: Starts a background thread (`gpu_stats_emitter_thread`) to periodically fetch (via `gpu_utils.py`) and emit GPU stats via `'gpu_stats_update'` event.
  - **Interaction**: Determines `PROJECT_ROOT` on startup, calls `sg_set_project_root()`. Uses `sg_get_project_root()` for path needs. Instantiates `KnowledgeBaseAgent`.

- **`file_utils.py`, `naming_utils.py`, `path_utils.py`, `tweet_utils.py`**: (`validation.py` removed).
- **`prompts.py`**: (No major changes noted).
- **`types.py`**:
  - `KnowledgeBaseItem` (dataclass): Represents a fully processed knowledge base item. Its fields are:
    - `display_title: str` (The main title for the knowledge base item)
    - `description: str` (A brief description or abstract of the item)
    - `markdown_content: str` (The full content of the item in Markdown format)
    - `raw_json_content: str` (The structured JSON content generated by the LLM, from which Markdown is derived)
    - `category_info: CategoryInfo` (Holds `main_category`, `sub_category`, `item_name`, and a generated `description` for the category context)
    - `source_tweet: Dict[str, Any]` (The original tweet data object that was processed to create this item)
    - `kb_media_paths_rel_item_dir: str` (A JSON string representing a list of media file paths, e.g., `'["media/image.png"]'`, relative to the item's own directory)
    - `kb_item_path_rel_project_root: str` (The path to the item's main `README.md` file, relative to the project root)
    - `image_descriptions: List[str]` (List of descriptions for associated images, often from alt text or AI-generated analysis)
    - `created_at: datetime` (Timestamp indicating when the knowledge base item was created)
    - `last_updated: datetime` (Timestamp indicating when the item was last updated)

- **`models.py` (SQLAlchemy `KnowledgeBaseItem` model)**:
  - Updated to include `kb_media_paths` (JSON string, stores paths relative to the item's directory), `display_title`, `raw_json_content`. `file_path` stores the path to the `README.md` relative to `PROJECT_ROOT`.

- **NEW: `gpu_utils.py`**:
  - **Purpose**: Utility for fetching GPU statistics.
  - **Key Functions**: `get_gpu_stats()` (e.g., using `nvidia-smi`).
  - **Interaction**: Used by `web.py`.

- **NEW: `shared_globals.py`**:
  - **Purpose**: Provides globally accessible variables/functions.
  - **Key Content**: `stop_flag`, `_project_root` (internal), `sg_set_project_root(path: Path)`, `sg_get_project_root() -> Path`.
  - **Interaction**: Used by `web.py` (sets/gets project root), various modules check `stop_flag`.

## Key Interactions and Dependencies (Updated)

- **Agent as Central Hub**: `KnowledgeBaseAgent` in `agent.py` remains central.
- **Path Management**: `PROJECT_ROOT` is key. Determined at startup (`main.py`/`web.py`), set in `config.py` and `shared_globals.py`. `Config` class resolves relative paths to absolute. Other modules use `config` instance or `sg_get_project_root()`.
- **State Persistence (`StateManager` & `tweet_cache.json`)**: Now stores richer data for each item: `kb_item_path` (relative to project root), `kb_media_paths` (JSON string of media paths relative to item's dir), `display_title`, `raw_json_content`.
- **AI Integration**: `ai_categorization.py` (naming/categorization) and `kb_item_generator.py` (full content JSON & Markdown).
- **Content Output Pipeline**:
    1. `kb_item_generator.py`: Tweet Data -> LLM -> JSON Content -> Markdown String -> `KnowledgeBaseItem` (dataclass).
    2. `markdown_writer.py`: `KnowledgeBaseItem` (dataclass) -> Filesystem (Directories, `README.md`, Copied Media with relative links). Returns item dir path and relative media paths.
    3. `content_processor.py`: Updates `tweet_cache.json` with paths. Synchronizes to SQL DB (`KnowledgeBaseItem` model).
- **Database Model (`models.py`)**: Stores final, accessible version of KB item metadata, including paths for content and media.

## Implementation Plan for Extension and Refinement
_(This section seems generally up-to-date but should be reviewed against the new roles of `kb_item_generator.py` and `markdown_writer.py` for content quality and review mechanisms. The `State Management` refinement point about storing richer data is now largely implemented and should be reflected as such or updated for further goals)._

### Refining Core Logic
- **State Management**:
    - The `StateManager` now handles richer item data. Future refinements could focus on more robust partial processing state recovery.
- **Content Quality**:
    - Review mechanisms could involve editing `raw_json_content` via the UI and re-triggering Markdown generation (from JSON) and `markdown_writer.py` steps, rather than direct Markdown editing if the JSON is the source of truth for structure.

## Getting Started for New Developers
- **Path Management**: Understand how `PROJECT_ROOT` is set (`main.py`/`web.py` -> `config.py`, `shared_globals.py`) and how `Config` resolves paths.
- **Content Generation**: Follow the flow from `ContentProcessor` -> `kb_item_generator.py` (JSON and Markdown generation) -> `markdown_writer.py` (filesystem and media handling).

## Conclusion

This implementation plan provides an updated overview of the Knowledge Base Agent's design, logical flow, and module functionalities, reflecting recent refactoring for portability, enhanced KB item generation, multi-client state synchronization, and GPU monitoring. It serves as a roadmap for extending the agent's capabilities, refining its core logic, and aiding collaboration.