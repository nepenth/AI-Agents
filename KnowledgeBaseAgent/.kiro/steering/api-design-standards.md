# API Design Standards

This document defines the standards and patterns for designing REST APIs in the AI Agent Backend system.

## General API Principles

### 1. RESTful Design
- Use standard HTTP methods (GET, POST, PUT, DELETE, PATCH)
- Resource-based URLs with clear hierarchies
- Stateless operations
- Consistent response formats

### 2. URL Structure
```
/api/v1/{resource}
/api/v1/{resource}/{id}
/api/v1/{resource}/{id}/{sub-resource}
```

**Examples:**
```
GET    /api/v1/content                    # List content items
POST   /api/v1/content                    # Create content item
GET    /api/v1/content/{id}               # Get specific content item
PUT    /api/v1/content/{id}               # Update content item
DELETE /api/v1/content/{id}               # Delete content item
GET    /api/v1/content/{id}/embeddings    # Get content embeddings

# Twitter/X-specific endpoints
GET    /api/v1/content/twitter/bookmarks  # Get Twitter/X bookmarks
GET    /api/v1/content/twitter/threads/{thread_id}  # Get thread visualization
GET    /api/v1/content/sub-phases/status  # Get sub-phase processing status
POST   /api/v1/content/sub-phases/{id}/reset  # Reset sub-phase status

# Seven-phase pipeline endpoints
POST   /api/v1/pipeline/phases/{phase}/execute  # Execute specific phase
GET    /api/v1/pipeline/status            # Get pipeline status
GET    /api/v1/pipeline/phases/{phase}/status  # Get phase-specific status
```

### 3. HTTP Status Codes
Use appropriate HTTP status codes:

- **200 OK**: Successful GET, PUT, PATCH
- **201 Created**: Successful POST
- **204 No Content**: Successful DELETE
- **400 Bad Request**: Invalid request data
- **401 Unauthorized**: Authentication required
- **403 Forbidden**: Insufficient permissions
- **404 Not Found**: Resource not found
- **409 Conflict**: Resource conflict
- **422 Unprocessable Entity**: Validation errors
- **500 Internal Server Error**: Server errors

## Request/Response Patterns

### 1. Request Models
Use Pydantic models for request validation:

```python
class ContentCreateRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=500)
    content: str = Field(..., min_length=1)
    source_url: Optional[str] = Field(default=None, regex=r'^https?://')
    content_type: str = Field(default="text", regex=r'^(text|markdown|html)$')
    tags: List[str] = Field(default_factory=list, max_items=10)
    metadata: Dict[str, Any] = Field(default_factory=dict)
```

### 2. Response Models
Consistent response structure with Twitter/X-specific fields:

```python
class ContentResponse(BaseModel):
    id: str
    title: str
    content: str
    source_url: Optional[str]
    content_type: str
    tags: List[str]
    metadata: Dict[str, Any]
    
    # Twitter/X-specific fields
    tweet_id: Optional[str]
    author_username: Optional[str]
    author_id: Optional[str]
    tweet_url: Optional[str]
    
    # Thread data
    thread_id: Optional[str]
    is_thread_root: bool
    position_in_thread: Optional[int]
    thread_length: Optional[int]
    
    # Engagement metrics
    like_count: Optional[int]
    retweet_count: Optional[int]
    reply_count: Optional[int]
    quote_count: Optional[int]
    total_engagement: int
    
    # Sub-phase processing states
    bookmark_cached: bool
    media_analyzed: bool
    content_understood: bool
    categorized: bool
    sub_phase_completion_percentage: float
    is_fully_processed: bool
    
    # Timestamps
    created_at: datetime
    updated_at: datetime
    processed_at: Optional[datetime]
    original_tweet_created_at: Optional[datetime]
    
    class Config:
        from_attributes = True

class TwitterBookmarkResponse(BaseModel):
    """Response schema for Twitter/X bookmark data."""
    id: str
    tweet_id: str
    author_username: str
    author_id: str
    tweet_url: str
    content: str
    thread_id: Optional[str]
    is_thread_root: bool
    thread_length: Optional[int]
    engagement_metrics: Dict[str, int]
    sub_phase_status: Dict[str, bool]
    created_at: str
    original_tweet_created_at: Optional[str]

class SubPhaseStatusResponse(BaseModel):
    """Response schema for sub-phase processing status."""
    content_id: str
    bookmark_cached: bool
    media_analyzed: bool
    content_understood: bool
    categorized: bool
    completion_percentage: float
    is_fully_processed: bool
    last_updated: str
    processing_errors: List[str]
```

### 2.1. Model Configuration Endpoints

New endpoints for model discovery and per-phase configuration:

```
GET    /api/v1/system/models/available
GET    /api/v1/system/models/config
PUT    /api/v1/system/models/config
```

Request/Response schemas:

```python
class PhaseLiteral(str, Enum):
    vision = "vision"
    kb_generation = "kb_generation"
    synthesis = "synthesis"
    chat = "chat"
    embeddings = "embeddings"

class PhaseModelSelector(BaseModel):
    backend: Literal['ollama','localai','openai']
    model: str
    params: Dict[str, Any] = Field(default_factory=dict)

class ModelsAvailableResponse(BaseModel):
    backends: Dict[str, Dict[str, Any]]  # {backend: {models: [...], capabilities: {model: ["vision","text","embed"]}}}

class ModelsConfigResponse(BaseModel):
    per_phase: Dict[PhaseLiteral, Optional[PhaseModelSelector]]

class ModelsConfigUpdateRequest(BaseModel):
    per_phase: Dict[PhaseLiteral, Optional[PhaseModelSelector]]
```

Standards:
- GET available: 200 OK with `ModelsAvailableResponse`
- GET config: 200 OK with `ModelsConfigResponse`
- PUT config: 200 OK on success; 400/422 for invalid backend/model or capability mismatch
- All endpoints require authentication; PUT requires `ADMIN_SYSTEM` or equivalent

### 3. List Responses
Standardized pagination and metadata:

```python
class ContentListResponse(BaseModel):
    items: List[ContentResponse]
    total: int
    page: int
    page_size: int
    has_next: bool
    has_previous: bool
```

### 4. Error Responses
Consistent error format:

```python
class ErrorResponse(BaseModel):
    error: str
    message: str
    details: Optional[Dict[str, Any]] = None
    timestamp: datetime
    request_id: str

# Example error response
{
    "error": "validation_error",
    "message": "Invalid request data",
    "details": {
        "field_errors": {
            "title": ["Field is required"],
            "content": ["Field must not be empty"]
        }
    },
    "timestamp": "2024-01-01T12:00:00Z",
    "request_id": "req_123456"
}
```

## Authentication and Authorization

### 1. Authentication Methods
Support multiple authentication methods:

```python
# JWT Bearer Token
Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...

# API Key
X-API-Key: ak_1234567890abcdef

# Both methods supported in endpoints
async def get_current_user_or_api_key(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)
) -> User:
    # Try JWT first, then API key
    pass
```

### 2. Permission Decorators
Use decorators for authorization:

```python
@router.get("/admin/users")
@admin_required
async def list_users(current_user: User = Depends(get_current_user)):
    pass

@router.post("/content")
@require_permissions([Permissions.CONTENT_CREATE])
async def create_content(
    content_data: ContentCreateRequest,
    current_user: User = Depends(get_current_user_or_api_key)
):
    pass
```

### 3. Security Headers
Include security headers in responses:

```python
# Middleware adds security headers
{
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "X-XSS-Protection": "1; mode=block",
    "Strict-Transport-Security": "max-age=31536000; includeSubDomains"
}
```

## Pagination and Filtering

### 1. Query Parameters
Standard query parameters for lists:

```python
@router.get("/content")
async def list_content(
    page: int = Query(default=1, ge=1, description="Page number"),
    page_size: int = Query(default=20, ge=1, le=100, description="Items per page"),
    search: Optional[str] = Query(default=None, description="Search query"),
    category: Optional[str] = Query(default=None, description="Filter by category"),
    tags: Optional[List[str]] = Query(default=None, description="Filter by tags"),
    sort_by: str = Query(default="created_at", description="Sort field"),
    sort_order: str = Query(default="desc", regex="^(asc|desc)$", description="Sort order"),
    created_after: Optional[datetime] = Query(default=None, description="Filter by creation date"),
    created_before: Optional[datetime] = Query(default=None, description="Filter by creation date")
):
    pass
```

### 2. Search Parameters
Standardized search functionality:

```python
class SearchRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=500)
    search_type: SearchType = Field(default=SearchType.HYBRID)
    filters: Dict[str, Any] = Field(default_factory=dict)
    limit: int = Field(default=20, ge=1, le=100)
    offset: int = Field(default=0, ge=0)
    include_embeddings: bool = Field(default=False)
    similarity_threshold: float = Field(default=0.7, ge=0.0, le=1.0)
```

### 3. Sorting and Ordering
Consistent sorting parameters:

```python
# URL: /api/v1/content?sort_by=title&sort_order=asc
# URL: /api/v1/content?sort_by=created_at&sort_order=desc

# Multiple sort fields
# URL: /api/v1/content?sort_by=category,created_at&sort_order=asc,desc
```

## Versioning Strategy

### 1. URL Versioning
Version in URL path:

```python
# Current version
/api/v1/content

# Future version
/api/v2/content

# Version-specific routers
app.include_router(v1_content.router, prefix="/api/v1/content")
app.include_router(v2_content.router, prefix="/api/v2/content")
```

### 2. Backward Compatibility
Maintain backward compatibility:

```python
# Add new optional fields
class ContentResponse(BaseModel):
    # Existing fields
    id: str
    title: str
    
    # New optional field (backward compatible)
    ai_summary: Optional[str] = None
    
    # Deprecated field (still included for compatibility)
    legacy_field: Optional[str] = Field(default=None, deprecated=True)
```

### 3. Deprecation Process
Clear deprecation process:

```python
@router.get("/content/legacy", deprecated=True)
async def get_content_legacy():
    """
    DEPRECATED: Use /api/v1/content instead.
    This endpoint will be removed in v2.0.
    """
    pass
```

## Real-time Features

### 1. WebSocket Endpoints
WebSocket for real-time updates:

```python
@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket_manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            # Handle WebSocket messages
    except WebSocketDisconnect:
        websocket_manager.disconnect(websocket)
```

WebSocket event conventions for model configuration:
- `settings.updated` payload: `{ "scope": "models", "per_phase": { ... } }`
- `agent.models_applied` payload: `{ "task_id": "...", "overrides": { ... } }`

### 2. Server-Sent Events
SSE for one-way real-time updates:

```python
@router.get("/events/stream")
async def event_stream(current_user: User = Depends(get_current_user)):
    async def generate():
        while True:
            # Get latest events
            events = await get_user_events(current_user.id)
            for event in events:
                yield f"data: {json.dumps(event)}\n\n"
            await asyncio.sleep(1)
    
    return StreamingResponse(generate(), media_type="text/plain")
```

### 3. Webhook Support
Webhook endpoints for external integrations:

```python
@router.post("/webhooks/content-updated")
async def content_updated_webhook(
    payload: WebhookPayload,
    signature: str = Header(..., alias="X-Webhook-Signature")
):
    # Verify webhook signature
    if not verify_webhook_signature(payload, signature):
        raise HTTPException(status_code=401, detail="Invalid signature")
    
    # Process webhook
    await process_content_update(payload)
    
    return {"status": "processed"}
```

## Seven-Phase Pipeline API Patterns

### 1. Phase Execution Endpoints
Endpoints for controlling the seven-phase pipeline:

```python
@router.post("/pipeline/phases/{phase}/execute")
async def execute_phase(
    phase: int,
    config: Optional[Dict[str, Any]] = None,
    force_reprocess: bool = False,
    current_user: User = Depends(get_current_user)
):
    """Execute a specific phase of the pipeline."""
    if phase not in range(1, 8):
        raise HTTPException(status_code=400, detail="Phase must be between 1 and 7")
    
    # Start phase execution
    task_id = await pipeline_service.execute_phase(phase, config, force_reprocess)
    
    return {
        "task_id": task_id,
        "phase": phase,
        "status": "started",
        "message": f"Phase {phase} execution started"
    }

@router.get("/pipeline/status")
async def get_pipeline_status(current_user: User = Depends(get_current_user)):
    """Get overall pipeline status."""
    status = await pipeline_service.get_pipeline_status()
    
    return {
        "overall_status": status.overall_status,
        "phases": {
            str(i): {
                "status": phase.status,
                "progress": phase.progress,
                "last_run": phase.last_run,
                "sub_phases": phase.sub_phases if hasattr(phase, 'sub_phases') else None
            }
            for i, phase in enumerate(status.phases, 1)
        },
        "active_tasks": status.active_tasks,
        "last_updated": status.last_updated
    }
```

### 2. Sub-Phase Management
Endpoints for managing sub-phase processing:

```python
@router.get("/content/sub-phases/status")
async def get_sub_phase_status(
    processing_state: Optional[str] = Query(None),
    incomplete_only: bool = Query(False),
    limit: int = Query(100, ge=1, le=500),
    current_user: User = Depends(get_current_user)
):
    """Get sub-phase processing status for content items."""
    items = await content_service.get_sub_phase_status(
        processing_state=processing_state,
        incomplete_only=incomplete_only,
        limit=limit
    )
    
    return [
        SubPhaseStatusResponse(
            content_id=item.id,
            bookmark_cached=item.bookmark_cached,
            media_analyzed=item.media_analyzed,
            content_understood=item.content_understood,
            categorized=item.categorized,
            completion_percentage=item.sub_phase_completion_percentage,
            is_fully_processed=item.is_fully_processed,
            last_updated=item.updated_at.isoformat(),
            processing_errors=[]  # TODO: Add error tracking
        )
        for item in items
    ]

@router.post("/content/sub-phases/{content_id}/reset")
async def reset_sub_phase_status(
    content_id: str,
    phases: List[str] = Query(..., description="Sub-phases to reset"),
    current_user: User = Depends(get_current_user)
):
    """Reset specific sub-phase processing status."""
    valid_phases = {"bookmark_cached", "media_analyzed", "content_understood", "categorized"}
    
    for phase in phases:
        if phase not in valid_phases:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid phase: {phase}. Valid phases: {valid_phases}"
            )
    
    await content_service.reset_sub_phase_status(content_id, phases)
    
    return {
        "message": f"Reset phases {phases} for content item {content_id}",
        "content_id": content_id,
        "reset_phases": phases
    }
```

### 3. Command-Line Testing Support
Endpoints specifically designed for CLI testing:

```python
@router.get("/cli/test-endpoints")
async def get_cli_test_endpoints(current_user: User = Depends(get_current_user)):
    """Get list of CLI-testable endpoints for command-line testing."""
    return {
        "message": "CLI-testable endpoints for seven-phase pipeline",
        "pipeline_endpoints": {
            "execute_phase": {
                "url": "/api/v1/pipeline/phases/{phase}/execute",
                "method": "POST",
                "description": "Execute specific pipeline phase",
                "example": "curl -X POST -H 'Authorization: Bearer TOKEN' '/api/v1/pipeline/phases/2/execute'"
            },
            "pipeline_status": {
                "url": "/api/v1/pipeline/status",
                "method": "GET",
                "description": "Get overall pipeline status",
                "example": "curl -H 'Authorization: Bearer TOKEN' '/api/v1/pipeline/status'"
            },
            "phase_status": {
                "url": "/api/v1/pipeline/phases/{phase}/status",
                "method": "GET",
                "description": "Get phase-specific status",
                "example": "curl -H 'Authorization: Bearer TOKEN' '/api/v1/pipeline/phases/3/status'"
            }
        },
        "content_endpoints": {
            "twitter_bookmarks": {
                "url": "/api/v1/content/twitter/bookmarks",
                "method": "GET",
                "description": "Get Twitter/X bookmarks with filtering",
                "example": "curl -H 'Authorization: Bearer TOKEN' '/api/v1/content/twitter/bookmarks?author=username&limit=10'"
            },
            "thread_visualization": {
                "url": "/api/v1/content/twitter/threads/{thread_id}",
                "method": "GET",
                "description": "Get thread visualization data",
                "example": "curl -H 'Authorization: Bearer TOKEN' '/api/v1/content/twitter/threads/thread123'"
            },
            "sub_phase_status": {
                "url": "/api/v1/content/sub-phases/status",
                "method": "GET",
                "description": "Get sub-phase processing status",
                "example": "curl -H 'Authorization: Bearer TOKEN' '/api/v1/content/sub-phases/status?incomplete_only=true'"
            }
        },
        "authentication": {
            "note": "All endpoints require authentication. Get token from /api/v1/auth/login",
            "login_example": "curl -X POST -H 'Content-Type: application/json' -d '{\"username\":\"user\",\"password\":\"pass\"}' '/api/v1/auth/login'"
        }
    }
```

## Background Tasks and Async Operations

### 1. Background Task Endpoints
Endpoints that trigger background tasks:

```python
@router.post("/content/{content_id}/process")
async def process_content(
    content_id: str,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user)
):
    # Start background processing
    task_id = str(uuid.uuid4())
    background_tasks.add_task(process_content_task, content_id, task_id)
    
    return {
        "task_id": task_id,
        "status": "started",
        "message": "Content processing started"
    }
```

### 2. Task Status Endpoints
Check background task status:

```python
@router.get("/tasks/{task_id}/status")
async def get_task_status(task_id: str):
    task_result = celery_app.AsyncResult(task_id)
    
    return {
        "task_id": task_id,
        "status": task_result.status,
        "result": task_result.result,
        "progress": task_result.info.get('progress', 0) if task_result.info else 0
    }
```

### 3. Streaming Responses
Stream large responses:

```python
@router.get("/content/{content_id}/export")
async def export_content(content_id: str):
    async def generate_export():
        # Stream large export data
        content = await get_content(content_id)
        yield json.dumps({"metadata": content.metadata}) + "\n"
        
        # Stream content in chunks
        for chunk in content.content_chunks:
            yield json.dumps({"chunk": chunk}) + "\n"
    
    return StreamingResponse(
        generate_export(),
        media_type="application/x-ndjson",
        headers={"Content-Disposition": "attachment; filename=export.jsonl"}
    )
```

## File Upload and Media Handling

### 1. File Upload Endpoints
Handle file uploads securely:

```python
@router.post("/content/upload")
async def upload_content(
    file: UploadFile = File(...),
    title: Optional[str] = Form(default=None),
    current_user: User = Depends(get_current_user)
):
    # Validate file
    if file.size > 10 * 1024 * 1024:  # 10MB limit
        raise HTTPException(status_code=413, detail="File too large")
    
    if file.content_type not in ["text/plain", "text/markdown", "application/json"]:
        raise HTTPException(status_code=415, detail="Unsupported file type")
    
    # Process file
    content = await file.read()
    processed_content = await process_uploaded_file(content, file.content_type)
    
    return {"message": "File uploaded successfully", "content_id": processed_content.id}
```

### 2. Media Serving
Serve media files with proper headers:

```python
@router.get("/media/{file_id}")
async def serve_media(file_id: str):
    file_info = await get_file_info(file_id)
    if not file_info:
        raise HTTPException(status_code=404, detail="File not found")
    
    return FileResponse(
        file_info.path,
        media_type=file_info.content_type,
        headers={
            "Cache-Control": "public, max-age=3600",
            "ETag": file_info.etag
        }
    )
```

### 3. File Validation
Comprehensive file validation:

```python
class FileValidator:
    ALLOWED_TYPES = {
        "text/plain": [".txt"],
        "text/markdown": [".md"],
        "application/json": [".json"],
        "image/jpeg": [".jpg", ".jpeg"],
        "image/png": [".png"]
    }
    
    MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB
    
    def validate_file(self, file: UploadFile) -> bool:
        # Check file size
        if file.size > self.MAX_FILE_SIZE:
            raise HTTPException(status_code=413, detail="File too large")
        
        # Check content type
        if file.content_type not in self.ALLOWED_TYPES:
            raise HTTPException(status_code=415, detail="Unsupported file type")
        
        # Check file extension
        file_ext = Path(file.filename).suffix.lower()
        allowed_extensions = self.ALLOWED_TYPES[file.content_type]
        if file_ext not in allowed_extensions:
            raise HTTPException(status_code=415, detail="Invalid file extension")
        
        return True
```

## Rate Limiting and Throttling

### 1. Rate Limiting Middleware
Implement rate limiting:

```python
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

@router.post("/content")
@limiter.limit("10/minute")
async def create_content(request: Request, content_data: ContentCreateRequest):
    pass
```

### 2. User-based Rate Limiting
Rate limiting per user:

```python
def get_user_id(request: Request) -> str:
    # Extract user ID from JWT token or API key
    return request.state.user_id

@router.post("/ai/generate")
@limiter.limit("5/minute", key_func=get_user_id)
async def generate_ai_content(request: Request):
    pass
```

### 3. Endpoint-specific Limits
Different limits for different endpoints:

```python
# High-frequency endpoints
@limiter.limit("100/minute")
async def list_content():
    pass

# Resource-intensive endpoints
@limiter.limit("5/minute")
async def generate_synthesis():
    pass

# Admin endpoints
@limiter.limit("1000/minute")
async def admin_operation():
    pass
```

## Monitoring and Observability

### 1. Request Logging
Log all API requests:

```python
@app.middleware("http")
async def log_requests(request: Request, call_next):
    start_time = time.time()
    
    # Log request
    logger.info(f"Request: {request.method} {request.url}")
    
    response = await call_next(request)
    
    # Log response
    process_time = time.time() - start_time
    logger.info(f"Response: {response.status_code} in {process_time:.3f}s")
    
    return response
```

### 2. Metrics Collection
Collect API metrics:

```python
from prometheus_client import Counter, Histogram

REQUEST_COUNT = Counter('api_requests_total', 'Total API requests', ['method', 'endpoint', 'status'])
REQUEST_DURATION = Histogram('api_request_duration_seconds', 'API request duration')

@app.middleware("http")
async def collect_metrics(request: Request, call_next):
    start_time = time.time()
    
    response = await call_next(request)
    
    # Record metrics
    REQUEST_COUNT.labels(
        method=request.method,
        endpoint=request.url.path,
        status=response.status_code
    ).inc()
    
    REQUEST_DURATION.observe(time.time() - start_time)
    
    return response
```

### 3. Health Check Endpoints
Comprehensive health checks:

```python
@router.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "version": "1.0.0"
    }

@router.get("/health/detailed")
async def detailed_health_check():
    checks = {
        "database": await check_database_health(),
        "redis": await check_redis_health(),
        "ai_service": await check_ai_service_health(),
        "celery": await check_celery_health()
    }
    
    overall_status = "healthy" if all(checks.values()) else "unhealthy"
    
    return {
        "status": overall_status,
        "checks": checks,
        "timestamp": datetime.utcnow().isoformat()
    }
```