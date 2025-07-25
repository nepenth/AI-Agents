#!/usr/bin/env python3
"""
Quick utility to clear stuck agent tasks and reset state.

This script provides a fast way to clean up stuck tasks without needing
to use the web interface, useful for debugging and emergency recovery.
"""

import sys
from pathlib import Path

# Add the project root to the Python path
project_root = Path(__file__).resolve().parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from knowledge_base_agent.web import create_app
from knowledge_base_agent.task_state_manager import TaskStateManager
from knowledge_base_agent.config import Config
from knowledge_base_agent.models import CeleryTaskState
import click


@click.command()
@click.option('--dry-run', is_flag=True, help='Show what would be cleaned without actually doing it')
@click.option('--force', is_flag=True, help='Skip confirmation prompts')
def main(dry_run, force):
    """Clear stuck agent tasks and reset state."""
    
    # Initialize Flask app context
    app, socketio, migrate, realtime_manager = create_app()
    
    with app.app_context():
        config = Config()
        task_manager = TaskStateManager(config)
        
        # Get stuck tasks count
        stuck_tasks = CeleryTaskState.query.filter(
            CeleryTaskState.status.in_(['PENDING', 'PROGRESS', 'STARTED'])
        ).all()
        
        if not stuck_tasks:
            click.echo("✅ No stuck tasks found. Agent state is clean.")
            return
        
        click.echo(f"🔍 Found {len(stuck_tasks)} stuck tasks:")
        click.echo("=" * 60)
        
        for task in stuck_tasks:
            duration = task.created_at
            click.echo(f"Task ID: {task.task_id}")
            click.echo(f"  Status: {task.status}")
            click.echo(f"  Created: {task.created_at}")
            click.echo(f"  Phase: {task.current_phase_message or 'None'}")
            click.echo()
        
        if dry_run:
            click.echo("🔍 DRY RUN: Would clean up the above tasks")
            return
        
        if not force:
            if not click.confirm(f"Clean up {len(stuck_tasks)} stuck tasks and reset agent state?"):
                click.echo("❌ Cancelled.")
                return
        
        click.echo("🧹 Performing comprehensive cleanup...")
        
        # Perform the reset
        success = task_manager.reset_agent_state()
        
        if success:
            click.echo(f"✅ Successfully cleaned up {len(stuck_tasks)} stuck tasks")
            click.echo("✅ Agent state reset to idle")
            click.echo("✅ Redis data cleared")
            click.echo("✅ Celery tasks revoked")
        else:
            click.echo("❌ Failed to reset agent state")
            sys.exit(1)


if __name__ == '__main__':
    main()