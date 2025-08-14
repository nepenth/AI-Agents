"""
Service layer package.

Avoid importing submodules at package import time to prevent circular imports
and failures during app startup. Import services explicitly where needed, e.g.:

from app.services.ai_service import initialize_ai_service
"""

__all__ = []