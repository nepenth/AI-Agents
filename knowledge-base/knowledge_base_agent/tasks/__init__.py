"""
Celery Tasks Package for Knowledge Base Agent

This package contains all Celery tasks that replace the current multiprocessing architecture.
Tasks are organized by functionality:

- agent_tasks.py: Main agent execution tasks
- processing_tasks.py: Individual processing phase tasks  
- chat_tasks.py: Chat/RAG system tasks
"""

# Import main tasks for easy access
from .agent_tasks import (
    run_agent_task,
    fetch_bookmarks_task,
    git_sync_task,
    generate_task_id
)

from .processing_tasks import (
    process_tweets_task,
    generate_synthesis_task,
    generate_embeddings_task,
    generate_readme_task
)

from .chat_tasks import (
    process_chat_task,
    update_embeddings_index_task,
    search_knowledge_base_task,
    generate_chat_context_task
)

__all__ = [
    # Agent tasks
    'run_agent_task',
    'fetch_bookmarks_task',
    'git_sync_task',
    
    # Processing tasks
    'process_tweets_task',
    'generate_synthesis_task',
    'generate_embeddings_task',
    'generate_readme_task',
    
    # Chat tasks
    'process_chat_task',
    'update_embeddings_index_task',
    'search_knowledge_base_task',
    'generate_chat_context_task',
    
    # Utilities
    'generate_task_id',
] 