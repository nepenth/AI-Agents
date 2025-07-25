"""
Main agent module coordinating knowledge base operations.

This module contains the core logic for the Knowledge Base Agent, which automates the process of fetching, processing, categorizing, and generating content for a structured knowledge base. It integrates various components to ensure seamless operation and data management.
"""

import logging
from typing import Set, List, Dict, Any, Optional, Callable
from pathlib import Path
import asyncio
from datetime import datetime, timezone
import time
import aiofiles
from flask_socketio import SocketIO
import json
from dataclasses import asdict
from flask import current_app
import math
from statistics import mean, median
from collections import defaultdict
import traceback

# Core imports needed at module level
from knowledge_base_agent.config import Config
from knowledge_base_agent.exceptions import AgentError, MarkdownGenerationError
from knowledge_base_agent.database_state_manager import DatabaseStateManager
from knowledge_base_agent.git_helper import GitSyncHandler
from knowledge_base_agent.category_manager import CategoryManager
from knowledge_base_agent.custom_types import TweetData, KnowledgeBaseItem
from knowledge_base_agent.preferences import UserPreferences, load_user_preferences
from knowledge_base_agent.progress import ProcessingStats, PhaseDetail
from knowledge_base_agent.content_processor import ContentProcessingError
from knowledge_base_agent.tweet_utils import parse_tweet_id_from_url
from knowledge_base_agent.http_client import HTTPClient
from knowledge_base_agent.shared_globals import stop_flag, clear_stop_flag, sg_get_project_root, sg_set_project_root
from knowledge_base_agent.models import db
from knowledge_base_agent.stats_manager import DynamicPhaseEstimator, get_historical_phase_average, format_duration_to_hhmm

# Heavy imports moved to functions where they're used

# Default phase IDs - ensure these match your UI elements' IDs
DEFAULT_PHASE_IDS = [
    "user_input_parsing",
    "fetch_bookmarks",
    "content_processing_overall",
    "synthesis_generation",
    "embedding_generation",
    "readme_generation",
    "git_sync"
]

def setup_logging(config: Config) -> None:
    """
    Configure logging with different levels for file and console.

    This function sets up logging handlers for both file and console output, with different
    formatting and filtering to ensure relevant information is logged appropriately.

    Args:
        config (Config): Configuration object containing logging settings, such as log file path.
    """
    # Note: Logging is configured by the main application, not here.
    # This function is kept for compatibility but does not set up duplicate handlers.
    pass

class KnowledgeBaseAgent:
    """
    The main agent responsible for the knowledge base creation process.
    """
    
    def __init__(self, app, config: Config, socketio: Optional[SocketIO] = None,
                 phase_callback: Optional[Callable[..., None]] = None,
                 log_callback: Optional[Callable[[str, str], None]] = None,
                 task_id: Optional[str] = None):
        """
        Initialize the agent with configuration.

        Args:
            config (Config): Configuration object containing settings for the agent.
            socketio (Optional[SocketIO]): SocketIO instance for real-time updates.
            task_id (Optional[str]): Task ID for unified logging system.
        """
        self.app = app
        self.config = config
        self.http_client = HTTPClient(config)
        self.state_manager = DatabaseStateManager(config)
        self.category_manager = CategoryManager(config, http_client=self.http_client)
        self.socketio = socketio
        self.task_id = task_id
        
        # Initialize unified logging system if task_id is provided
        if task_id:
            # TASK ID VALIDATION: Ensure task_id is properly set
            if not isinstance(task_id, str) or not task_id.strip():
                raise ValueError(f"task_id must be a non-empty string, got: {task_id}")
            
            from .unified_logging import get_unified_logger
            self.unified_logger = get_unified_logger(task_id, config)
            logging.info(f"✅ KnowledgeBaseAgent: Unified logger initialized with task_id={task_id}")
        else:
            self.unified_logger = None
            logging.warning("⚠️ KnowledgeBaseAgent: No task_id provided, unified logging disabled")
        
        # Optional external callbacks (e.g. Celery → Redis pipeline).  If provided, they
        # will be invoked in addition to the built-in Socket.IO emission so that the
        # caller can receive progress without monkey-patching these methods.
        self._external_phase_cb = phase_callback
        self._external_log_cb   = log_callback
        # Debug: Log socketio initialization
        if socketio:
            logging.info(f"Agent initialized WITH socketio: {type(socketio).__name__}")
        else:
            logging.warning("Agent initialized WITHOUT socketio - real-time updates will not work")
        # Initialize phase execution helper here to avoid import at module level
        from knowledge_base_agent.phase_execution_helper import PhaseExecutionHelper
        from knowledge_base_agent.tweet_cacher import TweetCacheValidator
        
        self.phase_execution_helper = PhaseExecutionHelper(self.config)
        self.content_processor = None  # Type hints removed to avoid import issues
        self.chat_manager = None
        self.embedding_manager = None
        self._processing_lock = asyncio.Lock()
        self.git_handler = GitSyncHandler(config)
        self.stats = ProcessingStats(start_time=datetime.now())
        self._initialized = False
        self.tweet_processor = TweetCacheValidator(config)
        self._is_running = False
        self._current_phase_id = None
        self._current_phase_message = "Idle"
        self._current_phase_status = None
        self._current_run_preferences = None
        self._plan_statuses = {}
        
        # Enhanced dynamic phase estimation system
        self.phase_estimator = DynamicPhaseEstimator()
        
        # Legacy time estimation tracking (kept for compatibility)
        self._phase_start_times = {}
        self._phase_item_processing_times = defaultdict(list)
        self._phase_total_items = {}
        self._phase_processed_items = {}
        self._phase_estimated_completion_times = {}
        
        self.logger = logging.getLogger(__name__)
        self.logger.info("KnowledgeBaseAgent initialized with dynamic phase estimation")

    def _update_state_in_db(self, **kwargs):
        """Helper to update the agent's state in the database."""
        if not self.app:
            self.logger.warning("Cannot update state in DB: No Flask app context.")
            return

        with self.app.app_context():
            from .models import AgentState, db
            
            state = AgentState.query.first()
            if not state:
                self.logger.error("Could not find AgentState row in database to update.")
                return

            # Update fields from kwargs
            for key, value in kwargs.items():
                if hasattr(state, key):
                    # Serialize dicts/lists to JSON strings for Text fields
                    if isinstance(value, (dict, list)):
                        setattr(state, key, json.dumps(value))
                    else:
                        setattr(state, key, value)

            state.last_update = datetime.now(timezone.utc)
            
            try:
                db.session.commit()
                self.logger.debug(f"Agent state updated in DB with keys: {list(kwargs.keys())}")
            except Exception as e:
                self.logger.error(f"Failed to commit agent state to DB: {e}")
                db.session.rollback()

    def socketio_emit_log(self, message: str, level: str = "INFO") -> None:
        """Emit a log message via socketio and also log it."""
        # Always log to the local logger first
        logging.log(getattr(logging, level.upper(), logging.INFO), message)
        
        log_data = {'message': message, 'level': level.upper()}

        # Socket.IO path (web-server run) -----------------------------------
        # Use unified logging system
        if hasattr(self, 'unified_logger') and self.unified_logger:
            self.unified_logger.log(log_data.get('message', ''), log_data.get('level', 'INFO'))
        else:
            # Fallback to standard logging
            logging.log(getattr(logging, log_data.get('level', 'INFO')), log_data.get('message', ''))

        # External callback path (Celery run) -------------------------------
        if self._external_log_cb:
            try:
                self._external_log_cb(message, level)
            except Exception:
                logging.debug("External log callback failed", exc_info=True)

        # For CLI runs with neither socketio nor external callback we just log locally

    def socketio_emit_phase_update(self, 
                                 phase_id: str, 
                                 status: str, 
                                 message: str, 
                                 is_sub_step_update: bool = False,
                                 processed_count: Optional[int] = None,
                                 total_count: Optional[int] = None,
                                 error_count: Optional[int] = None,
                                 initial_estimated_duration_seconds: Optional[float] = None):
        """Emits a phase update via SocketIO and updates internal agent state with dynamic estimation."""
        log_message = (
            f"Phase Update: ID='{phase_id}', Status='{status}', Message='{message}', SubStep='{is_sub_step_update}'"
        )
        if processed_count is not None:
            log_message += f", Processed={processed_count}"
        if total_count is not None:
            log_message += f", Total={total_count}"
        if error_count is not None:
            log_message += f", Errors={error_count}"
        if initial_estimated_duration_seconds is not None:
            log_message += f", InitialETC={initial_estimated_duration_seconds:.0f}s"
        logging.info(log_message)

        # Get current time for calculations
        current_time = time.time()
        estimated_completion_timestamp = None
        
        # Handle phase initialization and tracking for main phases (not sub-steps)
        if not is_sub_step_update:
            # When a phase starts, initialize dynamic tracking
            if status == 'active' or status == 'in_progress':
                if total_count is not None and total_count > 0:
                    logging.info(f"Initializing phase tracking for '{phase_id}' with {total_count} items")
                    # Initialize dynamic phase estimation
                    historical_duration = self.phase_estimator.initialize_phase_tracking(phase_id, total_count)
                    
                    # If we have historical data and no explicit initial estimate, use historical
                    if historical_duration and initial_estimated_duration_seconds is None:
                        initial_estimated_duration_seconds = historical_duration
                    
                    # Set legacy tracking for compatibility
                    if phase_id not in self._phase_start_times:
                        self._phase_start_times[phase_id] = current_time
                    self._phase_total_items[phase_id] = total_count
                    self._phase_processed_items[phase_id] = processed_count if processed_count is not None else 0
                    
                    # Use initial estimate if provided
                    if initial_estimated_duration_seconds is not None and initial_estimated_duration_seconds > 0:
                        estimated_completion_timestamp = current_time + initial_estimated_duration_seconds
                        logging.info(f"Phase '{phase_id}' initialized with ETC: {format_duration_to_hhmm(initial_estimated_duration_seconds)}")
                else:
                    logging.debug(f"Phase '{phase_id}' not initialized for tracking: status={status}, total_count={total_count}")
            
            # Update progress for ongoing phases
            elif processed_count is not None and total_count is not None:
                logging.debug(f"Updating progress for '{phase_id}': {processed_count}/{total_count}")
                # Update dynamic estimation with current progress
                estimation_result = self.phase_estimator.update_phase_progress(phase_id, processed_count)
                if estimation_result:
                    estimated_completion_timestamp = estimation_result.get("estimated_completion_timestamp")
                    logging.debug(f"Updated ETC for '{phase_id}': {estimation_result.get('estimated_remaining_minutes', 0)} minutes remaining")
                else:
                    logging.debug(f"No estimation result for '{phase_id}' progress update")
                
                # Update legacy tracking
                self._phase_processed_items[phase_id] = processed_count
            
            # When a phase ends, finalize tracking
            if status in ['completed', 'error', 'skipped', 'interrupted']:
                if status == 'completed':
                    self.phase_estimator.finalize_phase(phase_id)
                
                # Clean up legacy tracking
                self._phase_start_times.pop(phase_id, None)
                self._phase_estimated_completion_times.pop(phase_id, None)
                self._phase_item_processing_times.pop(phase_id, None)
                self._phase_total_items.pop(phase_id, None)
                self._phase_processed_items.pop(phase_id, None)
        
        # For ongoing phases, try to get dynamic estimate if not already set
        if estimated_completion_timestamp is None and not is_sub_step_update:
            estimate_data = self.phase_estimator.get_phase_estimate(phase_id)
            if estimate_data:
                estimated_completion_timestamp = estimate_data.get("estimated_completion_timestamp")

        # Update agent's overall phase state (non-sub-step only)
        if not is_sub_step_update:
            self._current_phase_id = phase_id
            self._current_phase_message = message
            self._current_phase_status = status
            if phase_id in DEFAULT_PHASE_IDS or phase_id.startswith("subphase_cp_"):
                self._plan_statuses[phase_id] = {'status': status, 'message': message, 'sub_step': False}

        # External callback (Celery worker) ---------------------------------
        if self._external_phase_cb:
            try:
                self._external_phase_cb(phase_id, status, message,
                                        is_sub_step_update=is_sub_step_update,
                                        processed_count=processed_count,
                                        total_count=total_count,
                                        error_count=error_count,
                                        initial_estimated_duration_seconds=initial_estimated_duration_seconds)
            except Exception:
                logging.debug("External phase callback failed", exc_info=True)

        # Prepare enhanced data for SocketIO emit
        data_to_emit = {
            'phase_id': phase_id,
            'status': status,
            'message': message,
            'is_sub_step_update': is_sub_step_update,
            'processed_count': processed_count,
            'total_count': total_count,
            'error_count': error_count,
            'initial_estimated_duration_seconds': initial_estimated_duration_seconds,
            'estimated_completion_timestamp': estimated_completion_timestamp
        }
        
        # Add dynamic estimation details for frontend
        if not is_sub_step_update:
            estimate_data = self.phase_estimator.get_phase_estimate(phase_id)
            if estimate_data:
                etc_data = {
                    'current_avg_time_per_item': estimate_data.get("current_avg_time_per_item", 0.0),
                    'estimated_remaining_minutes': estimate_data.get("estimated_remaining_minutes", 0.0),
                    'progress_percentage': (processed_count / total_count * 100) if processed_count and total_count else 0
                }
                data_to_emit.update(etc_data)
                logging.debug(f"Adding ETC data to emit for '{phase_id}': {etc_data}")
            else:
                logging.debug(f"No estimate data available for '{phase_id}'")
        
        # Log the complete data being emitted for debugging
        if logging.getLogger().isEnabledFor(logging.DEBUG):
            logging.debug(f"Emitting phase_update for '{phase_id}': {json.dumps(data_to_emit, default=str)}")
        
        # --- Persist state to DB ---
        db_updates = {
            'current_phase_id': self._current_phase_id,
            'current_phase_message': self._current_phase_message,
            'current_phase_status': self._current_phase_status,
            'plan_statuses': self._plan_statuses,
        }
        # Add dynamic estimates if available
        if not is_sub_step_update:
            active_estimates = self.phase_estimator.get_all_active_estimates()
            if active_estimates:
                db_updates['phase_estimates'] = active_estimates
        self._update_state_in_db(**db_updates)
        # --- End DB Persistence ---

        # Use unified logging system for phase updates
        if hasattr(self, 'unified_logger') and self.unified_logger:
            # Enhanced phase update with comprehensive data
            if status in ['active', 'in_progress']:
                self.unified_logger.emit_phase_start(
                    phase_id, 
                    message, 
                    estimated_duration=initial_estimated_duration_seconds
                )
            elif status == 'completed':
                self.unified_logger.emit_phase_complete(
                    phase_id,
                    result={
                        "processed_count": processed_count,
                        "total_count": total_count,
                        "error_count": error_count
                    }
                )
            elif status == 'error':
                self.unified_logger.emit_phase_error(phase_id, message)
            else:
                # For other status updates, use the legacy method for compatibility
                self.unified_logger.emit_phase_update(phase_id, status, message, processed_count or 0)
        else:
            # Fallback to standard logging when unified logger not available
            logging.info(f"Phase Update: {phase_id} - {status} - {message}")
            if not hasattr(self, '_socketio_warning_shown'):
                logging.debug("UnifiedLogger not available for phase updates")
                self._socketio_warning_shown = True

    async def initialize(self) -> tuple:
        """Initialize or re-initialize agent components."""
        if self._initialized and self.content_processor and self.embedding_manager and self.chat_manager:
            self.logger.info("Agent already initialized. Skipping re-initialization.")
            return self.content_processor, self.embedding_manager, self.chat_manager

        self.logger.info("Initializing agent components...")
        
        # Import components here to avoid circular imports
        from knowledge_base_agent.content_processor import StreamlinedContentProcessor
        from knowledge_base_agent.markdown_writer import MarkdownWriter
        from knowledge_base_agent.embedding_manager import EmbeddingManager
        from knowledge_base_agent.chat_manager import ChatManager
        
        # Initialize the streamlined content processor
        self.content_processor = StreamlinedContentProcessor(
            config=self.config,
            http_client=self.http_client,
            state_manager=self.state_manager,
            markdown_writer=MarkdownWriter(self.config),
            category_manager=self.category_manager,
            socketio=self.socketio,
            phase_emitter_func=self.socketio_emit_phase_update,
            task_id=self.task_id  # Pass task_id for unified logging
        )
        
        # Initialize EmbeddingManager
        self.embedding_manager = EmbeddingManager(
            config=self.config,
            http_client=self.http_client
        )

        # Initialize ChatManager
        if self.embedding_manager:
            self.chat_manager = ChatManager(
                config=self.config,
                http_client=self.http_client,
                embedding_manager=self.embedding_manager
            )

        await self.state_manager.initialize()
        self._initialized = True
        self.logger.info("Agent initialization complete.")
        return self.content_processor, self.embedding_manager, self.chat_manager

    async def fetch_and_queue_bookmarks(self, preferences: UserPreferences) -> int:
        """
        Fetches bookmarks and adds them to the processing queue.

        Returns:
            int: The number of new tweet IDs added to the unprocessed queue.
        """
        newly_added_tweet_ids_count = 0
        if stop_flag.is_set():
            logging.info("Bookmark fetching skipped due to stop flag.")
            self.socketio_emit_log("Bookmark fetching skipped due to stop flag.", "INFO")
            self.socketio_emit_phase_update('fetch_bookmarks', 'skipped', 'Stop flag active.')
            return newly_added_tweet_ids_count

        self.socketio_emit_phase_update('fetch_bookmarks', 'in_progress', 'Starting bookmark fetching...')
        self.socketio_emit_log("Fetching and queuing bookmarks...", "INFO")
        
        # Import here to avoid circular imports
        from knowledge_base_agent.fetch_bookmarks import BookmarksFetcher
        bookmark_fetcher = BookmarksFetcher(self.config)
        try:
            await bookmark_fetcher.initialize()
            bookmarks = await bookmark_fetcher.fetch_bookmarks()
            self.socketio_emit_log(f"Fetched {len(bookmarks)} bookmarks from source.", "INFO")

            new_tweet_ids_this_run = []
            total_bookmarks = len(bookmarks)
            for i, bookmark_url in enumerate(bookmarks):
                if stop_flag.is_set():
                    self.socketio_emit_log("Bookmark processing loop stopped by flag.", "INFO")
                    break
                
                current_progress_msg = f"Processing bookmark {i+1}/{total_bookmarks}: {bookmark_url[:50]}..."
                self.socketio_emit_phase_update('fetch_bookmarks', 'in_progress', current_progress_msg)
                self.socketio_emit_log(current_progress_msg, "DEBUG")

                tweet_id = parse_tweet_id_from_url(bookmark_url)
                if not tweet_id:
                    logging.warning(f"Invalid tweet URL in bookmark: {bookmark_url}")
                    self.socketio_emit_log(f"Invalid tweet URL in bookmark: {bookmark_url}", "WARNING")
                    continue
                
                processing_state = await self.state_manager.get_processing_state(tweet_id)
                is_processed = processing_state.get("fully_processed", False)
                in_unprocessed_queue = tweet_id in await self.state_manager.get_unprocessed_tweets()

                if not is_processed and not in_unprocessed_queue:
                    new_tweet_ids_this_run.append(tweet_id)
                    logging.info(f"Adding new tweet {tweet_id} from bookmark to unprocessed list.")
                    self.socketio_emit_log(f"Queued new tweet {tweet_id} from bookmark.", "DEBUG")
                elif is_processed:
                    logging.debug(f"Tweet {tweet_id} from bookmark already processed, skipping.")
                    self.socketio_emit_log(f"Tweet {tweet_id} (bookmark) already processed, skipping.", "DEBUG")
                else:
                    logging.debug(f"Tweet {tweet_id} from bookmark already in unprocessed queue, skipping.")
                    self.socketio_emit_log(f"Tweet {tweet_id} (bookmark) already in queue, skipping.", "DEBUG")
            
            if new_tweet_ids_this_run:
                await self.state_manager.add_tweets_to_unprocessed(new_tweet_ids_this_run)
                newly_added_tweet_ids_count = len(new_tweet_ids_this_run)
                final_msg = f"Added {newly_added_tweet_ids_count} new tweets from bookmarks to the unprocessed queue."
                logging.info(final_msg)
                self.socketio_emit_log(final_msg, "INFO")
            else:
                final_msg = "No new unique tweets found in bookmarks to add to the queue."
                logging.info(final_msg)
                self.socketio_emit_log(final_msg, "INFO")
                self.socketio_emit_log("BOOKMARK FETCH RESULT: No new bookmarks were found. This could mean: 1) All bookmarks are already processed, 2) No bookmarks exist, or 3) Bookmark fetching encountered an issue.", "INFO")

        except Exception as e:
            logging.exception("Bookmark fetching or queuing failed.")
            self.socketio_emit_log(f'Bookmark fetching/queuing failed: {e}', 'ERROR')
            self.socketio_emit_phase_update('fetch_bookmarks', 'error', f'Error: {e}')
            raise  # Re-raise the exception so the main run method can handle it
        finally:
            await bookmark_fetcher.cleanup()
            
        # Only emit completion status if we reach here without exception
        completion_message = f'{newly_added_tweet_ids_count} new tweets queued. {len(bookmarks)} bookmarks checked.'
        self.socketio_emit_phase_update('fetch_bookmarks', 'completed', completion_message)
        self.socketio_emit_log(f"Bookmark fetching finished. {completion_message}", "INFO")
        
        return newly_added_tweet_ids_count

    async def process_bookmarks(self) -> None:
        """
        Process bookmarks using the phased approach.

        This method fetches bookmarks, adds new tweet IDs to the unprocessed list,
        and processes them through the standard phased approach in ContentProcessor.

        Raises:
            AgentError: If bookmark fetching or processing fails.
        """
        if stop_flag.is_set():
            logging.info("Bookmark processing skipped due to stop flag.")
            # Optionally emit a socket event here if this phase is distinct in UI
            return

        from knowledge_base_agent.fetch_bookmarks import BookmarksFetcher
        logging.info("Starting bookmark processing")
        bookmark_fetcher = BookmarksFetcher(self.config)
        try:
            await bookmark_fetcher.initialize()
            bookmarks = await bookmark_fetcher.fetch_bookmarks()
            logging.info(f"Fetched {len(bookmarks)} bookmarks")
            
            new_tweet_ids = []
            for bookmark in bookmarks:
                if stop_flag.is_set():
                    logging.info("Stopping bookmark processing loop due to stop request")
                    break
                tweet_id = parse_tweet_id_from_url(bookmark)
                if not tweet_id:
                    logging.warning(f"Invalid tweet URL in bookmark: {bookmark}")
                    continue
                
                # Check if already processed or in unprocessed queue
                processing_state = await self.state_manager.get_processing_state(tweet_id)
                is_processed = processing_state.get("fully_processed", False)
                in_unprocessed_queue = tweet_id in await self.state_manager.get_unprocessed_tweets() # Assuming this returns a set/list

                if not is_processed and not in_unprocessed_queue:
                    # self.state_manager.unprocessed_tweets.append(tweet_id) # Deprecated direct access
                    new_tweet_ids.append(tweet_id)
                    logging.info(f"Queued new tweet {tweet_id} from bookmark.")
                elif is_processed:
                    logging.info(f"Tweet {tweet_id} from bookmark already processed, skipping.")
                else: # Already in unprocessed_queue
                    logging.info(f"Tweet {tweet_id} from bookmark already in unprocessed queue, skipping.")
            
            if new_tweet_ids:
                await self.state_manager.add_tweets_to_unprocessed(new_tweet_ids)
                logging.info(f"Added {len(new_tweet_ids)} new tweets from bookmarks to unprocessed list.")
                logging.info(f"Processing {len(new_tweet_ids)} new tweets from bookmarks via ContentProcessor...")
                # Assuming UserPreferences needs to be instantiated. 
                # This part needs careful review of what preferences are appropriate for this specific call path.
                # For now, using defaults that enable processing but not necessarily forcing everything.
                current_prefs = UserPreferences(
                    skip_fetch_bookmarks=True, # Already fetched here
                    skip_process_content=False,
                    # Set other flags as appropriate for this context, or load defaults
                )
                
                # Ensure content processor is initialized before use
                if not self.content_processor:
                    await self.initialize()
                assert self.content_processor is not None
                
                await self.content_processor.process_all_tweets(
                    preferences=current_prefs, 
                    unprocessed_tweets=new_tweet_ids,
                    total_tweets_for_processing=len(new_tweet_ids), # Corrected argument name
                    stats=self.stats,
                    category_manager=self.category_manager
                )
                logging.info(f"Completed phased processing of {len(new_tweet_ids)} tweets from bookmarks")
            else:
                logging.info("No new unique tweets to process from bookmarks.")
            
        except Exception as e:
            logging.exception("An error occurred during bookmark processing pipeline")
            raise AgentError(f"Failed to process bookmarks: {str(e)}")
        finally:
            if bookmark_fetcher: # Ensure fetcher was initialized
                await bookmark_fetcher.cleanup()

    async def update_indexes(self) -> None:
        """
        Update category indexes.

        This method iterates through all categories to update their indexes, ensuring the knowledge base
        structure is current. It respects the global stop flag for interruption.

        Raises:
            AgentError: If index update fails.
        """
        try:
            if stop_flag.is_set():
                logging.info("Skipping index update due to stop request")
                return
            logging.info("Starting index update")
            categories = self.category_manager.get_all_categories()
            for category in categories:
                if stop_flag.is_set():
                    logging.info("Stopping index update due to stop request")
                    break
                try:
                    pass  # Category-specific processing
                except Exception as e:
                    logging.error(f"Failed to process category {category}: {e}")
            logging.info("Index update completed")
        except Exception as e:
            logging.exception(f"Index update failed: {e}") # Log with stack trace
            raise AgentError("Failed to update indexes") from e



    async def sync_changes(self) -> None:
        """
        Sync changes to GitHub repository.

        This method synchronizes the local knowledge base changes to a remote GitHub repository.
        It respects the global stop flag for interruption.

        Raises:
            AgentError: If synchronization fails.
        """
        try:
            if stop_flag.is_set():
                logging.info("Skipping GitHub sync due to stop request")
                self.socketio_emit_phase_update('git_sync', 'skipped', 'Stop flag active.')
                return
            
            self.socketio_emit_phase_update('git_sync', 'in_progress', 'Starting GitHub synchronization...')
            logging.info("Starting GitHub sync...")
            self.socketio_emit_log("Starting GitHub sync...", "INFO")
            
            self.git_handler.sync_to_github("Update knowledge base content")
            
            logging.info("GitHub sync completed successfully")
            self.socketio_emit_log("GitHub sync completed successfully", "INFO")
            self.socketio_emit_phase_update('git_sync', 'completed', 'Successfully synced to GitHub repository.')
        except Exception as e:
            logging.exception(f"GitHub sync failed: {str(e)}") # Log with stack trace
            self.socketio_emit_log(f"GitHub sync failed: {str(e)}", "ERROR")
            self.socketio_emit_phase_update('git_sync', 'error', f"Sync failed: {str(e)}")
            raise AgentError("Failed to sync changes to GitHub") from e

    async def cleanup(self) -> None:
        """
        Cleanup temporary files and resources.

        This method removes temporary files created during processing to maintain a clean environment.

        Raises:
            None: Exceptions are logged but not raised to prevent disruption.
        """
        try:
            temp_files = list(self.config.data_processing_dir.glob("*.temp"))
            for temp_file in temp_files:
                temp_file.unlink()
            logging.info("Cleanup completed")
        except Exception as e:
            logging.warning(f"Cleanup failed: {e}")

    async def run(self, preferences: UserPreferences):
        # Enhanced debug logging to track execution flow
        self.socketio_emit_log(f"🔍 DEBUG_AGENT_RUN: Entering agent.run() method", "DEBUG")
        self.socketio_emit_log(f"DEBUG_AGENT_RUN: Prefs object received by run(): {preferences}", "DEBUG")
        self.socketio_emit_log(f"DEBUG_AGENT_RUN: Prefs type in run(): {type(preferences)}", "DEBUG")
        self.socketio_emit_log(f"DEBUG_AGENT_RUN: In run(), hasattr skip_fetch_bookmarks: {hasattr(preferences, 'skip_fetch_bookmarks')}", "DEBUG")
        self.socketio_emit_log(f"DEBUG_AGENT_RUN: In run(), hasattr skip_fetching_new_bookmarks: {hasattr(preferences, 'skip_fetching_new_bookmarks')}", "DEBUG")

        try:
            self.socketio_emit_log(f"🔍 DEBUG_AGENT_RUN: About to call initialize()", "DEBUG")
            content_processor, embedding_manager, chat_manager = await self.initialize()
            self.socketio_emit_log(f"🔍 DEBUG_AGENT_RUN: initialize() completed successfully", "DEBUG")
        except Exception as init_error:
            self.socketio_emit_log(f"❌ DEBUG_AGENT_RUN: Error in initialize(): {init_error}", "ERROR")
            self.socketio_emit_log(f"❌ DEBUG_AGENT_RUN: Initialize traceback: {traceback.format_exc()}", "ERROR")
            raise
        
        if self._is_running:
            self.socketio_emit_log("Agent is already running.", "WARNING")
            return {"status": "already_running", "message": "Agent is already running."}

        self.socketio_emit_log(f"🔍 DEBUG_AGENT_RUN: Setting _is_running to True", "DEBUG")
        self._is_running = True
        self._current_run_preferences = preferences
        
        try:
            # Use unified logging system for agent status updates
            if hasattr(self, 'unified_logger') and self.unified_logger:
                self.unified_logger.emit_agent_status({
                    'is_running': True,
                    'active_run_preferences': asdict(preferences),
                    'plan_statuses': self._plan_statuses
                })
            elif self.socketio:
                try:
                    self.socketio.emit('agent_status', {
                        'is_running': True, 
                        'active_run_preferences': asdict(preferences),
                        'plan_statuses': self._plan_statuses
                    })
                except Exception as e:
                    self.logger.error(f"Failed to emit agent_status: {e}")
                    # Try with simplified data
                    self.socketio.emit('agent_status', {
                        'is_running': True, 
                        'active_run_preferences': str(preferences),
                        'plan_statuses': {}
                    })
        except Exception as status_error:
            self.socketio_emit_log(f"❌ DEBUG_AGENT_RUN: Error emitting agent status: {status_error}", "ERROR")
            # Continue execution even if status emit fails
            
        self.socketio_emit_log(f"🔍 DEBUG_AGENT_RUN: About to clear stop flag and initialize plan statuses", "DEBUG")
        clear_stop_flag() # Clear stop flag at the beginning of a run
        self._initialize_plan_statuses(preferences) # Initialize/reset with current preferences
        self.socketio_emit_log("Knowledge Base Agent run started.", "INFO")
        
        # Emit initial state for all plan items based on preferences (only if socketio is available)
        if self.socketio:
            for phase_id, status_info in self._plan_statuses.items():
                self.socketio_emit_phase_update(phase_id, status_info['status'], status_info['message'])

        self.socketio_emit_log(f"🔍 DEBUG_AGENT_RUN: About to create ProcessingStats", "DEBUG")
        stats = ProcessingStats(start_time=datetime.now())
        phase_details_from_content_processor: List[PhaseDetail] = []

        original_tweet_count = 0
        processed_tweets_in_run = 0
        overall_start_time = time.time()

        try:
            # Handle different run modes
            self.socketio_emit_log(f"🔍 DEBUG_AGENT_RUN: About to handle run mode: {preferences.run_mode}", "DEBUG")
            
            if preferences.run_mode == "synthesis_only":
                self.socketio_emit_log("Running in synthesis-only mode - will only generate synthesis documents.", "INFO")
                self.socketio_emit_phase_update('user_input_parsing', 'completed', 'User preferences parsed - synthesis-only mode.')
                self.socketio_emit_phase_update('fetch_bookmarks', 'skipped', 'Skipped in synthesis-only mode.')
                self.socketio_emit_phase_update('content_processing_overall', 'skipped', 'Skipped in synthesis-only mode.')
                
                if stop_flag.is_set(): raise InterruptedError("Run stopped by user in synthesis-only mode.")
                await self.generate_synthesis(preferences)
                
                self.socketio_emit_phase_update('readme_generation', 'skipped', 'Skipped in synthesis-only mode.')
                self.socketio_emit_phase_update('git_sync', 'skipped', 'Skipped in synthesis-only mode.')
                
            elif preferences.run_mode == "embedding_only":
                self.socketio_emit_log("Running in embedding-only mode.", "INFO")
                self.socketio_emit_phase_update('user_input_parsing', 'completed', 'User preferences parsed - embedding-only mode.')
                self.socketio_emit_phase_update('fetch_bookmarks', 'skipped', 'Skipped in embedding-only mode.')
                self.socketio_emit_phase_update('content_processing_overall', 'skipped', 'Skipped in embedding-only mode.')
                self.socketio_emit_phase_update('synthesis_generation', 'skipped', 'Skipped in embedding-only mode.')
                self.socketio_emit_phase_update('readme_generation', 'skipped', 'Skipped in embedding-only mode.')
                self.socketio_emit_phase_update('git_sync', 'skipped', 'Skipped in embedding-only mode.')

                await self.generate_embeddings(preferences)
                if stop_flag.is_set(): raise InterruptedError("Run stopped by user in embedding-only mode.")

            elif preferences.run_mode == "full_pipeline":
                self.socketio_emit_log(f"🔍 DEBUG_AGENT_RUN: Starting full_pipeline mode execution", "DEBUG")
                # Existing full pipeline logic
                # --- Phase 1: Parse User Preferences (already done by receiving `preferences` object) ---
                self.socketio_emit_log(f"🔍 DEBUG_AGENT_RUN: Phase 1 - Emitting user_input_parsing completed", "DEBUG")
                self.socketio_emit_phase_update('user_input_parsing', 'completed', 'User preferences parsed and applied.')
                if stop_flag.is_set(): raise InterruptedError("Run stopped by user after parsing preferences.")

                # --- Phase 2: Fetch Bookmarks (Optional) ---
                self.socketio_emit_log(f"🔍 DEBUG_AGENT_RUN: Phase 2 - Checking bookmark fetching (skip={preferences.skip_fetch_bookmarks})", "DEBUG")
                if not preferences.skip_fetch_bookmarks:
                    self.socketio_emit_phase_update('fetch_bookmarks', 'active', 'Fetching bookmarks from source...', False)
                    try:
                        newly_added_tweet_ids_count = await self.fetch_and_queue_bookmarks(preferences)
                        if newly_added_tweet_ids_count > 0:
                            self.socketio_emit_phase_update('fetch_bookmarks', 'completed', f'Found {newly_added_tweet_ids_count} new bookmarks to process.', False, newly_added_tweet_ids_count, newly_added_tweet_ids_count, 0)
                        else:
                            self.socketio_emit_phase_update('fetch_bookmarks', 'completed', 'No new bookmarks found.', False, 0, 0, 0)
                            self.socketio_emit_log("BOOKMARK FETCH RESULT: No new bookmarks were found. This could mean: 1) All bookmarks are already processed, 2) No bookmarks exist, or 3) Bookmark fetching encountered an issue.", "INFO")
                    except Exception as e:
                        self.socketio_emit_log(f"Error during bookmark fetching: {e}", "ERROR")
                        self.socketio_emit_phase_update('fetch_bookmarks', 'error', f"Error: {e}", False)
                        stats.error_count +=1 # Generic error for this phase
                else:
                    self.socketio_emit_log("Skipping bookmark fetching due to user preference.", "INFO")
                    # Status already set by _initialize_plan_statuses and emitted loop

                if stop_flag.is_set(): raise InterruptedError("Run stopped by user after retrieving bookmarks.")

                # --- Phase 3: Process Content (Optional) ---
                if not preferences.skip_process_content: # Corrected attribute name
                    self.socketio_emit_phase_update('content_processing_overall', 'active', 'Starting content processing pipeline...', False)
                    try:
                        # First get unprocessed tweets
                        unprocessed_tweets = await self.state_manager.get_unprocessed_tweets()
                        self.socketio_emit_log(f"Found {len(unprocessed_tweets)} unprocessed tweets in queue", "INFO")
                        
                        # Include already processed tweets if any force reprocessing flag is enabled
                        tweets_to_process = list(unprocessed_tweets)  # Create a copy to avoid modifying the original
                        
                        # Check if any force reprocessing flag is enabled
                        any_force_reprocessing = (
                            preferences.force_reprocess_content or
                            preferences.force_reprocess_media or
                            preferences.force_reprocess_llm or
                            preferences.force_reprocess_kb_item
                        )
                        
                        if any_force_reprocessing:
                            # Get processed tweets from state manager
                            processed_tweets = await self.state_manager.get_processed_tweets()
                            if processed_tweets:
                                # Log which force flags are enabled
                                force_flags_enabled = []
                                if preferences.force_reprocess_content:
                                    force_flags_enabled.append("All Phases")
                                else:
                                    if preferences.force_reprocess_media:
                                        force_flags_enabled.append("Media Analysis")
                                    if preferences.force_reprocess_llm:
                                        force_flags_enabled.append("LLM Processing")
                                    if preferences.force_reprocess_kb_item:
                                        force_flags_enabled.append("KB Item Generation")
                                
                                self.socketio_emit_log(
                                    f"Force re-processing enabled for: {', '.join(force_flags_enabled)} - " +
                                    f"adding {len(processed_tweets)} already processed tweets to the queue", 
                                    "INFO"
                                )
                                tweets_to_process.extend(processed_tweets)
                            else:
                                self.socketio_emit_log("Force re-processing enabled but no processed tweets found", "INFO")
                        
                        total_tweets_count = len(tweets_to_process)
                        self.socketio_emit_log(f"Found {len(unprocessed_tweets)} unprocessed tweets and {total_tweets_count - len(unprocessed_tweets)} previously processed tweets to process (total: {total_tweets_count}).", "INFO")

                        if total_tweets_count > 0:
                            # Update with initial count info
                            self.socketio_emit_phase_update('content_processing_overall', 'in_progress', f'Processing {total_tweets_count} items...', False, 0, total_tweets_count, 0)
                            
                            phase_details_from_content_processor = await content_processor.process_all_tweets(
                                preferences=preferences,
                                unprocessed_tweets=tweets_to_process,
                                total_tweets_for_processing=total_tweets_count,
                                stats=stats, # Pass the shared stats object
                                category_manager=self.category_manager
                            )
                            # 'stats' object is mutated by process_all_tweets
                            processed_tweets_in_run = stats.processed_count # Use processed_count from stats, which is updated by CP
                            self.socketio_emit_log(f"Content processing finished. Processed in this run: {processed_tweets_in_run}, Errors: {stats.error_count}", "INFO")
                            self.socketio_emit_phase_update('content_processing_overall', 'completed', f'Processed {processed_tweets_in_run} of {total_tweets_count} items. Errors: {stats.error_count}.', False, processed_tweets_in_run, total_tweets_count, stats.error_count)
                        else:
                            self.socketio_emit_log("No tweets to process - the system has no unprocessed tweets and no force reprocessing flags are enabled.", "INFO")
                            self.socketio_emit_phase_update('content_processing_overall', 'completed', 'No tweets to process', False, 0, 0, 0)
                            
                            # Update content processing sub-phases to "completed" since no tweets need processing
                            # Note: database_sync is now a standalone phase, not a sub-phase of content processing
                            content_sub_phases = ['tweet_caching', 'media_analysis', 'llm_processing', 'kb_item_generation']
                            for sub_phase in content_sub_phases:
                                self.socketio_emit_phase_update(sub_phase, 'completed', 'Completed - no tweets to process', False, 0, 0, 0)
                            
                            # Check if we have any tweets in the system at all
                            all_tweets = await self.state_manager.get_all_tweets()
                            if len(all_tweets) == 0:
                                self.socketio_emit_log("SYSTEM STATE: No tweets found in the system. You may need to run bookmark fetching first to add tweets to the processing queue.", "WARNING")
                            else:
                                processed_tweets = await self.state_manager.get_processed_tweets()
                                self.socketio_emit_log(f"SYSTEM STATE: Found {len(all_tweets)} total tweets in cache, {len(processed_tweets)} are already processed. Try enabling force reprocessing flags or run bookmark fetching to add new tweets.", "INFO")
                    except Exception as e:
                        self.socketio_emit_log(f"Error during content processing: {e}", "ERROR")
                        self.socketio_emit_phase_update('content_processing_overall', 'error', f"Error: {e}", False)
                        stats.error_count += 1
                else:
                    self.socketio_emit_log("Skipping content processing due to user preference.", "INFO")
                    # Status already set by _initialize_plan_statuses and emitted loop

                if stop_flag.is_set(): raise InterruptedError("Run stopped by user during content processing.")

                if stop_flag.is_set(): raise InterruptedError("Run stopped by user after content processing.")

                # --- Phase 4: Database Sync (Standalone) ---
                self.socketio_emit_log(f"🔍 DB Sync Check: skip_process_content={preferences.skip_process_content}, force_reprocess_db_sync={preferences.force_reprocess_db_sync}", "INFO")
                if not preferences.skip_process_content or preferences.force_reprocess_db_sync:
                    try:
                        self.socketio_emit_log("🔄 Starting standalone database sync phase...", "INFO")
                        self.socketio_emit_log("🔍 About to call execute_standalone_db_sync method...", "INFO")
                        await self.execute_standalone_db_sync(preferences)
                        self.socketio_emit_log("✅ Standalone database sync phase completed successfully", "INFO")
                    except Exception as e:
                        self.socketio_emit_log(f"❌ Error during standalone database sync: {e}", "ERROR")
                        self.socketio_emit_log(f"❌ Database sync traceback: {traceback.format_exc()}", "ERROR")
                        self.socketio_emit_phase_update('database_sync', 'error', f"Database sync failed: {e}")
                        stats.error_count += 1
                        # Continue with other phases even if DB sync fails
                        self.socketio_emit_log("⚠️ Continuing with remaining phases despite DB sync error", "WARNING")
                else:
                    self.socketio_emit_log("Database sync skipped due to user preference.", "INFO")
                    self.socketio_emit_phase_update('database_sync', 'completed', 'Completed - skipped by user preference', False, 0, 0, 0)

                if stop_flag.is_set(): raise InterruptedError("Run stopped by user after database synchronization.")

                # --- Phase 6: Synthesis Generation (Optional) ---
                if not preferences.skip_synthesis_generation:
                    await self.generate_synthesis(preferences)
                else:
                    self.socketio_emit_log("Synthesis generation skipped due to user preference.", "INFO")
                    self.socketio_emit_phase_update('synthesis_generation', 'completed', 'Completed - skipped by user preference', False, 0, 0, 0)
                if stop_flag.is_set(): raise InterruptedError("Run stopped by user after synthesis generation.")

                # --- Phase 6: Embedding Generation (Optional) ---
                if not preferences.skip_embedding_generation:
                    await self.generate_embeddings(preferences)
                else:
                    self.socketio_emit_log("Embedding generation skipped due to user preference.", "INFO")
                    self.socketio_emit_phase_update('embedding_generation', 'completed', 'Completed - skipped by user preference', False, 0, 0, 0)
                if stop_flag.is_set(): raise InterruptedError("Run stopped by user after embedding generation.")

                # --- Phase 7: README Generation (Optional) ---
                if not preferences.skip_readme_generation:
                    await self.regenerate_readme(preferences)
                else:
                    self.socketio_emit_log("README generation skipped due to user preference.", "INFO")
                    self.socketio_emit_phase_update('readme_generation', 'completed', 'Completed - skipped by user preference', False, 0, 0, 0)

                if stop_flag.is_set(): raise InterruptedError("Run stopped by user after README generation.")

                # --- Phase 7: Git Sync (Optional) ---
                if not preferences.skip_git_push:
                    await self.sync_changes()
                else: # skip_git_push is true
                    self.socketio_emit_log("Git synchronization skipped due to user preference.", "INFO")
                    self.socketio_emit_phase_update('git_sync', 'completed', 'Completed - skipped by user preference', False, 0, 0, 0)

            else:
                # Handle other run modes or unknown modes
                self.socketio_emit_log(f"Unsupported run mode: {preferences.run_mode}. Falling back to full pipeline.", "WARNING")
                # Fall back to treating it as full_pipeline mode by continuing with the current logic
                # (The existing full pipeline logic would go here, but it's already been moved above)
                pass

        except InterruptedError:
            self.socketio_emit_log("Agent run was interrupted by user.", "WARNING")
            if self._current_phase_id and self._current_phase_status != 'completed': # If interrupted mid-phase
                 self.socketio_emit_phase_update(self._current_phase_id, 'interrupted', 'Run stopped by user during this phase.')
            # Mark subsequent phases as skipped due to interruption if not already done
            current_phase_found = False
            plan_steps_for_skip_check = self.initialize_and_get_execution_plan_steps(preferences) # get current plan definition
            for step in plan_steps_for_skip_check:
                if step['id'] == self._current_phase_id:
                    current_phase_found = True
                    continue # Don't mark the interrupting phase itself as skipped by interruption here
                if current_phase_found and self._plan_statuses.get(step['id'], {}).get('status') not in ['completed', 'skipped', 'error', 'interrupted']:
                    self.socketio_emit_phase_update(step['id'], 'skipped', 'Skipped due to earlier interruption.')

        except Exception as e:
            self.socketio_emit_log(f"An unexpected error occurred during agent run: {e}", "ERROR")
            self.logger.exception("Unhandled error in agent run:")
            if self._current_phase_id:
                self.socketio_emit_phase_update(self._current_phase_id, 'error', f"Run failed: {e}")
            stats.error_count += 1 # Ensure this error is counted.
        finally:
            self._is_running = False
            # Use unified logging system for agent status updates
            if hasattr(self, 'unified_logger') and self.unified_logger:
                self.unified_logger.emit_agent_status({
                    'is_running': False,
                    'active_run_preferences': None
                })
            elif self.socketio:
                self.socketio.emit('agent_status', {
                    'is_running': False,
                    'active_run_preferences': None
                })
            overall_duration = time.time() - overall_start_time
            self.socketio_emit_log(f"Knowledge Base Agent run finished in {overall_duration:.2f} seconds.", "INFO")
            
            # Ensure all expected attributes exist on stats before trying to access them
            summary_message = (
                f"Run Summary: "
                f"Processed in this run: {getattr(stats, 'tweets_processed_current_run', 0)}. "
                f"KB Items Created: {getattr(stats, 'kb_items_created', 0)}. "
                f"Total Errors: {getattr(stats, 'error_count', 0)}."
            )
            self.socketio_emit_log(summary_message, "INFO")
            
            # --- Finalize state in DB ---
            self._is_running = False
            final_db_state = {
                'is_running': False,
                'stop_flag_status': False,
                'current_phase_id': None,
                'current_phase_message': summary_message,
                'current_phase_status': 'completed' if stats.error_count == 0 else 'completed_with_errors'
            }
            self._update_state_in_db(**final_db_state)
            # --- End DB Finalization ---

            active_prefs_at_stop = self._current_run_preferences
            self._current_run_preferences = None

            final_plan_statuses = self._plan_statuses.copy() # Get final state of the plan

            completion_data = {
                'summary_message': summary_message,
                'plan_statuses': final_plan_statuses,
            }
            # Use unified logging system for completion updates
            if hasattr(self, 'unified_logger') and self.unified_logger:
                self.unified_logger.emit_agent_status({
                    'agent_run_completed': completion_data
                })
            elif self.socketio:
                self.socketio.emit('agent_run_completed', completion_data)
                # Also emit a final status update from the DB state
                with self.app.app_context():
                    from .models import AgentState
                    final_state = AgentState.query.first()
                    if final_state:
                        self.socketio.emit('agent_status_update', final_state.to_dict())

            
            if self.http_client:
                await self.http_client.close() # This remains async as http_client.close is async
            
        return {
            "status": "completed" if stats.error_count == 0 else "completed_with_errors",
            "message": summary_message,
            "processed_count": stats.processed_count,
            "error_count": stats.error_count
        }

    def get_current_state(self) -> Dict[str, Any]:
        """Returns the current operational state of the agent from the database."""
        if not self.app:
            self.logger.warning("Cannot get state from DB: No Flask app context.")
            # Fallback to in-memory state if no app context
            serializable_preferences = None
            if self._current_run_preferences:
                try:
                    serializable_preferences = asdict(self._current_run_preferences)
                except Exception:
                    serializable_preferences = str(self._current_run_preferences)
            return {
                'is_running': self._is_running,
                'current_phase_id': self._current_phase_id,
                'current_phase_message': self._current_phase_message,
                'current_phase_status': self._current_phase_status,
                'current_run_preferences': serializable_preferences,
                'plan_statuses': self._plan_statuses,
                'stop_flag_status': stop_flag.is_set(),
            }

        with self.app.app_context():
            from .models import AgentState
            state = AgentState.query.first()
            if state:
                return state.to_dict()
            else:
                self.logger.error("AgentState not found in database, returning empty state.")
                return {'is_running': False, 'current_phase_message': 'Error: State not found in DB'}

    def _initialize_plan_statuses(self, preferences: Optional[UserPreferences] = None):
        """Initializes or resets plan statuses, optionally considering user preferences for initial 'skipped' states."""
        base_plan = self.initialize_and_get_execution_plan_steps(preferences if preferences else load_user_preferences(self.config))
        for step in base_plan:
            self._plan_statuses[step['id']] = {'status': step['initial_status'], 'message': step['initial_message']}

    def initialize_and_get_execution_plan_steps(self, preferences: UserPreferences) -> List[Dict[str, Any]]:
        """Defines the agent's execution plan steps with initial status based on preferences."""
        self.socketio_emit_log(f"DEBUG_INIT_PLAN: Prefs object: {preferences}", "DEBUG")
        self.socketio_emit_log(f"DEBUG_INIT_PLAN: Prefs type: {type(preferences)}", "DEBUG")
        self.socketio_emit_log(f"DEBUG_INIT_PLAN: Has skip_fetch_bookmarks: {hasattr(preferences, 'skip_fetch_bookmarks')}", "DEBUG")
        
        plan = [
            {
                "id": "user_input_parsing",
                "name": "Parse User Preferences",
                "icon": "bi-sliders",
                "initial_status": "pending",
                "initial_message": "Waiting to parse user preferences..."
            },
            {
                "id": "fetch_bookmarks",
                "name": "Fetch New Bookmarks",
                "icon": "bi-bookmark-star",
                "initial_status": "skipped" if preferences.skip_fetch_bookmarks else "pending",
                "initial_message": "User preference: Skip fetching new bookmarks" if preferences.skip_fetch_bookmarks else "Waiting to fetch new bookmarks..."
            },
            {
                "id": "content_processing_overall",
                "name": "Process Content",
                "icon": "bi-gear-wide-connected",
                "initial_status": "skipped" if preferences.skip_process_content else "pending",
                "initial_message": "User preference: Skip content processing" if preferences.skip_process_content else "Waiting for content processing..."
            },
            # Sub-phases of content_processing_overall are handled by ContentProcessor's phase_emitter
            # and will update the UI dynamically. They are not typically "planned" from the agent's top level in the same way.
            {
                "id": "synthesis_generation",
                "name": "Generate Subcategory Syntheses",
                "icon": "bi-lightbulb",
                "initial_status": "skipped" if preferences.skip_synthesis_generation else "pending",
                "initial_message": "User preference: Skip synthesis generation" if preferences.skip_synthesis_generation else "Waiting for synthesis generation..."
            },
            {
                "id": "embedding_generation",
                "name": "Generate Embeddings",
                "icon": "bi-gpu-card", # Example icon
                "initial_status": "skipped" if preferences.skip_embedding_generation else "pending",
                "initial_message": "User preference: Skip embedding generation" if preferences.skip_embedding_generation else "Waiting for embedding generation..."
            },
            {
                "id": "readme_generation",
                "name": "Root README Generation",
                "icon": "bi-file-earmark-text",
                "initial_status": "skipped" if preferences.skip_readme_generation else "pending",
                "initial_message": "User preference: Skip Readme generation" if preferences.skip_readme_generation else "Waiting for Root README generation..."
            },
            {
                "id": "database_sync",
                "name": "Database Synchronization",
                "icon": "bi-database",
                "initial_status": "forced" if preferences.force_reprocess_db_sync else ("skipped" if preferences.skip_process_content else "pending"),
                "initial_message": "Force flag: Database sync will be forced" if preferences.force_reprocess_db_sync else ("User preference: Skip content processing" if preferences.skip_process_content else "Waiting for database synchronization...")
            },
            {
                "id": "git_sync",
                "name": "Git Synchronization",
                "icon": "bi-git",
                "initial_status": "skipped" if preferences.skip_git_push else "pending",
                "initial_message": "User preference: Skip Git push" if preferences.skip_git_push else "Waiting for Git synchronization..."
            }
        ]
        return plan

    async def process_tweet(self, tweet_id: str, preferences: Optional[UserPreferences] = None):
        """
        Process a single tweet URL: Cache it if not cached, add to unprocessed queue, 
        then run full content processing pipeline for this single tweet.
        This is an intensive operation for a single item, usually for testing or manual adds.
        """
        if stop_flag.is_set():
            self.socketio_emit_log(f"Skipping single tweet processing for {tweet_id} due to stop flag.", "INFO")
            return
        
        self.socketio_emit_log(f"Starting processing for single tweet: {tweet_id}", "INFO")

        try:
            with current_app.app_context():
                tweet_data = await self.state_manager.get_tweet(tweet_id)
                from knowledge_base_agent.tweet_cacher import cache_tweets
                if not tweet_data or not tweet_data.get('cache_complete'):
                    self.socketio_emit_log(f"Tweet {tweet_id} not fully cached, attempting to cache now...", "INFO")
                    await cache_tweets([tweet_id], self.config, self.http_client, self.state_manager, force_recache=True) 
                    tweet_data = await self.state_manager.get_tweet(tweet_id)
                    if not tweet_data or not tweet_data.get('cache_complete'):
                        self.socketio_emit_log(f"Failed to fetch and cache tweet {tweet_id} for single processing.", "ERROR")
                        raise ContentProcessingError(f"Failed to fetch/cache tweet {tweet_id}.")

                processing_state = await self.state_manager.get_processing_state(tweet_id)
                is_processed = processing_state.get("fully_processed", False)
                unprocessed_queue = await self.state_manager.get_unprocessed_tweets()
                
                if not is_processed and tweet_id not in unprocessed_queue:
                    await self.state_manager.add_tweets_to_unprocessed([tweet_id])
                    self.socketio_emit_log(f"Added tweet {tweet_id} to unprocessed list for dedicated processing.", "INFO")
                elif is_processed:
                    self.socketio_emit_log(f"Tweet {tweet_id} is already marked as processed. To re-process, use batch options with force flags or clear state.", "WARNING")
                    return

                effective_prefs = preferences if preferences else load_user_preferences(self.config)
                # For single tweet, don't skip content processing even if global pref is set.
                # However, keep other force flags.
                # This is tricky because process_all_tweets expects a UserPreferences object.
                # For now, let's assume if the user calls process_tweet, they want it processed.
                # We'll rely on force_recache_tweets and force_reprocess_content from the passed `preferences`.

                # Ensure content processor is initialized before use
                if not self.content_processor:
                    await self.initialize()
                assert self.content_processor is not None
                
                phase_details = await self.content_processor.process_all_tweets(
                    preferences=effective_prefs, # Pass the potentially modified preferences
                    unprocessed_tweets=[tweet_id],
                    total_tweets_for_processing=1,
                    stats=self.stats,
                    category_manager=self.category_manager
                )

                if phase_details:
                    self.socketio_emit_log(f"Successfully processed single tweet {tweet_id}. KB item created/updated.", "INFO")
                    if not effective_prefs.skip_readme_generation:
                        await self.regenerate_readme(effective_prefs)
                    if not effective_prefs.skip_git_push:
                        self.socketio_emit_log(f"Attempting Git sync after single tweet processing for {tweet_id}...", "INFO")
                        self.git_handler.sync_to_github(f"Update/add KB item for tweet {tweet_id}") # Changed to sync call
                        self.socketio_emit_log(f"Git sync successful for tweet {tweet_id}.", "INFO")
                else:
                    self.socketio_emit_log(f"Single tweet processing for {tweet_id} completed, but KB item was not reported as created/updated by content_processor. Check logs.", "ERROR")

        except Exception as e:
            self.socketio_emit_log(f"Failed to process single tweet {tweet_id}: {e}", "ERROR")

    async def execute_standalone_db_sync(self, preferences: UserPreferences) -> None:
        """
        Execute standalone database sync phase.
        
        This method runs database synchronization independently of content processing,
        allowing it to be forced even when no new tweets need processing.
        """
        self.socketio_emit_log("🚀 DB Sync: Method called - starting database sync evaluation...", "INFO")
        self.socketio_emit_phase_update('database_sync', 'active', 'Starting database sync evaluation...')
        
        try:
            self.socketio_emit_log("🔍 DB Sync: Getting all tweets from state manager...", "INFO")
            # Get all tweets for potential database sync
            try:
                all_tweets = await self.state_manager.get_all_tweets()
                self.socketio_emit_log(f"🔍 DB Sync: Successfully retrieved {len(all_tweets) if all_tweets else 0} tweets", "INFO")
            except Exception as e:
                self.socketio_emit_log(f"❌ DB Sync: Error getting tweets from state manager: {e}", "ERROR")
                self.socketio_emit_log(f"❌ DB Sync: Traceback: {traceback.format_exc()}", "ERROR")
                raise
            
            if not all_tweets:
                self.socketio_emit_log("No tweets found in system for database sync", "INFO")
                self.socketio_emit_phase_update('database_sync', 'completed', 'No tweets to sync', False, 0, 0, 0)
                return
            
            self.socketio_emit_log(f"🔍 DB Sync: Found {len(all_tweets)} tweets in system", "DEBUG")
            
            # Create force flags for phase execution helper
            force_flags = {
                'force_recache_tweets': preferences.force_recache_tweets,
                'force_reprocess_media': preferences.force_reprocess_media,
                'force_reprocess_llm': preferences.force_reprocess_llm,
                'force_reprocess_kb_item': preferences.force_reprocess_kb_item,
                'force_reprocess_db_sync': preferences.force_reprocess_db_sync
            }
            
            self.socketio_emit_log(f"🔍 DB Sync: Creating execution plans with force flags: {force_flags}", "DEBUG")
            
            # Get execution plan for database sync
            from knowledge_base_agent.phase_execution_helper import ProcessingPhase
            execution_plans = self.phase_execution_helper.create_all_execution_plans(all_tweets, force_flags)
            db_sync_plan = execution_plans[ProcessingPhase.DB_SYNC]
            
            self.socketio_emit_log(f"🔍 DB Sync: Execution plan created successfully", "DEBUG")
            
            self.socketio_emit_log(f"DB sync plan: {db_sync_plan.needs_processing_count} tweets need sync, {db_sync_plan.already_complete_count} already synced", "INFO")
            
            if db_sync_plan.should_skip_phase:
                self.socketio_emit_log(f"✅ Database sync - all {db_sync_plan.already_complete_count} tweets already synced", "INFO")
                self.socketio_emit_phase_update('database_sync', 'completed', 
                                               f'All {db_sync_plan.already_complete_count} tweets already synced',
                                               False, db_sync_plan.already_complete_count, db_sync_plan.already_complete_count, 0)
                return
            
            # Execute database sync for tweets that need it
            self.socketio_emit_log(f"🔄 Syncing {db_sync_plan.needs_processing_count} tweets to database", "INFO")
            self.socketio_emit_phase_update('database_sync', 'active', 
                                           f'Syncing {db_sync_plan.needs_processing_count} tweets to database...',
                                           False, 0, db_sync_plan.needs_processing_count, 0)
            
            # Initialize content processor if needed (for _sync_to_db method)
            if not self.content_processor:
                await self.initialize()
            
            # Process each tweet that needs database sync
            items_successfully_processed = 0
            error_count = 0
            
            for i, tweet_id in enumerate(db_sync_plan.tweets_needing_processing):
                if stop_flag.is_set():
                    self.socketio_emit_log("Database sync stopped by flag.", "WARNING")
                    self.socketio_emit_phase_update('database_sync', 'interrupted', 'Database sync stopped.')
                    break
                
                try:
                    tweet_data = all_tweets[tweet_id]
                    self.socketio_emit_log(f"🔄 Syncing item {i+1} of {db_sync_plan.needs_processing_count} to database", "INFO")
                    
                    # Update progress
                    self.socketio_emit_phase_update('database_sync', 'active', 
                                                   f'Syncing item {i+1} of {db_sync_plan.needs_processing_count}...',
                                                   False, i, db_sync_plan.needs_processing_count, error_count)
                    
                    # Use the content processor's sync method
                    await self.content_processor._sync_to_db(tweet_id, tweet_data, self.category_manager)
                    
                    # Update state manager
                    tweet_data['db_synced'] = True
                    await self.state_manager.update_tweet_data(tweet_id, tweet_data)
                    items_successfully_processed += 1
                    
                    self.socketio_emit_log(f"✅ Database sync complete for item {i+1}", "INFO")
                    
                except Exception as e:
                    self.socketio_emit_log(f"❌ Error syncing tweet {tweet_id} to database: {e}", "ERROR")
                    error_count += 1
                    # Continue with other tweets
            
            # Final status update
            if not stop_flag.is_set():
                if error_count == 0:
                    self.socketio_emit_log(f"✅ Database sync completed successfully for {items_successfully_processed} tweets", "INFO")
                    self.socketio_emit_phase_update('database_sync', 'completed', 
                                                   f'Synced {items_successfully_processed} tweets to database',
                                                   False, items_successfully_processed, db_sync_plan.needs_processing_count, error_count)
                else:
                    self.socketio_emit_log(f"⚠️ Database sync completed with {error_count} errors. {items_successfully_processed} tweets synced successfully", "WARNING")
                    self.socketio_emit_phase_update('database_sync', 'completed', 
                                                   f'Synced {items_successfully_processed} tweets with {error_count} errors',
                                                   False, items_successfully_processed, db_sync_plan.needs_processing_count, error_count)
            
        except Exception as e:
            self.socketio_emit_log(f"❌ Critical error in standalone database sync: {e}", "ERROR")
            self.socketio_emit_log(f"❌ DB Sync traceback: {traceback.format_exc()}", "ERROR")
            self.socketio_emit_phase_update('database_sync', 'error', f'Database sync failed: {e}')
            # Don't raise - let the pipeline continue with other phases

    async def regenerate_readme(self, preferences: UserPreferences) -> None:
        """
        Regenerate the root README file with intelligent dependency tracking.

        This method regenerates the main README file for the knowledge base only if needed,
        based on changes to Knowledge Base items since the last README generation.
        Uses intelligent tracking similar to synthesis generation.

        Raises:
            MarkdownGenerationError: If README regeneration fails completely.
        """
        if stop_flag.is_set():
            self.socketio_emit_log("Skipping README regeneration due to stop request.", "INFO")
            self.socketio_emit_phase_update('readme_generation', 'skipped', 'Stop flag active.')
            return
        
        from knowledge_base_agent.readme_generator import generate_root_readme, generate_static_root_readme
        self.socketio_emit_log("Starting README dependency analysis...", "INFO")
        
        # Import and initialize README dependency tracker
        from knowledge_base_agent.readme_tracker import ReadmeDependencyTracker
        readme_tracker = ReadmeDependencyTracker(self.config)
        
        # Emit phase start update with dependency analysis
        self.socketio_emit_phase_update(
            'readme_generation', 
            'in_progress', 
            'Analyzing README dependencies and staleness...',
            is_sub_step_update=False
        )

        try:
            # Analyze if README needs regeneration
            execution_plan = readme_tracker.create_readme_execution_plan(
                force_regenerate=getattr(preferences, 'force_regenerate_readme', False)
            )
            
            analysis = execution_plan['analysis']
            total_kb_items = execution_plan['total_kb_items']
            
            # Log analysis results with synthesis documents
            total_syntheses = analysis.get('total_syntheses', 0)
            total_content = analysis.get('total_content', total_kb_items)
            self.socketio_emit_log(f"README analysis: {total_kb_items} KB items, {total_syntheses} synthesis documents found", "INFO")
            if analysis['readme_exists']:
                self.socketio_emit_log(f"Existing README last modified: {analysis['readme_last_modified']}", "INFO")
            
            if not execution_plan['needs_generation']:
                skip_reason = execution_plan['skip_reason']
                if skip_reason == 'up_to_date':
                    self.socketio_emit_log("README is up to date - no regeneration needed", "INFO")
                    self.socketio_emit_phase_update(
                        'readme_generation',
                        'completed',
                        f'README up to date (covers {total_kb_items} KB items, {total_syntheses} synthesis docs)',
                        is_sub_step_update=False,
                        processed_count=total_content,
                        total_count=total_content,
                        error_count=0
                    )
                elif skip_reason == 'no_kb_items':
                    self.socketio_emit_log("No KB items found - skipping README generation", "INFO") 
                    self.socketio_emit_phase_update(
                        'readme_generation',
                        'completed',
                        'No KB items to catalog in README',
                        is_sub_step_update=False,
                        processed_count=0,
                        total_count=0,
                        error_count=0
                    )
                return
            
            # README needs regeneration
            if execution_plan['force_regenerate']:
                self.socketio_emit_log("README regeneration forced by user preference", "INFO")
            else:
                reason = analysis['staleness_reason']
                if reason == 'missing':
                    self.socketio_emit_log("README.md does not exist - generating new README", "INFO")
                elif reason == 'content_updated_after_readme' or reason == 'items_updated_after_readme':
                    new_items = analysis.get('new_items_since_readme', 0)
                    updated_items = analysis.get('updated_items_since_readme', 0)
                    new_syntheses = analysis.get('new_syntheses_since_readme', 0)
                    updated_syntheses = analysis.get('updated_syntheses_since_readme', 0)
                    
                    content_summary = []
                    if new_items > 0:
                        content_summary.append(f"{new_items} new KB items")
                    if updated_items > 0:
                        content_summary.append(f"{updated_items} updated KB items")
                    if new_syntheses > 0:
                        content_summary.append(f"{new_syntheses} new synthesis documents")
                    if updated_syntheses > 0:
                        content_summary.append(f"{updated_syntheses} updated synthesis documents")
                    
                    if content_summary:
                        self.socketio_emit_log(
                            f"README is stale: {', '.join(content_summary)} since last README", 
                            "INFO"
                        )
                    else:
                        self.socketio_emit_log("README is stale: content updated since last README", "INFO")
            
            # Emit progress update for generation start
            self.socketio_emit_phase_update(
                'readme_generation', 
                'in_progress', 
                f'Generating README for {total_kb_items} KB items, {total_syntheses} synthesis docs...',
                is_sub_step_update=False,
                processed_count=0,
                total_count=total_content,
                error_count=0
            )

            logging.info("Starting README regeneration")
            readme_path = self.config.knowledge_base_dir / "README.md"
            
            try:
                await generate_root_readme(
                    self.config.knowledge_base_dir,
                    self.category_manager,
                    self.http_client,
                    self.config
                )
                logging.info("Generated intelligent README")
                self.socketio_emit_log("Intelligent README generated successfully.", "INFO")
            except Exception as e:
                logging.warning(f"Intelligent README generation failed: {e}")
                self.socketio_emit_log(f"Intelligent README generation failed: {e}. Attempting static fallback.", "WARNING")
                content = await generate_static_root_readme(
                    self.config.knowledge_base_dir,
                    self.category_manager
                )
                async with aiofiles.open(readme_path, 'w', encoding='utf-8') as f:
                    await f.write(content)
                logging.info("Generated static README as fallback.")
                self.socketio_emit_log("Static README generated as fallback.", "INFO")
            
            # Emit completion phase update
            self.socketio_emit_phase_update(
                'readme_generation',
                'completed',
                f'README regeneration completed for {total_kb_items} KB items, {total_syntheses} synthesis docs',
                is_sub_step_update=False,
                processed_count=total_content,
                total_count=total_content,
                error_count=0
            )
                
        except Exception as e:
            logging.error(f"README regeneration failed: {e}")
            self.socketio_emit_log(f"README regeneration completely failed: {e}", "ERROR")
            
            # Emit error phase update
            self.socketio_emit_phase_update(
                'readme_generation',
                'error',
                f'README regeneration failed: {e}',
                is_sub_step_update=False
            )
            
            raise MarkdownGenerationError(f"Failed to regenerate README: {e}")

    async def generate_synthesis(self, preferences: UserPreferences) -> None:
        """Generates synthesis documents for all eligible subcategories with proper phase tracking."""
        
        from knowledge_base_agent.synthesis_generator import generate_syntheses
        # Check if we have access to Flask app context (required for database operations)
        if not self.app:
            self.logger.info("Skipping synthesis generation - no Flask app context available (running in subprocess mode)")
            self.socketio_emit_phase_update('synthesis_generation', 'skipped', 'Skipped - no database access in subprocess mode')
            return
        
        try:
            with self.app.app_context():
                # Create a custom phase emitter that also updates the dynamic phase estimator
                def enhanced_phase_emitter(phase_id, status, message, is_sub_step_update=False, 
                                         processed_count=None, total_count=None, error_count=None, 
                                         initial_estimated_duration_seconds=None):
                    
                    # Call the standard phase emitter
                    self.socketio_emit_phase_update(
                        phase_id, status, message, is_sub_step_update, 
                        processed_count, total_count, error_count, 
                        initial_estimated_duration_seconds
                    )
                    
                    # If this is the initial phase setup with total count, initialize tracking
                    if (phase_id == "synthesis_generation" and 
                        not is_sub_step_update and 
                        status == "in_progress" and 
                        total_count and total_count > 0 and 
                        processed_count == 0):
                        
                        self.logger.info(f"Initializing dynamic phase tracking for synthesis_generation with {total_count} items")
                        historical_duration = self.phase_estimator.initialize_phase_tracking(phase_id, total_count)
                        if historical_duration:
                            self.logger.info(f"Using historical average for synthesis ETC: {historical_duration:.1f}s total")
                    
                    # If we have progress updates, update the estimator
                    elif (phase_id == "synthesis_generation" and 
                          not is_sub_step_update and 
                          processed_count is not None):
                        
                        estimation_result = self.phase_estimator.update_phase_progress(phase_id, processed_count)
                        if estimation_result:
                            etc_minutes = estimation_result.get('estimated_remaining_minutes', 0)
                            self.logger.debug(f"Updated synthesis ETC: {etc_minutes:.1f} minutes remaining")
                
                syntheses, eligible_count, error_count = await generate_syntheses(
                    self.config,
                    self.http_client,
                    preferences,
                    self.socketio,
                    enhanced_phase_emitter
                )
                
                # Finalize phase tracking when complete
                if eligible_count > 0:
                    self.phase_estimator.finalize_phase("synthesis_generation")
                    self.logger.info(f"Finalized synthesis generation phase tracking")
                
        except RuntimeError as e:
            if "Working outside of application context" in str(e):
                self.logger.info("Skipping synthesis generation - no Flask app context available")
                self.socketio_emit_phase_update('synthesis_generation', 'skipped', 'Skipped - database context not available')
                return
            else:
                raise
        
        if error_count > 0:
            self.logger.warning(f"Synthesis generation completed with {error_count} errors.")
        else:
            self.logger.info("Synthesis generation completed successfully.")
            
        # The final phase status ('completed' or 'error') will be emitted by the execute_phase wrapper
        # based on whether this function raises an exception or not.

    async def generate_embeddings(self, preferences: UserPreferences) -> None:
        """Generates embeddings for all knowledge base items."""
        if not self.embedding_manager:
            self.logger.warning("Embedding manager not initialized, skipping embedding generation.")
            self.socketio_emit_phase_update('embedding_generation', 'skipped', 'Embedding manager not initialized')
            return
            
        # Check if we have access to Flask app context (required for database operations)
        if not self.app:
            self.logger.info("Skipping embedding generation - no Flask app context available (running in subprocess mode)")
            self.socketio_emit_phase_update('embedding_generation', 'skipped', 'Skipped - no database access in subprocess mode')
            return
        
        try:
            with self.app.app_context():
                await self.embedding_manager.generate_all_embeddings(
                    force_regenerate=preferences.force_regenerate_embeddings,
                    phase_emitter_func=self.socketio_emit_phase_update
                )
        except RuntimeError as e:
            if "Working outside of application context" in str(e):
                self.logger.info("Skipping embedding generation - no Flask app context available")
                self.socketio_emit_phase_update('embedding_generation', 'skipped', 'Skipped - database context not available')
                return
            else:
                raise

    async def handle_chat_query(self, query: str, model: Optional[str] = None) -> Dict[str, Any]:
        """Handles a chat query from the user."""
        if not self.chat_manager:
            self.logger.error("Chat manager is not initialized.")
            return {"error": "Chat functionality is not available."}
        
        return await self.chat_manager.handle_chat_query(query, model=model)
    
    def create_phase_enhancement(self) -> 'AgentPhaseEventEnhancement':
        """
        Create an AgentPhaseEventEnhancement for this agent.
        
        This method creates a phase enhancement wrapper that provides
        comprehensive event emission for all processing phases.
        
        Returns:
            AgentPhaseEventEnhancement: Enhanced phase event handler
            
        Raises:
            ValueError: If no task_id is available for event emission
        """
        if not self.task_id:
            raise ValueError("Cannot create phase enhancement without task_id")
        
        from .agent_phase_event_enhancement import AgentPhaseEventEnhancement
        return AgentPhaseEventEnhancement(self, self.task_id, self.config)

class InterruptedError(Exception):
    """Custom exception for when processing is interrupted by the stop flag."""
    pass