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
    celery_task_state = None
    
    # FIX: Get the loop that the celery worker is running on
    # This is crucial for the RedisTaskLogHandler to work correctly
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    try:
        # TASK ID VERIFICATION: Trace task_id through initialization process
        print(f"🔍 TASK ID VERIFICATION: Starting run_agent_task with task_id={task_id}")
        if not task_id:
            raise ValueError("task_id is required but was None or empty")
        if not isinstance(task_id, str):
            raise ValueError(f"task_id must be string, got {type(task_id)}")
        print(f"✅ TASK ID VERIFICATION: task_id validation passed")
        
        # Load configuration
        print(f"DEBUG: Loading config for task {task_id}")
        config = Config.from_env()
        config.ensure_directories()
        print(f"DEBUG: Config loaded successfully")

        # Get the progress manager
        print(f"DEBUG: Getting progress manager")
        progress_manager = get_progress_manager(config)
        print(f"DEBUG: Progress manager created")

        # TASK ID VERIFICATION: Verify task_id is passed to RedisTaskLogHandler
        print(f"🔍 TASK ID VERIFICATION: Creating RedisTaskLogHandler with task_id={task_id}")
        log_handler = RedisTaskLogHandler(task_id, progress_manager, loop)
        root_logger.addHandler(log_handler)
        print(f"✅ TASK ID VERIFICATION: RedisTaskLogHandler created and attached")
        
        # Initialize progress tracking
        loop.run_until_complete(progress_manager.log_message(task_id, "🚀 Agent execution started", "INFO"))
        loop.run_until_complete(progress_manager.update_progress(task_id, 0, "initialization", "Agent task started"))
        
        # PIPELINE TEST: Generate test log message to verify logging pipeline
        print(f"🧪 PIPELINE TEST: Generating test log message for task_id={task_id}")
        test_message = f"🧪 PIPELINE TEST: Logging pipeline verification for task {task_id}"
        loop.run_until_complete(progress_manager.log_message(task_id, test_message, "INFO"))
        
        # Verify test message was stored in Redis (with retry for timing)
        try:
            pipeline_test_passed = False
            max_retries = 3
            
            for attempt in range(max_retries):
                # Small delay to allow Redis operation to complete
                if attempt > 0:
                    time.sleep(0.1)  # Use time.sleep instead of await asyncio.sleep
                
                stored_logs = loop.run_until_complete(progress_manager.get_logs(task_id, limit=10))
                pipeline_test_passed = any(test_message in str(log) for log in stored_logs)
                
                if pipeline_test_passed:
                    break
                    
                print(f"🧪 PIPELINE TEST: Attempt {attempt + 1}/{max_retries} - Test message not yet found, retrying...")
            
            if pipeline_test_passed:
                print(f"✅ PIPELINE TEST: Test message successfully stored in Redis")
                loop.run_until_complete(progress_manager.log_message(task_id, "✅ Logging pipeline test PASSED", "INFO"))
            else:
                print(f"❌ PIPELINE TEST: Test message NOT found in Redis storage after {max_retries} attempts")
                print(f"📊 PIPELINE TEST: Found {len(stored_logs)} logs in Redis for task {task_id}")
                loop.run_until_complete(progress_manager.log_message(task_id, "❌ Logging pipeline test FAILED - message not stored", "WARNING"))
        except Exception as e:
            print(f"❌ PIPELINE TEST: Error verifying pipeline: {e}")
            loop.run_until_complete(progress_manager.log_message(task_id, f"❌ Logging pipeline test ERROR: {e}", "ERROR"))
        
        # Update Celery task state for monitoring (only if running via Celery)
        if hasattr(self, 'request') and self.request.id:
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

            # Update Celery task meta (still sync) - only if running via Celery
            if hasattr(self, 'request') and self.request.id:
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
            
            # CRITICAL FIX: Create CeleryTaskState record for proper state tracking
            from ..models import CeleryTaskState, AgentState, db
            
            # Create or update CeleryTaskState record
            # Generate human-readable name
            human_name = generate_human_readable_task_name()
            
            celery_task_state = CeleryTaskState.query.filter_by(task_id=task_id).first()
            if not celery_task_state:
                celery_task_state = CeleryTaskState(
                    task_id=task_id,
                    celery_task_id=self.request.id,
                    task_type='agent_run',
                    status='PROGRESS',
                    preferences=preferences_dict,
                    human_readable_name=human_name
                )
                celery_task_state.started_at = datetime.utcnow()
                db.session.add(celery_task_state)
            else:
                celery_task_state.status = 'PROGRESS'
                celery_task_state.celery_task_id = self.request.id
                celery_task_state.started_at = datetime.utcnow()
            
            celery_task_state.updated_at = datetime.utcnow()
            
            # Update AgentState to link to this task
            agent_state = AgentState.query.first()
            if not agent_state:
                agent_state = AgentState(
                    is_running=True,
                    current_task_id=task_id,
                    current_phase_message="Agent execution started",
                    last_update=datetime.utcnow()
                )
                db.session.add(agent_state)
            else:
                agent_state.is_running = True
                agent_state.current_task_id = task_id
                agent_state.current_phase_message = "Agent execution started"
                agent_state.last_update = datetime.utcnow()
            
            db.session.commit()
            loop.run_until_complete(progress_manager.log_message(task_id, "✅ Task state initialized in database", "INFO"))

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

            # TASK ID VERIFICATION: Verify task_id is passed to KnowledgeBaseAgent constructor
            print(f"🔍 TASK ID VERIFICATION: Creating KnowledgeBaseAgent with task_id={task_id}")
            agent = KnowledgeBaseAgent(
                app=app,
                config=config,
                socketio=None,
                phase_callback=_phase_cb,
                log_callback=_log_cb,
                task_id=task_id  # CRITICAL FIX: Pass task_id for unified logging
            )
            print(f"✅ TASK ID VERIFICATION: KnowledgeBaseAgent created successfully")
            
            progress_callback("initialization", "running", "Agent initialized, starting execution", 20)
            loop.run_until_complete(progress_manager.log_message(task_id, "🚀 Starting agent execution...", "INFO"))
            
            try:
                result = loop.run_until_complete(agent.run(preferences))
                
                # Generate comprehensive task run report
                run_report = _generate_task_run_report(agent, preferences, result, task_id)
                
                # Log the detailed report
                loop.run_until_complete(progress_manager.log_message(task_id, "📊 TASK RUN REPORT", "INFO"))
                for line in run_report['log_lines']:
                    loop.run_until_complete(progress_manager.log_message(task_id, line, "INFO"))
                
                # Mark completion
                progress_callback("completed", "completed", "Agent execution completed successfully", 100)
                
                return {
                    'status': 'completed', 'task_id': task_id, 'result': result,
                    'message': 'Agent execution completed successfully', 'preferences': asdict(preferences),
                    'run_report': run_report
                }
            finally:
                # The main loop is closed by the outer finally block
                pass
        
    except Exception as e:
        # Mark task as failed for cleanup
        self._task_failed = True
        
        error_msg = f"Agent execution failed: {str(e)}"
        print(f"DEBUG: Exception in task: {error_msg}")
        print(f"DEBUG: Traceback: {traceback.format_exc()}")
        
        if progress_manager:
            try:
                loop.run_until_complete(progress_manager.log_message(task_id, f"❌ {error_msg}", "ERROR"))
                loop.run_until_complete(progress_manager.update_progress(task_id, 0, "error", error_msg))
            except Exception as log_error:
                print(f"DEBUG: Error logging to Redis: {log_error}")
        
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
        
        # Update Celery state only if running via Celery
        if hasattr(self, 'request') and self.request.id:
            self.update_state(state='FAILURE', meta=error_details)
        raise KnowledgeBaseError(error_msg) from e
    
    finally:
        # CRITICAL FIX: Ensure all state systems are properly cleaned up
        try:
            # Create a new app context for cleanup operations
            app, _, _, _ = create_app()
            with app.app_context():
                from ..models import CeleryTaskState, AgentState, db
                
                # Update CeleryTaskState to reflect completion/failure
                celery_task_state = CeleryTaskState.query.filter_by(task_id=task_id).first()
                if celery_task_state:
                    celery_task_state.status = 'SUCCESS' if not hasattr(self, '_task_failed') else 'FAILURE'
                    celery_task_state.completed_at = datetime.utcnow()
                    celery_task_state.updated_at = datetime.utcnow()
                    
                    # Store the run report if task completed successfully
                    if not hasattr(self, '_task_failed') and 'run_report' in locals():
                        celery_task_state.run_report = run_report
                        celery_task_state.result_data = result if 'result' in locals() else None
                
                # Update AgentState to show agent is no longer running
                agent_state = AgentState.query.first()
                if agent_state:
                    agent_state.is_running = False
                    agent_state.current_task_id = None
                    agent_state.current_phase_message = 'Idle'
                    agent_state.last_update = datetime.utcnow()
                
                db.session.commit()
                
                # Clear Redis progress data
                if progress_manager:
                    loop.run_until_complete(progress_manager.clear_task_data(task_id))
                    loop.run_until_complete(progress_manager.log_message(task_id, "🧹 Task cleanup completed", "INFO"))
                
        except Exception as cleanup_error:
            logging.error(f"Error during task cleanup: {cleanup_error}", exc_info=True)
            # Don't raise - we don't want cleanup errors to mask the original error
        
        # Remove log handler
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
    
    # Create event loop for async operations
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    try:
        return loop.run_until_complete(async_main())
    except Exception as e:
        error_msg = f"Bookmark fetch failed: {str(e)}"
        loop.run_until_complete(progress_manager.log_message(task_id, f"❌ {error_msg}", "ERROR"))
        loop.run_until_complete(progress_manager.update_progress(task_id, 0, "error", error_msg))
        logging.error(f"Bookmark fetch task failed: {error_msg}", exc_info=True)
        raise KnowledgeBaseError(error_msg) from e
    finally:
        if loop and not loop.is_closed():
            loop.close()


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
        
        # Update Celery state only if running via Celery
        if hasattr(self, 'request') and self.request.id:
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


def _generate_task_run_report(agent, preferences: UserPreferences, result: Dict[str, Any], task_id: str) -> Dict[str, Any]:
    """
    Generate a comprehensive task run report with phase details, validation results, and processing statistics.
    """
    from datetime import datetime
    
    # Get phase statuses from agent
    phase_statuses = getattr(agent, '_plan_statuses', {})
    
    # Calculate execution time
    execution_time = result.get('execution_time', 'Unknown')
    
    # Extract processing statistics
    processed_count = result.get('processed_count', 0)
    error_count = result.get('error_count', 0)
    
    # Generate human-readable task name
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    human_readable_name = f"Agent Run - {timestamp}"
    
    # Build phase summary
    phase_summary = []
    for phase_id, status_info in phase_statuses.items():
        status = status_info.get('status', 'unknown')
        message = status_info.get('message', 'No message')
        
        # Add emoji based on status
        if status == 'completed':
            emoji = "✅"
        elif status == 'skipped':
            emoji = "⏭️"
        elif status == 'error':
            emoji = "❌"
        elif status == 'interrupted':
            emoji = "⏸️"
        else:
            emoji = "⏳"
            
        phase_summary.append(f"{emoji} {phase_id}: {status.upper()} - {message}")
    
    # Build preference summary
    preference_summary = []
    preference_summary.append(f"Run Mode: {preferences.run_mode}")
    preference_summary.append(f"Skip Fetch Bookmarks: {preferences.skip_fetch_bookmarks}")
    preference_summary.append(f"Skip Process Content: {preferences.skip_process_content}")
    preference_summary.append(f"Skip Synthesis Generation: {preferences.skip_synthesis_generation}")
    preference_summary.append(f"Skip Embedding Generation: {preferences.skip_embedding_generation}")
    preference_summary.append(f"Skip README Generation: {preferences.skip_readme_generation}")
    preference_summary.append(f"Skip Git Push: {preferences.skip_git_push}")
    
    # Add force flags if any are enabled
    force_flags = []
    if preferences.force_recache_tweets:
        force_flags.append("Force Recache Tweets")
    if preferences.force_reprocess_content:
        force_flags.append("Force Reprocess Content")
    if preferences.force_reprocess_media:
        force_flags.append("Force Reprocess Media")
    if preferences.force_reprocess_llm:
        force_flags.append("Force Reprocess LLM")
    if preferences.force_reprocess_kb_item:
        force_flags.append("Force Reprocess KB Items")
    if preferences.force_regenerate_synthesis:
        force_flags.append("Force Regenerate Synthesis")
    if preferences.force_regenerate_embeddings:
        force_flags.append("Force Regenerate Embeddings")
    if preferences.force_regenerate_readme:
        force_flags.append("Force Regenerate README")
    
    if force_flags:
        preference_summary.append(f"Force Flags: {', '.join(force_flags)}")
    else:
        preference_summary.append("Force Flags: None")
    
    # Build log lines for output
    log_lines = [
        "=" * 80,
        f"📋 TASK EXECUTION SUMMARY",
        f"Task ID: {task_id}",
        f"Human Name: {human_readable_name}",
        f"Execution Time: {execution_time}",
        f"Items Processed: {processed_count}",
        f"Errors Encountered: {error_count}",
        "",
        "🔧 EXECUTION PREFERENCES:",
        *[f"  • {pref}" for pref in preference_summary],
        "",
        "📊 PHASE EXECUTION RESULTS:",
        *[f"  {phase}" for phase in phase_summary],
        "",
        "🎯 FINAL STATUS: " + ("SUCCESS" if error_count == 0 else f"COMPLETED WITH {error_count} ERRORS"),
        "=" * 80
    ]
    
    return {
        'task_id': task_id,
        'human_readable_name': human_readable_name,
        'timestamp': timestamp,
        'execution_time': execution_time,
        'processed_count': processed_count,
        'error_count': error_count,
        'phase_statuses': phase_statuses,
        'preferences': asdict(preferences),
        'force_flags': force_flags,
        'log_lines': log_lines,
        'final_status': 'SUCCESS' if error_count == 0 else 'COMPLETED_WITH_ERRORS'
    }


def generate_task_id() -> str:
    """Generates a unique task ID."""
    return str(uuid.uuid4())


def generate_human_readable_task_name() -> str:
    """Generates a human-readable task name with timestamp."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return f"Agent Run - {timestamp}" 