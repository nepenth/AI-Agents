"""
Celery Task Monitoring and Observability

This module uses Celery signals to hook into the task lifecycle. It provides
centralized logging and persistent state updates for every task executed
by the workers, integrating with the CeleryTaskState database model.
"""

import logging
from datetime import datetime

from celery.signals import task_prerun, task_postrun, task_failure
from flask import Flask

from knowledge_base_agent.models import db, CeleryTaskState

# Create a logger for this module
logger = logging.getLogger(__name__)

def initialize_monitoring(app: Flask):
    """
    Initializes the monitoring signals with the Flask app context.
    This ensures that database operations can be performed within the signal handlers.
    """
    
    @task_prerun.connect
    def task_prerun_handler(sender=None, task_id=None, task=None, args=None, kwargs=None, **kwds):
        """
        Signal handler for before a task starts.
        Updates the database task state to 'PROGRESS' and logs the start.
        """
        with app.app_context():
            logger.info(f"Task {task.name} [{task_id}] started.")
            try:
                task_state = CeleryTaskState.query.filter_by(task_id=task_id).first()
                if task_state:
                    task_state.status = 'PROGRESS'
                    task_state.started_at = datetime.utcnow()
                    task_state.celery_task_id = task.request.id # Capture Celery's internal ID
                    db.session.commit()
                else:
                    # This can happen for tasks not initiated via our standard flow
                    # We create a new record to ensure all tasks are tracked.
                    logger.warning(f"No pre-existing task state found for {task_id}. Creating one.")
                    new_task_state = CeleryTaskState(
                        task_id=task_id,
                        celery_task_id=task.request.id,
                        task_type=task.name,
                        status='PROGRESS',
                        started_at=datetime.utcnow()
                    )
                    db.session.add(new_task_state)
                    db.session.commit()
            except Exception as e:
                logger.error(f"Error in task_prerun_handler for {task_id}: {e}", exc_info=True)
                db.session.rollback()

    @task_postrun.connect
    def task_postrun_handler(sender=None, task_id=None, task=None, args=None, kwargs=None, retval=None, state=None, **kwds):
        """
        Signal handler for after a task completes.
        Updates the database with the final state, result, and completion time.
        """
        with app.app_context():
            status = state or 'UNKNOWN'
            logger.info(f"Task {task.name} [{task_id}] completed with state: {status}")
            try:
                task_state = CeleryTaskState.query.filter_by(task_id=task_id).first()
                if task_state:
                    task_state.status = status
                    task_state.completed_at = datetime.utcnow()
                    
                    # Avoid storing large results or non-serializable objects
                    if retval and isinstance(retval, (dict, list, str, int, float, bool)):
                        task_state.result_data = retval
                    elif retval:
                        task_state.result_data = {'result_type': str(type(retval)), 'message': 'Result not serializable'}

                    db.session.commit()

                # Also update the singleton AgentState so that `/agent/status` shows idle
                from knowledge_base_agent.models import AgentState
                agent_state = AgentState.query.first()
                if agent_state and agent_state.current_task_id == task_id:
                    agent_state.is_running = False
                    agent_state.current_phase_message = f'Task {status.lower()}'
                    agent_state.last_update = datetime.utcnow()
                    db.session.commit()
            except Exception as e:
                logger.error(f"Error in task_postrun_handler for {task_id}: {e}", exc_info=True)
                db.session.rollback()

    @task_failure.connect
    def task_failure_handler(sender=None, task_id=None, exception=None, traceback=None, einfo=None, **kwds):
        """
        Signal handler for when a task fails.
        Logs the error and updates the database with the exception details.
        """
        with app.app_context():
            logger.error(f"Task {sender.name} [{task_id}] failed: {exception}")
            try:
                task_state = CeleryTaskState.query.filter_by(task_id=task_id).first()
                if task_state:
                    task_state.status = 'FAILURE'
                    task_state.completed_at = datetime.utcnow()
                    task_state.error_message = str(exception)
                    if einfo:
                        task_state.traceback = einfo.traceback
                    db.session.commit()

                # Update AgentState on failure as well
                from knowledge_base_agent.models import AgentState
                agent_state = AgentState.query.first()
                if agent_state and agent_state.current_task_id == task_id:
                    agent_state.is_running = False
                    agent_state.current_phase_message = f'Task failed: {exception}'
                    agent_state.last_update = datetime.utcnow()
                    db.session.commit()
            except Exception as e:
                logger.error(f"Error in task_failure_handler for {task_id}: {e}", exc_info=True)
                db.session.rollback()
    
    logger.info("Celery monitoring signals initialized.") 