from typing import Optional

# --- Base Exception ---

class KnowledgeBaseAgentError(Exception):
    """Base exception class for all application-specific errors."""
    def __init__(self, message: str, original_exception: Optional[Exception] = None):
        self.original_exception = original_exception
        if original_exception:
            # Ensure we don't create overly long messages if the original exception message is huge
            orig_msg = str(original_exception).split('\n')[0] # Take first line
            message += f" (Caused by: {type(original_exception).__name__}: {orig_msg})"
        super().__init__(message)

# --- Configuration Errors ---

class ConfigurationError(KnowledgeBaseAgentError):
    """Error related to application configuration loading or validation."""
    pass

# --- Interface Errors ---

class InterfaceError(KnowledgeBaseAgentError):
    """Base exception for errors interacting with external services."""
    def __init__(self, service_name: str, message: Optional[str] = None, original_exception: Optional[Exception] = None):
        self.service_name = service_name
        full_message = f"Error interacting with {service_name}"
        if message:
            full_message += f": {message}"
        super().__init__(full_message, original_exception)

class OllamaError(InterfaceError):
    """Specific error related to Ollama API interactions."""
    def __init__(self, message: Optional[str] = None, original_exception: Optional[Exception] = None):
        super().__init__("Ollama", message, original_exception)

class PlaywrightError(InterfaceError):
    """Specific error related to Playwright/browser automation."""
    def __init__(self, message: Optional[str] = None, original_exception: Optional[Exception] = None):
        super().__init__("Playwright", message, original_exception)

class GitError(InterfaceError):
    """Specific error related to Git operations."""
    def __init__(self, message: Optional[str] = None, original_exception: Optional[Exception] = None):
        super().__init__("Git", message, original_exception)

class HttpClientError(InterfaceError):
    """Specific error related to general HTTP client operations."""
    def __init__(self, url: str, status_code: Optional[int] = None, message: Optional[str] = None, original_exception: Optional[Exception] = None):
        self.url = url
        self.status_code = status_code
        http_message = f"HTTP request failed for URL: {url}"
        if status_code:
            http_message += f" (Status Code: {status_code})"
        if message:
            http_message += f" - {message}"
        super().__init__("HTTP Client", http_message, original_exception)


# --- Processing Pipeline Errors ---

class ProcessingError(KnowledgeBaseAgentError):
    """Base exception for errors occurring during the agent's processing pipeline."""
    def __init__(self, phase_name: str, tweet_id: Optional[str] = None, message: Optional[str] = None, original_exception: Optional[Exception] = None):
        self.phase_name = phase_name
        self.tweet_id = tweet_id
        full_message = f"Error during processing phase '{phase_name}'"
        if tweet_id:
            full_message += f" for tweet ID '{tweet_id}'"
        if message:
            full_message += f": {message}"
        super().__init__(full_message, original_exception)

class FetcherError(ProcessingError):
    """Error during the fetching phase (bookmarks or tweet data)."""
    def __init__(self, tweet_id: Optional[str] = None, message: Optional[str] = None, original_exception: Optional[Exception] = None):
        super().__init__("Fetcher", tweet_id, message, original_exception)

class CacherError(ProcessingError):
    """Error during the caching phase (URL expansion, media download, validation)."""
    def __init__(self, tweet_id: Optional[str] = None, message: Optional[str] = None, original_exception: Optional[Exception] = None):
        super().__init__("Cacher", tweet_id, message, original_exception)

class InterpretationError(ProcessingError):
    """Error during the media interpretation phase."""
    def __init__(self, tweet_id: Optional[str] = None, message: Optional[str] = None, original_exception: Optional[Exception] = None):
        super().__init__("Interpreter", tweet_id, message, original_exception)

class CategorizationError(ProcessingError):
    """Error during the content categorization phase."""
    def __init__(self, tweet_id: Optional[str] = None, message: Optional[str] = None, original_exception: Optional[Exception] = None):
        super().__init__("Categorizer", tweet_id, message, original_exception)

class GenerationError(ProcessingError):
    """Error during the KB item generation phase."""
    def __init__(self, tweet_id: Optional[str] = None, message: Optional[str] = None, original_exception: Optional[Exception] = None):
        super().__init__("Generator", tweet_id, message, original_exception)

class IndexerError(ProcessingError):
    """Error during the index generation phase."""
    def __init__(self, message: Optional[str] = None, original_exception: Optional[Exception] = None):
        # Indexing might not be tied to a specific tweet ID
        super().__init__("Indexer", tweet_id=None, message=message, original_exception=original_exception)

class DBSyncError(ProcessingError):
    """Error during the database synchronization phase."""
    def __init__(self, tweet_id: Optional[str] = None, message: Optional[str] = None, original_exception: Optional[Exception] = None):
        super().__init__("DBSync", tweet_id, message, original_exception)


# --- Other Application Errors ---

class StateManagementError(KnowledgeBaseAgentError):
    """Error related to loading, saving, or managing processing state."""
    pass

class FileOperationError(KnowledgeBaseAgentError):
    """Error during file system operations (reading, writing, copying)."""
    def __init__(self, file_path: str | object, operation: str, message: Optional[str] = None, original_exception: Optional[Exception] = None):
        # Handle Path objects gracefully
        self.file_path = str(file_path)
        self.operation = operation # e.g., "read", "write", "copy", "delete", "create_dir"
        full_message = f"File operation '{operation}' failed for path '{self.file_path}'"
        if message:
            full_message += f": {message}"
        super().__init__(full_message, original_exception)
