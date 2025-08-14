"""
Celery application configuration with comprehensive task queue infrastructure.
"""
import logging
from celery import Celery
from celery.signals import task_prerun, task_postrun, task_failure, worker_ready
from kombu import Queue

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

# Create Celery app
celery_app = Celery(
    "ai_agent_tasks",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=[
        "app.tasks.content_processing",
        "app.tasks.content_fetching", 
        "app.tasks.ai_processing",
        "app.tasks.synthesis_tasks",
        "app.tasks.monitoring",
        "app.tasks.base"
    ]
)

# Configure task routing and queues
celery_app.conf.update(
    # Serialization
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    
    # Timezone
    timezone="UTC",
    enable_utc=True,
    
    # Task tracking
    task_track_started=True,
    task_send_sent_event=True,
    task_store_eager_result=True,
    
    # Task execution
    task_time_limit=60 * 60,  # 1 hour hard limit
    task_soft_time_limit=50 * 60,  # 50 minutes soft limit
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    
    # Worker configuration
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=100,
    worker_disable_rate_limits=False,
    
    # Result backend
    result_expires=24 * 60 * 60,  # 24 hours
    result_persistent=True,
    
    # Task routing
    task_routes={
        'app.tasks.content_fetching.*': {'queue': 'content_fetching'},
        'app.tasks.ai_processing.*': {'queue': 'ai_processing'},
        'app.tasks.synthesis_tasks.*': {'queue': 'synthesis'},
        'app.tasks.monitoring.*': {'queue': 'monitoring'},
        'app.tasks.content_processing.*': {'queue': 'default'},
    },
    
    # Queue definitions
    task_default_queue='default',
    task_queues=(
        Queue('default', routing_key='default'),
        Queue('content_fetching', routing_key='content_fetching'),
        Queue('ai_processing', routing_key='ai_processing'),
        Queue('synthesis', routing_key='synthesis'),
        Queue('monitoring', routing_key='monitoring'),
        Queue('priority', routing_key='priority'),
    ),
    
    # Rate limiting
    task_annotations={
        'app.tasks.ai_processing.*': {'rate_limit': '10/m'},
        'app.tasks.content_fetching.*': {'rate_limit': '30/m'},
        'app.tasks.synthesis_tasks.*': {'rate_limit': '5/m'},
    },
    
    # Retry configuration
    task_default_retry_delay=60,  # 1 minute
    task_max_retries=3,
    
    # Monitoring
    worker_send_task_events=True,
    task_send_events=True,
)


@task_prerun.connect
def task_prerun_handler(sender=None, task_id=None, task=None, args=None, kwargs=None, **kwds):
    """Handle task pre-run events."""
    logger.info(f"Task {task.name} [{task_id}] starting with args={args}, kwargs={kwargs}")


@task_postrun.connect
def task_postrun_handler(sender=None, task_id=None, task=None, args=None, kwargs=None, 
                        retval=None, state=None, **kwds):
    """Handle task post-run events."""
    logger.info(f"Task {task.name} [{task_id}] completed with state={state}")


@task_failure.connect
def task_failure_handler(sender=None, task_id=None, exception=None, traceback=None, einfo=None, **kwds):
    """Handle task failure events."""
    logger.error(f"Task {sender.name} [{task_id}] failed: {exception}")
    logger.error(f"Traceback: {traceback}")


@worker_ready.connect
def worker_ready_handler(sender=None, **kwargs):
    """Handle worker ready events."""
    logger.info(f"Celery worker {sender.hostname} is ready")


# Health check task
@celery_app.task(name="health_check")
def health_check():
    """Simple health check task."""
    return {"status": "healthy", "message": "Celery worker is operational"}