"""
Command-Line Interface for Knowledge Base Agent

This module provides a CLI for managing the agent, including running tasks,
managing Celery workers, and interacting with the system. It uses Click for
creating clean and composable command-line utilities.
"""
import gevent.monkey
gevent.monkey.patch_all()

import psutil  # Import after monkey-patching

import click
import json
import uuid
import os

# To make this CLI runnable from the root directory, we need to adjust the path
import sys
from pathlib import Path
import asyncio

# Add the project root to the Python path
project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from flask import Flask
# FIX: Import the single app instance from web.py instead of creating a new one.
from knowledge_base_agent.web import app as cli_app, db
# FIX: We still need celery_app for the worker and monitor commands.
from knowledge_base_agent.celery_app import celery_app, init_celery
from knowledge_base_agent.tasks.agent_tasks import run_agent_task
from knowledge_base_agent.config import Config
from knowledge_base_agent.main import load_config
# from knowledge_base_agent.models import db # Now imported from web

# Global app instance for CLI context
# _cli_app = None # No longer needed

def _get_app():
    """
    Returns the application instance from web.py.
    This ensures all CLI commands operate on the same app context as the web server.
    """
    # The app is already created and configured at module level in web.py
    return cli_app

@click.group(invoke_without_command=True)
@click.pass_context
def cli(ctx):
    """Knowledge Base Agent CLI with Celery backend."""
    # Ensure app is created before any command is run
    _get_app()
    if ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())

@cli.command()
@click.option('--preferences', type=str, default='{}', help='JSON string of user preferences.')
def run(preferences):
    """
    Queue an agent execution task in Celery.
    
    Example:
    python -m knowledge_base_agent.cli run --preferences '{"skip_media_processing": true}'
    """
    try:
        prefs_dict = json.loads(preferences)
    except json.JSONDecodeError:
        click.echo(click.style("Error: Invalid JSON string for --preferences.", fg='red'), err=True)
        return

    task_id = str(uuid.uuid4())
    
    click.echo(f"Queuing agent task with ID: {task_id}")
    click.echo(f"Preferences: {prefs_dict}")

    # Queue the task in Celery
    task = run_agent_task.apply_async(args=[task_id, prefs_dict], task_id=task_id)
    
    click.echo(click.style(f"✅ Agent task queued successfully!", fg='green'))
    click.echo(f"   Task ID: {task_id}")
    click.echo(f"   Celery ID: {task.id}")

@cli.command()
@click.option('--queues', default='agent,processing,chat', help='Comma-separated list of queues to consume from.')
@click.option('--concurrency', default=2, type=int, help='Number of concurrent worker processes.')
def worker(queues, concurrency):
    """Start a Celery worker process."""
    # App is already initialized by the group invocation
    click.echo(f"Starting Celery worker for queues: {queues}")
    click.echo(f"Concurrency level: {concurrency}")
    
    # Construct the arguments for the Celery worker
    worker_argv = [
        'worker',
        '--loglevel=info',
        f'--queues={queues}',
        f'--concurrency={concurrency}',
    ]
    
    # Start the worker
    celery_app.worker_main(argv=worker_argv)

@cli.command()
@click.option('--port', default=5555, type=int, help='Port for the Flower dashboard.')
@click.option('--address', default='0.0.0.0', help='Address to bind the Flower dashboard to.')
def monitor(port, address):
    """Start the Flower monitoring dashboard."""
    app = _get_app()
    # The broker URL should be accessed from the Celery app's config
    broker_url = celery_app.conf.broker_url
    
    click.echo(f"Starting Flower monitoring dashboard on http://{address}:{port}")
    
    # Construct the arguments for Flower
    flower_argv = [
        f'--broker={broker_url}',
        f'--port={port}',
        f'--address={address}',
    ]

    # Flower is a separate command, so we use os.system or subprocess
    # For simplicity here, we build the command and instruct the user.
    # A more robust solution might use subprocess.
    
    # Find the celery executable
    celery_executable = "celery" # Assume it's in the PATH
    
    cmd = [
        celery_executable,
        '-A', 'knowledge_base_agent.celery_app',
        'flower'
    ] + flower_argv

    click.echo("Running command: " + " ".join(cmd))
    os.system(" ".join(cmd))


@cli.command()
def web():
    """Run the Flask web server with Socket.IO."""
    click.echo("Starting Flask-SocketIO server...")
    from knowledge_base_agent.web import main as web_main
    web_main()


if __name__ == '__main__':
    cli() 