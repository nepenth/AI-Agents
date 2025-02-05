# Knowledge Base Agent

A tool to build and maintain a technical knowledge base by processing tweet content, categorizing it via AI, and generating a structured Markdown repository.

## Features

- **Tweet Processing:** Extracts tweet text and downloads associated images from tweet URLs
- **AI-Powered Categorization:** Uses an AI service (e.g., via an Ollama API) to determine a main category, subcategory, and a concise technical item name
- **Markdown Generation:** Generates individual Markdown files for each tweet and creates a root README that indexes all knowledge items
- **Git Integration:** Optionally pushes updates to a GitHub repository to version-control the knowledge base
- **Interactive Re-Categorization:** Allows manual re-review and reprocessing of existing items for improved categorization
- **Asynchronous Operations:** All network-bound operations (e.g., fetching tweets, calling AI services) are fully asynchronous
- **Refactored Architecture:** The project employs dependency injection, improved error handling with custom exceptions, enhanced configuration management, and a clear separation of I/O from business logic

## Requirements

- **Python:** Version 3.8 or higher
- **Playwright:** Browser binaries must be installed after dependency installation

## Setup

### 1. Set Up a Virtual Environment

It is highly recommended to create a Python virtual environment to isolate the project's dependencies.

```bash
python -m venv venv
```

Activate the virtual environment:

**On Windows:**
```bash
venv\Scripts\activate
```

**On macOS/Linux:**
```bash
source venv/bin/activate
```

### 2. Clone the Repository

```bash
git clone <repo_url>
cd knowledge_base_agent
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Install Playwright Browsers

```bash
playwright install
```

### 5. Configure Environment Variables

Create a `.env` file in the root directory (next to the `knowledge_base_agent/` folder) with the following content (adjust values as needed):

```env
# API endpoints and models
OLLAMA_URL=https://your-ollama-instance/api
VISION_MODEL=your_vision_model
TEXT_MODEL=your_text_model

# GitHub credentials (if using Git integration)
GITHUB_TOKEN=your_github_token
GITHUB_USER_NAME=your_github_username
GITHUB_USER_EMAIL=your_email@example.com
GITHUB_REPO_URL=https://github.com/youruser/yourrepo.git

# File paths (defaults provided if not set)
KNOWLEDGE_BASE_DIR=knowledge-base
CATEGORIES_FILE=data/categories.json
BOOKMARKS_FILE=data/bookmarks_links.txt
PROCESSED_TWEETS_FILE=data/processed_tweets.json

# Logging and other settings
LOG_LEVEL=DEBUG
BATCH_SIZE=5
MAX_RETRIES=3
```

### 6. Prepare Data Directories

The tool will automatically create necessary directories (like `knowledge-base` and the `data` folder) if they do not exist. However, ensure that you have or can create the following files:

- `data/categories.json`
- `data/bookmarks_links.txt`
- `data/processed_tweets.json`

### 7. Populate the Bookmarks File

Add tweet URLs (one per line) to the file specified by `BOOKMARKS_FILE` (by default, `data/bookmarks_links.txt`).

## Usage

Run the main program using:

```bash
python -m knowledge_base_agent.main
```

During execution, you will be prompted to:

- Reprocess tweets that have already been processed
- Interactively re-review existing knowledge base items
- Push changes to GitHub (if GitHub credentials are provided)

The process will:

- Fetch tweet data (text and images)
- Call AI services to generate category and naming suggestions
- Write the results to Markdown files in a hierarchical directory structure
- Update a root README that serves as an index to your knowledge base
- Optionally push changes to a GitHub repository

## Running Tests

The project includes tests written with Python's built-in `unittest` framework. To run all tests, execute:

```bash
python -m unittest discover tests
```

## Additional Information

- **Dependency Injection:** External service calls (e.g., HTTP requests) accept an injectable client to facilitate testing and future changes
- **Improved Error Handling:** The project uses custom exceptions (e.g., `KnowledgeBaseError`) and logs errors consistently
- **Configuration Management:** The configuration can be loaded from environment variables or (optionally) from a JSON file
- **Async Consistency:** All asynchronous operations use `asyncio` for network-bound tasks
- **Separation of I/O and Business Logic:** The codebase separates file I/O, state management, and Markdown generation from the core processing logic to improve testability and maintainability

## License

This project is licensed under the MIT License.