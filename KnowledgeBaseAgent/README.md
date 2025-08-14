# AI Agent Rebuild

A modern, scalable Knowledge Base AI Agent system built with FastAPI backend and React frontend.

## Project Structure

```
ai-agent-rebuild/
├── backend/                 # FastAPI backend application
│   ├── app/                # Application core
│   │   ├── main.py         # FastAPI app initialization
│   │   ├── config.py       # Configuration management
│   │   ├── database.py     # Database setup
│   │   ├── dependencies.py # Dependency injection
│   │   ├── middleware.py   # Custom middleware
│   │   └── tasks/          # Celery tasks
│   ├── api/                # API endpoints
│   │   └── v1/             # API version 1
│   ├── alembic/            # Database migrations
│   ├── tests/              # Test suite
│   ├── Dockerfile          # Docker configuration
│   └── requirements.txt    # Python dependencies
├── frontend/               # React frontend
├── docker-compose.yml      # Development environment
└── README.md              # This file
```

## Quick Start

### Prerequisites

- Docker and Docker Compose
- Python 3.11+ (for local development)
- Node.js 18+ (for frontend development)

### Development Setup

1. **Clone the repository and navigate to the project directory**

2. **Copy environment configuration:**
   ```bash
   cp backend/.env.example backend/.env
   ```

3. **Start the development environment:**
   ```bash
   docker compose up -d
   ```

   This will start:
   - PostgreSQL database with pgvector extension (port 5433)
   - Redis for caching and task queue (port 6380)
   - FastAPI backend API (port 8000)
   - Celery worker for background tasks
   - Celery beat scheduler for periodic tasks

4. **Start the frontend (separate terminal):**
   ```bash
   cd frontend
   npm install
   npm run dev
   ```

   Frontend: http://localhost:3000 (proxied to backend at 8000)

5. **Verify the setup:**
   - API health check: http://localhost:8000/health
   - API documentation: http://localhost:8000/docs
   - ReDoc documentation: http://localhost:8000/redoc

### Local Development (without Docker)

1. **Install Python dependencies:**
   ```bash
   cd backend
   pip install -r requirements.txt
   ```

2. **Set up local PostgreSQL and Redis:**
   - Install PostgreSQL with pgvector extension
   - Install Redis
   - Update `.env` file with local connection strings

3. **Run database migrations:**
   ```bash
   alembic upgrade head
   ```

4. **Start the FastAPI server:**
   ```bash
   uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
   ```

5. **Start Celery worker (in another terminal):**
   ```bash
   celery -A app.tasks.celery_app worker --loglevel=info
   ```

6. **Start Celery beat scheduler (in another terminal):**
   ```bash
   celery -A app.tasks.celery_app beat --loglevel=info
   ```

## Testing

Run backend tests:

```bash
cd backend
pytest
```

Run backend tests with coverage:
Run frontend tests:
```bash
cd frontend
npm run test
```

Run frontend tests with UI/coverage:
```bash
npm run test:ui
npm run test:coverage
```

## Frontend build & performance

The Vite config enables sourcemaps and manual chunks for code splitting (vendor/router/ui/state). To build:
```bash
cd frontend
npm run build
npm run preview
```

## Phase-specific models (optional env)

Defaults can be set via env or through the Settings page:
`PHASE_MODEL_VISION_*`, `PHASE_MODEL_KB_GENERATION_*`, `PHASE_MODEL_SYNTHESIS_*`, `PHASE_MODEL_CHAT_*`, `PHASE_MODEL_EMBEDDINGS_*`.


```bash
pytest --cov=app --cov-report=html
```

## API Endpoints

### System Health
- `GET /health` - Basic health check
- `GET /api/v1/system/health` - Comprehensive system health
- `GET /api/v1/system/metrics` - System resource metrics

### Agent Control (Placeholder)
- `POST /api/v1/agent/start` - Start AI agent processing
- `GET /api/v1/agent/status/{task_id}` - Get task status
- `POST /api/v1/agent/stop/{task_id}` - Stop running task
- `GET /api/v1/agent/history` - Get execution history

### Content Management (Placeholder)
- `GET /api/v1/content/items` - List content items
- `POST /api/v1/content/items` - Create content item
- `GET /api/v1/content/items/{id}` - Get content item
- `PUT /api/v1/content/items/{id}` - Update content item
- `DELETE /api/v1/content/items/{id}` - Delete content item
- `POST /api/v1/content/search` - Search content

### Knowledge Base (Placeholder)
- `GET /api/v1/knowledge/categories` - Get categories
- `GET /api/v1/knowledge/synthesis` - Get synthesis documents
- `POST /api/v1/knowledge/synthesis/generate` - Generate synthesis
- `GET /api/v1/knowledge/embeddings/search` - Vector search

### Chat Interface (Placeholder)
- `POST /api/v1/chat/sessions` - Create chat session
- `GET /api/v1/chat/sessions` - List chat sessions
- `GET /api/v1/chat/sessions/{id}/messages` - Get messages
- `POST /api/v1/chat/sessions/{id}/messages` - Send message

## Configuration

Key environment variables:

- `DATABASE_URL` - PostgreSQL connection string (default: localhost:5433)
- `REDIS_URL` - Redis connection string (default: localhost:6380)
- `SECRET_KEY` - Application secret key
- `DEBUG` - Enable debug mode
- `LOG_LEVEL` - Logging level (DEBUG, INFO, WARNING, ERROR)
- `ALLOWED_ORIGINS` - CORS allowed origins
- `DEFAULT_AI_BACKEND` - Default AI backend (ollama, localai, openai)

See `backend/.env.example` for all available configuration options.

## Troubleshooting

### Port Conflicts
If you encounter port conflicts when starting Docker Compose:

- **PostgreSQL (5432)**: The compose file uses port 5433 to avoid conflicts
- **Redis (6379)**: The compose file uses port 6380 to avoid conflicts
- **FastAPI (8000)**: Change the port mapping in docker-compose.yml if needed

Use the included `check_ports.py` script to diagnose port conflicts:
```bash
python3 check_ports.py
```

### Docker Permission Issues
If you get permission denied errors with Docker:
```bash
# Add your user to the docker group
sudo usermod -aG docker $USER
# Then log out and back in, or use sudo with docker commands
```

### Container Health Issues
Check container logs if services aren't starting:
```bash
# Check all services
docker compose ps

# Check specific service logs
docker compose logs api
docker compose logs worker
docker compose logs db
```

### Common Import Errors
The project uses modern versions of dependencies. If you encounter import errors:
- Pydantic v2: `BaseSettings` is now in `pydantic-settings`
- FastAPI: Middleware imports use `starlette.middleware.base`

## Development Status

This is the initial foundation implementation (Task 1) of the AI Agent Rebuild project. 

### ✅ Completed
- FastAPI project structure with proper directory organization
- Docker Compose development environment with PostgreSQL, Redis, and pgvector
- Configuration management with Pydantic settings and environment variables
- Database connection setup with SQLAlchemy and Alembic migrations
- Basic health check endpoints and logging configuration
- Unit tests for configuration and database connectivity
- Placeholder API endpoints for all major services

### 🚧 Next Steps (Upcoming Tasks)
- Database models and schema implementation (Task 2)
- Core API layer with CRUD operations (Task 3)
- AI backend abstraction layer (Task 4)
- Celery task queue infrastructure (Task 5)
- And more...

## Contributing

This project follows the implementation plan defined in `.kiro/specs/ai-agent-rebuild/tasks.md`. Each task builds incrementally on the previous ones.

## License

[Add your license information here]