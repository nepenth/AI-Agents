# Knowledge Base Agent v2

This project implements an automated agent designed to process information (primarily sourced from Twitter/X bookmarks) and transform it into a structured, searchable knowledge base stored in Markdown format and synchronized with a Git repository and a local database.

## Features

*   **Automated Input Acquisition:** Fetches tweet IDs from Twitter/X bookmarks using Playwright.
*   **Tweet Processing Pipeline:** A multi-phase asynchronous pipeline processes each tweet:
    *   **Caching:** Fetches detailed tweet data (text, author, media) and caches media locally using `twscrape`.
    *   **Interpretation:** Generates descriptions for images using a multimodal LLM (via Ollama).
    *   **Categorization:** Determines appropriate knowledge base categories (`main`, `sub`, `item_name`) using an LLM (via Ollama).
    *   **Generation:** Creates a structured Markdown (`README.md`) entry for the item, incorporating tweet text, generated descriptions, and media, using an LLM (via Ollama).
*   **Knowledge Base Structure:** Organizes generated items into a hierarchical directory structure (`kb-generated/main_category/sub_category/item_name/`).
*   **Database Synchronization:** Stores metadata about each generated knowledge base item in a local SQLite database for quick access and querying.
*   **Web Interface:** Provides a Flask and SocketIO-based web UI for:
    *   Monitoring agent status (idle, running, stopping).
    *   Viewing real-time logs.
    *   Starting and stopping agent runs.
    *   Browsing the generated knowledge base items.
    *   Viewing individual item details (including the rendered `README.md`).
    *   Viewing logs from specific runs.
    *   Persisting UI settings (e.g., checkbox states).
*   **Command-Line Interface:** Offers a CLI for running the agent, suitable for scripting and headless operation.
*   **Git Synchronization:** Automatically commits and pushes the generated knowledge base (`kb-generated/` directory) to a configured remote Git repository.
*   **Configuration:** Uses `.env` files and Pydantic for flexible and validated configuration.
*   **Robust State Management:** Tracks the processing state of each tweet reliably using JSON files.
*   **Modular Architecture:** Built with clear separation of concerns between interfaces, processing logic, data types, and UI components.
*   **Asynchronous Core:** Leverages `asyncio` for efficient I/O-bound operations.

## Architecture Overview

The agent is built around a central `AgentPipeline` that orchestrates processing phases. Each phase interacts with external services (Ollama, Playwright, Git, Twitter via `twscrape`) through dedicated interface modules. State is managed by a `StateManager`, configuration is loaded via `config.py`, and logging is centralized in `log_setup.py`. A Flask/SocketIO application provides the web interface, while `main_cli.py` serves as the command-line entry point. Data is persisted in a local SQLite database (`database.py`) and state files (`data/`).

## Installation & Setup

1.  **Clone the Repository:**
    ```bash
    git clone <your-repo-url>
    cd knowledge-base_v2
    ```

2.  **Create and Activate Virtual Environment:**
    ```bash
    python -m venv .venv
    source .venv/bin/activate # On Linux/macOS
    # .\venv\Scripts\activate # On Windows
    ```

3.  **Install Dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

4.  **Install Playwright Browsers:**
    ```bash
    playwright install
    ```

5.  **Configure Environment Variables:**
    *   Copy the example environment file:
        ```bash
        cp .env.example .env
        ```
    *   Edit the `.env` file and fill in your specific details for:
        *   Ollama URLs and model names (`OLLAMA_URL`, `TEXT_MODEL`, `VISION_MODEL`, etc.)
        *   Filesystem paths (`KNOWLEDGE_BASE_DIR`, `DATA_DIR`, `LOG_DIR`)
        *   Twitter/X credentials and bookmark URL (if `FETCH_BOOKMARKS_ENABLED=true`)
        *   Git repository details and credentials (if `GIT_ENABLED=true`)
        *   Flask secret key (`FLASK_SECRET_KEY`)
        *   Database URL (`DATABASE_URL`)

6.  **Initialize Database (if running Web UI first):**
    The web application will attempt to create the database tables on startup. Ensure the directory specified in `DATABASE_URL` (e.g., `./data/`) exists.

## Configuration (`.env`)

Review the `.env.example` file for a detailed list of all configurable variables. Key settings include:

*   `OLLAMA_URL`, `TEXT_MODEL`, `VISION_MODEL`: Ollama connection and models.
*   `KNOWLEDGE_BASE_DIR`, `DATA_DIR`, `LOG_DIR`: Essential filesystem paths.
*   `FETCH_BOOKMARKS_ENABLED`, `X_USERNAME`, `X_PASSWORD`, `X_BOOKMARKS_URL`: Twitter/X bookmark fetching settings.
*   `GIT_ENABLED`, `GITHUB_TOKEN`, `GITHUB_USER_NAME`, `GITHUB_USER_EMAIL`, `GITHUB_REPO_URL`: Git synchronization settings.
*   `FLASK_SECRET_KEY`, `DATABASE_URL`: Web server and database settings.
*   `FORCE_RECACHE`: Whether to ignore cached data and re-fetch tweets.

## Usage

### Command-Line Interface (CLI)

Activate your virtual environment first (`source .venv/bin/activate`).

Run the agent pipeline:

```bash
python -m knowledge_base_agent.main_cli [options]
```

**Common Options:**

*   `--force-recache`: Force re-downloading and processing of all tweets.
*   `--skip-fetch`: Skip the bookmark fetching phase.
*   `--skip-git`: Skip the Git synchronization phase.
*   `--log-level [DEBUG|INFO|WARNING|ERROR|CRITICAL]`: Set console log level (default: INFO).

### Web Interface

Activate your virtual environment first (`source .venv/bin/activate`).

Start the web server:

```bash
python -m knowledge_base_agent.main_web
```

By default, the server runs on `http://0.0.0.0:5000`. Open this URL in your web browser.

The web UI allows you to:

*   View the agent's current status.
*   Start or stop pipeline runs using the controls.
*   See live log output in the "Logs" tab.
*   Browse generated knowledge base items under the "Knowledge Base" tab.
*   Select specific run logs using the dropdown in the "Logs" tab.

## Project Structure

```text
knowledge-base_v2/
│
├── knowledge_base_agent/    # Main Python package
│   ├── interfaces/      # External service interactions (Ollama, Playwright, Git, HTTP)
│   ├── processing/      # Core pipeline logic (phases, state, pipeline orchestrator)
│   ├── utils/           # Utility functions (file I/O, web, markdown)
│   ├── web/             # Web UI components (Flask routes, SocketIO handlers)
│   ├── config.py        # Configuration loading
│   ├── database.py      # Database models and session management
│   ├── exceptions.py    # Custom exceptions
│   ├── log_setup.py     # Logging configuration
│   ├── main_cli.py      # CLI entry point
│   ├── main_web.py      # Web server entry point
│   └── types.py         # Core data structures (Pydantic models)
│
├── data/                    # Runtime data (cache, state, database)
├── kb-generated/            # Output knowledge base files
├── logs/                    # Log files
├── static/                  # Web UI static assets (CSS, JS)
├── templates/               # Web UI HTML templates
├── .env                     # Local environment variables (ignored by git)
├── .env.example             # Example environment variables
├── implementation_plan.md   # Design document
├── requirements.txt         # Python dependencies
└── README.md                # This file
```

## Dependencies

Key Python libraries used:

*   Flask, Flask-SocketIO: Web framework and WebSocket communication.
*   SQLAlchemy, Flask-SQLAlchemy: Database ORM.
*   httpx, aiofiles: Asynchronous HTTP requests and file operations.
*   Pydantic: Data validation and settings management.
*   Playwright: Browser automation for bookmark fetching.
*   twscrape: Twitter scraping library.
*   GitPython: Interacting with Git repositories.
*   Markdown: Rendering Markdown content.

See `requirements.txt` for the full list.

## Contributing

(Optional: Add contribution guidelines here if applicable).

## License

(Optional: Add license information here, e.g., MIT License).
