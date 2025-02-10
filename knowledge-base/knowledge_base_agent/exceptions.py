class KnowledgeBaseError(Exception):
    """Base exception class for Knowledge Base errors."""
    pass

class FileOperationError(KnowledgeBaseError):
    """Raised when file operations fail."""
    pass

class ValidationError(KnowledgeBaseError):
    """Raised when validation fails."""
    pass

class AIProcessingError(KnowledgeBaseError):
    """Raised when AI processing fails."""
    pass

class NetworkError(KnowledgeBaseError):
    """Raised when network operations fail."""
    pass

class CategoryError(KnowledgeBaseError):
    """Raised when category operations fail."""
    pass

class MediaProcessingError(KnowledgeBaseError):
    """Raised when media processing fails."""
    pass
