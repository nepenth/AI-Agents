"""
Abstract Base Class for Inference Backends

This module defines the InferenceBackend interface that all backend implementations
must follow to ensure consistent behavior across different inference engines.
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
import logging


class InferenceBackend(ABC):
    """
    Abstract base class for inference backends.
    
    This interface defines the contract that all inference backends must implement
    to provide text generation, chat completion, and embedding functionality.
    """
    
    def __init__(self, config, session_manager):
        """
        Initialize the backend with configuration and session manager.
        
        Args:
            config: Configuration object containing backend-specific settings
            session_manager: HTTP session manager for making API requests
        """
        self.config = config
        self.session_manager = session_manager
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        
    @property
    @abstractmethod
    def backend_name(self) -> str:
        """Return the name of this backend (e.g., 'ollama', 'exllamav2')."""
        pass
    
    @property
    @abstractmethod
    def base_url(self) -> str:
        """Return the base URL for this backend's API."""
        pass
    
    @abstractmethod
    async def generate(
        self,
        model: str,
        prompt: str,
        temperature: float = 0.7,
        max_tokens: int = 50000,
        top_p: float = 0.9,
        timeout: Optional[int] = None,
        options: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Generate text completion using the backend's API.
        
        Args:
            model: The model to use for generation
            prompt: The input prompt text
            temperature: Controls randomness (0.0-1.0)
            max_tokens: Maximum tokens to generate
            top_p: Nucleus sampling parameter
            timeout: Request timeout in seconds
            options: Additional backend-specific options
            
        Returns:
            str: Generated text response
            
        Raises:
            BackendError: If the generation fails
            BackendTimeoutError: If the request times out
            BackendConnectionError: If connection to backend fails
        """
        pass
    
    @abstractmethod
    async def chat(
        self,
        model: str,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        top_p: float = 0.9,
        timeout: Optional[int] = None,
        options: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Generate chat completion using the backend's API.
        
        Args:
            model: The model to use for chat
            messages: List of message objects with 'role' and 'content' keys
            temperature: Controls randomness (0.0-1.0)
            top_p: Nucleus sampling parameter
            timeout: Request timeout in seconds
            options: Additional backend-specific options
            
        Returns:
            str: Generated chat response
            
        Raises:
            BackendError: If the chat generation fails
            BackendTimeoutError: If the request times out
            BackendConnectionError: If connection to backend fails
        """
        pass
    
    @abstractmethod
    async def embed(
        self,
        model: str,
        text: str,
        timeout: Optional[int] = None
    ) -> List[float]:
        """
        Generate text embeddings using the backend's API.
        
        Args:
            model: The embedding model to use
            text: The text to embed
            timeout: Request timeout in seconds
            
        Returns:
            List[float]: The generated embedding vector
            
        Raises:
            BackendError: If the embedding generation fails
            BackendTimeoutError: If the request times out
            BackendConnectionError: If connection to backend fails
        """
        pass
    
    @abstractmethod
    async def get_available_models(self) -> List[Dict[str, str]]:
        """
        Get list of available models from the backend.
        
        Returns:
            List[Dict[str, str]]: List of model dictionaries with 'id' and 'name' keys
            
        Raises:
            BackendError: If unable to retrieve models
            BackendConnectionError: If connection to backend fails
        """
        pass
    
    @abstractmethod
    async def health_check(self) -> Dict[str, Any]:
        """
        Check the health status of the backend.
        
        Returns:
            Dict[str, Any]: Health status information including:
                - status: 'healthy' or 'unhealthy'
                - backend: backend name
                - api_url: backend API URL
                - available_models: number of available models
                - error: error message if unhealthy
                
        Raises:
            BackendConnectionError: If unable to connect to backend
        """
        pass
    
    def __str__(self) -> str:
        """Return string representation of the backend."""
        return f"{self.__class__.__name__}(backend={self.backend_name}, url={self.base_url})"
    
    def __repr__(self) -> str:
        """Return detailed string representation of the backend."""
        return (f"{self.__class__.__name__}("
                f"backend='{self.backend_name}', "
                f"url='{self.base_url}', "
                f"config={type(self.config).__name__})")