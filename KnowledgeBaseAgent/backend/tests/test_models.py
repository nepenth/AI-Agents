"""
Tests for database models.
"""
import pytest
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    ContentItem,
    KnowledgeItem,
    Embedding,
    SynthesisDocument,
    Task,
    ChatSession,
    ChatMessage,
)


@pytest.mark.asyncio
async def test_content_item_creation(test_db_session):
    """Test creating a content item."""
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
    
    test_db_session.add(content_item)
    await test_db_session.commit()
    
    # Verify the item was created
    assert content_item.id == "test-content-1"
    assert content_item.source_type == "twitter"
    assert content_item.is_processed is False
    assert content_item.has_media is False
    assert len(content_item.tags) == 2


@pytest.mark.asyncio
async def test_knowledge_item_with_content_item(test_db_session: AsyncSession):
    """Test creating a knowledge item linked to a content item."""
    # Create content item first
    content_item = ContentItem(
        id="test-content-2",
        source_type="url",
        source_id="https://example.com",
        title="Example Article",
        content="This is example article content",
        processing_state="completed",
        tags=["article"],
        media_files=[],
        generated_files=[]
    )
    test_db_session.add(content_item)
    await test_db_session.flush()
    
    # Create knowledge item
    knowledge_item = KnowledgeItem(
        id="test-knowledge-1",
        content_item_id=content_item.id,
        display_title="Enhanced Example Article",
        summary="This is a summary of the example article",
        enhanced_content="Enhanced content with AI improvements",
        key_points=["Point 1", "Point 2"],
        entities=[{"name": "Example", "type": "organization"}]
    )
    test_db_session.add(knowledge_item)
    await test_db_session.commit()
    
    # Verify relationships
    assert knowledge_item.content_item_id == content_item.id
    assert knowledge_item.has_embeddings is False
    assert knowledge_item.embedding_count == 0
    assert len(knowledge_item.key_points) == 2


@pytest.mark.asyncio
async def test_embedding_creation(test_db_session: AsyncSession):
    """Test creating embeddings for a knowledge item."""
    # Create content and knowledge items first
    content_item = ContentItem(
        id="test-content-3",
        source_type="file",
        source_id="document.pdf",
        title="Test Document",
        content="Document content for embedding",
        processing_state="completed",
        tags=["document"],
        media_files=[],
        generated_files=[]
    )
    test_db_session.add(content_item)
    await test_db_session.flush()
    
    knowledge_item = KnowledgeItem(
        id="test-knowledge-2",
        content_item_id=content_item.id,
        display_title="Test Document Knowledge",
        enhanced_content="Enhanced document content",
        key_points=["Key point"],
        entities=[]
    )
    test_db_session.add(knowledge_item)
    await test_db_session.flush()
    
    # Create embedding
    embedding = Embedding(
        id="test-embedding-1",
        knowledge_item_id=knowledge_item.id,
        model="text-embedding-ada-002",
        chunk_index=0,
        chunk_text="This is the first chunk of text",
        embedding_dimension=1536,
        token_count=10
    )
    test_db_session.add(embedding)
    await test_db_session.commit()
    
    # Verify embedding
    assert embedding.knowledge_item_id == knowledge_item.id
    assert embedding.model == "text-embedding-ada-002"
    assert embedding.embedding_dimension == 1536


@pytest.mark.asyncio
async def test_synthesis_document_creation(test_db_session: AsyncSession):
    """Test creating a synthesis document."""
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
    
    test_db_session.add(synthesis_doc)
    await test_db_session.commit()
    
    # Verify synthesis document
    assert synthesis_doc.category_path == "Technology/AI"
    assert synthesis_doc.source_count == 3
    assert synthesis_doc.needs_regeneration is False
    
    # Test marking as stale
    synthesis_doc.mark_stale()
    assert synthesis_doc.is_stale is True
    assert synthesis_doc.needs_regeneration is True


@pytest.mark.asyncio
async def test_task_creation_and_progress(test_db_session: AsyncSession):
    """Test creating and updating a task."""
    task = Task(
        id="test-task-1",
        task_type="content_processing",
        task_name="Process Content Item",
        status="pending",
        config={"source": "twitter", "count": 10},
        retry_count=0,
        max_retries=3
    )
    
    test_db_session.add(task)
    await test_db_session.commit()
    
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


@pytest.mark.asyncio
async def test_chat_session_and_messages(test_db_session: AsyncSession):
    """Test creating chat sessions and messages."""
    # Create chat session
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
    
    test_db_session.add(chat_session)
    await test_db_session.flush()
    
    # Create user message
    user_message = ChatMessage(
        id="test-message-1",
        session_id=chat_session.id,
        role="user",
        content="Hello, how are you?",
        token_count=5,
        word_count=4,
        sources=[],
        is_edited=False,
        is_regenerated=False
    )
    test_db_session.add(user_message)
    
    # Create assistant message
    assistant_message = ChatMessage(
        id="test-message-2",
        session_id=chat_session.id,
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
    test_db_session.add(assistant_message)
    await test_db_session.commit()
    
    # Verify session properties
    assert chat_session.is_empty is True  # message_count not updated yet
    assert len(chat_session.messages) == 2
    
    # Update session stats
    chat_session.update_stats()
    assert chat_session.message_count == 2
    assert chat_session.total_tokens == 15
    assert chat_session.is_empty is False
    
    # Verify message properties
    assert user_message.is_user_message is True
    assert user_message.is_assistant_message is False
    assert assistant_message.is_user_message is False
    assert assistant_message.is_assistant_message is True
    
    # Test adding source to assistant message
    assistant_message.add_source("knowledge-item-1", "Relevant Article", 0.85)
    assert assistant_message.has_sources is True
    assert assistant_message.source_count == 1


@pytest.mark.asyncio
async def test_model_to_dict_methods(test_db_session: AsyncSession):
    """Test the to_dict methods of all models."""
    # Create a content item
    content_item = ContentItem(
        id="test-dict-1",
        source_type="test",
        source_id="test-123",
        title="Test Item",
        content="Test content",
        processing_state="pending",
        tags=["test"],
        media_files=[],
        generated_files=[]
    )
    
    # Test to_dict method
    content_dict = content_item.to_dict()
    assert content_dict["id"] == "test-dict-1"
    assert content_dict["source_type"] == "test"
    assert content_dict["processing_state"] == "pending"
    assert content_dict["has_media"] is False
    assert "created_at" in content_dict
    assert "updated_at" in content_dict


@pytest.mark.asyncio
async def test_model_relationships(test_db_session: AsyncSession):
    """Test relationships between models."""
    # Create content item
    content_item = ContentItem(
        id="test-rel-1",
        source_type="test",
        source_id="test-rel",
        title="Relationship Test",
        content="Testing relationships",
        processing_state="completed",
        tags=["relationship"],
        media_files=[],
        generated_files=[]
    )
    test_db_session.add(content_item)
    await test_db_session.flush()
    
    # Create knowledge item
    knowledge_item = KnowledgeItem(
        id="test-rel-knowledge-1",
        content_item_id=content_item.id,
        display_title="Relationship Knowledge",
        enhanced_content="Enhanced relationship content",
        key_points=["Relationship point"],
        entities=[]
    )
    test_db_session.add(knowledge_item)
    await test_db_session.flush()
    
    # Create embedding
    embedding = Embedding(
        id="test-rel-embedding-1",
        knowledge_item_id=knowledge_item.id,
        model="test-model",
        chunk_index=0,
        chunk_text="Relationship chunk",
        embedding_dimension=768
    )
    test_db_session.add(embedding)
    await test_db_session.commit()
    
    # Test relationships
    assert knowledge_item.content_item.id == content_item.id
    assert content_item.knowledge_item.id == knowledge_item.id
    assert embedding.knowledge_item.id == knowledge_item.id
    assert knowledge_item.embeddings[0].id == embedding.id