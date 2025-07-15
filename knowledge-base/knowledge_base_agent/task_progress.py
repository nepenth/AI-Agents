from __future__ import annotations
"""
Task Progress Management for Celery Tasks

This module manages task progress and logging using Redis, providing a replacement
for the current multiprocessing queue-based communication system.
"""

import redis.asyncio as redis
import json
import logging
from datetime import datetime
from typing import Dict, Any, Optional, List
from .config import Config
import asyncio


class TaskProgressManager:
    """
    Manages task progress and logging using Redis.
    """
    
    def __init__(self, config: Config):
        """Initialize Redis connections for progress and logging."""
        self.progress_redis = redis.Redis.from_url(config.redis_progress_url, decode_responses=True)
        self.logs_redis = redis.Redis.from_url(config.redis_logs_url, decode_responses=True)
        # Circuit breaker to prevent recursive logging
        self._logging_in_progress = False

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
            await self.progress_redis.publish('task_phase_updates', json.dumps({
                'type': 'progress_update', 'task_id': task_id, 'data': progress_data
            }))
        except Exception as e:
            logging.error(f"Failed to update progress for task {task_id}: {e}")
    
    async def log_message(self, task_id: str, message: str, level: str = "INFO", **extra_data):
        """
        Add log message to Redis list.
        """
        # Circuit breaker to prevent recursive logging
        if self._logging_in_progress:
            return
            
        try:
            self._logging_in_progress = True
            
            log_entry = {
                'timestamp': datetime.utcnow().isoformat(), 'level': level,
                'message': message, 'task_id': task_id, **extra_data
            }
            log_key = f"logs:{task_id}"
            await self.logs_redis.lpush(log_key, json.dumps(log_entry))
            await self.logs_redis.ltrim(log_key, 0, 999)
            await self.logs_redis.expire(log_key, 86400)
            
            # Publish to Redis channel for real-time updates
            publish_data = {
                'type': 'log_message', 'task_id': task_id, 'data': log_entry
            }
            await self.logs_redis.publish('task_logs', json.dumps(publish_data))
            
            # Debug logging removed - too verbose for Live Logs
            # Internal logging removed to prevent recursive loop with RedisTaskLogHandler
        except Exception as e:
            # Use print instead of logging to avoid potential recursion
            print(f"Failed to log message for task {task_id}: {e}", file=__import__('sys').stderr)
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
            await self.progress_redis.publish('task_phase_updates', json.dumps(phase_update))
            await self.update_progress(task_id, progress, phase_id, message, status=status)
        except Exception as e:
            logging.error(f"Failed to publish phase update for task {task_id}: {e}")
    
    async def publish_agent_status_update(self, status_data: Dict[str, Any]):
        """
        Publish agent status update for real-time UI updates.
        """
        try:
            status_update = {
                'type': 'agent_status_update', 'data': status_data,
                'timestamp': datetime.utcnow().isoformat()
            }
            await self.progress_redis.publish('task_status_updates', json.dumps(status_update))
        except Exception as e:
            logging.error(f"Failed to publish agent status update: {e}")
    
    async def close(self):
        """Close Redis connections."""
        try:
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