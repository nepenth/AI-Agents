class KnowledgeBaseError(Exception):
    """Base exception for knowledge base errors."""
    pass

class AgentError(KnowledgeBaseError):
    """Raised when agent operations fail."""
    pass

class BookmarksFetchError(KnowledgeBaseError):
    """Raised when bookmark fetching fails."""
    pass

class MarkdownGenerationError(KnowledgeBaseError):
    """Raised when markdown generation fails."""
    pass

class PathValidationError(KnowledgeBaseError):
    """Raised when path validation fails."""
    pass

class StateError(KnowledgeBaseError):
    """Raised when state management operations fail."""
    pass

class TweetProcessingError(KnowledgeBaseError):
    """Raised when tweet processing fails."""
    pass

class ModelInferenceError(KnowledgeBaseError):
    """Raised when AI model inference fails."""
    pass

class GitSyncError(KnowledgeBaseError):
    """Raised when GitHub sync fails."""
    pass

class ConfigurationError(KnowledgeBaseError):
    """Raised when configuration is invalid."""
    pass

class FetchError(KnowledgeBaseError):
    """Raised when failing to fetch data from external sources."""
    pass

class ProcessingError(KnowledgeBaseError):
    """Raised when failing to process content."""
    pass

class StorageError(KnowledgeBaseError):
    """Raised when failing to store or retrieve data."""
    pass

class GitError(KnowledgeBaseError):
    """Raised when Git operations fail."""
    pass

class CategoryError(KnowledgeBaseError):
    """Raised when there's an issue with category operations."""
    pass

class AIError(KnowledgeBaseError):
    """Raised when AI operations (Ollama, etc.) fail."""
    pass

class ValidationError(KnowledgeBaseError):
    """Raised when validation fails."""
    pass

class FileOperationError(KnowledgeBaseError):
    """Raised when file operations fail."""
    pass

class NetworkError(KnowledgeBaseError):
    """Raised when network operations fail."""
    pass

class MediaProcessingError(KnowledgeBaseError):
    """Raised when media processing fails."""
    pass

class ContentProcessingError(KnowledgeBaseError):
    """Content processing related errors."""
    pass
