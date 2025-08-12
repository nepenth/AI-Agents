"""
Modern Real-time Communication System

Implements the recommended hybrid architecture pattern:
- Durable state in Postgres + initial REST snapshot + real-time push via Socket.IO backed by Redis
- Workers emit lightweight events cross-process via Redis message_queue
- Clean separation: Postgres = source of truth, REST = initial fetch, Socket.IO = ephemeral real-time UX

This module provides standardized event payloads and communication patterns.
"""

import json
import logging
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, asdict
from flask_socketio import SocketIO
from .config import Config

logger = logging.getLogger(__name__)


@dataclass
class PhaseUpdateEvent:
    """Standardized phase update event payload."""
    task_id: str
    phase_id: str
    status: str  # active|in_progress|completed|error|interrupted
    message: str
    processed_count: int = 0
    total_count: int = 0
    error_count: int = 0
    eta_seconds: Optional[int] = None
    timestamp: Optional[str] = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now(timezone.utc).isoformat()


@dataclass
class PhaseCompleteEvent:
    """Standardized phase completion event payload."""
    task_id: str
    phase_id: str
    processed_count: int
    total_count: int
    error_count: int = 0
    duration_seconds: Optional[float] = None
    timestamp: Optional[str] = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now(timezone.utc).isoformat()


@dataclass
class TaskStatusEvent:
    """Standardized task status event payload."""
    task_id: str
    is_running: bool
    current_phase_message: str
    current_phase: Optional[str] = None
    started_at: Optional[str] = None
    updated_at: Optional[str] = None
    timestamp: Optional[str] = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now(timezone.utc).isoformat()


@dataclass
class LogEvent:
    """Standardized log event payload."""
    task_id: str
    sequence: Optional[int]
    level: str
    message: str
    component: Optional[str] = None
    phase: Optional[str] = None
    timestamp: Optional[str] = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now(timezone.utc).isoformat()


class ModernRealtimeEmitter:
    """
    Modern real-time event emitter for Celery workers.
    
    Uses Redis message_queue to emit standardized events cross-process to the main
    web server's SocketIO instance. Provides clean, type-safe event emission.
    """
    
    def __init__(self, config: Optional[Config] = None):
        """Initialize the modern real-time emitter."""
        self.config = config or Config()
        self._socketio = None
        self._initialized = False
    
    def _ensure_initialized(self):
        """Lazy initialization of SocketIO client with Redis message_queue."""
        if self._initialized:
            return
        
        try:
            # Create SocketIO instance with same message_queue as web server
            # Use the logs Redis URL for SocketIO cross-process message queue
            self._socketio = SocketIO(
                message_queue=self.config.redis_logs_url,
                logger=False,
                engineio_logger=False
            )
            self._initialized = True
            logger.debug("ModernRealtimeEmitter initialized with Redis message_queue")
        except Exception as e:
            logger.error(f"Failed to initialize ModernRealtimeEmitter: {e}")
            self._socketio = None
            self._initialized = False
    
    def _emit_event(self, event_name: str, event_data: Dict[str, Any], room: Optional[str] = None):
        """Internal method to emit events via Redis message_queue."""
        try:
            self._ensure_initialized()
            
            if not self._socketio:
                logger.warning(f"SocketIO emitter not available, cannot emit '{event_name}'")
                return
            
            # Emit via Redis message_queue for cross-process communication
            if room:
                self._socketio.emit(event_name, event_data, room=room)
            else:
                self._socketio.emit(event_name, event_data)
                
            logger.debug(f"Emitted '{event_name}' event for task {event_data.get('task_id', 'unknown')}")
            
        except Exception as e:
            logger.error(f"Failed to emit '{event_name}' event: {e}")
    
    def emit_phase_update(self, event: PhaseUpdateEvent):
        """Emit a phase update event with standardized payload."""
        event_data = asdict(event)
        
        # Emit to multiple channels for compatibility
        self._emit_event('phase_update', event_data)
        self._emit_event('phase_status_update', event_data)
        self._emit_event('task_progress', event_data)
        
        # Also emit to task-specific room if available
        task_room = f"task:{event.task_id}"
        self._emit_event('phase_update', event_data, room=task_room)
    
    def emit_phase_complete(self, event: PhaseCompleteEvent):
        """Emit a phase completion event with standardized payload."""
        event_data = asdict(event)
        
        # Emit completion event
        self._emit_event('phase_complete', event_data)
        
        # Also emit to task-specific room
        task_room = f"task:{event.task_id}"
        self._emit_event('phase_complete', event_data, room=task_room)
    
    def emit_task_status(self, event: TaskStatusEvent):
        """Emit a task status update event with standardized payload."""
        event_data = asdict(event)
        
        # Emit to multiple channels for compatibility
        self._emit_event('task_status', event_data)
        self._emit_event('agent_status_update', event_data)
        self._emit_event('status_update', event_data)
        
        # Also emit to task-specific room
        task_room = f"task:{event.task_id}"
        self._emit_event('task_status', event_data, room=task_room)
    
    def emit_log(self, event: LogEvent):
        """Emit a log event with standardized payload."""
        event_data = asdict(event)
        
        # Emit to multiple channels for compatibility
        self._emit_event('log', event_data)
        self._emit_event('live_log', event_data)
        
        # Also emit to task-specific room
        task_room = f"task:{event.task_id}"
        self._emit_event('log', event_data, room=task_room)


class RealtimeEventFactory:
    """Factory for creating standardized real-time events."""
    
    @staticmethod
    def create_phase_update(task_id: str, phase_id: str, status: str, message: str,
                           processed_count: int = 0, total_count: int = 0, 
                           error_count: int = 0, eta_seconds: Optional[int] = None) -> PhaseUpdateEvent:
        """Create a standardized phase update event."""
        return PhaseUpdateEvent(
            task_id=task_id,
            phase_id=phase_id,
            status=status,
            message=message,
            processed_count=processed_count,
            total_count=total_count,
            error_count=error_count,
            eta_seconds=eta_seconds
        )
    
    @staticmethod
    def create_phase_complete(task_id: str, phase_id: str, processed_count: int,
                             total_count: int, error_count: int = 0,
                             duration_seconds: Optional[float] = None) -> PhaseCompleteEvent:
        """Create a standardized phase completion event."""
        return PhaseCompleteEvent(
            task_id=task_id,
            phase_id=phase_id,
            processed_count=processed_count,
            total_count=total_count,
            error_count=error_count,
            duration_seconds=duration_seconds
        )
    
    @staticmethod
    def create_task_status(task_id: str, is_running: bool, current_phase_message: str,
                          current_phase: Optional[str] = None, started_at: Optional[str] = None,
                          updated_at: Optional[str] = None) -> TaskStatusEvent:
        """Create a standardized task status event."""
        return TaskStatusEvent(
            task_id=task_id,
            is_running=is_running,
            current_phase_message=current_phase_message,
            current_phase=current_phase,
            started_at=started_at,
            updated_at=updated_at
        )
    
    @staticmethod
    def create_log_event(task_id: str, level: str, message: str, sequence: Optional[int] = None,
                        component: Optional[str] = None, phase: Optional[str] = None) -> LogEvent:
        """Create a standardized log event."""
        return LogEvent(
            task_id=task_id,
            sequence=sequence,
            level=level,
            message=message,
            component=component,
            phase=phase
        )


# Global emitter instance
_global_emitter: Optional[ModernRealtimeEmitter] = None


def get_realtime_emitter(config: Optional[Config] = None) -> ModernRealtimeEmitter:
    """Get or create the global real-time emitter instance."""
    global _global_emitter
    
    if _global_emitter is None:
        _global_emitter = ModernRealtimeEmitter(config)
    
    return _global_emitter


def emit_phase_update(task_id: str, phase_id: str, status: str, message: str,
                     processed_count: int = 0, total_count: int = 0, 
                     error_count: int = 0, eta_seconds: Optional[int] = None,
                     config: Optional[Config] = None):
    """Convenience function to emit a phase update event."""
    emitter = get_realtime_emitter(config)
    event = RealtimeEventFactory.create_phase_update(
        task_id, phase_id, status, message, processed_count, 
        total_count, error_count, eta_seconds
    )
    emitter.emit_phase_update(event)


def emit_phase_complete(task_id: str, phase_id: str, processed_count: int,
                       total_count: int, error_count: int = 0,
                       duration_seconds: Optional[float] = None,
                       config: Optional[Config] = None):
    """Convenience function to emit a phase completion event."""
    emitter = get_realtime_emitter(config)
    event = RealtimeEventFactory.create_phase_complete(
        task_id, phase_id, processed_count, total_count, error_count, duration_seconds
    )
    emitter.emit_phase_complete(event)


def emit_task_status(task_id: str, is_running: bool, current_phase_message: str,
                    current_phase: Optional[str] = None, started_at: Optional[str] = None,
                    updated_at: Optional[str] = None, config: Optional[Config] = None):
    """Convenience function to emit a task status event."""
    emitter = get_realtime_emitter(config)
    event = RealtimeEventFactory.create_task_status(
        task_id, is_running, current_phase_message, current_phase, started_at, updated_at
    )
    emitter.emit_task_status(event)


def emit_log_event(task_id: str, level: str, message: str, sequence: Optional[int] = None,
                  component: Optional[str] = None, phase: Optional[str] = None,
                  config: Optional[Config] = None):
    """Convenience function to emit a log event."""
    emitter = get_realtime_emitter(config)
    event = RealtimeEventFactory.create_log_event(
        task_id, level, message, sequence, component, phase
    )
    emitter.emit_log(event)