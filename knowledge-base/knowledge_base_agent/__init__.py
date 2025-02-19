"""
Knowledge Base Agent package.

A system for automatically processing tweets into a structured knowledge base.
"""

__version__ = "0.1.0"

from .agent import KnowledgeBaseAgent
from .category_manager import CategoryManager
from .markdown_writer import MarkdownWriter
from .state_manager import StateManager
from .config import Config
from .exceptions import (
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
