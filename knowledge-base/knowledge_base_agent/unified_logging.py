"""
Enhanced Unified Logging System for Knowledge Base Agent

This module provides a comprehensive interface for all logging, progress updates,
and structured event emission that routes everything through Redis/TaskProgressManager,
completely eliminating direct SocketIO emission patterns.

Features:
- Structured event emission for phases, progress, and status
- Enhanced logging with component identification and structured data
- Comprehensive error handling with context and tracebacks
- Performance optimization with async operations
"""

import logging
import asyncio
import traceback
import json
import sys
from datetime import datetime, timezone
from typing import Optional, Dict, Any, Union
from .task_progress import TaskProgressManager, get_progress_manager
from .config import Config


class StructuredEventEmitter:
    """
    Handles structured event emission to Redis for real-time updates.
    Provides type-safe event emission with validation and error handling.
    """
    
    def __init__(self, task_id: str, progress_manager: TaskProgressManager):
        self.task_id = task_id
        self.progress_manager = progress_manager
        self._loop = None
    
    def _ensure_loop(self):
        """Ensure we have an event loop for async operations."""
        try:
            self._loop = asyncio.get_event_loop()
        except RuntimeError:
            self._loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self._loop)
    
    def _safe_async_call(self, coro):
        """Safely execute async coroutine in current context."""
        try:
            self._ensure_loop()
            if self._loop.is_running():
                future = asyncio.run_coroutine_threadsafe(coro, self._loop)
                try:
                    future.result(timeout=0.1)
                except:
                    pass  # Event was scheduled, that's what matters
            else:
                self._loop.run_until_complete(coro)
        except Exception as e:
            # Use print instead of logging.error to avoid circular logging issues
            print(f"[UNIFIED_LOGGER_ERROR] Failed to emit event: {e}", file=sys.stderr)
    
    def emit_log_event(self, message: str, level: str, component: str = None, 
                      structured_data: Dict[str, Any] = None, traceback_info: str = None):
        """Emit enhanced log event with structured data support."""
        log_entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "task_id": self.task_id,
            "level": level,
            "component": component or "unknown",
            "message": message,
            "structured_data": structured_data or {},
            "traceback": traceback_info
        }
        
        # Remove None values to keep events clean
        log_entry = {k: v for k, v in log_entry.items() if v is not None}
        
        self._safe_async_call(
            self.progress_manager.log_message(
                self.task_id, message, level, 
                component=component,
                structured_data=structured_data,
                traceback=traceback_info
            )
        )
    
    def emit_phase_event(self, event_type: str, phase_name: str, 
                        phase_description: str = None, estimated_duration: int = None,
                        start_time: str = None, end_time: str = None,
                        result: Any = None, error: str = None, 
                        traceback_info: str = None):
        """Emit comprehensive phase-related events."""
        phase_data = {
            "phase_name": phase_name,
            "phase_description": phase_description,
            "estimated_duration": estimated_duration,
            "start_time": start_time,
            "end_time": end_time,
            "result": result,
            "error": error,
            "traceback": traceback_info,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        # Remove None values to keep events clean
        phase_data = {k: v for k, v in phase_data.items() if v is not None}
        
        self._safe_async_call(
            self.progress_manager.publish_phase_event(
                self.task_id, event_type, phase_data
            )
        )
    
    def emit_progress_event(self, current: int, total: int, operation: str = None,
                           percentage: float = None, eta: str = None):
        """Emit progress update with comprehensive metrics."""
        if percentage is None and total > 0:
            percentage = round((current / total) * 100, 2)
        
        progress_data = {
            "current": current,
            "total": total,
            "percentage": percentage,
            "operation": operation,
            "eta": eta,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        # Remove None values to keep events clean
        progress_data = {k: v for k, v in progress_data.items() if v is not None}
        
        self._safe_async_call(
            self.progress_manager.publish_progress_update(
                self.task_id, progress_data
            )
        )
    
    def emit_status_event(self, status: str, details: Dict[str, Any] = None,
                         phase: str = None, message: str = None):
        """Emit status change events with comprehensive context."""
        status_data = {
            "status": status,
            "phase": phase,
            "message": message,
            "details": details or {},
            "timestamp": datetime.utcnow().isoformat()
        }
        
        # Remove None values to keep events clean
        status_data = {k: v for k, v in status_data.items() if v is not None}
        
        self._safe_async_call(
            self.progress_manager.publish_agent_status_update({
                "task_id": self.task_id,
                **status_data
            })
        )


class EnhancedUnifiedLogger:
    """
    Enhanced unified logger with comprehensive event emission capabilities.
    
    Provides structured logging, phase management, progress tracking, and status updates
    while maintaining complete compatibility with the existing UnifiedLogger interface.
    """
    
    def __init__(self, task_id: str, config: Optional[Config] = None):
        self.task_id = task_id
        self.config = config or Config()
        self.progress_manager = get_progress_manager(self.config)
        self.event_emitter = StructuredEventEmitter(task_id, self.progress_manager)
        self._loop = None
        
        # Phase tracking for timing and context
        self._active_phases = {}
        self._phase_start_times = {}
    
    def _get_caller_component(self) -> str:
        """Automatically determine the calling component from stack trace."""
        try:
            frame = traceback.extract_stack()[-3]  # Go back 3 frames to get actual caller
            filename = frame.filename.split('/')[-1].replace('.py', '')
            return filename
        except:
            return "unknown"
    
    # ===== ENHANCED LOGGING METHODS =====
    
    def log_structured(self, message: str, level: str = "INFO", 
                      component: str = None, structured_data: Dict[str, Any] = None,
                      include_traceback: bool = False):
        """Enhanced logging with structured data support and automatic component detection."""
        component = component or self._get_caller_component()
        traceback_info = None
        
        if include_traceback or level in ["ERROR", "CRITICAL"]:
            traceback_info = traceback.format_exc() if include_traceback else None
        
        self.event_emitter.emit_log_event(
            message, level, component, structured_data, traceback_info
        )
    
    def log_error(self, message: str, error: Exception = None, 
                  component: str = None, structured_data: Dict[str, Any] = None):
        """Specialized error logging with exception context."""
        component = component or self._get_caller_component()
        
        if error:
            error_data = {
                "error_type": type(error).__name__,
                "error_message": str(error),
                **(structured_data or {})
            }
            message = f"{message}: {error}"
        else:
            error_data = structured_data
        
        self.event_emitter.emit_log_event(
            message, "ERROR", component, error_data, traceback.format_exc()
        )
    
    # ===== PHASE MANAGEMENT METHODS =====
    
    def emit_phase_start(self, phase_name: str, phase_description: str = None, 
                        estimated_duration: int = None, component: str = None):
        """Emit phase start event with comprehensive metadata."""
        component = component or self._get_caller_component()
        start_time = datetime.utcnow().isoformat()
        
        # Track phase for timing
        self._active_phases[phase_name] = {
            "start_time": start_time,
            "component": component,
            "description": phase_description
        }
        self._phase_start_times[phase_name] = datetime.utcnow()
        
        self.event_emitter.emit_phase_event(
            "phase_start", phase_name, phase_description, 
            estimated_duration, start_time
        )
        
        # Also log the phase start
        self.log_structured(
            f"Phase started: {phase_name}",
            "INFO", component,
            {
                "phase_name": phase_name,
                "phase_description": phase_description,
                "estimated_duration": estimated_duration
            }
        )
    
    def emit_phase_complete(self, phase_name: str, result: Any = None, 
                           component: str = None, structured_data: Dict[str, Any] = None):
        """Emit phase completion event with timing and results."""
        component = component or self._get_caller_component()
        end_time = datetime.utcnow().isoformat()
        
        # Calculate duration if we tracked the start
        duration = None
        if phase_name in self._phase_start_times:
            duration = (datetime.utcnow() - self._phase_start_times[phase_name]).total_seconds()
            del self._phase_start_times[phase_name]
        
        if phase_name in self._active_phases:
            start_time = self._active_phases[phase_name]["start_time"]
            del self._active_phases[phase_name]
        else:
            start_time = None
        
        self.event_emitter.emit_phase_event(
            "phase_complete", phase_name, 
            start_time=start_time, end_time=end_time, result=result
        )
        
        # Enhanced completion message with counts
        completion_message = f"Phase completed: {phase_name}"
        if duration:
            completion_message += f" ({duration:.2f}s)"
        
        # Add completion counts to the message if available in result
        if result and isinstance(result, dict):
            if 'processed_count' in result and 'total_count' in result:
                processed = result['processed_count']
                total = result['total_count']
                if processed == 0 and total == 0:
                    completion_message += " - No items needed processing"
                else:
                    completion_message += f" - {processed} of {total} items processed"
            elif 'skipped_count' in result:
                completion_message += f" - {result['skipped_count']} items skipped"
        
        # Also log the phase completion
        log_data = {
            "phase_name": phase_name,
            "duration_seconds": duration,
            **(structured_data or {})
        }
        if result is not None:
            log_data["result"] = result
        
        self.log_structured(completion_message, "INFO", component, log_data)
        
        # Emit a legacy phase update for backward compatibility with completion status
        if result and isinstance(result, dict):
            self.emit_phase_update(
                phase_name, 
                "completed", 
                completion_message,
                100  # 100% progress for completed phases
            )
    
    def emit_phase_error(self, phase_name: str, error: Union[str, Exception], 
                        component: str = None, structured_data: Dict[str, Any] = None):
        """Emit phase error event with comprehensive error context."""
        component = component or self._get_caller_component()
        end_time = datetime.utcnow().isoformat()
        
        # Calculate duration if we tracked the start
        duration = None
        if phase_name in self._phase_start_times:
            duration = (datetime.utcnow() - self._phase_start_times[phase_name]).total_seconds()
            del self._phase_start_times[phase_name]
        
        if phase_name in self._active_phases:
            start_time = self._active_phases[phase_name]["start_time"]
            del self._active_phases[phase_name]
        else:
            start_time = None
        
        error_str = str(error)
        traceback_info = traceback.format_exc() if isinstance(error, Exception) else None
        
        self.event_emitter.emit_phase_event(
            "phase_error", phase_name,
            start_time=start_time, end_time=end_time, 
            error=error_str, traceback_info=traceback_info
        )
        
        # Also log the phase error
        log_data = {
            "phase_name": phase_name,
            "error": error_str,
            "duration_seconds": duration,
            **(structured_data or {})
        }
        
        self.log_structured(
            f"Phase failed: {phase_name} - {error_str}",
            "ERROR", component, log_data, include_traceback=True
        )
    
    # ===== PROGRESS TRACKING METHODS =====
    
    def emit_progress_update(self, current: int, total: int, operation: str = None,
                           component: str = None, eta: str = None):
        """Emit progress update with comprehensive metrics and ETA calculation."""
        component = component or self._get_caller_component()
        
        self.event_emitter.emit_progress_event(current, total, operation, eta=eta)
        
        # Also update the legacy progress system for compatibility
        percentage = round((current / total) * 100, 2) if total > 0 else 0
        self.update_progress(
            int(percentage), 
            operation or "processing", 
            f"{operation or 'Processing'}: {current}/{total} ({percentage}%)"
        )
    
    def emit_status_update(self, status: str, phase: str = None, message: str = None,
                          details: Dict[str, Any] = None, component: str = None):
        """Emit comprehensive status update with context."""
        component = component or self._get_caller_component()
        
        self.event_emitter.emit_status_event(status, details, phase, message)
        
        # Also log the status update
        self.log_structured(
            f"Status update: {status}" + (f" - {message}" if message else ""),
            "INFO", component,
            {
                "status": status,
                "phase": phase,
                "message": message,
                **(details or {})
            }
        )
    
    # ===== BACKWARD COMPATIBILITY METHODS =====
    
    def log(self, message: str, level: str = "INFO", **extra_data):
        """Backward compatible log method - enhanced with automatic component detection."""
        component = extra_data.pop('component', None) or self._get_caller_component()
        structured_data = {k: v for k, v in extra_data.items() if k not in ['component']}
        
        self.log_structured(message, level, component, structured_data)
    
    def update_progress(self, progress: int, phase_id: str, message: str, status: str = "running"):
        """Backward compatible progress update method."""
        try:
            self._ensure_loop()
            if self._loop.is_running():
                future = asyncio.run_coroutine_threadsafe(
                    self.progress_manager.update_progress(self.task_id, progress, phase_id, message, status),
                    self._loop
                )
                try:
                    future.result(timeout=0.1)
                except:
                    pass
            else:
                self._loop.run_until_complete(
                    self.progress_manager.update_progress(self.task_id, progress, phase_id, message, status)
                )
        except Exception as e:
            # Use print instead of logging.error to avoid circular logging issues
            print(f"[UNIFIED_LOGGER_ERROR] Failed to update progress: {e}", file=sys.stderr)
    
    def emit_phase_update(self, phase_id: str, status: str, message: str, progress: int = 0):
        """Backward compatible phase update method - enhanced with comprehensive events."""
        try:
            self._ensure_loop()
            if self._loop.is_running():
                future = asyncio.run_coroutine_threadsafe(
                    self.progress_manager.publish_phase_update(self.task_id, phase_id, status, message, progress),
                    self._loop
                )
                try:
                    future.result(timeout=0.1)
                except:
                    pass
            else:
                self._loop.run_until_complete(
                    self.progress_manager.publish_phase_update(self.task_id, phase_id, status, message, progress)
                )
        except Exception as e:
            # Use print instead of logging.error to avoid circular logging issues
            print(f"[UNIFIED_LOGGER_ERROR] Failed to emit phase update: {e}", file=sys.stderr)
    
    def emit_agent_status(self, status_data: Dict[str, Any]):
        """Backward compatible agent status method."""
        try:
            status_data['task_id'] = self.task_id
            self._ensure_loop()
            if self._loop.is_running():
                future = asyncio.run_coroutine_threadsafe(
                    self.progress_manager.publish_agent_status_update(status_data),
                    self._loop
                )
                try:
                    future.result(timeout=0.1)
                except:
                    pass
            else:
                self._loop.run_until_complete(
                    self.progress_manager.publish_agent_status_update(status_data)
                )
        except Exception as e:
            # Use print instead of logging.error to avoid circular logging issues
            print(f"[UNIFIED_LOGGER_ERROR] Failed to emit agent status: {e}", file=sys.stderr)
    
    def _ensure_loop(self):
        """Ensure we have an event loop for async operations."""
        try:
            self._loop = asyncio.get_event_loop()
        except RuntimeError:
            self._loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self._loop)



# Maintain backward compatibility with existing UnifiedLogger
UnifiedLogger = EnhancedUnifiedLogger

# Global registry for task loggers
_task_loggers: Dict[str, EnhancedUnifiedLogger] = {}


def get_unified_logger(task_id: str, config: Optional[Config] = None) -> EnhancedUnifiedLogger:
    """Get or create an enhanced unified logger for a task."""
    if task_id not in _task_loggers:
        _task_loggers[task_id] = EnhancedUnifiedLogger(task_id, config)
    return _task_loggers[task_id]


def cleanup_task_logger(task_id: str):
    """Clean up logger for completed task."""
    if task_id in _task_loggers:
        del _task_loggers[task_id]