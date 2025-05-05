import asyncio
import logging
import os
from pathlib import Path
from typing import Optional

import aiofiles.os

from ..config import Config
from ..exceptions import GenerationError, FileOperationError
from ..interfaces.ollama import OllamaClient
from ..types import TweetData
from ..utils import file_io, markdown as md_utils # Use markdown utils if needed later
from .state import StateManager

logger = logging.getLogger(__name__)

# --- Prompt Engineering ---
GENERATION_SYSTEM_PROMPT = """
You are an AI assistant creating a knowledge base entry from a tweet and its potential thread.
Based on the provided Combined Tweet Text (including thread), Image Descriptions, and Categories:
1. Write a comprehensive summary or explanation of the topic discussed.
2. Format the output as Markdown suitable for a README file.
3. Include relevant context, details, and explanations based *only* on the provided information.
4. Do NOT add any preamble like "Here is the summary:" or "## Summary". Just start with the Markdown content.
5. If the text contains code blocks, preserve them using Markdown code fences.
"""

def _build_generation_prompt(tweet_data: TweetData) -> str:
    """Builds the prompt string for the KB content generation LLM call."""
    prompt_parts = []
    prompt_parts.append(f"# Knowledge Base Entry: {tweet_data.main_category} / {tweet_data.sub_category} / {tweet_data.item_name}")
    prompt_parts.append(f"\nOriginal Tweet URL: {tweet_data.source_url or 'N/A'}")
    prompt_parts.append(f"Author: @{tweet_data.author_handle or 'Unknown'} (ID: {tweet_data.author_id or 'N/A'})")
    prompt_parts.append(f"Date: {tweet_data.created_at.strftime('%Y-%m-%d %H:%M') if tweet_data.created_at else 'N/A'}")

    prompt_parts.append("\n## Combined Tweet Content (including thread)")
    prompt_parts.append("```text")
    prompt_parts.append(tweet_data.combined_text or 'N/A')
    prompt_parts.append("```")

    if tweet_data.media_items:
        prompt_parts.append("\n## Associated Media Descriptions")
        has_desc = False
        for i, item in enumerate(tweet_data.media_items):
            if item.description and item.description != "[Error generating description]":
                 prompt_parts.append(f"### Media {i+1} ({item.type or 'unknown'}):")
                 prompt_parts.append(item.description)
                 has_desc = True
        if not has_desc:
             prompt_parts.append("(No valid descriptions generated or no media)")


    prompt_parts.append("\n## Generated Knowledge Base Content")
    prompt_parts.append("Please generate the Markdown content for the README file based on the information above:")
    return "\n".join(prompt_parts)


async def _copy_media_item(media_item, source_base_dir: Path, target_item_dir: Path) -> Optional[Path]:
    """Copies a single media item, returns relative target path on success."""
    if not media_item.local_path:
        logger.warning(f"Cannot copy media, local_path is missing for {media_item.original_url}")
        return None

    source_path = media_item.local_path
    if not source_path.is_absolute():
        source_path = (source_base_dir / source_path).resolve()

    if not await aiofiles.os.path.exists(source_path):
        logger.error(f"Media source file not found, cannot copy: {source_path}")
        return None

    target_filename = source_path.name # Use the same filename
    target_path = target_item_dir / target_filename

    try:
        logger.debug(f"Copying media file {source_path} to {target_path}")
        # Use asyncio.to_thread for shutil.copy2 if preserving metadata is crucial
        # For simple copy, aiofiles.os.copyfile might suffice (check compatibility)
        # Let's try wrapping os.link or shutil.copy2 for better performance/metadata
        try:
             # Try hard link first (fastest, same filesystem only)
             await asyncio.to_thread(os.link, source_path, target_path)
             logger.debug(f"Hard linked media {target_filename}")
        except (OSError, AttributeError): # OSError (cross-device link), AttributeError (Windows?)
             # Fallback to copy
             await asyncio.to_thread(shutil.copy2, source_path, target_path) # copy2 preserves metadata
             logger.debug(f"Copied media {target_filename}")

        # Return the path relative to the KB base directory for storage/linking
        # Assuming target_item_dir is like .../kb-generated/main/sub/item
        # We want main/sub/item/filename
        # kb_base_dir = target_item_dir.parent.parent.parent # Risky assumption
        # A better way: get kb_base_dir from config
        # relative_target_path = target_path.relative_to(config.knowledge_base_dir)
        # For now, just return the filename, linking can handle directory structure
        return Path(target_filename) # Return just the filename for simplicity in README links

    except (IOError, OSError, FileOperationError) as e:
        logger.error(f"Failed to copy media file {source_path} to {target_path}: {e}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error copying media file {source_path}: {e}", exc_info=True)
        return None

import shutil # Import shutil for copy2 fallback

async def generate_kb_item(
    tweet_data: TweetData,
    ollama_client: OllamaClient,
    config: Config,
    state_manager: StateManager
):
    """
    Generates the KB item content (README.md), creates the directory structure,
    and copies associated media files.

    Updates the TweetData object and saves state via StateManager.
    """
    tweet_id = tweet_data.tweet_id
    if not all([tweet_data.main_category, tweet_data.sub_category, tweet_data.item_name]):
         logger.warning(f"Skipping KB generation for {tweet_id}: Missing category/item name.")
         tweet_data.mark_failed("Generator", "Missing category/item name.")
         state_manager.update_tweet_data(tweet_id, tweet_data)
         return

    logger.info(f"Generating KB item for tweet {tweet_id}: "
                f"{tweet_data.main_category}/{tweet_data.sub_category}/{tweet_data.item_name}")

    # Define paths
    item_dir_relative = Path(tweet_data.main_category) / tweet_data.sub_category / tweet_data.item_name
    item_dir_absolute = config.knowledge_base_dir.resolve() / item_dir_relative
    readme_path = item_dir_absolute / "README.md"
    media_cache_dir = config.data_dir / "media_cache"

    # IMPORTANT: Media cache dir for source is now per-tweet
    media_source_base_dir = media_cache_dir / tweet_id

    generated_content = ""
    copied_media_paths = [] # Store relative paths (filenames) of copied media

    try:
        # 1. Ensure Directory Exists
        await file_io.ensure_dir_async(item_dir_absolute)

        # 2. Generate README Content via LLM
        prompt = _build_generation_prompt(tweet_data)
        logger.debug(f"Generating README content for {tweet_id}...")
        response = await ollama_client.generate(
            prompt=prompt,
            system_prompt=GENERATION_SYSTEM_PROMPT,
            model=config.text_model, # Use primary text model
            stream=False
        )
        if not isinstance(response, dict) or 'response' not in response:
             raise GenerationError(tweet_id, f"Unexpected response structure from Ollama for generation: {response}")

        generated_content = response['response'].strip()
        if not generated_content:
             raise GenerationError(tweet_id, "LLM returned empty content for README.")

        logger.info(f"README content generated for {tweet_id} (Length: {len(generated_content)}).")


        # 3. Copy Media Files
        media_copy_tasks = []
        for item in tweet_data.media_items:
            if item.local_path: # Only copy if it was successfully cached
                media_copy_tasks.append(
                     _copy_media_item(item, media_source_base_dir, item_dir_absolute)
                )

        if media_copy_tasks:
            logger.debug(f"Copying {len(media_copy_tasks)} media items for {tweet_id}...")
            results = await asyncio.gather(*media_copy_tasks, return_exceptions=True)
            for result in results:
                 if isinstance(result, Path):
                      copied_media_paths.append(result) # Store relative path (filename)
                 elif isinstance(result, Exception):
                      logger.error(f"Error gathering media copy results for {tweet_id}: {result}")
                 # else: None was returned on copy failure, logged in _copy_media_item


        # 4. Append Media Links to README Content
        if copied_media_paths:
            generated_content += "\n\n## Media\n"
            for relative_media_path in copied_media_paths:
                 # Assume filename is sufficient for relative linking within README
                 filename = relative_media_path.name
                 if filename.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.webp')):
                      generated_content += f"\n![{filename}](./{filename})"
                 else: # Basic link for other types (videos, etc.)
                      generated_content += f"\n[{filename}](./{filename})"


        # 5. Write README.md
        logger.debug(f"Writing README.md to {readme_path}")
        await file_io.write_text_atomic_async(readme_path, generated_content)


        # 6. Update TweetData state
        tweet_data.generated_content = generated_content # Store generated content? Optional.
        tweet_data.kb_item_path = item_dir_relative # Store relative path
        tweet_data.kb_media_paths = copied_media_paths # Store relative paths (filenames)
        tweet_data.kb_item_created = True
        # Clear previous error if reprocessing succeeded
        if tweet_data.failed_phase == "Generator":
            tweet_data.error_message = None
            tweet_data.failed_phase = None
        logger.info(f"KB item generation successful for tweet {tweet_id} at {item_dir_relative}")


    except Exception as e:
        logger.error(f"Error during KB item generation phase for tweet {tweet_id}: {e}", exc_info=True)
        tweet_data.kb_item_created = False
        if not isinstance(e, GenerationError):
            tweet_data.mark_failed("Generator", e)
        else:
             tweet_data.mark_failed("Generator", str(e))
        # Don't re-raise

    finally:
        state_manager.update_tweet_data(tweet_id, tweet_data)
