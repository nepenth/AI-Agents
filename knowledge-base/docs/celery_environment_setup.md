# Celery Environment Setup

## Environment Configuration for Celery Migration

Copy the following configuration to your `.env` file in the project root:

```bash
# =============================================================================
# CELERY CONFIGURATION (NEW)
# =============================================================================
# Celery Broker and Backend
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/0
CELERY_TASK_SERIALIZER=json
CELERY_ACCEPT_CONTENT=["json"]
CELERY_RESULT_SERIALIZER=json

# Redis Configuration for Progress/Logs
REDIS_PROGRESS_URL=redis://localhost:6379/1
REDIS_LOGS_URL=redis://localhost:6379/2

# Enhanced Task Configuration
CELERY_TASK_TRACK_STARTED=true
CELERY_TASK_TIME_LIMIT=7200
CELERY_WORKER_PREFETCH_MULTIPLIER=1

# Feature Flag - Enable Celery instead of multiprocessing
USE_CELERY=false
```

## Redis Setup

Before using Celery, ensure Redis is installed and running:

```bash
# Ubuntu/Debian
sudo apt-get install redis-server
sudo systemctl start redis
sudo systemctl enable redis

# macOS
brew install redis
brew services start redis

# Docker
docker run -d -p 6379:6379 redis:7-alpine
```

## Configuration Fields Added to config.py

The following new configuration fields have been added to the `Config` class:

- `celery_broker_url`: Redis URL for the Celery broker
- `celery_result_backend`: Redis URL for storing task results
- `celery_task_serializer`: Serialization format for tasks (json)
- `celery_accept_content`: Accepted content types
- `celery_result_serializer`: Serialization format for results
- `redis_progress_url`: Redis database for progress tracking
- `redis_logs_url`: Redis database for log streaming
- `celery_task_track_started`: Enable task start tracking
- `celery_task_time_limit`: Maximum task execution time (2 hours)
- `celery_worker_prefetch_multiplier`: Worker prefetch settings
- `use_celery`: Feature flag to enable Celery (defaults to false)

## Next Steps

1. Install Redis on your system or use Docker
2. Add the Celery configuration to your `.env` file
3. Keep `USE_CELERY=false` until the migration is complete
4. Continue with Phase 1.3: Celery Application Setup 