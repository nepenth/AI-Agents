"""
Knowledge Base Agent package.

A system for automatically processing tweets into a structured knowledge base.
"""

__version__ = "0.1.0"

from knowledge_base_agent.agent import KnowledgeBaseAgent
from knowledge_base_agent.category_manager import CategoryManager
from knowledge_base_agent.markdown_writer import MarkdownWriter
from knowledge_base_agent.state_manager import StateManager
from knowledge_base_agent.config import Config
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
