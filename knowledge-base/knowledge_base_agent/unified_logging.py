"""
Unified Logging System for Knowledge Base Agent

This module provides a single, clean interface for all logging and progress updates
that routes everything through Redis/TaskProgressManager, eliminating the hybrid
SocketIO emission patterns.
"""

import logging
import asyncio
from typing import Optional, Dict, Any
from .task_progress import TaskProgressManager, get_progress_manager
from .config import Config


class UnifiedLogger:
    """
    Single interface for all logging and progress updates.
    Routes everything through Redis/TaskProgressManager for consistency.
    """
    
    def __init__(self, task_id: str, config: Optional[Config] = None):
        self.task_id = task_id
        self.config = config or Config()
        self.progress_manager = get_progress_manager(self.config)
        self._loop = None
        
    def _ensure_loop(self):
        """Ensure we have an event loop for async operations."""
        try:
            self._loop = asyncio.get_event_loop()
        except RuntimeError:
            self._loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self._loop)
    
    def log(self, message: str, level: str = "INFO", **extra_data):
        """Log a message through the unified system."""
        try:
            self._ensure_loop()
            if self._loop.is_running():
                # If loop is already running, schedule the coroutine
                asyncio.create_task(
                    self.progress_manager.log_message(self.task_id, message, level, **extra_data)
                )
            else:
                # Run the coroutine in the loop
                self._loop.run_until_complete(
                    self.progress_manager.log_message(self.task_id, message, level, **extra_data)
                )
        except Exception as e:
            # Fallback to standard logging
            logging.error(f"Failed to log via UnifiedLogger: {e}")
            logging.log(getattr(logging, level.upper(), logging.INFO), f"[Task {self.task_id}] {message}")
    
    def update_progress(self, progress: int, phase_id: str, message: str, status: str = "running"):
        """Update task progress through the unified system."""
        try:
            self._ensure_loop()
            if self._loop.is_running():
                asyncio.create_task(
                    self.progress_manager.update_progress(self.task_id, progress, phase_id, message, status)
                )
            else:
                self._loop.run_until_complete(
                    self.progress_manager.update_progress(self.task_id, progress, phase_id, message, status)
                )
        except Exception as e:
            logging.error(f"Failed to update progress via UnifiedLogger: {e}")
    
    def emit_phase_update(self, phase_id: str, status: str, message: str, progress: int = 0):
        """Emit phase update through the unified system."""
        try:
            self._ensure_loop()
            if self._loop.is_running():
                asyncio.create_task(
                    self.progress_manager.publish_phase_update(self.task_id, phase_id, status, message, progress)
                )
            else:
                self._loop.run_until_complete(
                    self.progress_manager.publish_phase_update(self.task_id, phase_id, status, message, progress)
                )
        except Exception as e:
            logging.error(f"Failed to emit phase update via UnifiedLogger: {e}")
    
    def emit_agent_status(self, status_data: Dict[str, Any]):
        """Emit agent status update through the unified system."""
        try:
            status_data['task_id'] = self.task_id
            self._ensure_loop()
            if self._loop.is_running():
                asyncio.create_task(
                    self.progress_manager.publish_agent_status_update(status_data)
                )
            else:
                self._loop.run_until_complete(
                    self.progress_manager.publish_agent_status_update(status_data)
                )
        except Exception as e:
            logging.error(f"Failed to emit agent status via UnifiedLogger: {e}")


# Global registry for task loggers
_task_loggers: Dict[str, UnifiedLogger] = {}


def get_unified_logger(task_id: str, config: Optional[Config] = None) -> UnifiedLogger:
    """Get or create a unified logger for a task."""
    if task_id not in _task_loggers:
        _task_loggers[task_id] = UnifiedLogger(task_id, config)
    return _task_loggers[task_id]


def cleanup_task_logger(task_id: str):
    """Clean up logger for completed task."""
    if task_id in _task_loggers:
        del _task_loggers[task_id]