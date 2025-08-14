# Seven-Phase Pipeline Testing Guide

This comprehensive guide outlines how to test each phase and component of the AI Agent seven-phase pipeline system.

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Environment Setup](#environment-setup)
3. [Phase-by-Phase Testing](#phase-by-phase-testing)
4. [Component Testing](#component-testing)
5. [Integration Testing](#integration-testing)
6. [CLI Testing Tools](#cli-testing-tools)
7. [Troubleshooting](#troubleshooting)

## Prerequisites

### Required Services
- PostgreSQL with pgvector extension
- Redis server
- Ollama/LocalAI/OpenAI-compatible AI service
- Twitter/X API access (for full testing)

### Required Python Packages
```bash
pip install -r requirements.txt
```

### Database Setup
```bash
# Run database migrations
alembic upgrade head

# Verify database connection
python -c "from app.database.connection import get_db_session; print('Database connected')"
```

## Environment Setup

### 1. Copy Environment File
```bash
cp .env.example .env
```

### 2. Essential Environment Variables

#### **Database Configuration** (Required)
```bash
DATABASE_URL=postgresql+asyncpg://aiagent_user:aiagent_password@localhost:5433/aiagent
DATABASE_ECHO=false
```

#### **Redis Configuration** (Required)
```bash
REDIS_URL=redis://localhost:6380
CELERY_BROKER_URL=redis://localhost:6380/0
CELERY_RESULT_BACKEND=redis://localhost:6380/0
```

#### **AI Backend Configuration** (Required)
Choose one of the following:

**Option A: Ollama (Recommended for local testing)**
```bash
AI_PROVIDER=ollama
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama2:7b
OLLAMA_EMBEDDING_MODEL=nomic-embed-text

# Per-phase model configuration (optional)
PHASE_MODEL_VISION_BACKEND=ollama
PHASE_MODEL_VISION_MODEL=llava:13b
PHASE_MODEL_KB_GENERATION_BACKEND=ollama
PHASE_MODEL_KB_GENERATION_MODEL=llama2:7b
PHASE_MODEL_SYNTHESIS_BACKEND=ollama
PHASE_MODEL_SYNTHESIS_MODEL=llama2:7b
PHASE_MODEL_CHAT_BACKEND=ollama
PHASE_MODEL_CHAT_MODEL=llama2:7b
PHASE_MODEL_EMBEDDINGS_BACKEND=ollama
PHASE_MODEL_EMBEDDINGS_MODEL=nomic-embed-text
```

**Option B: LocalAI**
```bash
AI_PROVIDER=localai
LOCALAI_BASE_URL=http://localhost:8080
LOCALAI_MODEL=gpt-3.5-turbo
LOCALAI_EMBEDDING_MODEL=text-embedding-ada-002
```

**Option C: OpenAI Compatible**
```bash
AI_PROVIDER=openai_compatible
OPENAI_API_KEY=your-api-key
OPENAI_BASE_URL=https://api.openai.com/v1
OPENAI_MODEL=gpt-3.5-turbo
OPENAI_EMBEDDING_MODEL=text-embedding-ada-002
```

#### **Twitter/X API Configuration** (Required for full testing)
```bash
X_API_KEY=your-twitter-api-key
X_API_SECRET=your-twitter-api-secret
X_BEARER_TOKEN=your-twitter-bearer-token
X_BOOKMARK_URL=https://api.twitter.com/2/users/me/bookmarks
```

#### **Git Sync Configuration** (Optional)
```bash
GIT_REPO_URL=https://github.com/yourusername/your-repo.git
GIT_BRANCH=main
GIT_USERNAME=your-git-username
GIT_PASSWORD=your-git-token-or-password
GIT_AUTO_PUSH=false  # Set to false for testing
```

### 3. Testing-Specific Variables
```bash
# Enable debug mode for testing
DEBUG=true
LOG_LEVEL=DEBUG

# Disable rate limiting for testing
RATE_LIMIT_ENABLED=false

# Enable all monitoring for testing
PIPELINE_MONITORING_ENABLED=true
AGENT_MONITORING_ENABLED=true
METRICS_ENABLED=true

# XML prompting validation
XML_PROMPT_VALIDATION_ENABLED=true
XML_OUTPUT_VALIDATION_ENABLED=true
```

## Phase-by-Phase Testing

### Phase 1: Initialization

#### Test System Initialization
```bash
# Using CLI tool
python cli_test_phases.py --phase 1

# Using API
curl -X POST "http://localhost:8000/api/v1/pipeline/phases/1/execute" \
  -H "Content-Type: application/json" \
  -d '{"config": {}}'
```

#### Required Environment Variables
```bash
DATABASE_URL=postgresql+asyncpg://...
REDIS_URL=redis://localhost:6380
AI_PROVIDER=ollama
OLLAMA_BASE_URL=http://localhost:11434
```

#### Expected Output
```json
{
  "phase": "1",
  "status": "completed",
  "message": "System initialization completed successfully",
  "components_status": {
    "database": true,
    "redis": true,
    "ai_service": true,
    "twitter_api": true
  }
}
```

### Phase 2: Fetch Bookmarks

#### Test Bookmark Fetching
```bash
# Using CLI tool
python cli_test_phases.py --phase 2 --config '{"bookmark_url": "https://api.twitter.com/2/users/me/bookmarks", "max_results": 10}'

# Using API
curl -X POST "http://localhost:8000/api/v1/pipeline/phases/2/execute" \
  -H "Content-Type: application/json" \
  -d '{
    "config": {
      "bookmark_url": "https://api.twitter.com/2/users/me/bookmarks",
      "max_results": 10,
      "force_refresh": false
    }
  }'
```

#### Required Environment Variables
```bash
X_API_KEY=your-twitter-api-key
X_API_SECRET=your-twitter-api-secret
X_BEARER_TOKEN=your-twitter-bearer-token
X_BOOKMARK_URL=https://api.twitter.com/2/users/me/bookmarks
X_API_TIMEOUT=30
X_API_MAX_RETRIES=3
```

#### Expected Output
```json
{
  "phase": "2",
  "status": "completed",
  "bookmarks_fetched": 10,
  "new_bookmarks": 8,
  "updated_bookmarks": 2
}
```

### Sub-Phase 2.1: Bookmark Caching

#### Test Bookmark Caching
```bash
# Test individual content item
python cli_test_phases.py --phase 2 --sub-phase 1 --content-ids "content-id-1,content-id-2"

# Using API
curl -X POST "http://localhost:8000/api/v1/content/sub-phases/bookmark-caching" \
  -H "Content-Type: application/json" \
  -d '{"content_ids": ["content-id-1", "content-id-2"], "force_refresh": false}'
```

#### Required Environment Variables
```bash
X_THREAD_DETECTION_ENABLED=true
X_THREAD_MAX_DEPTH=50
X_MEDIA_CACHE_ENABLED=true
X_MEDIA_MAX_SIZE=10485760
```

### Phase 3: Content Processing

#### Test Complete Content Processing
```bash
# Process all sub-phases
python cli_test_phases.py --phase 3 --content-ids "content-id-1,content-id-2"

# Test individual sub-phases
python cli_test_phases.py --phase 3 --sub-phase 1 --content-ids "content-id-1"  # Media Analysis
python cli_test_phases.py --phase 3 --sub-phase 2 --content-ids "content-id-1"  # Content Understanding
python cli_test_phases.py --phase 3 --sub-phase 3 --content-ids "content-id-1"  # Categorization
```

#### Sub-Phase 3.1: Media Analysis
```bash
# Using API
curl -X POST "http://localhost:8000/api/v1/content/sub-phases/media-analysis" \
  -H "Content-Type: application/json" \
  -d '{"content_ids": ["content-id-1"], "models_override": {"vision": {"backend": "ollama", "model": "llava:13b"}}}'
```

#### Required Environment Variables
```bash
# Vision model configuration
PHASE_MODEL_VISION_BACKEND=ollama
PHASE_MODEL_VISION_MODEL=llava:13b
XML_PROMPT_VALIDATION_ENABLED=true
```

#### Sub-Phase 3.2: Content Understanding
```bash
# Using API
curl -X POST "http://localhost:8000/api/v1/content/sub-phases/content-understanding" \
  -H "Content-Type: application/json" \
  -d '{"content_ids": ["content-id-1"]}'
```

#### Required Environment Variables
```bash
PHASE_MODEL_KB_GENERATION_BACKEND=ollama
PHASE_MODEL_KB_GENERATION_MODEL=llama2:7b
```

#### Sub-Phase 3.3: Categorization
```bash
# Using API
curl -X POST "http://localhost:8000/api/v1/content/sub-phases/categorization" \
  -H "Content-Type: application/json" \
  -d '{"content_ids": ["content-id-1"]}'
```

### Phase 4: Synthesis Generation

#### Test Synthesis Generation
```bash
# Using CLI tool
python cli_test_phases.py --phase 4

# Using API
curl -X POST "http://localhost:8000/api/v1/pipeline/phases/4/execute" \
  -H "Content-Type: application/json" \
  -d '{"config": {"min_bookmarks_per_category": 3}}'
```

#### Required Environment Variables
```bash
PHASE_MODEL_SYNTHESIS_BACKEND=ollama
PHASE_MODEL_SYNTHESIS_MODEL=llama2:7b
SYNTHESIS_ENABLED=true
SYNTHESIS_MIN_SOURCES=3
SYNTHESIS_MAX_SOURCES=20
```

### Phase 5: Embedding Generation

#### Test Embedding Generation
```bash
# Using CLI tool
python cli_test_phases.py --phase 5

# Using API
curl -X POST "http://localhost:8000/api/v1/pipeline/phases/5/execute" \
  -H "Content-Type: application/json" \
  -d '{}'
```

#### Required Environment Variables
```bash
PHASE_MODEL_EMBEDDINGS_BACKEND=ollama
PHASE_MODEL_EMBEDDINGS_MODEL=nomic-embed-text
VECTOR_DIMENSION=384
EMBEDDING_BATCH_SIZE=10
```

### Phase 6: README Generation

#### Test README Generation
```bash
# Using CLI tool
python cli_test_phases.py --phase 6

# Using API
curl -X POST "http://localhost:8000/api/v1/pipeline/phases/6/execute" \
  -H "Content-Type: application/json" \
  -d '{"config": {"include_statistics": true}}'
```

#### Required Environment Variables
```bash
PHASE_MODEL_KB_GENERATION_BACKEND=ollama
PHASE_MODEL_KB_GENERATION_MODEL=llama2:7b
```

### Phase 7: Git Sync

#### Test Git Sync
```bash
# Using CLI tool (with dry-run)
python cli_test_phases.py --phase 7 --config '{"dry_run": true}'

# Using API
curl -X POST "http://localhost:8000/api/v1/pipeline/phases/7/execute" \
  -H "Content-Type: application/json" \
  -d '{
    "config": {
      "git_repo_url": "https://github.com/yourusername/test-repo.git",
      "dry_run": true
    }
  }'
```

#### Required Environment Variables
```bash
GIT_REPO_URL=https://github.com/yourusername/your-repo.git
GIT_BRANCH=main
GIT_USERNAME=your-git-username
GIT_PASSWORD=your-git-token-or-password
GIT_AUTO_PUSH=false  # Set to false for testing
GIT_CLEANUP_TEMP_FILES=true
```

## Component Testing

### XML Prompting System

#### Test Prompt Generation
```python
# Test script
from app.services.xml_prompting_system import get_xml_prompting_system, PromptType

xml_system = get_xml_prompting_system()

# Test media analysis prompt
prompt = xml_system.create_media_analysis_prompt(
    media_url="https://example.com/image.jpg",
    media_type="image",
    tweet_context="This is a test tweet with an image",
    author_username="testuser"
)
print(prompt)
```

#### Required Environment Variables
```bash
XML_PROMPT_VALIDATION_ENABLED=true
XML_PROMPT_STRICT_MODE=false
XML_OUTPUT_VALIDATION_ENABLED=true
```

### Twitter/X API Client

#### Test Twitter Connection
```python
# Test script
import asyncio
from app.services.twitter_client import get_twitter_client, test_twitter_connection

async def test_twitter():
    result = await test_twitter_connection()
    print(result)

asyncio.run(test_twitter())
```

#### Required Environment Variables
```bash
X_API_KEY=your-twitter-api-key
X_API_SECRET=your-twitter-api-secret
X_BEARER_TOKEN=your-twitter-bearer-token
```

### Model Router

#### Test Model Resolution
```python
# Test script
import asyncio
from app.services.model_router import get_model_router
from app.services.model_settings import ModelPhase

async def test_model_router():
    router = get_model_router()
    
    # Test each phase
    for phase in ModelPhase:
        try:
            backend, model, params = await router.resolve(phase)
            print(f"{phase}: {backend.name} - {model}")
        except Exception as e:
            print(f"{phase}: Error - {e}")

asyncio.run(test_model_router())
```

### Database Connectivity

#### Test Database Connection
```python
# Test script
import asyncio
from app.database.connection import get_db_session

async def test_database():
    try:
        async with get_db_session() as db:
            result = await db.execute("SELECT 1")
            print("Database connection successful")
    except Exception as e:
        print(f"Database connection failed: {e}")

asyncio.run(test_database())
```

## Integration Testing

### Full Pipeline Test

#### Test Complete Pipeline
```bash
# Using CLI tool
python cli_test_phases.py --full-pipeline --config '{
  "bookmark_url": "https://api.twitter.com/2/users/me/bookmarks",
  "max_results": 5,
  "git_repo_url": "https://github.com/yourusername/test-repo.git",
  "dry_run": true
}'

# Using API
curl -X POST "http://localhost:8000/api/v1/pipeline/execute" \
  -H "Content-Type: application/json" \
  -d '{
    "config": {
      "bookmark_url": "https://api.twitter.com/2/users/me/bookmarks",
      "max_results": 5,
      "force_refresh": false,
      "git_repo_url": "https://github.com/yourusername/test-repo.git",
      "dry_run": true
    },
    "models_override": {
      "vision": {"backend": "ollama", "model": "llava:13b"},
      "kb_generation": {"backend": "ollama", "model": "llama2:7b"}
    }
  }'
```

### Pipeline Status Monitoring

#### Check Pipeline Status
```bash
# Get overall pipeline status
curl "http://localhost:8000/api/v1/pipeline/status"

# Get specific phase status
curl "http://localhost:8000/api/v1/pipeline/phases/3/status"

# Get sub-phase status
curl "http://localhost:8000/api/v1/content/sub-phases/status?incomplete_only=true"
```

### WebSocket Testing

#### Test Real-time Updates
```javascript
// JavaScript WebSocket test
const ws = new WebSocket('ws://localhost:8000/ws');

ws.onmessage = function(event) {
    const data = JSON.parse(event.data);
    console.log('Pipeline update:', data);
};

ws.onopen = function() {
    console.log('WebSocket connected');
    // Subscribe to pipeline updates
    ws.send(JSON.stringify({
        type: 'subscribe',
        channel: 'pipeline_progress'
    }));
};
```

## CLI Testing Tools

### Available CLI Commands

#### Phase Execution
```bash
# Execute specific phase
python cli_test_phases.py --phase 2 --config '{"max_results": 10}'

# Execute sub-phase
python cli_test_phases.py --phase 3 --sub-phase 1 --content-ids "id1,id2"

# Force reprocessing
python cli_test_phases.py --phase 3 --force-reprocess

# Get phase status
python cli_test_phases.py --status --phase 2
```

#### Content Management
```bash
# List content items
python cli_test_phases.py --list-content --category "machine-learning"

# Show content details
python cli_test_phases.py --show-content --content-id "content-id-1"

# Reset sub-phase status
python cli_test_phases.py --reset-subphase --content-id "content-id-1" --phases "media_analyzed,categorized"
```

#### System Information
```bash
# Show system status
python cli_test_phases.py --system-status

# List available models
python cli_test_phases.py --list-models

# Test AI connectivity
python cli_test_phases.py --test-ai
```

## Troubleshooting

### Common Issues and Solutions

#### 1. Database Connection Issues
```bash
# Check database status
python -c "from app.database.connection import get_db_session; print('DB OK')"

# Run migrations
alembic upgrade head

# Check environment variables
echo $DATABASE_URL
```

#### 2. AI Service Connection Issues
```bash
# Test Ollama connection
curl http://localhost:11434/api/tags

# Test LocalAI connection
curl http://localhost:8080/v1/models

# Check AI service logs
python cli_test_phases.py --test-ai --verbose
```

#### 3. Twitter/X API Issues
```bash
# Test Twitter API connection
python -c "
import asyncio
from app.services.twitter_client import test_twitter_connection
print(asyncio.run(test_twitter_connection()))
"

# Check API credentials
echo $X_BEARER_TOKEN | head -c 20
```

#### 4. Redis/Celery Issues
```bash
# Test Redis connection
redis-cli ping

# Check Celery workers
celery -A app.tasks.celery_app worker --loglevel=info

# Monitor Celery tasks
celery -A app.tasks.celery_app flower
```

#### 5. Phase Execution Failures

**Check Phase Dependencies:**
```bash
# Verify Phase 2 completion before Phase 3
python cli_test_phases.py --status --phase 2

# Check sub-phase completion
curl "http://localhost:8000/api/v1/content/sub-phases/status?incomplete_only=true"
```

**Check Model Availability:**
```bash
# List available models
curl "http://localhost:8000/api/v1/system/models/available"

# Check model configuration
curl "http://localhost:8000/api/v1/system/models/config"
```

**Check Content Processing Status:**
```bash
# Get processing statistics
curl "http://localhost:8000/api/v1/content/stats"

# Check for processing errors
python cli_test_phases.py --show-errors --phase 3
```

### Debug Mode Testing

#### Enable Debug Logging
```bash
# In .env file
DEBUG=true
LOG_LEVEL=DEBUG
LOG_TO_FILE=true
LOG_FILE_PATH=./logs/debug.log

# Run with verbose output
python cli_test_phases.py --phase 3 --verbose --debug
```

#### Monitor Real-time Logs
```bash
# Follow application logs
tail -f ./logs/debug.log

# Monitor specific component
grep "twitter_client" ./logs/debug.log | tail -20
```

### Performance Testing

#### Load Testing
```bash
# Test with multiple concurrent requests
for i in {1..5}; do
  curl -X POST "http://localhost:8000/api/v1/pipeline/phases/3/execute" \
    -H "Content-Type: application/json" \
    -d '{"config": {"content_ids": ["test-'$i'"]}}' &
done
wait
```

#### Memory and CPU Monitoring
```bash
# Monitor system resources during testing
htop

# Monitor Python process
ps aux | grep python

# Check memory usage
python -c "
import psutil
process = psutil.Process()
print(f'Memory: {process.memory_info().rss / 1024 / 1024:.2f} MB')
"
```

## Test Data Setup

### Create Test Content
```python
# Create test content script
import asyncio
from app.database.connection import get_db_session
from app.repositories.content import get_content_repository

async def create_test_content():
    async with get_db_session() as db:
        content_repo = get_content_repository()
        
        test_content = {
            "title": "Test Tweet Content",
            "content": "This is a test tweet for pipeline testing",
            "source_type": "twitter",
            "tweet_id": "test_tweet_123",
            "author_username": "testuser",
            "media_content": [{
                "id": "media_123",
                "type": "image",
                "url": "https://example.com/test.jpg"
            }]
        }
        
        item = await content_repo.create(db, test_content)
        print(f"Created test content: {item.id}")

asyncio.run(create_test_content())
```

This comprehensive testing guide provides everything needed to test each component and phase of the seven-phase pipeline system. Make sure to set up the required environment variables and services before running the tests.