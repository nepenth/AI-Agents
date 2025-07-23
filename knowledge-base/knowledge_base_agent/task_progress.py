from __future__ import annotations
"""
Task Progress Management for Celery Tasks

This module manages task progress and logging using Redis, providing a replacement
for the current multiprocessing queue-based communication system.
"""

import redis.asyncio as redis
import json
import logging
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List
from .config import Config
import asyncio


class TaskProgressManager:
    """
    Manages task progress and logging using Redis.
    """
    
    # STANDARDIZED REDIS CHANNEL CONSTANTS
    # These ensure consistent channel names between publishers and subscribers
    LOG_CHANNEL = "task_logs"                # For log messages
    PHASE_CHANNEL = "task_phase_updates"     # For phase updates  
    STATUS_CHANNEL = "task_status_updates"   # For status updates
    
    def __init__(self, config: Config):
        """Initialize Redis connections for progress and logging."""
        self.progress_redis = redis.Redis.from_url(config.redis_progress_url, decode_responses=True)
        self.logs_redis = redis.Redis.from_url(config.redis_logs_url, decode_responses=True)
        # Circuit breaker to prevent recursive logging
        self._logging_in_progress = False
        
        # Emergency log buffering when Redis is unavailable
        self._log_buffer = []
        self._max_buffer_size = 1000
        self._redis_available = True
        self._last_redis_check = None
        self._redis_check_interval = 30  # seconds

    async def test_connections(self):
        try:
            await self.progress_redis.ping()
            await self.logs_redis.ping()
            # Connection success logged at debug level only
            logging.debug("TaskProgressManager: Redis connections established")
        except redis.ConnectionError as e:
            logging.error(f"TaskProgressManager: Failed to connect to Redis: {e}")
            raise
    
    async def update_progress(self, task_id: str, progress: int, phase_id: str, message: str, status: str = "running"):
        """
        Update task progress in Redis hash.
        """
        try:
            progress_key = f"progress:{task_id}"
            progress_data = {
                'progress': progress, 'phase_id': phase_id, 'message': message,
                'status': status, 'last_update': datetime.utcnow().isoformat()
            }
            await self.progress_redis.hset(progress_key, mapping=progress_data)
            await self.progress_redis.expire(progress_key, 86400)
            await self.progress_redis.publish(self.PHASE_CHANNEL, json.dumps({
                'type': 'progress_update', 'task_id': task_id, 'data': progress_data
            }))
        except Exception as e:
            logging.error(f"Failed to update progress for task {task_id}: {e}")
    
    async def log_message(self, task_id: str, message: str, level: str = "INFO", **extra_data):
        """
        Add log message to Redis list with enhanced structured data support and emergency buffering.
        """
        # Circuit breaker to prevent recursive logging
        if self._logging_in_progress:
            return
            
        try:
            self._logging_in_progress = True
            
            # Enhanced log entry with structured data support
            log_entry = {
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'level': level,
                'message': message,
                'task_id': task_id,
                **extra_data
            }
            
            # Check Redis availability and handle buffering
            if not await self._check_redis_availability():
                # Redis unavailable - buffer the log entry
                await self._buffer_log_entry(log_entry)
                return
            
            # Try to flush any buffered logs first
            await self._flush_log_buffer()
            
            # Store in Redis list for persistence
            log_key = f"logs:{task_id}"
            await self.logs_redis.lpush(log_key, json.dumps(log_entry))
            await self.logs_redis.ltrim(log_key, 0, 999)
            await self.logs_redis.expire(log_key, 86400)
            
            # Publish to Redis channel for real-time updates
            publish_data = {
                'type': 'log_message', 'task_id': task_id, 'data': log_entry
            }
            await self.logs_redis.publish(self.LOG_CHANNEL, json.dumps(publish_data))
            
        except Exception as e:
            # Redis operation failed - buffer the log entry
            await self._buffer_log_entry(log_entry)
            # Use print instead of logging to avoid potential recursion
            print(f"Failed to log message for task {task_id}, buffered instead: {e}", file=__import__('sys').stderr)
        finally:
            self._logging_in_progress = False
    
    async def get_progress(self, task_id: str) -> Optional[Dict[str, Any]]:
        """
        Get current progress for task.
        """
        try:
            progress_data = await self.progress_redis.hgetall(f"progress:{task_id}")
            if not progress_data:
                return None
            if 'progress' in progress_data:
                progress_data['progress'] = int(progress_data['progress'])
            return progress_data
        except Exception as e:
            logging.error(f"Failed to get progress for task {task_id}: {e}")
            return None
    
    async def get_logs(self, task_id: str, limit: int = 100) -> List[Dict[str, Any]]:
        """
        Get logs for task.
        """
        try:
            log_entries = await self.logs_redis.lrange(f"logs:{task_id}", 0, limit - 1)
            return [json.loads(entry) for entry in log_entries]
        except Exception as e:
            logging.error(f"Failed to get logs for task {task_id}: {e}")
            return []
    
    async def clear_task_data(self, task_id: str):
        """
        Clear all data for a specific task.
        """
        try:
            await self.progress_redis.delete(f"progress:{task_id}")
            await self.logs_redis.delete(f"logs:{task_id}")
            logging.info(f"Cleared data for task {task_id}")
        except Exception as e:
            logging.error(f"Failed to clear data for task {task_id}: {e}")
    
    async def clear_all_data(self):
        """
        Clear all task progress and log data from Redis.
        WARNING: This clears ALL task data.
        """
        try:
            # Clear all progress keys
            progress_keys = await self.progress_redis.keys("progress:*")
            if progress_keys:
                await self.progress_redis.delete(*progress_keys)
            
            # Clear all log keys
            log_keys = await self.logs_redis.keys("logs:*")
            if log_keys:
                await self.logs_redis.delete(*log_keys)
            
            logging.info(f"Cleared all task data from Redis - {len(progress_keys)} progress keys, {len(log_keys)} log keys")
        except Exception as e:
            logging.error(f"Failed to clear all task data from Redis: {e}")
            raise
    
    async def get_all_active_tasks(self) -> List[str]:
        """
        Get list of all active task IDs.
        """
        try:
            keys = await self.progress_redis.keys("progress:*")
            # Keys are already decoded strings when decode_responses=True
            return [key.split(":", 1)[1] for key in keys]
        except Exception as e:
            logging.error(f"Failed to get active tasks: {e}")
            return []
    
    async def publish_phase_update(self, task_id: str, phase_id: str, status: str, message: str, progress: int = 0):
        """
        Publish phase update for real-time UI updates.
        """
        try:
            phase_update = {
                'type': 'phase_update', 'task_id': task_id, 'phase_id': phase_id,
                'status': status, 'message': message, 'progress': progress,
                'timestamp': datetime.utcnow().isoformat()
            }
            await self.progress_redis.publish(self.PHASE_CHANNEL, json.dumps(phase_update))
            await self.update_progress(task_id, progress, phase_id, message, status=status)
        except Exception as e:
            logging.error(f"Failed to publish phase update for task {task_id}: {e}")
    
    async def publish_phase_event(self, task_id: str, event_type: str, phase_data: Dict[str, Any]):
        """
        Publish comprehensive phase events (start, complete, error) for real-time UI updates.
        """
        try:
            phase_event = {
                'type': f'phase_{event_type}',
                'task_id': task_id,
                'data': phase_data,
                'timestamp': datetime.utcnow().isoformat()
            }
            await self.progress_redis.publish(self.PHASE_CHANNEL, json.dumps(phase_event))
        except Exception as e:
            logging.error(f"Failed to publish phase event for task {task_id}: {e}")
    
    async def publish_progress_update(self, task_id: str, progress_data: Dict[str, Any]):
        """
        Publish detailed progress updates with metrics and ETA.
        """
        try:
            progress_event = {
                'type': 'progress_update',
                'task_id': task_id,
                'data': progress_data,
                'timestamp': datetime.utcnow().isoformat()
            }
            await self.progress_redis.publish(self.PHASE_CHANNEL, json.dumps(progress_event))
            
            # Also update the legacy progress system for compatibility
            if 'percentage' in progress_data:
                await self.update_progress(
                    task_id, 
                    int(progress_data['percentage']),
                    progress_data.get('operation', 'processing'),
                    f"{progress_data.get('operation', 'Processing')}: {progress_data.get('current', 0)}/{progress_data.get('total', 0)}"
                )
        except Exception as e:
            logging.error(f"Failed to publish progress update for task {task_id}: {e}")

    async def publish_agent_status_update(self, status_data: Dict[str, Any]):
        """
        Publish agent status update for real-time UI updates.
        """
        try:
            status_update = {
                'type': 'agent_status_update', 'data': status_data,
                'timestamp': datetime.utcnow().isoformat()
            }
            await self.progress_redis.publish(self.STATUS_CHANNEL, json.dumps(status_update))
        except Exception as e:
            logging.error(f"Failed to publish agent status update: {e}")
    
    async def _check_redis_availability(self) -> bool:
        """
        Check if Redis is available with caching to avoid excessive checks.
        
        Returns:
            bool: True if Redis is available
        """
        now = datetime.utcnow()
        
        # Use cached result if recent check was performed
        if (self._last_redis_check and 
            (now - self._last_redis_check).total_seconds() < self._redis_check_interval):
            return self._redis_available
        
        try:
            # Quick ping to both Redis instances
            await self.logs_redis.ping()
            await self.progress_redis.ping()
            
            # If Redis was previously unavailable and is now available, log recovery
            if not self._redis_available:
                print("Redis connection restored", file=__import__('sys').stderr)
            
            self._redis_available = True
            self._last_redis_check = now
            
            return True
            
        except Exception as e:
            self._redis_available = False
            self._last_redis_check = now
            
            # Log Redis unavailability (but avoid recursion)
            print(f"Redis unavailable, buffering logs: {e}", file=__import__('sys').stderr)
            return False
    
    async def _buffer_log_entry(self, log_entry: Dict[str, Any]):
        """
        Buffer a log entry when Redis is unavailable.
        
        Args:
            log_entry: The log entry to buffer
        """
        # Add to buffer
        self._log_buffer.append(log_entry)
        
        # Trim buffer if it exceeds max size (keep most recent entries)
        if len(self._log_buffer) > self._max_buffer_size:
            # Remove oldest entries, keep most recent
            excess = len(self._log_buffer) - self._max_buffer_size
            self._log_buffer = self._log_buffer[excess:]
            
            print(f"Log buffer full, removed {excess} oldest entries", file=__import__('sys').stderr)
    
    async def _flush_log_buffer(self):
        """
        Flush buffered log entries to Redis when connection is restored.
        """
        if not self._log_buffer:
            return
        
        print(f"Flushing {len(self._log_buffer)} buffered log entries to Redis", file=__import__('sys').stderr)
        
        # Process buffered entries
        flushed_count = 0
        failed_count = 0
        
        # Create a copy of the buffer and clear the original to avoid blocking new logs
        buffer_copy = self._log_buffer.copy()
        self._log_buffer.clear()
        
        for log_entry in buffer_copy:
            try:
                task_id = log_entry['task_id']
                
                # Store in Redis list for persistence
                log_key = f"logs:{task_id}"
                await self.logs_redis.lpush(log_key, json.dumps(log_entry))
                await self.logs_redis.ltrim(log_key, 0, 999)
                await self.logs_redis.expire(log_key, 86400)
                
                # Publish to Redis channel for real-time updates
                publish_data = {
                    'type': 'log_message', 'task_id': task_id, 'data': log_entry
                }
                await self.logs_redis.publish(self.LOG_CHANNEL, json.dumps(publish_data))
                
                flushed_count += 1
                
            except Exception as e:
                # If individual entry fails, put it back in buffer
                self._log_buffer.append(log_entry)
                failed_count += 1
                
                # Don't spam error messages for each failed entry
                if failed_count == 1:
                    print(f"Failed to flush some buffered log entries: {e}", file=__import__('sys').stderr)
        
        if flushed_count > 0:
            print(f"Successfully flushed {flushed_count} buffered log entries", file=__import__('sys').stderr)
        
        if failed_count > 0:
            print(f"{failed_count} log entries remain buffered due to errors", file=__import__('sys').stderr)
    
    def get_buffer_stats(self) -> Dict[str, Any]:
        """
        Get statistics about the log buffer.
        
        Returns:
            Dict containing buffer statistics
        """
        return {
            'buffer_size': len(self._log_buffer),
            'max_buffer_size': self._max_buffer_size,
            'redis_available': self._redis_available,
            'last_redis_check': self._last_redis_check.isoformat() if self._last_redis_check else None,
            'redis_check_interval': self._redis_check_interval
        }

    async def close(self):
        """Close Redis connections and flush any remaining buffered logs."""
        try:
            # Try to flush any remaining buffered logs before closing
            if self._log_buffer and self._redis_available:
                await self._flush_log_buffer()
            
            await self.progress_redis.close()
            await self.logs_redis.close()
            logging.info("TaskProgressManager: Redis connections closed")
        except Exception as e:
            logging.error(f"Error closing Redis connections: {e}")

class RedisTaskLogHandler(logging.Handler):
    """
    A logging handler that forwards log records to the TaskProgressManager.
    """
    def __init__(self, task_id: str, progress_manager: TaskProgressManager, loop: asyncio.AbstractEventLoop):
        super().__init__()
        self.task_id = task_id
        self.progress_manager = progress_manager
        self.loop = loop

    def emit(self, record: logging.LogRecord):
        if record.levelno < logging.INFO:
            return
        try:
            if 'task_progress_internal' in record.name:
                return
            message = self.format(record)
            coro = self.progress_manager.log_message(
                self.task_id, message, level=record.levelname
            )
            asyncio.run_coroutine_threadsafe(coro, self.loop)
        except Exception:
            pass

_progress_manager_instance: Optional[TaskProgressManager] = None

def get_progress_manager(config: Optional[Config] = None) -> TaskProgressManager:
    """
    Factory function for TaskProgressManager instance.
    
    This is no longer a singleton to prevent asyncio event loop conflicts
    between different contexts (e.g., Flask app and Celery worker).
    """
    if config is None:
        # This path is generally used by Celery workers or scripts
        logging.debug("TaskProgressManager created without explicit config. Loading from env.")
        config = Config.from_env()
    
    # Always create a new instance to ensure connection pools are tied
    # to the correct event loop.
    return TaskProgressManager(config)