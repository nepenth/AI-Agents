"""
Pydantic schemas for synthesis document operations.
"""
from typing import List, Optional, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field

from .common import FilterParams


class SynthesisDocumentBase(BaseModel):
    """Base schema for synthesis documents."""
    main_category: str = Field(description="Main category")
    sub_category: str = Field(description="Sub category")
    title: str = Field(description="Document title")
    content: str = Field(description="Document content")
    executive_summary: Optional[str] = Field(default=None, description="Executive summary")
    item_count: int = Field(description="Number of source items")
    word_count: Optional[int] = Field(default=None, description="Word count")
    source_item_ids: List[str] = Field(description="Source content item IDs")


class SynthesisDocumentCreate(SynthesisDocumentBase):
    """Schema for creating a synthesis document."""
    generation_model: Optional[str] = Field(default=None, description="AI model used")
    generation_parameters: Optional[Dict[str, Any]] = Field(default=None, description="Generation parameters")


class SynthesisDocumentUpdate(BaseModel):
    """Schema for updating a synthesis document."""
    title: Optional[str] = Field(default=None, description="Updated title")
    content: Optional[str] = Field(default=None, description="Updated content")
    executive_summary: Optional[str] = Field(default=None, description="Updated summary")
    is_stale: Optional[bool] = Field(default=None, description="Stale status")


class SynthesisDocumentResponse(SynthesisDocumentBase):
    """Schema for synthesis document responses."""
    id: str = Field(description="Unique document ID")
    content_hash: Optional[str] = Field(default=None, description="Content hash")
    is_stale: bool = Field(description="Whether document needs regeneration")
    generation_model: Optional[str] = Field(default=None, description="AI model used")
    generation_parameters: Optional[Dict[str, Any]] = Field(default=None, description="Generation parameters")
    generation_duration: Optional[float] = Field(default=None, description="Generation time in seconds")
    coherence_score: Optional[float] = Field(default=None, description="Coherence score")
    completeness_score: Optional[float] = Field(default=None, description="Completeness score")
    markdown_path: Optional[str] = Field(default=None, description="Markdown file path")
    created_at: datetime = Field(description="Creation timestamp")
    updated_at: datetime = Field(description="Last update timestamp")
    last_generated_at: Optional[datetime] = Field(default=None, description="Last generation timestamp")
    
    # Computed properties
    category_path: str = Field(description="Full category path")
    source_count: int = Field(description="Number of source items")
    needs_regeneration: bool = Field(description="Whether regeneration is needed")
    
    class Config:
        from_attributes = True


class SynthesisDocumentList(BaseModel):
    """Schema for listing synthesis documents."""
    items: List[SynthesisDocumentResponse] = Field(description="List of synthesis documents")
    total: int = Field(description="Total number of documents")
    category_stats: Dict[str, int] = Field(description="Category statistics")
    stale_count: int = Field(description="Number of stale documents")