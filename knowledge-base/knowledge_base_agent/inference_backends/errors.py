"""
Unified Error Handling for Inference Backends

This module provides consistent error types and handling across all inference backends,
ensuring that backend-specific errors are translated to unified error types.
"""

import logging
from typing import Optional, Any, Dict
from datetime import datetime


class BackendError(Exception):
    """
    Base exception for all backend-related errors.
    
    This is the parent class for all backend errors and provides
    consistent error information across different backends.
    """
    
    def __init__(
        self, 
        message: str, 
        backend: str, 
        original_error: Optional[Exception] = None,
        error_code: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None
    ):
        """
        Initialize backend error.
        
        Args:
            message: Human-readable error message
            backend: Name of the backend that generated the error
            original_error: Original exception that caused this error
            error_code: Backend-specific error code
            context: Additional context information
        """
        self.backend = backend
        self.original_error = original_error
        self.error_code = error_code
        self.context = context or {}
        self.timestamp = datetime.utcnow()
        
        # Format the error message with backend information
        formatted_message = f"[{backend}] {message}"
        if error_code:
            formatted_message += f" (Code: {error_code})"
            
        super().__init__(formatted_message)
        
        # Log the error for debugging
        logger = logging.getLogger(__name__)
        logger.error(
            f"Backend error in {backend}: {message}",
            extra={
                'backend': backend,
                'error_code': error_code,
                'original_error': str(original_error) if original_error else None,
                'context': context
            },
            exc_info=original_error
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert error to dictionary for serialization."""
        return {
            'error_type': self.__class__.__name__,
            'message': str(self),
            'backend': self.backend,
            'error_code': self.error_code,
            'context': self.context,
            'timestamp': self.timestamp.isoformat(),
            'original_error': str(self.original_error) if self.original_error else None
        }


class BackendConnectionError(BackendError):
    """
    Error raised when unable to connect to the backend API.
    
    This includes network connectivity issues, DNS resolution failures,
    and backend service unavailability.
    """
    
    def __init__(
        self, 
        message: str, 
        backend: str, 
        original_error: Optional[Exception] = None,
        api_url: Optional[str] = None
    ):
        context = {'api_url': api_url} if api_url else {}
        super().__init__(
            message=f"Connection failed: {message}",
            backend=backend,
            original_error=original_error,
            error_code="CONNECTION_ERROR",
            context=context
        )


class BackendTimeoutError(BackendError):
    """
    Error raised when a backend request times out.
    
    This occurs when the backend takes longer than the configured
    timeout period to respond to a request.
    """
    
    def __init__(
        self, 
        message: str, 
        backend: str, 
        original_error: Optional[Exception] = None,
        timeout_seconds: Optional[float] = None,
        operation: Optional[str] = None
    ):
        context = {}
        if timeout_seconds:
            context['timeout_seconds'] = timeout_seconds
        if operation:
            context['operation'] = operation
            
        super().__init__(
            message=f"Request timed out: {message}",
            backend=backend,
            original_error=original_error,
            error_code="TIMEOUT_ERROR",
            context=context
        )


class BackendModelError(BackendError):
    """
    Error raised when there's an issue with the specified model.
    
    This includes model not found, model loading failures,
    and model-specific configuration issues.
    """
    
    def __init__(
        self, 
        message: str, 
        backend: str, 
        original_error: Optional[Exception] = None,
        model_name: Optional[str] = None,
        available_models: Optional[list] = None
    ):
        context = {}
        if model_name:
            context['model_name'] = model_name
        if available_models:
            context['available_models'] = available_models
            
        super().__init__(
            message=f"Model error: {message}",
            backend=backend,
            original_error=original_error,
            error_code="MODEL_ERROR",
            context=context
        )


class BackendAuthenticationError(BackendError):
    """
    Error raised when authentication with the backend fails.
    
    This includes invalid API keys, expired tokens,
    and insufficient permissions.
    """
    
    def __init__(
        self, 
        message: str, 
        backend: str, 
        original_error: Optional[Exception] = None
    ):
        super().__init__(
            message=f"Authentication failed: {message}",
            backend=backend,
            original_error=original_error,
            error_code="AUTH_ERROR"
        )


class BackendRateLimitError(BackendError):
    """
    Error raised when the backend rate limit is exceeded.
    
    This occurs when too many requests are made to the backend
    within a given time period.
    """
    
    def __init__(
        self, 
        message: str, 
        backend: str, 
        original_error: Optional[Exception] = None,
        retry_after: Optional[int] = None
    ):
        context = {'retry_after': retry_after} if retry_after else {}
        super().__init__(
            message=f"Rate limit exceeded: {message}",
            backend=backend,
            original_error=original_error,
            error_code="RATE_LIMIT_ERROR",
            context=context
        )


class BackendValidationError(BackendError):
    """
    Error raised when request validation fails.
    
    This includes invalid parameters, malformed requests,
    and constraint violations.
    """
    
    def __init__(
        self, 
        message: str, 
        backend: str, 
        original_error: Optional[Exception] = None,
        validation_errors: Optional[Dict[str, Any]] = None
    ):
        context = {'validation_errors': validation_errors} if validation_errors else {}
        super().__init__(
            message=f"Validation failed: {message}",
            backend=backend,
            original_error=original_error,
            error_code="VALIDATION_ERROR",
            context=context
        )


def translate_http_error(
    error: Exception, 
    backend: str, 
    operation: str = "request",
    timeout_seconds: Optional[float] = None
) -> BackendError:
    """
    Translate common HTTP errors to unified backend errors.
    
    Args:
        error: The original HTTP error
        backend: Name of the backend
        operation: Description of the operation that failed
        timeout_seconds: Timeout value if applicable
        
    Returns:
        BackendError: Appropriate backend error type
    """
    error_str = str(error).lower()
    
    # Import here to avoid circular imports
    try:
        import aiohttp
        import asyncio
        
        if isinstance(error, asyncio.TimeoutError):
            return BackendTimeoutError(
                f"Timeout during {operation}",
                backend,
                error,
                timeout_seconds=timeout_seconds,
                operation=operation
            )
        elif isinstance(error, aiohttp.ClientConnectionError):
            return BackendConnectionError(
                f"Connection failed during {operation}",
                backend,
                error
            )
        elif isinstance(error, aiohttp.ClientResponseError):
            if error.status == 401:
                return BackendAuthenticationError(
                    f"Authentication failed during {operation}",
                    backend,
                    error
                )
            elif error.status == 429:
                retry_after = error.headers.get('Retry-After')
                return BackendRateLimitError(
                    f"Rate limit exceeded during {operation}",
                    backend,
                    error,
                    retry_after=int(retry_after) if retry_after else None
                )
            elif error.status == 404:
                return BackendModelError(
                    f"Model or endpoint not found during {operation}",
                    backend,
                    error
                )
            elif 400 <= error.status < 500:
                return BackendValidationError(
                    f"Client error during {operation}: {error.message}",
                    backend,
                    error
                )
            else:
                return BackendError(
                    f"HTTP error during {operation}: {error.message}",
                    backend,
                    error,
                    error_code=f"HTTP_{error.status}"
                )
    except ImportError:
        pass
    
    # Handle timeout-related errors
    if 'timeout' in error_str or 'timed out' in error_str:
        return BackendTimeoutError(
            f"Timeout during {operation}",
            backend,
            error,
            timeout_seconds=timeout_seconds,
            operation=operation
        )
    
    # Handle connection-related errors
    if any(term in error_str for term in ['connection', 'connect', 'network', 'dns']):
        return BackendConnectionError(
            f"Connection failed during {operation}",
            backend,
            error
        )
    
    # Default to generic backend error
    return BackendError(
        f"Unexpected error during {operation}: {str(error)}",
        backend,
        error
    )


def log_backend_error(error: BackendError, logger: Optional[logging.Logger] = None) -> None:
    """
    Log a backend error with appropriate detail level.
    
    Args:
        error: The backend error to log
        logger: Logger to use (defaults to module logger)
    """
    if logger is None:
        logger = logging.getLogger(__name__)
    
    # Log with different levels based on error type
    if isinstance(error, (BackendConnectionError, BackendTimeoutError)):
        # These are often transient, log as warning
        logger.warning(
            f"Backend {error.backend} error: {error}",
            extra=error.context
        )
    elif isinstance(error, (BackendAuthenticationError, BackendModelError)):
        # These are configuration issues, log as error
        logger.error(
            f"Backend {error.backend} configuration error: {error}",
            extra=error.context
        )
    else:
        # Generic errors, log as error with full context
        logger.error(
            f"Backend {error.backend} error: {error}",
            extra=error.context,
            exc_info=error.original_error
        )