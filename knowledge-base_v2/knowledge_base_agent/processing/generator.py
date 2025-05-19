import asyncio
import logging
import os
from pathlib import Path
from typing import Optional, List
from datetime import datetime # Added for last_generated_at

import aiofiles.os
import shutil # Ensure shutil is imported

from ..config import Config
from ..exceptions import GenerationError, FileOperationError
from ..interfaces.ollama import OllamaClient
from ..types import TweetData, MediaItem # Assuming MediaItem is imported for _copy_media_item type hint
from ..utils import file_io # Import file_io directly
from .state import StateManager # Not used directly in generate_kb_item_for_tweet

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
    prompt_parts.append(tweet_data.combined_text or 'N/A') # Use combined_text
    prompt_parts.append("```")

    if tweet_data.media_items:
        prompt_parts.append("\n## Associated Media Descriptions")
        has_desc = False
        for i, item in enumerate(tweet_data.media_items):
            if item.type == "image" and item.description and not item.interpret_error: # Check for interpret_error
                 prompt_parts.append(f"### Media {i+1} ({item.type or 'unknown'}):") # Use item.type
                 prompt_parts.append(item.description)
                 has_desc = True
        if not has_desc:
             prompt_parts.append("(No valid descriptions generated or no applicable media)")

    prompt_parts.append("\n## Generated Knowledge Base Content")
    prompt_parts.append("Please generate the Markdown content for the README file based on the information above:")
    return "\n".join(prompt_parts)


async def _copy_media_item_to_kb(
    media_item: MediaItem, # Use MediaItem type hint
    tweet_id: str, # For constructing source media path
    config: Config,
    target_item_dir: Path # Absolute path to .../kb-generated/main/sub/item
) -> Optional[Path]:
    """
    Copies a single media item from media_cache to the KB item directory.
    Returns relative target path (filename) on success for linking in README.
    """
    if not media_item.local_path:
        logger.warning(f"Tweet {tweet_id}, Media {media_item.original_url}: Cannot copy, local_path is missing.")
        return None

    # Construct full source path
    # Assuming media_item.local_path is stored by cacher as relative to "media_cache/tweet_id/"
    # e.g., local_path = Path("image.jpg")
    # If local_path is relative to "media_cache/" e.g. Path("tweet_id/image.jpg"), adjust accordingly.
    media_cache_base_dir = config.data_dir / "media_cache"
    source_path_in_tweet_cache = media_cache_base_dir / tweet_id / media_item.local_path
    
    # Resolve to ensure it's absolute and normalized
    source_path_absolute = source_path_in_tweet_cache.resolve()


    if not await aiofiles.os.path.exists(source_path_absolute):
        logger.error(f"Tweet {tweet_id}, Media {media_item.original_url}: Source file not found at {source_path_absolute}, cannot copy.")
        return None

    target_filename = media_item.local_path.name # Use the original filename from the media item's local_path
    target_path_absolute = target_item_dir / target_filename

    try:
        logger.debug(f"Copying media file {source_path_absolute} to {target_path_absolute}")
        await file_io.ensure_dir_async(target_item_dir) # Ensure target item dir exists

        try:
             await asyncio.to_thread(os.link, source_path_absolute, target_path_absolute)
             logger.debug(f"Hard linked media {target_filename} for tweet {tweet_id}")
        except (OSError, AttributeError):
             await asyncio.to_thread(shutil.copy2, source_path_absolute, target_path_absolute)
             logger.debug(f"Copied media {target_filename} for tweet {tweet_id}")

        return Path(target_filename) # Return just the filename for linking

    except Exception as e:
        logger.error(f"Unexpected error copying media file {source_path_absolute} for tweet {tweet_id}: {e}", exc_info=True)
        return None

async def generate_kb_item_for_tweet(
    tweet_data: TweetData,
    ollama_client: OllamaClient,
    config: Config
):
    """
    Generates the KB item content (README.md), creates the directory structure,
    and copies associated media files. Updates TweetData in place.
    """
    tweet_id = tweet_data.tweet_id
    if not all([tweet_data.main_category, tweet_data.sub_category, tweet_data.item_name]):
        logger.warning(f"Skipping KB generation for {tweet_id}: Missing category/item name.")
        tweet_data.error_message = "Missing category/item name for generation."
        tweet_data.failed_phase = "Generation"
        tweet_data.kb_item_created = False
        return

    logger.info(f"Generating KB item for tweet {tweet_id}: "
                f"{tweet_data.main_category}/{tweet_data.sub_category}/{tweet_data.item_name}")

    item_dir_relative = Path(tweet_data.main_category) / tweet_data.sub_category / tweet_data.item_name
    item_dir_absolute = config.knowledge_base_dir.resolve() / item_dir_relative
    readme_path = item_dir_absolute / "README.md"

    generated_readme_content = ""
    copied_media_filenames: List[Path] = []

    try:
        await file_io.ensure_dir_async(item_dir_absolute)
        prompt = _build_generation_prompt(tweet_data)
        logger.debug(f"Generating README content for {tweet_id}...")
        
        response = await ollama_client.generate( # Assuming this returns the dict directly
            prompt=prompt,
            system_prompt=GENERATION_SYSTEM_PROMPT,
            model=config.text_model,
            stream=False
        )
        # If ollama_client.generate returns raw response, adapt as in categorizer
        # For now, assuming 'response' key holds the text if it's a dict, or it's the text itself
        if isinstance(response, dict) and 'response' in response:
            generated_readme_content = response['response'].strip()
        elif isinstance(response, str): # If client directly returns string
            generated_readme_content = response.strip()
        else:
            raise GenerationError(tweet_id, f"Unexpected response structure from Ollama for generation: {response}")

        if not generated_readme_content:
             raise GenerationError(tweet_id, "LLM returned empty content for README.")
        logger.info(f"README content generated for {tweet_id} (Length: {len(generated_readme_content)}).")

        media_copy_tasks = []
        for item in tweet_data.media_items:
            if item.local_path and await aiofiles.os.path.exists(config.data_dir / "media_cache" / tweet_id / item.local_path): # Check existence before scheduling
                media_copy_tasks.append(
                     _copy_media_item_to_kb(item, tweet_id, config, item_dir_absolute)
                )
        
        if media_copy_tasks:
            logger.debug(f"Copying {len(media_copy_tasks)} media items for {tweet_id}...")
            results = await asyncio.gather(*media_copy_tasks, return_exceptions=True)
            for result in results:
                 if isinstance(result, Path):
                      copied_media_filenames.append(result)
                 elif result is not None: # Log errors from gather if they are not None
                      logger.error(f"Error during media copy for {tweet_id}: {result}")
        
        if copied_media_filenames:
            generated_readme_content += "\n\n## Media\n"
            for media_filename in copied_media_filenames:
                 link_name = media_filename.name
                 if link_name.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.webp')):
                      generated_readme_content += f"\n![{link_name}](./{link_name})"
                 else:
                      generated_readme_content += f"\n[{link_name}](./{link_name})"
        
        await file_io.write_text_atomic_async(readme_path, generated_readme_content)
        
        tweet_data.generated_content = generated_readme_content
        tweet_data.kb_item_path = item_dir_relative
        tweet_data.kb_media_paths = [item_dir_relative / fname for fname in copied_media_filenames]
        tweet_data.kb_item_created = True
        tweet_data.error_message = None
        tweet_data.failed_phase = None
        logger.info(f"KB item generation successful for tweet {tweet_id} at {item_dir_relative}")

    except Exception as e:
        logger.error(f"Error during KB item generation for tweet {tweet_id}: {e}", exc_info=True)
        tweet_data.kb_item_created = False
        tweet_data.error_message = f"Generation error: {e}"
        tweet_data.failed_phase = "Generation"

async def run_generate_phase(
    tweet_id: str,
    tweet_data: TweetData,
    config: Config,
    ollama_client: OllamaClient,
    state_manager: StateManager, # Now used for should_process check
    force_regenerate: bool = False,
    **kwargs
):
    """
    Phase function for generating KB item for a single tweet.
    Called by the AgentPipeline.
    """
    logger.debug(f"Running generate phase for tweet ID: {tweet_id}. Force regenerate: {force_regenerate}")

    if not tweet_data.cache_complete or \
       not tweet_data.media_processed or \
       not tweet_data.categories_processed:
        logger.warning(f"Tweet {tweet_id}: Skipping generation, prerequisite phases not complete.")
        return

    should_process = state_manager.should_process_phase(tweet_id, "Generation", force_regenerate)
    if not should_process:
        logger.info(f"Tweet {tweet_id}: Skipping generation phase based on state and preferences.")
        return

    await generate_kb_item_for_tweet(
        tweet_data=tweet_data,
        ollama_client=ollama_client,
        config=config
    )
    # Pipeline saves state
