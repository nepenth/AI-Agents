"""
Backend Factory for Dynamic Backend Selection

This module provides the factory pattern implementation for creating
appropriate inference backends based on configuration.
"""

import logging
from typing import Type, Dict, Any, Optional

from .base import InferenceBackend
from .errors import BackendError, BackendConnectionError
from ..config import Config


class BackendFactory:
    """
    Factory class for creating inference backends based on configuration.
    
    This factory handles backend selection, validation, and instantiation
    with proper error handling and logging.
    """
    
    # Registry of available backends
    _backends: Dict[str, Type[InferenceBackend]] = {}
    
    @classmethod
    def register_backend(cls, name: str, backend_class: Type[InferenceBackend]) -> None:
        """
        Register a backend implementation.
        
        Args:
            name: Backend name (e.g., 'ollama', 'exllamav2')
            backend_class: Backend implementation class
        """
        cls._backends[name.lower()] = backend_class
        logging.info(f"Registered inference backend: {name}")
    
    @classmethod
    def get_available_backends(cls) -> Dict[str, Type[InferenceBackend]]:
        """
        Get all registered backends.
        
        Returns:
            Dict mapping backend names to their implementation classes
        """
        return cls._backends.copy()
    
    @classmethod
    def create_backend(
        cls, 
        config: Config, 
        session_manager: Any,
        backend_name: Optional[str] = None
    ) -> InferenceBackend:
        """
        Create an inference backend based on configuration.
        
        Args:
            config: Configuration object
            session_manager: HTTP session manager
            backend_name: Override backend name (defaults to config.inference_backend)
            
        Returns:
            InferenceBackend: Configured backend instance
            
        Raises:
            BackendError: If backend creation fails
        """
        logger = logging.getLogger(__name__)
        
        # Determine which backend to use
        selected_backend = backend_name or getattr(config, 'inference_backend', 'ollama')
        selected_backend = selected_backend.lower()
        
        logger.info(f"Creating inference backend: {selected_backend}")
        
        # Validate backend selection
        if selected_backend not in cls._backends:
            available = list(cls._backends.keys())
            logger.warning(
                f"Unknown backend '{selected_backend}'. Available backends: {available}. "
                f"Falling back to 'ollama'"
            )
            selected_backend = 'ollama'
            
            # If ollama is also not available, raise error
            if selected_backend not in cls._backends:
                raise BackendError(
                    f"No backends available. Requested: {backend_name or config.inference_backend}",
                    backend="factory",
                    context={'available_backends': available}
                )
        
        # Get the backend class
        backend_class = cls._backends[selected_backend]
        
        try:
            # Create and return the backend instance
            backend = backend_class(config, session_manager)
            logger.info(f"Successfully created {selected_backend} backend: {backend}")
            return backend
            
        except Exception as e:
            logger.error(f"Failed to create {selected_backend} backend: {e}", exc_info=True)
            
            # If this is not the fallback backend, try falling back to ollama
            if selected_backend != 'ollama' and 'ollama' in cls._backends:
                logger.warning(f"Falling back to ollama backend due to {selected_backend} creation failure")
                try:
                    fallback_backend = cls._backends['ollama'](config, session_manager)
                    logger.info(f"Successfully created fallback ollama backend: {fallback_backend}")
                    return fallback_backend
                except Exception as fallback_error:
                    logger.error(f"Fallback to ollama also failed: {fallback_error}", exc_info=True)
                    raise BackendError(
                        f"Failed to create both {selected_backend} and fallback ollama backends",
                        backend="factory",
                        original_error=e,
                        context={
                            'primary_error': str(e),
                            'fallback_error': str(fallback_error)
                        }
                    )
            else:
                # No fallback available or already trying fallback
                raise BackendError(
                    f"Failed to create {selected_backend} backend",
                    backend="factory",
                    original_error=e
                )
    
    @classmethod
    def validate_backend_config(cls, config: Config, backend_name: Optional[str] = None) -> Dict[str, Any]:
        """
        Validate backend configuration without creating the backend.
        
        Args:
            config: Configuration object
            backend_name: Backend name to validate (defaults to config.inference_backend)
            
        Returns:
            Dict containing validation results:
                - valid: bool indicating if configuration is valid
                - backend: backend name being validated
                - errors: list of validation errors
                - warnings: list of validation warnings
        """
        logger = logging.getLogger(__name__)
        
        selected_backend = backend_name or getattr(config, 'inference_backend', 'ollama')
        selected_backend = selected_backend.lower()
        
        result = {
            'valid': True,
            'backend': selected_backend,
            'errors': [],
            'warnings': []
        }
        
        # Check if backend is registered
        if selected_backend not in cls._backends:
            available = list(cls._backends.keys())
            result['errors'].append(
                f"Unknown backend '{selected_backend}'. Available: {available}"
            )
            result['valid'] = False
            return result
        
        # Backend-specific validation
        try:
            if selected_backend == 'ollama':
                # Validate Ollama configuration
                if not hasattr(config, 'ollama_url') or not config.ollama_url:
                    result['errors'].append("OLLAMA_URL is required for Ollama backend")
                    result['valid'] = False
                    
            elif selected_backend == 'exllamav2':
                # Validate ExLlamaV2 configuration
                if not hasattr(config, 'exllamav2_api_url') or not config.exllamav2_api_url:
                    result['warnings'].append(
                        "EXLLAMAV2_API_URL not set, using default: http://localhost:5000"
                    )
                
                # Check timeout configuration
                timeout = getattr(config, 'exllamav2_timeout', 180)
                if timeout < 30:
                    result['warnings'].append(
                        f"ExLlamaV2 timeout ({timeout}s) is very low, consider increasing"
                    )
                    
        except Exception as e:
            logger.error(f"Error during backend configuration validation: {e}", exc_info=True)
            result['errors'].append(f"Configuration validation error: {str(e)}")
            result['valid'] = False
        
        return result
    
    @classmethod
    def get_backend_info(cls, backend_name: str) -> Dict[str, Any]:
        """
        Get information about a specific backend.
        
        Args:
            backend_name: Name of the backend
            
        Returns:
            Dict containing backend information
        """
        backend_name = backend_name.lower()
        
        if backend_name not in cls._backends:
            return {
                'name': backend_name,
                'available': False,
                'error': f"Backend '{backend_name}' not registered"
            }
        
        backend_class = cls._backends[backend_name]
        
        return {
            'name': backend_name,
            'available': True,
            'class': backend_class.__name__,
            'module': backend_class.__module__,
            'description': backend_class.__doc__ or "No description available"
        }


def auto_register_backends() -> None:
    """
    Automatically register all available backend implementations.
    
    This function attempts to import and register all known backend
    implementations, handling import errors gracefully.
    """
    logger = logging.getLogger(__name__)
    
    # Try to register Ollama backend
    try:
        from .ollama_backend import OllamaBackend
        BackendFactory.register_backend('ollama', OllamaBackend)
    except ImportError as e:
        logger.warning(f"Could not register Ollama backend: {e}")
    
    # Try to register LocalAI backend
    try:
        from .localai_backend import LocalAIBackend
        BackendFactory.register_backend('localai', LocalAIBackend)
    except ImportError as e:
        logger.debug(f"Could not register LocalAI backend: {e}")
    
    # Log registered backends
    registered = list(BackendFactory.get_available_backends().keys())
    logger.info(f"Auto-registered inference backends: {registered}")


# Auto-register backends when module is imported
auto_register_backends()