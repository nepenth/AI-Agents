# Environment Variables in Knowledge Base Agent

This document explains all environment variables used in the Knowledge Base Agent and their current status.

## Core Configuration

| Variable | Description | Status |
|----------|-------------|--------|
| `OLLAMA_URL` | URL for Ollama API | Active, required |
| `VISION_MODEL` | Model name for vision tasks | Active, required |
| `TEXT_MODEL` | Model name for text generation | Active, required |
| `FALLBACK_MODEL` | Fallback model if primary fails | Active, required |
| `CATEGORIZATION_MODEL` | Model for AI categorization (lighter than TEXT_MODEL) | Active, optional (defaults to TEXT_MODEL) |
| `GPU_TOTAL_MEMORY` | Total GPU memory available in MB (e.g., 48000 for 48GB) | Active, optional |
| `TEXT_MODEL_THINKING` | Enable reasoning mode for supported models | Active, optional (default: false) |
| `CATEGORIZATION_MODEL_THINKING` | Enable reasoning mode for categorization model | Active, optional (default: false) |
| `OLLAMA_SUPPORTS_JSON_MODE` | Whether Ollama supports JSON mode | Active, optional (default: false) |

## GitHub Configuration

| Variable | Description | Status |
|----------|-------------|--------|
| `GITHUB_TOKEN` | GitHub personal access token | Active, required if `GIT_ENABLED=true` |
| `GITHUB_USER_NAME` | GitHub username | Active, required if `GIT_ENABLED=true` |
| `GITHUB_REPO_URL` | GitHub repository URL | Active, required if `GIT_ENABLED=true` |
| `GITHUB_USER_EMAIL` | GitHub user email | Active, required if `GIT_ENABLED=true` |
| `GIT_ENABLED` | Enable Git integration | Active, required |

## Directory Configuration 

| Variable | Description | Status |
|----------|-------------|--------|
| `KNOWLEDGE_BASE_DIR` | Path to KB output directory | Active, optional (default: kb-generated) |
| `CATEGORIES_FILE` | Path to categories JSON file | Active, optional (default: data/categories.json) |
| `BOOKMARKS_FILE` | Path to bookmarks JSON file | Active, optional (default: data/tweet_bookmarks.json) |
| `PROCESSED_TWEETS_FILE` | Path to processed tweets JSON | Active, optional (default: data/processed_tweets.json) |
| `UNPROCESSED_TWEETS_FILE` | Path to unprocessed tweets JSON | Active, optional (default: data/unprocessed_tweets.json) |
| `MEDIA_CACHE_DIR` | Path to media cache directory | Active, optional (default: data/media_cache) |
| `DATA_PROCESSING_DIR` | Path to data processing directory | Active, optional (default: data) |
| `TWEET_CACHE_FILE` | Path to tweet cache JSON | Active, optional (default: data/tweet_cache.json) |

## Logging Configuration

| Variable | Description | Status |
|----------|-------------|--------|
| `LOG_FILE` | Path to log file | Active, optional (default: agent_program.log) |
| `LOG_LEVEL` | Logging level (DEBUG, INFO, etc.) | Active, optional (default: INFO) |
| `LOG_DIR` | Directory for logs | Active, optional (default: logs/) |

## GPU Monitoring

| Variable | Description | Status |
|----------|-------------|--------|
| `ENABLE_GPU_STATS_MONITORING` | Enable GPU monitoring | Active, optional (default: false) |
| `GPU_STATS_INTERVAL` | Interval (seconds) between GPU stats | Active, optional (default: 5) |

## Request Settings

| Variable | Description | Status |
|----------|-------------|--------|
| `BATCH_SIZE` | Number of items to process in batch | Active, optional (default: 1) |
| `MAX_RETRIES` | Max retries for failed requests | Active, optional (default: 5) |
| `MAX_CONCURRENT_REQUESTS` | Maximum concurrent requests | Active, optional (default: 1) |
| `REQUEST_TIMEOUT` | HTTP request timeout in seconds | Active, optional (default: 180) |
| `RETRY_BACKOFF` | Enable exponential backoff | Active, optional (default: True) |
| `MAX_POOL_SIZE` | Maximum connection pool size | Active, optional (default: 1) |
| `RATE_LIMIT_REQUESTS` | Max requests per period | Active, optional (default: 100) |
| `RATE_LIMIT_PERIOD` | Rate limit period in seconds | Active, optional (default: 3600) |

## Content Processing Settings

| Variable | Description | Status |
|----------|-------------|--------|
| `MIN_CONTENT_LENGTH` | Minimum content length to process | Active, optional (default: 50) |
| `MAX_CONTENT_LENGTH` | Maximum content length | Active, optional (default: 5000) |
| `SUMMARY_LENGTH` | Length of generated summaries | Active, optional (default: 280) |
| `CONTENT_GENERATION_TIMEOUT` | Timeout for content generation | Active, optional (default: 300) |
| `CONTENT_RETRIES` | Number of retries for content generation | Active, optional (default: 3) |
| `PROCESS_VIDEOS` | Whether to process videos | Active, optional (default: True) |

## X/Twitter Settings

| Variable | Description | Status |
|----------|-------------|--------|
| `X_USERNAME` | X/Twitter username | Active, required |
| `X_PASSWORD` | X/Twitter password | Active, required |
| `X_BOOKMARKS_URL` | URL to your X/Twitter bookmarks | Active, required |
| `SELENIUM_TIMEOUT` | Timeout for Selenium operations | Active, optional (default: 30) |
| `SELENIUM_HEADLESS` | Run browser in headless mode | Active, optional (default: True) |

## Processing Phase Settings (Web UI Replaced)

These variables are no longer needed as they've been replaced by the web UI:

| Variable | Description | Status |
|----------|-------------|--------|
| `REPROCESS_MEDIA` | Force reprocess media | Replaced by web UI |
| `REPROCESS_CATEGORIES` | Force reprocess categories | Replaced by web UI |
| `REPROCESS_KB_ITEMS` | Force regenerate KB items | Replaced by web UI |
| `REGENERATE_ROOT_README` | Force regenerate main README | Replaced by web UI |
| `FORCE_RECACHE_TWEETS` | Force re-cache all tweets | Replaced by web UI |

## Web UI Controls

The web UI now provides these controls:

1. **Skip Options**:
   - Skip Fetching New Bookmarks
   - Skip Processing Content
   - Skip README Regeneration
   - Skip Push to Git

2. **Force Options**:
   - Force Re-cache Tweet Data
   - Force Re-analyze Media + Subsequent Phases
   - Force Re-run LLM Processing + Subsequent Phases
   - Force Regenerate KB Items + DB Sync 