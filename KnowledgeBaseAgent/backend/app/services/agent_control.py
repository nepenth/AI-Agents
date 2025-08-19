"""
Agent control service for managing and monitoring AI agent tasks.
"""

import asyncio
import logging
import uuid
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from enum import Enum

from app.tasks.celery_app import celery_app
from app.services.content_processing_pipeline import get_content_processing_pipeline
from app.services.seven_phase_pipeline import get_seven_phase_pipeline
from app.tasks.synthesis_tasks import generate_synthesis_document
from app.tasks.monitoring import system_health_check
from app.websocket.pubsub import get_notification_service
from app.repositories.tasks import get_task_repository
from app.database.connection import get_db_session
from app.services.log_service import log_with_context, log_task_status, log_pipeline_progress

logger = logging.getLogger(__name__)


class AgentTaskType(str, Enum):
    """Types of agent tasks."""
    CONTENT_FETCHING = "content_fetching"
    CONTENT_PROCESSING = "content_processing"
    SYNTHESIS_GENERATION = "synthesis_generation"
    SYSTEM_MONITORING = "system_monitoring"
    PIPELINE_EXECUTION = "pipeline_execution"


class AgentTaskStatus(str, Enum):
    """Status of agent tasks."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    RETRYING = "retrying"


@dataclass
class AgentTaskConfig:
    """Configuration for agent tasks."""
    task_type: AgentTaskType
    parameters: Dict[str, Any]
    priority: int = 5  # 1-10, higher is more priority
    timeout: Optional[int] = None  # seconds
    retry_count: int = 3
    schedule: Optional[str] = None  # cron-like schedule


@dataclass
class AgentTaskInfo:
    """Information about an agent task."""
    task_id: str
    task_type: AgentTaskType
    status: AgentTaskStatus
    config: AgentTaskConfig
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    progress: Optional[Dict[str, Any]] = None
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    celery_task_id: Optional[str] = None


class AgentControlService:
    """Service for controlling and monitoring AI agent operations."""
    
    def __init__(self):
        self.active_tasks: Dict[str, AgentTaskInfo] = {}
        self.task_history: List[AgentTaskInfo] = []
        self.max_history_size = 1000
        self.notification_service = get_notification_service()
    
    async def start_task(self, config: AgentTaskConfig) -> str:
        """
        Start a new agent task.
        
        Args:
            config: Task configuration
            
        Returns:
            Task ID
        """
        try:
            task_id = str(uuid.uuid4())
            
            # Create task info
            task_info = AgentTaskInfo(
                task_id=task_id,
                task_type=config.task_type,
                status=AgentTaskStatus.PENDING,
                config=config,
                created_at=datetime.utcnow()
            )
            
            # Store task
            self.active_tasks[task_id] = task_info
            
            # Start the appropriate Celery task
            celery_task = await self._start_celery_task(config)
            task_info.celery_task_id = celery_task.id
            task_info.status = AgentTaskStatus.RUNNING
            task_info.started_at = datetime.utcnow()
            
            # Send notification
            await self.notification_service.send_notification(
                f"Started {config.task_type.value} task",
                level="info"
            )
            
            # Log task start with context
            log_task_status(
                task_id=task_id,
                status="STARTED",
                message=f"Started {config.task_type.value} task",
                task_type=config.task_type.value,
                parameters=config.parameters
            )
            
            logger.info(f"Started agent task {task_id} of type {config.task_type}")
            
            return task_id
            
        except Exception as e:
            logger.error(f"Failed to start agent task: {e}")
            if task_id in self.active_tasks:
                self.active_tasks[task_id].status = AgentTaskStatus.FAILED
                self.active_tasks[task_id].error = str(e)
            raise
    
    async def stop_task(self, task_id: str) -> bool:
        """
        Stop a running agent task.
        
        Args:
            task_id: Task ID to stop
            
        Returns:
            True if task was stopped successfully
        """
        try:
            if task_id not in self.active_tasks:
                return False
            
            task_info = self.active_tasks[task_id]
            
            if task_info.status not in [AgentTaskStatus.RUNNING, AgentTaskStatus.PENDING]:
                return False
            
            # Revoke Celery task
            if task_info.celery_task_id:
                celery_app.control.revoke(task_info.celery_task_id, terminate=True)
            
            # Update task status
            task_info.status = AgentTaskStatus.CANCELLED
            task_info.completed_at = datetime.utcnow()
            
            # Move to history
            self._move_to_history(task_id)
            
            # Send notification
            await self.notification_service.send_notification(
                f"Stopped {task_info.task_type.value} task",
                level="warning"
            )
            
            # Log task stop
            log_task_status(
                task_id=task_id,
                status="STOPPED",
                message=f"Stopped {task_info.task_type.value} task",
                task_type=task_info.task_type.value
            )
            
            logger.info(f"Stopped agent task {task_id}")
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to stop agent task {task_id}: {e}")
            return False
    
    async def get_task_status(self, task_id: str) -> Optional[AgentTaskInfo]:
        """Get status of a specific task."""
        if task_id in self.active_tasks:
            return self.active_tasks[task_id]
        
        # Check history
        for task in self.task_history:
            if task.task_id == task_id:
                return task
        
        return None
    
    async def list_active_tasks(self) -> List[AgentTaskInfo]:
        """List all active tasks."""
        return list(self.active_tasks.values())
    
    async def list_task_history(
        self,
        limit: int = 50,
        task_type: Optional[AgentTaskType] = None,
        status: Optional[AgentTaskStatus] = None
    ) -> List[AgentTaskInfo]:
        """List task history with optional filtering."""
        history = self.task_history.copy()
        
        # Filter by task type
        if task_type:
            history = [t for t in history if t.task_type == task_type]
        
        # Filter by status
        if status:
            history = [t for t in history if t.status == status]
        
        # Sort by creation time (newest first)
        history.sort(key=lambda x: x.created_at, reverse=True)
        
        return history[:limit]
    
    async def get_system_metrics(self) -> Dict[str, Any]:
        """Get comprehensive system metrics."""
        try:
            # Get Celery worker stats
            inspect = celery_app.control.inspect()
            worker_stats = inspect.stats() or {}
            active_tasks = inspect.active() or {}
            
            # Calculate metrics
            total_workers = len(worker_stats)
            total_active_celery_tasks = sum(len(tasks) for tasks in active_tasks.values())
            
            # Get agent task metrics
            active_agent_tasks = len(self.active_tasks)
            completed_tasks_24h = len([
                t for t in self.task_history
                if t.completed_at and t.completed_at > datetime.utcnow() - timedelta(hours=24)
            ])
            
            # System resource metrics (would integrate with monitoring tools)
            system_metrics = {
                "cpu_usage_percent": 45.2,  # Mock data
                "memory_usage_percent": 67.8,
                "disk_usage_percent": 34.5,
                "network_io_mbps": 12.3
            }
            
            return {
                "timestamp": datetime.utcnow().isoformat(),
                "celery": {
                    "total_workers": total_workers,
                    "active_tasks": total_active_celery_tasks,
                    "worker_stats": worker_stats
                },
                "agent": {
                    "active_tasks": active_agent_tasks,
                    "completed_tasks_24h": completed_tasks_24h,
                    "task_history_size": len(self.task_history)
                },
                "system": system_metrics
            }
            
        except Exception as e:
            logger.error(f"Failed to get system metrics: {e}")
            return {"error": str(e), "timestamp": datetime.utcnow().isoformat()}
    
    async def schedule_task(self, config: AgentTaskConfig, schedule: str) -> str:
        """
        Schedule a task to run on a cron-like schedule.
        
        Args:
            config: Task configuration
            schedule: Cron-like schedule string
            
        Returns:
            Schedule ID
        """
        try:
            # This would integrate with a scheduler like Celery Beat
            # For now, we'll store the schedule and return a mock ID
            
            config.schedule = schedule
            schedule_id = str(uuid.uuid4())
            
            logger.info(f"Scheduled task {config.task_type} with schedule {schedule}")
            
            return schedule_id
            
        except Exception as e:
            logger.error(f"Failed to schedule task: {e}")
            raise
    
    async def update_task_progress(self, task_id: str, progress: Dict[str, Any]):
        """Update task progress."""
        if task_id in self.active_tasks:
            self.active_tasks[task_id].progress = progress
            
            # Send WebSocket notification
            await self.notification_service.notify_task_progress(task_id, progress)
    
    async def complete_task(self, task_id: str, result: Dict[str, Any]):
        """Mark task as completed."""
        if task_id in self.active_tasks:
            task_info = self.active_tasks[task_id]
            task_info.status = AgentTaskStatus.COMPLETED
            task_info.completed_at = datetime.utcnow()
            task_info.result = result
            
            # Move to history
            self._move_to_history(task_id)
            
            # Send notifications
            await self.notification_service.notify_task_completion(task_id, result)
            await self.notification_service.send_notification(
                f"Completed {task_info.task_type.value} task",
                level="success"
            )
    
    async def fail_task(self, task_id: str, error: str):
        """Mark task as failed."""
        if task_id in self.active_tasks:
            task_info = self.active_tasks[task_id]
            task_info.status = AgentTaskStatus.FAILED
            task_info.completed_at = datetime.utcnow()
            task_info.error = error
            
            # Move to history
            self._move_to_history(task_id)
            
            # Send notifications
            await self.notification_service.notify_task_failure(task_id, {"error": error})
            await self.notification_service.send_notification(
                f"Failed {task_info.task_type.value} task: {error}",
                level="error"
            )
    
    async def _start_celery_task(self, config: AgentTaskConfig):
        """Start the appropriate Celery task based on configuration."""
        if config.task_type == AgentTaskType.CONTENT_FETCHING:
            return fetch_content_from_sources.apply_async(
                args=[config.parameters.get("sources", [])],
                priority=config.priority
            )
        
        elif config.task_type == AgentTaskType.CONTENT_PROCESSING:
            return complete_content_processing.apply_async(
                args=[config.parameters.get("content_id")],
                priority=config.priority
            )
        
        elif config.task_type == AgentTaskType.SYNTHESIS_GENERATION:
            return generate_synthesis_document.apply_async(
                args=[
                    config.parameters.get("main_category"),
                    config.parameters.get("sub_category")
                ],
                priority=config.priority
            )
        
        elif config.task_type == AgentTaskType.SYSTEM_MONITORING:
            return system_health_check.apply_async(priority=config.priority)
        
        elif config.task_type == AgentTaskType.PIPELINE_EXECUTION:
            # This would be a complex pipeline task
            return fetch_content_from_sources.apply_async(
                args=[config.parameters.get("sources", [])],
                priority=config.priority
            )
        
        else:
            raise ValueError(f"Unknown task type: {config.task_type}")
    
    def _move_to_history(self, task_id: str):
        """Move task from active to history."""
        if task_id in self.active_tasks:
            task_info = self.active_tasks.pop(task_id)
            self.task_history.append(task_info)
            
            # Limit history size
            if len(self.task_history) > self.max_history_size:
                self.task_history = self.task_history[-self.max_history_size:]
    
    async def cleanup_old_tasks(self, days_old: int = 7):
        """Clean up old task history."""
        cutoff_date = datetime.utcnow() - timedelta(days=days_old)
        
        original_count = len(self.task_history)
        self.task_history = [
            task for task in self.task_history
            if task.created_at > cutoff_date
        ]
        
        cleaned_count = original_count - len(self.task_history)
        
        if cleaned_count > 0:
            logger.info(f"Cleaned up {cleaned_count} old task records")
            
            await self.notification_service.send_notification(
                f"Cleaned up {cleaned_count} old task records",
                level="info"
            )
        
        return cleaned_count
    
    async def get_task_statistics(self) -> Dict[str, Any]:
        """Get task execution statistics."""
        try:
            # Calculate statistics from history
            total_tasks = len(self.task_history)
            
            if total_tasks == 0:
                return {
                    "total_tasks": 0,
                    "success_rate": 0.0,
                    "average_duration": 0.0,
                    "task_type_distribution": {},
                    "status_distribution": {}
                }
            
            # Success rate
            completed_tasks = [t for t in self.task_history if t.status == AgentTaskStatus.COMPLETED]
            success_rate = len(completed_tasks) / total_tasks
            
            # Average duration
            durations = []
            for task in self.task_history:
                if task.started_at and task.completed_at:
                    duration = (task.completed_at - task.started_at).total_seconds()
                    durations.append(duration)
            
            average_duration = sum(durations) / len(durations) if durations else 0.0
            
            # Task type distribution
            task_type_counts = {}
            for task in self.task_history:
                task_type = task.task_type.value
                task_type_counts[task_type] = task_type_counts.get(task_type, 0) + 1
            
            # Status distribution
            status_counts = {}
            for task in self.task_history:
                status = task.status.value
                status_counts[status] = status_counts.get(status, 0) + 1
            
            return {
                "total_tasks": total_tasks,
                "success_rate": round(success_rate, 3),
                "average_duration_seconds": round(average_duration, 2),
                "task_type_distribution": task_type_counts,
                "status_distribution": status_counts,
                "active_tasks": len(self.active_tasks)
            }
            
        except Exception as e:
            logger.error(f"Failed to get task statistics: {e}")
            return {"error": str(e)}


# Global service instance
_agent_control_service: Optional[AgentControlService] = None


def get_agent_control_service() -> AgentControlService:
    """Get the global agent control service instance."""
    global _agent_control_service
    if _agent_control_service is None:
        _agent_control_service = AgentControlService()
    return _agent_control_service