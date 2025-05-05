import asyncio
import logging
from pathlib import Path
from typing import Dict, Any, Optional

from ..config import Config # Needed to find data_dir
from ..exceptions import FileOperationError
from ..utils.file_io import read_json_async, write_json_atomic_async

logger = logging.getLogger(__name__)

UI_STATE_FILENAME = "ui_state.json"
_ui_state_cache: Optional[Dict[str, Any]] = None
_lock = asyncio.Lock() # Lock for reading/writing the file/cache

def get_ui_state_path(config: Config) -> Path:
    """Gets the absolute path to the UI state file."""
    return config.data_dir.resolve() / UI_STATE_FILENAME

async def load_ui_state(config: Config) -> Dict[str, Any]:
    """
    Loads UI state from the JSON file, using an in-memory cache.
    Returns default empty dict if file doesn't exist or is invalid.
    """
    global _ui_state_cache
    async with _lock:
        if _ui_state_cache is not None:
            return _ui_state_cache.copy() # Return copy from cache

        file_path = get_ui_state_path(config)
        state: Dict[str, Any] = {}
        if await asyncio.to_thread(file_path.exists):
            logger.info(f"Loading UI state from {file_path}")
            try:
                state = await read_json_async(file_path)
                if not isinstance(state, dict):
                    logger.warning(f"UI state file {file_path} does not contain a valid JSON object. Resetting.")
                    state = {}
            except FileOperationError as e:
                logger.error(f"Error reading UI state file {file_path}: {e}. Returning default state.")
                state = {}
            except Exception as e:
                 logger.error(f"Unexpected error loading UI state file {file_path}: {e}. Returning default state.", exc_info=True)
                 state = {}
        else:
            logger.info(f"UI state file {file_path} not found. Initializing empty state.")
            state = {} # Default empty state

        _ui_state_cache = state # Store in cache
        return _ui_state_cache.copy()


async def save_ui_state(config: Config, new_state: Dict[str, Any]):
    """
    Saves the entire UI state dictionary to the JSON file atomically
    and updates the in-memory cache.
    """
    global _ui_state_cache
    if not isinstance(new_state, dict):
         logger.error("Attempted to save non-dictionary as UI state.")
         return

    async with _lock:
        file_path = get_ui_state_path(config)
        logger.info(f"Saving UI state to {file_path}")
        try:
            # Ensure data directory exists
            await asyncio.to_thread(file_path.parent.mkdir, parents=True, exist_ok=True)
            await write_json_atomic_async(file_path, new_state, indent=2)
            _ui_state_cache = new_state.copy() # Update cache on successful save
            logger.debug("UI state saved successfully.")
        except FileOperationError as e:
            logger.error(f"Error writing UI state file {file_path}: {e}")
            # Don't update cache if save failed
        except Exception as e:
            logger.error(f"Unexpected error saving UI state file {file_path}: {e}", exc_info=True)
            # Don't update cache if save failed


async def update_ui_state_key(config: Config, key: str, value: Any):
    """
    Updates a single key in the UI state and saves the entire state.
    """
    # Load current state first (uses cache)
    current_state = await load_ui_state(config)
    current_state[key] = value
    # Save the modified state
    await save_ui_state(config, current_state)
