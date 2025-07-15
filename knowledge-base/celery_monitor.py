#!/usr/bin/env python3
"""
Celery Task Monitor and Management Utility

This script provides commands to monitor, inspect, and manage Celery tasks
for the knowledge base agent system.
"""

import os
import sys
import click
import json
import asyncio
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Any

# Add the project root to the Python path
project_root = Path(__file__).resolve().parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from knowledge_base_agent.celery_app import celery_app
from knowledge_base_agent.config import Config
from knowledge_base_agent.task_progress import get_progress_manager
from knowledge_base_agent.web import create_app
from knowledge_base_agent.models import db, CeleryTaskState, AgentState
import redis


@click.group()
@click.pass_context
def cli(ctx):
    """Celery Task Monitor and Management Utility"""
    ctx.ensure_object(dict)
    
    # Initialize Flask app context for database operations
    app, socketio, migrate, realtime_manager = create_app()
    ctx.obj['app'] = app
    ctx.obj['config'] = Config()


@cli.command()
@click.pass_context
def active_tasks(ctx):
    """List all active Celery tasks"""
    app = ctx.obj['app']
    
    with app.app_context():
        # Get active tasks from Celery
        active_tasks = celery_app.control.inspect().active()
        
        if not active_tasks:
            click.echo("No active tasks found.")
            return
        
        click.echo("Active Celery Tasks:")
        click.echo("=" * 50)
        
        for worker, tasks in active_tasks.items():
            click.echo(f"\nWorker: {worker}")
            for task in tasks:
                task_id = task.get('id')
                name = task.get('name', 'Unknown')
                started = task.get('time_start', 'Unknown')
                args = task.get('args', [])
                
                click.echo(f"  Task ID: {task_id}")
                click.echo(f"  Name: {name}")
                click.echo(f"  Started: {started}")
                click.echo(f"  Args: {args}")
                click.echo()


@cli.command()
@click.pass_context
def stuck_tasks(ctx):
    """Check for potentially stuck tasks"""
    app = ctx.obj['app']
    config = ctx.obj['config']
    
    with app.app_context():
        # Check database for long-running tasks
        cutoff_time = datetime.utcnow() - timedelta(hours=3)  # Tasks running > 3 hours
        
        stuck_tasks = CeleryTaskState.query.filter(
            CeleryTaskState.status.in_(['PENDING', 'PROGRESS', 'STARTED']),
            CeleryTaskState.created_at < cutoff_time
        ).all()
        
        if not stuck_tasks:
            click.echo("No stuck tasks found.")
            return
        
        click.echo("Potentially Stuck Tasks:")
        click.echo("=" * 50)
        
        for task in stuck_tasks:
            duration = datetime.utcnow() - task.created_at
            
            click.echo(f"Task ID: {task.task_id}")
            click.echo(f"Type: {task.task_type}")
            click.echo(f"Status: {task.status}")
            click.echo(f"Started: {task.created_at}")
            click.echo(f"Duration: {duration}")
            click.echo(f"Phase: {task.current_phase_message}")
            click.echo()


@cli.command()
@click.option('--older-than', default=24, type=int, help='Clear tasks older than X hours')
@click.option('--status', multiple=True, help='Clear tasks with specific status (can be used multiple times)')
@click.option('--dry-run', is_flag=True, help='Show what would be deleted without actually deleting')
@click.pass_context
def clear_old_tasks(ctx, older_than, status, dry_run):
    """Clear old Celery tasks from database and Redis"""
    app = ctx.obj['app']
    config = ctx.obj['config']
    
    with app.app_context():
        # Calculate cutoff time
        cutoff_time = datetime.utcnow() - timedelta(hours=older_than)
        
        # Build query
        query = CeleryTaskState.query.filter(CeleryTaskState.created_at < cutoff_time)
        
        if status:
            query = query.filter(CeleryTaskState.status.in_(status))
        
        old_tasks = query.all()
        
        if not old_tasks:
            click.echo(f"No tasks found older than {older_than} hours.")
            return
        
        click.echo(f"Found {len(old_tasks)} tasks older than {older_than} hours:")
        
        for task in old_tasks:
            click.echo(f"  {task.task_id} - {task.status} - {task.created_at}")
        
        if dry_run:
            click.echo("\nDRY RUN: Would delete above tasks")
            return
        
        # Confirm deletion
        if not click.confirm(f"Delete {len(old_tasks)} tasks?"):
            click.echo("Cancelled.")
            return
        
        # Clear from Redis
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            progress_manager = get_progress_manager(config)
            
            for task in old_tasks:
                # Clear from Redis
                loop.run_until_complete(progress_manager.clear_task_data(task.task_id))
                
                # Delete from database
                db.session.delete(task)
            
            db.session.commit()
            click.echo(f"Successfully deleted {len(old_tasks)} tasks.")
            
        except Exception as e:
            click.echo(f"Error clearing tasks: {e}")
            db.session.rollback()
        finally:
            loop.close()


@cli.command()
@click.option('--task-id', help='Revoke specific task by ID')
@click.option('--all-active', is_flag=True, help='Revoke all active tasks')
@click.pass_context
def revoke_tasks(ctx, task_id, all_active):
    """Revoke (cancel) running Celery tasks"""
    if not task_id and not all_active:
        click.echo("Must specify either --task-id or --all-active")
        return
    
    if task_id:
        # Revoke specific task
        click.echo(f"Revoking task: {task_id}")
        celery_app.control.revoke(task_id, terminate=True, signal='SIGTERM')
        click.echo("Task revocation sent.")
    
    elif all_active:
        # Get all active tasks
        active_tasks = celery_app.control.inspect().active()
        
        if not active_tasks:
            click.echo("No active tasks to revoke.")
            return
        
        # Confirm revocation
        total_tasks = sum(len(tasks) for tasks in active_tasks.values())
        if not click.confirm(f"Revoke {total_tasks} active tasks?"):
            click.echo("Cancelled.")
            return
        
        # Revoke all active tasks
        for worker, tasks in active_tasks.items():
            for task in tasks:
                task_id = task.get('id')
                celery_app.control.revoke(task_id, terminate=True, signal='SIGTERM')
                click.echo(f"Revoked: {task_id}")


@cli.command()
@click.pass_context
def flush_redis(ctx):
    """Flush all task data from Redis"""
    config = ctx.obj['config']
    
    if not click.confirm("This will clear ALL task progress and logs from Redis. Continue?"):
        click.echo("Cancelled.")
        return
    
    try:
        # Connect to Redis instances
        progress_redis = redis.Redis.from_url(config.redis_progress_url)
        logs_redis = redis.Redis.from_url(config.redis_logs_url)
        
        # Clear progress data
        progress_keys = progress_redis.keys("progress:*")
        if progress_keys:
            progress_redis.delete(*progress_keys)
            click.echo(f"Cleared {len(progress_keys)} progress entries")
        
        # Clear log data
        log_keys = logs_redis.keys("logs:*")
        if log_keys:
            logs_redis.delete(*log_keys)
            click.echo(f"Cleared {len(log_keys)} log entries")
        
        click.echo("Redis flush completed.")
        
    except Exception as e:
        click.echo(f"Error flushing Redis: {e}")


@cli.command()
@click.pass_context
def stats(ctx):
    """Show Celery and task statistics"""
    app = ctx.obj['app']
    
    with app.app_context():
        # Database stats
        total_tasks = CeleryTaskState.query.count()
        pending_tasks = CeleryTaskState.query.filter_by(status='PENDING').count()
        running_tasks = CeleryTaskState.query.filter_by(status='PROGRESS').count()
        completed_tasks = CeleryTaskState.query.filter_by(status='SUCCESS').count()
        failed_tasks = CeleryTaskState.query.filter_by(status='FAILURE').count()
        
        # Celery stats
        stats = celery_app.control.inspect().stats()
        active_tasks = celery_app.control.inspect().active()
        
        click.echo("Database Task Statistics:")
        click.echo("=" * 30)
        click.echo(f"Total tasks: {total_tasks}")
        click.echo(f"Pending: {pending_tasks}")
        click.echo(f"Running: {running_tasks}")
        click.echo(f"Completed: {completed_tasks}")
        click.echo(f"Failed: {failed_tasks}")
        click.echo()
        
        if stats:
            click.echo("Celery Worker Statistics:")
            click.echo("=" * 30)
            for worker, worker_stats in stats.items():
                click.echo(f"\nWorker: {worker}")
                click.echo(f"  Pool: {worker_stats.get('pool', {}).get('max-concurrency', 'N/A')} processes")
                click.echo(f"  Total tasks: {worker_stats.get('total', 'N/A')}")
        
        if active_tasks:
            total_active = sum(len(tasks) for tasks in active_tasks.values())
            click.echo(f"\nCurrently active tasks: {total_active}")


@cli.command()
@click.pass_context
def reset_agent_state(ctx):
    """Reset the agent state to idle"""
    app = ctx.obj['app']
    
    with app.app_context():
        state = AgentState.query.first()
        if state:
            state.is_running = False
            state.current_task_id = None
            state.current_phase_message = 'State reset to idle'
            state.last_update = datetime.utcnow()
            db.session.commit()
            click.echo("Agent state reset to idle.")
        else:
            click.echo("No agent state found.")


@cli.command()
@click.option('--queue', default='', help='Purge specific queue (default: all queues)')
@click.pass_context
def purge_queues(ctx, queue):
    """Purge all messages from Celery queues"""
    if queue:
        queues = [queue]
    else:
        queues = ['agent', 'processing', 'chat']
    
    if not click.confirm(f"This will purge all messages from queues: {', '.join(queues)}. Continue?"):
        click.echo("Cancelled.")
        return
    
    for q in queues:
        try:
            celery_app.control.purge()
            click.echo(f"Purged queue: {q}")
        except Exception as e:
            click.echo(f"Error purging queue {q}: {e}")


if __name__ == '__main__':
    cli() 