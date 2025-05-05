import asyncio
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Set, Dict

from ..config import Config
from ..exceptions import StateManagementError, FileOperationError
from ..types import ProcessingState, TweetData
from ..utils.file_io import read_json_async, write_json_atomic_async

logger = logging.getLogger(__name__)

# Define filenames within the data directory
STATE_FILENAME = "processing_state.json" # Combine cache, processed, unprocessed

class StateManager:
    """
    Manages the loading, saving, and access of the agent's processing state
    from a JSON file. Uses Pydantic models for structure and validation.
    """

    def __init__(self, config: Config):
        self.config = config
        self.data_dir = config.data_dir
        self.state_file_path = self.data_dir / STATE_FILENAME
        self._state: ProcessingState = ProcessingState() # Holds the in-memory state
        self._lock = asyncio.Lock() # Lock for atomic saving/modification access
        logger.info(f"StateManager initialized. State file: {self.state_file_path}")

    async def load_state(self, perform_reconciliation: bool = True):
        """
        Loads the processing state from the JSON file.

        Args:
            perform_reconciliation: If True, performs basic checks after loading.
        """
        async with self._lock: # Ensure loading doesn't conflict with saving
            logger.info(f"Attempting to load state from {self.state_file_path}...")
            if not await asyncio.to_thread(self.state_file_path.exists): # Use thread for sync exists check
                logger.warning(f"State file {self.state_file_path} not found. Initializing empty state.")
                self._state = ProcessingState()
                # Save initial empty state? Optional, but good practice.
                await self._save_state_internal()
                return

            try:
                raw_state_data = await read_json_async(self.state_file_path)
                # Validate data against the Pydantic model
                self._state = ProcessingState.model_validate(raw_state_data)
                logger.info(f"Successfully loaded state. "
                            f"{len(self._state.unprocessed_tweet_ids)} unprocessed, "
                            f"{len(self._state.processed_tweet_ids)} processed, "
                            f"{len(self._state.tweet_cache)} cached tweets.")
                if perform_reconciliation:
                     await self.reconcile_state()

            except FileOperationError as e:
                logger.error(f"File operation error loading state: {e}")
                raise StateManagementError(f"Failed to read state file {self.state_file_path}", original_exception=e) from e
            except Exception as e: # Catch Pydantic validation errors or other issues
                logger.exception(f"Error loading or validating state file {self.state_file_path}. Resetting to empty state.", exc_info=True)
                # Decide recovery strategy: raise error or reset state? Resetting might lose data.
                # For now, let's raise to make the issue explicit.
                raise StateManagementError(f"Failed to load/validate state: {e}. Check state file format.", original_exception=e) from e


    async def save_state(self):
        """Atomically saves the current state to the JSON file."""
        async with self._lock:
            await self._save_state_internal()

    async def _save_state_internal(self):
        """Internal save function (assumes lock is held)."""
        logger.info(f"Attempting to save state to {self.state_file_path}...")
        try:
            # Ensure data directory exists
            await asyncio.to_thread(self.data_dir.mkdir, parents=True, exist_ok=True)

            # Update timestamp
            self._state.last_run_timestamp = datetime.utcnow()

            # Dump Pydantic model to dict for JSON serialization
            state_dict = self._state.model_dump(mode='json', exclude_none=True)

            await write_json_atomic_async(self.state_file_path, state_dict, indent=2)
            logger.info(f"Successfully saved state. "
                        f"{len(self._state.unprocessed_tweet_ids)} unprocessed, "
                        f"{len(self._state.processed_tweet_ids)} processed.")
        except FileOperationError as e:
            logger.error(f"File operation error saving state: {e}")
            raise StateManagementError(f"Failed to save state file {self.state_file_path}", original_exception=e) from e
        except Exception as e:
            logger.exception(f"Unexpected error saving state: {e}", exc_info=True)
            raise StateManagementError(f"Unexpected error saving state: {e}", original_exception=e) from e


    # --- State Accessors and Mutators ---

    def get_unprocessed_ids(self) -> Set[str]:
        """Returns a copy of the set of unprocessed tweet IDs."""
        # Return a copy to prevent external modification of the internal set
        return self._state.unprocessed_tweet_ids.copy()

    def add_unprocessed_ids(self, tweet_ids: Set[str]):
        """Adds new tweet IDs to the unprocessed set, avoiding duplicates."""
        new_ids = tweet_ids - self._state.processed_tweet_ids - self._state.unprocessed_tweet_ids
        if new_ids:
             self._state.unprocessed_tweet_ids.update(new_ids)
             logger.info(f"Added {len(new_ids)} new tweet IDs to the unprocessed set.")
        else:
             logger.debug("No new unique tweet IDs provided to add to unprocessed set.")


    def get_tweet_data(self, tweet_id: str) -> Optional[TweetData]:
        """Gets the TweetData for a specific tweet ID, or None if not cached."""
        return self._state.tweet_cache.get(tweet_id)

    def update_tweet_data(self, tweet_id: str, data: TweetData):
        """
        Updates or adds the TweetData for a specific tweet ID in the cache.
        Ensures the tweet_id in the data matches the key.
        """
        if tweet_id != data.tweet_id:
            raise ValueError(f"Mismatch between key tweet_id ('{tweet_id}') and data.tweet_id ('{data.tweet_id}')")
        self._state.tweet_cache[tweet_id] = data
        logger.debug(f"Updated/added TweetData for ID: {tweet_id}")

    def get_or_create_tweet_data(self, tweet_id: str) -> TweetData:
         """Gets existing TweetData or creates a new empty one if not found."""
         if tweet_id not in self._state.tweet_cache:
             logger.debug(f"No cache entry found for tweet ID {tweet_id}, creating new TweetData.")
             self._state.tweet_cache[tweet_id] = TweetData(tweet_id=tweet_id)
         return self._state.tweet_cache[tweet_id]


    def mark_processed(self, tweet_id: str):
        """Moves a tweet ID from the unprocessed set to the processed set."""
        if tweet_id in self._state.unprocessed_tweet_ids:
            self._state.unprocessed_tweet_ids.remove(tweet_id)
            self._state.processed_tweet_ids.add(tweet_id)
            logger.debug(f"Marked tweet ID {tweet_id} as processed.")
        elif tweet_id in self._state.processed_tweet_ids:
             logger.debug(f"Tweet ID {tweet_id} is already marked as processed.")
        else:
            # If it wasn't unprocessed, should we add it directly to processed?
            # This might happen if processing is manually triggered for an ID.
            logger.warning(f"Tweet ID {tweet_id} marked processed but was not in the unprocessed set. Adding to processed set.")
            self._state.processed_tweet_ids.add(tweet_id)

    def is_processed(self, tweet_id: str) -> bool:
        """Checks if a tweet ID is in the processed set."""
        return tweet_id in self._state.processed_tweet_ids

    def get_all_tweet_data(self) -> Dict[str, TweetData]:
         """Returns the entire tweet cache."""
         return self._state.tweet_cache.copy() # Return a copy

    async def reconcile_state(self):
        """
        Performs basic validation and reconciliation checks on the loaded state.
        (e.g., ensures IDs in sets exist in cache, checks for inconsistencies).
        """
        logger.info("Performing state reconciliation...")
        issues_found = 0
        all_known_ids = self._state.unprocessed_tweet_ids.union(self._state.processed_tweet_ids)

        # Check if all IDs in sets are present in the cache
        for tweet_id in all_known_ids:
            if tweet_id not in self._state.tweet_cache:
                logger.warning(f"Reconciliation: Tweet ID {tweet_id} found in processed/unprocessed sets but missing from cache. Creating empty entry.")
                self._state.tweet_cache[tweet_id] = TweetData(tweet_id=tweet_id)
                issues_found += 1

        # Check if IDs in cache are in one of the sets
        cached_ids = set(self._state.tweet_cache.keys())
        missing_from_sets = cached_ids - all_known_ids
        if missing_from_sets:
            logger.warning(f"Reconciliation: {len(missing_from_sets)} tweet IDs found in cache but not in processed/unprocessed sets: {missing_from_sets}. Adding to unprocessed set.")
            self._state.unprocessed_tweet_ids.update(missing_from_sets)
            issues_found += len(missing_from_sets)

        # Check for overlap between processed and unprocessed
        overlap = self._state.unprocessed_tweet_ids.intersection(self._state.processed_tweet_ids)
        if overlap:
            logger.warning(f"Reconciliation: {len(overlap)} tweet IDs found in BOTH processed and unprocessed sets: {overlap}. Removing from unprocessed set.")
            self._state.unprocessed_tweet_ids.difference_update(overlap)
            issues_found += len(overlap)

        # TODO: Add more checks?
        # - Validate TweetData flags (e.g., cannot have kb_item_created=True if categories_processed=False)
        # - Check existence of referenced files (kb_item_path, media paths) - potentially expensive

        if issues_found > 0:
             logger.warning(f"State reconciliation completed with {issues_found} issues corrected/logged.")
             # Save the corrected state immediately?
             # await self._save_state_internal() # Be careful about lock contention if called externally
        else:
             logger.info("State reconciliation completed. No major inconsistencies found.")
