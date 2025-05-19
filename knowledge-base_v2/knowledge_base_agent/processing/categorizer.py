import asyncio
import json
import logging
import re # Import re for JSON extraction and sanitization
from typing import Optional

from ..config import Config # Not directly used, but good practice
from ..exceptions import CategorizationError
from ..interfaces.ollama import OllamaClient
from ..types import TweetData
from .state import StateManager

logger = logging.getLogger(__name__)

# --- Prompt Engineering ---
CATEGORIZATION_SYSTEM_PROMPT = """
You are an expert categorizer for knowledge base items derived from tweets/threads.
Analyze the provided tweet content (text, potential thread, and image descriptions) and determine:
1.  A concise, relevant `main_category` (e.g., "Technology", "Art", "Science", "Programming", "News"). Use Title Case.
2.  A specific `sub_category` within the main category (e.g., "Python", "AI Models", "Digital Painting", "Astrophysics"). Use Title Case.
3.  A short, descriptive, filesystem-safe `item_name` based on the content's core subject (use lowercase words separated by hyphens, e.g., "ollama-vision-models" or "stable-diffusion-tips"). Max 50 chars.

Respond ONLY with a single, valid JSON object containing these three keys: "main_category", "sub_category", and "item_name". Do not include any other text, explanation, markdown formatting, or code fences around the JSON.

Example Valid Response:
{
  "main_category": "Programming",
  "sub_category": "Python",
  "item_name": "asyncio-best-practices"
}
"""

def _build_categorization_prompt(tweet_data: TweetData) -> str:
    """Builds the prompt string for the categorization LLM call."""
    prompt_parts = []
    prompt_parts.append("Tweet/Thread Content:")
    # Use combined_text which includes thread parts
    prompt_parts.append(f"```text\n{tweet_data.combined_text or 'N/A'}\n```")

    if tweet_data.media_items:
        prompt_parts.append("\nImage Descriptions:")
        has_desc = False
        for i, item in enumerate(tweet_data.media_items):
            # Only include valid, non-error descriptions
            if item.type == "image" and item.description and item.description != "[Error generating description]":
                 prompt_parts.append(f" - Image {i+1}: {item.description}")
                 has_desc = True
        if not has_desc:
             prompt_parts.append(" (No valid image descriptions available)")
    else:
        prompt_parts.append("\n(No media items)")

    prompt_parts.append("\nBased *only* on the content above, provide the JSON categorization object.")
    return "\n".join(prompt_parts)

def _sanitize_item_name(name: str) -> str:
     """Sanitizes item_name for filesystem compatibility."""
     if not isinstance(name, str): return "untitled-item"
     # Lowercase
     name = name.lower()
     # Replace whitespace and underscores with hyphens
     name = re.sub(r"[\s_]+", "-", name)
     # Remove characters not suitable for filenames/URLs
     # Allow letters, numbers, hyphens.
     name = re.sub(r"[^a-z0-9\-]", "", name)
     # Remove consecutive hyphens
     name = re.sub(r"-+", "-", name)
     # Remove leading/trailing hyphens
     name = name.strip("-")
     # Limit length
     name = name[:50] # Max 50 chars
     # Prevent empty names after sanitization
     return name or "untitled-item"

async def categorize_content(
    tweet_data: TweetData,
    ollama_client: OllamaClient,
    state_manager: StateManager
):
    """
    Uses an LLM to determine main_category, sub_category, and item_name.
    Updates the TweetData object and saves state via StateManager.
    """
    tweet_id = tweet_data.tweet_id
    logger.info(f"Categorizing content for tweet {tweet_id}...")

    if not tweet_data.combined_text and not any(
        item.description and item.description != "[Error generating description]"
        for item in tweet_data.media_items if item.type == 'image'
    ):
        logger.warning(f"Skipping categorization for tweet {tweet_id}: No text/thread or valid image descriptions available.")
        tweet_data.categories_processed = False
        tweet_data.mark_failed("Categorizer", "No content to categorize.")
        return

    prompt = _build_categorization_prompt(tweet_data)

    try:
        response = await ollama_client.generate(
            prompt=prompt,
            system_prompt=CATEGORIZATION_SYSTEM_PROMPT,
            model=state_manager.config.text_model,
            stream=False,
            format="json",
        )

        if not isinstance(response, dict) or 'response' not in response:
            raise CategorizationError(tweet_id, f"Unexpected response structure from Ollama: {response}")

        llm_output = response['response'].strip()
        logger.debug(f"LLM JSON output for categorization '{tweet_id}':\n{llm_output}")

        # --- Simplified JSON Parsing ---
        # With format="json", we expect the output to be directly parsable JSON
        try:
            parsed_json = json.loads(llm_output)
        except json.JSONDecodeError as json_err:
            # This shouldn't happen often with format="json", but catch just in case
            logger.error(f"Failed to parse expected JSON response from LLM for tweet {tweet_id}: {json_err}\nLLM Raw Output:\n{llm_output}")
            raise CategorizationError(tweet_id, "LLM response was not valid JSON despite format=json.", original_exception=json_err) from json_err

        # --- Validate Parsed JSON ---
        if not isinstance(parsed_json, dict):
             raise CategorizationError(tweet_id, f"LLM response parsed, but is not a JSON object (dict). Type: {type(parsed_json)}")

        # Check for required keys (case-insensitive check just in case)
        required_keys = {"main_category", "sub_category", "item_name"}
        present_keys_lower = {k.lower() for k in parsed_json.keys()}
        if not required_keys.issubset(present_keys_lower):
            missing = required_keys - present_keys_lower
            raise CategorizationError(tweet_id, f"LLM JSON response missing required keys: {missing}. Response: {parsed_json}")

        # Find actual keys (preserving original case from LLM if possible)
        key_map = {k.lower(): k for k in parsed_json.keys()}
        main_cat = parsed_json[key_map["main_category"]].strip()
        sub_cat = parsed_json[key_map["sub_category"]].strip()
        item_name_raw = parsed_json[key_map["item_name"]].strip()

        # --- Assign & Sanitize ---
        tweet_data.main_category = main_cat
        tweet_data.sub_category = sub_cat
        tweet_data.item_name = _sanitize_item_name(item_name_raw)

        if not tweet_data.main_category or not tweet_data.sub_category or not tweet_data.item_name:
             logger.warning(f"LLM returned empty values for category/item name for tweet {tweet_id}. Parsed: {parsed_json}")
             raise CategorizationError(tweet_id, "LLM returned empty values for category/item name.")

        # --- Mark Success ---
        tweet_data.categories_processed = True
        if tweet_data.failed_phase == "Categorizer":
            tweet_data.error_message = None
            tweet_data.failed_phase = None
        logger.info(f"Categorization successful for tweet {tweet_id}: "
                    f"{tweet_data.main_category}/{tweet_data.sub_category}/{tweet_data.item_name}")
    except Exception as e:
        logger.error(f"Error during categorization phase for tweet {tweet_id}: {e}", exc_info=True)
        tweet_data.categories_processed = False
        tweet_data.mark_failed("Categorizer", str(e))
    finally:
        state_manager.update_tweet_data(tweet_id, tweet_data)

async def run_categorize_phase(
    tweet_id: str,
    tweet_data: TweetData,
    config: Config,
    ollama_client: OllamaClient,
    state_manager: StateManager, # Now used for should_process check
    force_recategorize: bool = False,
    **kwargs
):
    """
    Phase function for categorizing content of a single tweet.
    Called by the AgentPipeline.
    """
    logger.debug(f"Running categorize phase for tweet ID: {tweet_id}. Force recategorize: {force_recategorize}")

    if not tweet_data.cache_complete or not tweet_data.media_processed:
        logger.warning(f"Tweet {tweet_id}: Skipping categorization, prerequisite phases (cache/interpret) not complete.")
        return

    should_process = state_manager.should_process_phase(tweet_id, "Categorization", force_recategorize)
    if not should_process:
        logger.info(f"Tweet {tweet_id}: Skipping categorization phase based on state and preferences.")
        return

    await categorize_content(
        tweet_data=tweet_data,
        ollama_client=ollama_client,
        state_manager=state_manager
    )
    # Pipeline saves state
