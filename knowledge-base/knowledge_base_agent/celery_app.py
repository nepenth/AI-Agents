"""
Celery Application Setup for Knowledge Base Agent

This module creates and configures the Celery application for distributed task processing,
re-architecting it to integrate tightly with the Flask application context.
"""

import logging
from celery import Celery
from flask import Flask

# The Celery instance is now created in init_celery
celery_app = Celery('knowledge_base_agent')

def init_celery(app: Flask):
    """
    Initializes and configures the Celery application, binding it to the
    Flask application context.
    
    Args:
        app: The configured Flask application instance.
    """
    global celery_app
    
    # Update Celery configuration from Flask app config
    celery_app.conf.update(app.config.get('CELERY_CONFIG', {}))

    # ------------------------------------------------------------------
    # Default routing rules – ensure every task family lands on the
    # correct logical queue even when producer code uses `.delay()`.
    # You can still override per-call via ``apply_async(queue=...)``.
    # ------------------------------------------------------------------

    default_routes = {
        # Core agent orchestration & helpers
        r"knowledge_base_agent.tasks.agent.*":      {"queue": "agent"},

        # Content-processing fan-out tasks (tweet caching, media, llm, …)
        r"knowledge_base_agent.tasks.processing.*": {"queue": "processing"},

        # Chat / RAG related tasks
        r"knowledge_base_agent.tasks.chat.*":       {"queue": "chat"},
    }

    # Merge with any routes the user supplied in Flask config
    if celery_app.conf.task_routes:
        # Existing routes may be a dict or a list of routers; we handle dict case
        if isinstance(celery_app.conf.task_routes, dict):
            merged = {**default_routes, **celery_app.conf.task_routes}
            celery_app.conf.task_routes = merged
    else:
        celery_app.conf.task_routes = default_routes
    
    # Subclass Task to automatically wrap task execution in an app context
    class ContextTask(celery_app.Task):
        def __call__(self, *args, **kwargs):
            with app.app_context():
                return self.run(*args, **kwargs)

    celery_app.Task = ContextTask
    
    # Auto-discover tasks from the specified packages
    celery_app.autodiscover_tasks([
        'knowledge_base_agent.tasks.agent_tasks',
        'knowledge_base_agent.tasks.processing_tasks', 
        'knowledge_base_agent.tasks.chat_tasks',
    ], force=True)

    # Import and initialize signal handlers for monitoring
    try:
        from . import monitoring
        monitoring.initialize_monitoring(app)
        logging.info("Celery monitoring signals initialized and connected.")
    except ImportError:
        logging.warning("Celery monitoring module not found - monitoring signals not loaded.")

    return celery_app