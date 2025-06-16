import gevent.monkey
gevent.monkey.patch_all()

"""
Knowledge Base Agent package.

A system for automatically processing tweets into a structured knowledge base.
"""

__version__ = "0.1.1"  # Bumped to reflect fixes

from knowledge_base_agent.agent import KnowledgeBaseAgent
from knowledge_base_agent.category_manager import CategoryManager
from knowledge_base_agent.markdown_writer import MarkdownWriter
from knowledge_base_agent.state_manager import StateManager
from knowledge_base_agent.config import Config
from knowledge_base_agent.git_helper import GitSyncHandler
from knowledge_base_agent.progress import ProcessingStats, ProcessingResult
from knowledge_base_agent.exceptions import (
    KnowledgeBaseError,
    ConfigurationError,
    CategoryError,
    TweetProcessingError,
    MarkdownGenerationError,
    GitSyncError,
    NetworkError,
    StateError
)

__all__ = [
    'KnowledgeBaseAgent',
    'CategoryManager',
    'MarkdownWriter',
    'StateManager',
    'Config',
    'GitSyncHandler',         # Added for Git sync functionality
    'ProcessingStats',        # Added for stats tracking
    'ProcessingResult',       # Added for run results
    'KnowledgeBaseError',
    'ConfigurationError',
    'CategoryError',
    'TweetProcessingError',
    'MarkdownGenerationError',
    'GitSyncError',
    'NetworkError',
    'StateError',
]

# Initialize knowledge_base_agent package