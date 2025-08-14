"""
Pydantic schemas for chat operations.
"""
from typing import List, Optional, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field

from .common import FilterParams


class ChatSessionBase(BaseModel):
    """Base schema for chat sessions."""
    model_config = {"protected_namespaces": (), "from_attributes": True}
    
    title: Optional[str] = Field(default=None, description="Session title")
    description: Optional[str] = Field(default=None, description="Session description")
    model_name: Optional[str] = Field(default=None, description="AI model name")
    system_prompt: Optional[str] = Field(default=None, description="System prompt")
    temperature: Optional[float] = Field(default=None, description="Temperature setting")
    max_tokens: Optional[int] = Field(default=None, description="Max tokens setting")
    context_window: int = Field(default=10, description="Context window size")
    auto_summarize: bool = Field(default=True, description="Auto-summarize setting")


class ChatSessionCreate(ChatSessionBase):
    """Schema for creating a chat session."""
    pass


class ChatSessionUpdate(BaseModel):
    """Schema for updating a chat session."""
    model_config = {"protected_namespaces": ()}
    
    title: Optional[str] = Field(default=None, description="Updated title")
    description: Optional[str] = Field(default=None, description="Updated description")
    is_archived: Optional[bool] = Field(default=None, description="Archive status")
    is_pinned: Optional[bool] = Field(default=None, description="Pin status")
    model_name: Optional[str] = Field(default=None, description="Updated model name")
    temperature: Optional[float] = Field(default=None, description="Updated temperature")
    max_tokens: Optional[int] = Field(default=None, description="Updated max tokens")


class ChatSessionResponse(ChatSessionBase):
    """Schema for chat session responses."""
    id: str = Field(description="Unique session ID")
    message_count: int = Field(description="Number of messages")
    total_tokens: int = Field(description="Total tokens used")
    is_archived: bool = Field(description="Whether session is archived")
    is_pinned: bool = Field(description="Whether session is pinned")
    created_at: datetime = Field(description="Creation timestamp")
    last_updated: datetime = Field(description="Last update timestamp")
    last_message_at: Optional[datetime] = Field(default=None, description="Last message timestamp")
    
    # Computed properties
    is_empty: bool = Field(description="Whether session has no messages")


class ChatMessageBase(BaseModel):
    """Base schema for chat messages."""
    role: str = Field(description="Message role (user/assistant)")
    content: str = Field(description="Message content")


class ChatMessageCreate(ChatMessageBase):
    """Schema for creating a chat message."""
    pass


class ChatMessageResponse(ChatMessageBase):
    """Schema for chat message responses."""
    model_config = {"protected_namespaces": (), "from_attributes": True}
    
    id: str = Field(description="Unique message ID")
    session_id: str = Field(description="Session ID")
    token_count: Optional[int] = Field(default=None, description="Token count")
    word_count: Optional[int] = Field(default=None, description="Word count")
    model_used: Optional[str] = Field(default=None, description="AI model used")
    generation_time: Optional[float] = Field(default=None, description="Generation time")
    temperature_used: Optional[float] = Field(default=None, description="Temperature used")
    sources: List[Dict[str, Any]] = Field(description="Source attributions")
    context_stats: Optional[Dict[str, Any]] = Field(default=None, description="Context statistics")
    is_edited: bool = Field(description="Whether message was edited")
    is_regenerated: bool = Field(description="Whether message was regenerated")
    parent_message_id: Optional[str] = Field(default=None, description="Parent message ID")
    relevance_score: Optional[float] = Field(default=None, description="Relevance score")
    helpfulness_score: Optional[float] = Field(default=None, description="Helpfulness score")
    created_at: datetime = Field(description="Creation timestamp")
    updated_at: datetime = Field(description="Last update timestamp")
    
    # Computed properties
    is_user_message: bool = Field(description="Whether this is a user message")
    is_assistant_message: bool = Field(description="Whether this is an assistant message")
    has_sources: bool = Field(description="Whether message has sources")
    source_count: int = Field(description="Number of sources")


class ChatSessionList(BaseModel):
    """Schema for listing chat sessions."""
    items: List[ChatSessionResponse] = Field(description="List of chat sessions")
    total: int = Field(description="Total number of sessions")
    archived_count: int = Field(description="Number of archived sessions")
    pinned_count: int = Field(description="Number of pinned sessions")


class ChatMessageList(BaseModel):
    """Schema for listing chat messages."""
    items: List[ChatMessageResponse] = Field(description="List of chat messages")
    total: int = Field(description="Total number of messages")
    session_id: str = Field(description="Session ID")
    token_stats: Dict[str, int] = Field(description="Token usage statistics")