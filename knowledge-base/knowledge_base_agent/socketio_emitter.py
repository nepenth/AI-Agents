"""
Lightweight SocketIO Emitter for Celery Workers

This module provides a minimal SocketIO client that Celery workers can use to emit
events cross-process via Redis message_queue, enabling real-time updates from
background tasks without requiring full SocketIO server instances.
"""

import logging
from typing import Dict, Any, Optional
from flask_socketio import SocketIO
from .config import Config

logger = logging.getLogger(__name__)


class WorkerSocketIOEmitter:
    """
    Lightweight SocketIO emitter for Celery workers.
    
    Uses Redis message_queue to emit events cross-process to the main web server's
    SocketIO instance, enabling real-time updates from background tasks.
    """
    
    def __init__(self, config: Optional[Config] = None):
        """
        Initialize the worker SocketIO emitter.
        
        Args:
            config: Configuration instance containing Redis URL
        """
        self.config = config or Config()
        self._socketio = None
        self._initialized = False
    
    def _ensure_initialized(self):
        """Lazy initialization of SocketIO client."""
        if self._initialized:
            return
        
        try:
            # Create minimal SocketIO instance with same message_queue as web server
            self._socketio = SocketIO(
                message_queue=self.config.redis_url,
                logger=False,
                engineio_logger=False
            )
            self._initialized = True
            logger.debug("WorkerSocketIOEmitter initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize WorkerSocketIOEmitter: {e}")
            self._socketio = None
            self._initialized = False
    
    def emit(self, event: str, data: Dict[str, Any], room: Optional[str] = None):
        """
        Emit an event to all connected clients via Redis message_queue.
        
        Args:
            event: SocketIO event name
            data: Event data to send
            room: Optional room to emit to (for task-specific events)
        """
        try:
            self._ensure_initialized()
            
            if not self._socketio:
                logger.warning(f"SocketIO emitter not available, cannot emit event '{event}'")
                return
            
            # Emit event via Redis message_queue
            if room:
                self._socketio.emit(event, data, room=room)
            else:
                self._socketio.emit(event, data)
                
            logger.debug(f"Emitted SocketIO event '{event}' with data: {data}")
            
        except Exception as e:
            logger.error(f"Failed to emit SocketIO event '{event}': {e}")
    
    def emit_log(self, task_id: str, message: str, level: str = "INFO", **extra_data):
        """
        Emit a log message event.
        
        Args:
            task_id: Task identifier
            message: Log message
            level: Log level
            **extra_data: Additional log data
        """
        log_data = {
            'task_id': task_id,
            'message': message,
            'level': level,
            'timestamp': extra_data.get('timestamp'),
            **{k: v for k, v in extra_data.items() if k != 'timestamp'}
        }
        
        self.emit('log', log_data)
        self.emit('live_log', log_data)  # Also emit to live_log for compatibility
    
    def emit_phase_update(self, task_id: str, phase_id: str, status: str, 
                         message: str, processed_count: int = 0, 
                         total_count: int = 0, error_count: int = 0,
                         eta_seconds: Optional[int] = None):
        """
        Emit a phase update event.
        
        Args:
            task_id: Task identifier
            phase_id: Phase identifier
            status: Phase status (active, completed, error, etc.)
            message: Phase message
            processed_count: Number of items processed
            total_count: Total number of items
            error_count: Number of errors
            eta_seconds: Estimated time to completion
        """
        phase_data = {
            'task_id': task_id,
            'phase_id': phase_id,
            'phase': phase_id,  # Alias for compatibility
            'status': status,
            'message': message,
            'processed_count': processed_count,
            'total_count': total_count,
            'error_count': error_count
        }
        
        if eta_seconds is not None:
            phase_data['eta_seconds'] = eta_seconds
        
        self.emit('phase_update', phase_data)
        self.emit('phase_status_update', phase_data)  # Also emit for compatibility
    
    def emit_phase_complete(self, task_id: str, phase_id: str, 
                           processed_count: int, total_count: int, 
                           error_count: int = 0, duration_seconds: Optional[float] = None):
        """
        Emit a phase completion event.
        
        Args:
            task_id: Task identifier
            phase_id: Phase identifier
            processed_count: Number of items processed
            total_count: Total number of items
            error_count: Number of errors
            duration_seconds: Phase duration in seconds
        """
        completion_data = {
            'task_id': task_id,
            'phase_id': phase_id,
            'phase': phase_id,  # Alias for compatibility
            'processed_count': processed_count,
            'total_count': total_count,
            'error_count': error_count
        }
        
        if duration_seconds is not None:
            completion_data['duration_seconds'] = duration_seconds
        
        self.emit('phase_complete', completion_data)
    
    def emit_task_status(self, task_id: str, is_running: bool, 
                        current_phase_message: str, started_at: Optional[str] = None,
                        updated_at: Optional[str] = None):
        """
        Emit a task status update event.
        
        Args:
            task_id: Task identifier
            is_running: Whether task is currently running
            current_phase_message: Current phase message
            started_at: Task start time (ISO format)
            updated_at: Last update time (ISO format)
        """
        status_data = {
            'task_id': task_id,
            'is_running': is_running,
            'current_phase_message': current_phase_message
        }
        
        if started_at:
            status_data['started_at'] = started_at
        if updated_at:
            status_data['updated_at'] = updated_at
        
        self.emit('task_status', status_data)
        self.emit('agent_status_update', status_data)  # Also emit for compatibility
    
    def emit_progress_update(self, task_id: str, processed_count: int, 
                           total_count: int, operation: Optional[str] = None):
        """
        Emit a progress update event.
        
        Args:
            task_id: Task identifier
            processed_count: Number of items processed
            total_count: Total number of items
            operation: Current operation description
        """
        progress_data = {
            'task_id': task_id,
            'processed_count': processed_count,
            'total_count': total_count
        }
        
        if total_count > 0:
            progress_data['percentage'] = int((processed_count / total_count) * 100)
        else:
            progress_data['percentage'] = 0
        
        if operation:
            progress_data['operation'] = operation
        
        self.emit('progress_update', progress_data)
        self.emit('task_progress', progress_data)  # Also emit for compatibility


# Global instance for easy access
_worker_emitter: Optional[WorkerSocketIOEmitter] = None


def get_worker_socketio_emitter(config: Optional[Config] = None) -> WorkerSocketIOEmitter:
    """
    Get or create the global worker SocketIO emitter instance.
    
    Args:
        config: Configuration instance
        
    Returns:
        WorkerSocketIOEmitter instance
    """
    global _worker_emitter
    
    if _worker_emitter is None:
        _worker_emitter = WorkerSocketIOEmitter(config)
    
    return _worker_emitter