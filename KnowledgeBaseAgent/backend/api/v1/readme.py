"""
README generation and management API endpoints.
"""
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from app.models.readme import ReadmeContent
from app.services.readme_generator import get_readme_generator_service
from app.repositories.readme import get_readme_repository
from app.database.connection import get_db_session
from app.dependencies import get_current_user
from app.models.auth import User

router = APIRouter(prefix="/readme", tags=["readme"])


# Pydantic schemas
class ReadmeContentResponse(BaseModel):
    """Response schema for README content."""
    id: str
    content_type: str
    category: Optional[str]
    subcategory: Optional[str]
    title: str
    content: str
    item_count: int
    file_path: str
    content_hash: Optional[str]
    is_stale: bool
    generation_model_used: Optional[str]
    created_at: str
    updated_at: str
    
    class Config:
        from_attributes = True


class ReadmeGenerationRequest(BaseModel):
    """Request schema for README generation."""
    models_override: Optional[Dict[str, Any]] = None


class ReadmeListResponse(BaseModel):
    """Response schema for README content lists."""
    items: List[ReadmeContentResponse]
    total: int


@router.get("/", response_model=ReadmeListResponse)
async def list_readme_content(
    content_type: Optional[str] = Query(None, description="Filter by content type"),
    category: Optional[str] = Query(None, description="Filter by category"),
    subcategory: Optional[str] = Query(None, description="Filter by subcategory"),
    stale_only: bool = Query(False, description="Show only stale content"),
    current_user: User = Depends(get_current_user)
):
    """
    List README content with optional filtering.
    """
    readme_repo = get_readme_repository()
    
    async with get_db_session() as db:
        if stale_only:
            items = await readme_repo.get_stale_content(db)
        elif content_type:
            items = await readme_repo.get_by_type(db, content_type)
        elif category:
            items = await readme_repo.get_by_category(db, category, subcategory)
        else:
            items = await readme_repo.get_all(db)
        
        return ReadmeListResponse(
            items=[ReadmeContentResponse.from_orm(item) for item in items],
            total=len(items)
        )


@router.get("/{readme_id}", response_model=ReadmeContentResponse)
async def get_readme_content(
    readme_id: str,
    current_user: User = Depends(get_current_user)
):
    """
    Get specific README content by ID.
    """
    readme_repo = get_readme_repository()
    
    async with get_db_session() as db:
        readme_content = await readme_repo.get(db, readme_id)
        if not readme_content:
            raise HTTPException(status_code=404, detail="README content not found")
        
        return ReadmeContentResponse.from_orm(readme_content)


@router.post("/generate/main", response_model=ReadmeContentResponse)
async def generate_main_readme(
    request: ReadmeGenerationRequest,
    current_user: User = Depends(get_current_user)
):
    """
    Generate the main README file for the knowledge base.
    """
    readme_service = get_readme_generator_service()
    
    try:
        readme_content = await readme_service.generate_main_readme(
            models_override=request.models_override
        )
        return ReadmeContentResponse.from_orm(readme_content)
    except Exception as e:
        raise HTTPException(
            status_code=500, 
            detail=f"Failed to generate main README: {str(e)}"
        )


@router.post("/generate/category/{category}", response_model=ReadmeContentResponse)
async def generate_category_index(
    category: str,
    request: ReadmeGenerationRequest,
    current_user: User = Depends(get_current_user)
):
    """
    Generate an index file for a specific category.
    """
    readme_service = get_readme_generator_service()
    
    try:
        readme_content = await readme_service.generate_category_index(
            category=category,
            models_override=request.models_override
        )
        return ReadmeContentResponse.from_orm(readme_content)
    except Exception as e:
        raise HTTPException(
            status_code=500, 
            detail=f"Failed to generate category index: {str(e)}"
        )


@router.post("/generate/subcategory/{category}/{subcategory}", response_model=ReadmeContentResponse)
async def generate_subcategory_index(
    category: str,
    subcategory: str,
    request: ReadmeGenerationRequest,
    current_user: User = Depends(get_current_user)
):
    """
    Generate an index file for a specific subcategory.
    """
    readme_service = get_readme_generator_service()
    
    try:
        readme_content = await readme_service.generate_subcategory_index(
            category=category,
            subcategory=subcategory,
            models_override=request.models_override
        )
        return ReadmeContentResponse.from_orm(readme_content)
    except Exception as e:
        raise HTTPException(
            status_code=500, 
            detail=f"Failed to generate subcategory index: {str(e)}"
        )


@router.post("/regenerate/stale", response_model=ReadmeListResponse)
async def regenerate_stale_content(
    request: ReadmeGenerationRequest,
    current_user: User = Depends(get_current_user)
):
    """
    Regenerate all stale README content.
    """
    readme_service = get_readme_generator_service()
    
    try:
        regenerated_items = await readme_service.regenerate_all_stale_content(
            models_override=request.models_override
        )
        return ReadmeListResponse(
            items=[ReadmeContentResponse.from_orm(item) for item in regenerated_items],
            total=len(regenerated_items)
        )
    except Exception as e:
        raise HTTPException(
            status_code=500, 
            detail=f"Failed to regenerate stale content: {str(e)}"
        )


@router.post("/mark-stale")
async def mark_content_stale(
    content_type: Optional[str] = Query(None, description="Content type to mark stale"),
    category: Optional[str] = Query(None, description="Category to mark stale"),
    subcategory: Optional[str] = Query(None, description="Subcategory to mark stale"),
    current_user: User = Depends(get_current_user)
):
    """
    Mark README content as stale to trigger regeneration.
    """
    readme_service = get_readme_generator_service()
    
    try:
        if content_type:
            count = await readme_service.mark_stale_content(
                content_type=content_type,
                category=category,
                subcategory=subcategory
            )
        else:
            # Mark all content as stale
            readme_repo = get_readme_repository()
            async with get_db_session() as db:
                count = await readme_repo.mark_all_stale(db)
        
        return {"message": f"Marked {count} README items as stale"}
    except Exception as e:
        raise HTTPException(
            status_code=500, 
            detail=f"Failed to mark content as stale: {str(e)}"
        )


@router.get("/export/files", response_model=ReadmeListResponse)
async def get_export_files(
    current_user: User = Depends(get_current_user)
):
    """
    Get all README content files that should be exported to Git.
    """
    readme_repo = get_readme_repository()
    
    async with get_db_session() as db:
        items = await readme_repo.get_content_for_export(db)
        
        return ReadmeListResponse(
            items=[ReadmeContentResponse.from_orm(item) for item in items],
            total=len(items)
        )


@router.get("/search", response_model=ReadmeListResponse)
async def search_readme_content(
    q: str = Query(..., description="Search query"),
    content_type: Optional[str] = Query(None, description="Filter by content type"),
    category: Optional[str] = Query(None, description="Filter by category"),
    current_user: User = Depends(get_current_user)
):
    """
    Search README content by text query.
    """
    readme_repo = get_readme_repository()
    
    async with get_db_session() as db:
        items = await readme_repo.search_content(
            db=db,
            query=q,
            content_type=content_type,
            category=category
        )
        
        return ReadmeListResponse(
            items=[ReadmeContentResponse.from_orm(item) for item in items],
            total=len(items)
        )