"""
Base classes for Celery tasks with progress tracking and error handling.
"""

import logging
import time
import traceback
from typing import Dict, Any, Optional, List
from celery import Task
from celery.exceptions import Retry, WorkerLostError
from dataclasses import dataclass, asdict
from enum import Enum

from app.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


class TaskState(str, Enum):
    """Task execution states."""
    PENDING = "PENDING"
    STARTED = "STARTED"
    PROGRESS = "PROGRESS"
    SUCCESS = "SUCCESS"
    FAILURE = "FAILURE"
    RETRY = "RETRY"
    REVOKED = "REVOKED"


@dataclass
class TaskProgress:
    """Task progress information."""
    current: int
    total: int
    status: str
    phase: Optional[str] = None
    details: Optional[Dict[str, Any]] = None
    start_time: Optional[float] = None
    estimated_completion: Optional[float] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)
    
    @property
    def percentage(self) -> float:
        """Calculate completion percentage."""
        if self.total == 0:
            return 0.0
        return min(100.0, (self.current / self.total) * 100.0)


@dataclass
class TaskResult:
    """Task execution result."""
    success: bool
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    error_type: Optional[str] = None
    execution_time: Optional[float] = None
    retry_count: Optional[int] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)


class BaseTask(Task):
    """Base task class with enhanced progress tracking and error handling."""
    
    # Task configuration
    autoretry_for = (Exception,)
    retry_kwargs = {'max_retries': 3, 'countdown': 60}
    retry_backoff = True
    retry_backoff_max = 600  # 10 minutes
    retry_jitter = True
    
    def __init__(self):
        super().__init__()
        self.start_time = None
        self.progress = None
    
    def on_retry(self, exc, task_id, args, kwargs, einfo):
        """Handle task retry."""
        logger.warning(f"Task {self.name} [{task_id}] retrying due to: {exc}")
        self.update_state(
            state=TaskState.RETRY,
            meta={
                'error': str(exc),
                'retry_count': self.request.retries,
                'max_retries': self.max_retries
            }
        )
    
    def on_failure(self, exc, task_id, args, kwargs, einfo):
        """Handle task failure."""
        logger.error(f"Task {self.name} [{task_id}] failed: {exc}")
        
        error_result = TaskResult(
            success=False,
            error=str(exc),
            error_type=type(exc).__name__,
            execution_time=time.time() - self.start_time if self.start_time else None,
            retry_count=self.request.retries
        )
        
        self.update_state(
            state=TaskState.FAILURE,
            meta=error_result.to_dict()
        )
    
    def on_success(self, retval, task_id, args, kwargs):
        """Handle task success."""
        logger.info(f"Task {self.name} [{task_id}] completed successfully")
        
        if isinstance(retval, dict) and 'success' not in retval:
            # Wrap return value in TaskResult format
            success_result = TaskResult(
                success=True,
                data=retval,
                execution_time=time.time() - self.start_time if self.start_time else None,
                retry_count=self.request.retries
            )
            return success_result.to_dict()
        
        return retval
    
    def update_progress(
        self,
        current: int,
        total: int,
        status: str,
        phase: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        """Update task progress."""
        if not self.start_time:
            self.start_time = time.time()
        
        # Calculate estimated completion time
        if current > 0 and self.start_time:
            elapsed = time.time() - self.start_time
            rate = current / elapsed
            remaining = total - current
            estimated_completion = time.time() + (remaining / rate) if rate > 0 else None
        else:
            estimated_completion = None
        
        self.progress = TaskProgress(
            current=current,
            total=total,
            status=status,
            phase=phase,
            details=details,
            start_time=self.start_time,
            estimated_completion=estimated_completion
        )
        
        self.update_state(
            state=TaskState.PROGRESS,
            meta=self.progress.to_dict()
        )
        
        # Send WebSocket notification
        try:
            import asyncio
            from app.websocket.pubsub import get_notification_service
            
            # Get current event loop or create new one
            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
            
            # Send notification asynchronously
            notification_service = get_notification_service()
            task_id = getattr(self.request, 'id', 'unknown')
            
            # Create task to send notification
            loop.create_task(notification_service.notify_task_progress(
                task_id, self.progress.to_dict()
            ))
            
        except Exception as e:
            logger.warning(f"Failed to send WebSocket progress notification: {e}")
        
        logger.debug(f"Task {self.name} progress: {current}/{total} - {status}")
    
    def handle_exception(self, exc: Exception, context: str = "") -> None:
        """Handle exceptions with proper logging and state updates."""
        error_msg = f"{context}: {str(exc)}" if context else str(exc)
        logger.error(f"Task {self.name} error - {error_msg}")
        logger.error(f"Exception traceback: {traceback.format_exc()}")
        
        # Check if this is a retryable exception
        if isinstance(exc, (ConnectionError, TimeoutError, WorkerLostError)):
            logger.info(f"Retrying task {self.name} due to retryable exception")
            raise self.retry(exc=exc)
        
        # For non-retryable exceptions, fail the task
        raise exc
    
    def validate_inputs(self, *args, **kwargs) -> bool:
        """Validate task inputs. Override in subclasses."""
        return True
    
    def cleanup(self) -> None:
        """Cleanup resources. Override in subclasses."""
        pass
    
    def __call__(self, *args, **kwargs):
        """Enhanced task execution with validation and cleanup."""
        try:
            # Validate inputs
            if not self.validate_inputs(*args, **kwargs):
                raise ValueError("Invalid task inputs")
            
            # Initialize progress tracking
            self.start_time = time.time()
            self.update_progress(0, 100, "Starting task execution...")
            
            # Execute the task
            result = super().__call__(*args, **kwargs)
            
            return result
            
        except Exception as exc:
            self.handle_exception(exc, "Task execution failed")
        finally:
            # Always cleanup
            try:
                self.cleanup()
            except Exception as cleanup_exc:
                logger.error(f"Cleanup failed for task {self.name}: {cleanup_exc}")


class ContentProcessingTask(BaseTask):
    """Base class for content processing tasks."""
    
    # Longer timeout for content processing
    time_limit = 30 * 60  # 30 minutes
    soft_time_limit = 25 * 60  # 25 minutes
    
    def validate_inputs(self, *args, **kwargs) -> bool:
        """Validate content processing inputs."""
        # Basic validation - override in subclasses for specific validation
        return len(args) > 0 or len(kwargs) > 0


class AIProcessingTask(BaseTask):
    """Base class for AI processing tasks."""
    
    # AI tasks may take longer
    time_limit = 45 * 60  # 45 minutes
    soft_time_limit = 40 * 60  # 40 minutes
    
    # More conservative retry for AI tasks
    retry_kwargs = {'max_retries': 2, 'countdown': 120}
    
    def validate_inputs(self, *args, **kwargs) -> bool:
        """Validate AI processing inputs."""
        # Ensure we have content to process
        if args and len(args) > 0:
            return True
        if kwargs and any(key in kwargs for key in ['content', 'text', 'prompt']):
            return True
        return False


class FetchingTask(BaseTask):
    """Base class for content fetching tasks."""
    
    # Shorter timeout for fetching
    time_limit = 15 * 60  # 15 minutes
    soft_time_limit = 12 * 60  # 12 minutes
    
    # More aggressive retry for network tasks
    retry_kwargs = {'max_retries': 5, 'countdown': 30}
    
    def validate_inputs(self, *args, **kwargs) -> bool:
        """Validate fetching inputs."""
        # Ensure we have sources to fetch from
        if args and len(args) > 0:
            return True
        if kwargs and any(key in kwargs for key in ['urls', 'sources', 'source_config']):
            return True
        return False


class SynthesisTask(BaseTask):
    """Base class for synthesis generation tasks."""
    
    # Synthesis tasks can take very long
    time_limit = 60 * 60  # 1 hour
    soft_time_limit = 55 * 60  # 55 minutes
    
    # Conservative retry for synthesis
    retry_kwargs = {'max_retries': 1, 'countdown': 300}  # 5 minutes
    
    def validate_inputs(self, *args, **kwargs) -> bool:
        """Validate synthesis inputs."""
        # Ensure we have category information
        if kwargs and any(key in kwargs for key in ['main_category', 'sub_category', 'category']):
            return True
        if args and len(args) >= 2:  # main_category, sub_category
            return True
        return False


class MonitoringTask(BaseTask):
    """Base class for monitoring and maintenance tasks."""
    
    # Quick execution for monitoring
    time_limit = 5 * 60  # 5 minutes
    soft_time_limit = 4 * 60  # 4 minutes
    
    # No retry for monitoring tasks
    autoretry_for = ()
    retry_kwargs = {'max_retries': 0}


# Task registry for easy access
TASK_CLASSES = {
    'base': BaseTask,
    'content_processing': ContentProcessingTask,
    'ai_processing': AIProcessingTask,
    'fetching': FetchingTask,
    'synthesis': SynthesisTask,
    'monitoring': MonitoringTask,
}


def get_task_class(task_type: str) -> BaseTask:
    """Get task class by type."""
    return TASK_CLASSES.get(task_type, BaseTask)