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

    async def load_state(self):
        """Loads the state from the file if it exists, otherwise initializes a new state."""
        logger.info(f"Attempting to load state from {self.state_file_path}...")
        try:
            if await asyncio.to_thread(self.state_file_path.exists):
                raw_state_data = await read_json_async(self.state_file_path)
                
                # Correctly populate self._state
                loaded_unprocessed_ids = set(raw_state_data.get("unprocessed_tweet_ids", []))
                loaded_processed_ids = set(raw_state_data.get("processed_tweet_ids", []))
                loaded_tweet_cache_raw = raw_state_data.get("tweet_cache", {})
                
                loaded_tweet_cache: Dict[str, TweetData] = {}
                for tweet_id, tweet_data_dict in loaded_tweet_cache_raw.items():
                    try:
                        # Use model_validate for robust parsing and default application
                        # This ensures that new fields in TweetData with defaults (like Optional[datetime]=None)
                        # are correctly initialized if missing from the stored JSON.
                        validated_data = TweetData.model_validate(tweet_data_dict)
                        loaded_tweet_cache[tweet_id] = validated_data
                    except Exception as e: # Catch PydanticValidationError specifically if preferred
                        logger.error(f"Error validating/deserializing TweetData for ID {tweet_id} from cache: {e}. Skipping this item. Data: {tweet_data_dict}")
                        continue # Skip problematic items

                self._state = ProcessingState(
                    unprocessed_tweet_ids=loaded_unprocessed_ids,
                    processed_tweet_ids=loaded_processed_ids,
                    tweet_cache=loaded_tweet_cache,
                    last_run_timestamp=raw_state_data.get("last_run_timestamp") # Keep existing timestamp
                )
                
                # Log based on the actual self._state contents
                logger.info(f"Successfully loaded state. "
                            f"{len(self._state.unprocessed_tweet_ids)} unprocessed, "
                            f"{len(self._state.processed_tweet_ids)} processed, "
                            f"{len(self._state.tweet_cache)} items in cache.")
            else:
                logger.warning(f"State file {self.state_file_path} does not exist. Initializing new empty state.")
                await self._initialize_empty_state() # This already sets self._state correctly
        except FileOperationError as e:
            logger.error(f"File operation error loading state: {e}")
            logger.info("Initializing new empty state due to file operation error.")
            await self._initialize_empty_state()
        except Exception as e:
            logger.error(f"Unexpected error loading state: {e}", exc_info=True)
            logger.info("Initializing new empty state due to unexpected error.")
            await self._initialize_empty_state()

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

    def add_unprocessed_ids(self, tweet_ids: Set[str]) -> int: # Return the count added
        """Adds new tweet IDs to the unprocessed set, avoiding duplicates. Returns count of new IDs added."""
        processed_or_already_unprocessed = self._state.processed_tweet_ids.union(self._state.unprocessed_tweet_ids)
        new_ids = tweet_ids - processed_or_already_unprocessed
        count_added = len(new_ids)
        if count_added > 0:
             self._state.unprocessed_tweet_ids.update(new_ids)
             logger.info(f"Added {count_added} new tweet IDs to the unprocessed set.")
        else:
             logger.debug("No new unique tweet IDs provided to add to unprocessed set.")
        return count_added # Return count


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

    def get_or_create_tweet_data(self, tweet_id: str, tweet_url: Optional[str] = None) -> TweetData:
         """Gets existing TweetData or creates a new empty one if not found. Optionally sets the source URL."""
         if tweet_id not in self._state.tweet_cache:
             logger.debug(f"No cache entry found for tweet ID {tweet_id}, creating new TweetData.")
             self._state.tweet_cache[tweet_id] = TweetData(tweet_id=tweet_id, source_url=tweet_url)
         elif tweet_url and not self._state.tweet_cache[tweet_id].source_url:
             self._state.tweet_cache[tweet_id].source_url = tweet_url
             logger.debug(f"Updated source_url for tweet ID {tweet_id}.")
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

    def get_all_known_ids(self) -> Set[str]:
        """Returns a set of all tweet IDs known to the state (i.e., all keys in the cache)."""
        return set(self._state.tweet_cache.keys())

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

    def should_process_phase(self, tweet_id: str, phase_name: str, force_flag: bool = False) -> bool:
        """
        Determines if a specific phase should be processed for a tweet based on its current state and force flag.
        """
        tweet_data = self.get_tweet_data(tweet_id)
        if not tweet_data:
            return True  # If no data exists, it needs processing

        if force_flag:
            logger.info(f"Tweet {tweet_id}: Force flag enabled for phase '{phase_name}'.")
            return True

        if phase_name == "Caching" and not tweet_data.cache_complete:
            return True
        elif phase_name == "Interpretation" and not tweet_data.media_processed:
            return True
        elif phase_name == "Categorization" and not tweet_data.categories_processed:
            return True
        elif phase_name == "Generation" and not tweet_data.kb_item_created:
            return True
        elif phase_name == "DBSync" and not tweet_data.db_synced:
            return True
        elif tweet_data.failed_phase == phase_name or (tweet_data.error_message and phase_name.lower() in tweet_data.error_message.lower()):
            logger.info(f"Tweet {tweet_id}: Has previous error for phase '{phase_name}': '{tweet_data.error_message}'. Re-processing.")
            return True
        else:
            logger.info(f"Tweet {tweet_id}: Phase '{phase_name}' already processed and no error. Skipping unless forced.")
            return False

    def reset_phase_flags(self, tweet_id: str, phase_name: str):
        """
        Resets the relevant flags and clears errors for a specific phase when forced.
        """
        tweet_data = self.get_tweet_data(tweet_id)
        if not tweet_data:
            return

        if tweet_data.failed_phase == phase_name:
            tweet_data.error_message = None
            tweet_data.failed_phase = None

        if phase_name == "Caching":
            tweet_data.cache_complete = False
        elif phase_name == "Interpretation":
            tweet_data.media_processed = False
        elif phase_name == "Categorization":
            tweet_data.categories_processed = False
            tweet_data.main_category = None
            tweet_data.sub_category = None
            tweet_data.item_name = None
        elif phase_name == "Generation":
            tweet_data.kb_item_created = False
            tweet_data.kb_item_path = None
            tweet_data.kb_media_paths = []
            tweet_data.generated_content = None
        elif phase_name == "DBSync":
            tweet_data.db_synced = False

        self.update_tweet_data(tweet_id, tweet_data)
        logger.info(f"Tweet {tweet_id}: Flags reset for phase '{phase_name}'.")

    async def _initialize_empty_state(self):
        self._state = ProcessingState()
        self._state.unprocessed_tweet_ids = set()
        self._state.processed_tweet_ids = set()
        self._state.tweet_cache = {}
        self._state.last_run_timestamp = datetime.utcnow()
        await self._save_state_internal()
