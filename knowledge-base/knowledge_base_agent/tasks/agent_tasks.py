"""
Main Agent Execution Tasks for Celery

This module contains the primary agent execution task that replaces the current
multiprocessing subprocess execution with a Celery task.
"""

import logging
import uuid
import time
import traceback
import asyncio
from datetime import datetime
from typing import Dict, Any, Optional
from dataclasses import asdict

from celery import current_task
from ..celery_app import celery_app
from ..task_progress import get_progress_manager
from ..config import Config
from ..prompts import UserPreferences
from ..exceptions import KnowledgeBaseError
# FIX: Import the new RedisTaskLogHandler
from ..task_progress import RedisTaskLogHandler

# Import the app factory from the web module
from ..web import create_app  # type: ignore


@celery_app.task(bind=True, name='knowledge_base_agent.tasks.agent.run_agent')
def run_agent_task(self, task_id: str, preferences_dict: Dict[str, Any]):
    """
    Main agent execution task - migrated from background_worker.py and main.py
    
    Preserves all functionality from current agent.run() method while
    running in Celery worker context instead of multiprocessing subprocess.
    
    Args:
        task_id: Unique task identifier for progress tracking
        preferences_dict: UserPreferences as dictionary
        
    Returns:
        Dict with execution results and status
    """
    # FIX: Move declarations to the top
    log_handler = None
    root_logger = logging.getLogger()
    progress_manager = None
    
    # FIX: Get the loop that the celery worker is running on
    # This is crucial for the RedisTaskLogHandler to work correctly
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    try:
        # Load configuration
        config = Config.from_env()
        config.ensure_directories()

        # Get the progress manager
        progress_manager = get_progress_manager(config)

        # Attach the Redis log handler, passing the worker's event loop
        log_handler = RedisTaskLogHandler(task_id, progress_manager, loop)
        root_logger.addHandler(log_handler)
        
        # Initialize progress tracking
        loop.run_until_complete(progress_manager.log_message(task_id, "🚀 Agent task started in Celery worker", "INFO"))
        loop.run_until_complete(progress_manager.update_progress(task_id, 0, "initialization", "Agent task started"))
        
        # Update Celery task state for monitoring
        self.update_state(
            state='PROGRESS',
            meta={
                'phase_id': 'initialization',
                'status': 'running',
                'message': 'Agent task started',
                'progress': 0,
                'task_id': task_id
            }
        )
        
        # Convert dict back to UserPreferences
        try:
            preferences = UserPreferences(**preferences_dict)
            loop.run_until_complete(progress_manager.log_message(task_id, f"✅ UserPreferences loaded: {preferences.run_mode}", "INFO"))
        except Exception as e:
            error_msg = f"Failed to parse UserPreferences: {e}"
            loop.run_until_complete(progress_manager.log_message(task_id, f"❌ {error_msg}", "ERROR"))
            raise ValueError(error_msg)
        
        # Create progress callback that mimics current SocketIO emissions
        def _safe_await(coro):
            """Await *coro* whether the loop is already running or not."""
            if loop.is_running():
                asyncio.run_coroutine_threadsafe(coro, loop)
            else:
                loop.run_until_complete(coro)

        def progress_callback(phase_id: str, status: str, message: str, progress: int = 0, **kwargs):
            # Update Redis progress & log
            _safe_await(progress_manager.update_progress(task_id, progress, phase_id, message, status=status))
            _safe_await(progress_manager.log_message(task_id, f"[{phase_id}] {message}", "INFO"))

            # Update Celery task meta (still sync)
            self.update_state(
                state='PROGRESS',
                meta={ 'phase_id': phase_id, 'status': status, 'message': message, 'progress': progress, 'task_id': task_id, **kwargs }
            )
            # Publish via pubsub for WebSocket layer
            _safe_await(progress_manager.publish_phase_update(task_id, phase_id, status, message, progress))
        
        # Create agent status update callback
        def status_callback(status_data: Dict[str, Any]):
            status_data['task_id'] = task_id
            loop.run_until_complete(progress_manager.publish_agent_status_update(status_data))
        
        # Initialize agent
        progress_callback("initialization", "running", "Initializing agent components", 10)
        
        # Import agent here to avoid circular imports
        from ..agent import KnowledgeBaseAgent
        
        # Create a proper Flask app context
        app, _, _, _ = create_app()
        loop.run_until_complete(progress_manager.log_message(task_id, "💾 Flask app context created for database operations", "INFO"))
        
        with app.app_context():
            config = app.config.get('APP_CONFIG')
            if not config:
                 raise KnowledgeBaseError("Configuration not found in Flask app context.")

            from ..shared_globals import sg_set_project_root
            sg_set_project_root(config.project_root)

            # Bridge functions passed into the agent – avoids fragile monkey-patching
            def _phase_cb(phase_id: str, status: str, message: str, **kwargs):
                # Progress percentage if tweet counts available
                pct = 0
                pc, tc = kwargs.get("processed_count"), kwargs.get("total_count")
                if pc is not None and tc:
                    try:
                        pct = int(pc / tc * 100)
                    except ZeroDivisionError:
                        pct = 0
                progress_callback(phase_id, status, message, pct, **kwargs)

            def _log_cb(msg: str, level: str = "INFO"):
                _safe_await(progress_manager.log_message(task_id, msg, level))

            agent = KnowledgeBaseAgent(
                app=app,
                config=config,
                socketio=None,
                phase_callback=_phase_cb,
                log_callback=_log_cb,
            )
            
            progress_callback("initialization", "running", "Agent initialized, starting execution", 20)
            loop.run_until_complete(progress_manager.log_message(task_id, "🚀 Starting agent execution...", "INFO"))
            
            try:
                result = loop.run_until_complete(agent.run(preferences))
                
                # Mark completion
                progress_callback("completed", "completed", "Agent execution completed successfully", 100)
                
                return {
                    'status': 'completed', 'task_id': task_id, 'result': result,
                    'message': 'Agent execution completed successfully', 'preferences': asdict(preferences)
                }
            finally:
                # The main loop is closed by the outer finally block
                pass
        
    except Exception as e:
        error_msg = f"Agent execution failed: {str(e)}"
        
        if progress_manager:
            loop.run_until_complete(progress_manager.log_message(task_id, f"❌ {error_msg}", "ERROR"))
            loop.run_until_complete(progress_manager.update_progress(task_id, 0, "error", error_msg))
        
        logging.error(f"Agent task failed: {error_msg}", exc_info=True)
        
        error_details = {
            'error': error_msg, 'traceback': traceback.format_exc(),
            'task_id': task_id, 'timestamp': datetime.utcnow().isoformat(),
            'config_loaded': config is not None
        }
        
        if progress_manager:
            loop.run_until_complete(progress_manager.publish_agent_status_update({
                'is_running': False, 'current_phase_id': 'error',
                'current_phase_message': error_msg, 'current_phase_status': 'error', 'task_id': task_id
            }))
        
        self.update_state(state='FAILURE', meta=error_details)
        raise KnowledgeBaseError(error_msg) from e
    
    finally:
        if log_handler:
            root_logger.removeHandler(log_handler)
        
        # Close the loop if we created a new one
        if not asyncio.get_event_loop().is_running():
            loop.close()


@celery_app.task(bind=True, name='knowledge_base_agent.tasks.agent.fetch_bookmarks')
def fetch_bookmarks_task(self, task_id: str):
    progress_manager = get_progress_manager()
    
    async def _async_fetch():
        from ..fetch_bookmarks import BookmarksFetcher
        from ..shared_globals import sg_set_project_root
        app, _, _, _ = create_app()
        with app.app_context():
            config = app.config.get('APP_CONFIG')
            if not config:
                raise KnowledgeBaseError("Configuration not found in Flask app context for fetch_bookmarks.")
        config.ensure_directories()
        sg_set_project_root(config.project_root)
        fetcher = BookmarksFetcher(config)
        try:
            await fetcher.initialize()
            bookmarks = await fetcher.fetch_bookmarks()
            return bookmarks
        finally:
            await fetcher.cleanup()
    
    async def async_main():
        await progress_manager.log_message(task_id, "📚 Starting bookmark fetch task", "INFO")
        await progress_manager.update_progress(task_id, 0, "fetch_bookmarks", "Starting bookmark fetch")
        await progress_manager.update_progress(task_id, 50, "fetch_bookmarks", "Fetching bookmarks...")
        bookmarks = await _async_fetch()
        await progress_manager.update_progress(task_id, 100, "fetch_bookmarks", "Bookmark fetch completed")
        await progress_manager.log_message(task_id, f"✅ Fetched {len(bookmarks)} bookmarks successfully", "INFO")
        return {'status': 'completed', 'task_id': task_id, 'bookmarks_fetched': len(bookmarks)}
    
    try:
        return asyncio.run(async_main())
    except Exception as e:
        error_msg = f"Bookmark fetch failed: {str(e)}"
        asyncio.run(progress_manager.log_message(task_id, f"❌ {error_msg}", "ERROR"))
        asyncio.run(progress_manager.update_progress(task_id, 0, "error", error_msg))
        logging.error(f"Bookmark fetch task failed: {error_msg}", exc_info=True)
        raise KnowledgeBaseError(error_msg) from e


@celery_app.task(bind=True, name='knowledge_base_agent.tasks.agent.git_sync')
def git_sync_task(self, task_id: str, commit_message: Optional[str] = None):
    """
    Git sync task - can be run independently or as part of main agent run.
    """
    progress_manager = get_progress_manager()
    
    # Create event loop for async operations
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    try:
        loop.run_until_complete(progress_manager.log_message(task_id, " syncing git repository", "INFO"))
        
        # Create an app context to access the configuration correctly
        app, _, _, _ = create_app()
        with app.app_context():
            config = app.config.get('APP_CONFIG')
            if not config:
                raise KnowledgeBaseError("Configuration not found in Flask app context for git_sync.")
            
            from ..git_helper import GitSyncHandler
            handler = GitSyncHandler(config)
            
            if not commit_message:
                commit_message = "Update knowledge base content"
            
            try:
                handler.add()  # type: ignore
                handler.commit(commit_message)  # type: ignore
                handler.push()  # type: ignore
            except Exception as git_error:
                loop.run_until_complete(progress_manager.update_progress(task_id, 0, "error", f"Git sync failed: {git_error}"))
                raise KnowledgeBaseError(f"Git operation failed: {git_error}") from git_error

            loop.run_until_complete(progress_manager.update_progress(task_id, 100, "git_sync", "Git sync completed successfully"))
            loop.run_until_complete(progress_manager.log_message(task_id, "✅ Git sync completed successfully", "INFO"))
        
            return {'status': 'completed', 'task_id': task_id}
        
    except Exception as e:
        error_msg = f"Git sync failed: {str(e)}"
        if progress_manager:
            # Create a new loop for error logging if the main one is broken
            try:
                if loop.is_closed():
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                loop.run_until_complete(progress_manager.log_message(task_id, f"❌ {error_msg}", "ERROR"))
                loop.run_until_complete(progress_manager.update_progress(task_id, 0, "error", error_msg))
            except Exception as log_exc:
                logging.critical(f"Failed to log error message during exception handling: {log_exc}")
        
        logging.error(f"Git sync task failed: {error_msg}", exc_info=True)
        
        self.update_state(
            state='FAILURE',
            meta={
                'error': error_msg,
                'task_id': task_id,
                'timestamp': datetime.utcnow().isoformat()
            }
        )
        raise KnowledgeBaseError(error_msg) from e
    finally:
        if loop and not loop.is_closed():
            loop.close()


def generate_task_id() -> str:
    """Generates a unique task ID."""
    return str(uuid.uuid4()) 