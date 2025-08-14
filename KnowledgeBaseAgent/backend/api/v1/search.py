"""
Search API endpoints for vector and text search functionality.
"""

from fastapi import APIRouter, HTTPException, Query, Depends
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field

from app.services.vector_search import get_vector_search_service, SearchQuery, SearchType, SearchResult
from app.services.embedding_service import get_embedding_service
from app.repositories.knowledge import get_knowledge_repository
from app.database.connection import get_db_session

router = APIRouter()


class SearchRequest(BaseModel):
    """Search request model."""
    query: str = Field(..., description="Search query text")
    search_type: SearchType = Field(default=SearchType.HYBRID, description="Type of search to perform")
    limit: int = Field(default=10, ge=1, le=50, description="Maximum number of results")
    similarity_threshold: float = Field(default=0.7, ge=0.0, le=1.0, description="Minimum similarity threshold")
    categories: Optional[List[str]] = Field(default=None, description="Filter by categories")
    model_name: Optional[str] = Field(default=None, description="Specific embedding model to use")
    include_content: bool = Field(default=True, description="Include full content in results")


class SearchResultResponse(BaseModel):
    """Search result response model."""
    knowledge_item_id: str
    similarity_score: float
    chunk_text: str
    chunk_index: int
    rank: int
    knowledge_item: Optional[Dict[str, Any]] = None


class SearchResponse(BaseModel):
    """Search response model."""
    query: str
    search_type: str
    total_results: int
    results: List[SearchResultResponse]
    execution_time_ms: float


class SimilarItemsRequest(BaseModel):
    """Similar items request model."""
    knowledge_item_id: str = Field(..., description="ID of the knowledge item to find similar items for")
    limit: int = Field(default=10, ge=1, le=50, description="Maximum number of results")
    similarity_threshold: float = Field(default=0.8, ge=0.0, le=1.0, description="Minimum similarity threshold")


@router.post("/search", response_model=SearchResponse)
async def search_knowledge_base(request: SearchRequest):
    """
    Search the knowledge base using vector similarity and/or text search.
    """
    try:
        import time
        start_time = time.time()
        
        search_service = get_vector_search_service()
        
        # Create search query
        query = SearchQuery(
            query_text=request.query,
            search_type=request.search_type,
            limit=request.limit,
            similarity_threshold=request.similarity_threshold,
            categories=request.categories,
            model_name=request.model_name,
            include_content=request.include_content
        )
        
        # Perform search
        results = await search_service.search(query)
        
        # Convert to response format
        result_responses = []
        for result in results:
            knowledge_item_data = None
            if result.knowledge_item and request.include_content:
                knowledge_item_data = result.knowledge_item.to_dict()
            
            result_response = SearchResultResponse(
                knowledge_item_id=result.knowledge_item_id,
                similarity_score=result.similarity_score,
                chunk_text=result.chunk_text,
                chunk_index=result.chunk_index,
                rank=result.rank,
                knowledge_item=knowledge_item_data
            )
            result_responses.append(result_response)
        
        execution_time = (time.time() - start_time) * 1000  # Convert to milliseconds
        
        return SearchResponse(
            query=request.query,
            search_type=request.search_type.value,
            total_results=len(result_responses),
            results=result_responses,
            execution_time_ms=round(execution_time, 2)
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")


@router.get("/search", response_model=SearchResponse)
async def search_knowledge_base_get(
    q: str = Query(..., description="Search query"),
    search_type: SearchType = Query(default=SearchType.HYBRID, description="Search type"),
    limit: int = Query(default=10, ge=1, le=50, description="Maximum results"),
    threshold: float = Query(default=0.7, ge=0.0, le=1.0, description="Similarity threshold"),
    categories: Optional[str] = Query(default=None, description="Comma-separated categories"),
    model: Optional[str] = Query(default=None, description="Embedding model name"),
    include_content: bool = Query(default=False, description="Include full content")
):
    """
    Search the knowledge base using GET parameters (for simple queries).
    """
    # Parse categories
    category_list = None
    if categories:
        category_list = [cat.strip() for cat in categories.split(",") if cat.strip()]
    
    # Create request object
    request = SearchRequest(
        query=q,
        search_type=search_type,
        limit=limit,
        similarity_threshold=threshold,
        categories=category_list,
        model_name=model,
        include_content=include_content
    )
    
    return await search_knowledge_base(request)


@router.post("/similar", response_model=SearchResponse)
async def find_similar_items(request: SimilarItemsRequest):
    """
    Find items similar to a given knowledge item.
    """
    try:
        import time
        start_time = time.time()
        
        search_service = get_vector_search_service()
        
        # Find similar items
        results = await search_service.find_similar_items(
            request.knowledge_item_id,
            request.limit,
            request.similarity_threshold
        )
        
        # Convert to response format
        result_responses = []
        for result in results:
            knowledge_item_data = None
            if result.knowledge_item:
                knowledge_item_data = result.knowledge_item.to_dict()
            
            result_response = SearchResultResponse(
                knowledge_item_id=result.knowledge_item_id,
                similarity_score=result.similarity_score,
                chunk_text=result.chunk_text,
                chunk_index=result.chunk_index,
                rank=result.rank,
                knowledge_item=knowledge_item_data
            )
            result_responses.append(result_response)
        
        execution_time = (time.time() - start_time) * 1000
        
        return SearchResponse(
            query=f"Similar to item {request.knowledge_item_id}",
            search_type="vector_similarity",
            total_results=len(result_responses),
            results=result_responses,
            execution_time_ms=round(execution_time, 2)
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Similar items search failed: {str(e)}")


@router.get("/suggestions")
async def get_search_suggestions(
    q: str = Query(..., description="Partial query for suggestions"),
    limit: int = Query(default=5, ge=1, le=10, description="Maximum suggestions")
):
    """
    Get search suggestions based on partial query.
    """
    try:
        search_service = get_vector_search_service()
        suggestions = await search_service.get_search_suggestions(q, limit)
        
        return {
            "query": q,
            "suggestions": suggestions
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get suggestions: {str(e)}")


@router.get("/stats")
async def get_search_stats():
    """
    Get search system statistics and performance metrics.
    """
    try:
        search_service = get_vector_search_service()
        stats = await search_service.get_search_stats()
        
        return {
            "search_stats": stats,
            "timestamp": "2024-01-01T00:00:00Z"  # Would be actual timestamp
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get search stats: {str(e)}")


@router.post("/embeddings/generate/{knowledge_item_id}")
async def generate_embeddings_for_item(
    knowledge_item_id: str,
    model_name: Optional[str] = Query(default=None, description="Embedding model to use"),
    force_regenerate: bool = Query(default=False, description="Force regeneration of existing embeddings")
):
    """
    Generate embeddings for a specific knowledge item.
    """
    try:
        embedding_service = get_embedding_service()
        knowledge_repo = get_knowledge_repository()
        
        async with get_db_session() as db:
            # Get knowledge item
            knowledge_item = await knowledge_repo.get(db, knowledge_item_id)
            if not knowledge_item:
                raise HTTPException(status_code=404, detail="Knowledge item not found")
            
            # Generate embeddings
            embedding_results = await embedding_service.generate_embeddings_for_knowledge_item(
                knowledge_item, model_name, force_regenerate
            )
            
            # Save embeddings
            saved_embeddings = await embedding_service.save_embeddings(embedding_results)
            
            return {
                "knowledge_item_id": knowledge_item_id,
                "embeddings_generated": len(embedding_results),
                "embeddings_saved": len(saved_embeddings),
                "model_used": embedding_results[0].model if embedding_results else None,
                "embedding_dimension": embedding_results[0].embedding_dimension if embedding_results else None
            }
            
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate embeddings: {str(e)}")


@router.post("/embeddings/batch")
async def batch_generate_embeddings(
    knowledge_item_ids: List[str],
    model_name: Optional[str] = Query(default=None, description="Embedding model to use"),
    batch_size: int = Query(default=5, ge=1, le=20, description="Batch processing size")
):
    """
    Generate embeddings for multiple knowledge items in batch.
    """
    try:
        embedding_service = get_embedding_service()
        knowledge_repo = get_knowledge_repository()
        
        async with get_db_session() as db:
            # Get knowledge items
            knowledge_items = []
            for item_id in knowledge_item_ids:
                item = await knowledge_repo.get(db, item_id)
                if item:
                    knowledge_items.append(item)
            
            if not knowledge_items:
                raise HTTPException(status_code=404, detail="No valid knowledge items found")
            
            # Generate embeddings in batch
            batch_results = await embedding_service.batch_generate_embeddings(
                knowledge_items, model_name, batch_size
            )
            
            # Save all embeddings
            total_saved = 0
            for item_id, embedding_results in batch_results.items():
                if embedding_results:
                    saved_embeddings = await embedding_service.save_embeddings(embedding_results)
                    total_saved += len(saved_embeddings)
            
            return {
                "requested_items": len(knowledge_item_ids),
                "processed_items": len(knowledge_items),
                "total_embeddings_generated": sum(len(results) for results in batch_results.values()),
                "total_embeddings_saved": total_saved,
                "batch_results": {
                    item_id: len(results) for item_id, results in batch_results.items()
                }
            }
            
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Batch embedding generation failed: {str(e)}")


@router.delete("/embeddings/{knowledge_item_id}")
async def delete_embeddings_for_item(knowledge_item_id: str):
    """
    Delete all embeddings for a specific knowledge item.
    """
    try:
        knowledge_repo = get_knowledge_repository()
        
        async with get_db_session() as db:
            # Check if knowledge item exists
            knowledge_item = await knowledge_repo.get(db, knowledge_item_id)
            if not knowledge_item:
                raise HTTPException(status_code=404, detail="Knowledge item not found")
            
            # Delete embeddings
            deleted_count = await knowledge_repo.delete_embeddings_for_item(db, knowledge_item_id)
            
            return {
                "knowledge_item_id": knowledge_item_id,
                "embeddings_deleted": deleted_count
            }
            
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete embeddings: {str(e)}")