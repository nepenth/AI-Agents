# Knowledge Base Agent 🤖📚

An intelligent agent for automatically building and maintaining a structured technical knowledge base from Twitter/X bookmarks. The agent processes tweets, extracts valuable technical content, and organizes it into a searchable Markdown-based knowledge repository.

# Key Features ✨

# Automated Content Processing
- 🧠 AI-powered categorization using Ollama models
- 🖼️ Media analysis and description generation
- 📂 Automatic directory structure management

# Intelligent Organization
- 🏷️ Two-level hierarchical categorization (e.g., programming/python)
- 🔄 Dynamic category suggestions and validation
- 📈 Automatic index generation

# Enterprise-Grade Operations
- 🔒 State management with atomic writes
- ♻️ Idempotent processing with content caching
- 🤖 Headless browser integration for content fetching
- 🔄 GitHub synchronization with conflict resolution

# Advanced Capabilities
- 📊 Processing statistics and metrics
- 🚦 Comprehensive error handling with retries
- 🔍 Content validation and sanitization
- 📝 Automatic Markdown generation with semantic linking

## Core Features

- **Automated Content Processing**
  - Fetches and processes bookmarked tweets
  - Extracts text, media, and embedded links
  - Analyzes images using AI vision models
  - Generates comprehensive technical summaries

- **Intelligent Categorization**
  - Uses AI to categorize content into technical domains
  - Maintains consistent naming conventions
  - Supports hierarchical organization (categories/subcategories)
  - Learns from existing categorizations

- **Knowledge Base Management**
  - Generates structured Markdown files
  - Maintains a central README index
  - Handles media attachments and references
  - Preserves original sources and context

- **Smart Processing**
  - Caches processed content for efficiency
  - Tracks processing state and progress
  - Supports incremental updates
  - Handles rate limiting and retries

## Technical Requirements

### Core Dependencies
- Python 3.8+
- Ollama for AI inference
- Playwright for web interaction
- Git for version control

### Environment Variables

## Installation

1. Clone the repository
2. Install dependencies: `pip install -r requirements.txt`
3. Configure environment variables
4. Ensure Ollama is running with required models

## Usage

## Architecture

### Core Components

- **Agent**: Orchestrates the overall processing pipeline
- **State Manager**: Tracks processing state and progress
- **Category Manager**: Handles content organization
- **Markdown Writer**: Generates knowledge base files
- **HTTP Client**: Manages external API interactions
- **Playwright Fetcher**: Handles web content extraction

### Environment Variables
# API Configuration
- OLLAMA_URL=
- VISION_MODEL=
- TEXT_MODEL=
# GitHub Settings
- GITHUB_TOKEN=your_token
- GITHUB_USER_NAME=your_username
- GITHUB_USER_EMAIL=your_email
- GITHUB_REPO_URL=https://github.com/user/repo
# Processing Settings
- DATA_PROCESSING_DIR=data
- KNOWLEDGE_BASE_DIR=kb-generated
- MAX_CONTENT_LENGTH=5000
- BATCH_SIZE=1

### Processing Pipeline

1. **Bookmark Fetching**
   - Authenticates with Twitter/X
   - Retrieves latest bookmarks
   - Handles pagination and rate limits

2. **Content Extraction**
   - Processes tweet text and metadata
   - Downloads and processes media
   - Expands URLs and fetches link previews

3. **AI Processing**
   - Analyzes text using Ollama models
   - Processes images with LLaVA
   - Generates technical summaries

4. **Knowledge Organization**
   - Categorizes content using AI
   - Creates hierarchical structure
   - Maintains consistent naming

5. **Documentation Generation**
   - Creates Markdown files
   - Handles media attachments
   - Updates central index
   - Maintains source references

## Contributing

Contributions are welcome! Please follow these steps:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Make your changes
4. Run tests (`pytest`)
5. Submit a pull request

Please ensure your code:
- Follows PEP 8 style guide
- Includes appropriate tests
- Updates documentation as needed
- Maintains type hints and docstrings


## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgments

- Built with Ollama for AI inference
- Uses Playwright for robust web interaction
- Leverages LLaVA for vision tasks

## Quick Start Guide

1. Clone the repository
2. Install dependencies: `pip install -r requirements.txt`
3. Configure environment variables
4. Ensure Ollama is running with required models

## Detailed Configuration

```ini
# Core Services
OLLAMA_URL=http://localhost:11434
GITHUB_TOKEN=your_personal_access_token
GITHUB_REPO=yourusername/your-knowledge-base

# Processing Parameters
TEXT_MODEL=mistral:latest
VISION_MODEL=llava:latest
MAX_CONTENT_LENGTH=5000
PROCESS_MEDIA=true

# GitHub Sync
SYNC_TO_GITHUB=true
COMMIT_MESSAGE_PREFIX="KB Update: "
```

## Core Workflow

1. **Bookmark Ingestion**
   - Headless Twitter bookmark scraping
   - URL deduplication and validation
   - Atomic state tracking

2. **Content Processing**
   ```mermaid
   graph TD
     A[Tweet URL] --> B{In Cache?}
     B -->|Yes| C[Use Cached Data]
     B -->|No| D[Fetch with Playwright]
     D --> E[AI Categorization]
     E --> F[Media Analysis]
     F --> G[Markdown Generation]
     G --> H[GitHub Sync]
   ```

3. **Knowledge Base Structure**
   ```
   knowledge_base/
   └── <main_category>/
       ├── <sub_category>/
       │   └── <item_name>.md
       └── _index.md
   ```

## Advanced Usage

### Custom Category Management

Define custom categories in `config/categories.json`:

```json
{
  "machine_learning": {
    "description": "ML concepts and implementations",
    "subcategories": ["neural_nets", "transformers", "rl"],
    "keywords": ["llm", "pytorch", "tensorflow"]
  }
}
```

### Monitoring & Metrics

Access processing statistics through:

```python
from knowledge_base_agent import agent

async def show_stats():
    kb_agent = KnowledgeBaseAgent(config)
    print(await kb_agent.get_processing_metrics())
```

### Maintenance Commands

```bash
# Regenerate all indexes
python -m knowledge_base_agent rebuild-indexes

# Force reprocess all content
python -m knowledge_base_agent reprocess --all

# Clean temporary files
python -m knowledge_base_agent cleanup
```

## Error Handling & Recovery

The system implements:

- **Automatic Retries** (3 attempts with exponential backoff)
- **State Checkpointing**
- **Atomic Operations**
- **Detailed Error Logging** (see `logs/kb_agent_*.log`)

Common recovery scenarios:
```bash
# Reset failed processing state
python -m knowledge_base_agent reset-state --tweet <tweet_id>

# Repair Git synchronization
python -m knowledge_base_agent repair-git-state
```

## Security Considerations

1. **Secrets Management**
   - Never commit `.env` files
   - Use environment variables for sensitive data
   - Rotate GitHub tokens regularly

2. **Content Sanitization**
   - Automatic HTML/JS stripping
   - Media file type validation
   - Path traversal prevention

## Contribution Guidelines

We welcome contributions! Please see our:
- [Architecture Decision Records](/docs/architecture)
- [Testing Framework](/tests/README.md)
- [Style Guide](/docs/style_guide.md)

## Installation Commands

```bash
python -m pip install "git+https://github.com/yourrepo/knowledge-base-agent.git"
python -m playwright install
```