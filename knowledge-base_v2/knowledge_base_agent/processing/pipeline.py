import asyncio
import logging
from typing import Optional, Dict, Any, List, Set, TYPE_CHECKING
import time
from flask_socketio import SocketIO

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
# --- Import Database Function ---
from .. import database

# Add AccountsPool conditionally for type hint
if TYPE_CHECKING:
    from twscrape import AccountsPool
else:
    try:
        from twscrape import AccountsPool
    except ImportError:
        AccountsPool = None

logger = logging.getLogger(__name__)

# --- REMOVE MOCK FUNCTIONS ---
# (Delete all the async def mock_... functions and assignments)

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
        twscrape_pool: Optional["AccountsPool"],
        socketio: SocketIO,
    ):
        self.config = config
        self.state_manager = state_manager
        self.http_manager = http_manager
        self.ollama_client = ollama_client
        self.playwright_client = playwright_client
        self.git_client = git_client
        self.twscrape_pool = twscrape_pool
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

    def _emit_progress(self, processed_count: int, total_items: int, current_phase: str, current_item_id: Any, eta_seconds: float | None):
        """Emits progress update via SocketIO."""
        if not self.socketio:
             return

        progress_data = {
            "processed_count": processed_count,
            "total_items": total_items,
            "current_phase": current_phase,
            "current_item_id": str(current_item_id),
            "eta": format_eta(eta_seconds),
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
        if self.stats and self.stats.start_time and not self.stats.end_time:
             logger.warning("Pipeline run requested, but it appears to be already running.")
             return

        self._stop_requested = False
        self.stats = stats.ProcessingStats()
        self.stats.mark_start()
        logger.info(f"Starting agent pipeline run with preferences: {run_preferences or {}}")

        prefs = run_preferences or {}
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
            current_phase_for_progress = "Loading State"
            self._emit_progress(0, 0, current_phase_for_progress, "", None)
            await self.state_manager.load_state()
            all_tweet_ids = self.state_manager.get_all_known_ids()
            total_items = len(all_tweet_ids)
            logger.info(f"Loaded state. Total known items: {total_items}")

            current_phase_for_progress = "Fetching Input"
            self._emit_progress(0, total_items, current_phase_for_progress, "", None)
            if not skip_fetch and self.config.fetch_bookmarks_enabled:
                if not self.playwright_client:
                     logger.warning("Bookmark fetching enabled but PlaywrightClient not provided.")
                     self.stats.record_error("Fetch", message="Playwright client missing")
                else:
                    if self._stop_requested: raise asyncio.CancelledError("Stop requested")
                    await self._run_phase_input_acquisition()
                    all_tweet_ids = self.state_manager.get_all_known_ids()
                    total_items = len(all_tweet_ids)
            elif skip_fetch: logger.info("Skipping bookmark fetching (preference).")
            else: logger.info("Bookmark fetching disabled (config).")

            logger.info(f"Starting processing loop for {total_items} known items...")
            if total_items == 0: logger.warning("No items to process.")

            CONCURRENT_LLM_LIMIT = 3
            CONCURRENT_CACHE_LIMIT = 5
            CONCURRENT_DB_LIMIT = 10

            llm_semaphore = asyncio.Semaphore(CONCURRENT_LLM_LIMIT)
            cache_semaphore = asyncio.Semaphore(CONCURRENT_CACHE_LIMIT)
            db_semaphore = asyncio.Semaphore(CONCURRENT_DB_LIMIT)

            if not self._stop_requested:
                 await self._run_concurrent_phase("Caching", cacher.run_cache_phase, all_tweet_ids, cache_semaphore, force_recache=force_recache)
                 await self.state_manager.save_state()

            if not self._stop_requested:
                 await self._run_concurrent_phase("Interpretation", interpreter.run_interpret_phase, all_tweet_ids, llm_semaphore, force_reinterpret=force_reinterpret)
                 await self.state_manager.save_state()

            if not self._stop_requested:
                 await self._run_concurrent_phase("Categorization", categorizer.run_categorize_phase, all_tweet_ids, llm_semaphore, force_recategorize=force_recategorize)
                 await self.state_manager.save_state()

            if not self._stop_requested:
                 await self._run_concurrent_phase("Generation", generator.run_generate_phase, all_tweet_ids, llm_semaphore, force_regenerate=force_regenerate)
                 await self.state_manager.save_state()

            if not self._stop_requested:
                 await self._run_concurrent_phase("DBSync", database.sync_kb_item_async, all_tweet_ids, db_semaphore)
                 await self.state_manager.save_state()

            logger.info("Finished main processing loop.")

            if self._stop_requested: raise asyncio.CancelledError("Stop requested")

            current_phase_for_progress = "Generating Index"
            self._emit_progress(total_items, total_items, current_phase_for_progress, "", 0.0)
            if not skip_indexing:
                await self._run_phase_indexing()
            else:
                logger.info("Skipping Indexing phase (preference).")

            current_phase_for_progress = "Syncing Git"
            self._emit_progress(total_items, total_items, current_phase_for_progress, "", 0.0)
            if not skip_git and self.config.git_enabled:
                if not self.git_client:
                     logger.warning("Git sync enabled but GitClient not provided.")
                     self.stats.record_error("GitSync", message="Git client missing")
                else:
                     await self._run_phase_git_sync()
            elif skip_git: logger.info("Skipping Git Sync phase (preference).")
            else: logger.info("Git sync disabled (config).")

            current_phase_for_progress = "Finalizing"
            self._emit_progress(total_items, total_items, current_phase_for_progress, "", 0.0)
            await self._finalize_state()

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
                self._emit_progress(total_items, total_items, "Finished" if final_status == 'idle' else "Failed", "", 0.0)

    async def _run_phase_input_acquisition(self):
        logger.info("Running Input Acquisition phase...")
        self.stats.enter_phase("Fetch")
        start_time = time.monotonic()
        try:
            new_ids = await fetcher.fetch_bookmark_tweet_ids(self.config, self.playwright_client)
            if new_ids:
                 added_count = self.state_manager.add_unprocessed_ids(new_ids)
                 logger.info(f"Fetched {len(new_ids)} bookmark items, added {added_count} new tweet IDs.")
                 self.stats.increment_counter("new_tweet_ids_added", added_count)
                 await self.state_manager.save_state()
            else:
                 logger.info("No new bookmark items found.")
            self.stats.finish_phase("Fetch", True)
        except Exception as e:
            logger.error(f"Error during Input Acquisition phase: {e}", exc_info=True)
            self.stats.finish_phase("Fetch", False)
            self.stats.record_error("Fetch", error=e)
        finally:
             self.stats.add_timing("Fetch", time.monotonic() - start_time)

    async def _run_concurrent_phase(self, phase_name: str, phase_func: callable, item_ids: List[Any],
                                    semaphore: asyncio.Semaphore, **phase_kwargs):
        logger.info(f"--- Starting Phase: {phase_name} ---")
        start_phase_time = time.monotonic()
        tasks = []
        items_queued = 0
        total_items = len(item_ids)

        force_flag_name = f"force_{phase_name.lower().replace('db', 'db_')}"
        if phase_name == "Caching": force_flag_name = "force_recache"
        if phase_name == "Interpretation": force_flag_name = "force_reinterpret"
        if phase_name == "Categorization": force_flag_name = "force_recategorize"
        if phase_name == "Generation": force_flag_name = "force_regenerate"

        force_run = phase_kwargs.get(force_flag_name, False)

        common_dependencies = {
            "config": self.config,
            "state_manager": self.state_manager,
            "http_manager": self.http_manager,
            "ollama_client": self.ollama_client,
            "twscrape_pool": self.twscrape_pool,
        }

        for index, item_id in enumerate(item_ids):
            if self._stop_requested: break
            tweet_data = self.state_manager.get_tweet_data(item_id)

            if not tweet_data:
                 logger.warning(f"[{phase_name}] No data found for item {item_id}, skipping.")
                 continue

            if tweet_data.needs_processing(phase_name) or force_run:
                 items_queued += 1
                 logger.debug(f"[{phase_name}] Queueing item {item_id} ({items_queued} in batch)")
                 specific_args = {"tweet_data": tweet_data}
                 if phase_name == "Caching":
                     deps = {"config", "http_manager", "state_manager", "twscrape_pool"}
                 elif phase_name == "Interpretation":
                     deps = {"ollama_client", "state_manager"}
                 elif phase_name == "Categorization":
                      deps = {"ollama_client", "state_manager"}
                 elif phase_name == "Generation":
                       deps = {"ollama_client", "config", "state_manager"}
                 elif phase_name == "DBSync":
                       deps = {}
                 else:
                       deps = set()

                 for dep_name in deps:
                     if dep_name in common_dependencies:
                         specific_args[dep_name] = common_dependencies[dep_name]
                     else:
                          logger.error(f"Missing dependency '{dep_name}' for phase '{phase_name}'")

                 task = asyncio.create_task(
                     self._run_single_item_phase(
                         phase_name, phase_func, semaphore, item_id, specific_args
                     ),
                     name=f"{phase_name}-{item_id}"
                 )
                 tasks.append(task)

        self.stats.increment_counter(f"{phase_name}_tasks_created", items_queued)
        if tasks:
            logger.info(f"[{phase_name}] Running {len(tasks)} tasks with concurrency limit...")
            await asyncio.gather(*tasks)
            logger.info(f"[{phase_name}] Task batch finished.")
        else:
            logger.info(f"[{phase_name}] No items required processing in this phase.")

        phase_duration = time.monotonic() - start_phase_time
        self.stats.add_timing(phase_name, phase_duration)
        logger.info(f"--- Finished Phase: {phase_name} ({phase_duration:.2f}s) ---")

    async def _run_single_item_phase(self, phase_name: str, phase_func: callable,
                                     semaphore: asyncio.Semaphore, item_id: Any,
                                     phase_args: Dict[str, Any]):
         success = False
         result = None
         phase_start_time = time.monotonic()
         tweet_data = phase_args.get("tweet_data")

         async with semaphore:
             if self._stop_requested:
                  logger.warning(f"[{phase_name}] Stop requested before processing item {item_id}")
                  return

             logger.debug(f"[{phase_name}] Starting processing for item {item_id}")
             self.stats.enter_phase(phase_name)

             try:
                 result = await phase_func(**phase_args)

                 if isinstance(result, bool):
                      success = result
                 else:
                      success = True
                      logger.debug(f"[{phase_name}] Task for {item_id} returned non-boolean: {result}. Assuming success.")

                 self.stats.finish_phase(phase_name, success)
                 if phase_name in ['Interpretation', 'Categorization', 'Generation']:
                      duration = time.monotonic() - phase_start_time
                      self.stats.record_llm_duration(phase_name.lower(), duration)

                 if not success and tweet_data:
                     error_msg = f"Phase function returned failure for {item_id}"
                     logger.warning(f"[{phase_name}] {error_msg}")
                     tweet_data.mark_failed(phase_name, error_msg)
                     self.state_manager.update_tweet_data(item_id, tweet_data)
                     self.stats.record_error(phase_name, tweet_id=item_id, message=error_msg)

             except Exception as e:
                 success = False
                 logger.error(f"[{phase_name}] Exception processing item {item_id}: {e}", exc_info=True)
                 self.stats.finish_phase(phase_name, False)
                 self.stats.record_error(phase_name, tweet_id=item_id, error=e)
                 if tweet_data:
                     tweet_data.mark_failed(phase_name, str(e))
                     try:
                          self.state_manager.update_tweet_data(item_id, tweet_data)
                     except Exception as save_err:
                           logger.error(f"Failed to save failure state for item {item_id} after exception: {save_err}")

             finally:
                 duration = time.monotonic() - phase_start_time
                 logger.debug(f"[{phase_name}] Finished processing item {item_id} (Success: {success}) in {duration:.2f}s")

    async def _run_phase_indexing(self):
         logger.info("Running Indexing phase...")
         self.stats.enter_phase("Index")
         start_time = time.monotonic()
         success = False
         try:
             await indexer.generate_indexes(self.state_manager, self.config)
             success = True
             self.stats.finish_phase("Index", success)
             logger.info("Indexing phase completed successfully.")
         except Exception as e:
             logger.error(f"Error during Indexing phase: {e}", exc_info=True)
             self.stats.finish_phase("Index", False)
             self.stats.record_error("Index", error=e)
         finally:
             self.stats.add_timing("Index", time.monotonic() - start_time)

    async def _run_phase_git_sync(self):
         logger.info("Running Git Sync phase...")
         self.stats.enter_phase("GitSync")
         start_time = time.monotonic()
         success = False
         if not self.git_client:
              logger.warning("Git client not available, skipping sync.")
              self.stats.finish_phase("GitSync", False)
              self.stats.record_error("GitSync", message="Git client unavailable")
              return
         try:
             success = await self.git_client.commit_and_push_changes("Automated knowledge base update")
             self.stats.finish_phase("GitSync", success)
             if success: logger.info("Git synchronization completed successfully.")
             else: logger.warning("Git synchronization reported failure or no changes.")
         except Exception as e:
             logger.error(f"Error during Git Sync phase: {e}", exc_info=True)
             self.stats.finish_phase("GitSync", False)
             self.stats.record_error("GitSync", error=e)
         finally:
             self.stats.add_timing("GitSync", time.monotonic() - start_time)

    async def _finalize_state(self):
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
