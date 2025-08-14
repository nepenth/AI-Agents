"""
Pydantic schemas for task operations.
"""
from typing import List, Optional, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field

from .common import FilterParams


class TaskBase(BaseModel):
    """Base schema for tasks."""
    task_type: str = Field(description="Type of task")
    task_name: Optional[str] = Field(default=None, description="Human-readable task name")
    config: Optional[Dict[str, Any]] = Field(default=None, description="Task configuration")
    queue_name: Optional[str] = Field(default=None, description="Queue name")
    max_retries: int = Field(default=3, description="Maximum retry attempts")


class TaskCreate(TaskBase):
    """Schema for creating a task."""
    status: str = Field(default="pending", description="Initial task status")


class TaskUpdate(BaseModel):
    """Schema for updating a task."""
    status: Optional[str] = Field(default=None, description="Updated status")
    current_phase: Optional[str] = Field(default=None, description="Current phase")
    progress_percentage: Optional[int] = Field(default=None, description="Progress percentage")
    progress_message: Optional[str] = Field(default=None, description="Progress message")
    result_data: Optional[Dict[str, Any]] = Field(default=None, description="Result data")
    error_message: Optional[str] = Field(default=None, description="Error message")


class TaskResponse(TaskBase):
    """Schema for task responses."""
    id: str = Field(description="Unique task ID")
    status: str = Field(description="Current status")
    current_phase: Optional[str] = Field(default=None, description="Current phase")
    progress_percentage: int = Field(description="Progress percentage")
    progress_message: Optional[str] = Field(default=None, description="Progress message")
    worker_id: Optional[str] = Field(default=None, description="Worker ID")
    result_data: Optional[Dict[str, Any]] = Field(default=None, description="Result data")
    error_message: Optional[str] = Field(default=None, description="Error message")
    error_traceback: Optional[str] = Field(default=None, description="Error traceback")
    execution_time: Optional[float] = Field(default=None, description="Execution time")
    memory_usage: Optional[int] = Field(default=None, description="Memory usage")
    retry_count: int = Field(description="Current retry count")
    created_at: datetime = Field(description="Creation timestamp")
    started_at: Optional[datetime] = Field(default=None, description="Start timestamp")
    completed_at: Optional[datetime] = Field(default=None, description="Completion timestamp")
    updated_at: datetime = Field(description="Last update timestamp")
    
    # Computed properties
    is_running: bool = Field(description="Whether task is running")
    is_completed: bool = Field(description="Whether task is completed")
    is_failed: bool = Field(description="Whether task has failed")
    can_retry: bool = Field(description="Whether task can be retried")
    duration: Optional[float] = Field(default=None, description="Task duration in seconds")
    
    class Config:
        from_attributes = True


class TaskList(BaseModel):
    """Schema for listing tasks."""
    items: List[TaskResponse] = Field(description="List of tasks")
    total: int = Field(description="Total number of tasks")
    status_stats: Dict[str, int] = Field(description="Status statistics")
    type_stats: Dict[str, int] = Field(description="Task type statistics")