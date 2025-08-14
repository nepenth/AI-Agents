"""
Custom middleware for the FastAPI application.
"""
import time
import uuid
import logging
from typing import Callable
from fastapi import FastAPI, Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Middleware to log HTTP requests and responses."""
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Generate request ID
        request_id = str(uuid.uuid4())
        request.state.request_id = request_id
        
        # Log request
        start_time = time.time()
        logger.info(
            f"Request started - {request.method} {request.url.path} "
            f"[{request_id}] from {request.client.host if request.client else 'unknown'}"
        )
        
        # Process request
        try:
            response = await call_next(request)
            
            # Log response
            process_time = time.time() - start_time
            logger.info(
                f"Request completed - {request.method} {request.url.path} "
                f"[{request_id}] {response.status_code} in {process_time:.3f}s"
            )
            
            # Add request ID to response headers
            response.headers["X-Request-ID"] = request_id
            
            return response
            
        except Exception as e:
            process_time = time.time() - start_time
            logger.error(
                f"Request failed - {request.method} {request.url.path} "
                f"[{request_id}] {str(e)} in {process_time:.3f}s"
            )
            raise


def setup_middleware(app: FastAPI) -> None:
    """Setup all middleware for the application."""
    app.add_middleware(RequestLoggingMiddleware)