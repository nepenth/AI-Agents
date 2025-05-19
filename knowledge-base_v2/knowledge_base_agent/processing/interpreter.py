import asyncio
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional
import aiofiles

from ..config import Config
from ..types import TweetData, MediaItem # Assuming MediaItem is part of types.py
from ..interfaces.ollama import OllamaClient
from .state import StateManager # Though not strictly used in this phase's core logic, often good for consistency

logger = logging.getLogger(__name__)

async def interpret_single_media_item(
    media_item: MediaItem,
    tweet_id: str, # For logging context
    ollama_client: OllamaClient,
    config: Config,
    force_reinterpret: bool = False
) -> bool:
    """
    Interprets a single media item (currently images).
    Updates media_item.description and media_item.interpret_error in place.
    Returns True if successful or not applicable, False on error during interpretation.
    """
    if not media_item.local_path:
        logger.warning(f"Tweet {tweet_id}, Media {media_item.original_url}: No local_path, cannot interpret.")
        media_item.interpret_error = "Missing local_path for interpretation."
        return False # Indicate an issue preventing interpretation

    if media_item.type != "image":
        logger.info(f"Tweet {tweet_id}, Media {media_item.original_url}: Type '{media_item.type}' not interpretable by vision model. Skipping.")
        # Not an error, just not applicable for current vision models
        media_item.description = None # Ensure no stale description
        media_item.interpret_error = None
        return True

    if media_item.description and not force_reinterpret:
        logger.debug(f"Tweet {tweet_id}, Media {media_item.original_url}: Already has description and not forced. Skipping.")
        return True

    # Construct full path if local_path is relative
    path_to_resolve = media_item.local_path
    if not path_to_resolve.is_absolute():
        base_media_cache_dir = config.data_dir / "media_cache"
        # media_item.local_path is now expected to be relative to base_media_cache_dir
        # e.g., "tweet_id/filename.ext"
        full_media_path = (base_media_cache_dir / path_to_resolve).resolve()
    else:
        full_media_path = path_to_resolve # It's already absolute

    if not await asyncio.to_thread(full_media_path.exists):
        logger.error(f"Tweet {tweet_id}, Media {media_item.original_url}: File not found at {full_media_path} (local_path was: {media_item.local_path}) for interpretation.")
        media_item.interpret_error = f"File not found at {full_media_path}"
        return False

    logger.info(f"Tweet {tweet_id}, Media {media_item.original_url}: Interpreting image at {full_media_path}...")
    try:
        # Read the image file to get bytes
        async with aiofiles.open(full_media_path, 'rb') as f:
            image_content_bytes = await f.read()

        # Define a suitable prompt for the vision model
        prompt = (
            "Concisely describe this image. Focus on key objects, entities, "
            "setting, and any text visible. This description will be used as context for a knowledge base."
        )
        description = await ollama_client.generate_image_description(
            image_bytes=image_content_bytes, # Pass the image bytes
            prompt=prompt,
            model=config.vision_model # Ensure vision model is specified in config
        )
        if description and isinstance(description, dict) and description.get("response"):
            actual_text_description = description.get("response", "")
            media_item.description = actual_text_description.strip()
            media_item.interpret_error = None
            logger.info(f"Tweet {tweet_id}, Media {media_item.original_url}: Interpretation successful.")
            return True
        elif isinstance(description, str) and description: # Fallback for a simple string, though unlikely now
            media_item.description = description.strip()
            media_item.interpret_error = None
            logger.info(f"Tweet {tweet_id}, Media {media_item.original_url}: Interpretation successful (raw string).")
            return True
        else:
            actual_response_content = description.get("response") if isinstance(description, dict) else str(description)
            media_item.interpret_error = f"Vision model returned empty or invalid description. Response: {actual_response_content[:100]}..."
            logger.warning(f"Tweet {tweet_id}, Media {media_item.original_url}: Vision model returned empty/invalid description. Response: {actual_response_content[:100]}...")
            return False
    except Exception as e:
        logger.error(f"Tweet {tweet_id}, Media {media_item.original_url}: Error during Ollama vision processing: {e}", exc_info=True)
        media_item.interpret_error = f"Ollama error: {e}"
        return False


async def run_interpret_phase(
    tweet_id: str,
    tweet_data: TweetData,
    config: Config,
    ollama_client: OllamaClient,
    force_reinterpret: bool = False,
    **kwargs
):
    """
    Phase function for interpreting media in a single tweet.
    Called by the AgentPipeline.
    """
    logger.debug(f"Running interpret phase for tweet ID: {tweet_id}. Force reinterpret: {force_reinterpret}")

    if not tweet_data.cache_complete:
        logger.warning(f"Tweet {tweet_id}: Skipping interpretation, cache is not complete.")
        return

    if not tweet_data.media_items:
        logger.info(f"Tweet {tweet_id}: No media items to interpret.")
        tweet_data.media_processed = True
        tweet_data.media_interpret_error = None
        tweet_data.last_interpreted_at = datetime.utcnow()
        return

    all_items_succeeded_or_skipped = True
    any_item_processed_this_run = False

    for item_index, media_item in enumerate(tweet_data.media_items):
        # Re-check individual item state even if overall phase is 'should_process'
        # This allows skipping already described items if not force_reinterpreting all
        item_needs_processing = force_reinterpret or not media_item.description or media_item.interpret_error

        if item_needs_processing:
            logger.debug(f"Tweet {tweet_id}: Processing media item {item_index + 1}/{len(tweet_data.media_items)}: {media_item.original_url}")
            success = await interpret_single_media_item(
                media_item=media_item,
                tweet_id=tweet_id,
                ollama_client=ollama_client,
                config=config,
                force_reinterpret=force_reinterpret # Pass force if we want to force this specific item
            )
            if not success and media_item.type == "image": # Changed from media_type to type, count image interpretation failures
                all_items_succeeded_or_skipped = False
            if success or media_item.type != "image": # Changed from media_type to type
                any_item_processed_this_run = True # Counts if an attempt was made or non-image skipped
        else:
            logger.debug(f"Tweet {tweet_id}: Skipping already interpreted media item {item_index + 1}/{len(tweet_data.media_items)} (not forced).")

    # Update overall status
    if all_items_succeeded_or_skipped:
        tweet_data.media_processed = True
        tweet_data.media_interpret_error = None
        logger.info(f"Tweet {tweet_id}: Media interpretation phase completed successfully for all applicable items.")
    else:
        tweet_data.media_processed = False # Mark as not fully processed if any image failed
        tweet_data.media_interpret_error = "One or more media items failed interpretation."
        logger.warning(f"Tweet {tweet_id}: Media interpretation phase completed with errors for one or more items.")

    if any_item_processed_this_run or force_reinterpret:
        tweet_data.last_interpreted_at = datetime.utcnow()
    
    # Pipeline will save state
