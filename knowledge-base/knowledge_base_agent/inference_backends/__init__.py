"""
Inference Backend Infrastructure

This module provides the infrastructure for supporting multiple inference backends
(Ollama, LocalAI, etc.) through a unified interface pattern.
"""

from .base import InferenceBackend
from .errors import (
    BackendError,
    BackendConnectionError, 
    BackendTimeoutError,
    BackendModelError
)
from .factory import BackendFactory

__all__ = [
    'InferenceBackend',
    'BackendError',
    'BackendConnectionError',
    'BackendTimeoutError', 
    'BackendModelError',
    'BackendFactory'
]