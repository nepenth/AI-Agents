"""
Logging configuration for the application.
"""
import logging
import sys
from typing import Dict, Any
from pythonjsonlogger import jsonlogger

from app.config import get_settings


def setup_logging() -> None:
    """Setup application logging configuration."""
    settings = get_settings()
    
    # Configure root logger
    logging.basicConfig(
        level=getattr(logging, settings.LOG_LEVEL.upper()),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout)
        ]
    )
    
    # Configure JSON logging for production
    if not settings.DEBUG:
        # Create JSON formatter
        json_formatter = jsonlogger.JsonFormatter(
            '%(asctime)s %(name)s %(levelname)s %(message)s'
        )
        
        # Update handlers to use JSON formatter
        for handler in logging.root.handlers:
            handler.setFormatter(json_formatter)
    
    # Set specific logger levels
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.pool").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.access").setLevel(logging.INFO)
    
    # Application loggers
    logging.getLogger("app").setLevel(getattr(logging, settings.LOG_LEVEL.upper()))
    logging.getLogger("api").setLevel(getattr(logging, settings.LOG_LEVEL.upper()))
    
    logging.info("Logging configuration completed")


def get_logger(name: str) -> logging.Logger:
    """Get a logger instance with the specified name."""
    return logging.getLogger(name)