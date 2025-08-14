"""
Pydantic schemas for knowledge item and embedding operations.
"""
from typing import List, Optional, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field

from .common import FilterParams


class KnowledgeItemBase(BaseModel):
    """Base schema for knowledge items."""
    display_title: str = Field(description="AI-enhanced display title")
    summary: Optional[str] = Field(default=None, description="AI-generated summary")
    enhanced_content: str = Field(description="AI-enhanced content")
    key_points: List[str] = Field(default_factory=list, description="Extracted key points")
    entities: List[Dict[str, Any]] = Field(default_factory=list, description="Named entities")
    sentiment_score: Optional[float] = Field(default=None, description="Sentiment analysis score")
    quality_score: Optional[float] = Field(default=None, description="Content quality score")
    completeness_score: Optional[float] = Field(default=None, description="Content completeness score")


class KnowledgeItemCreate(KnowledgeItemBase):
    """Schema for creating a new knowledge item."""
    content_item_id: str = Field(description="Associated content item ID")
    markdown_path: Optional[str] = Field(default=None, description="Path to markdown file")
    media_paths: List[str] = Field(default_factory=list, description="Paths to media files")


class KnowledgeItemUpdate(BaseModel):
    """Schema for updating a knowledge item."""
    display_title: Optional[str] = Field(default=None, description="Updated display title")
    summary: Optional[str] = Field(default=None, description="Updated summary")
    enhanced_content: Optional[str] = Field(default=None, description="Updated enhanced content")
    key_points: Optional[List[str]] = Field(default=None, description="Updated key points")
    entities: Optional[List[Dict[str, Any]]] = Field(default=None, description="Updated entities")
    sentiment_score: Optional[float] = Field(default=None, description="Updated sentiment score")
    quality_score: Optional[float] = Field(default=None, description="Updated quality score")
    completeness_score: Optional[float] = Field(default=None, description="Updated completeness score")


class KnowledgeItemResponse(KnowledgeItemBase):
    """Schema for knowledge item responses."""
    id: str = Field(description="Unique knowledge item ID")
    content_item_id: str = Field(description="Associated content item ID")
    markdown_path: Optional[str] = Field(default=None, description="Path to markdown file")
    media_paths: List[str] = Field(default_factory=list, description="Paths to media files")
    created_at: datetime = Field(description="Creation timestamp")
    updated_at: datetime = Field(description="Last update timestamp")
    
    # Computed properties
    has_embeddings: bool = Field(description="Whether the item has vector embeddings")
    embedding_count: int = Field(description="Number of embedding chunks")
    
    class Config:
        from_attributes = True


class KnowledgeItemList(BaseModel):
    """Schema for listing knowledge items with metadata."""
    items: List[KnowledgeItemResponse] = Field(description="List of knowledge items")
    total: int = Field(description="Total number of items")
    quality_stats: Dict[str, float] = Field(description="Quality score statistics")
    entity_stats: Dict[str, int] = Field(description="Entity type statistics")


class KnowledgeItemFilter(FilterParams):
    """Filter parameters specific to knowledge items."""
    content_item_id: Optional[str] = Field(default=None, description="Filter by content item ID")
    has_embeddings: Optional[bool] = Field(default=None, description="Filter by embedding presence")
    min_quality_score: Optional[float] = Field(default=None, description="Minimum quality score")
    max_quality_score: Optional[float] = Field(default=None, description="Maximum quality score")
    entity_types: Optional[List[str]] = Field(default=None, description="Filter by entity types")


class EmbeddingBase(BaseModel):
    """Base schema for embeddings."""
    model: str = Field(description="Embedding model used")
    chunk_index: int = Field(description="Chunk index for this embedding")
    chunk_text: str = Field(description="Text chunk that was embedded")
    embedding_dimension: int = Field(description="Dimension of the embedding vector")
    token_count: Optional[int] = Field(default=None, description="Number of tokens in chunk")


class EmbeddingCreate(EmbeddingBase):
    """Schema for creating a new embedding."""
    knowledge_item_id: str = Field(description="Associated knowledge item ID")
    # Note: embedding vector will be handled separately due to pgvector


class EmbeddingResponse(EmbeddingBase):
    """Schema for embedding responses."""
    id: str = Field(description="Unique embedding ID")
    knowledge_item_id: str = Field(description="Associated knowledge item ID")
    created_at: datetime = Field(description="Creation timestamp")
    
    class Config:
        from_attributes = True


class VectorSearchRequest(BaseModel):
    """Schema for vector similarity search requests."""
    query: str = Field(description="Search query to embed and search for")
    model: Optional[str] = Field(default=None, description="Embedding model to use")
    limit: int = Field(default=10, ge=1, le=100, description="Maximum number of results")
    threshold: Optional[float] = Field(default=None, description="Similarity threshold (0-1)")
    filters: Optional[KnowledgeItemFilter] = Field(default=None, description="Additional filters")


class VectorSearchResult(BaseModel):
    """Schema for vector search results."""
    knowledge_item: KnowledgeItemResponse = Field(description="Matching knowledge item")
    similarity_score: float = Field(description="Similarity score (0-1)")
    chunk_text: str = Field(description="Matching text chunk")
    chunk_index: int = Field(description="Chunk index")


class VectorSearchResponse(BaseModel):
    """Schema for vector search response."""
    results: List[VectorSearchResult] = Field(description="Search results")
    query: str = Field(description="Original search query")
    model: str = Field(description="Embedding model used")
    total_results: int = Field(description="Total number of results found")
    search_time: float = Field(description="Search execution time in seconds")