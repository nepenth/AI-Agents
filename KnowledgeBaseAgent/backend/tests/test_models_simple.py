"""
Simple tests for database models without complex fixtures.
"""
import pytest
from datetime import datetime

from app.models import (
    ContentItem,
    KnowledgeItem,
    Embedding,
    SynthesisDocument,
    Task,
    ChatSession,
    ChatMessage,
)


def test_content_item_creation():
    """Test creating a content item object."""
    content_item = ContentItem(
        id="test-content-1",
        source_type="twitter",
        source_id="tweet-123",
        title="Test Tweet",
        content="This is a test tweet content",
        processing_state="pending",
        tags=["test", "example"],
        media_files=[],
        generated_files=[]
    )
    
    # Verify the item properties
    assert content_item.id == "test-content-1"
    assert content_item.source_type == "twitter"
    assert content_item.is_processed is False
    assert content_item.has_media is False
    assert len(content_item.tags) == 2
    
    # Test to_dict method
    content_dict = content_item.to_dict()
    assert content_dict["id"] == "test-content-1"
    assert content_dict["source_type"] == "twitter"
    assert content_dict["processing_state"] == "pending"
    assert content_dict["has_media"] is False


def test_knowledge_item_creation():
    """Test creating a knowledge item object."""
    knowledge_item = KnowledgeItem(
        id="test-knowledge-1",
        content_item_id="test-content-1",
        display_title="Enhanced Test Tweet",
        summary="This is a summary",
        enhanced_content="Enhanced content with AI improvements",
        key_points=["Point 1", "Point 2"],
        entities=[{"name": "Test", "type": "organization"}]
    )
    
    # Verify properties
    assert knowledge_item.id == "test-knowledge-1"
    assert knowledge_item.content_item_id == "test-content-1"
    assert knowledge_item.has_embeddings is False
    assert knowledge_item.embedding_count == 0
    assert len(knowledge_item.key_points) == 2
    
    # Test to_dict method
    knowledge_dict = knowledge_item.to_dict()
    assert knowledge_dict["id"] == "test-knowledge-1"
    assert knowledge_dict["display_title"] == "Enhanced Test Tweet"
    assert knowledge_dict["has_embeddings"] is False


def test_embedding_creation():
    """Test creating an embedding object."""
    embedding = Embedding(
        id="test-embedding-1",
        knowledge_item_id="test-knowledge-1",
        model="text-embedding-ada-002",
        chunk_index=0,
        chunk_text="This is the first chunk of text",
        embedding_dimension=1536,
        token_count=10
    )
    
    # Verify properties
    assert embedding.id == "test-embedding-1"
    assert embedding.knowledge_item_id == "test-knowledge-1"
    assert embedding.model == "text-embedding-ada-002"
    assert embedding.embedding_dimension == 1536
    
    # Test to_dict method
    embedding_dict = embedding.to_dict()
    assert embedding_dict["id"] == "test-embedding-1"
    assert embedding_dict["model"] == "text-embedding-ada-002"
    assert embedding_dict["embedding_dimension"] == 1536


def test_synthesis_document_creation():
    """Test creating a synthesis document object."""
    synthesis_doc = SynthesisDocument(
        id="test-synthesis-1",
        main_category="Technology",
        sub_category="AI",
        title="AI Technology Synthesis",
        content="This is a synthesis of AI technology content",
        item_count=5,
        source_item_ids=["item1", "item2", "item3"],
        is_stale=False
    )
    
    # Verify properties
    assert synthesis_doc.category_path == "Technology/AI"
    assert synthesis_doc.source_count == 3
    assert synthesis_doc.needs_regeneration is False
    
    # Test marking as stale
    synthesis_doc.mark_stale()
    assert synthesis_doc.is_stale is True
    assert synthesis_doc.needs_regeneration is True
    
    # Test marking as fresh
    synthesis_doc.mark_fresh()
    assert synthesis_doc.is_stale is False
    assert synthesis_doc.needs_regeneration is False
    
    # Test to_dict method
    synthesis_dict = synthesis_doc.to_dict()
    assert synthesis_dict["category_path"] == "Technology/AI"
    assert synthesis_dict["source_count"] == 3


def test_task_creation_and_progress():
    """Test creating and updating a task object."""
    task = Task(
        id="test-task-1",
        task_type="content_processing",
        task_name="Process Content Item",
        status="pending",
        config={"source": "twitter", "count": 10},
        retry_count=0,
        max_retries=3
    )
    
    # Verify initial state
    assert task.is_running is True
    assert task.is_completed is False
    assert task.is_failed is False
    assert task.can_retry is False
    
    # Test progress update
    task.update_progress(50, "Processing items", "extraction")
    assert task.progress_percentage == 50
    assert task.progress_message == "Processing items"
    assert task.current_phase == "extraction"
    
    # Test marking as started
    task.mark_started("worker-1")
    assert task.status == "started"
    assert task.worker_id == "worker-1"
    assert task.started_at is not None
    
    # Test marking as completed
    task.mark_completed({"processed_items": 10})
    assert task.status == "success"
    assert task.is_completed is True
    assert task.progress_percentage == 100
    assert task.result_data["processed_items"] == 10
    
    # Test to_dict method
    task_dict = task.to_dict()
    assert task_dict["id"] == "test-task-1"
    assert task_dict["task_type"] == "content_processing"
    assert task_dict["is_completed"] is True


def test_chat_session_creation():
    """Test creating a chat session object."""
    chat_session = ChatSession(
        id="test-session-1",
        title="Test Chat Session",
        message_count=0,
        total_tokens=0,
        is_archived=False,
        is_pinned=False,
        model_name="gpt-3.5-turbo",
        temperature=0.7,
        context_window=10,
        auto_summarize=True
    )
    
    # Verify properties
    assert chat_session.id == "test-session-1"
    assert chat_session.is_empty is True
    assert chat_session.model_name == "gpt-3.5-turbo"
    
    # Test to_dict method
    session_dict = chat_session.to_dict()
    assert session_dict["id"] == "test-session-1"
    assert session_dict["is_empty"] is True
    assert session_dict["model_name"] == "gpt-3.5-turbo"


def test_chat_message_creation():
    """Test creating chat message objects."""
    # Create user message
    user_message = ChatMessage(
        id="test-message-1",
        session_id="test-session-1",
        role="user",
        content="Hello, how are you?",
        token_count=5,
        word_count=4,
        sources=[],
        is_edited=False,
        is_regenerated=False
    )
    
    # Verify user message properties
    assert user_message.is_user_message is True
    assert user_message.is_assistant_message is False
    assert user_message.has_sources is False
    assert user_message.source_count == 0
    
    # Create assistant message
    assistant_message = ChatMessage(
        id="test-message-2",
        session_id="test-session-1",
        role="assistant",
        content="I'm doing well, thank you for asking!",
        token_count=10,
        word_count=8,
        model_used="gpt-3.5-turbo",
        generation_time=1.5,
        sources=[],
        is_edited=False,
        is_regenerated=False
    )
    
    # Verify assistant message properties
    assert assistant_message.is_user_message is False
    assert assistant_message.is_assistant_message is True
    
    # Test adding source to assistant message
    assistant_message.add_source("knowledge-item-1", "Relevant Article", 0.85)
    assert assistant_message.has_sources is True
    assert assistant_message.source_count == 1
    
    # Test to_dict method
    message_dict = assistant_message.to_dict()
    assert message_dict["id"] == "test-message-2"
    assert message_dict["role"] == "assistant"
    assert message_dict["has_sources"] is True
    assert message_dict["source_count"] == 1