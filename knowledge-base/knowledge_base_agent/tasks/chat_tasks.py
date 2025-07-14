"""
Chat System Tasks for Celery

This module contains chat/RAG system tasks that migrate chat_manager.py
functionality to async Celery processing.
"""

import logging
import uuid
import asyncio
from datetime import datetime
from typing import Dict, Any, Optional

from ..celery_app import celery_app
from ..task_progress import get_progress_manager
from ..config import Config
from ..shared_globals import sg_set_project_root
from ..exceptions import KnowledgeBaseError


@celery_app.task(bind=True, name='knowledge_base_agent.tasks.chat.process_chat')
def process_chat_task(self, task_id: str, session_id: str, message: str, context: Dict[str, Any]):
    """
    Chat processing task for RAG pipeline.
    
    Migrates chat_manager.py functionality to async processing.
    Preserves current ChatManager.get_response() behavior.
    
    Args:
        task_id: Unique task identifier for progress tracking
        session_id: Chat session identifier
        message: User message/query
        context: Additional context for the chat
        
    Returns:
        Dict with chat response results
    """
    progress_manager = get_progress_manager()
    
    async def _async_chat():
        from ..chat_manager import ChatManager
        from ..embedding_manager import EmbeddingManager
        from ..http_client import HTTPClient
        
        config = Config.from_env()
        config.ensure_directories()
        sg_set_project_root(config.project_root)
        
        # Initialize chat components
        http_client = HTTPClient(config)
        embedding_manager = EmbeddingManager(config, http_client)
        chat_manager = ChatManager(config, http_client, embedding_manager)
        
        # Update progress
        progress_manager.update_progress(task_id, 25, "chat_processing", "Initializing chat components")
        
        # Process chat (identical to current implementation)
        progress_manager.update_progress(task_id, 50, "chat_processing", "Processing chat query")
        response = await chat_manager.get_response(message, context)
        
        progress_manager.update_progress(task_id, 100, "chat_processing", "Chat processing completed")
        
        return response
    
    try:
        progress_manager.log_message(task_id, f"💬 Starting chat processing for session {session_id}", "INFO")
        progress_manager.update_progress(task_id, 0, "chat_processing", "Starting chat processing")
        
        # Create event loop for async operations
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            response = loop.run_until_complete(_async_chat())
        finally:
            loop.close()
        
        progress_manager.log_message(task_id, f"✅ Chat processing completed for session {session_id}", "INFO")
        
        return {
            'status': 'completed',
            'task_id': task_id,
            'session_id': session_id,
            'message': message,
            'response': response,
            'context': context,
            'message': 'Chat processing completed successfully'
        }
        
    except Exception as e:
        error_msg = f"Chat processing failed: {str(e)}"
        progress_manager.log_message(task_id, f"❌ {error_msg}", "ERROR")
        progress_manager.update_progress(task_id, 0, "error", error_msg)
        
        logging.error(f"Chat processing task failed: {error_msg}", exc_info=True)
        
        self.update_state(
            state='FAILURE',
            meta={
                'error': error_msg,
                'task_id': task_id,
                'session_id': session_id,
                'message': message,
                'timestamp': datetime.utcnow().isoformat()
            }
        )
        
        raise


@celery_app.task(bind=True, name='knowledge_base_agent.tasks.chat.update_embeddings_index')
def update_embeddings_index_task(self, task_id: str, content_paths: Optional[list] = None):
    """
    Update embeddings index for chat/RAG system.
    
    Args:
        task_id: Unique task identifier for progress tracking
        content_paths: Optional list of specific content paths to index
        
    Returns:
        Dict with index update results
    """
    progress_manager = get_progress_manager()
    
    async def _async_index_update():
        from ..embedding_manager import EmbeddingManager
        from ..http_client import HTTPClient
        
        config = Config.from_env()
        config.ensure_directories()
        sg_set_project_root(config.project_root)
        
        # Initialize embedding manager
        http_client = HTTPClient(config)
        embedding_manager = EmbeddingManager(config, http_client)
        
        # Update progress
        progress_manager.update_progress(task_id, 25, "update_embeddings_index", "Initializing embedding manager")
        
        # Update embeddings index
        progress_manager.update_progress(task_id, 50, "update_embeddings_index", "Updating embeddings index")
        
        if content_paths:
            # Update specific content paths
            updated_count = 0
            for i, path in enumerate(content_paths):
                try:
                    await embedding_manager.update_embedding_for_path(path)
                    updated_count += 1
                    progress_manager.update_progress(
                        task_id, 
                        50 + int((i + 1) / len(content_paths) * 40), 
                        "update_embeddings_index",
                        f"Updated embeddings for {i+1}/{len(content_paths)} paths"
                    )
                except Exception as e:
                    progress_manager.log_message(task_id, f"Failed to update embeddings for {path}: {e}", "ERROR")
            
            result = {'updated_paths': updated_count, 'total_paths': len(content_paths)}
        else:
            # Full index update
            result = await embedding_manager.rebuild_index()
            
        progress_manager.update_progress(task_id, 100, "update_embeddings_index", "Embeddings index update completed")
        
        return result
    
    try:
        progress_manager.log_message(task_id, "🧠 Starting embeddings index update", "INFO")
        progress_manager.update_progress(task_id, 0, "update_embeddings_index", "Starting embeddings index update")
        
        # Create event loop for async operations
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            result = loop.run_until_complete(_async_index_update())
        finally:
            loop.close()
        
        progress_manager.log_message(task_id, "✅ Embeddings index update completed", "INFO")
        
        return {
            'status': 'completed',
            'task_id': task_id,
            'content_paths': content_paths,
            'result': result,
            'message': 'Embeddings index update completed successfully'
        }
        
    except Exception as e:
        error_msg = f"Embeddings index update failed: {str(e)}"
        progress_manager.log_message(task_id, f"❌ {error_msg}", "ERROR")
        progress_manager.update_progress(task_id, 0, "error", error_msg)
        
        logging.error(f"Embeddings index update task failed: {error_msg}", exc_info=True)
        
        self.update_state(
            state='FAILURE',
            meta={
                'error': error_msg,
                'task_id': task_id,
                'content_paths': content_paths,
                'timestamp': datetime.utcnow().isoformat()
            }
        )
        
        raise


@celery_app.task(bind=True, name='knowledge_base_agent.tasks.chat.search_knowledge_base')
def search_knowledge_base_task(self, task_id: str, query: str, max_results: int = 10, similarity_threshold: float = 0.7):
    """
    Search knowledge base for relevant content.
    
    Args:
        task_id: Unique task identifier for progress tracking
        query: Search query
        max_results: Maximum number of results to return
        similarity_threshold: Minimum similarity score for results
        
    Returns:
        Dict with search results
    """
    progress_manager = get_progress_manager()
    
    async def _async_search():
        from ..embedding_manager import EmbeddingManager
        from ..http_client import HTTPClient
        
        config = Config.from_env()
        config.ensure_directories()
        sg_set_project_root(config.project_root)
        
        # Initialize embedding manager
        http_client = HTTPClient(config)
        embedding_manager = EmbeddingManager(config, http_client)
        
        # Update progress
        progress_manager.update_progress(task_id, 25, "search_knowledge_base", "Initializing search components")
        
        # Perform search
        progress_manager.update_progress(task_id, 50, "search_knowledge_base", "Searching knowledge base")
        results = await embedding_manager.search_similar_content(
            query, 
            max_results=max_results,
            similarity_threshold=similarity_threshold
        )
        
        progress_manager.update_progress(task_id, 100, "search_knowledge_base", "Search completed")
        
        return results
    
    try:
        progress_manager.log_message(task_id, f"🔍 Starting knowledge base search for: {query[:50]}...", "INFO")
        progress_manager.update_progress(task_id, 0, "search_knowledge_base", "Starting knowledge base search")
        
        # Create event loop for async operations
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            results = loop.run_until_complete(_async_search())
        finally:
            loop.close()
        
        progress_manager.log_message(task_id, f"✅ Knowledge base search completed: {len(results)} results", "INFO")
        
        return {
            'status': 'completed',
            'task_id': task_id,
            'query': query,
            'max_results': max_results,
            'similarity_threshold': similarity_threshold,
            'results': results,
            'results_count': len(results),
            'message': 'Knowledge base search completed successfully'
        }
        
    except Exception as e:
        error_msg = f"Knowledge base search failed: {str(e)}"
        progress_manager.log_message(task_id, f"❌ {error_msg}", "ERROR")
        progress_manager.update_progress(task_id, 0, "error", error_msg)
        
        logging.error(f"Knowledge base search task failed: {error_msg}", exc_info=True)
        
        self.update_state(
            state='FAILURE',
            meta={
                'error': error_msg,
                'task_id': task_id,
                'query': query,
                'timestamp': datetime.utcnow().isoformat()
            }
        )
        
        raise


@celery_app.task(bind=True, name='knowledge_base_agent.tasks.chat.generate_chat_context')
def generate_chat_context_task(self, task_id: str, query: str, search_results: list):
    """
    Generate contextual information for chat responses.
    
    Args:
        task_id: Unique task identifier for progress tracking
        query: Original user query
        search_results: Knowledge base search results
        
    Returns:
        Dict with generated context
    """
    progress_manager = get_progress_manager()
    
    async def _async_context_generation():
        from ..chat_manager import ChatManager
        from ..embedding_manager import EmbeddingManager
        from ..http_client import HTTPClient
        
        config = Config.from_env()
        config.ensure_directories()
        sg_set_project_root(config.project_root)
        
        # Initialize chat components
        http_client = HTTPClient(config)
        embedding_manager = EmbeddingManager(config, http_client)
        chat_manager = ChatManager(config, http_client, embedding_manager)
        
        # Update progress
        progress_manager.update_progress(task_id, 25, "generate_chat_context", "Initializing context generation")
        
        # Generate context
        progress_manager.update_progress(task_id, 50, "generate_chat_context", "Generating chat context")
        context = await chat_manager.generate_context_from_search_results(query, search_results)
        
        progress_manager.update_progress(task_id, 100, "generate_chat_context", "Context generation completed")
        
        return context
    
    try:
        progress_manager.log_message(task_id, f"📝 Starting context generation for query: {query[:50]}...", "INFO")
        progress_manager.update_progress(task_id, 0, "generate_chat_context", "Starting context generation")
        
        # Create event loop for async operations
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            context = loop.run_until_complete(_async_context_generation())
        finally:
            loop.close()
        
        progress_manager.log_message(task_id, "✅ Context generation completed", "INFO")
        
        return {
            'status': 'completed',
            'task_id': task_id,
            'query': query,
            'search_results_count': len(search_results),
            'context': context,
            'message': 'Context generation completed successfully'
        }
        
    except Exception as e:
        error_msg = f"Context generation failed: {str(e)}"
        progress_manager.log_message(task_id, f"❌ {error_msg}", "ERROR")
        progress_manager.update_progress(task_id, 0, "error", error_msg)
        
        logging.error(f"Context generation task failed: {error_msg}", exc_info=True)
        
        self.update_state(
            state='FAILURE',
            meta={
                'error': error_msg,
                'task_id': task_id,
                'query': query,
                'timestamp': datetime.utcnow().isoformat()
            }
        )
        
        raise


def generate_task_id() -> str:
    """Generate a unique task ID for tracking purposes."""
    return str(uuid.uuid4()) 