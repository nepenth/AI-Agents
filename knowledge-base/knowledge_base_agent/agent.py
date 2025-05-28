"""
Main agent module coordinating knowledge base operations.

This module contains the core logic for the Knowledge Base Agent, which automates the process of fetching, processing, categorizing, and generating content for a structured knowledge base. It integrates various components to ensure seamless operation and data management.
"""

import logging
from typing import Set, List, Dict, Any, Optional
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

from knowledge_base_agent.config import Config, load_config
from knowledge_base_agent.exceptions import AgentError, MarkdownGenerationError
from knowledge_base_agent.state_manager import StateManager
from knowledge_base_agent.git_helper import GitSyncHandler
from knowledge_base_agent.fetch_bookmarks import BookmarksFetcher
from knowledge_base_agent.markdown_writer import MarkdownWriter
from knowledge_base_agent.readme_generator import generate_root_readme, generate_static_root_readme
from knowledge_base_agent.category_manager import CategoryManager
from knowledge_base_agent.types import TweetData, KnowledgeBaseItem
from knowledge_base_agent.prompts import UserPreferences, load_user_preferences
from knowledge_base_agent.progress import ProcessingStats, PhaseDetail
from knowledge_base_agent.content_processor import ContentProcessingError
from knowledge_base_agent.tweet_utils import parse_tweet_id_from_url
from knowledge_base_agent.file_utils import async_json_load
from knowledge_base_agent.http_client import HTTPClient
from knowledge_base_agent.content_processor import ContentProcessor
from knowledge_base_agent.tweet_cacher import cache_tweets, TweetCacheValidator
from knowledge_base_agent.shared_globals import stop_flag, clear_stop_flag, sg_get_project_root, sg_set_project_root
from knowledge_base_agent.models import db

# Default phase IDs - ensure these match your UI elements' IDs
DEFAULT_PHASE_IDS = [
    "user_input_parsing",
    "fetch_bookmarks",
    "content_processing_overall",
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
    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    
    file_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    console_formatter = logging.Formatter('%(message)s')

    file_handler = logging.FileHandler(config.log_file)
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(file_formatter)

    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(console_formatter)
    
    class TweetProgressFilter(logging.Filter):
        def filter(self, record):
            msg = record.getMessage()
            return not any(x in msg for x in [
                'Caching data for',
                'Tweet caching completed',
                '✓ Cached tweet'
            ])
    
    console_handler.addFilter(TweetProgressFilter())

    root_logger.setLevel(logging.DEBUG)
    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)

    logging.getLogger('httpx').setLevel(logging.WARNING)
    logging.getLogger('playwright').setLevel(logging.WARNING)

class KnowledgeBaseAgent:
    """
    Main agent coordinating knowledge base operations.

    The KnowledgeBaseAgent class is the central component of the knowledge base system. It orchestrates
    the fetching of content from various sources, processes and categorizes this content, manages state,
    and generates structured outputs. It integrates with other modules to ensure a seamless workflow.

    Attributes:
        config (Config): Configuration object for the agent.
        http_client (HTTPClient): Client for making HTTP requests.
        state_manager (StateManager): Manages the state of processed and unprocessed content.
        category_manager (CategoryManager): Handles content categorization.
        content_processor (ContentProcessor): Processes content for the knowledge base.
        _processing_lock (asyncio.Lock): Lock to prevent concurrent processing issues.
        git_handler (GitSyncHandler): Handles synchronization with Git repositories.
        stats (ProcessingStats): Tracks processing statistics.
        _initialized (bool): Flag indicating if the agent has been initialized.
        socketio (SocketIO, optional): SocketIO instance for real-time updates.
        _is_running (bool): Flag indicating if the agent is currently running.
        _current_phase_id (Optional[str]): Current phase ID.
        _current_phase_message (Optional[str]): Current phase message.
        _current_phase_status (Optional[str]): Current phase status.
        _current_run_preferences (Optional[UserPreferences]): Current run preferences.
        _plan_statuses (Dict[str, Dict[str, str]]): Stores {'phase_id': {'status': '...', 'message': '...'}}
        
        # Time estimation tracking
        _phase_start_times = {}
        _phase_item_processing_times = defaultdict(list)
        _phase_total_items = {}
        _phase_processed_items = {}
        _phase_estimated_completion_times = {}
    """
    
    def __init__(self, app, config: Config, socketio: Optional[SocketIO] = None):
        """
        Initialize the agent with configuration.

        Args:
            config (Config): Configuration object containing settings for the agent.
            socketio (Optional[SocketIO]): SocketIO instance for real-time updates.
        """
        self.app = app
        self.config = config
        self.http_client = HTTPClient(config)
        self.state_manager = StateManager(config)
        self.category_manager = CategoryManager(config, http_client=self.http_client)
        self.socketio = socketio
        self.content_processor = ContentProcessor(
            config=config,
            http_client=self.http_client,
            state_manager=self.state_manager,
            socketio=socketio,
            phase_emitter_func=self.socketio_emit_phase_update
        )
        self._processing_lock = asyncio.Lock()
        self.git_handler = GitSyncHandler(config)
        self.stats = ProcessingStats(start_time=datetime.now())
        self._initialized = False
        self.tweet_processor = TweetCacheValidator(config)
        self._is_running = False
        self._current_phase_id = None
        self._current_phase_message = None
        self._current_phase_status = None
        self._current_run_preferences = None
        self._plan_statuses = {}
        
        # Time estimation tracking
        self._phase_start_times = {}
        self._phase_item_processing_times = defaultdict(list)
        self._phase_total_items = {}
        self._phase_processed_items = {}
        self._phase_estimated_completion_times = {}
        
        self.logger = logging.getLogger(__name__)
        logging.info("KnowledgeBaseAgent initialized")

    def socketio_emit_log(self, message: str, level: str = "INFO") -> None:
        """Emit a log message via socketio and logging module."""
        logging.log(getattr(logging, level.upper(), logging.INFO), message)
        if self.socketio:
            self.socketio.emit('log', {'message': message, 'level': level.upper()})

    def socketio_emit_phase_update(self, 
                                 phase_id: str, 
                                 status: str, 
                                 message: str, 
                                 is_sub_step_update: bool = False,
                                 processed_count: Optional[int] = None,
                                 total_count: Optional[int] = None,
                                 error_count: Optional[int] = None,
                                 initial_estimated_duration_seconds: Optional[float] = None):
        """Emits a phase update via SocketIO and updates internal agent state."""
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
        self.logger.info(log_message)

        # Track timing and estimate completion
        current_time = time.time()
        estimated_completion_time = None
        estimated_remaining_minutes = None
        
        # Handle timing for non-substep updates (main phases)
        if not is_sub_step_update:
            # When a phase starts, record the start time and historical ETC if provided
            if status == 'active' or status == 'in_progress':
                if phase_id not in self._phase_start_times:
                    self._phase_start_times[phase_id] = current_time
                
                if initial_estimated_duration_seconds is not None and initial_estimated_duration_seconds > 0:
                    self._phase_estimated_completion_times[phase_id] = current_time + initial_estimated_duration_seconds
                    self.logger.info(f"Historical ETC for {phase_id} set: ends at {self._phase_estimated_completion_times[phase_id]} (in {initial_estimated_duration_seconds:.0f}s)")
                
                if total_count is not None and total_count > 0:
                    self._phase_total_items[phase_id] = total_count
                    self._phase_processed_items[phase_id] = processed_count if processed_count is not None else 0
            
            # When a phase ends, clear its timing data
            if status in ['completed', 'error', 'skipped', 'interrupted']:
                self._phase_start_times.pop(phase_id, None)
                self._phase_estimated_completion_times.pop(phase_id, None)
                self._phase_item_processing_times.pop(phase_id, None)
                self._phase_total_items.pop(phase_id, None)
                self._phase_processed_items.pop(phase_id, None)
        
        # Determine the ETC to send to UI
        final_etc_timestamp_to_send = self._phase_estimated_completion_times.get(phase_id)
        
        # Dynamic ETC calculation (can be a fallback or refinement)
        dynamic_etc_timestamp = None
        if processed_count is not None and total_count is not None and total_count > 0:
            phase_key = phase_id
            
            previous_processed = self._phase_processed_items.get(phase_key, 0)
            if processed_count > previous_processed:
                items_just_processed = processed_count - previous_processed
                
                batch_start_time = self._phase_start_times.get(phase_key, current_time)
                
                elapsed_since_batch_start = current_time - batch_start_time
                
                if elapsed_since_batch_start > 1 and items_just_processed > 0:
                    time_per_item = elapsed_since_batch_start / items_just_processed
                    self._phase_item_processing_times[phase_key].append(time_per_item)
                    
                    if len(self._phase_item_processing_times[phase_key]) > 10:
                        self._phase_item_processing_times[phase_key] = self._phase_item_processing_times[phase_key][-10:]
            
            self._phase_processed_items[phase_key] = processed_count

            if self._phase_item_processing_times[phase_key]:
                median_time_per_item = median(self._phase_item_processing_times[phase_key])
                remaining_items = total_count - processed_count
                if remaining_items > 0 and median_time_per_item > 0:
                    dynamic_etc_timestamp = current_time + (remaining_items * median_time_per_item)

        # Prefer historical ETC if available, otherwise use dynamic if calculated
        if final_etc_timestamp_to_send is None and dynamic_etc_timestamp is not None:
            final_etc_timestamp_to_send = dynamic_etc_timestamp

        # Update agent's overall phase state (non-sub-step only)
        if not is_sub_step_update:
            self._current_phase_id = phase_id
            self._current_phase_message = message
            self._current_phase_status = status
            if phase_id in DEFAULT_PHASE_IDS or phase_id.startswith("subphase_cp_"):
                self._plan_statuses[phase_id] = {'status': status, 'message': message, 'sub_step': False}

        # Prepare data for SocketIO emit
        data_to_emit = {
            'phase_id': phase_id,
            'status': status,
            'message': message,
            'is_sub_step_update': is_sub_step_update,
            'processed_count': processed_count,
            'total_count': total_count,
            'error_count': error_count,
            'initial_estimated_duration_seconds': initial_estimated_duration_seconds,
            'estimated_completion_timestamp': final_etc_timestamp_to_send
        }
        
        if self.socketio:
            self.socketio.emit('agent_phase_update', data_to_emit)

        # If overall content processing is done, update its status based on sub-phases
        if phase_id.startswith("subphase_cp_") and status in ['completed', 'error', 'skipped', 'interrupted']:
            pass

    async def initialize(self) -> None:
        """
        Initialize all components and ensure directory structure.

        This method sets up the necessary directories and initializes the state and category managers.
        It ensures that the agent is ready to process content.

        Raises:
            AgentError: If initialization fails due to directory creation or component setup issues.
        """
        self.socketio_emit_log("Agent initialization process started.", "INFO")
        try:
            self.socketio_emit_log("Creating required directories...", "DEBUG")
            self.config.knowledge_base_dir.mkdir(parents=True, exist_ok=True)
            self.config.data_processing_dir.mkdir(parents=True, exist_ok=True)
            self.config.media_cache_dir.mkdir(parents=True, exist_ok=True)
            
            self.socketio_emit_log("Initializing state manager...", "DEBUG")
            await self.state_manager.initialize()
            
            self.socketio_emit_log("Initializing category manager...", "DEBUG")
            await self.category_manager.initialize()
            
            if self.socketio and self.content_processor:
                if not self.content_processor.socketio:
                    self.content_processor.socketio = self.socketio
                if self.content_processor.phase_emitter_func != self.socketio_emit_phase_update:
                    self.content_processor.phase_emitter_func = self.socketio_emit_phase_update

            self._initialized = True
            self.socketio_emit_log("Agent initialization complete.", "INFO")
        except Exception as e:
            logging.exception(f"Agent initialization failed: {str(e)}")
            self.socketio_emit_log(f"Agent initialization failed: {str(e)}", "ERROR")
            self.socketio_emit_phase_update('initialization', 'error', f'Initialization failed: {str(e)}')
            raise AgentError(f"Failed to initialize agent: {str(e)}") from e

    async def fetch_and_queue_bookmarks(self) -> int:
        """
        Fetches bookmarks and adds new, unprocessed tweet IDs to the state manager's queue.
        Does not trigger full processing on its own.

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
                
                is_processed = await self.state_manager.is_tweet_processed(tweet_id)
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
                is_processed = await self.state_manager.is_tweet_processed(tweet_id)
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
                return
            logging.info("Starting GitHub sync...")
            await self.git_handler.sync_to_github("Update knowledge base content")
            logging.info("GitHub sync completed successfully")
        except Exception as e:
            logging.exception(f"GitHub sync failed: {str(e)}") # Log with stack trace
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
        self.socketio_emit_log(f"DEBUG_AGENT_RUN: Prefs object received by run(): {preferences}", "DEBUG")
        self.socketio_emit_log(f"DEBUG_AGENT_RUN: Prefs type in run(): {type(preferences)}", "DEBUG")
        self.socketio_emit_log(f"DEBUG_AGENT_RUN: In run(), hasattr skip_fetch_bookmarks: {hasattr(preferences, 'skip_fetch_bookmarks')}", "DEBUG")
        self.socketio_emit_log(f"DEBUG_AGENT_RUN: In run(), hasattr skip_fetching_new_bookmarks: {hasattr(preferences, 'skip_fetching_new_bookmarks')}", "DEBUG")

        if self._is_running:
            self.socketio_emit_log("Agent is already running.", "WARNING")
            return {"status": "already_running", "message": "Agent is already running."}

        self._is_running = True
        self._current_run_preferences = preferences  # Store preferences for state restoration
        if self.socketio:
            self.socketio.emit('agent_status', {
                'is_running': True, 
                'active_run_preferences': asdict(preferences),
                'plan_statuses': self._plan_statuses
            })
        clear_stop_flag() # Clear stop flag at the beginning of a run
        self._initialize_plan_statuses(preferences) # Initialize/reset with current preferences
        self.socketio_emit_log("Knowledge Base Agent run started.", "INFO")
        # Emit initial state for all plan items based on preferences
        for phase_id, status_info in self._plan_statuses.items():
            self.socketio_emit_phase_update(phase_id, status_info['status'], status_info['message'])

        stats = ProcessingStats(start_time=datetime.now())
        phase_details_from_content_processor: List[PhaseDetail] = []

        original_tweet_count = 0
        processed_tweets_in_run = 0
        overall_start_time = time.time()

        try:
            # --- Phase 1: Parse User Preferences (already done by receiving `preferences` object) ---
            self.socketio_emit_phase_update('user_input_parsing', 'completed', 'User preferences parsed and applied.')
            if stop_flag.is_set(): raise InterruptedError("Run stopped by user after parsing preferences.")

            # --- Phase 2: Retrieve New Bookmarks (Optional) ---
            if not preferences.skip_fetch_bookmarks:
                self.socketio_emit_phase_update('fetch_bookmarks', 'in_progress', 'Fetching new bookmarks...')
                try:
                    # Call the actual bookmark fetching implementation
                    newly_added_count = await self.fetch_and_queue_bookmarks()
                    if newly_added_count > 0:
                        completion_message = f'Added {newly_added_count} new bookmarks to processing queue.'
                        self.socketio_emit_log(completion_message, "INFO")
                        self.socketio_emit_phase_update('fetch_bookmarks', 'completed', completion_message)
                    else:
                        completion_message = 'No new bookmarks found to queue for processing.'
                        self.socketio_emit_log(completion_message, "INFO")
                        self.socketio_emit_phase_update('fetch_bookmarks', 'completed', completion_message)
                except Exception as e:
                    self.socketio_emit_log(f"Error fetching bookmarks: {e}", "ERROR")
                    self.socketio_emit_phase_update('fetch_bookmarks', 'error', f"Error fetching bookmarks: {e}")
                    stats.error_count +=1 # Generic error for this phase
            else:
                self.socketio_emit_log("Skipping bookmark fetching due to user preference.", "INFO")
                # Status already set by _initialize_plan_statuses and emitted loop

            if stop_flag.is_set(): raise InterruptedError("Run stopped by user after retrieving bookmarks.")

            # --- Phase 3: Process Content (Optional) ---
            if not preferences.skip_process_content: # Corrected attribute name
                self.socketio_emit_phase_update('content_processing_overall', 'in_progress', 'Starting content processing pipeline...')
                try:
                    # First get unprocessed tweets
                    unprocessed_tweets = await self.state_manager.get_unprocessed_tweets()
                    
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
                    
                    total_tweets_count = len(tweets_to_process)
                    self.socketio_emit_log(f"Found {len(unprocessed_tweets)} unprocessed tweets and {total_tweets_count - len(unprocessed_tweets)} previously processed tweets to process (total: {total_tweets_count}).", "INFO")

                    if total_tweets_count > 0:
                        phase_details_from_content_processor = await self.content_processor.process_all_tweets(
                            preferences=preferences,
                            unprocessed_tweets=tweets_to_process,
                            total_tweets_for_processing=total_tweets_count,
                            stats=stats, # Pass the shared stats object
                            category_manager=self.category_manager
                        )
                        # 'stats' object is mutated by process_all_tweets
                        processed_tweets_in_run = stats.processed_count # Use processed_count from stats, which is updated by CP
                        self.socketio_emit_log(f"Content processing finished. Processed in this run: {processed_tweets_in_run}, Errors: {stats.error_count}", "INFO")
                        self.socketio_emit_phase_update('content_processing_overall', 'completed', f'Processed {processed_tweets_in_run}/{total_tweets_count} items. Errors: {stats.error_count}.')
                    else:
                        if any_force_reprocessing:
                            self.socketio_emit_log("No tweets found to process, even with force reprocessing options enabled. Your knowledge base may be empty.", "INFO")
                        else:
                            self.socketio_emit_log("No unprocessed tweets found. Add new tweets or enable one of the force reprocessing options to reprocess existing items.", "INFO")
                        self.socketio_emit_phase_update('content_processing_overall', 'skipped', 'No tweets to process.')
                except Exception as e:
                    self.socketio_emit_log(f"Error during content processing: {e}", "ERROR")
                    self.socketio_emit_phase_update('content_processing_overall', 'error', f"Error: {e}")
                    stats.error_count +=1 # Generic error for this phase
            else:
                self.socketio_emit_log("Skipping content processing due to user preference.", "INFO")
                # Status already set

            if stop_flag.is_set(): raise InterruptedError("Run stopped by user during content processing.")

            # --- Phase 4: Generate/Update Readmes (Optional) ---
            if not preferences.skip_readme_generation:
                self.socketio_emit_phase_update('readme_generation', 'in_progress', 'Generating/updating Readme files...')
                try:
                    with self.app.app_context():
                        # Corrected call to generate_static_root_readme
                        await generate_static_root_readme(self.config.knowledge_base_dir, self.category_manager)
                        # The generate_root_readme call might also need review, but the error was specific to static one.
                        # Assuming generate_root_readme(self.config, db) is correct or handled elsewhere if it also has issues.
                        # For now, let's assume the main error was with generate_static_root_readme.
                        # If generate_root_readme also needs db, its definition should reflect that.
                        # The original error was: "Error generating Readmes: generate_static_root_readme() takes 2 positional arguments but 3 were given"
                        # This implies generate_root_readme(self.config, db) might be okay or a different issue.
                        # Let's stick to fixing the identified TypeError first.
                        # If generate_root_readme also has an issue, it would be a separate TypeError.
                        # Upon review of readme_generator.py, generate_root_readme expects:
                        # kb_dir: Path, category_manager: CategoryManager, http_client: HTTPClient, config: Config
                        # So, the call should be:
                        await generate_root_readme(self.config.knowledge_base_dir, self.category_manager, self.http_client, self.config)
                    self.socketio_emit_log("Readme files generated/updated successfully.", "INFO")
                    self.socketio_emit_phase_update('readme_generation', 'completed', 'Readme files generated/updated.')
                except Exception as e:
                    self.socketio_emit_log(f"Error generating Readmes: {e}", "ERROR")
                    self.socketio_emit_phase_update('readme_generation', 'error', f"Error generating Readmes: {e}")
                    stats.error_count +=1
            else:
                self.socketio_emit_log("Skipping Readme generation due to user preference.", "INFO")
                # Status already set

            if stop_flag.is_set(): raise InterruptedError("Run stopped by user after Readme generation.")

            # --- Phase 5: Git Synchronization (Optional) ---
            # Use self.config.git_enabled directly as it's a boolean field in the Config model
            if self.config.git_enabled and not preferences.skip_git_push:
                self.socketio_emit_phase_update('git_sync', 'in_progress', 'Starting Git synchronization...')
                try:
                    self.socketio_emit_log("Attempting to add, commit, and push changes to Git...", "INFO")
                    # Ensure stats.tweets_processed_current_run is a valid attribute of stats
                    processed_count_for_commit = getattr(stats, 'tweets_processed_current_run', 0)
                    commit_message = f"Automated KB update: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S %Z')} - {processed_count_for_commit} items processed."
                    
                    await self.git_handler.sync_to_github(commit_message)
                    # self.socketio_emit_log(f"Git sync result: {sync_result}", "INFO") # sync_to_github might not return a string directly
                    self.socketio_emit_log("Git sync completed successfully.", "INFO")
                    self.socketio_emit_phase_update('git_sync', 'completed', 'Git synchronization completed.')

                except Exception as e:
                    self.socketio_emit_log(f"Error during Git synchronization: {e}", "ERROR")
                    self.socketio_emit_phase_update('git_sync', 'error', f"Error during Git sync: {e}")
                    stats.error_count +=1 # Ensure stats is the correct stats object
            elif not self.config.git_enabled:
                self.socketio_emit_log("Skipping Git synchronization: Git is not configured (git_enabled is false).", "WARNING")
                self.socketio_emit_phase_update('git_sync', 'skipped', 'Git not configured (git_enabled is false).')
            else: # skip_git_push is true
                self.socketio_emit_log("Skipping Git synchronization due to user preference.", "INFO")
                self.socketio_emit_phase_update('git_sync', 'skipped', 'Skipped by user preference.')

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
            if self.socketio:
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
            
            self._is_running = False
            self._current_phase_id = None
            self._current_phase_message = None
            self._current_phase_status = None
            active_prefs_at_stop = self._current_run_preferences
            self._current_run_preferences = None

            final_plan_statuses = self._plan_statuses.copy() # Get final state of the plan

            completion_data = {
                'is_running': False,
                'summary_message': summary_message,
                'plan_statuses': final_plan_statuses,
                # active_run_preferences is implicitly handled by client setting it to null on this event
                # final_run_preferences_for_plan is not a standard field for this event, handled internally if needed
            }
            if self.socketio:
                self.socketio.emit('agent_run_completed', completion_data)
            
            if self.http_client:
                await self.http_client.close()
            
        return {
            "status": "completed" if stats.error_count == 0 else "completed_with_errors",
            "message": summary_message,
            "processed_count": stats.processed_count,
            "error_count": stats.error_count
        }

    def get_current_state(self) -> Dict[str, Any]:
        """Returns the current operational state of the agent."""
        # Make sure current_run_preferences is serializable if it's not None
        serializable_preferences = None
        if self._current_run_preferences:
            try:
                serializable_preferences = asdict(self._current_run_preferences)
            except Exception as e:
                self.logger.warning(f"Could not serialize current_run_preferences: {e}")
                serializable_preferences = str(self._current_run_preferences) # Fallback to string

        state = {
            'is_running': self._is_running,
            'current_phase_id': self._current_phase_id,
            'current_phase_message': self._current_phase_message,
            'current_phase_status': self._current_phase_status,
            'current_run_preferences': serializable_preferences,
            'plan_statuses': self._plan_statuses, # For execution plan visualization
            'stop_flag_status': stop_flag.is_set(),
            'phase_estimated_completion_times': self._phase_estimated_completion_times # Send current ETCs
        }
        self.logger.debug(f"Reporting current state - Running: {self._is_running}, Phase: {self._current_phase_id}, Plan items: {len(self._plan_statuses)}")
        return state

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
                "icon": "bi-cloud-download",
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
                "id": "readme_generation",
                "name": "Generate/Update Readmes",
                "icon": "bi-file-earmark-text",
                "initial_status": "skipped" if preferences.skip_readme_generation else "pending",
                "initial_message": "User preference: Skip Readme generation" if preferences.skip_readme_generation else "Waiting for Readme generation..."
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
                if not tweet_data or not tweet_data.get('cache_complete'):
                    self.socketio_emit_log(f"Tweet {tweet_id} not fully cached, attempting to cache now...", "INFO")
                    await cache_tweets([tweet_id], self.config, self.http_client, self.state_manager, force_recache=True) 
                    tweet_data = await self.state_manager.get_tweet(tweet_id)
                    if not tweet_data or not tweet_data.get('cache_complete'):
                        self.socketio_emit_log(f"Failed to fetch and cache tweet {tweet_id} for single processing.", "ERROR")
                        raise ContentProcessingError(f"Failed to fetch/cache tweet {tweet_id}.")

                is_processed = await self.state_manager.is_tweet_processed(tweet_id)
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

                phase_details = await self.content_processor.process_all_tweets(
                    preferences=effective_prefs, # Pass the potentially modified preferences
                    unprocessed_tweets=[tweet_id],
                    total_tweets_for_processing=1,
                    stats=self.stats,
                    category_manager=self.category_manager
                )

                if phase_details:
                    self.socketio_emit_log(f"Successfully processed single tweet {tweet_id}. KB item created/updated.", "INFO")
                    if effective_prefs.regenerate_readme:
                        await self.regenerate_readme()
                    if effective_prefs.git_push and self.config.git_enabled:
                        self.socketio_emit_log(f"Attempting Git sync after single tweet processing for {tweet_id}...", "INFO")
                        await self.git_handler.sync_to_github(f"Update/add KB item for tweet {tweet_id}")
                        self.socketio_emit_log(f"Git sync successful for tweet {tweet_id}.", "INFO")
                else:
                    self.socketio_emit_log(f"Single tweet processing for {tweet_id} completed, but KB item was not reported as created/updated by content_processor. Check logs.", "ERROR")

        except Exception as e:
            self.socketio_emit_log(f"Failed to process single tweet {tweet_id}: {e}", "ERROR")

    async def regenerate_readme(self) -> None:
        """
        Regenerate the root README file.

        This method regenerates the main README file for the knowledge base, attempting to create
        an intelligent version first, falling back to a static version if that fails.

        Raises:
            MarkdownGenerationError: If README regeneration fails completely.
        """
        if stop_flag.is_set():
            self.socketio_emit_log("Skipping README regeneration due to stop request.", "INFO")
            self.socketio_emit_phase_update('readme_generation', 'skipped', 'Stop flag active.')
            return
        
        self.socketio_emit_log("Starting README regeneration process...", "INFO")

        try:
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
                logging.info("Generated static README as fallback")
                self.socketio_emit_log("Static README generated as fallback.", "INFO")
                
        except Exception as e:
            logging.error(f"README regeneration failed: {e}")
            self.socketio_emit_log(f"README regeneration completely failed: {e}", "ERROR")
            raise MarkdownGenerationError(f"Failed to regenerate README: {e}")

    async def _verify_tweet_cached(self, tweet_id: str) -> bool:
        """
        Verify that a tweet exists in the cache.

        Args:
            tweet_id (str): The ID of the tweet to verify.

        Returns:
            bool: True if the tweet is in the cache, False otherwise.
        """
        try:
            cache_file = Path(self.config.tweet_cache_file)
            if not cache_file.exists():
                logging.error("Tweet cache file does not exist")
                return False
            
            cache_data = await async_json_load(cache_file)
            return tweet_id in cache_data
            
        except Exception as e:
            logging.error(f"Error verifying tweet cache for {tweet_id}: {e}")
            return False

    async def _verify_kb_item_created(self, tweet_id: str) -> bool:
        """
        Verify that a knowledge base item was created for the tweet.

        Args:
            tweet_id (str): The ID of the tweet to verify.

        Returns:
            bool: True if a knowledge base item exists for the tweet, False otherwise.
        """
        try:
            cache_file = Path(self.config.tweet_cache_file)
            if not cache_file.exists():
                logging.error("Tweet cache file does not exist")
                return False
            
            cache_data = await async_json_load(cache_file)
            if tweet_id not in cache_data:
                logging.error(f"Tweet {tweet_id} not found in cache")
                return False
            
            tweet_data = cache_data[tweet_id]
            if 'kb_item_path' in tweet_data:
                kb_path = Path(tweet_data['kb_item_path'])
                if kb_path.exists():
                    return True
            
            logging.error(f"No knowledge base item found for tweet {tweet_id}")
            return False
            
        except Exception as e:
            logging.error(f"Error verifying KB item for tweet {tweet_id}: {e}")
            return False

    async def _count_media_items(self) -> int:
        """
        Count total media items that need processing.

        Returns:
            int: The number of media items across all tweets in the cache.
        """
        try:
            cache_data = await async_json_load(self.config.tweet_cache_file)
            return sum(len(tweet_data.get('media', [])) for tweet_data in cache_data.values())
        except Exception:
            return 0

    async def process_tweets(self, tweet_urls: List[str]) -> None:
        """
        Process tweets while preserving existing cache.

        This method processes a list of tweet URLs, skipping already processed tweets unless forced,
        and updates progress via SocketIO if available.

        Args:
            tweet_urls (List[str]): List of tweet URLs or IDs to process.
        """
        if not self._initialized:
            await self.initialize()

        stats = ProcessingStats(datetime.now())
        total_tweets = len(tweet_urls)
        
        for i, tweet_url in enumerate(tweet_urls):
            if stop_flag.is_set():
                logging.info("Stopping tweet processing due to stop request")
                break
            tweet_id = parse_tweet_id_from_url(tweet_url)
            if not tweet_id:
                continue

            if await self.state_manager.is_tweet_processed(tweet_id) and not self.config.force_update:
                logging.info(f"Tweet {tweet_id} already processed, skipping")
                stats.skipped_count += 1
                if self.socketio:
                    self.socketio.emit('progress', {'processed': stats.processed_count, 'total': total_tweets, 'errors': stats.error_count, 'skipped': stats.skipped_count, 'current_item_id': tweet_id, 'status_message': f'Skipped {tweet_id}'})
                continue

            try:
                cached_data = await self.state_manager.get_tweet_cache(tweet_id)
                if cached_data and not self.config.force_update:
                    stats.cache_hits += 1
                    logging.debug(f"Cache hit for {tweet_id}")
                else:
                    logging.debug(f"Cache miss or force update for {tweet_id}. Fetching...")
                    tweet_data = await self._fetch_tweet_data(tweet_url)
                    await self.state_manager.save_tweet_cache(tweet_id, tweet_data)
                    stats.cache_misses += 1
                stats.processed_count += 1
                if self.socketio:
                    self.socketio.emit('progress', {'processed': stats.processed_count, 'total': total_tweets, 'errors': stats.error_count, 'skipped': stats.skipped_count, 'current_item_id': tweet_id, 'status_message': f'Processed {tweet_id}'})
            except Exception as e:
                logging.error(f"Failed to process tweet {tweet_id}: {e}")
                stats.error_count += 1
                if self.socketio:
                    self.socketio.emit('progress', {'processed': stats.processed_count, 'total': total_tweets, 'errors': stats.error_count, 'skipped': stats.skipped_count, 'current_item_id': tweet_id, 'status_message': f'Error processing {tweet_id}'})
                continue

class InterruptedError(Exception):
    """Custom exception for when the agent run is stopped by the user."""
    pass