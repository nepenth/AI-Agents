"""
Pydantic schemas for request/response validation.
"""
from .content import (
    ContentItemCreate,
    ContentItemUpdate,
    ContentItemResponse,
    ContentItemList,
)
from .knowledge import (
    KnowledgeItemCreate,
    KnowledgeItemUpdate,
    KnowledgeItemResponse,
    KnowledgeItemList,
    EmbeddingCreate,
    EmbeddingResponse,
)
from .synthesis import (
    SynthesisDocumentCreate,
    SynthesisDocumentUpdate,
    SynthesisDocumentResponse,
    SynthesisDocumentList,
)
from .tasks import (
    TaskCreate,
    TaskUpdate,
    TaskResponse,
    TaskList,
)
from .chat import (
    ChatSessionCreate,
    ChatSessionUpdate,
    ChatSessionResponse,
    ChatSessionList,
    ChatMessageCreate,
    ChatMessageResponse,
    ChatMessageList,
)
from .common import (
    PaginationParams,
    PaginatedResponse,
    SearchParams,
    FilterParams,
)

__all__ = [
    # Content schemas
    "ContentItemCreate",
    "ContentItemUpdate", 
    "ContentItemResponse",
    "ContentItemList",
    # Knowledge schemas
    "KnowledgeItemCreate",
    "KnowledgeItemUpdate",
    "KnowledgeItemResponse", 
    "KnowledgeItemList",
    "EmbeddingCreate",
    "EmbeddingResponse",
    # Synthesis schemas
    "SynthesisDocumentCreate",
    "SynthesisDocumentUpdate",
    "SynthesisDocumentResponse",
    "SynthesisDocumentList",
    # Task schemas
    "TaskCreate",
    "TaskUpdate",
    "TaskResponse",
    "TaskList",
    # Chat schemas
    "ChatSessionCreate",
    "ChatSessionUpdate",
    "ChatSessionResponse",
    "ChatSessionList",
    "ChatMessageCreate",
    "ChatMessageResponse",
    "ChatMessageList",
    # Common schemas
    "PaginationParams",
    "PaginatedResponse",
    "SearchParams",
    "FilterParams",
]