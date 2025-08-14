"""
Pydantic schemas for content item operations.
"""
from typing import List, Optional, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field

from .common import FilterParams


class ContentItemBase(BaseModel):
    """Base schema for content items."""
    source_type: str = Field(description="Type of content source (twitter, url, file, etc.)")
    source_id: str = Field(description="Unique identifier from the source")
    title: str = Field(description="Content title")
    content: str = Field(description="Raw content text")
    raw_data: Optional[Dict[str, Any]] = Field(default=None, description="Raw data from source")
    tags: List[str] = Field(default_factory=list, description="Content tags")
    media_content: List[Dict[str, Any]] = Field(default_factory=list, description="Media content stored in database")
    word_count: Optional[int] = Field(default=None, description="Word count of content")
    language: Optional[str] = Field(default=None, description="Detected language")
    
    # Twitter/X-specific fields
    tweet_id: Optional[str] = Field(default=None, description="Twitter/X tweet ID")
    author_username: Optional[str] = Field(default=None, description="Twitter/X author username")
    author_id: Optional[str] = Field(default=None, description="Twitter/X author ID")
    tweet_url: Optional[str] = Field(default=None, description="Twitter/X tweet URL")
    
    # Thread detection data
    thread_id: Optional[str] = Field(default=None, description="Thread identifier")
    is_thread_root: bool = Field(default=False, description="Whether this is the root of a thread")
    position_in_thread: Optional[int] = Field(default=None, description="Position in thread (0-based)")
    thread_length: Optional[int] = Field(default=None, description="Total length of thread")
    
    # Engagement metrics
    like_count: Optional[int] = Field(default=None, description="Number of likes")
    retweet_count: Optional[int] = Field(default=None, description="Number of retweets")
    reply_count: Optional[int] = Field(default=None, description="Number of replies")
    quote_count: Optional[int] = Field(default=None, description="Number of quotes")
    
    # Additional metadata
    original_tweet_created_at: Optional[datetime] = Field(default=None, description="Original tweet creation time")


class ContentItemCreate(ContentItemBase):
    """Schema for creating a new content item."""
    processing_state: str = Field(default="pending", description="Initial processing state")


class ContentItemUpdate(BaseModel):
    """Schema for updating a content item."""
    title: Optional[str] = Field(default=None, description="Updated title")
    content: Optional[str] = Field(default=None, description="Updated content")
    processing_state: Optional[str] = Field(default=None, description="Updated processing state")
    main_category: Optional[str] = Field(default=None, description="Main category")
    sub_category: Optional[str] = Field(default=None, description="Sub category")
    tags: Optional[List[str]] = Field(default=None, description="Updated tags")
    processed_at: Optional[datetime] = Field(default=None, description="Processing completion time")


class ContentItemResponse(ContentItemBase):
    """Schema for content item responses."""
    id: str = Field(description="Unique content item ID")
    processing_state: str = Field(description="Current processing state")
    processed_at: Optional[datetime] = Field(default=None, description="Processing completion time")
    main_category: Optional[str] = Field(default=None, description="AI-assigned main category")
    sub_category: Optional[str] = Field(default=None, description="AI-assigned sub category")
    created_at: datetime = Field(description="Creation timestamp")
    updated_at: datetime = Field(description="Last update timestamp")
    
    # Sub-phase processing states
    bookmark_cached: bool = Field(description="Whether bookmark has been cached")
    media_analyzed: bool = Field(description="Whether media has been analyzed")
    content_understood: bool = Field(description="Whether content has been understood by AI")
    categorized: bool = Field(description="Whether content has been categorized")
    
    # AI analysis results (metadata only for API responses)
    has_media_analysis: bool = Field(description="Whether media analysis results exist")
    has_collective_understanding: bool = Field(description="Whether collective understanding exists")
    category_intelligence_used: Optional[Dict[str, Any]] = Field(default=None, description="Category intelligence metadata")
    
    # Provenance
    vision_model_used: Optional[str] = Field(default=None, description="Vision model used for media analysis")
    understanding_model_used: Optional[str] = Field(default=None, description="Model used for content understanding")
    categorization_model_used: Optional[str] = Field(default=None, description="Model used for categorization")
    
    # Computed properties
    is_processed: bool = Field(description="Whether the item has been processed")
    has_media: bool = Field(description="Whether the item has associated media")
    is_twitter_content: bool = Field(description="Whether this is Twitter/X content")
    is_thread: bool = Field(description="Whether this content is part of a thread")
    sub_phase_completion_percentage: float = Field(description="Percentage of sub-phases completed")
    is_fully_processed: bool = Field(description="Whether all sub-phases are completed")
    total_engagement: int = Field(description="Total engagement count")
    
    class Config:
        from_attributes = True


class ContentItemList(BaseModel):
    """Schema for listing content items with metadata."""
    items: List[ContentItemResponse] = Field(description="List of content items")
    total: int = Field(description="Total number of items")
    processing_stats: Dict[str, int] = Field(description="Processing state statistics")
    category_stats: Dict[str, int] = Field(description="Category statistics")


class ContentItemFilter(FilterParams):
    """Filter parameters specific to content items."""
    source_type: Optional[str] = Field(default=None, description="Filter by source type")
    processing_state: Optional[str] = Field(default=None, description="Filter by processing state")
    main_category: Optional[str] = Field(default=None, description="Filter by main category")
    sub_category: Optional[str] = Field(default=None, description="Filter by sub category")
    has_media: Optional[bool] = Field(default=None, description="Filter by media presence")
    tags: Optional[List[str]] = Field(default=None, description="Filter by tags (any match)")


class ContentItemSearch(BaseModel):
    """Search parameters for content items."""
    query: str = Field(description="Search query")
    fields: List[str] = Field(
        default=["title", "content"], 
        description="Fields to search in"
    )
    filters: Optional[ContentItemFilter] = Field(default=None, description="Additional filters")
    highlight: bool = Field(default=False, description="Include search highlights in results")


# Twitter/X-specific schemas
class TwitterBookmarkCreate(BaseModel):
    """Schema for creating content from Twitter/X bookmark."""
    tweet_id: str = Field(description="Twitter/X tweet ID")
    force_refresh: bool = Field(default=False, description="Force refresh even if already cached")


class TwitterThreadResponse(BaseModel):
    """Schema for Twitter/X thread information."""
    thread_id: str = Field(description="Thread identifier")
    root_tweet_id: str = Field(description="Root tweet ID")
    thread_length: int = Field(description="Total number of tweets in thread")
    tweets: List[ContentItemResponse] = Field(description="All tweets in the thread")
    author_username: str = Field(description="Thread author username")
    created_at: datetime = Field(description="Thread creation time")
    total_engagement: int = Field(description="Total engagement across thread")


class SubPhaseStatus(BaseModel):
    """Schema for sub-phase processing status."""
    bookmark_cached: bool = Field(description="Bookmark caching status")
    media_analyzed: bool = Field(description="Media analysis status")
    content_understood: bool = Field(description="Content understanding status")
    categorized: bool = Field(description="Categorization status")
    completion_percentage: float = Field(description="Overall completion percentage")
    last_updated: datetime = Field(description="Last status update time")


class SubPhaseUpdate(BaseModel):
    """Schema for updating sub-phase status."""
    phase: str = Field(description="Sub-phase name (bookmark_cached, media_analyzed, content_understood, categorized)")
    status: bool = Field(description="New status for the sub-phase")
    model_used: Optional[str] = Field(default=None, description="Model used for this phase")
    results: Optional[Dict[str, Any]] = Field(default=None, description="Phase-specific results")


class MediaAnalysisResult(BaseModel):
    """Schema for media analysis results."""
    media_id: str = Field(description="Media identifier")
    media_type: str = Field(description="Type of media (image, video, etc.)")
    description: str = Field(description="AI-generated description")
    technical_analysis: str = Field(description="Technical analysis of content")
    key_insights: List[str] = Field(description="Key insights extracted")
    confidence_score: float = Field(description="Analysis confidence score")


class CollectiveUnderstandingResult(BaseModel):
    """Schema for collective understanding results."""
    collective_understanding: str = Field(description="AI-generated collective understanding")
    key_concepts: List[str] = Field(description="Key concepts identified")
    technical_domain: str = Field(description="Technical domain classification")
    actionable_insights: List[str] = Field(description="Actionable insights extracted")


class CategorizationResult(BaseModel):
    """Schema for categorization results."""
    category: str = Field(description="Assigned category")
    subcategory: str = Field(description="Assigned subcategory")
    reasoning: str = Field(description="Categorization reasoning")
    is_new_category: bool = Field(description="Whether this is a new category")
    confidence_score: float = Field(description="Categorization confidence")
    existing_categories_considered: List[str] = Field(description="Existing categories that were considered")