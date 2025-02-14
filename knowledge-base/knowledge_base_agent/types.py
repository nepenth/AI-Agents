"""
Type definitions for the knowledge base agent.

This module contains all the core data structures and type definitions used
throughout the knowledge base agent system.
"""

from typing import TypedDict, List, Dict, Optional
from datetime import datetime

class TweetMedia(TypedDict):
    """Media information from a tweet."""
    url: str
    type: str  # 'photo', 'video', etc.
    alt_text: Optional[str]

class TweetData(TypedDict):
    """Structured tweet data format."""
    id: str
    text: str
    created_at: datetime
    media: List[TweetMedia]
    author: str
    url: str

class CategoryInfo(TypedDict):
    """Category structure for knowledge base organization."""
    category: str
    subcategory: str
    name: str
    description: str

class KnowledgeBaseItem(TypedDict):
    """Structure for a knowledge base entry."""
    title: str
    description: str
    content: str
    category_info: CategoryInfo
    source_tweet: TweetData
    media_analysis: List[Dict[str, str]]
    created_at: datetime
    last_updated: datetime 