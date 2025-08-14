"""Agent control API endpoints."""

from fastapi import APIRouter, HTTPException, Query
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field
from datetime import datetime

from app.services.agent_control import (
    get_agent_control_service, 
    AgentTaskConfig, 
    AgentTaskType, 
    AgentTaskStatus
)

router = APIRouter()


class StartTaskRequest(BaseModel):
    """Request model for starting an agent task."""
    task_type: str = Field(..., description="Type of task to start")
    parameters: Dict[str, Any] = Field(default_factory=dict, description="Task parameters")
    priority: int = Field(default=5, ge=1, le=10, description="Task priority (1-10)")
    timeout: Optional[int] = Field(default=None, description="Task timeout in seconds")
    retry_count: int = Field(default=3, ge=0, description="Number of retries")


class ScheduleTaskRequest(BaseModel):
    """Request model for scheduling a task."""
    task_type: str = Field(..., description="Type of task to schedule")
    parameters: Dict[str, Any] = Field(default_factory=dict, description="Task parameters")
    schedule: str = Field(..., description="Cron-like schedule string")
    priority: int = Field(default=5, ge=1, le=10, description="Task priority")


class UpdateProgressRequest(BaseModel):
    """Request model for updating task progress."""
    progress: Dict[str, Any] = Field(..., description="Progress information")


@router.post("/tasks/start")
async def start_agent_task(request: StartTaskRequest):
    """Start a new agent task."""
    try:
        agent_service = get_agent_control_service()
        
        # Convert string to enum
        try:
            task_type = AgentTaskType(request.task_type)
        except ValueError:
            valid_types = [t.value for t in AgentTaskType]
            raise HTTPException(
                status_code=400, 
                detail=f"Invalid task type: {request.task_type}. Valid types: {valid_types}"
            )
        
        config = AgentTaskConfig(
            task_type=task_type,
            parameters=request.parameters,
            priority=request.priority,
            timeout=request.timeout,
            retry_count=request.retry_count
        )
        
        task_id = await agent_service.start_task(config)
        
        return {
            "task_id": task_id,
            "status": "started",
            "task_type": request.task_type,
            "created_at": datetime.utcnow().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to start task: {str(e)}")


@router.post("/tasks/schedule")
async def schedule_agent_task(request: ScheduleTaskRequest):
    """Schedule a recurring agent task."""
    try:
        agent_service = get_agent_control_service()
        
        # Convert string to enum
        try:
            task_type = AgentTaskType(request.task_type)
        except ValueError:
            valid_types = [t.value for t in AgentTaskType]
            raise HTTPException(
                status_code=400, 
                detail=f"Invalid task type: {request.task_type}. Valid types: {valid_types}"
            )
        
        config = AgentTaskConfig(
            task_type=task_type,
            parameters=request.parameters,
            priority=request.priority,
            schedule=request.schedule
        )
        
        schedule_id = await agent_service.schedule_task(config, request.schedule)
        
        return {
            "schedule_id": schedule_id,
            "task_type": request.task_type,
            "schedule": request.schedule,
            "status": "scheduled"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to schedule task: {str(e)}")


@router.post("/tasks/{task_id}/stop")
async def stop_agent_task(task_id: str):
    """Stop a running agent task."""
    try:
        agent_service = get_agent_control_service()
        success = await agent_service.stop_task(task_id)
        
        if not success:
            raise HTTPException(status_code=404, detail="Task not found or cannot be stopped")
        
        return {
            "task_id": task_id, 
            "status": "stopped",
            "stopped_at": datetime.utcnow().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to stop task: {str(e)}")


@router.put("/tasks/{task_id}/progress")
async def update_task_progress(task_id: str, request: UpdateProgressRequest):
    """Update the progress of a running task."""
    try:
        agent_service = get_agent_control_service()
        await agent_service.update_task_progress(task_id, request.progress)
        
        return {
            "task_id": task_id,
            "progress": request.progress,
            "updated_at": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update task progress: {str(e)}")


@router.get("/tasks/{task_id}/status")
async def get_task_status(task_id: str):
    """Get the status of a specific task."""
    try:
        agent_service = get_agent_control_service()
        task_info = await agent_service.get_task_status(task_id)
        
        if not task_info:
            raise HTTPException(status_code=404, detail="Task not found")
        
        return {
            "task_id": task_info.task_id,
            "task_type": task_info.task_type.value,
            "status": task_info.status.value,
            "created_at": task_info.created_at.isoformat(),
            "started_at": task_info.started_at.isoformat() if task_info.started_at else None,
            "completed_at": task_info.completed_at.isoformat() if task_info.completed_at else None,
            "progress": task_info.progress,
            "result": task_info.result,
            "error": task_info.error,
            "config": {
                "priority": task_info.config.priority,
                "timeout": task_info.config.timeout,
                "retry_count": task_info.config.retry_count
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get task status: {str(e)}")


@router.get("/tasks/active")
async def list_active_tasks():
    """List all active tasks."""
    try:
        agent_service = get_agent_control_service()
        tasks = await agent_service.list_active_tasks()
        
        return {
            "active_tasks": [
                {
                    "task_id": task.task_id,
                    "task_type": task.task_type.value,
                    "status": task.status.value,
                    "created_at": task.created_at.isoformat(),
                    "started_at": task.started_at.isoformat() if task.started_at else None,
                    "progress": task.progress,
                    "priority": task.config.priority
                }
                for task in tasks
            ],
            "total": len(tasks)
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list active tasks: {str(e)}")


@router.get("/tasks/history")
async def get_task_history(
    limit: int = Query(default=50, ge=1, le=500, description="Maximum number of tasks"),
    task_type: Optional[str] = Query(default=None, description="Filter by task type"),
    status: Optional[str] = Query(default=None, description="Filter by status")
):
    """Get task execution history."""
    try:
        agent_service = get_agent_control_service()
        
        # Convert string filters to enums if provided
        task_type_enum = None
        if task_type:
            try:
                task_type_enum = AgentTaskType(task_type)
            except ValueError:
                valid_types = [t.value for t in AgentTaskType]
                raise HTTPException(
                    status_code=400, 
                    detail=f"Invalid task type: {task_type}. Valid types: {valid_types}"
                )
        
        status_enum = None
        if status:
            try:
                status_enum = AgentTaskStatus(status)
            except ValueError:
                valid_statuses = [s.value for s in AgentTaskStatus]
                raise HTTPException(
                    status_code=400, 
                    detail=f"Invalid status: {status}. Valid statuses: {valid_statuses}"
                )
        
        tasks = await agent_service.list_task_history(limit, task_type_enum, status_enum)
        
        return {
            "task_history": [
                {
                    "task_id": task.task_id,
                    "task_type": task.task_type.value,
                    "status": task.status.value,
                    "created_at": task.created_at.isoformat(),
                    "started_at": task.started_at.isoformat() if task.started_at else None,
                    "completed_at": task.completed_at.isoformat() if task.completed_at else None,
                    "duration_seconds": (
                        (task.completed_at - task.started_at).total_seconds()
                        if task.started_at and task.completed_at else None
                    ),
                    "error": task.error,
                    "priority": task.config.priority
                }
                for task in tasks
            ],
            "total": len(tasks),
            "filters": {
                "task_type": task_type,
                "status": status,
                "limit": limit
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get task history: {str(e)}")


@router.get("/tasks/statistics")
async def get_task_statistics():
    """Get task execution statistics."""
    try:
        agent_service = get_agent_control_service()
        stats = await agent_service.get_task_statistics()
        
        return stats
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get task statistics: {str(e)}")


@router.delete("/tasks/history/cleanup")
async def cleanup_old_tasks(
    days_old: int = Query(default=7, ge=1, description="Delete tasks older than this many days")
):
    """Clean up old task history."""
    try:
        agent_service = get_agent_control_service()
        cleaned_count = await agent_service.cleanup_old_tasks(days_old)
        
        return {
            "cleaned_count": cleaned_count,
            "days_old": days_old,
            "cleaned_at": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to cleanup old tasks: {str(e)}")


@router.get("/system/metrics")
async def get_system_metrics():
    """Get comprehensive system metrics."""
    try:
        agent_service = get_agent_control_service()
        metrics = await agent_service.get_system_metrics()
        
        return metrics
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get system metrics: {str(e)}")


@router.get("/system/health")
async def health_check():
    """Comprehensive health check endpoint."""
    try:
        agent_service = get_agent_control_service()
        
        # Get basic metrics for health assessment
        metrics = await agent_service.get_system_metrics()
        active_tasks = await agent_service.list_active_tasks()
        
        # Determine health status
        health_status = "healthy"
        issues = []
        
        # Check for system issues
        if "error" in metrics:
            health_status = "degraded"
            issues.append("Failed to get system metrics")
        
        # Check for too many active tasks (threshold: 50)
        if len(active_tasks) > 50:
            health_status = "degraded"
            issues.append(f"High number of active tasks: {len(active_tasks)}")
        
        # Check Celery workers
        if metrics.get("celery", {}).get("total_workers", 0) == 0:
            health_status = "unhealthy"
            issues.append("No Celery workers available")
        
        return {
            "status": health_status,
            "service": "agent-control",
            "timestamp": datetime.utcnow().isoformat(),
            "active_tasks": len(active_tasks),
            "celery_workers": metrics.get("celery", {}).get("total_workers", 0),
            "issues": issues,
            "uptime_info": {
                "service_started": "2024-01-01T00:00:00Z",  # This would be dynamic
                "checks_passed": len(issues) == 0
            }
        }
        
    except Exception as e:
        return {
            "status": "unhealthy",
            "service": "agent-control",
            "timestamp": datetime.utcnow().isoformat(),
            "error": str(e),
            "issues": ["Health check failed"]
        }


@router.get("/system/status")
async def get_system_status():
    """Get detailed system status information."""
    try:
        agent_service = get_agent_control_service()
        
        # Get comprehensive system information
        metrics = await agent_service.get_system_metrics()
        active_tasks = await agent_service.list_active_tasks()
        stats = await agent_service.get_task_statistics()
        
        return {
            "timestamp": datetime.utcnow().isoformat(),
            "system_metrics": metrics,
            "task_statistics": stats,
            "active_tasks_summary": {
                "total": len(active_tasks),
                "by_type": {},
                "by_status": {}
            },
            "service_info": {
                "name": "AI Agent Control System",
                "version": "1.0.0",
                "environment": "development"  # This would be from config
            }
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get system status: {str(e)}")


@router.get("/tasks/types")
async def get_available_task_types():
    """Get list of available task types."""
    return {
        "task_types": [
            {
                "value": task_type.value,
                "name": task_type.value.replace("_", " ").title(),
                "description": f"Execute {task_type.value.replace('_', ' ')} operations"
            }
            for task_type in AgentTaskType
        ]
    }


@router.get("/tasks/statuses")
async def get_available_task_statuses():
    """Get list of available task statuses."""
    return {
        "task_statuses": [
            {
                "value": status.value,
                "name": status.value.replace("_", " ").title(),
                "description": f"Task is {status.value}"
            }
            for status in AgentTaskStatus
        ]
    }


# Legacy endpoints for backward compatibility
@router.get("/health")
async def agent_health():
    """Check agent service health (legacy endpoint)."""
    return {"status": "healthy", "service": "agent"}


@router.post("/start")
async def start_agent():
    """Start the AI agent processing pipeline (legacy endpoint)."""
    # Redirect to new task-based system
    return {
        "message": "Use /tasks/start endpoint for starting specific tasks",
        "available_types": [t.value for t in AgentTaskType]
    }


@router.get("/status/{task_id}")
async def get_agent_status(task_id: str):
    """Get status of a specific agent task (legacy endpoint)."""
    # Redirect to new endpoint
    return await get_task_status(task_id)


@router.post("/stop/{task_id}")
async def stop_agent(task_id: str):
    """Stop a running agent task (legacy endpoint)."""
    # Redirect to new endpoint
    return await stop_agent_task(task_id)


@router.get("/history")
async def get_agent_history():
    """Get agent execution history (legacy endpoint)."""
    # Redirect to new endpoint with default parameters
    return await get_task_history()