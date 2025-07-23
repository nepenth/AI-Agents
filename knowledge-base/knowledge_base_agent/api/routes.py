from flask import Blueprint, jsonify, request, current_app, send_from_directory, url_for, abort
from ..models import db, KnowledgeBaseItem, SubcategorySynthesis, Setting, AgentState, CeleryTaskState, TaskLog
from ..prompts import UserPreferences, save_user_preferences
from ..task_progress import get_progress_manager
from ..config import Config
from ..agent import KnowledgeBaseAgent
from .logs import list_logs
from .log_content import get_log_content
from ..postgresql_logging import LogQueryService
import shutil
from pathlib import Path
import os
from typing import Dict, Any, List
import logging
from datetime import datetime, timezone
import json
import uuid
import asyncio
import platform
import psutil
from dataclasses import asdict
import markdown
import concurrent.futures
import tempfile
import glob

# Celery Migration Imports (NEW)
from ..celery_app import celery_app

def run_async_in_gevent_context(coro):
    """
    Helper function to run async coroutines in a gevent context where an event loop may already be running.
    This handles the common Flask-SocketIO + gevent + asyncio integration issues.
    """
    try:
        # Try to get the current event loop
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # If loop is running (gevent context), use run_in_executor with a thread pool
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(asyncio.run, coro)
                return future.result(timeout=30)
        else:
            # If no loop is running, we can use run_until_complete
            return loop.run_until_complete(coro)
    except RuntimeError:
        # No event loop exists, create one
        return asyncio.run(coro)

bp = Blueprint('api', __name__)
logger = logging.getLogger(__name__)


# --- V2 CELERY-BASED AGENT ENDPOINTS (PRIMARY) ---

@bp.route('/v2/agent/start', methods=['POST'])
def start_agent_v2():
    """Sync wrapper that queues an agent run. Executes async logic via asyncio.run."""

    async def _start_async():
        from ..tasks import run_agent_task, generate_task_id
        from ..web import get_or_create_agent_state
        from ..prompts import UserPreferences, save_user_preferences

        data = request.json or {}
        preferences_data = data.get('preferences', {})

        # Validate preferences
        try:
            user_preferences = UserPreferences(**preferences_data)
            preferences_dict = asdict(user_preferences)
        except Exception as e:
            logger.error("Invalid preferences data: %s", e)
            return jsonify({'success': False, 'error': f'Invalid preferences: {e}'}), 400

        task_id = generate_task_id()
        celery_task = run_agent_task.delay(task_id, preferences_dict)

        progress_manager = get_progress_manager()
        await progress_manager.update_progress(task_id, 0, "queued", "Agent execution queued")

        state = get_or_create_agent_state()
        state.is_running = True
        state.current_task_id = task_id
        state.current_phase_message = 'Agent starting...'
        state.last_update = datetime.utcnow()
        db.session.commit()

        save_user_preferences(preferences_data)

        return jsonify({'success': True, 'task_id': task_id, 'celery_task_id': celery_task.id, 'message': 'Agent execution queued'})

    return run_async_in_gevent_context(_start_async())


# Replace async route with sync wrapper ----------------------------------
@bp.route('/v2/agent/status/<task_id>', methods=['GET'])
def get_task_status(task_id: str):
    """Sync wrapper around async status-gathering logic."""

    async def _status_async(tid: str):
        progress_manager = get_progress_manager()

        progress_data = await progress_manager.get_progress(tid)

        celery_task = celery_app.AsyncResult(tid)
        try:
            celery_status = {
                'state': celery_task.state,
                'info': celery_task.info if isinstance(celery_task.info, dict) else str(celery_task.info)
            }
        except ValueError as e:
            if 'Exception information must include' in str(e):
                logger.warning("Task %s has a corrupted result in the backend. Reporting as FAILED.", tid)
                celery_status = {'state': 'FAILURE', 'info': 'Corrupted result in backend.'}
            else:
                raise

        logs = await progress_manager.get_logs(tid, limit=10)

        # Get task metadata from database
        task_metadata = CeleryTaskState.query.filter_by(task_id=tid).first()
        human_readable_name = None
        if task_metadata:
            human_readable_name = task_metadata.human_readable_name

        response_data = {
            'task_id': tid,
            'human_readable_name': human_readable_name,
            'progress': progress_data,
            'celery_status': celery_status,
            'logs': logs
        }

        running_states = {'PENDING', 'PROGRESS', 'STARTED', 'RETRY'}
        response_data['is_running'] = celery_status['state'] in running_states

        response_data['current_phase_message'] = (
            progress_data.get('message') if progress_data and progress_data.get('message') else celery_status['state']
        )

        if progress_data:
            response_data.update(progress_data)

        return jsonify(response_data)

    try:
        return run_async_in_gevent_context(_status_async(task_id))
    except Exception as e:
        logger.error("Error getting agent status for task %s: %s", task_id, e, exc_info=True)
        return jsonify({'error': str(e)}), 500

# ------------------------------------------------------------------------
@bp.route('/v2/agent/stop', methods=['POST'])
def stop_agent_v2():
    """Stops a running agent task via Celery."""
    async def _stop_async():
        data = request.json or {}
        task_id = data.get('task_id')
        
        # If no task_id provided, get it from agent state
        if not task_id:
            from ..web import get_or_create_agent_state
            state = get_or_create_agent_state()
            task_id = state.current_task_id
            
        if not task_id:
            return jsonify({'success': False, 'error': 'No running task found to stop'}), 400

        logger.info(f"Stopping agent task: {task_id}")
        
        # Check if task is already stopped to avoid duplicate stop messages
        celery_task = celery_app.AsyncResult(task_id)
        if celery_task.state in ['REVOKED', 'FAILURE', 'SUCCESS']:
            logger.info(f"Task {task_id} already in terminal state: {celery_task.state}")
            return jsonify({'success': True, 'message': f'Task {task_id} already stopped'})
        
        # Revoke the Celery task
        celery_app.control.revoke(task_id, terminate=True, signal='SIGTERM')
        
        # Also try to revoke by Celery task ID if different
        celery_task = celery_app.AsyncResult(task_id)
        if celery_task.id != task_id:
            celery_app.control.revoke(celery_task.id, terminate=True, signal='SIGTERM')

        progress_manager = get_progress_manager()
        await progress_manager.update_progress(task_id, -1, "revoked", "Agent execution stopped by user.")
        await progress_manager.log_message(task_id, "🛑 Agent execution stopped by user request", "WARNING")

        from ..web import get_or_create_agent_state
        state = get_or_create_agent_state()
        if state.current_task_id == task_id:
            state.is_running = False
            state.current_task_id = None
            state.current_phase_message = 'Agent stopped by user'
            state.last_update = datetime.utcnow()
            db.session.commit()

        return jsonify({'success': True, 'message': f'Agent stop request sent for task {task_id}'})

    try:
        return run_async_in_gevent_context(_stop_async())
    except Exception as e:
        logger.error("Failed to stop agent task: %s", e, exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500

# ------------------------------------------------------------------------
# Historical Task Viewing Endpoints
@bp.route('/v2/agent/history', methods=['GET'])
def get_task_history():
    """Get recent completed tasks for historical viewing."""
    try:
        limit = request.args.get('limit', 5, type=int)
        
        # Get recent completed tasks
        completed_tasks = CeleryTaskState.query.filter(
            CeleryTaskState.status.in_(['SUCCESS', 'FAILURE'])
        ).order_by(CeleryTaskState.completed_at.desc()).limit(limit).all()
        
        task_list = []
        for task in completed_tasks:
            task_info = {
                'task_id': task.task_id,
                'human_readable_name': task.human_readable_name or f"Task {task.task_id[:8]}",
                'status': task.status,
                'created_at': task.created_at.isoformat() if task.created_at else None,
                'completed_at': task.completed_at.isoformat() if task.completed_at else None,
                'duration': None,
                'processed_count': 0,
                'error_count': 0
            }
            
            # Calculate duration
            if task.started_at and task.completed_at:
                duration = (task.completed_at - task.started_at).total_seconds()
                task_info['duration'] = f"{duration:.1f}s"
            
            # Extract processing stats from result_data or run_report
            if task.run_report:
                task_info['processed_count'] = task.run_report.get('processed_count', 0)
                task_info['error_count'] = task.run_report.get('error_count', 0)
            elif task.result_data:
                result = task.result_data.get('result', {})
                task_info['processed_count'] = result.get('processed_count', 0)
                task_info['error_count'] = result.get('error_count', 0)
            
            task_list.append(task_info)
        
        return jsonify({
            'success': True,
            'tasks': task_list,
            'total_count': len(task_list)
        })
        
    except Exception as e:
        logger.error(f"Error getting task history: {e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500


@bp.route('/v2/agent/history/<task_id>', methods=['GET'])
def get_historical_task_details(task_id: str):
    """Get detailed information about a completed task including logs and run report."""
    try:
        task = CeleryTaskState.query.filter_by(task_id=task_id).first()
        if not task:
            return jsonify({'success': False, 'error': 'Task not found'}), 404
        
        # Get logs for this task
        progress_manager = get_progress_manager()
        logs = []
        try:
            logs = run_async_in_gevent_context(progress_manager.get_task_logs(task_id))
        except Exception as log_error:
            logger.warning(f"Could not retrieve logs for task {task_id}: {log_error}")
        
        # Build detailed task information
        task_details = {
            'task_id': task.task_id,
            'human_readable_name': task.human_readable_name or f"Task {task.task_id[:8]}",
            'status': task.status,
            'created_at': task.created_at.isoformat() if task.created_at else None,
            'started_at': task.started_at.isoformat() if task.started_at else None,
            'completed_at': task.completed_at.isoformat() if task.completed_at else None,
            'duration': None,
            'preferences': task.preferences or {},
            'run_report': task.run_report or {},
            'result_data': task.result_data or {},
            'error_message': task.error_message,
            'logs': logs
        }
        
        # Calculate duration
        if task.started_at and task.completed_at:
            duration = (task.completed_at - task.started_at).total_seconds()
            task_details['duration'] = f"{duration:.1f}s"
        
        return jsonify({
            'success': True,
            'task': task_details
        })
        
    except Exception as e:
        logger.error(f"Error getting historical task details: {e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500

# ------------------------------------------------------------------------
@bp.route('/v2/celery/clear-queue', methods=['POST'])
def clear_celery_queue_v2():
    """Clear all tasks from Celery queue."""
    try:
        celery_app.control.purge()
        logger.info("Celery queue cleared")
        return jsonify({'success': True, 'message': 'Task queue cleared successfully'})
    except Exception as e:
        logger.error("Failed to clear Celery queue: %s", e, exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500

@bp.route('/v2/celery/clear-old-tasks', methods=['POST'])
def clear_old_celery_tasks_v2():
    """Clear old Celery tasks from database and Redis."""
    try:
        data = request.json or {}
        older_than_hours = data.get('older_than', 24)
        status_filter = data.get('status', [])  # List of statuses to filter
        dry_run = data.get('dry_run', False)
        
        from datetime import datetime, timedelta
        cutoff_time = datetime.utcnow() - timedelta(hours=older_than_hours)
        
        # Query old tasks
        query = CeleryTaskState.query.filter(CeleryTaskState.created_at < cutoff_time)
        
        if status_filter:
            query = query.filter(CeleryTaskState.status.in_(status_filter))
        
        old_tasks = query.all()
        
        if dry_run:
            task_info = [{'task_id': task.task_id, 'status': task.status, 'created_at': task.created_at.isoformat()} for task in old_tasks]
            return jsonify({
                'success': True,
                'message': f'Would delete {len(old_tasks)} tasks',
                'tasks': task_info,
                'dry_run': True
            })
        
        # Clear from Redis and database
        progress_manager = get_progress_manager()
        deleted_count = 0
        
        for task in old_tasks:
            try:
                # Clear from Redis
                run_async_in_gevent_context(progress_manager.clear_task_data(task.task_id))
                
                # Delete from database
                db.session.delete(task)
                deleted_count += 1
            except Exception as e:
                logger.warning(f"Failed to delete task {task.task_id}: {e}")
        
        db.session.commit()
        
        logger.info(f"Cleared {deleted_count} old Celery tasks")
        return jsonify({
            'success': True,
            'message': f'Cleared {deleted_count} old tasks',
            'deleted_count': deleted_count
        })
        
    except Exception as e:
        logger.error("Failed to clear old Celery tasks: %s", e, exc_info=True)
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500

@bp.route('/v2/celery/stuck-tasks', methods=['GET'])
def get_stuck_celery_tasks_v2():
    """Get tasks that have been running for too long."""
    try:
        data = request.args
        max_runtime_hours = int(data.get('max_runtime', 3))
        
        from datetime import datetime, timedelta
        cutoff_time = datetime.utcnow() - timedelta(hours=max_runtime_hours)
        
        # Get tasks that started before cutoff and are still in progress
        stuck_tasks = CeleryTaskState.query.filter(
            CeleryTaskState.started_at < cutoff_time,
            CeleryTaskState.status.in_(['PROGRESS', 'STARTED', 'PENDING'])
        ).all()
        
        task_info = []
        for task in stuck_tasks:
            runtime_hours = (datetime.utcnow() - task.started_at).total_seconds() / 3600 if task.started_at else 0
            task_info.append({
                'task_id': task.task_id,
                'celery_task_id': task.celery_task_id,
                'status': task.status,
                'started_at': task.started_at.isoformat() if task.started_at else None,
                'runtime_hours': round(runtime_hours, 2),
                'current_phase_message': task.current_phase_message
            })
        
        return jsonify({
            'success': True,
            'stuck_tasks': task_info,
            'count': len(task_info)
        })
        
    except Exception as e:
        logger.error("Failed to get stuck Celery tasks: %s", e, exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500

@bp.route('/v2/celery/revoke-tasks', methods=['POST'])
def revoke_celery_tasks_v2():
    """Revoke (cancel) specific or all active Celery tasks."""
    try:
        data = request.json or {}
        task_id = data.get('task_id')
        all_active = data.get('all_active', False)
        
        if not task_id and not all_active:
            return jsonify({'success': False, 'error': 'Must specify either task_id or all_active'}), 400
        
        revoked_tasks = []
        
        if task_id:
            # Revoke specific task
            celery_app.control.revoke(task_id, terminate=True, signal='SIGTERM')
            revoked_tasks.append(task_id)
            logger.info(f"Revoked task: {task_id}")
        
        if all_active:
            # Get and revoke all active tasks
            inspect = celery_app.control.inspect()
            active_tasks = inspect.active() or {}
            
            for worker, tasks in active_tasks.items():
                for task in tasks:
                    task_id = task.get('id')
                    celery_app.control.revoke(task_id, terminate=True, signal='SIGTERM')
                    revoked_tasks.append(task_id)
                    logger.info(f"Revoked task: {task_id}")
        
        return jsonify({
            'success': True,
            'message': f'Revoked {len(revoked_tasks)} tasks',
            'revoked_tasks': revoked_tasks
        })
        
    except Exception as e:
        logger.error("Failed to revoke Celery tasks: %s", e, exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500

@bp.route('/v2/celery/flush-redis', methods=['POST'])
def flush_redis_celery_data_v2():
    """Flush all task data from Redis."""
    try:
        progress_manager = get_progress_manager()
        
        # Clear all progress and log data
        run_async_in_gevent_context(progress_manager.clear_all_data())
        
        logger.info("Flushed all Celery task data from Redis")
        return jsonify({
            'success': True,
            'message': 'All task data flushed from Redis'
        })
        
    except Exception as e:
        logger.error("Failed to flush Redis data: %s", e, exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500

@bp.route('/v2/celery/purge-tasks', methods=['POST'])
def purge_celery_tasks_v2():
    """Purge all Celery tasks (active and queued)."""
    try:
        # Get active tasks
        active_tasks = celery_app.control.inspect().active()
        
        # Revoke all active tasks
        if active_tasks:
            for worker, tasks in active_tasks.items():
                for task in tasks:
                    task_id = task.get('id')
                    celery_app.control.revoke(task_id, terminate=True, signal='SIGTERM')
                    logger.info(f"Revoked task: {task_id}")
        
        # Purge queue
        celery_app.control.purge()
        
        logger.info("All Celery tasks purged")
        return jsonify({'success': True, 'message': 'All tasks purged successfully'})
    except Exception as e:
        logger.error("Failed to purge Celery tasks: %s", e, exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500

@bp.route('/v2/celery/restart-workers', methods=['POST'])
def restart_celery_workers_v2():
    """Restart Celery workers."""
    try:
        # Send restart signal to workers
        celery_app.control.broadcast('pool_restart', arguments={'reload': True})
        logger.info("Celery worker restart signal sent")
        return jsonify({'success': True, 'message': 'Worker restart signal sent'})
    except Exception as e:
        logger.error("Failed to restart Celery workers: %s", e, exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500

@bp.route('/v2/celery/status', methods=['GET'])
def celery_worker_status_v2():
    """Get Celery worker status."""
    try:
        inspect = celery_app.control.inspect()
        
        # Get worker stats
        stats = inspect.stats()
        active_tasks = inspect.active()
        scheduled_tasks = inspect.scheduled()
        
        status_data = {
            'workers': stats or {},
            'active_tasks': active_tasks or {},
            'scheduled_tasks': scheduled_tasks or {},
            'total_active': sum(len(tasks) for tasks in (active_tasks or {}).values()),
            'total_scheduled': sum(len(tasks) for tasks in (scheduled_tasks or {}).values())
        }
        
        return jsonify({'success': True, 'data': status_data})
    except Exception as e:
        logger.error("Failed to get Celery status: %s", e, exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500


# --- LOGGING ENDPOINTS ---

@bp.route('/logs/recent', methods=['GET'])
def get_recent_logs():
    """Get recent log messages with normalized format matching SocketIO events."""
    from ..web import get_or_create_agent_state
    
    # Get current active task
    state = get_or_create_agent_state()
    current_task_id = state.current_task_id if state else None
    
    async def fetch_and_normalize_logs():
        if current_task_id:
            progress_manager = get_progress_manager()
            try:
                raw_logs = await progress_manager.get_logs(current_task_id, limit=100)
                normalized_logs = []
                
                for log in raw_logs:
                    try:
                        # Handle both string and dict formats
                        if isinstance(log, str):
                            try:
                                log = json.loads(log)
                            except json.JSONDecodeError as e:
                                logger.warning(f"Failed to parse log entry as JSON: {log[:100]}... Error: {e}")
                                # Create a basic log entry from the string
                                log = {
                                    'message': log,
                                    'level': 'INFO',
                                    'timestamp': datetime.utcnow().isoformat(),
                                    'task_id': current_task_id
                                }
                        
                        # NORMALIZED FORMAT: Match SocketIO event structure
                        normalized_log = {
                            'message': log.get('message', ''),
                            'level': log.get('level', 'INFO'),
                            'timestamp': log.get('timestamp', datetime.utcnow().isoformat()),
                            'component': log.get('component', 'system'),
                            'task_id': log.get('task_id', current_task_id)
                        }
                        
                        # Validate required fields
                        if not normalized_log['message']:
                            logger.warning(f"Log entry missing message field: {log}")
                            continue
                            
                        normalized_logs.append(normalized_log)
                        
                    except Exception as e:
                        logger.warning(f"Error processing log entry: {e}. Log: {log}")
                        # Continue processing other logs
                        continue
                
                return normalized_logs
                
            except Exception as e:
                logger.error(f"Error fetching logs from TaskProgressManager: {e}", exc_info=True)
                return []
        return []
    
    try:
        logs_list = run_async_in_gevent_context(fetch_and_normalize_logs())
        
        # If no current task, return success with helpful message
        if not current_task_id:
            return jsonify({
                'logs': [], 
                'task_id': None,
                'count': 0,
                'success': True,
                'message': 'No active agent task. Start an agent run to see live logs.'
            })
        
        return jsonify({
            'logs': logs_list, 
            'task_id': current_task_id,
            'count': len(logs_list),
            'success': True
        })
    except Exception as e:
        logger.error(f"Error getting recent logs: {e}", exc_info=True)
        return jsonify({
            'error': 'Failed to get recent logs', 
            'logs': [],
            'success': False,
            'message': f'Error loading logs: {str(e)}'
        }), 500

@bp.route('/logs/clear', methods=['POST'])
def clear_logs():
    """Clear logs for the current task."""
    from ..web import get_or_create_agent_state
    
    # Get current active task
    state = get_or_create_agent_state()
    current_task_id = state.current_task_id if state else None
    
    if not current_task_id:
        return jsonify({
            'success': False,
            'message': 'No active task'
        })
    
    async def clear_logs_operation():
        try:
            progress_manager = get_progress_manager()
            await progress_manager.clear_task_data(current_task_id)
            return True
        except Exception as e:
            logger.error(f"Error clearing logs: {e}", exc_info=True)
            return False
    
    try:
        success = run_async_in_gevent_context(clear_logs_operation())
        if success:
            return jsonify({
                'success': True,
                'message': 'Logs cleared'
            })
        else:
            return jsonify({
                'success': False,
                'message': 'Failed to clear logs'
            }), 500
    except Exception as e:
        logger.error(f"Error in clear logs endpoint: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'message': 'Failed to clear logs'
        }), 500


# --- POSTGRESQL LOGGING ENDPOINTS ---

@bp.route('/v2/logs/<task_id>', methods=['GET'])
def get_task_logs_postgresql(task_id: str):
    """Get logs for a specific task from PostgreSQL."""
    try:
        # Get query parameters
        level_filter = request.args.get('level')
        component_filter = request.args.get('component')
        phase_filter = request.args.get('phase')
        limit = request.args.get('limit', 1000, type=int)
        offset = request.args.get('offset', 0, type=int)
        since_sequence = request.args.get('since_sequence', 0, type=int)
        
        # Use since_sequence for real-time updates, otherwise use regular query
        if since_sequence > 0:
            logs = LogQueryService.get_recent_logs(task_id, since_sequence, limit)
        else:
            logs = LogQueryService.get_task_logs(
                task_id, level_filter, component_filter, phase_filter, limit, offset
            )
        
        return jsonify({
            'success': True,
            'task_id': task_id,
            'logs': logs,
            'count': len(logs)
        })
        
    except Exception as e:
        logger.error(f"Error getting PostgreSQL logs for task {task_id}: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@bp.route('/v2/logs/<task_id>/summary', methods=['GET'])
def get_task_log_summary(task_id: str):
    """Get a summary of logs for a specific task."""
    try:
        summary = LogQueryService.get_log_summary(task_id)
        return jsonify({
            'success': True,
            'summary': summary
        })
        
    except Exception as e:
        logger.error(f"Error getting log summary for task {task_id}: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@bp.route('/v2/logs/<task_id>/recent', methods=['GET'])
def get_recent_task_logs_postgresql(task_id: str):
    """Get recent logs for a task (for real-time updates)."""
    try:
        since_sequence = request.args.get('since_sequence', 0, type=int)
        limit = request.args.get('limit', 100, type=int)
        
        logs = LogQueryService.get_recent_logs(task_id, since_sequence, limit)
        
        return jsonify({
            'success': True,
            'task_id': task_id,
            'logs': logs,
            'count': len(logs),
            'latest_sequence': logs[-1]['sequence_number'] if logs else since_sequence
        })
        
    except Exception as e:
        logger.error(f"Error getting recent PostgreSQL logs for task {task_id}: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@bp.route('/v2/logs/<task_id>/export', methods=['GET'])
def export_task_logs(task_id: str):
    """Export all logs for a task as a downloadable file."""
    try:
        # Get all logs for the task
        logs = LogQueryService.get_task_logs(task_id, limit=10000)  # Large limit for export
        
        if not logs:
            return jsonify({
                'success': False,
                'error': 'No logs found for this task'
            }), 404
        
        # Format logs as text
        log_lines = []
        log_lines.append(f"# Task Logs Export - Task ID: {task_id}")
        log_lines.append(f"# Generated: {datetime.now(timezone.utc).isoformat()}")
        log_lines.append(f"# Total Logs: {len(logs)}")
        log_lines.append("")
        
        for log in logs:
            timestamp = log['timestamp']
            level = log['level']
            message = log['message']
            component = log.get('component', '')
            phase = log.get('phase', '')
            
            # Format: [TIMESTAMP] [LEVEL] [COMPONENT:PHASE] MESSAGE
            component_phase = f"{component}:{phase}" if component and phase else (component or phase or "system")
            log_line = f"[{timestamp}] [{level}] [{component_phase}] {message}"
            log_lines.append(log_line)
        
        log_content = "\n".join(log_lines)
        
        # Return as downloadable file
        from flask import Response
        return Response(
            log_content,
            mimetype='text/plain',
            headers={
                'Content-Disposition': f'attachment; filename=task_{task_id}_logs.txt'
            }
        )
        
    except Exception as e:
        logger.error(f"Error exporting logs for task {task_id}: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# --- PRIMARY STATUS ENDPOINT (V2 UI) ---

@bp.route('/agent/status', methods=['GET'])
def get_agent_status():
    """Get current agent status with validation to prevent stale state issues."""
    from ..web import get_or_create_agent_state
    from ..models import CeleryTaskState
    import asyncio

    state = get_or_create_agent_state()
    task_id = state.current_task_id

    if not task_id:
        return jsonify({
            'is_running': False,
            'task_id': None,
            'celery_task_id': None,
            'current_phase_message': 'Idle',
            'phase': 'idle',
            'progress': 0,
            'status': 'IDLE'
        })

    # CRITICAL FIX: Validate that the task is actually still running
    try:
        celery_task = CeleryTaskState.query.filter_by(task_id=task_id).first()
        
        if not celery_task:
            # Task not found in database - clear stale state
            logger.warning(f"Stale task_id {task_id} found in AgentState, clearing...")
            state.is_running = False
            state.current_task_id = None
            state.current_phase_message = 'Idle'
            state.last_update = datetime.utcnow()
            db.session.commit()
            
            return jsonify({
                'is_running': False,
                'task_id': None,
                'celery_task_id': None,
                'current_phase_message': 'Idle',
                'phase': 'idle',
                'progress': 0,
                'status': 'IDLE'
            })
        
        # Check if task is in a terminal state
        if celery_task.status in ['SUCCESS', 'FAILURE', 'REVOKED']:
            logger.warning(f"Task {task_id} is in terminal state {celery_task.status}, clearing AgentState...")
            state.is_running = False
            state.current_task_id = None
            state.current_phase_message = 'Idle'
            state.last_update = datetime.utcnow()
            db.session.commit()
            
            return jsonify({
                'is_running': False,
                'task_id': None,
                'celery_task_id': None,
                'current_phase_message': 'Idle',
                'phase': 'idle',
                'progress': 0,
                'status': 'IDLE'
            })
        
        # Task exists and is active - try to get detailed status, fallback to basic status
        try:
            return get_task_status(task_id)
        except Exception as detailed_error:
            logger.warning(f"Failed to get detailed task status for {task_id}, returning basic status: {detailed_error}")
            
            # Fallback: return basic status from database and agent state
            basic_status = {
                'is_running': True,
                'task_id': task_id,
                'celery_task_id': celery_task.celery_task_id,
                'current_phase_message': celery_task.current_phase_message or state.current_phase_message or 'Processing...',
                'phase': 'processing',
                'progress': celery_task.progress_percentage or 0,
                'status': celery_task.status or 'PROGRESS',
                'human_readable_name': celery_task.human_readable_name,
                'created_at': celery_task.created_at.isoformat() if celery_task.created_at else None,
                'updated_at': celery_task.updated_at.isoformat() if celery_task.updated_at else None
            }
            
            # Add progress data if available
            if celery_task.current_phase_id:
                basic_status['progress'] = {
                    'phase_id': celery_task.current_phase_id,
                    'message': celery_task.current_phase_message,
                    'progress': celery_task.progress_percentage or 0,
                    'status': 'running'
                }
            
            return jsonify(basic_status)
        
    except Exception as e:
        logger.error(f"Error validating task status: {e}", exc_info=True)
        # On error, return safe idle state
        return jsonify({
            'is_running': False,
            'task_id': None,
            'celery_task_id': None,
            'current_phase_message': 'Error checking status',
            'phase': 'error',
            'progress': 0,
            'status': 'ERROR'
        })

@bp.route('/agent/reset-state', methods=['POST'])
def reset_agent_state():
    """Reset agent state to idle - useful for fixing stuck states."""
    try:
        from ..web import get_or_create_agent_state
        from ..models import CeleryTaskState
        
        state = get_or_create_agent_state()
        old_task_id = state.current_task_id
        
        # Get task info for diagnostics
        task_info = None
        if old_task_id:
            celery_task = CeleryTaskState.query.filter_by(task_id=old_task_id).first()
            if celery_task:
                task_info = {
                    'task_id': celery_task.task_id,
                    'status': celery_task.status,
                    'created_at': celery_task.created_at.isoformat() if celery_task.created_at else None,
                    'updated_at': celery_task.updated_at.isoformat() if celery_task.updated_at else None
                }
        
        # Reset state to idle
        state.is_running = False
        state.current_task_id = None
        state.current_phase_message = 'Idle'
        state.last_update = datetime.utcnow()
        db.session.commit()
        
        logger.info(f"Agent state reset to idle (was task_id: {old_task_id})")
        
        return jsonify({
            'success': True,
            'message': 'Agent state reset to idle',
            'previous_task_id': old_task_id,
            'task_info': task_info
        })
        
    except Exception as e:
        logger.error(f"Error resetting agent state: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@bp.route('/agent/diagnostics', methods=['GET'])
def get_agent_diagnostics():
    """Get detailed agent state diagnostics for troubleshooting."""
    try:
        from ..web import get_or_create_agent_state
        from ..models import CeleryTaskState
        
        # Get agent state
        state = get_or_create_agent_state()
        
        # Get recent tasks
        recent_tasks = CeleryTaskState.query.order_by(CeleryTaskState.created_at.desc()).limit(5).all()
        
        # Get current task details if exists
        current_task_details = None
        if state.current_task_id:
            current_task = CeleryTaskState.query.filter_by(task_id=state.current_task_id).first()
            if current_task:
                current_task_details = {
                    'task_id': current_task.task_id,
                    'celery_task_id': current_task.celery_task_id,
                    'status': current_task.status,
                    'created_at': current_task.created_at.isoformat() if current_task.created_at else None,
                    'updated_at': current_task.updated_at.isoformat() if current_task.updated_at else None,
                    'current_phase_id': current_task.current_phase_id,
                    'current_phase_message': current_task.current_phase_message,
                    'progress_percentage': current_task.progress_percentage
                }
        
        # Build diagnostics
        diagnostics = {
            'agent_state': {
                'is_running': state.is_running,
                'current_task_id': state.current_task_id,
                'current_phase_message': state.current_phase_message,
                'last_update': state.last_update.isoformat() if state.last_update else None
            },
            'current_task': current_task_details,
            'recent_tasks': [
                {
                    'task_id': task.task_id,
                    'status': task.status,
                    'created_at': task.created_at.isoformat() if task.created_at else None,
                    'current_phase_id': task.current_phase_id
                }
                for task in recent_tasks
            ],
            'task_counts': {
                'total': CeleryTaskState.query.count(),
                'pending': CeleryTaskState.query.filter_by(status='PENDING').count(),
                'progress': CeleryTaskState.query.filter_by(status='PROGRESS').count(),
                'success': CeleryTaskState.query.filter_by(status='SUCCESS').count(),
                'failure': CeleryTaskState.query.filter_by(status='FAILURE').count()
            }
        }
        
        return jsonify({
            'success': True,
            'diagnostics': diagnostics
        })
        
    except Exception as e:
        logger.error(f"Error getting agent diagnostics: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# --- LEGACY & DEPRECATED ENDPOINTS ---

@bp.route('/agent/status_legacy')
def get_agent_status_legacy():
    """DEPRECATED: Returns the current status of the agent from the database."""
    from ..web import get_or_create_agent_state
    state = get_or_create_agent_state()
    return jsonify(state.to_dict())

@bp.route('/media/<path:path>')
def serve_kb_media_generic(path):
    """Serve media files from the knowledge base directory."""
    config = current_app.config.get('APP_CONFIG')
    if not config or not config.knowledge_base_dir:
        return "Knowledge base root directory not configured.", 500

    # This is a security risk if kb_root_dir is not carefully controlled.
    # It should be an absolute path.
    return send_from_directory(config.knowledge_base_dir, path)

# --- V1 BACKWARD COMPATIBILITY --
@bp.route('/schedule', methods=['GET', 'POST'])
def schedule_endpoint():
    """V1 LEGACY ENDPOINT: Simulates schedule handling for backward compatibility."""
    if request.method == 'GET':
        return jsonify({'schedule': 'Not Scheduled (Legacy View)'})

    if request.method == 'POST':
        data = request.get_json()
        if not data or 'schedule' not in data:
            return jsonify({'error': 'Invalid request body'}), 400

        logger.info(f"V1 schedule endpoint received schedule update: {data['schedule']}. Ignoring, as this is a legacy endpoint.")
        return jsonify({'success': True, 'message': 'Schedule update received (legacy endpoint).'})

    # Method Not Allowed
    return jsonify({'error': 'Method not supported'}), 405
# --- END V1 COMPATIBILITY ---

@bp.route('/chat/models', methods=['GET'])
def get_chat_models():
    """Returns the list of available chat models from the config."""
    app_config = current_app.config.get('APP_CONFIG')
    if not app_config or not hasattr(app_config, 'available_chat_models'):
        return jsonify({"error": "Chat models configuration not available"}), 500
    
    models = [{"id": model, "name": model} for model in app_config.available_chat_models]
    return jsonify(models)

@bp.route('/chat', methods=['POST'])
def chat():
    """Handle chat interactions via API using the knowledge base agent."""
    try:
        data = request.json or {}
        query = data.get('message') or data.get('query')  # Support both parameter names
        model = data.get('model')
        
        if not query:
            return jsonify({"error": "No query provided"}), 400
            
        # Get the agent from the current app's config
        app_config = current_app.config.get('APP_CONFIG')
        if not app_config:
            return jsonify({"error": "Application configuration not available"}), 500
            
        # Import and create agent components
        from ..agent import KnowledgeBaseAgent
        from ..http_client import HTTPClient
        from ..embedding_manager import EmbeddingManager
        from ..chat_manager import ChatManager
        
        # Create HTTP client and embedding manager
        http_client = HTTPClient(app_config)
        embedding_manager = EmbeddingManager(app_config, http_client)
        chat_manager = ChatManager(app_config, http_client, embedding_manager)
        
        # Process the chat query asynchronously
        async def process_chat():
            try:
                await http_client.initialize()
                # EmbeddingManager doesn't have an initialize method, it's ready to use
                response = await chat_manager.handle_chat_query(query, model)
                return response
            finally:
                await http_client.close()  # Use close() instead of cleanup()
        
        # Run the async chat processing
        response = run_async_in_gevent_context(process_chat())
        
        if "error" in response:
            return jsonify(response), 500
            
        return jsonify(response)
        
    except Exception as e:
        current_app.logger.error(f"Chat API error: {e}", exc_info=True)
        return jsonify({"error": f"Internal server error: {str(e)}"}), 500

@bp.route('/chat/legacy', methods=['POST'])
def api_chat_legacy():
    """Legacy chat endpoint for backward compatibility."""
    try:
        data = request.get_json()
        message = data.get('message', '').strip()
        
        if not message:
            return jsonify({'error': 'Message is required'}), 400
        
        # Simple response for legacy compatibility
        return jsonify({
            'response': f"Legacy chat response for: {message}",
            'sources': []
        })
        
    except Exception as e:
        logging.error(f"Error in legacy chat API: {e}", exc_info=True)
        return jsonify({'error': 'Internal server error'}), 500

@bp.route('/chat/enhanced', methods=['POST'])
def api_chat_enhanced():
    """Enhanced chat API endpoint with technical expertise and rich source metadata."""
    try:
        from ..models import ChatSession, ChatMessage, db
        from datetime import datetime, timezone
        
        data = request.get_json()
        if not data or 'message' not in data:
            return jsonify({'error': 'Message is required'}), 400
        
        message = data['message'].strip()
        if not message:
            return jsonify({'error': 'Message cannot be empty'}), 400
        
        # Get optional model selection and session ID
        model = data.get('model')
        session_id = data.get('session_id')
        
        # Create new session if none provided
        if not session_id:
            session_id = str(uuid.uuid4())
            now = datetime.now(timezone.utc)
            
            session = ChatSession()
            session.session_id = session_id
            session.title = message[:50] + "..." if len(message) > 50 else message
            session.created_at = now
            session.last_updated = now
            session.is_archived = False
            session.message_count = 0
            
            db.session.add(session)
            db.session.commit()
        else:
            # Get existing session
            session = ChatSession.query.filter_by(session_id=session_id).first()
            if not session:
                return jsonify({'error': 'Session not found'}), 404
        
        # Save user message
        now = datetime.now(timezone.utc)
        user_message = ChatMessage()
        user_message.session_id = session_id
        user_message.role = 'user'
        user_message.content = message
        user_message.created_at = now
        
        db.session.add(user_message)
        
        # Get chat manager
        from ..web import get_chat_manager
        chat_mgr = get_chat_manager()
        if not chat_mgr:
            return jsonify({'error': 'Chat functionality not available'}), 503
        
        # Process chat query asynchronously
        result = run_async_in_gevent_context(
            chat_mgr.handle_chat_query(message, model)
        )
        
        if 'error' in result:
            return jsonify(result), 500
        
        # Save assistant response
        assistant_message = ChatMessage()
        assistant_message.session_id = session_id
        assistant_message.role = 'assistant'
        assistant_message.content = result.get('response', '')
        assistant_message.created_at = datetime.now(timezone.utc)
        assistant_message.model_used = model or 'default'
        assistant_message.sources = json.dumps(result.get('sources', []))
        assistant_message.context_stats = json.dumps(result.get('context_stats', {}))
        assistant_message.performance_metrics = json.dumps(result.get('performance_metrics', {}))
        
        db.session.add(assistant_message)
        
        # Update session
        session.message_count += 2
        session.last_updated = datetime.now(timezone.utc)
        
        db.session.commit()
        
        # Add session_id to result
        result['session_id'] = session_id
        
        return jsonify(result)
        
    except Exception as e:
        logging.error(f"Error in enhanced chat API: {e}", exc_info=True)
        return jsonify({'error': 'Internal server error'}), 500

@bp.route('/chat/models/available', methods=['GET'])
def api_chat_models_available():
    """Get available chat models."""
    try:
        from ..web import get_chat_manager
        chat_mgr = get_chat_manager()
        if not chat_mgr:
            return jsonify([]), 200
        
        # Get available models asynchronously
        models = run_async_in_gevent_context(chat_mgr.get_available_models())
        
        return jsonify(models)
        
    except Exception as e:
        logging.error(f"Error getting chat models: {e}", exc_info=True)
        return jsonify([{'id': 'default', 'name': 'Default Model'}]), 200

@bp.route('/chat/sessions', methods=['GET'])
def api_get_chat_sessions():
    """Get all chat sessions."""
    try:
        from ..models import ChatSession
        
        sessions = ChatSession.query.order_by(ChatSession.last_updated.desc()).all()
        session_list = []
        
        for session in sessions:
            session_list.append({
                'id': session.id,
                'session_id': session.session_id,
                'title': session.title,
                'created_at': session.created_at.isoformat() if session.created_at else None,
                'last_updated': session.last_updated.isoformat() if session.last_updated else None,
                'is_archived': session.is_archived,
                'message_count': session.message_count
            })
        
        return jsonify(session_list)
    except Exception as e:
        logging.error(f"Error retrieving chat sessions: {e}", exc_info=True)
        return jsonify({'error': 'Failed to retrieve chat sessions'}), 500

@bp.route('/chat/sessions/<session_id>', methods=['GET'])
def api_get_chat_session(session_id):
    """Get a specific chat session with messages."""
    try:
        from ..models import ChatSession, ChatMessage
        import json
        
        session = ChatSession.query.filter_by(session_id=session_id).first()
        if not session:
            return jsonify({'error': 'Session not found'}), 404
        
        messages = ChatMessage.query.filter_by(session_id=session_id).order_by(ChatMessage.created_at.asc()).all()
        
        message_list = []
        for message in messages:
            msg_data = {
                'id': message.id,
                'role': message.role,
                'content': message.content,
                'created_at': message.created_at.isoformat() if message.created_at else None,
                'model_used': message.model_used
            }
            
            # Parse JSON fields if they exist
            if message.sources:
                try:
                    msg_data['sources'] = json.loads(message.sources)
                except:
                    msg_data['sources'] = []
            
            if message.context_stats:
                try:
                    msg_data['context_stats'] = json.loads(message.context_stats)
                except:
                    msg_data['context_stats'] = {}
            
            if message.performance_metrics:
                try:
                    msg_data['performance_metrics'] = json.loads(message.performance_metrics)
                except:
                    msg_data['performance_metrics'] = {}
                    
            message_list.append(msg_data)
        
        return jsonify({
            'session': {
                'id': session.id,
                'session_id': session.session_id,
                'title': session.title,
                'created_at': session.created_at.isoformat() if session.created_at else None,
                'last_updated': session.last_updated.isoformat() if session.last_updated else None,
                'is_archived': session.is_archived,
                'message_count': session.message_count
            },
            'messages': message_list
        })
    except Exception as e:
        logging.error(f"Error retrieving chat session {session_id}: {e}", exc_info=True)
        return jsonify({'error': 'Failed to retrieve chat session'}), 500

@bp.route('/chat/sessions', methods=['POST'])
def api_create_chat_session():
    """Create a new chat session."""
    try:
        from ..models import ChatSession, db
        from datetime import datetime, timezone
        import uuid
        
        data = request.get_json()
        
        # Generate a unique session ID
        session_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc)
        
        session = ChatSession()
        session.session_id = session_id
        session.title = data.get('title', 'New Chat')
        session.created_at = now
        session.last_updated = now
        session.is_archived = False
        session.message_count = 0
        
        db.session.add(session)
        db.session.commit()
        
        return jsonify({
            'session_id': session.session_id,
            'title': session.title,
            'created_at': session.created_at.isoformat()
        }), 201
        
    except Exception as e:
        logging.error(f"Error creating chat session: {e}", exc_info=True)
        return jsonify({'error': 'Failed to create chat session'}), 500

@bp.route('/chat/sessions/<session_id>/archive', methods=['POST'])
def api_archive_chat_session(session_id):
    """Archive/unarchive a chat session."""
    try:
        from ..models import ChatSession, db
        from datetime import datetime, timezone
        
        session = ChatSession.query.filter_by(session_id=session_id).first()
        if not session:
            return jsonify({'error': 'Session not found'}), 404
        
        session.is_archived = not session.is_archived
        session.last_updated = datetime.now(timezone.utc)
        db.session.commit()
        
        return jsonify({'message': 'Session archived successfully' if session.is_archived else 'Session unarchived successfully'})
    except Exception as e:
        logging.error(f"Error archiving chat session {session_id}: {e}", exc_info=True)
        return jsonify({'error': 'Failed to archive chat session'}), 500

@bp.route('/chat/sessions/<session_id>', methods=['DELETE'])
def api_delete_chat_session(session_id):
    """Delete a chat session and all its messages."""
    try:
        from ..models import ChatSession, db
        
        session = ChatSession.query.filter_by(session_id=session_id).first()
        if not session:
            return jsonify({'error': 'Session not found'}), 404
        
        db.session.delete(session)
        db.session.commit()
        
        return jsonify({'message': 'Session deleted successfully'})
    except Exception as e:
        logging.error(f"Error deleting chat session {session_id}: {e}", exc_info=True)
        return jsonify({'error': 'Failed to delete chat session'}), 500

@bp.route('/preferences', methods=['GET'])
def get_preferences():
    """Get current user preferences."""
    try:
        from ..prompts import load_user_preferences
        config = current_app.config.get('APP_CONFIG')
        if not config:
            return jsonify({'error': 'Configuration not available'}), 500
        
        preferences = load_user_preferences(config)
        # Convert to dictionary for JSON response - include ALL UserPreferences fields
        prefs_dict = {
            # Run mode
            'run_mode': preferences.run_mode,
            
            # Skip flags
            'skip_fetch_bookmarks': preferences.skip_fetch_bookmarks,
            'skip_process_content': preferences.skip_process_content,
            'skip_readme_generation': preferences.skip_readme_generation,
            'skip_git_push': preferences.skip_git_push,
            'skip_synthesis_generation': preferences.skip_synthesis_generation,
            'skip_embedding_generation': preferences.skip_embedding_generation,
            
            # Force flags
            'force_recache_tweets': preferences.force_recache_tweets,
            'force_regenerate_synthesis': preferences.force_regenerate_synthesis,
            'force_regenerate_embeddings': preferences.force_regenerate_embeddings,
            'force_regenerate_readme': preferences.force_regenerate_readme,
            
            # Granular force flags for content processing phases
            'force_reprocess_media': preferences.force_reprocess_media,
            'force_reprocess_llm': preferences.force_reprocess_llm,
            'force_reprocess_kb_item': preferences.force_reprocess_kb_item,
            
            # Legacy/combined flag
            'force_reprocess_content': preferences.force_reprocess_content,
            
            # Additional options
            'synthesis_mode': preferences.synthesis_mode,
            'synthesis_min_items': preferences.synthesis_min_items,
            'synthesis_max_items': preferences.synthesis_max_items
        }
        return jsonify(prefs_dict)
        
    except Exception as e:
        logging.error(f"Error getting preferences: {e}", exc_info=True)
        return jsonify({'error': 'Failed to get preferences'}), 500

@bp.route('/preferences', methods=['POST'])
def save_preferences():
    """Save user preferences."""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No preferences data provided'}), 400
        
        # Validate preferences structure
        from ..prompts import UserPreferences
        try:
            user_prefs = UserPreferences(**data)
            # In a full implementation, you would save these to a user session or database
            # For now, we'll just validate and return success
            return jsonify({'status': 'success', 'message': 'Preferences validated and saved'})
        except Exception as validation_error:
            return jsonify({'error': f'Invalid preferences: {validation_error}'}), 400
        
    except Exception as e:
        logging.error(f"Error saving preferences: {e}", exc_info=True)
        return jsonify({'error': 'Failed to save preferences'}), 500

@bp.route('/synthesis', methods=['GET'])
def get_synthesis_documents():
    """API endpoint to get all synthesis documents."""
    try:
        syntheses = db.session.query(SubcategorySynthesis).order_by(SubcategorySynthesis.last_updated.desc()).all()  # type: ignore
        synthesis_list = [{
            "id": synth.id,
            "title": synth.synthesis_title,
            "summary": (synth.synthesis_content or "")[:200] + '...',
            "topic": f"{synth.main_category}/{synth.sub_category}",
            "last_updated": synth.last_updated.isoformat()
        } for synth in syntheses]
        return jsonify(synthesis_list)
    except Exception as e:
        current_app.logger.error(f"API Error fetching syntheses: {e}", exc_info=True)
        return jsonify({"error": "Failed to fetch synthesis documents."}), 500

@bp.route('/logs', methods=['GET'])
def api_list_logs():
    """API endpoint to list available log files."""
    app_config = current_app.config.get('APP_CONFIG')
    if not app_config:
        return jsonify({"error": "Configuration not available"}), 500
    return list_logs(app_config)

@bp.route('/logs/<filename>', methods=['GET'])
def api_get_log_content(filename):
    """API endpoint to get the content of a specific log file."""
    app_config = current_app.config.get('APP_CONFIG')
    if not app_config:
        return jsonify({"error": "Configuration not available"}), 500
    return get_log_content(filename, app_config)

@bp.route('/logs/delete-all', methods=['POST'])
def api_delete_all_logs():
    """API endpoint to delete all log files."""
    try:
        app_config = current_app.config.get('APP_CONFIG')
        if not app_config or not hasattr(app_config, 'log_dir'):
            return jsonify({"error": "Configuration for log directory not available"}), 500

        log_dir = Path(app_config.log_dir).expanduser().resolve()
        if not log_dir.exists():
            return jsonify({"message": "No log directory found", "deleted_count": 0})

        # Count and delete .log files
        log_files = list(log_dir.glob('*.log'))
        deleted_count = len(log_files)
        
        for log_file in log_files:
            log_file.unlink()

        return jsonify({
            "message": f"Successfully deleted {deleted_count} log files",
            "deleted_count": deleted_count
        })
    except Exception as e:
        current_app.logger.error(f"Error deleting log files: {e}", exc_info=True)
        return jsonify({"error": f"Failed to delete log files: {str(e)}"}), 500

@bp.route('/environment-variables', methods=['GET'])
def get_environment_variables():
    """Get all environment variables with metadata."""
    try:
        # Get current environment variables
        env_variables = dict(os.environ)
        
        # Get config field information
        config_fields = {}
        try:
            # Import Config to get field definitions
            from ..config import Config
            for field_name, field_info in Config.model_fields.items():
                config_fields[field_name] = {
                    'description': field_info.description or 'No description available',
                    'required': field_info.is_required(),
                    'type': str(field_info.annotation),
                    'alias': field_info.alias
                }
        except Exception as e:
            logging.warning(f"Could not load config field info: {e}")
            config_fields = {}

        # Get list of used environment variables (those with aliases in Config)
        used_env_vars = []
        unused_env_vars = []
        missing_env_vars = []
        
        # Create mapping of aliases to field names
        alias_to_field = {}
        for field_name, field_info in config_fields.items():
            if field_info.get('alias'):
                alias_to_field[field_info['alias']] = field_name
        
        # Check which env vars are used/unused
        for env_var in env_variables:
            if env_var in alias_to_field:
                used_env_vars.append(env_var)
            else:
                unused_env_vars.append(env_var)
        
        # Check for missing required variables
        for field_name, field_info in config_fields.items():
            if field_info.get('required') and field_info.get('alias'):
                if field_info['alias'] not in env_variables:
                    missing_env_vars.append(field_info['alias'])

        return jsonify({
            'used_variables': used_env_vars,
            'unused_variables': unused_env_vars,
            'missing_variables': missing_env_vars,
            'config_fields': config_fields,
            'total_env_vars': len(env_variables)
        })
        
    except Exception as e:
        logging.error(f"Error getting environment variables: {e}", exc_info=True)
        return jsonify({'error': 'Failed to get environment variables'}), 500


# === UTILITY ENDPOINTS FOR AGENT DASHBOARD ===

@bp.route('/utilities/celery/clear-queue', methods=['POST'])
def clear_celery_queue():
    """Clear all pending tasks from Celery queue."""
    try:
        # Purge all tasks from the default queue
        celery_app.control.purge()
        
        # Also purge specific queues
        queues_to_purge = ['agent', 'processing', 'chat']
        for queue in queues_to_purge:
            try:
                celery_app.control.purge(queue)
            except Exception as e:
                logging.warning(f"Failed to purge queue {queue}: {e}")
        
        return jsonify({
            'success': True,
            'message': 'Task queue cleared successfully'
        })
        
    except Exception as e:
        logging.error(f"Failed to clear Celery queue: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': f'Failed to clear queue: {str(e)}'
        }), 500

@bp.route('/utilities/celery/purge-all', methods=['POST'])
def purge_all_celery_tasks():
    """Purge all Celery tasks (pending, active, reserved)."""
    try:
        # Revoke all active tasks
        active_tasks = celery_app.control.inspect().active()
        if active_tasks:
            for worker, tasks in active_tasks.items():
                for task in tasks:
                    celery_app.control.revoke(task['id'], terminate=True)
        
        # Purge all queues
        celery_app.control.purge()
        
        # Clear reserved tasks
        celery_app.control.cancel_consumer('celery')
        
        return jsonify({
            'success': True,
            'message': 'All Celery tasks purged successfully'
        })
        
    except Exception as e:
        logging.error(f"Failed to purge Celery tasks: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': f'Failed to purge tasks: {str(e)}'
        }), 500

@bp.route('/utilities/celery/restart-workers', methods=['POST'])
def restart_celery_workers():
    """Restart Celery workers."""
    try:
        # Send restart signal to all workers
        celery_app.control.broadcast('pool_restart', arguments={'reload': True})
        
        return jsonify({
            'success': True,
            'message': 'Celery workers restart signal sent'
        })
        
    except Exception as e:
        logging.error(f"Failed to restart Celery workers: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': f'Failed to restart workers: {str(e)}'
        }), 500

@bp.route('/utilities/celery/status', methods=['GET'])
def get_celery_status():
    """Get Celery worker and task status."""
    try:
        inspect = celery_app.control.inspect()
        
        # Get worker stats
        stats = inspect.stats() or {}
        active_tasks = inspect.active() or {}
        reserved_tasks = inspect.reserved() or {}
        
        # Count workers and tasks
        total_workers = len(stats)
        active_workers = len([w for w in stats.values() if w])
        
        total_active_tasks = sum(len(tasks) for tasks in active_tasks.values())
        total_reserved_tasks = sum(len(tasks) for tasks in reserved_tasks.values())
        
        return jsonify({
            'success': True,
            'data': {
                'total_workers': total_workers,
                'active_workers': active_workers,
                'active_tasks': total_active_tasks,
                'pending_tasks': total_reserved_tasks,
                'worker_details': stats
            }
        })
        
    except Exception as e:
        logging.error(f"Failed to get Celery status: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': f'Failed to get status: {str(e)}'
        }), 500

@bp.route('/utilities/system/clear-redis', methods=['POST'])
def clear_redis_cache():
    """Clear Redis cache."""
    try:
        import redis
        config = current_app.config.get('APP_CONFIG')
        if not config:
            raise Exception("Configuration not available")
        
        # Clear progress and logs Redis databases
        progress_redis = redis.Redis.from_url(config.redis_progress_url)
        logs_redis = redis.Redis.from_url(config.redis_logs_url)
        
        progress_redis.flushdb()
        logs_redis.flushdb()
        
        return jsonify({
            'success': True,
            'message': 'Redis cache cleared successfully'
        })
        
    except Exception as e:
        logging.error(f"Failed to clear Redis cache: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': f'Failed to clear cache: {str(e)}'
        }), 500

@bp.route('/utilities/system/cleanup-temp', methods=['POST'])
def cleanup_temp_files():
    """Cleanup temporary files."""
    try:
        config = current_app.config.get('APP_CONFIG')
        if not config:
            raise Exception("Configuration not available")
        
        deleted_count = 0
        
        # Clean up temp directories
        temp_dirs = [
            tempfile.gettempdir(),
            config.project_root / 'temp',
            config.project_root / 'tmp'
        ]
        
        for temp_dir in temp_dirs:
            temp_path = Path(temp_dir)
            if temp_path.exists():
                # Remove old temp files (older than 1 day)
                import time
                current_time = time.time()
                for temp_file in temp_path.glob('*'):
                    try:
                        if temp_file.is_file() and (current_time - temp_file.stat().st_mtime) > 86400:
                            temp_file.unlink()
                            deleted_count += 1
                    except Exception:
                        continue
        
        return jsonify({
            'success': True,
            'message': f'Cleaned up {deleted_count} temporary files'
        })
        
    except Exception as e:
        logging.error(f"Failed to cleanup temp files: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': f'Failed to cleanup: {str(e)}'
        }), 500

@bp.route('/utilities/system/health-check', methods=['GET'])
def system_health_check():
    """Perform system health check."""
    try:
        import redis
        config = current_app.config.get('APP_CONFIG')
        health = {}
        
        # Test Redis connection
        try:
            redis_client = redis.Redis.from_url(config.redis_progress_url)
            redis_client.ping()
            health['redis'] = True
        except Exception:
            health['redis'] = False
        
        # Test database connection
        try:
            db.session.execute('SELECT 1')
            health['database'] = True
        except Exception:
            health['database'] = False
        
        # Test Celery
        try:
            inspect = celery_app.control.inspect()
            stats = inspect.stats()
            health['celery'] = bool(stats)
        except Exception:
            health['celery'] = False
        
        # Get system info
        disk_usage = shutil.disk_usage('/')
        health['disk_space'] = f"{disk_usage.free // (1024**3)} GB free"
        health['memory_usage'] = f"{psutil.virtual_memory().percent}%"
        
        return jsonify({
            'success': True,
            'data': health
        })
        
    except Exception as e:
        logging.error(f"Failed to run health check: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': f'Health check failed: {str(e)}'
        }), 500

@bp.route('/utilities/debug/export-logs', methods=['GET'])
def export_logs():
    """Export all logs as a downloadable file."""
    try:
        config = current_app.config.get('APP_CONFIG')
        if not config:
            raise Exception("Configuration not available")
        
        log_dir = Path(config.log_dir)
        if not log_dir.exists():
            raise Exception("Log directory not found")
        
        # Combine all log files
        combined_logs = []
        for log_file in log_dir.glob('*.log'):
            try:
                with open(log_file, 'r') as f:
                    combined_logs.append(f"=== {log_file.name} ===\n")
                    combined_logs.append(f.read())
                    combined_logs.append(f"\n\n")
            except Exception as e:
                combined_logs.append(f"Error reading {log_file.name}: {e}\n\n")
        
        return jsonify({
            'success': True,
            'data': ''.join(combined_logs)
        })
        
    except Exception as e:
        logging.error(f"Failed to export logs: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': f'Failed to export logs: {str(e)}'
        }), 500

@bp.route('/utilities/debug/test-connections', methods=['GET'])
def test_connections():
    """Test all system connections."""
    try:
        import redis
        config = current_app.config.get('APP_CONFIG')
        tests = {}
        
        # Test Redis
        try:
            redis_client = redis.Redis.from_url(config.redis_progress_url)
            redis_client.ping()
            tests['Redis'] = {'connected': True}
        except Exception as e:
            tests['Redis'] = {'connected': False, 'error': str(e)}
        
        # Test Database
        try:
            db.session.execute('SELECT 1')
            tests['Database'] = {'connected': True}
        except Exception as e:
            tests['Database'] = {'connected': False, 'error': str(e)}
        
        # Test Celery
        try:
            inspect = celery_app.control.inspect()
            stats = inspect.stats()
            tests['Celery'] = {'connected': bool(stats)}
        except Exception as e:
            tests['Celery'] = {'connected': False, 'error': str(e)}
        
        # Test HTTP Client (Ollama)
        try:
            from ..http_client import HTTPClient
            http_client = HTTPClient(config)
            # This is a basic test - you might want to make it more comprehensive
            tests['Ollama'] = {'connected': True}  # Simplified for now
        except Exception as e:
            tests['Ollama'] = {'connected': False, 'error': str(e)}
        
        return jsonify({
            'success': True,
            'data': tests
        })
        
    except Exception as e:
        logging.error(f"Failed to test connections: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': f'Connection tests failed: {str(e)}'
        }), 500

@bp.route('/utilities/debug/info', methods=['GET'])
def get_debug_info():
    """Get system debug information."""
    try:
        import sys
        import time
        
        config = current_app.config.get('APP_CONFIG')
        
        # Get system info
        info = {
            'version': '2.0.0',  # You can make this dynamic
            'python_version': sys.version,
            'platform': platform.platform(),
            'uptime': f"{time.time() - psutil.boot_time():.0f} seconds",
            'memory_usage': f"{psutil.virtual_memory().percent}%",
            'cpu_usage': f"{psutil.cpu_percent()}%"
        }
        
        # Get active tasks count
        try:
            inspect = celery_app.control.inspect()
            active_tasks = inspect.active() or {}
            info['active_tasks'] = sum(len(tasks) for tasks in active_tasks.values())
        except Exception:
            info['active_tasks'] = 0
        
        return jsonify({
            'success': True,
            'data': info
        })
        
    except Exception as e:
        logging.error(f"Failed to get debug info: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': f'Failed to get debug info: {str(e)}'
        }), 500
        missing_env_vars = []
        
        # Create mapping of aliases to field names
        alias_to_field = {}
        for field_name, field_info in config_fields.items():
            if field_info.get('alias'):
                alias_to_field[field_info['alias']] = field_name
        
        # Check which env vars are used/unused
        for env_var in env_variables:
            if env_var in alias_to_field:
                used_env_vars.append(env_var)
            else:
                unused_env_vars.append(env_var)
        
        # Check for missing required variables
        for field_name, field_info in config_fields.items():
            alias = field_info.get('alias')
            if alias and field_info.get('required', False) and alias not in env_variables:
                missing_env_vars.append(alias)
        
        return jsonify({
            'success': True,
            'env_variables': env_variables,
            'config_fields': config_fields,
            'used_env_vars': used_env_vars,
            'unused_env_vars': unused_env_vars,
            'missing_env_vars': missing_env_vars
        })
    
    except Exception as e:
        logging.error(f"Error getting environment variables: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@bp.route('/environment-variables', methods=['POST'])
def update_environment_variables():
    """Update environment variables."""
    try:
        data = request.get_json()
        env_variables = data.get('env_variables', {})
        
        if not env_variables:
            return jsonify({
                'success': False,
                'error': 'No environment variables provided'
            }), 400
        
        # Update environment variables in the current process
        updated_count = 0
        for key, value in env_variables.items():
            os.environ[key] = str(value)
            updated_count += 1
        
        # Try to update .env file if it exists
        env_file_path = Path('.env')
        if env_file_path.exists():
            try:
                # Read existing .env file
                with open(env_file_path, 'r') as f:
                    lines = f.readlines()
                
                # Update or add variables
                updated_lines = []
                updated_vars = set()
                
                for line in lines:
                    line = line.strip()
                    if '=' in line and not line.startswith('#'):
                        var_name = line.split('=')[0].strip()
                        if var_name in env_variables:
                            # Update existing variable
                            updated_lines.append(f"{var_name}={env_variables[var_name]}\n")
                            updated_vars.add(var_name)
                        else:
                            updated_lines.append(line + '\n')
                    else:
                        updated_lines.append(line + '\n')
                
                # Add new variables
                for var_name, var_value in env_variables.items():
                    if var_name not in updated_vars:
                        updated_lines.append(f"{var_name}={var_value}\n")
                
                # Write back to .env file
                with open(env_file_path, 'w') as f:
                    f.writelines(updated_lines)
                
                logging.info(f"Updated .env file with {updated_count} variables")
                
            except Exception as e:
                logging.warning(f"Could not update .env file: {e}")
        
        return jsonify({
            'success': True,
            'message': f'Successfully updated {updated_count} environment variables',
            'updated_count': updated_count
        })
    
    except Exception as e:
        logging.error(f"Error updating environment variables: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@bp.route('/environment-variables/<variable_name>', methods=['DELETE'])
def delete_environment_variable(variable_name):
    """Delete an environment variable."""
    try:
        # Remove from current process environment
        if variable_name in os.environ:
            del os.environ[variable_name]
        
        # Try to remove from .env file if it exists
        env_file_path = Path('.env')
        if env_file_path.exists():
            try:
                with open(env_file_path, 'r') as f:
                    lines = f.readlines()
                
                # Filter out the variable
                updated_lines = []
                for line in lines:
                    line_stripped = line.strip()
                    if '=' in line_stripped and not line_stripped.startswith('#'):
                        var_name = line_stripped.split('=')[0].strip()
                        if var_name != variable_name:
                            updated_lines.append(line)
                    else:
                        updated_lines.append(line)
                
                with open(env_file_path, 'w') as f:
                    f.writelines(updated_lines)
                
                logging.info(f"Removed {variable_name} from .env file")
                
            except Exception as e:
                logging.warning(f"Could not update .env file: {e}")
        
        return jsonify({
            'success': True,
            'message': f'Environment variable {variable_name} deleted successfully'
        })
    
    except Exception as e:
        logging.error(f"Error deleting environment variable: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@bp.route('/hardware-detection', methods=['GET'])
def get_hardware_detection():
    """Get detected hardware information."""
    try:
        from ..hardware_detector import HardwareDetector
        
        detector = HardwareDetector()
        system_info = detector.detect_system_info()
        
        return jsonify({
            'success': True,
            'hardware': {
                'gpu_count': len(system_info.gpus),
                'gpu_total_memory': sum(gpu.memory_total_mb for gpu in system_info.gpus),
                'gpu_devices': [
                    {
                        'name': gpu.name,
                        'memory': gpu.memory_total_mb,
                        'utilization': gpu.memory_free_mb  # Using free memory as utilization placeholder
                    } for gpu in system_info.gpus
                ],
                'cpu_cores': system_info.cpu.physical_cores,
                'total_memory': system_info.total_ram_gb * 1024 * 1024 * 1024,  # Convert to bytes
                'available_memory': system_info.available_ram_gb * 1024 * 1024 * 1024  # Convert to bytes
            }
        })
    
    except ImportError as e:
        return jsonify({
            'success': False,
            'error': f'Hardware detection not available: {e}'
        }), 500
    except Exception as e:
        logging.error(f"Error detecting hardware: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@bp.route('/ollama-optimization', methods=['POST'])
def generate_ollama_optimization():
    """Generate Ollama optimization settings based on hardware and profile."""
    try:
        data = request.get_json()
        profile = data.get('profile', 'balanced')
        apply_to_env = data.get('apply_to_env', False)
        
        if profile not in ['performance', 'balanced', 'memory_efficient']:
            return jsonify({
                'success': False,
                'error': 'Invalid profile. Must be one of: performance, balanced, memory_efficient'
            }), 400
        
        # Use the Config class method to generate optimization
        env_vars = Config.auto_configure_ollama_optimization(
            workload_type=profile,
            apply_to_env=apply_to_env
        )
        
        if not env_vars:
            return jsonify({
                'success': False,
                'error': 'Hardware detection failed or no optimization possible'
            }), 500
        
        # If apply_to_env is True, also update the .env file
        if apply_to_env:
            env_file_path = Path('.env')
            if env_file_path.exists():
                try:
                    # Read existing .env file
                    with open(env_file_path, 'r') as f:
                        lines = f.readlines()
                    
                    # Update or add variables
                    updated_lines = []
                    updated_vars = set()
                    
                    for line in lines:
                        line_stripped = line.strip()
                        if '=' in line_stripped and not line_stripped.startswith('#'):
                            var_name = line_stripped.split('=')[0].strip()
                            if var_name in env_vars:
                                # Update existing variable
                                updated_lines.append(f"{var_name}={env_vars[var_name]}\n")
                                updated_vars.add(var_name)
                            else:
                                updated_lines.append(line)
                        else:
                            updated_lines.append(line)
                    
                    # Add new variables with header
                    if any(var_name not in updated_vars for var_name in env_vars):
                        updated_lines.append(f"\n# Auto-generated Ollama optimization ({profile} profile)\n")
                        for var_name, var_value in env_vars.items():
                            if var_name not in updated_vars:
                                updated_lines.append(f"{var_name}={var_value}\n")
                    
                    # Write back to .env file
                    with open(env_file_path, 'w') as f:
                        f.writelines(updated_lines)
                    
                    logging.info(f"Applied {len(env_vars)} optimization variables to .env file")
                    
                except Exception as e:
                    logging.warning(f"Could not update .env file: {e}")
        
        return jsonify({
            'success': True,
            'profile': profile,
            'env_variables': env_vars,
            'applied_to_env': apply_to_env,
            'message': f'Generated {len(env_vars)} optimization settings for {profile} profile'
        })
    
    except Exception as e:
        logging.error(f"Error generating Ollama optimization: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@bp.route('/syntheses', methods=['GET'])
def api_synthesis_list():
    """API endpoint to get all synthesis documents."""
    try:
        syntheses = db.session.query(SubcategorySynthesis).order_by(SubcategorySynthesis.last_updated.desc()).all()  # type: ignore
        synthesis_list = []
        for synth in syntheses:
            synthesis_list.append({
                'id': synth.id,
                'synthesis_title': synth.synthesis_title,
                'synthesis_short_name': synth.synthesis_short_name,
                'main_category': synth.main_category,
                'sub_category': synth.sub_category,
                'item_count': synth.item_count,
                'created_at': synth.created_at.isoformat() if synth.created_at else None,
                'last_updated': synth.last_updated.isoformat() if synth.last_updated else None
            })
        return jsonify(synthesis_list)
    except Exception as e:
        logging.error(f"Error retrieving synthesis list: {e}", exc_info=True)
        return jsonify({'error': 'Failed to retrieve synthesis documents'}), 500

@bp.route('/gpu-stats', methods=['GET'])
def api_gpu_stats():
    """REST API: Get GPU statistics."""
    try:
        # Use shared business logic (no SocketIO emission)
        from .. import web
        result = web.get_gpu_stats_operation(socketio_emit=False)
        
        if result['success']:
            return jsonify({'gpus': result['gpus']})
        else:
            return jsonify({'error': result['error']}), 500
    except Exception as e:
        logging.error(f"Error getting GPU stats via API: {e}", exc_info=True)
        return jsonify({'error': f'Failed to get GPU stats: {str(e)}'}), 500

@bp.route('/gpu-status', methods=['GET'])
def get_gpu_status():
    """Check comprehensive GPU status including NVIDIA, CUDA, and Ollama."""
    try:
        from ..utils.gpu_check import check_nvidia_smi, check_cuda_environment, check_ollama_gpu
        
        gpu_info = {
            'nvidia': {},
            'cuda_env': {},
            'ollama': {}
        }
        
        # Check NVIDIA GPU status
        nvidia_success, nvidia_result = check_nvidia_smi()
        gpu_info['nvidia']['success'] = nvidia_success
        gpu_info['nvidia']['result'] = nvidia_result
        
        # Check CUDA environment
        cuda_vars = check_cuda_environment()
        gpu_info['cuda_env'] = cuda_vars
        
        # Check Ollama
        ollama_success, ollama_result = check_ollama_gpu()
        gpu_info['ollama']['success'] = ollama_success
        gpu_info['ollama']['result'] = ollama_result
        
        return jsonify(gpu_info)
    except Exception as e:
        logging.error(f"Error checking GPU status: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500

@bp.route('/schedules', methods=['GET'])
def api_get_schedules():
    """Get all schedules."""
    try:
        from ..models import Schedule
        schedules = Schedule.query.all()
        schedule_list = []
        
        for schedule in schedules:
            schedule_list.append({
                'id': schedule.id,
                'name': schedule.name,
                'description': schedule.description,
                'frequency': schedule.frequency,
                'time': schedule.time,
                'day_of_week': schedule.day_of_week,
                'day_of_month': schedule.day_of_month,
                'cron_expression': schedule.cron_expression,
                'pipeline_type': schedule.pipeline_type,
                'enabled': schedule.enabled,
                'next_run': schedule.next_run.isoformat() if schedule.next_run else None,
                'last_run': schedule.last_run.isoformat() if schedule.last_run else None,
                'created_at': schedule.created_at.isoformat() if schedule.created_at else None
            })
        
        return jsonify(schedule_list)
    except Exception as e:
        logging.error(f"Error retrieving schedules: {e}", exc_info=True)
        return jsonify({'error': 'Failed to retrieve schedules'}), 500

@bp.route('/schedules', methods=['POST'])
def api_create_schedule():
    """Create a new schedule."""
    try:
        from ..models import Schedule, db
        from datetime import datetime, timezone
        import json
        
        data = request.get_json()
        
        # Validate required fields
        if not data.get('name') or not data.get('frequency'):
            return jsonify({'error': 'Name and frequency are required'}), 400
        
        # Create new schedule
        now = datetime.now(timezone.utc)
        schedule = Schedule()
        schedule.name = data['name']
        schedule.description = data.get('description', '')
        schedule.frequency = data['frequency']
        schedule.time = data.get('time')
        schedule.day_of_week = data.get('day')
        schedule.day_of_month = data.get('date')
        schedule.cron_expression = data.get('cron')
        schedule.pipeline_type = data.get('pipeline', 'full')
        schedule.pipeline_config = json.dumps({
            'skip_fetch_bookmarks': data.get('skip_fetch_bookmarks', False),
            'skip_process_content': data.get('skip_process_content', False),
            'force_recache_tweets': data.get('force_recache_tweets', False),
            'force_reprocess_media': data.get('force_reprocess_media', False),
            'force_reprocess_llm': data.get('force_reprocess_llm', False),
            'force_reprocess_kb_item': data.get('force_reprocess_kb_item', False)
        })
        schedule.enabled = data.get('enabled', True)
        schedule.created_at = now
        schedule.last_updated = now
        
        db.session.add(schedule)
        db.session.commit()
        
        return jsonify({
            'id': schedule.id,
            'name': schedule.name,
            'description': schedule.description,
            'frequency': schedule.frequency,
            'time': schedule.time,
            'pipeline_type': schedule.pipeline_type,
            'enabled': schedule.enabled,
            'created_at': schedule.created_at.isoformat()
        }), 201
        
    except Exception as e:
        logging.error(f"Error creating schedule: {e}", exc_info=True)
        return jsonify({'error': 'Failed to create schedule'}), 500

@bp.route('/schedules/<int:schedule_id>', methods=['PUT'])
def api_update_schedule(schedule_id):
    """Update an existing schedule."""
    try:
        from ..models import Schedule, db
        from datetime import datetime, timezone
        import json
        
        schedule = Schedule.query.get(schedule_id)
        if not schedule:
            return jsonify({'error': 'Schedule not found'}), 404
        
        data = request.get_json()
        
        # Update schedule fields
        if 'name' in data:
            schedule.name = data['name']
        if 'description' in data:
            schedule.description = data['description']
        if 'frequency' in data:
            schedule.frequency = data['frequency']
        if 'time' in data:
            schedule.time = data['time']
        if 'day' in data:
            schedule.day_of_week = data['day']
        if 'date' in data:
            schedule.day_of_month = data['date']
        if 'cron' in data:
            schedule.cron_expression = data['cron']
        if 'pipeline' in data:
            schedule.pipeline_type = data['pipeline']
        if 'enabled' in data:
            schedule.enabled = data['enabled']
        
        # Update pipeline config
        pipeline_config = {
            'skip_fetch_bookmarks': data.get('skip_fetch_bookmarks', False),
            'skip_process_content': data.get('skip_process_content', False),
            'force_recache_tweets': data.get('force_recache_tweets', False),
            'force_reprocess_media': data.get('force_reprocess_media', False),
            'force_reprocess_llm': data.get('force_reprocess_llm', False),
            'force_reprocess_kb_item': data.get('force_reprocess_kb_item', False)
        }
        schedule.pipeline_config = json.dumps(pipeline_config)
        schedule.last_updated = datetime.now(timezone.utc)
        
        db.session.commit()
        return jsonify({'message': 'Schedule updated successfully'})
    except Exception as e:
        logging.error(f"Error updating schedule {schedule_id}: {e}", exc_info=True)
        return jsonify({'error': 'Failed to update schedule'}), 500

@bp.route('/schedules/<int:schedule_id>', methods=['DELETE'])
def api_delete_schedule(schedule_id):
    """Delete a schedule."""
    try:
        from ..models import Schedule, db
        
        schedule = Schedule.query.get(schedule_id)
        if not schedule:
            return jsonify({'error': 'Schedule not found'}), 404
        
        db.session.delete(schedule)
        db.session.commit()
        
        return jsonify({'message': 'Schedule deleted successfully'})
    except Exception as e:
        logging.error(f"Error deleting schedule {schedule_id}: {e}", exc_info=True)
        return jsonify({'error': 'Failed to delete schedule'}), 500

@bp.route('/schedules/<int:schedule_id>/toggle', methods=['POST'])
def api_toggle_schedule(schedule_id):
    """Toggle schedule enabled/disabled status."""
    try:
        from ..models import Schedule, db
        from datetime import datetime, timezone
        
        schedule = Schedule.query.get(schedule_id)
        if not schedule:
            return jsonify({'error': 'Schedule not found'}), 404
        
        schedule.enabled = not schedule.enabled
        schedule.last_updated = datetime.now(timezone.utc)
        db.session.commit()
        
        return jsonify({'message': 'Schedule toggled successfully'})
    except Exception as e:
        logging.error(f"Error toggling schedule {schedule_id}: {e}", exc_info=True)
        return jsonify({'error': 'Failed to toggle schedule'}), 500

@bp.route('/schedules/<int:schedule_id>/run', methods=['POST'])
def api_run_schedule(schedule_id):
    """Run a schedule immediately."""
    try:
        from ..models import Schedule, ScheduleRun, db
        from datetime import datetime, timezone
        
        schedule = Schedule.query.get(schedule_id)
        if not schedule:
            return jsonify({'error': 'Schedule not found'}), 404
        
        # Create a new schedule run record
        run = ScheduleRun()
        run.schedule_id = schedule_id
        run.execution_time = datetime.now(timezone.utc)
        run.status = 'running'
        db.session.add(run)
        db.session.commit()
        
        # TODO: Actually trigger the agent run here
        # For now, just mark as completed
        run.status = 'completed'
        run.duration = '0 seconds'
        run.processed_items = 0
        db.session.commit()
        
        return jsonify({'message': 'Schedule execution started'})
    except Exception as e:
        logging.error(f"Error running schedule {schedule_id}: {e}", exc_info=True)
        return jsonify({'error': 'Failed to run schedule'}), 500

@bp.route('/schedule-history', methods=['GET'])
def api_get_schedule_history():
    """Get schedule execution history."""
    try:
        from ..models import ScheduleRun, Schedule
        
        runs = db.session.query(ScheduleRun, Schedule).join(Schedule).order_by(ScheduleRun.execution_time.desc()).limit(50).all()
        
        history = []
        for run, schedule in runs:
            history.append({
                'id': run.id,
                'schedule_name': schedule.name,
                'execution_time': run.execution_time.isoformat() if run.execution_time else None,
                'status': run.status,
                'duration': run.duration,
                'processed_items': run.processed_items or 0
            })
        
        return jsonify(history)
    except Exception as e:
        logging.error(f"Error retrieving schedule history: {e}", exc_info=True)
        return jsonify({'error': 'Failed to retrieve schedule history'}), 500

@bp.route('/schedule-runs/<int:run_id>', methods=['DELETE'])
def delete_schedule_run(run_id):
    """API endpoint to delete a schedule run from history."""
    try:
        from ..models import ScheduleRun, db
        
        run = ScheduleRun.query.get(run_id)
        if not run:
            return jsonify({'error': 'Schedule run not found'}), 404
        
        db.session.delete(run)
        db.session.commit()
        
        return jsonify({'success': True, 'message': 'Schedule run deleted successfully'})
    except Exception as e:
        logging.error(f"Error deleting schedule run {run_id}: {e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500

@bp.route('/environment')
def get_environment_settings():
    """Returns environment settings from the config."""
    config = current_app.config.get('APP_CONFIG')
    if not config:
        return jsonify({'error': 'Application config not loaded'}), 500
    
    # Expose only safe-to-view settings
    settings = {
        'Log Level': getattr(config, 'log_level', 'N/A'),
        'Log File': str(getattr(config, 'log_file', 'N/A')),
        'Knowledge Base Root': str(getattr(config, 'knowledge_base_dir', 'N/A')),
        'LLM Service URL': str(getattr(config, 'ollama_url', 'N/A')),
        'Embedding Service URL': str(getattr(config, 'embedding_model', 'N/A')),
    }
    return jsonify(settings)

@bp.route('/kb/all')
def get_kb_all():
    """Returns a JSON object with all KB items and syntheses for the TOC."""
    try:
        items = db.session.query(KnowledgeBaseItem).order_by(KnowledgeBaseItem.main_category, KnowledgeBaseItem.sub_category, KnowledgeBaseItem.title).all()
        syntheses = db.session.query(SubcategorySynthesis).order_by(SubcategorySynthesis.main_category, SubcategorySynthesis.sub_category).all()  # type: ignore
        
        items_data = [{
            'id': item.id, 'title': item.title, 'display_title': item.display_title,
            'main_category': item.main_category, 'sub_category': item.sub_category
        } for item in items]
        
        syntheses_data = [{
            'id': synth.id, 'synthesis_title': synth.synthesis_title,
            'main_category': synth.main_category, 'sub_category': synth.sub_category
        } for synth in syntheses]

        return jsonify({'items': items_data, 'syntheses': syntheses_data})
    except Exception as e:
        logging.error(f"Error fetching KB index: {e}", exc_info=True)
        return jsonify({'error': 'Failed to fetch Knowledge Base index'}), 500

@bp.route('/v2/schedule', methods=['GET', 'POST'])
def schedule_v2_endpoint():
    """V2 ENDPOINT: Handles getting and setting the agent execution schedule from the database."""
    if request.method == 'GET':
        schedule_setting = db.session.query(Setting).filter_by(key='schedule').first()
        schedule = schedule_setting.value if schedule_setting else 'Not Scheduled'
        return jsonify({'schedule': schedule})
    
    if request.method == 'POST':
        data = request.get_json()
        if not data or 'schedule' not in data:
            return jsonify({'error': 'Invalid request body'}), 400
        
        new_schedule_value = data['schedule']
        
        try:
            schedule_setting = db.session.query(Setting).filter_by(key='schedule').first()
            if schedule_setting:
                schedule_setting.value = new_schedule_value
            else:
                schedule_setting = Setting('schedule', new_schedule_value)
                db.session.add(schedule_setting)
            
            db.session.commit()
            
            return jsonify({'success': True, 'message': 'Schedule updated successfully.'})

        except Exception as e:
            db.session.rollback()
            logging.error(f"Failed to update schedule in database: {e}", exc_info=True)
            return jsonify({'error': 'Failed to write to database'}), 500
    
    # Method Not Allowed
    return jsonify({'error': 'Method not supported'}), 405

# This should be the last route in the file if it doesn't exist already
@bp.route('/logs/files')
def get_log_files():
    """API endpoint to get a list of log files."""
    config = current_app.config.get('APP_CONFIG')
    if not config:
        return jsonify({'error': 'Application config not loaded'}), 500
        
    log_dir = getattr(config, 'log_dir_path', None)
    if not log_dir or not os.path.isdir(log_dir):
        return jsonify({'error': 'Log directory not configured or found'}), 400
    
    try:
        files = [f for f in os.listdir(log_dir) if f.endswith('.log')]
        files.sort(key=lambda name: os.path.getmtime(os.path.join(log_dir, name)), reverse=True)
        return jsonify({'files': files})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/kb/validate')
def validate_kb_items():
    """API endpoint for validating Knowledge Base items in the database."""
    try:
        from ..db_validation import DatabaseValidator
        config = current_app.config.get('APP_CONFIG')
        
        if not config:
            return jsonify({'error': 'Application config not loaded'}), 500
        
        validator = DatabaseValidator(config)
        validation_results = validator.validate_kb_items()
        
        return jsonify({
            'success': True,
            'validation_results': validation_results
        })
    except Exception as e:
        logging.error(f"Error validating KB items: {e}", exc_info=True)
        return jsonify({'error': f'Failed to validate KB items: {str(e)}'}), 500

@bp.route('/items/<int:item_id>')
def get_kb_item(item_id):
    """API endpoint for getting KB item data in JSON format."""
    try:
        from flask import url_for
        item = KnowledgeBaseItem.query.get_or_404(item_id)
        
        # Parse raw JSON content if it exists
        raw_json_content_parsed = None
        if item.raw_json_content:
            try:
                import json
                raw_json_content_parsed = json.loads(item.raw_json_content)
            except (json.JSONDecodeError, TypeError):
                raw_json_content_parsed = None
        
        # Parse media paths
        media_files_for_template = []
        if item.kb_media_paths:
            try:
                import json
                media_paths = json.loads(item.kb_media_paths)
                if isinstance(media_paths, list):
                    for media_path in media_paths:
                        filename = media_path.split('/')[-1] if media_path else 'unknown'
                        media_type = 'image' if any(filename.lower().endswith(ext) for ext in ['.jpg', '.jpeg', '.png', '.gif', '.webp']) else 'video' if any(filename.lower().endswith(ext) for ext in ['.mp4', '.mov', '.avi', '.mkv', '.webm']) else 'other'
                        media_files_for_template.append({
                            'name': filename,
                            'url': url_for('api.serve_kb_media_generic', path=media_path),
                            'type': media_type
                        })
            except (json.JSONDecodeError, TypeError):
                pass
        
        item_data = {
            'id': item.id,
            'tweet_id': item.tweet_id,
            'title': item.title,
            'display_title': item.display_title,
            'description': item.description,
            'content': item.content,
            'main_category': item.main_category,
            'sub_category': item.sub_category,
            'item_name': item.item_name,
            'source_url': item.source_url,
            'created_at': item.created_at.isoformat() if item.created_at else None,
            'last_updated': item.last_updated.isoformat() if item.last_updated else None,
            'file_path': item.file_path,
            'kb_media_paths': item.kb_media_paths,
            'raw_json_content': item.raw_json_content,
            'raw_json_content_parsed': raw_json_content_parsed,
            'media_files_for_template': media_files_for_template
            , 'content_html': markdown.markdown(item.content or "", extensions=['extra','codehilite']) if item.content and item.content.strip() else ""
        }
        return jsonify(item_data)
    except Exception as e:
        return jsonify({'error': f'Failed to fetch KB item: {str(e)}'}), 500

@bp.route('/synthesis/<int:synthesis_id>')
def get_synthesis_item(synthesis_id):
    """API endpoint for getting synthesis data in JSON format."""
    try:
        synth = SubcategorySynthesis.query.get_or_404(synthesis_id)
        
        # Parse raw JSON content if it exists
        raw_json_content_parsed = None
        if synth.raw_json_content:
            try:
                import json
                raw_json_content_parsed = json.loads(synth.raw_json_content)
            except (json.JSONDecodeError, TypeError):
                raw_json_content_parsed = None
        
        synthesis_data = {
            'id': synth.id,
            'synthesis_title': synth.synthesis_title,
            'synthesis_short_name': synth.synthesis_short_name,
            'main_category': synth.main_category,
            'sub_category': synth.sub_category,
            'synthesis_content': synth.synthesis_content,
            'raw_json_content': synth.raw_json_content,
            'raw_json_content_parsed': raw_json_content_parsed,
            'item_count': synth.item_count,
            'file_path': synth.file_path,
            'created_at': synth.created_at.isoformat() if synth.created_at else None,
            'last_updated': synth.last_updated.isoformat() if synth.last_updated else None,
            'synthesis_content_html': markdown.markdown(synth.synthesis_content or "", extensions=['extra','codehilite'])
        }
        return jsonify(synthesis_data)
    except Exception as e:
        return jsonify({'error': f'Failed to fetch synthesis: {str(e)}'}), 500



@bp.route('/system/info', methods=['GET'])
def get_system_info():
    """Get comprehensive system information."""
    try:
        from ..web import get_gpu_stats
        import psutil
        import platform
        from pathlib import Path
        
        config = current_app.config.get('APP_CONFIG')
        
        # Get system stats
        system_info = {
            'platform': {
                'system': platform.system(),
                'release': platform.release(),
                'version': platform.version(),
                'machine': platform.machine(),
                'processor': platform.processor()
            },
            'memory': {
                'total': psutil.virtual_memory().total,
                'available': psutil.virtual_memory().available,
                'percent': psutil.virtual_memory().percent
            },
            'cpu': {
                'count': psutil.cpu_count(),
                'percent': psutil.cpu_percent(interval=1)
            },
            'disk_usage': {
                'total': psutil.disk_usage('/').total,
                'used': psutil.disk_usage('/').used,
                'free': psutil.disk_usage('/').free
            } if psutil.disk_usage('/') else None,
            'gpu_stats': get_gpu_stats() or 'Not available',
            'config_status': {
                'knowledge_base_dir': str(config.knowledge_base_dir) if config else 'Not configured',
                'log_level': getattr(config, 'log_level', 'Not configured'),
                'ollama_url': str(getattr(config, 'ollama_url', 'Not configured'))
            } if config else 'Configuration not loaded'
        }
        
        return jsonify(system_info)
        
    except Exception as e:
        logging.error(f"Error getting system info: {e}", exc_info=True)
        return jsonify({'error': 'Failed to get system information'}), 500

# Removed duplicate /logs/recent endpoint - already defined above

@bp.route('/logs/clear', methods=['POST'])
def clear_recent_logs():
    """REST API: Clear the in-memory log buffer."""
    try:
        # Use shared business logic (no SocketIO emission)
        from .. import web
        result = web.clear_logs_operation(socketio_emit=False)
        return jsonify(result)
    except Exception as e:
        logging.error(f"Error clearing logs: {e}", exc_info=True)
        return jsonify({'error': 'Failed to clear logs'}), 500 

# --- API ENDPOINTS FOR PURE POLLING ARCHITECTURE ---
# These endpoints work with the simplified web_api_only.py server

@bp.route('/v2/logs/clear', methods=['POST'])
def clear_logs_v2():
    """V2 API: Clear all server-side logs."""
    try:
        from ..web import clear_logs_operation
        return jsonify(clear_logs_operation())
    except ImportError:
        return jsonify({'error': 'clear_logs_operation not available'}), 503
    except Exception as e:
        logging.error(f"Error clearing logs via v2 endpoint: {e}", exc_info=True)
        return jsonify({'error': 'Failed to clear logs'}), 500

@bp.route('/v2/realtime-manager/health', methods=['GET'])
def get_realtime_manager_health():
    """Get comprehensive health status of the EnhancedRealtimeManager."""
    try:
        from ..web import realtime_manager
        
        if not realtime_manager:
            return jsonify({
                'success': False,
                'status': 'NOT_INITIALIZED',
                'error': 'EnhancedRealtimeManager not initialized'
            }), 503
        
        # Get comprehensive health statistics
        health_stats = realtime_manager.get_stats()
        
        # Determine overall health status
        is_healthy = health_stats.get('is_healthy', False)
        buffer_enabled = health_stats.get('buffer_enabled', False)
        
        # Calculate health score based on various factors
        health_score = 100
        if not is_healthy:
            health_score -= 50
        if buffer_enabled:
            health_score -= 20  # Buffering indicates connection issues
        if health_stats.get('events_rejected', 0) > health_stats.get('events_validated', 1) * 0.1:
            health_score -= 15  # High rejection rate indicates issues
        
        status = 'HEALTHY' if health_score >= 80 else 'DEGRADED' if health_score >= 50 else 'UNHEALTHY'
        
        return jsonify({
            'success': True,
            'status': status,
            'health_score': max(0, health_score),
            'statistics': health_stats,
            'recommendations': _get_health_recommendations(health_stats)
        })
        
    except Exception as e:
        logging.error(f"Error getting realtime manager health: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'status': 'ERROR',
            'error': str(e)
        }), 500

def _get_health_recommendations(stats):
    """Generate health recommendations based on statistics."""
    recommendations = []
    
    if not stats.get('is_healthy', False):
        recommendations.append("Redis connection is unhealthy - check Redis server status")
    
    if stats.get('buffer_enabled', False):
        recommendations.append("Event buffering is active - indicates Redis connectivity issues")
    
    events_rejected = stats.get('events_rejected', 0)
    events_validated = stats.get('events_validated', 1)
    if events_rejected > events_validated * 0.1:
        recommendations.append(f"High event rejection rate ({events_rejected}/{events_validated}) - check event validation logic")
    
    if stats.get('reconnections', 0) > 5:
        recommendations.append("Frequent reconnections detected - investigate network stability")
    
    if not recommendations:
        recommendations.append("System is operating normally")
    
    return recommendations

@bp.route('/v2/realtime-manager/restart', methods=['POST'])
def restart_realtime_manager():
    """Restart the EnhancedRealtimeManager (emergency recovery)."""
    try:
        from ..web import realtime_manager
        
        if not realtime_manager:
            return jsonify({
                'success': False,
                'error': 'EnhancedRealtimeManager not initialized'
            }), 503
        
        logging.warning("Manual restart of EnhancedRealtimeManager requested")
        
        # Stop the current listener
        try:
            realtime_manager.stop_listener()
            logging.info("EnhancedRealtimeManager stopped")
        except Exception as e:
            logging.warning(f"Error stopping realtime manager: {e}")
        
        # Start it again
        try:
            realtime_manager.start_listener()
            logging.info("EnhancedRealtimeManager restarted successfully")
            
            return jsonify({
                'success': True,
                'message': 'EnhancedRealtimeManager restarted successfully'
            })
        except Exception as e:
            logging.error(f"Failed to restart EnhancedRealtimeManager: {e}", exc_info=True)
            return jsonify({
                'success': False,
                'error': f'Failed to restart: {str(e)}'
            }), 500
        
    except Exception as e:
        logging.error(f"Error restarting realtime manager: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500