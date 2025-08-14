"""
Celery tasks for system monitoring and maintenance.
"""

import logging
import time
from typing import Dict, Any, List
from celery import current_task
from datetime import datetime, timedelta

from app.tasks.celery_app import celery_app
from app.tasks.base import MonitoringTask, TaskResult
from app.services.ai_service import get_ai_service

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, base=MonitoringTask, name="system_health_check")
def system_health_check(self) -> Dict[str, Any]:
    """
    Perform comprehensive system health check.
    
    Returns:
        Dict containing health check results
    """
    try:
        self.update_progress(0, 5, "Starting system health check...")
        
        health_results = {}
        overall_healthy = True
        
        # Check 1: Database connectivity
        self.update_progress(1, 5, "Checking database connectivity...")
        db_health = _check_database_health()
        health_results["database"] = db_health
        if not db_health["healthy"]:
            overall_healthy = False
        
        # Check 2: Redis connectivity
        self.update_progress(2, 5, "Checking Redis connectivity...")
        redis_health = _check_redis_health()
        health_results["redis"] = redis_health
        if not redis_health["healthy"]:
            overall_healthy = False
        
        # Check 3: AI service health
        self.update_progress(3, 5, "Checking AI service health...")
        ai_health = _check_ai_service_health()
        health_results["ai_service"] = ai_health
        if not ai_health["healthy"]:
            overall_healthy = False
        
        # Check 4: File system health
        self.update_progress(4, 5, "Checking file system health...")
        fs_health = _check_filesystem_health()
        health_results["filesystem"] = fs_health
        if not fs_health["healthy"]:
            overall_healthy = False
        
        # Check 5: Worker status
        self.update_progress(5, 5, "Checking Celery worker status...")
        worker_health = _check_worker_health()
        health_results["workers"] = worker_health
        if not worker_health["healthy"]:
            overall_healthy = False
        
        return TaskResult(
            success=True,
            data={
                "overall_healthy": overall_healthy,
                "timestamp": datetime.utcnow().isoformat(),
                "checks": health_results
            }
        ).to_dict()
        
    except Exception as e:
        logger.error(f"System health check failed: {e}")
        return TaskResult(
            success=False,
            error=str(e),
            error_type=type(e).__name__
        ).to_dict()


def _check_database_health() -> Dict[str, Any]:
    """Check database connectivity and performance."""
    try:
        # This would test database connectivity
        # For now, return a mock result
        return {
            "healthy": True,
            "response_time_ms": 15,
            "connection_pool_size": 10,
            "active_connections": 3
        }
    except Exception as e:
        return {
            "healthy": False,
            "error": str(e)
        }


def _check_redis_health() -> Dict[str, Any]:
    """Check Redis connectivity and performance."""
    try:
        # This would test Redis connectivity
        # For now, return a mock result
        return {
            "healthy": True,
            "response_time_ms": 5,
            "memory_usage_mb": 128,
            "connected_clients": 5
        }
    except Exception as e:
        return {
            "healthy": False,
            "error": str(e)
        }


def _check_ai_service_health() -> Dict[str, Any]:
    """Check AI service health."""
    try:
        # This would check AI service health
        # For now, return a mock result
        return {
            "healthy": True,
            "available_backends": ["ollama", "localai"],
            "total_models": 5,
            "response_time_ms": 250
        }
    except Exception as e:
        return {
            "healthy": False,
            "error": str(e)
        }


def _check_filesystem_health() -> Dict[str, Any]:
    """Check file system health and disk space."""
    try:
        import shutil
        
        # Check disk space
        total, used, free = shutil.disk_usage("/")
        usage_percent = (used / total) * 100
        
        return {
            "healthy": usage_percent < 90,  # Consider unhealthy if >90% full
            "disk_usage_percent": round(usage_percent, 2),
            "free_space_gb": round(free / (1024**3), 2),
            "total_space_gb": round(total / (1024**3), 2)
        }
    except Exception as e:
        return {
            "healthy": False,
            "error": str(e)
        }


def _check_worker_health() -> Dict[str, Any]:
    """Check Celery worker health."""
    try:
        from celery import current_app
        
        # Get worker stats
        inspect = current_app.control.inspect()
        stats = inspect.stats()
        active = inspect.active()
        
        if not stats:
            return {
                "healthy": False,
                "error": "No workers responding"
            }
        
        total_workers = len(stats)
        total_active_tasks = sum(len(tasks) for tasks in (active or {}).values())
        
        return {
            "healthy": total_workers > 0,
            "total_workers": total_workers,
            "active_tasks": total_active_tasks,
            "worker_details": stats
        }
    except Exception as e:
        return {
            "healthy": False,
            "error": str(e)
        }


@celery_app.task(bind=True, base=MonitoringTask, name="cleanup_old_tasks")
def cleanup_old_tasks(self, days_old: int = 7) -> Dict[str, Any]:
    """
    Clean up old task results and logs.
    
    Args:
        days_old: Number of days old for tasks to be considered for cleanup
        
    Returns:
        Dict containing cleanup results
    """
    try:
        self.update_progress(0, 3, "Starting task cleanup...")
        
        cutoff_date = datetime.utcnow() - timedelta(days=days_old)
        
        # Clean up task results
        self.update_progress(1, 3, "Cleaning up old task results...")
        cleaned_results = _cleanup_task_results(cutoff_date)
        
        # Clean up log files
        self.update_progress(2, 3, "Cleaning up old log files...")
        cleaned_logs = _cleanup_log_files(cutoff_date)
        
        # Clean up temporary files
        self.update_progress(3, 3, "Cleaning up temporary files...")
        cleaned_temp = _cleanup_temp_files(cutoff_date)
        
        return TaskResult(
            success=True,
            data={
                "days_old_threshold": days_old,
                "cutoff_date": cutoff_date.isoformat(),
                "cleaned_task_results": cleaned_results,
                "cleaned_log_files": cleaned_logs,
                "cleaned_temp_files": cleaned_temp,
                "total_cleaned": cleaned_results + cleaned_logs + cleaned_temp
            }
        ).to_dict()
        
    except Exception as e:
        logger.error(f"Task cleanup failed: {e}")
        return TaskResult(
            success=False,
            error=str(e),
            error_type=type(e).__name__
        ).to_dict()


def _cleanup_task_results(cutoff_date: datetime) -> int:
    """Clean up old task results."""
    try:
        # This would clean up old task results from the result backend
        # For now, return a mock count
        return 25
    except Exception as e:
        logger.error(f"Failed to cleanup task results: {e}")
        return 0


def _cleanup_log_files(cutoff_date: datetime) -> int:
    """Clean up old log files."""
    try:
        # This would clean up old log files
        # For now, return a mock count
        return 5
    except Exception as e:
        logger.error(f"Failed to cleanup log files: {e}")
        return 0


def _cleanup_temp_files(cutoff_date: datetime) -> int:
    """Clean up old temporary files."""
    try:
        # This would clean up old temporary files
        # For now, return a mock count
        return 15
    except Exception as e:
        logger.error(f"Failed to cleanup temp files: {e}")
        return 0


@celery_app.task(bind=True, base=MonitoringTask, name="generate_system_report")
def generate_system_report(self) -> Dict[str, Any]:
    """
    Generate comprehensive system status report.
    
    Returns:
        Dict containing system report
    """
    try:
        self.update_progress(0, 4, "Generating system report...")
        
        # Get system health
        self.update_progress(1, 4, "Collecting health metrics...")
        health_result = system_health_check.apply_async().get()
        health_data = health_result.get("data", {}) if health_result.get("success") else {}
        
        # Get task statistics
        self.update_progress(2, 4, "Collecting task statistics...")
        task_stats = _get_task_statistics()
        
        # Get resource usage
        self.update_progress(3, 4, "Collecting resource usage...")
        resource_usage = _get_resource_usage()
        
        # Generate report
        self.update_progress(4, 4, "Finalizing report...")
        report = {
            "report_timestamp": datetime.utcnow().isoformat(),
            "system_health": health_data,
            "task_statistics": task_stats,
            "resource_usage": resource_usage,
            "uptime_hours": _get_system_uptime()
        }
        
        return TaskResult(
            success=True,
            data=report
        ).to_dict()
        
    except Exception as e:
        logger.error(f"System report generation failed: {e}")
        return TaskResult(
            success=False,
            error=str(e),
            error_type=type(e).__name__
        ).to_dict()


def _get_task_statistics() -> Dict[str, Any]:
    """Get task execution statistics."""
    try:
        # This would collect task statistics from the result backend
        # For now, return mock statistics
        return {
            "total_tasks_24h": 150,
            "successful_tasks_24h": 142,
            "failed_tasks_24h": 8,
            "average_execution_time_seconds": 45.2,
            "most_common_task_types": [
                {"task": "categorize_content_item", "count": 45},
                {"task": "generate_knowledge_item", "count": 38},
                {"task": "fetch_content_from_sources", "count": 25}
            ]
        }
    except Exception as e:
        logger.error(f"Failed to get task statistics: {e}")
        return {}


def _get_resource_usage() -> Dict[str, Any]:
    """Get system resource usage."""
    try:
        import psutil
        
        # CPU usage
        cpu_percent = psutil.cpu_percent(interval=1)
        
        # Memory usage
        memory = psutil.virtual_memory()
        
        # Disk usage
        disk = psutil.disk_usage('/')
        
        return {
            "cpu_usage_percent": cpu_percent,
            "memory_usage_percent": memory.percent,
            "memory_available_gb": round(memory.available / (1024**3), 2),
            "disk_usage_percent": round((disk.used / disk.total) * 100, 2),
            "disk_free_gb": round(disk.free / (1024**3), 2)
        }
    except Exception as e:
        logger.error(f"Failed to get resource usage: {e}")
        return {}


def _get_system_uptime() -> float:
    """Get system uptime in hours."""
    try:
        import psutil
        boot_time = psutil.boot_time()
        uptime_seconds = time.time() - boot_time
        return round(uptime_seconds / 3600, 2)
    except Exception as e:
        logger.error(f"Failed to get system uptime: {e}")
        return 0.0


@celery_app.task(bind=True, base=MonitoringTask, name="monitor_queue_sizes")
def monitor_queue_sizes(self) -> Dict[str, Any]:
    """
    Monitor Celery queue sizes and alert if queues are backing up.
    
    Returns:
        Dict containing queue monitoring results
    """
    try:
        self.update_progress(0, 1, "Monitoring queue sizes...")
        
        from celery import current_app
        
        # Get queue lengths
        inspect = current_app.control.inspect()
        active_queues = inspect.active_queues()
        
        queue_stats = {}
        alerts = []
        
        if active_queues:
            for worker, queues in active_queues.items():
                for queue_info in queues:
                    queue_name = queue_info['name']
                    
                    # This would get actual queue length from Redis
                    # For now, use mock data
                    queue_length = 5  # Mock queue length
                    
                    queue_stats[queue_name] = {
                        "length": queue_length,
                        "worker": worker
                    }
                    
                    # Alert if queue is backing up
                    if queue_length > 50:
                        alerts.append({
                            "queue": queue_name,
                            "length": queue_length,
                            "severity": "high" if queue_length > 100 else "medium"
                        })
        
        self.update_progress(1, 1, "Queue monitoring completed")
        
        return TaskResult(
            success=True,
            data={
                "timestamp": datetime.utcnow().isoformat(),
                "queue_stats": queue_stats,
                "alerts": alerts,
                "total_queues": len(queue_stats),
                "queues_with_alerts": len(alerts)
            }
        ).to_dict()
        
    except Exception as e:
        logger.error(f"Queue monitoring failed: {e}")
        return TaskResult(
            success=False,
            error=str(e),
            error_type=type(e).__name__
        ).to_dict()