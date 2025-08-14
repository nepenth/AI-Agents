"""
Content management endpoints for CRUD operations on content items.
"""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
import uuid
from datetime import datetime

from app.dependencies import get_database
from app.repositories.content import ContentItemRepository
from app.schemas.content import (
    ContentItemCreate,
    ContentItemUpdate,
    ContentItemResponse,
    ContentItemList,
    ContentItemFilter,
    ContentItemSearch,
    TwitterBookmarkCreate,
    TwitterThreadResponse,
    SubPhaseStatus,
    SubPhaseUpdate,
    MediaAnalysisResult,
    CollectiveUnderstandingResult,
    CategorizationResult,
)
from app.schemas.common import PaginationParams, PaginatedResponse, SuccessResponse, ErrorResponse

router = APIRouter()


@router.get("/health")
async def content_health():
    """Check content service health."""
    return {"status": "healthy", "service": "content"}


@router.get("/items", response_model=PaginatedResponse[ContentItemResponse])
async def get_content_items(
    pagination: PaginationParams = Depends(),
    source_type: Optional[str] = Query(None, description="Filter by source type"),
    processing_state: Optional[str] = Query(None, description="Filter by processing state"),
    main_category: Optional[str] = Query(None, description="Filter by main category"),
    sub_category: Optional[str] = Query(None, description="Filter by sub category"),
    has_media: Optional[bool] = Query(None, description="Filter by media presence"),
    created_after: Optional[str] = Query(None, description="Filter by creation date (ISO format)"),
    created_before: Optional[str] = Query(None, description="Filter by creation date (ISO format)"),
    db: AsyncSession = Depends(get_database)
):
    """Get all content items with optional filtering and pagination."""
    repo = ContentItemRepository(db)
    
    # Build filters
    filters = {}
    if source_type:
        filters['source_type'] = source_type
    if processing_state:
        filters['processing_state'] = processing_state
    if main_category:
        filters['main_category'] = main_category
    if sub_category:
        filters['sub_category'] = sub_category
    
    # Get items and total count
    items = await repo.find_by_filters(
        filters=filters,
        offset=pagination.offset,
        limit=pagination.size,
        order_by="created_at"
    )
    
    total = await repo.count(**filters)
    
    # Convert to response models
    response_items = []
    for item in items:
        item_dict = item.to_dict()
        response_items.append(ContentItemResponse(**item_dict))
    
    return PaginatedResponse.create(
        items=response_items,
        total=total,
        page=pagination.page,
        size=pagination.size
    )


@router.post("/items", response_model=ContentItemResponse, status_code=201)
async def create_content_item(
    item_data: ContentItemCreate,
    db: AsyncSession = Depends(get_database)
):
    """Create a new content item."""
    repo = ContentItemRepository(db)
    
    # Check if item with same source already exists
    existing_item = await repo.get_by_source(item_data.source_type, item_data.source_id)
    if existing_item:
        raise HTTPException(
            status_code=409,
            detail=f"Content item with source {item_data.source_type}:{item_data.source_id} already exists"
        )
    
    # Generate ID and create item
    item_id = str(uuid.uuid4())
    item = await repo.create(
        id=item_id,
        **item_data.model_dump()
    )
    
    # Convert to response model
    item_dict = item.to_dict()
    return ContentItemResponse(**item_dict)


@router.get("/items/{item_id}", response_model=ContentItemResponse)
async def get_content_item(
    item_id: str,
    db: AsyncSession = Depends(get_database)
):
    """Get a specific content item by ID."""
    repo = ContentItemRepository(db)
    
    item = await repo.get_by_id(item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Content item not found")
    
    # Convert to response model
    item_dict = item.to_dict()
    return ContentItemResponse(**item_dict)


@router.put("/items/{item_id}", response_model=ContentItemResponse)
async def update_content_item(
    item_id: str,
    update_data: ContentItemUpdate,
    db: AsyncSession = Depends(get_database)
):
    """Update a specific content item."""
    repo = ContentItemRepository(db)
    
    # Check if item exists
    if not await repo.exists(item_id):
        raise HTTPException(status_code=404, detail="Content item not found")
    
    # Update item
    item = await repo.update(item_id, **update_data.model_dump(exclude_unset=True))
    
    # Convert to response model
    item_dict = item.to_dict()
    return ContentItemResponse(**item_dict)


@router.delete("/items/{item_id}", response_model=SuccessResponse)
async def delete_content_item(
    item_id: str,
    db: AsyncSession = Depends(get_database)
):
    """Delete a specific content item."""
    repo = ContentItemRepository(db)
    
    # Check if item exists
    if not await repo.exists(item_id):
        raise HTTPException(status_code=404, detail="Content item not found")
    
    # Delete item
    success = await repo.delete(item_id)
    
    if not success:
        raise HTTPException(status_code=500, detail="Failed to delete content item")
    
    return SuccessResponse(
        message="Content item deleted successfully",
        timestamp=datetime.utcnow().isoformat()
    )


@router.post("/search", response_model=PaginatedResponse[ContentItemResponse])
async def search_content(
    search_params: ContentItemSearch,
    pagination: PaginationParams = Depends(),
    db: AsyncSession = Depends(get_database)
):
    """Search content items with various filters."""
    repo = ContentItemRepository(db)
    
    # Perform search
    items, total = await repo.search_content(
        query=search_params.query,
        filters=search_params.filters,
        offset=pagination.offset,
        limit=pagination.size
    )
    
    # Convert to response models
    response_items = []
    for item in items:
        item_dict = item.to_dict()
        response_items.append(ContentItemResponse(**item_dict))
    
    return PaginatedResponse.create(
        items=response_items,
        total=total,
        page=pagination.page,
        size=pagination.size
    )


@router.get("/stats")
async def get_content_stats(db: AsyncSession = Depends(get_database)):
    """Get content statistics."""
    repo = ContentItemRepository(db)
    
    processing_stats = await repo.get_processing_stats()
    category_stats = await repo.get_category_stats()
    source_stats = await repo.get_source_stats()
    total_count = await repo.count()
    
    return {
        "total_items": total_count,
        "processing_stats": processing_stats,
        "category_stats": category_stats,
        "source_stats": source_stats,
        "timestamp": datetime.utcnow().isoformat()
    }


@router.get("/categories")
async def get_categories(db: AsyncSession = Depends(get_database)):
    """Get all unique categories."""
    repo = ContentItemRepository(db)
    category_stats = await repo.get_category_stats()
    
    return {
        "categories": list(category_stats.keys()),
        "category_counts": category_stats,
        "total_categories": len(category_stats)
    }


@router.get("/source/{source_type}/{source_id}", response_model=ContentItemResponse)
async def get_content_by_source(
    source_type: str,
    source_id: str,
    db: AsyncSession = Depends(get_database)
):
    """Get content item by source type and ID."""
    repo = ContentItemRepository(db)
    
    item = await repo.get_by_source(source_type, source_id)
    if not item:
        raise HTTPException(
            status_code=404, 
            detail=f"Content item not found for source {source_type}:{source_id}"
        )
    
    # Convert to response model
    item_dict = item.to_dict()
    return ContentItemResponse(**item_dict)


# Twitter/X-specific endpoints
@router.post("/twitter/bookmark", response_model=ContentItemResponse, status_code=201)
async def create_twitter_bookmark(
    bookmark_data: TwitterBookmarkCreate,
    db: AsyncSession = Depends(get_database)
):
    """Create content item from Twitter/X bookmark."""
    repo = ContentItemRepository(db)
    
    # Check if bookmark already exists
    existing_item = await repo.get_by_source("twitter", bookmark_data.tweet_id)
    if existing_item and not bookmark_data.force_refresh:
        raise HTTPException(
            status_code=409,
            detail=f"Twitter bookmark {bookmark_data.tweet_id} already exists. Use force_refresh=true to update."
        )
    
    # TODO: Implement Twitter API integration to fetch tweet data
    # For now, create a placeholder that will be populated by the bookmark caching phase
    item_id = str(uuid.uuid4())
    
    if existing_item:
        # Update existing item
        item = await repo.update(existing_item.id, 
            bookmark_cached=False,  # Reset to trigger re-caching
            updated_at=datetime.utcnow()
        )
    else:
        # Create new item
        item = await repo.create(
            id=item_id,
            source_type="twitter",
            source_id=bookmark_data.tweet_id,
            tweet_id=bookmark_data.tweet_id,
            title=f"Twitter Bookmark {bookmark_data.tweet_id}",
            content="",  # Will be populated by bookmark caching
            processing_state="pending",
            bookmark_cached=False
        )
    
    # Convert to response model
    item_dict = item.to_dict()
    return ContentItemResponse(**item_dict)


@router.get("/twitter/thread/{thread_id}", response_model=TwitterThreadResponse)
async def get_twitter_thread(
    thread_id: str,
    db: AsyncSession = Depends(get_database)
):
    """Get all tweets in a Twitter/X thread."""
    repo = ContentItemRepository(db)
    
    # Get all items in the thread
    thread_items = await repo.find_by_filters(
        filters={"thread_id": thread_id, "source_type": "twitter"},
        order_by="position_in_thread"
    )
    
    if not thread_items:
        raise HTTPException(status_code=404, detail=f"Thread {thread_id} not found")
    
    # Convert to response models
    tweets = []
    for item in thread_items:
        item_dict = item.to_dict()
        tweets.append(ContentItemResponse(**item_dict))
    
    # Get thread metadata from root tweet
    root_tweet = next((t for t in tweets if t.is_thread_root), tweets[0])
    
    return TwitterThreadResponse(
        thread_id=thread_id,
        root_tweet_id=root_tweet.tweet_id,
        thread_length=len(tweets),
        tweets=tweets,
        author_username=root_tweet.author_username or "unknown",
        created_at=root_tweet.created_at,
        total_engagement=sum(t.total_engagement for t in tweets)
    )


@router.get("/twitter/threads", response_model=List[TwitterThreadResponse])
async def get_twitter_threads(
    limit: int = Query(default=20, le=100, description="Maximum number of threads to return"),
    db: AsyncSession = Depends(get_database)
):
    """Get all Twitter/X threads."""
    repo = ContentItemRepository(db)
    
    # Get all unique thread IDs
    thread_items = await repo.find_by_filters(
        filters={"source_type": "twitter", "thread_id__ne": None},
        limit=limit * 10  # Get more items to ensure we have enough threads
    )
    
    # Group by thread_id
    threads_dict = {}
    for item in thread_items:
        if item.thread_id not in threads_dict:
            threads_dict[item.thread_id] = []
        threads_dict[item.thread_id].append(item)
    
    # Convert to response models
    threads = []
    for thread_id, items in list(threads_dict.items())[:limit]:
        # Sort by position in thread
        items.sort(key=lambda x: x.position_in_thread or 0)
        
        tweets = []
        for item in items:
            item_dict = item.to_dict()
            tweets.append(ContentItemResponse(**item_dict))
        
        # Get thread metadata from root tweet
        root_tweet = next((t for t in tweets if t.is_thread_root), tweets[0])
        
        threads.append(TwitterThreadResponse(
            thread_id=thread_id,
            root_tweet_id=root_tweet.tweet_id,
            thread_length=len(tweets),
            tweets=tweets,
            author_username=root_tweet.author_username or "unknown",
            created_at=root_tweet.created_at,
            total_engagement=sum(t.total_engagement for t in tweets)
        ))
    
    return threads


# Sub-phase tracking endpoints
@router.get("/items/{item_id}/subphases", response_model=SubPhaseStatus)
async def get_subphase_status(
    item_id: str,
    db: AsyncSession = Depends(get_database)
):
    """Get sub-phase processing status for a content item."""
    repo = ContentItemRepository(db)
    
    item = await repo.get_by_id(item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Content item not found")
    
    return SubPhaseStatus(
        bookmark_cached=item.bookmark_cached,
        media_analyzed=item.media_analyzed,
        content_understood=item.content_understood,
        categorized=item.categorized,
        completion_percentage=item.sub_phase_completion_percentage,
        last_updated=item.updated_at
    )


@router.put("/items/{item_id}/subphases", response_model=SubPhaseStatus)
async def update_subphase_status(
    item_id: str,
    update_data: SubPhaseUpdate,
    db: AsyncSession = Depends(get_database)
):
    """Update sub-phase processing status for a content item."""
    repo = ContentItemRepository(db)
    
    item = await repo.get_by_id(item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Content item not found")
    
    # Validate phase name
    valid_phases = ["bookmark_cached", "media_analyzed", "content_understood", "categorized"]
    if update_data.phase not in valid_phases:
        raise HTTPException(
            status_code=400, 
            detail=f"Invalid phase. Must be one of: {', '.join(valid_phases)}"
        )
    
    # Update the specific phase
    update_fields = {update_data.phase: update_data.status}
    
    # Update model provenance if provided
    if update_data.model_used:
        if update_data.phase == "media_analyzed":
            update_fields["vision_model_used"] = update_data.model_used
        elif update_data.phase == "content_understood":
            update_fields["understanding_model_used"] = update_data.model_used
        elif update_data.phase == "categorized":
            update_fields["categorization_model_used"] = update_data.model_used
    
    # Update results if provided
    if update_data.results:
        if update_data.phase == "media_analyzed":
            update_fields["media_analysis_results"] = update_data.results
        elif update_data.phase == "content_understood":
            update_fields["collective_understanding"] = update_data.results.get("collective_understanding")
        elif update_data.phase == "categorized":
            update_fields["category_intelligence_used"] = update_data.results
            if "category" in update_data.results:
                update_fields["main_category"] = update_data.results["category"]
            if "subcategory" in update_data.results:
                update_fields["sub_category"] = update_data.results["subcategory"]
    
    # Update the item
    item = await repo.update(item_id, **update_fields)
    
    return SubPhaseStatus(
        bookmark_cached=item.bookmark_cached,
        media_analyzed=item.media_analyzed,
        content_understood=item.content_understood,
        categorized=item.categorized,
        completion_percentage=item.sub_phase_completion_percentage,
        last_updated=item.updated_at
    )


# CLI testing endpoints
@router.post("/test/phase/{phase_name}")
async def test_phase_processing(
    phase_name: str,
    item_id: str = Query(description="Content item ID to process"),
    force: bool = Query(default=False, description="Force processing even if already completed"),
    db: AsyncSession = Depends(get_database)
):
    """Test individual phase processing (for CLI testing)."""
    repo = ContentItemRepository(db)
    
    item = await repo.get_by_id(item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Content item not found")
    
    valid_phases = ["bookmark_caching", "media_analysis", "content_understanding", "categorization"]
    if phase_name not in valid_phases:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid phase. Must be one of: {', '.join(valid_phases)}"
        )
    
    # TODO: Implement actual phase processing logic
    # For now, return a test response
    return {
        "message": f"Phase {phase_name} processing initiated for item {item_id}",
        "item_id": item_id,
        "phase": phase_name,
        "force": force,
        "current_status": item.sub_phase_completion_status,
        "timestamp": datetime.utcnow().isoformat()
    }