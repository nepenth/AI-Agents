# Backend Architecture Guidelines

This document provides steering guidelines for the AI Agent Backend system architecture and implementation patterns.

## System Overview

The AI Agent Backend is built as a modern, scalable FastAPI application focused on Twitter/X bookmark processing with the following core principles:

- **Seven-Phase Pipeline Architecture**: Systematic processing through Initialization, Fetch Bookmarks, Content Processing (with sub-phases), Synthesis Generation, Embedding Generation, README Generation, and Git Sync
- **Twitter/X-First Design**: Specialized for processing Twitter/X bookmarks with thread detection, media analysis, and engagement tracking
- **Sub-Phase Intelligence**: Intelligent processing logic with bookmark caching, media analysis, content understanding, and AI categorization sub-phases
- **Database-Driven Knowledge Base**: All content stored in unified database schema without flat file dependencies
- **AI-First Design**: Every component designed to work seamlessly with multi-provider AI processing (Ollama, LocalAI, OpenAI-compatible)
- **Real-time Communication**: WebSocket support for live pipeline progress and status updates
- **Command-Line Testable**: Full CLI testing capabilities for all phases and sub-phases
- **Microservice-Ready**: Modular design that can be easily split into microservices
- **Security-First**: Comprehensive authentication, authorization, and audit logging

## Architecture Layers

### 1. API Layer (`api/v1/`)
- **RESTful Endpoints**: Standard REST API design with proper HTTP methods
- **FastAPI Framework**: Leveraging FastAPI's automatic documentation and validation
- **Pydantic Models**: Request/response validation with clear schemas
- **Error Handling**: Consistent error responses with proper HTTP status codes

**Implementation Pattern:**
```python
@router.post("/items", response_model=ItemResponse)
async def create_item(
    item_create: ItemCreate,
    current_user: User = Depends(get_current_user)
):
    # Implementation here
    pass
```

### 2. Service Layer (`app/services/`)
- **Business Logic**: All business logic encapsulated in service classes
- **Async/Await**: Full async support for I/O operations
- **Dependency Injection**: Services use dependency injection pattern
- **Error Propagation**: Services raise specific exceptions for API layer handling

- **Model Routing Service**: Central `ModelRouter` resolves per-phase model/backend/params with capability validation and fallbacks

**Implementation Pattern:**
```python
class ContentService:
    async def create_content(self, content_data: ContentCreate) -> ContentItem:
        # Business logic implementation
        pass

def get_content_service() -> ContentService:
    # Singleton pattern for service instances
    pass
```

Model routing and settings services:
```python
class ModelPhase(str, Enum):
    vision = "vision"
    kb_generation = "kb_generation"
    synthesis = "synthesis"
    chat = "chat"
    embeddings = "embeddings"

class ModelSettingsService:
    async def get_config(self) -> Dict[str, Any]:
        ...
    async def set_config(self, per_phase: Dict[ModelPhase, dict]) -> Dict[str, Any]:
        ...
    async def list_available(self) -> Dict[str, Any]:
        ...

def get_model_router() -> ModelRouter:
    # DI factory returning singleton ModelRouter initialized with providers and settings service
    ...
```

### 3. Repository Layer (`app/repositories/`)
- **Data Access**: All database operations through repository pattern
- **SQLAlchemy Async**: Using async SQLAlchemy for database operations
- **Base Repository**: Common CRUD operations in base repository class
- **Transaction Management**: Proper transaction handling with context managers

- **Settings Repository**: Persist per-phase model config in database table `system_settings` or in a dedicated `model_settings` table; cache in Redis

**Implementation Pattern:**
```python
class ContentRepository(BaseRepository[ContentItem]):
    async def get_by_category(self, db: AsyncSession, category: str) -> List[ContentItem]:
        # Database query implementation
        pass
```

### 4. Model Layer (`app/models/`)
- **SQLAlchemy Models**: Database models with proper relationships
- **JSON Serialization**: Models include `to_dict()` methods for serialization
- **Timestamps**: All models include created_at/updated_at timestamps
- **Soft Deletes**: Important models support soft deletion

**Implementation Pattern:**
```python
class ContentItem(Base):
    __tablename__ = "content_items"
    
    id = Column(String, primary_key=True)
    # Other columns...
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            # Other fields...
        }
```

Twitter/X-specific database fields for content tracking:
- `content_items.tweet_id`, `author_username`, `author_id`, `tweet_url`
- `content_items.thread_id`, `is_thread_root`, `position_in_thread`, `thread_length`
- `content_items.like_count`, `retweet_count`, `reply_count`, `quote_count`, `total_engagement`
- Sub-phase processing states: `bookmark_cached`, `media_analyzed`, `content_understood`, `categorized`
- Media content: `media_content` (JSON), `media_analysis_results` (JSON)
- AI analysis: `collective_understanding` (JSON), `has_media_analysis`, `has_collective_understanding`

Provenance columns for phase model tracking:
- `content_items.vision_model_used` (Phase 3.1)
- `knowledge_items.generation_model_used` (Phase 3.2)
- `synthesis_documents.synthesis_model_used` (Phase 4)
- `content_items.embeddings_model_used` (Phase 5)

### 5. Schema Layer (`app/schemas/`)
- **Pydantic Models**: Request/response schemas with validation
- **Inheritance**: Base schemas for common patterns
- **Validation**: Custom validators for business rules
- **Documentation**: Clear field descriptions for API documentation

Include Pydantic schemas for model settings and available models as per API standards.

## Key Design Patterns

### 1. Dependency Injection
All services use the dependency injection pattern with global singleton instances:

```python
_service_instance: Optional[ServiceClass] = None

def get_service() -> ServiceClass:
    global _service_instance
    if _service_instance is None:
        _service_instance = ServiceClass()
    return _service_instance
```

### 2. Async Context Managers
Database operations use async context managers for proper resource management:

```python
async with get_db_session() as db:
    result = await repository.create(db, data)
    # Session automatically closed
```

### 3. Error Handling
Consistent error handling with custom exceptions:

```python
class BusinessLogicError(Exception):
    pass

# In API layer
try:
    result = await service.operation()
except BusinessLogicError as e:
    raise HTTPException(status_code=400, detail=str(e))
```

### 4. Background Tasks
Long-running operations use Celery for background processing:

```python
@celery_app.task
def process_content_task(content_id: str):
    # Background processing
    # Example: resolve and use per-phase models
    backend, model, params = await get_model_router().resolve(ModelPhase.vision)
    vision_text = await backend.generate_text(prompt, model=model, **params)
    # Save provenance: vision_model_used = model
```

## AI Integration Guidelines

### 1. AI Service Abstraction
- Use the AI service factory pattern for different AI providers
- All AI operations should be async
- Implement proper error handling for AI service failures
- Support for streaming responses where applicable

### 2. Seven-Phase Content Processing Pipeline
- **Phase 1 (Initialization)**: System setup, configuration validation, environment preparation
- **Phase 2 (Fetch Bookmarks)**: Twitter/X API integration with bookmark retrieval
  - **Sub-phase 2.1 (Bookmark Caching)**: Thread detection, media caching, ground-truth data storage
- **Phase 3 (Content Processing)**: Multi-stage AI analysis with three sub-phases
  - **Sub-phase 3.1 (Media Analysis)**: Vision model analysis of images/videos
  - **Sub-phase 3.2 (AI Content Understanding)**: Collective understanding generation
  - **Sub-phase 3.3 (AI Categorization)**: Category and sub-category assignment
- **Phase 4 (Synthesis Generation)**: AI-powered synthesis document creation
- **Phase 5 (Embedding Generation)**: Vector database population for semantic search
- **Phase 6 (README Generation)**: Dynamic README creation with navigation tree
- **Phase 7 (Git Sync)**: Repository export with markdown file generation

Each phase is independently testable and controllable with intelligent processing logic to avoid unnecessary reprocessing. All phases use `ModelRouter.resolve(phase)` for AI model selection and record provenance data.

### 3. Vector Search Integration
- All content automatically gets vector embeddings
- Search combines traditional text search with vector similarity
- Embeddings are cached and updated incrementally
- Support for different embedding models

## Security Guidelines

### 1. Authentication & Authorization
- JWT-based authentication with refresh tokens
- Role-based access control (RBAC) with permissions
- API key support for programmatic access
- Comprehensive audit logging for security events

### 2. Input Validation & Sanitization
- All user input is validated using Pydantic schemas
- HTML content is sanitized to prevent XSS attacks
- SQL injection prevention through parameterized queries
- File upload validation and virus scanning

### 3. Data Protection
- Sensitive data is encrypted at rest
- API keys and passwords are properly hashed
- Personal data handling follows privacy regulations
- Secure backup and recovery procedures

## Performance Guidelines

### 1. Database Optimization
- Proper indexing on frequently queried columns
- Connection pooling for database connections
- Query optimization with SQLAlchemy query analysis
- Pagination for large result sets

### 2. Caching Strategy
- Redis caching for frequently accessed data
- Application-level caching for expensive computations
- CDN integration for static content
- Cache invalidation strategies

### 3. Async Operations
- All I/O operations are async
- Background task processing for long operations
- WebSocket connections for real-time updates
- Proper resource cleanup and connection management

## Testing Guidelines

### 1. Test Structure
- Unit tests for individual components
- Integration tests for API endpoints
- End-to-end tests for complete workflows
- Performance tests for critical paths

### 2. Test Patterns
- Mock external dependencies (AI services, databases)
- Use fixtures for common test data
- Test both success and failure scenarios
- Maintain high test coverage (>80%)

### 3. Test Data Management
- Use factories for creating test data
- Clean up test data after each test
- Use separate test database
- Mock time-dependent operations

## Deployment Guidelines

### 1. Environment Configuration
- Use environment variables for configuration
- Separate configs for dev/staging/production
- Secure secret management
- Health check endpoints for monitoring

### 2. Scalability Considerations
- Stateless application design
- Horizontal scaling support
- Load balancer compatibility
- Database connection pooling

### 3. Monitoring & Logging
- Structured logging with correlation IDs
- Application metrics and monitoring
- Error tracking and alerting
- Performance monitoring and profiling

## Code Quality Standards

### 1. Code Style
- Follow PEP 8 Python style guidelines
- Use type hints for all function signatures
- Meaningful variable and function names
- Consistent naming conventions

### 2. Documentation
- Docstrings for all public functions and classes
- API documentation through FastAPI
- Architecture decision records (ADRs)
- Code comments for complex business logic

### 3. Code Review Process
- All code changes require review
- Automated testing before merge
- Security review for sensitive changes
- Performance impact assessment

## Migration and Compatibility

### 1. Database Migrations
- Use Alembic for database schema changes
- Backward compatible migrations when possible
- Data migration scripts for complex changes
- Rollback procedures for failed migrations

### 2. API Versioning
- Version API endpoints (/api/v1/, /api/v2/)
- Maintain backward compatibility
- Deprecation notices for old endpoints
- Clear migration paths for API consumers

### 3. Legacy System Integration
- Comprehensive migration tools
- Data validation and integrity checking
- Incremental migration support
- Rollback capabilities for failed migrations