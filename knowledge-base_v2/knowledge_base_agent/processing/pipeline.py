import asyncio
import logging
from typing import Optional, Dict, Any, List, Set, TYPE_CHECKING
import time
from flask_socketio import SocketIO
import sys

from ..config import Config
from ..exceptions import KnowledgeBaseAgentError, DBSyncError
from ..types import TweetData
from .state import StateManager

# Import interface types for dependency injection
from ..interfaces.http_client import HttpClientManager
from ..interfaces.ollama import OllamaClient
from ..interfaces.playwright_client import PlaywrightClient
from ..interfaces.git import GitClient

# --- Import Actual Phase Logic ---
from . import fetcher
from . import cacher
from . import interpreter
from . import categorizer
from . import generator
from . import indexer
from . import stats
from .fetcher import Fetcher
# --- Import Database Function ---
from .. import database

# Add AccountsPool conditionally for type hint
if TYPE_CHECKING:
    from twscrape import AccountsPool, API as TwscrapeAPI_TYPE
else:
    try:
        from twscrape import AccountsPool, API as TwscrapeAPI_TYPE
    except ImportError:
        AccountsPool = None
        TwscrapeAPI_TYPE = None

logger = logging.getLogger(__name__)

# Define the sequence of processing phases (names should match phase_name used in calls)
# Tuples: (Phase Name, phase_function, semaphore_type, force_flag_key_in_prefs, skip_flag_key_in_prefs)
# Use None for semaphore_type if it's a single-run phase like Indexing or Git.
# Use None for force/skip flag if not applicable.
PIPELINE_PHASES_CONFIG = [
    # Concurrent, item-specific phases
    ("Caching", cacher.run_cache_phase, "cache", "force_recache", None),
    ("Interpretation", interpreter.run_interpret_phase, "llm", "force_reinterpret", None),
    ("Categorization", categorizer.run_categorize_phase, "llm", "force_recategorize", None),
    ("Generation", generator.run_generate_phase, "llm", "force_regenerate", None),
    ("DBSync", database.sync_kb_item_async, "db", None, None), # No specific force flag from UI yet
    # Sequential, run-level phases (handled differently after the loop)
    # ("Indexing", indexer.generate_indexes, None, None, "skip_indexing"),
    # ("GitSync", None, None, None, "skip_git"), # GitClient method called directly
    # ("Finalizing", None, None, None, None)
]
# Note: Input Acquisition, Indexing, GitSync, Finalizing are handled separately in the main run() logic for now.
# This config is primarily for the concurrent item-processing loop.

# Helper to format seconds into HH:MM:SS
def format_eta(seconds: float | None) -> str:
    if seconds is None or seconds < 0:
        return "--:--:--"
    try:
        seconds = int(seconds)
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        secs = seconds % 60
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    except Exception:
        return "--:--:--"

class AgentPipeline:
    """
    Orchestrates the knowledge base agent's processing workflow.
    Handles phase execution, concurrency, state management coordination,
    statistics tracking, and progress reporting.
    """
    def __init__(
        self,
        config: Config,
        state_manager: StateManager,
        http_manager: HttpClientManager,
        ollama_client: OllamaClient,
        playwright_client: Optional[PlaywrightClient],
        git_client: Optional[GitClient],
        fetcher: Optional[Fetcher],
        socketio: SocketIO,
    ):
        self.config = config
        self.state_manager = state_manager
        self.http_manager = http_manager
        self.ollama_client = ollama_client
        self.playwright_client = playwright_client
        self.git_client = git_client
        self.fetcher = fetcher
        self.socketio = socketio
        self.stats: Optional[stats.ProcessingStats] = None
        self._stop_requested = False
        logger.info("AgentPipeline initialized.")

    def request_stop(self):
        """Flags the pipeline to stop gracefully after the current item/batch."""
        if self.stats:
             logger.warning("Stop requested for the current pipeline run.")
             self._stop_requested = True
        else:
             logger.info("Stop requested, but pipeline is not running.")

    def _emit_progress(self, processed_count: int, total_items: int, current_phase: str,
                       current_item_id: Any, eta_seconds: float | None,
                       total_phases: Optional[int] = None, current_phase_num: Optional[int] = None):
        """Emits progress update via SocketIO."""
        if not self.socketio:
             return

        progress_data = {
            "processed_count": processed_count,
            "total_items": total_items,
            "current_phase": current_phase,
            "current_item_id": str(current_item_id),
            "eta": format_eta(eta_seconds),
            "total_phases": total_phases or self.stats.total_phases_for_run if self.stats else 0,
            "current_phase_num": current_phase_num or self.stats.current_phase_number if self.stats else 0,
            "overall_items_processed": self.stats.get_counter("items_processed_overall_distinct") if self.stats else 0,
            "overall_total_items": self.stats.total_items_in_run if self.stats else 0,
        }
        try:
            self.socketio.emit('progress_update', progress_data, namespace='/agent')
        except Exception as e:
            logger.error(f"Failed to emit progress update via SocketIO: {e}", exc_info=False)

    async def _calculate_eta(self, completed_index: int, total_items: int) -> float | None:
         if total_items == 0 or completed_index >= total_items -1 :
              return 0.0

         remaining_items = total_items - (completed_index + 1)
         avg_interpret = self.stats.get_avg_llm_duration('interpret')
         avg_categorize = self.stats.get_avg_llm_duration('categorize')
         avg_generate = self.stats.get_avg_llm_duration('generate')

         time_per_item = 0
         phases_with_avg = 0
         if avg_interpret: time_per_item += avg_interpret; phases_with_avg += 1
         if avg_categorize: time_per_item += avg_categorize; phases_with_avg += 1
         if avg_generate: time_per_item += avg_generate; phases_with_avg += 1

         if time_per_item > 0:
              return remaining_items * time_per_item
         else:
              return None

    async def run(self, run_preferences: Optional[Dict[str, Any]] = None):
        logger.info(f"DEBUG: AgentPipeline.run received run_preferences: {run_preferences}")
        logger.info("--- Agent Pipeline Run Invoked ---")
        if self.stats and self.stats.start_time and not self.stats.end_time:
             logger.warning("Pipeline run requested, but it appears to be already running. Aborting new run.")
             if self.socketio:
                  self.socketio.emit('status_update', {
                      'status': 'running',
                      'message': 'Agent is already running. New run request ignored.'
                  }, namespace='/agent')
             return

        self._stop_requested = False
        self.stats = stats.ProcessingStats()
        self.stats.mark_start()

        prefs = run_preferences or {}
        self.current_run_preferences = prefs
        logger.info("Run Preferences (inside AgentPipeline.run, from 'prefs' dictionary):")
        logger.info(f"  - Run Only Phase: {prefs.get('run_only_phase', 'Full')}")
        logger.info(f"  - Skip Fetch Bookmarks: {prefs.get('skip_fetch', False)}")
        logger.info(f"  - Skip Git Sync: {prefs.get('skip_git', False)}")
        logger.info(f"  - Skip Indexing: {prefs.get('skip_indexing', False)}")
        logger.info(f"  - Force Re-cache Tweets: {prefs.get('force_recache', False)}")
        logger.info(f"  - Force Re-interpret Media: {prefs.get('force_reinterpret', False)}")
        logger.info(f"  - Force Re-categorize Content: {prefs.get('force_recategorize', False)}")
        logger.info(f"  - Force Re-generate KB Items: {prefs.get('force_regenerate', False)}")

        logger.info("Key Configuration Values:")
        logger.info(f"  - Ollama URL: {self.config.ollama_url}")
        logger.info(f"  - Text Model: {self.config.text_model}")
        logger.info(f"  - Fallback Model: {self.config.fallback_model}")
        logger.info(f"  - Vision Model: {self.config.vision_model}")
        
        # Modified logging for bookmark fetching capability
        can_fetch_bookmarks = bool(self.config.x_username and self.config.x_password and self.config.x_email and self.config.x_bookmarks_url)
        logger.info(f"  - Bookmark Fetching Possible (credentials present): {can_fetch_bookmarks}")
        if can_fetch_bookmarks:
            logger.info(f"  - X Username: {self.config.x_username}") # Log username if configured
            logger.info(f"  - X Email: {self.config.x_email}") # Log email if configured
            logger.info(f"  - X Bookmarks URL: {self.config.x_bookmarks_url}")
        
        logger.info(f"  - Git Sync Enabled (config): {self.config.git_enabled}")
        logger.info(f"  - Knowledge Base Dir: {self.config.knowledge_base_dir}")
        logger.info(f"  - Data Dir: {self.config.data_dir}")
        logger.info(f"  - Log Dir: {self.config.log_dir}")
        logger.info("------------------------------------")

        force_recache = prefs.get('force_recache', False)
        force_reinterpret = prefs.get('force_reinterpret', False)
        force_recategorize = prefs.get('force_recategorize', False)
        force_regenerate = prefs.get('force_regenerate', False)
        skip_fetch = prefs.get('skip_fetch', False)
        skip_git = prefs.get('skip_git', False)
        skip_indexing = prefs.get('skip_indexing', False)

        run_error = None
        processed_count = 0
        total_items = 0
        last_progress_emit_time = time.monotonic()

        try:
            # --- Phase Planning ---
            # Define all potential phases in execution order
            # (Name, async_method_to_call, is_loop_for_items, force_flag_key, skip_flag_key)
            all_potential_phases_definitions = [
                # Name, function, is_main_processing_loop_sub_phase, force_key_in_prefs, skip_key_in_prefs
                ("InputAcquisition", self._run_phase_input_acquisition, False, None, "skip_fetch"),
                # The "ProcessingLoop" is a meta-phase that runs concurrent sub-phases
                ("Caching", self._run_main_processing_loop_sub_phase, True, "force_recache", None),
                ("Interpretation", self._run_main_processing_loop_sub_phase, True, "force_reinterpret", None),
                ("Categorization", self._run_main_processing_loop_sub_phase, True, "force_recategorize", None),
                ("Generation", self._run_main_processing_loop_sub_phase, True, "force_regenerate", None),
                ("DBSync", self._run_main_processing_loop_sub_phase, True, None, None), # No specific force flag from UI
                ("Indexing", self._run_phase_indexing, False, None, "skip_indexing"),
                ("GitSync", self._run_phase_git_sync, False, None, "skip_git"),
                ("Finalizing", self._finalize_state, False, None, None),
            ]

            requested_run_only_phase = prefs.get('run_only_phase')
            logger.info(f"DEBUG: AgentPipeline.run - requested_run_only_phase from prefs.get(): '{requested_run_only_phase}'")
            phases_to_execute_this_run = []

            if requested_run_only_phase and requested_run_only_phase != "Full":
                logger.info(f"Run mode: 'Run Only Phase' selected - {requested_run_only_phase}")
                found_phase = False
                for name, func, is_sub_phase, force_key, skip_key in all_potential_phases_definitions:
                    if name == requested_run_only_phase:
                        phases_to_execute_this_run.append(
                            {"name": name, "func": func, "is_sub_phase": is_sub_phase, 
                             "force_key": force_key, "skip_key": skip_key}
                        )
                        found_phase = True
                        break
                if not found_phase:
                    logger.warning(f"Requested 'run_only_phase' ('{requested_run_only_phase}') not found in definitions. Running full pipeline.")
                    # Fallback to full pipeline if specific phase not found
                    requested_run_only_phase = "Full" 
            
            if not requested_run_only_phase or requested_run_only_phase == "Full":
                logger.info("Run mode: 'Full Pipeline'")
                for name, func, is_sub_phase, force_key, skip_key in all_potential_phases_definitions:
                    is_skipped_by_pref = False
                    if skip_key and prefs.get(skip_key, False):
                        is_skipped_by_pref = True
                        logger.info(f"Skipping phase '{name}' due to run preference '{skip_key}'.")
                    elif name == "GitSync" and not self.config.git_enabled:
                        is_skipped_by_pref = True
                        logger.info(f"Skipping phase '{name}' (Git Sync disabled in config).")
                    
                    if not is_skipped_by_pref:
                        phases_to_execute_this_run.append(
                            {"name": name, "func": func, "is_sub_phase": is_sub_phase,
                             "force_key": force_key, "skip_key": skip_key}
                        )
            
            total_phases_count_for_run = len(phases_to_execute_this_run)
            self.stats.total_phases_for_run = total_phases_count_for_run
            logger.info(f"Total phases planned for this run: {total_phases_count_for_run}. Phases: {[p['name'] for p in phases_to_execute_this_run]}")
            # --- End Phase Planning ---

            current_phase_number = 0 

            # --- Load State (always happens before any phase) ---
            current_phase_for_progress = "Loading State"
            self._emit_progress(0, 0, current_phase_for_progress, "", None, total_phases_count_for_run, current_phase_number)
            await self.state_manager.load_state()
            all_tweet_ids_initial = list(self.state_manager.get_all_known_ids())
            total_initial_items = len(all_tweet_ids_initial)
            logger.info(f"Loaded state. Total known items initially: {total_initial_items}. IDs: {all_tweet_ids_initial if total_initial_items < 20 else str(all_tweet_ids_initial[:20])+'...'}")
            self.stats.set_total_items_to_process(total_initial_items)
            # ---

            # --- Execute Planned Phases ---
            # This loop now iterates through the filtered `phases_to_execute_this_run`
            for phase_definition in phases_to_execute_this_run:
                phase_name = phase_definition["name"]
                phase_func = phase_definition["func"]
                is_main_processing_sub_phase = phase_definition["is_sub_phase"]
                
                current_phase_number += 1
                if self._stop_requested: raise asyncio.CancelledError("Stop requested")

                logger.info(f"--- Starting Overall Phase {current_phase_number}/{total_phases_count_for_run}: {phase_name} ---")
                
                phase_specific_run_prefs = {
                    "force_recache": prefs.get('force_recache', False),
                    "force_reinterpret": prefs.get('force_reinterpret', False),
                    "force_recategorize": prefs.get('force_recategorize', False),
                    "force_regenerate": prefs.get('force_regenerate', False),
                }

                if is_main_processing_sub_phase:
                    # This function now needs to know which *specific* sub-phase to run
                    await phase_func( # This is _run_main_processing_loop_sub_phase
                        phase_to_run_in_loop=phase_name, # Pass the specific sub-phase name
                        item_ids=all_tweet_ids_initial, 
                        run_prefs=phase_specific_run_prefs, # Pass specific force flags for sub-phases
                        loop_phase_num=current_phase_number, # Overall phase number
                        total_pipeline_phases=total_phases_count_for_run
                    )
                elif phase_name == "InputAcquisition":
                     await phase_func(current_phase_number, total_phases_count_for_run)
                     old_count = total_initial_items
                     all_tweet_ids_initial = list(self.state_manager.get_all_known_ids())
                     total_initial_items = len(all_tweet_ids_initial)
                     logger.info(f"After Input Acquisition. Total known items now: {total_initial_items} (Added: {total_initial_items - old_count}). IDs: {all_tweet_ids_initial if total_initial_items < 20 else str(all_tweet_ids_initial[:20])+'...'}")
                     self.stats.set_total_items_to_process(total_initial_items)
                elif phase_name in ["Indexing", "GitSync", "Finalizing"]:
                    await phase_func(current_phase_number, total_phases_count_for_run)
                else: 
                     logger.error(f"Unknown phase execution type for: {phase_name} in primary execution loop.")

                logger.info(f"--- Finished Overall Phase {current_phase_number}/{total_phases_count_for_run}: {phase_name} ---")
            # --- End Phase Execution ---

            logger.info("Agent pipeline run finished successfully.")

        except asyncio.CancelledError:
             run_error = KnowledgeBaseAgentError("Pipeline run cancelled by stop request.")
             logger.warning(run_error)
             self.stats.record_error("Pipeline", message="Run cancelled")
        except Exception as e:
            run_error = e
            logger.exception("Critical error during pipeline execution:", exc_info=True)
            self.stats.record_error("Pipeline", error=e, message="Critical pipeline failure")
        finally:
            try:
                 await self.state_manager.save_state()
            except Exception as final_save_e:
                 logger.error(f"Failed to save final state: {final_save_e}")
                 if not run_error: run_error = final_save_e

            self.stats.mark_end()
            final_report = self.stats.get_report()
            logger.info(f"Run Statistics:\n{final_report}")

            final_status = 'idle' if not run_error else 'failed'
            final_message = f'Agent run finished.' if final_status == 'idle' else f'Agent run failed: {run_error}'
            if self.socketio:
                self.socketio.emit('status_update', {'status': final_status, 'message': final_message}, namespace='/agent')
                self._emit_progress(
                    self.stats.get_counter("items_processed_overall_distinct"), # Use distinct count for final processed
                    self.stats.total_items_in_run,
                    "Finished" if final_status == 'idle' else "Failed",
                    "", 0.0,
                    self.stats.total_phases_for_run, # Use count stored in stats
                    self.stats.total_phases_for_run # Mark as last phase
                )

    async def _run_phase_input_acquisition(self, current_phase_num: int, total_phases: int): # Add args
        logger.info("Running Input Acquisition Phase...")
        self._emit_progress(0, 0, "InputAcquisition", "N/A", None, total_phases, current_phase_num)

        if not self.fetcher:
            logger.warning("Fetcher not available. Skipping input acquisition.")
            return

        skip_fetch = self.current_run_preferences.get('skip_fetch', False)
        
        if skip_fetch:
            logger.info("Skipping fetch due to run preferences.")
            self.stats.set_counter("items_fetched_this_run", 0)
            return

        try:
            # Fetcher now returns a dict: {tweet_id: source_url}
            newly_fetched_sources: Dict[str, str] = await self.fetcher.get_tweet_sources_to_process(self.current_run_preferences)
            
            self.stats.set_counter("items_fetched_this_run", len(newly_fetched_sources))

            if newly_fetched_sources:
                logger.info(f"Fetcher provided {len(newly_fetched_sources)} new tweet_id-URL pairs.")
                
                # For each fetched item, ensure a TweetData object exists and its source_url is set.
                for tweet_id, source_url in newly_fetched_sources.items():
                    # This will create a new TweetData if one doesn't exist for tweet_id,
                    # or retrieve the existing one. In both cases, it ensures source_url is set
                    # if provided and was previously missing.
                    self.state_manager.get_or_create_tweet_data(tweet_id=tweet_id, tweet_url=source_url)
                
                # After ensuring TweetData objects exist with source_urls,
                # add the set of tweet_ids to the unprocessed list in StateManager.
                # StateManager.add_unprocessed_ids handles duplicates and checks against processed list.
                tweet_ids_from_fetch = set(newly_fetched_sources.keys())
                count_actually_added_to_unprocessed = self.state_manager.add_unprocessed_ids(tweet_ids_from_fetch)
                
                logger.info(f"{count_actually_added_to_unprocessed} IDs were newly added to the unprocessed set by StateManager.")

                if count_actually_added_to_unprocessed > 0: # Only save if truly new IDs were added to unprocessed list
                    await self.state_manager.save_state() 
            else:
                logger.info("No new items fetched in this run.")
        
        except Exception as e:
            logger.error(f"Error during input acquisition phase: {e}", exc_info=True)
            self.stats.record_error("InputAcquisition", str(e))

        logger.info("Input Acquisition Phase completed.")

    async def _run_main_processing_loop_sub_phase(
        self, 
        phase_to_run_in_loop: str, # Specific sub-phase to run (e.g., "Caching")
        item_ids: List[str], 
        run_prefs: Dict, # Contains force flags
        loop_phase_num: int, # Current overall phase number in the pipeline
        total_pipeline_phases: int # Total phases in the entire pipeline run
    ):
        """
        Handles the execution of a single concurrent, item-based processing sub-phase 
        (like Caching, Interpretation, etc.) within the main processing loop.
        """
        if not item_ids:
            logger.warning(f"No items provided to _run_main_processing_loop_sub_phase for {phase_to_run_in_loop}.")
            self.stats.enter_phase(phase_to_run_in_loop, loop_phase_num, total_pipeline_phases) # Still enter/finish for stats
            self.stats.finish_phase(phase_to_run_in_loop, True)
            return

        # Find the definition for the specific sub-phase we need to run
        sub_phase_definition = None
        # Simplified mapping for sub-phase details
        sub_phase_configs = {
            "Caching": {"func": cacher.run_cache_phase, "sem_type": "cache", "force_key": "force_recache"},
            "Interpretation": {"func": interpreter.run_interpret_phase, "sem_type": "llm", "force_key": "force_reinterpret"},
            "Categorization": {"func": categorizer.run_categorize_phase, "sem_type": "llm", "force_key": "force_recategorize"},
            "Generation": {"func": generator.run_generate_phase, "sem_type": "llm", "force_key": "force_regenerate"},
            "DBSync": {"func": database.sync_kb_item_async, "sem_type": "db", "force_key": None},
        }
        
        if phase_to_run_in_loop not in sub_phase_configs:
            logger.error(f"Definition for sub-phase '{phase_to_run_in_loop}' not found in sub_phase_configs.")
            return
            
        config = sub_phase_configs[phase_to_run_in_loop]
        phase_func = config["func"]
        sem_type = config["sem_type"]
        force_key = config["force_key"]

        phase_specific_kwargs = {}
        if force_key and run_prefs.get(force_key, False):
            phase_specific_kwargs[force_key] = True
        
        # Add run_only_phase and whether fetching is involved for decision-making in cacher.py
        phase_specific_kwargs['run_only_phase'] = run_prefs.get('run_only_phase', 'Full')
        phase_specific_kwargs['is_fetching_bookmarks'] = run_prefs.get('run_only_phase', 'Full') == 'InputAcquisition' or (run_prefs.get('run_only_phase', 'Full') == 'Full' and not run_prefs.get('skip_fetch', False))
        
        current_semaphore = None
        if sem_type == "llm": current_semaphore = asyncio.Semaphore(self.config.max_concurrent_llm_tasks) # Re-init semaphores if needed
        elif sem_type == "cache": current_semaphore = asyncio.Semaphore(self.config.max_concurrent_caching_tasks)
        elif sem_type == "db": current_semaphore = asyncio.Semaphore(self.config.max_concurrent_db_sync_tasks)
        else: 
            logger.error(f"Unknown semaphore type for sub-phase {phase_to_run_in_loop}: {sem_type}")
            return

        # Call the _run_concurrent_phase helper, which now handles a single sub-phase logic
        # Note: sub_phase_num and total_sub_phases are now 1, as we are running one sub-phase here.
        await self._run_concurrent_phase(
            phase_name=phase_to_run_in_loop, 
            phase_func=phase_func, 
            item_ids=item_ids, 
            semaphore=current_semaphore,
            current_phase_num=loop_phase_num, 
            total_phases_in_run=total_pipeline_phases,
            sub_phase_num=1, # This function now handles one sub-phase at a time
            total_sub_phases=1,
            **phase_specific_kwargs 
        )
        await self.state_manager.save_state() # Save state after each sub-phase completes

    async def _run_concurrent_phase(self, phase_name: str, phase_func: callable, item_ids: List[Any],
                                    semaphore: asyncio.Semaphore,
                                    current_phase_num: int, 
                                    total_phases_in_run: int, 
                                    sub_phase_num: int,
                                    total_sub_phases: int,
                                    **phase_kwargs):
        # Update how enter_phase is called
        log_phase_display_name = f"{phase_name}"
        if total_sub_phases > 1:  # If it's truly a sub-phase of a larger loop
            log_phase_display_name = f"{phase_name} ({sub_phase_num}/{total_sub_phases})"
        
        logger.info(f"--- Starting Phase: {log_phase_display_name} --- "
                    f"(Overall Pipeline Step {current_phase_num}/{total_phases_in_run})")
        start_phase_time = time.monotonic()
        self.stats.enter_phase(phase_name, current_phase_num, total_phases_in_run)  # Use the main phase name for stats
        
        tasks = []
        items_to_process_in_this_phase_batch: List[str] = []

        force_run_for_phase = False
        if phase_name == "Caching": force_run_for_phase = phase_kwargs.get("force_recache", False)
        elif phase_name == "Interpretation": force_run_for_phase = phase_kwargs.get("force_reinterpret", False)
        elif phase_name == "Categorization": force_run_for_phase = phase_kwargs.get("force_recategorize", False)
        elif phase_name == "Generation": force_run_for_phase = phase_kwargs.get("force_regenerate", False)

        for item_id_str in item_ids:
            if self._stop_requested: break
            tweet_data = self.state_manager.get_tweet_data(item_id_str)
            if not tweet_data:
                logger.warning(f"[{phase_name}] No TweetData for item {item_id_str}, skipping.")
                continue

            if force_run_for_phase or tweet_data.needs_processing(phase_name):
                items_to_process_in_this_phase_batch.append(item_id_str)
        
        total_in_batch = len(items_to_process_in_this_phase_batch)
        self.stats.set_current_batch_total(total_in_batch)
        logger.info(f"[{phase_name}] Identified {total_in_batch} items for processing in this batch.")
        self._emit_progress(0, total_in_batch, f"{phase_name} ({sub_phase_num}/{total_sub_phases})", "", await self._calculate_eta(0, total_in_batch), self.stats.total_phases_for_run, current_phase_num)

        processed_in_batch = 0
        if total_in_batch > 0:
            # Dynamic adjustment of semaphore limit for LLM phases based on recent performance
            if phase_name in ["Interpretation", "Categorization", "Generation"]:
                avg_duration = self.stats.get_avg_llm_duration(phase_name.lower())
                if avg_duration and avg_duration > 10:  # If average duration is high, reduce concurrency
                    new_limit = max(1, semaphore._value - 1)
                    logger.info(f"Adjusting concurrency for {phase_name} from {semaphore._value} to {new_limit} due to high avg duration {avg_duration:.2f}s")
                    semaphore._value = new_limit
                elif avg_duration and avg_duration < 5:  # If low, increase concurrency
                    new_limit = min(self.config.max_concurrent_llm_tasks * 2, semaphore._value + 1)
                    logger.info(f"Adjusting concurrency for {phase_name} from {semaphore._value} to {new_limit} due to low avg duration {avg_duration:.2f}s")
                    semaphore._value = new_limit

            for item_id_to_process in items_to_process_in_this_phase_batch:
                if self._stop_requested: break
                task = asyncio.create_task(
                    self._run_single_item_phase(
                        phase_name, phase_func, semaphore, item_id_to_process, phase_kwargs
                    ),
                    name=f"{phase_name}-{item_id_to_process}"
                )
                tasks.append(task)

            if tasks:
                logger.info(f"[{phase_name}] Awaiting {len(tasks)} tasks...")
                results = await asyncio.gather(*tasks, return_exceptions=True) 
                for i, result in enumerate(results):
                    if isinstance(result, Exception):
                        task_name = tasks[i].get_name() if hasattr(tasks[i], 'get_name') else f"Task-{i}"
                        logger.error(f"[{phase_name}] Error in gathered task {task_name}: {result}", exc_info=isinstance(result, BaseException))
                
                logger.info(f"[{phase_name}] Task batch finished gathering.")
                processed_count_for_phase = self.stats.phase_counts.get(phase_name, {}).get('success', 0)
                
                self._emit_progress(
                    processed_count_for_phase, 
                    total_in_batch, 
                    f"{phase_name} ({sub_phase_num}/{total_sub_phases})", 
                    "Batch Complete", 
                    0.0,
                    self.stats.total_phases_for_run, 
                    current_phase_num
                )
        else:
            logger.info(f"[{phase_name}] No items required processing in this batch.")
            self._emit_progress(0, 0, f"{phase_name} ({sub_phase_num}/{total_sub_phases})", "None", 0.0, self.stats.total_phases_for_run, current_phase_num)

        phase_duration = time.monotonic() - start_phase_time
        self.stats.add_timing(phase_name, phase_duration)
        self.stats.finish_phase(phase_name, True)
        logger.info(f"--- Finished Phase: {log_phase_display_name} --- "
                    f"(Overall Pipeline Step {current_phase_num}/{total_phases_in_run}) --- ({phase_duration:.2f}s)")

    async def _run_single_item_phase(self, phase_name: str, phase_func: callable,
                                     semaphore: asyncio.Semaphore, item_id: Any,
                                     phase_args: Dict[str, Any]):
        """
        Helper to run a specific phase for a single item with concurrency control and error handling.
        phase_args will contain the specific 'force_...' flag for this phase.
        """
        async with semaphore:
            if self._stop_requested:
                logger.debug(f"Stop requested, skipping {phase_name} for item {item_id}")
                return

            tweet_data_obj = self.state_manager.get_or_create_tweet_data(str(item_id))
            start_time = time.monotonic()
            error_occurred = False
            phase_error_details = None

            current_phase_force_flag = False # This is the overall force flag for the phase from run_preferences
            if phase_name == "Caching": current_phase_force_flag = phase_args.get("force_recache", False)
            elif phase_name == "Interpretation": current_phase_force_flag = phase_args.get("force_reinterpret", False)
            elif phase_name == "Categorization": current_phase_force_flag = phase_args.get("force_recategorize", False)
            elif phase_name == "Generation": current_phase_force_flag = phase_args.get("force_regenerate", False)

            # Determine if the phase should run based on its current state
            needs_processing_due_to_prior_error = False
            if tweet_data_obj and tweet_data_obj.failed_phase == phase_name:
                 needs_processing_due_to_prior_error = True
            
            # Reset flags if forced OR if reprocessing due to a prior error in this specific phase
            if current_phase_force_flag or needs_processing_due_to_prior_error:
                if current_phase_force_flag:
                    logger.debug(f"Item {item_id}: Force flag is set for phase '{phase_name}'. Resetting phase flags.")
                if needs_processing_due_to_prior_error and not current_phase_force_flag: # Avoid double logging if force is also true
                    logger.debug(f"Item {item_id}: Reprocessing phase '{phase_name}' due to prior error. Resetting phase flags.")
                self.state_manager.reset_phase_flags(item_id, phase_name) 
            
            # Now, re-evaluate if it should run after potential reset
            # The current_phase_force_flag is passed to should_process_phase, which will correctly return True if the flag is set.
            # If not forced, should_process_phase will check the (now potentially reset) completion/error flags.
            should_run_this_phase = self.state_manager.should_process_phase(item_id, phase_name, current_phase_force_flag)

            if not should_run_this_phase:
                # This log might now be less common if needs_processing_due_to_prior_error was true,
                # as should_process_phase will likely return true after a reset.
                logger.debug(f"Item {item_id}: Skipping phase '{phase_name}' based on current state (and force flag was false or item is already complete).")
                self.stats.record_item_skipped(phase_name)
                return

            logger.debug(f"Item {item_id}: Starting phase '{phase_name}'.")
            current_item_id_for_progress = f"{item_id} ({phase_name})"

            phase_dependencies = {
                "config": self.config,
                "state_manager": self.state_manager,
                "http_manager": self.http_manager,
                "ollama_client": self.ollama_client,
                "playwright_client": self.playwright_client,
                "git_client": self.git_client,
            }

            # Retry logic for LLM-based phases
            max_retries = 3
            retries = 0
            while retries < max_retries:
                try:
                    await phase_func(
                        tweet_id=str(item_id),
                        tweet_data=tweet_data_obj,
                        **phase_dependencies,
                        **phase_args
                    )
                    # Check if the phase marked an error in TweetData
                    if tweet_data_obj.failed_phase == phase_name or (tweet_data_obj.error_message and phase_name.lower() in tweet_data_obj.error_message.lower()):
                        error_occurred = True
                        phase_error_details = tweet_data_obj.error_message
                        logger.warning(f"Item {item_id}: Phase '{phase_name}' completed with error: {phase_error_details}")
                    else:
                        logger.debug(f"Item {item_id}: Phase '{phase_name}' completed successfully.")
                    break  # Exit loop on success
                except Exception as e:
                    error_occurred = True
                    phase_error_details = str(e)
                    logger.error(f"Item {item_id}: Unhandled exception in phase '{phase_name}', attempt {retries+1}/{max_retries}: {e}", exc_info=True)
                    tweet_data_obj.mark_failed(phase_name, e)
                    retries += 1
                    if retries < max_retries and phase_name in ["Interpretation", "Categorization", "Generation"]:
                        delay = 2 ** retries  # Exponential backoff
                        logger.info(f"Retrying phase '{phase_name}' for item {item_id} after {delay}s delay...")
                        await asyncio.sleep(delay)
                    else:
                        break
                finally:
                    duration = time.monotonic() - start_time
                    self.stats.record_item_processed(phase_name, duration, error_occurred, error_details=phase_error_details)

    async def _run_phase_indexing(self, current_phase_num: int, total_phases: int): # Add args
         phase_name = "Indexing"
         logger.info(f"Running {phase_name} phase ({current_phase_num}/{total_phases})...")
         self.stats.enter_phase(phase_name, current_phase_num, total_phases) # Pass correct args
         start_time = time.monotonic()
         success = False
         try:
             await indexer.generate_indexes(self.state_manager, self.config)
             success = True
             self.stats.finish_phase(phase_name, success)
             logger.info("Indexing phase completed successfully.")
         except Exception as e:
             logger.error(f"Error during Indexing phase: {e}", exc_info=True)
             self.stats.finish_phase(phase_name, False)
             self.stats.record_error("Index", error=e)
         finally:
             self.stats.add_timing("Index", time.monotonic() - start_time)

    async def _run_phase_git_sync(self, current_phase_num: int, total_phases: int): # Add args
         phase_name = "GitSync"
         logger.info(f"Running {phase_name} phase ({current_phase_num}/{total_phases})...")
         self.stats.enter_phase(phase_name, current_phase_num, total_phases) # Pass correct args
         start_time = time.monotonic()
         success = False
         if not self.git_client:
              logger.warning("Git client not available, skipping sync.")
              self.stats.finish_phase(phase_name, False)
              self.stats.record_error("GitSync", message="Git client unavailable")
              return
         try:
             success = await self.git_client.commit_and_push_changes("Automated knowledge base update")
             self.stats.finish_phase(phase_name, success)
             if success: logger.info("Git synchronization completed successfully.")
             else: logger.warning("Git synchronization reported failure or no changes.")
         except Exception as e:
             logger.error(f"Error during Git Sync phase: {e}", exc_info=True)
             self.stats.finish_phase(phase_name, False)
             self.stats.record_error("GitSync", error=e)
         finally:
             self.stats.add_timing("GitSync", time.monotonic() - start_time)

    async def _finalize_state(self, current_phase_num: int, total_phases: int): # Add args
        phase_name = "Finalizing"
        logger.info(f"Running {phase_name} phase ({current_phase_num}/{total_phases})...")
        self.stats.enter_phase(phase_name, current_phase_num, total_phases) # Pass correct args
        logger.info("Finalizing state: Checking for fully processed items...")
        processed_count_this_run = 0
        all_ids = self.state_manager.get_all_known_ids()

        for tweet_id in all_ids:
            if self.state_manager.is_processed(tweet_id):
                 continue

            tweet_data = self.state_manager.get_tweet_data(tweet_id)
            if (tweet_data and
                tweet_data.cache_complete and
                tweet_data.media_processed and
                tweet_data.categories_processed and
                tweet_data.kb_item_created and
                tweet_data.db_synced and
                not tweet_data.error_message):

                self.state_manager.mark_processed(tweet_id)
                processed_count_this_run += 1
                logger.debug(f"Marked tweet {tweet_id} as fully processed.")

        if processed_count_this_run > 0:
            logger.info(f"Marked {processed_count_this_run} items as fully processed in this run.")
            self.stats.increment_counter("tweets_marked_processed", processed_count_this_run)
            await self.state_manager.save_state()
        else:
            logger.info("No additional items were marked as fully processed in this run.")
        self.stats.finish_phase(phase_name, True) # Mark finalizing as complete
