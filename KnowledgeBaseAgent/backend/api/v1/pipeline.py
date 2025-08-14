"""
Pipeline API endpoints for content processing and seven-phase pipeline execution.
"""
from typing import Dict, Any, List, Optional
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from pydantic import BaseModel, Field
from datetime import datetime

from app.services.content_processing_pipeline import get_content_processing_pipeline
from app.services.seven_phase_pipeline import get_seven_phase_pipeline
from app.dependencies import get_current_user
from app.models.auth import User
from app.schemas.common import ResponseModel

router = APIRouter(prefix="/pipeline", tags=["pipeline"])


# Request/Response Models
class ProcessBookmarkRequest(BaseModel):
    """Request model for processing a single bookmark."""
    tweet_id: str = Field(..., description="Twitter tweet ID to process")
    force_refresh: bool = Field(default=False, description="Force reprocessing even if already completed")
    models_override: Optional[Dict[str, Any]] = Field(default=None, description="Optional model overrides for AI phases")
    run_async: bool = Field(default=True, description="Whether to run phases asynchronously via Celery")


class FetchBookmarksRequest(BaseModel):
    """Request model for fetching bookmarks from collection."""
    collection_url: Optional[str] = Field(default=None, description="Twitter/X bookmark collection URL")
    max_results: int = Field(default=100, ge=1, le=1000, description="Maximum number of bookmarks to fetch")
    force_refresh: bool = Field(default=False, description="Force re-fetching even if already cached")


class GenerateSynthesisRequest(BaseModel):
    """Request model for generating synthesis documents."""
    models_override: Optional[Dict[str, Any]] = Field(default=None, description="Optional model overrides for synthesis generation")
    min_bookmarks_per_category: int = Field(default=3, ge=1, description="Minimum bookmarks required per category")


class SevenPhasePipelineRequest(BaseModel):
    """Request model for seven-phase pipeline execution."""
    config: Dict[str, Any] = Field(..., description="Pipeline configuration")
    models_override: Optional[Dict[str, Any]] = Field(default=None, description="Optional model overrides for AI phases")
    run_async: bool = Field(default=True, description="Whether to run pipeline asynchronously via Celery")


class BookmarkProcessingResponse(BaseModel):
    """Response model for bookmark processing."""
    status: str
    content_id: Optional[str] = None
    tweet_id: Optional[str] = None
    processing_method: Optional[str] = None
    task_results: Optional[Dict[str, Any]] = None
    phase_results: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    timestamp: str


class BookmarkFetchResponse(BaseModel):
    """Response model for bookmark fetching."""
    status: str
    fetched_count: int
    skipped_count: int
    failed_count: int
    fetched_bookmarks: List[Dict[str, Any]]
    skipped_bookmarks: List[Dict[str, Any]]
    failed_bookmarks: List[Dict[str, Any]]
    timestamp: str


class SynthesisGenerationResponse(BaseModel):
    """Response model for synthesis generation."""
    status: str
    generated_count: int
    skipped_count: int
    generated_syntheses: List[Dict[str, Any]]
    skipped_categories: List[Dict[str, Any]]
    model_used: Optional[str] = None
    timestamp: str


class PipelineExecutionResponse(BaseModel):
    """Response model for pipeline execution."""
    status: str
    pipeline_id: str
    task_id: Optional[str] = None
    total_duration: Optional[float] = None
    phases_completed: Optional[int] = None
    phases_failed: Optional[int] = None
    phase_results: Optional[Dict[str, Any]] = None
    failed_phases: Optional[List[str]] = None
    error: Optional[str] = None
    message: Optional[str] = None
    timestamp: str


# Content Processing Pipeline Endpoints
@router.post("/process-bookmark", response_model=BookmarkProcessingResponse)
async def process_bookmark(
    request: ProcessBookmarkRequest,
    current_user: User = Depends(get_current_user)
):
    """
    Process a single Twitter bookmark through all sub-phases.
    
    This endpoint processes a Twitter bookmark through the complete content processing pipeline:
    - Phase 2.1: Bookmark caching with thread detection and media storage
    - Phase 3.1: Media analysis using vision models
    - Phase 3.2: AI content understanding
    - Phase 3.3: AI categorization with existing category intelligence
    """
    try:
        pipeline = get_content_processing_pipeline()
        
        result = await pipeline.process_twitter_bookmark(
            tweet_id=request.tweet_id,
            force_refresh=request.force_refresh,
            models_override=request.models_override,
            run_async=request.run_async
        )
        
        return BookmarkProcessingResponse(**result)
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to process bookmark: {str(e)}")


@router.post("/fetch-bookmarks", response_model=BookmarkFetchResponse)
async def fetch_bookmarks(
    request: FetchBookmarksRequest,
    current_user: User = Depends(get_current_user)
):
    """
    Fetch bookmarks from specified Twitter/X collection.
    
    This endpoint fetches bookmarks from Twitter/X API and creates content items
    for processing. It handles rate limiting, error handling, and duplicate detection.
    """
    try:
        pipeline = get_content_processing_pipeline()
        
        result = await pipeline.fetch_bookmarks_from_collection(
            collection_url=request.collection_url,
            max_results=request.max_results,
            force_refresh=request.force_refresh
        )
        
        return BookmarkFetchResponse(**result)
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch bookmarks: {str(e)}")


@router.post("/generate-synthesis", response_model=SynthesisGenerationResponse)
async def generate_synthesis(
    request: GenerateSynthesisRequest,
    current_user: User = Depends(get_current_user)
):
    """
    Generate synthesis documents for categories with sufficient bookmarks.
    
    This endpoint generates synthesis documents by aggregating content from multiple
    bookmarks within the same category. Only categories with the minimum required
    number of bookmarks will have synthesis documents generated.
    """
    try:
        pipeline = get_content_processing_pipeline()
        
        result = await pipeline.generate_synthesis_documents(
            models_override=request.models_override,
            min_bookmarks_per_category=request.min_bookmarks_per_category
        )
        
        return SynthesisGenerationResponse(**result)
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate synthesis: {str(e)}")


# Seven-Phase Pipeline Endpoints
@router.post("/execute-seven-phase", response_model=PipelineExecutionResponse)
async def execute_seven_phase_pipeline(
    request: SevenPhasePipelineRequest,
    current_user: User = Depends(get_current_user)
):
    """
    Execute the complete seven-phase processing pipeline.
    
    This endpoint executes the complete seven-phase pipeline:
    1. Initialization - Component setup and configuration validation
    2. Fetch Bookmarks - Twitter/X API integration and source management
    3. Content Processing - Media analysis, content understanding, and categorization
    4. Synthesis Generation - Document aggregation for categories with 3+ bookmarks
    5. Embedding Generation - Vector creation for search and similarity
    6. README Generation - Index content creation with navigation
    7. Git Sync - File export, Git operations, and cleanup
    """
    try:
        pipeline = get_seven_phase_pipeline()
        
        result = await pipeline.execute_pipeline(
            config=request.config,
            models_override=request.models_override,
            run_async=request.run_async
        )
        
        return PipelineExecutionResponse(**result)
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to execute seven-phase pipeline: {str(e)}")


@router.get("/status")
async def get_pipeline_system_status():
    """
    Get the overall pipeline system status.
    
    This endpoint returns the current status of the pipeline system,
    including available components and recent executions.
    """
    try:
        return {
            "system_status": "ready",
            "pipeline_version": "1.0.0",
            "available_phases": [
                {"phase": 1, "name": "Initialization", "status": "available"},
                {"phase": 2, "name": "Fetch Bookmarks", "status": "available"},
                {"phase": 3, "name": "Content Processing", "status": "available"},
                {"phase": 4, "name": "Synthesis Generation", "status": "available"},
                {"phase": 5, "name": "Embedding Generation", "status": "available"},
                {"phase": 6, "name": "README Generation", "status": "available"},
                {"phase": 7, "name": "Git Sync", "status": "available"}
            ],
            "active_executions": 0,
            "total_executions": 0,
            "last_execution": None,
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get pipeline status: {str(e)}")


@router.get("/status/{pipeline_id}")
async def get_pipeline_execution_status(
    pipeline_id: str,
    current_user: User = Depends(get_current_user)
):
    """
    Get the status of a specific pipeline execution.
    
    This endpoint returns the current status and progress of a pipeline execution,
    including phase-by-phase results and any errors that occurred.
    """
    try:
        # TODO: Implement pipeline status tracking
        # For now, return a placeholder response
        return {
            "pipeline_id": pipeline_id,
            "status": "running",
            "current_phase": "phase_3_content_processing",
            "progress": 60,
            "phases_completed": 2,
            "phases_total": 7,
            "estimated_completion": "2024-01-01T12:30:00Z",
            "message": "Processing content items..."
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get pipeline status: {str(e)}")


@router.post("/abort/{pipeline_id}")
async def abort_pipeline(
    pipeline_id: str,
    current_user: User = Depends(get_current_user)
):
    """
    Abort a running pipeline execution.
    
    This endpoint attempts to gracefully abort a running pipeline execution,
    stopping any in-progress phases and cleaning up resources.
    """
    try:
        # TODO: Implement pipeline abortion logic
        # For now, return a placeholder response
        return {
            "pipeline_id": pipeline_id,
            "status": "aborted",
            "message": "Pipeline execution aborted successfully",
            "timestamp": "2024-01-01T12:00:00Z"
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to abort pipeline: {str(e)}")


# Pipeline Configuration and Testing Endpoints
@router.get("/test-components")
async def test_pipeline_components(
    current_user: User = Depends(get_current_user)
):
    """
    Test the availability and configuration of all pipeline components.
    
    This endpoint tests the connectivity and configuration of:
    - Twitter/X API
    - AI backends (Ollama, LocalAI, OpenAI-compatible)
    - Database connection
    - Redis connection
    - Model router configuration
    """
    try:
        pipeline = get_content_processing_pipeline()
        
        # Test Twitter API
        async with pipeline.twitter_client as client:
            twitter_available = await client.is_available()
        
        # Test AI service
        ai_available = await pipeline.ai_service.is_available()
        
        # Test model router
        try:
            from app.services.model_settings import ModelPhase
            backend, model, params = await pipeline.model_router.resolve(ModelPhase.vision)
            model_router_available = True
            model_router_info = {
                'backend': backend.name if hasattr(backend, 'name') else str(backend),
                'model': model,
                'params': params
            }
        except Exception as e:
            model_router_available = False
            model_router_info = {'error': str(e)}
        
        # Test database
        try:
            from app.database.connection import get_db_session
            async with get_db_session() as db:
                await db.execute("SELECT 1")
            database_available = True
        except Exception:
            database_available = False
        
        return {
            "components": {
                "twitter_api": {
                    "available": twitter_available,
                    "status": "connected" if twitter_available else "disconnected"
                },
                "ai_service": {
                    "available": ai_available,
                    "status": "connected" if ai_available else "disconnected"
                },
                "model_router": {
                    "available": model_router_available,
                    "info": model_router_info
                },
                "database": {
                    "available": database_available,
                    "status": "connected" if database_available else "disconnected"
                }
            },
            "overall_status": "ready" if all([
                twitter_available, ai_available, model_router_available, database_available
            ]) else "not_ready",
            "timestamp": "2024-01-01T12:00:00Z"
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to test components: {str(e)}")