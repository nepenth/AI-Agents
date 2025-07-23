"""
PostgreSQL-based Logging System for Knowledge Base Agent

This module provides a comprehensive PostgreSQL-based logging system that replaces
the Redis-based approach for better persistence, historical access, and scalability.

Features:
- Persistent log storage in PostgreSQL
- Structured logging with metadata and progress tracking
- Historical log access for completed tasks
- Real-time log streaming for active tasks
- Efficient querying and filtering
"""

import logging
import json
import traceback
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List, Union
from flask import current_app
from .models import db, TaskLog, CeleryTaskState
from .config import Config


class PostgreSQLLogger:
    """
    PostgreSQL-based logger that stores all agent execution logs in the database.
    Provides structured logging with metadata, progress tracking, and efficient querying.
    """
    
    def __init__(self, task_id: str, config: Optional[Config] = None):
        self.task_id = task_id
        self.config = config
        self.sequence_counter = 0
        self._ensure_task_exists()
    
    def _ensure_task_exists(self):
        """Ensure the task exists in CeleryTaskState table."""
        try:
            task = CeleryTaskState.query.filter_by(task_id=self.task_id).first()
            if not task:
                # Create a basic task record if it doesn't exist
                task = CeleryTaskState(
                    task_id=self.task_id,
                    task_type='agent_execution',
                    status='PROGRESS'
                )
                db.session.add(task)
                db.session.commit()
        except Exception as e:
            logging.error(f"Failed to ensure task exists: {e}")
    
    def _get_next_sequence_number(self) -> int:
        """Get the next sequence number for this task."""
        self.sequence_counter += 1
        return self.sequence_counter
    
    def log(self, message: str, level: str = "INFO", component: Optional[str] = None, 
            phase: Optional[str] = None, metadata: Optional[Dict[str, Any]] = None,
            progress_data: Optional[Dict[str, Any]] = None, error_data: Optional[Dict[str, Any]] = None):
        """
        Log a message to PostgreSQL with structured data.
        
        Args:
            message: The log message
            level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
            component: Component that generated the log (e.g., 'content_processor')
            phase: Current processing phase (e.g., 'tweet_caching')
            metadata: Additional structured metadata
            progress_data: Progress information (counts, percentages, etc.)
            error_data: Error context and traceback information
        """
        try:
            log_entry = TaskLog(
                task_id=self.task_id,
                timestamp=datetime.now(timezone.utc),
                level=level.upper(),
                message=message,
                component=component,
                phase=phase,
                sequence_number=self._get_next_sequence_number(),
                log_metadata=json.dumps(metadata) if metadata else None,
                progress_data=json.dumps(progress_data) if progress_data else None,
                error_data=json.dumps(error_data) if error_data else None
            )
            
            db.session.add(log_entry)
            db.session.commit()
            
            # Also log to Python logging system for immediate visibility
            python_logger = logging.getLogger(component or 'postgresql_logger')
            log_level = getattr(logging, level.upper(), logging.INFO)
            python_logger.log(log_level, f"[{self.task_id}] {message}")
            
        except Exception as e:
            # Fallback to Python logging if database logging fails
            # Don't print to stderr as it clutters the logs - just use Python logging
            python_logger = logging.getLogger(component or 'postgresql_logger')
            log_level = getattr(logging, level.upper(), logging.INFO)
            python_logger.log(log_level, f"[{self.task_id}] {message}")
            
            # Log the PostgreSQL error at debug level to avoid spam
            logging.debug(f"PostgreSQL logging failed: {e}")
            logging.debug(f"Original message: [{level}] {message}")
    
    def log_phase_start(self, phase: str, message: str, total_items: Optional[int] = None):
        """Log the start of a processing phase."""
        progress_data = {'total_items': total_items} if total_items else None
        self.log(
            message=message,
            level="INFO",
            phase=phase,
            progress_data=progress_data,
            metadata={'event_type': 'phase_start'}
        )
    
    def log_phase_progress(self, phase: str, message: str, processed_count: int, 
                          total_count: int, error_count: int = 0):
        """Log progress during a processing phase."""
        progress_data = {
            'processed_count': processed_count,
            'total_count': total_count,
            'error_count': error_count,
            'progress_percentage': round((processed_count / total_count) * 100, 1) if total_count > 0 else 0
        }
        
        self.log(
            message=message,
            level="INFO",
            phase=phase,
            progress_data=progress_data,
            metadata={'event_type': 'phase_progress'}
        )
    
    def log_phase_complete(self, phase: str, message: str, processed_count: int, 
                          total_count: int, error_count: int = 0, duration_seconds: Optional[float] = None):
        """Log the completion of a processing phase."""
        progress_data = {
            'processed_count': processed_count,
            'total_count': total_count,
            'error_count': error_count,
            'success_rate': round((processed_count / total_count) * 100, 1) if total_count > 0 else 100
        }
        
        metadata = {'event_type': 'phase_complete'}
        if duration_seconds:
            metadata['duration_seconds'] = duration_seconds
            metadata['items_per_second'] = round(processed_count / duration_seconds, 2) if duration_seconds > 0 else 0
        
        self.log(
            message=message,
            level="INFO",
            phase=phase,
            progress_data=progress_data,
            metadata=metadata
        )
    
    def log_error(self, message: str, error: Exception, component: Optional[str] = None, 
                  phase: Optional[str] = None, context: Optional[Dict[str, Any]] = None):
        """Log an error with full context and traceback."""
        error_data = {
            'error_type': type(error).__name__,
            'error_message': str(error),
            'traceback': traceback.format_exc(),
            'context': context or {}
        }
        
        self.log(
            message=message,
            level="ERROR",
            component=component,
            phase=phase,
            error_data=error_data,
            metadata={'event_type': 'error'}
        )


class LogQueryService:
    """
    Service for querying and retrieving logs from PostgreSQL.
    Provides efficient filtering, pagination, and formatting for API responses.
    """
    
    @staticmethod
    def get_task_logs(task_id: str, level_filter: Optional[str] = None, 
                     component_filter: Optional[str] = None, phase_filter: Optional[str] = None,
                     limit: int = 1000, offset: int = 0) -> List[Dict[str, Any]]:
        """
        Get logs for a specific task with optional filtering.
        
        Args:
            task_id: The task ID to get logs for
            level_filter: Filter by log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
            component_filter: Filter by component name
            phase_filter: Filter by phase name
            limit: Maximum number of logs to return
            offset: Number of logs to skip (for pagination)
            
        Returns:
            List of log dictionaries
        """
        try:
            query = TaskLog.query.filter_by(task_id=task_id)
            
            # Apply filters
            if level_filter:
                query = query.filter(TaskLog.level == level_filter.upper())
            if component_filter:
                query = query.filter(TaskLog.component == component_filter)
            if phase_filter:
                query = query.filter(TaskLog.phase == phase_filter)
            
            # Order by sequence number for chronological order
            query = query.order_by(TaskLog.sequence_number)
            
            # Apply pagination
            logs = query.offset(offset).limit(limit).all()
            
            return [log.to_dict() for log in logs]
            
        except Exception as e:
            logging.error(f"Failed to query task logs: {e}")
            return []
    
    @staticmethod
    def get_recent_logs(task_id: str, since_sequence: int = 0, limit: int = 100) -> List[Dict[str, Any]]:
        """
        Get recent logs since a specific sequence number (for real-time updates).
        
        Args:
            task_id: The task ID to get logs for
            since_sequence: Get logs after this sequence number
            limit: Maximum number of logs to return
            
        Returns:
            List of log dictionaries
        """
        try:
            logs = TaskLog.query.filter(
                TaskLog.task_id == task_id,
                TaskLog.sequence_number > since_sequence
            ).order_by(TaskLog.sequence_number).limit(limit).all()
            
            return [log.to_dict() for log in logs]
            
        except Exception as e:
            logging.error(f"Failed to query recent logs: {e}")
            return []
    
    @staticmethod
    def get_log_summary(task_id: str) -> Dict[str, Any]:
        """
        Get a summary of logs for a task (counts by level, phases, etc.).
        
        Args:
            task_id: The task ID to get summary for
            
        Returns:
            Dictionary with log summary statistics
        """
        try:
            # Get total count
            total_count = TaskLog.query.filter_by(task_id=task_id).count()
            
            # Get counts by level
            level_counts = {}
            for level in ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']:
                count = TaskLog.query.filter_by(task_id=task_id, level=level).count()
                if count > 0:
                    level_counts[level] = count
            
            # Get unique phases
            phases = db.session.query(TaskLog.phase).filter(
                TaskLog.task_id == task_id,
                TaskLog.phase.isnot(None)
            ).distinct().all()
            phase_list = [phase[0] for phase in phases]
            
            # Get unique components
            components = db.session.query(TaskLog.component).filter(
                TaskLog.task_id == task_id,
                TaskLog.component.isnot(None)
            ).distinct().all()
            component_list = [component[0] for component in components]
            
            # Get time range
            first_log = TaskLog.query.filter_by(task_id=task_id).order_by(TaskLog.sequence_number).first()
            last_log = TaskLog.query.filter_by(task_id=task_id).order_by(TaskLog.sequence_number.desc()).first()
            
            return {
                'task_id': task_id,
                'total_count': total_count,
                'level_counts': level_counts,
                'phases': phase_list,
                'components': component_list,
                'start_time': first_log.timestamp.isoformat() if first_log else None,
                'end_time': last_log.timestamp.isoformat() if last_log else None,
                'latest_sequence': last_log.sequence_number if last_log else 0
            }
            
        except Exception as e:
            logging.error(f"Failed to get log summary: {e}")
            return {
                'task_id': task_id,
                'total_count': 0,
                'level_counts': {},
                'phases': [],
                'components': [],
                'start_time': None,
                'end_time': None,
                'latest_sequence': 0
            }


def get_postgresql_logger(task_id: str, config: Optional[Config] = None) -> PostgreSQLLogger:
    """
    Factory function to get a PostgreSQL logger instance.
    
    Args:
        task_id: The task ID to associate logs with
        config: Optional configuration object
        
    Returns:
        PostgreSQLLogger instance
    """
    return PostgreSQLLogger(task_id, config)


# Compatibility function for existing unified_logging usage
def get_unified_logger(task_id: str, config: Optional[Config] = None) -> PostgreSQLLogger:
    """
    Compatibility function that returns a PostgreSQL logger.
    This allows existing code to work without changes.
    """
    return get_postgresql_logger(task_id, config)