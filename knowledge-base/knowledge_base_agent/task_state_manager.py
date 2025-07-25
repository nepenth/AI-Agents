"""
Enhanced Task State Management Service

Provides comprehensive task lifecycle management, state persistence,
and frontend state recovery capabilities.
"""

import logging
import json
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import asdict

from .models import db, CeleryTaskState, AgentState, JobHistory, TaskLog
from .config import Config
from .preferences import UserPreferences

logger = logging.getLogger(__name__)


class TaskStateManager:
    """
    Centralized task state management with complete lifecycle tracking.
    Handles task creation, progress updates, completion, and historical records.
    """
    
    def __init__(self, config: Config):
        self.config = config
    
    def create_task(
        self, 
        task_id: str, 
        task_type: str, 
        preferences: Optional[UserPreferences] = None,
        celery_task_id: Optional[str] = None,
        job_type: str = 'manual',
        trigger_source: str = 'web_ui'
    ) -> CeleryTaskState:
        """
        Create a new task with complete state initialization.
        
        Args:
            task_id: Unique task identifier
            task_type: Type of task ('agent_run', 'fetch_bookmarks', etc.)
            preferences: User preferences for agent runs
            celery_task_id: Celery's internal task ID
            job_type: Type of job ('manual', 'scheduled', 'api')
            trigger_source: Source that triggered the job
            
        Returns:
            Created CeleryTaskState instance
        """
        try:
            # Generate human-readable name
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            human_name = f"{task_type.replace('_', ' ').title()} - {timestamp}"
            
            # Create task state record
            task_state = CeleryTaskState(
                task_id=task_id,
                celery_task_id=celery_task_id,
                task_type=task_type,
                status='PENDING',
                human_readable_name=human_name,
                preferences=asdict(preferences) if preferences else None,
                is_active=True
            )
            
            db.session.add(task_state)
            
            # Create job history record
            job_history = JobHistory(
                task_id=task_id,
                job_type=job_type,
                trigger_source=trigger_source,
                user_preferences=asdict(preferences) if preferences else None,
                system_info=self._get_system_info()
            )
            
            db.session.add(job_history)
            
            # Update agent state for agent runs
            if task_type == 'agent_run':
                agent_state = self._get_or_create_agent_state()
                agent_state.is_running = True
                agent_state.current_task_id = task_id
                agent_state.current_phase_message = 'Task starting...'
                agent_state.current_run_preferences = json.dumps(asdict(preferences)) if preferences else None
                agent_state.last_update = datetime.now(timezone.utc)
            
            db.session.commit()
            logger.info(f"Created task {task_id} with type {task_type}")
            
            return task_state
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"Failed to create task {task_id}: {e}")
            raise
    
    def update_task_progress(
        self, 
        task_id: str, 
        progress: int, 
        phase_id: str, 
        message: str,
        status: str = 'PROGRESS'
    ) -> bool:
        """
        Update task progress and state.
        
        Args:
            task_id: Task identifier
            progress: Progress percentage (0-100)
            phase_id: Current phase identifier
            message: Progress message
            status: Task status
            
        Returns:
            True if update successful, False otherwise
        """
        try:
            task_state = CeleryTaskState.query.filter_by(task_id=task_id).first()
            if not task_state:
                logger.warning(f"Task {task_id} not found for progress update")
                return False
            
            # Update task state
            task_state.status = status
            task_state.current_phase_id = phase_id
            task_state.current_phase_message = message
            task_state.progress_percentage = progress
            task_state.updated_at = datetime.utcnow()
            
            # Update started_at if this is the first progress update
            if not task_state.started_at and status == 'PROGRESS':
                task_state.started_at = datetime.utcnow()
            
            # Update agent state for agent runs
            if task_state.task_type == 'agent_run':
                agent_state = self._get_or_create_agent_state()
                agent_state.current_phase_message = message
                agent_state.current_phase_id = phase_id
                agent_state.last_update = datetime.now(timezone.utc)
            
            db.session.commit()
            return True
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"Failed to update progress for task {task_id}: {e}")
            return False
    
    def complete_task(
        self, 
        task_id: str, 
        status: str, 
        result_data: Optional[Dict[str, Any]] = None,
        run_report: Optional[Dict[str, Any]] = None,
        error_message: Optional[str] = None,
        traceback: Optional[str] = None
    ) -> bool:
        """
        Mark task as completed and create comprehensive historical record.
        
        Args:
            task_id: Task identifier
            status: Final status ('SUCCESS', 'FAILURE', 'REVOKED')
            result_data: Task execution results
            run_report: Detailed run report
            error_message: Error message if failed
            traceback: Error traceback if failed
            
        Returns:
            True if completion successful, False otherwise
        """
        try:
            task_state = CeleryTaskState.query.filter_by(task_id=task_id).first()
            if not task_state:
                logger.warning(f"Task {task_id} not found for completion")
                return False
            
            # Calculate execution duration
            duration = None
            if task_state.started_at:
                duration_seconds = (datetime.utcnow() - task_state.started_at).total_seconds()
                duration = self._format_duration(duration_seconds)
            
            # Update task state
            task_state.status = status
            task_state.completed_at = datetime.utcnow()
            task_state.updated_at = datetime.utcnow()
            task_state.execution_duration = duration
            task_state.result_data = result_data
            task_state.run_report = run_report
            task_state.error_message = error_message
            task_state.traceback = traceback
            task_state.is_active = False
            
            # Extract processing statistics from run_report
            if run_report:
                task_state.items_processed = run_report.get('processed_count', 0)
                task_state.items_failed = run_report.get('error_count', 0)
            
            # Update job history with execution results
            job_history = JobHistory.query.filter_by(task_id=task_id).first()
            if job_history:
                job_history.execution_summary = self._create_execution_summary(task_state, run_report)
                job_history.phase_results = run_report.get('phase_statuses') if run_report else None
                job_history.performance_metrics = self._extract_performance_metrics(run_report)
            
            # Update agent state for agent runs
            if task_state.task_type == 'agent_run':
                agent_state = self._get_or_create_agent_state()
                agent_state.is_running = False
                agent_state.current_task_id = None
                agent_state.current_phase_message = 'Idle'
                agent_state.current_phase_id = None
                agent_state.last_update = datetime.now(timezone.utc)
            
            db.session.commit()
            logger.info(f"Completed task {task_id} with status {status}")
            
            return True
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"Failed to complete task {task_id}: {e}")
            return False
    
    def get_active_task(self) -> Optional[Dict[str, Any]]:
        """
        Get the currently active task with full state information.
        
        Returns:
            Dictionary with active task data or None if no active task
        """
        try:
            # First check agent state
            agent_state = AgentState.query.first()
            if agent_state and agent_state.is_running and agent_state.current_task_id:
                task_id = agent_state.current_task_id
            else:
                # Fallback: look for any active task
                active_task = CeleryTaskState.query.filter_by(is_active=True).first()
                if not active_task:
                    return None
                task_id = active_task.task_id
            
            return self.get_task_status(task_id)
            
        except Exception as e:
            logger.error(f"Failed to get active task: {e}")
            return None
    
    def get_task_status(self, task_id: str) -> Optional[Dict[str, Any]]:
        """
        Get comprehensive task status including logs and progress.
        
        Args:
            task_id: Task identifier
            
        Returns:
            Dictionary with complete task status or None if not found
        """
        try:
            task_state = CeleryTaskState.query.filter_by(task_id=task_id).first()
            if not task_state:
                return None
            
            # Get recent logs
            recent_logs = TaskLog.query.filter_by(task_id=task_id)\
                .order_by(TaskLog.sequence_number.desc())\
                .limit(50)\
                .all()
            
            # Get job history
            job_history = JobHistory.query.filter_by(task_id=task_id).first()
            
            return {
                'task_id': task_id,
                'human_readable_name': task_state.human_readable_name,
                'task_type': task_state.task_type,
                'status': task_state.status,
                'is_running': task_state.status in ['PENDING', 'PROGRESS'],
                'is_active': task_state.is_active,
                'current_phase_id': task_state.current_phase_id,
                'current_phase_message': task_state.current_phase_message,
                'progress_percentage': task_state.progress_percentage,
                'items_processed': task_state.items_processed,
                'items_failed': task_state.items_failed,
                'execution_duration': task_state.execution_duration,
                'created_at': task_state.created_at.isoformat() if task_state.created_at else None,
                'started_at': task_state.started_at.isoformat() if task_state.started_at else None,
                'completed_at': task_state.completed_at.isoformat() if task_state.completed_at else None,
                'updated_at': task_state.updated_at.isoformat() if task_state.updated_at else None,
                'preferences': task_state.preferences,
                'result_data': task_state.result_data,
                'run_report': task_state.run_report,
                'error_message': task_state.error_message,
                'logs': [log.to_dict() for log in recent_logs],
                'job_history': job_history.to_dict() if job_history else None
            }
            
        except Exception as e:
            logger.error(f"Failed to get task status for {task_id}: {e}")
            return None
    
    def get_job_history(
        self, 
        limit: int = 50, 
        offset: int = 0,
        job_type: Optional[str] = None,
        status_filter: Optional[str] = None
    ) -> Tuple[List[Dict[str, Any]], int]:
        """
        Get paginated job history with filtering.
        
        Args:
            limit: Maximum number of records to return
            offset: Number of records to skip
            job_type: Filter by job type ('manual', 'scheduled', 'api')
            status_filter: Filter by status ('SUCCESS', 'FAILURE', etc.)
            
        Returns:
            Tuple of (job_list, total_count)
        """
        try:
            query = db.session.query(JobHistory).join(CeleryTaskState)
            
            # Apply filters
            if job_type:
                query = query.filter(JobHistory.job_type == job_type)
            if status_filter:
                query = query.filter(CeleryTaskState.status == status_filter)
            
            # Get total count
            total_count = query.count()
            
            # Apply pagination and ordering
            jobs = query.order_by(JobHistory.created_at.desc())\
                .offset(offset)\
                .limit(limit)\
                .all()
            
            return [job.to_dict() for job in jobs], total_count
            
        except Exception as e:
            logger.error(f"Failed to get job history: {e}")
            return [], 0
    
    def cleanup_old_tasks(self, days_to_keep: int = 30) -> int:
        """
        Clean up old completed tasks and their logs.
        
        Args:
            days_to_keep: Number of days of history to keep
            
        Returns:
            Number of tasks cleaned up
        """
        try:
            from datetime import timedelta
            cutoff_date = datetime.utcnow() - timedelta(days=days_to_keep)
            
            # Find old completed tasks
            old_tasks = CeleryTaskState.query.filter(
                CeleryTaskState.completed_at < cutoff_date,
                CeleryTaskState.status.in_(['SUCCESS', 'FAILURE', 'REVOKED']),
                CeleryTaskState.is_archived == False
            ).all()
            
            cleaned_count = 0
            for task in old_tasks:
                # Archive instead of delete to preserve history
                task.is_archived = True
                cleaned_count += 1
            
            db.session.commit()
            logger.info(f"Archived {cleaned_count} old tasks")
            
            return cleaned_count
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"Failed to cleanup old tasks: {e}")
            return 0
    
    def reset_agent_state(self) -> bool:
        """
        Enhanced agent state reset with comprehensive cleanup (emergency recovery function).
        
        This function performs a complete reset of the agent system:
        1. Revokes all active Celery tasks
        2. Clears stuck database task records
        3. Clears Redis progress/log data for stuck tasks
        4. Resets agent state to idle
        
        Returns:
            True if reset successful, False otherwise
        """
        try:
            from .celery_app import celery_app
            from .task_progress import get_progress_manager
            import asyncio
            
            logger.info("Starting comprehensive agent state reset...")
            
            # Step 1: Get all stuck tasks (running but likely orphaned)
            stuck_tasks = CeleryTaskState.query.filter(
                CeleryTaskState.status.in_(['PENDING', 'PROGRESS', 'STARTED'])
            ).all()
            
            stuck_task_ids = [task.task_id for task in stuck_tasks]
            stuck_celery_ids = [task.celery_task_id for task in stuck_tasks if task.celery_task_id]
            
            logger.info(f"Found {len(stuck_tasks)} stuck tasks to clean up")
            
            # Step 2: Revoke all active Celery tasks
            try:
                # Get currently active Celery tasks
                inspect = celery_app.control.inspect()
                active_tasks = inspect.active() or {}
                
                # Revoke all active tasks
                for worker, tasks in active_tasks.items():
                    for task in tasks:
                        celery_task_id = task.get('id')
                        logger.info(f"Revoking active Celery task: {celery_task_id}")
                        celery_app.control.revoke(celery_task_id, terminate=True, signal='SIGTERM')
                
                # Also revoke stuck tasks by their Celery IDs
                for celery_id in stuck_celery_ids:
                    if celery_id:
                        logger.info(f"Revoking stuck Celery task: {celery_id}")
                        celery_app.control.revoke(celery_id, terminate=True, signal='SIGTERM')
                        
            except Exception as e:
                logger.warning(f"Error revoking Celery tasks (continuing anyway): {e}")
            
            # Step 3: Clear Redis data for stuck tasks
            try:
                progress_manager = get_progress_manager(self.config)
                
                # Create event loop if needed
                try:
                    loop = asyncio.get_event_loop()
                except RuntimeError:
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                
                # Clear Redis data for each stuck task
                for task_id in stuck_task_ids:
                    try:
                        if loop.is_running():
                            # If loop is running, we need to handle this differently
                            import concurrent.futures
                            with concurrent.futures.ThreadPoolExecutor() as executor:
                                future = executor.submit(asyncio.run, progress_manager.clear_task_data(task_id))
                                future.result(timeout=5)
                        else:
                            loop.run_until_complete(progress_manager.clear_task_data(task_id))
                        logger.info(f"Cleared Redis data for task: {task_id}")
                    except Exception as e:
                        logger.warning(f"Error clearing Redis data for task {task_id}: {e}")
                        
            except Exception as e:
                logger.warning(f"Error clearing Redis data (continuing anyway): {e}")
            
            # Step 4: Update stuck tasks in database
            for task in stuck_tasks:
                task.status = 'REVOKED'
                task.is_active = False
                task.completed_at = datetime.now(timezone.utc)
                task.updated_at = datetime.now(timezone.utc)
                task.error_message = 'Task revoked during agent state reset'
                logger.info(f"Marked task as revoked: {task.task_id}")
            
            # Step 5: Reset agent state
            agent_state = self._get_or_create_agent_state()
            agent_state.is_running = False
            agent_state.current_task_id = None
            agent_state.current_phase_message = 'Idle (reset completed)'
            agent_state.current_phase_id = None
            agent_state.stop_flag_status = False
            agent_state.last_update = datetime.now(timezone.utc)
            
            # Step 6: Mark any remaining active tasks as inactive
            remaining_active_tasks = CeleryTaskState.query.filter_by(is_active=True).all()
            for task in remaining_active_tasks:
                task.is_active = False
                task.updated_at = datetime.now(timezone.utc)
            
            db.session.commit()
            
            logger.info(f"Agent state reset completed successfully. Cleaned up {len(stuck_tasks)} stuck tasks.")
            
            return True
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"Failed to reset agent state: {e}", exc_info=True)
            return False
    
    def _get_or_create_agent_state(self) -> AgentState:
        """Get or create the singleton agent state."""
        agent_state = AgentState.query.first()
        if not agent_state:
            agent_state = AgentState()
            db.session.add(agent_state)
        return agent_state
    
    def _get_system_info(self) -> Dict[str, Any]:
        """Get current system information for job history."""
        import platform
        import psutil
        
        try:
            return {
                'platform': platform.platform(),
                'python_version': platform.python_version(),
                'cpu_count': psutil.cpu_count(),
                'memory_total': psutil.virtual_memory().total,
                'timestamp': datetime.utcnow().isoformat()
            }
        except Exception as e:
            logger.warning(f"Failed to get system info: {e}")
            return {'error': str(e)}
    
    def _create_execution_summary(
        self, 
        task_state: CeleryTaskState, 
        run_report: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Create execution summary for job history."""
        summary = {
            'task_type': task_state.task_type,
            'status': task_state.status,
            'duration': task_state.execution_duration,
            'items_processed': task_state.items_processed or 0,
            'items_failed': task_state.items_failed or 0
        }
        
        if run_report:
            summary.update({
                'final_status': run_report.get('final_status'),
                'force_flags': run_report.get('force_flags', []),
                'execution_time': run_report.get('execution_time')
            })
        
        return summary
    
    def _extract_performance_metrics(
        self, 
        run_report: Optional[Dict[str, Any]]
    ) -> Optional[Dict[str, Any]]:
        """Extract performance metrics from run report."""
        if not run_report:
            return None
        
        return {
            'execution_time': run_report.get('execution_time'),
            'processed_count': run_report.get('processed_count', 0),
            'error_count': run_report.get('error_count', 0),
            'phase_count': len(run_report.get('phase_statuses', {}))
        }
    
    def _format_duration(self, seconds: float) -> str:
        """Format duration in seconds to human-readable string."""
        if seconds < 60:
            return f"{seconds:.1f}s"
        elif seconds < 3600:
            minutes = seconds / 60
            return f"{minutes:.1f}m"
        else:
            hours = seconds / 3600
            return f"{hours:.1f}h"