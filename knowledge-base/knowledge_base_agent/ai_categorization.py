import requests
import logging
import asyncio
import json
import re
from typing import Tuple, Optional, Dict, Any, List
from knowledge_base_agent.naming_utils import normalize_name_for_filesystem, is_valid_item_name, fix_invalid_name, fallback_snippet_based_name
from knowledge_base_agent.exceptions import KnowledgeBaseError, AIError
from knowledge_base_agent.http_client import HTTPClient

# Define specific terms we want to reject if the AI returns them
REJECTED_CATEGORY_TERMS = {
    # Generic placeholders
    'general', 'default', 'uncategorized', 'miscellaneous', 'other', 'fallback', 'undefined',
    # Too-broad technical domains
    'software_engineering', 'programming', 'devops', 'cloud_computing', 'technology', 
    'development', 'engineering', 'computer_science', 'tech', 'software', 'development',
    'machine_learning', 'data_science', 'artificial_intelligence', 'tech_insights',
    'web_development', 'mobile_development', 'infrastructure', 'security', 'coding',
    'best_practices', 'frameworks', 'architecture'
}

def process_category_response(response_text: str, tweet_id: str) -> Tuple[str, str, str]:
    """
    Process and validate the category JSON response from the AI model strictly.

    Args:
        response_text: Raw response string from the AI model, expected to be a JSON object.
        tweet_id: Tweet identifier for logging purposes

    Returns:
        Tuple of (main_category, sub_category, item_name)

    Raises:
        ValueError: If the response format is invalid JSON, missing required keys, contains empty parts,
                    or uses rejected generic terms.
    """
    try:
        # Clean up potential markdown fences or extra text around JSON
        if "```json" in response_text:
            response_text = response_text.split("```json")[1].split("```")[0].strip()
        elif "```" in response_text:
            response_text = response_text.split("```")[1].strip()
        
        response_text = response_text.strip()

        try:
            data = json.loads(response_text)
        except json.JSONDecodeError as e:
            logging.warning(f"Invalid JSON response for tweet {tweet_id}: {e}. Response: '{response_text}'")
            raise ValueError(f"Response is not valid JSON: {e}")

        if not isinstance(data, dict):
            raise ValueError("Response JSON is not a dictionary.")

        main_category = data.get("main_category")
        sub_category = data.get("sub_category")
        item_name = data.get("item_name")

        if not main_category or not sub_category or not item_name:
            logging.warning(f"Missing required keys in JSON response for tweet {tweet_id}: {data}")
            raise ValueError("Response JSON missing required keys: 'main_category', 'sub_category', or 'item_name'")

        # Stricter validation: Ensure no part is empty after stripping
        main_category = str(main_category).strip()
        sub_category = str(sub_category).strip()
        item_name = str(item_name).strip()

        if not all([main_category, sub_category, item_name]):
            logging.warning(f"Empty category part detected for tweet {tweet_id}: main='{main_category}', sub='{sub_category}', item='{item_name}'")
            raise ValueError("Empty category parts are not allowed")

        # Normalize names
        main_category_norm = normalize_name_for_filesystem(main_category)
        sub_category_norm = normalize_name_for_filesystem(sub_category)
        item_name_norm = normalize_name_for_filesystem(item_name) # Also normalize item_name for consistency

        # Reject common unwanted generic terms
        if main_category_norm.lower() in REJECTED_CATEGORY_TERMS or sub_category_norm.lower() in REJECTED_CATEGORY_TERMS:
            logging.warning(f"Rejected generic category term for tweet {tweet_id}: {main_category_norm}/{sub_category_norm}")
            raise ValueError(f"Rejected generic category term used: {main_category_norm}/{sub_category_norm}")

        # Final check on normalized names (should be redundant if initial check and normalization are robust)
        if not main_category_norm or not sub_category_norm or not item_name_norm:
            logging.warning(f"Empty normalized category part after processing for tweet {tweet_id}: {main_category_norm}/{sub_category_norm}/{item_name_norm}")
            raise ValueError("Empty normalized category parts are not allowed")
        
        # Further validation for item_name, e.g., length, specific characters (optional, can be enhanced)
        if not is_valid_item_name(item_name_norm):
            logging.warning(f"Invalid item_name '{item_name_norm}' generated for tweet {tweet_id}. Attempting to fix or fallback.")
            # Potentially try to fix it or use a fallback, or raise ValueError
            # For now, we let it pass but it could be a point of failure for path creation
            # item_name_norm = fix_invalid_name(item_name_norm) or fallback_snippet_based_name(context_content[:100]) # Example fix

        return main_category_norm, sub_category_norm, item_name_norm

    except ValueError as ve:
        raise ve # Re-raise to be caught by retry loop
    except Exception as e:
        logging.error(f"Unexpected error processing category JSON response for tweet {tweet_id}: {e}. Response: '{response_text}'")
        raise ValueError(f"Unexpected error processing category JSON response: {e}")


async def categorize_and_name_content(
    http_client: HTTPClient,
    tweet_data: Dict[str, Any],
    text_model: str,
    tweet_id: str,
    category_manager, # Instance of CategoryManager
    max_retries: int = 5,
    fallback_model: str = ""
) -> Tuple[str, str, str]:
    """Categorize content using text and image descriptions, with robust retries, expecting JSON output."""
    
    raw_tweet_text = ""
    thread_segments = tweet_data.get("thread_tweets", [])

    if thread_segments:
        logging.debug(f"Processing categorization for tweet/thread {tweet_id} with {len(thread_segments)} segment(s).")
        all_texts = []
        for i, segment in enumerate(thread_segments):
            segment_text = segment.get("full_text", "") or segment.get("text_content", "")
            if segment_text.strip():
                if len(thread_segments) > 1:
                    all_texts.append(f"Segment {i+1}: {segment_text}")
                else:
                    all_texts.append(segment_text)
        raw_tweet_text = "\n\n".join(all_texts)
    else:
        logging.debug(f"Processing categorization for single tweet {tweet_id}.")
        raw_tweet_text = tweet_data.get('full_text', '') or tweet_data.get('text', '')

    # If we still don't have text content, try other fields that might contain text
    if not raw_tweet_text.strip():
        logging.debug(f"No direct text content found in primary fields for {tweet_id}, checking alternative fields")
        # Try top-level fields that might have text content
        for field in ['content', 'text_content', 'text']:
            if field in tweet_data and tweet_data[field] and isinstance(tweet_data[field], str):
                raw_tweet_text = tweet_data[field]
                break
    
    # Collect all image descriptions from both thread segments and top-level
    image_descriptions = []
    
    # First try thread_segments if available
    if thread_segments:
        for segment in thread_segments:
            # Try media_item_details first
            for media_item in segment.get("media_item_details", []):
                alt_text = media_item.get("alt_text")
                if alt_text and isinstance(alt_text, str) and alt_text.strip() and not alt_text.startswith("Video file:"):
                    image_descriptions.append(alt_text)
    
    # If no image descriptions from thread_segments or no thread_segments, try top-level media_item_details
    if not image_descriptions:
        for media_item in tweet_data.get("media_item_details", []):
            alt_text = media_item.get("alt_text")
            if alt_text and isinstance(alt_text, str) and alt_text.strip() and not alt_text.startswith("Video file:"):
                image_descriptions.append(alt_text)
    
    # If still no image descriptions, try the image_descriptions list directly
    if not image_descriptions:
        for desc in tweet_data.get("image_descriptions", []):
            if desc and isinstance(desc, str) and desc.strip() and not desc.startswith("Video file:"):
                image_descriptions.append(desc)

    context_content = raw_tweet_text
    if image_descriptions:
        descriptions_str = "\n".join([str(desc) for desc in image_descriptions if desc])
        if descriptions_str:
            # Ensure there's a separator if raw_tweet_text is not empty
            separator = "\n\n" if raw_tweet_text.strip() else ""
            context_content += separator + "Associated Media Insights (derived from images/videos in the tweet/thread):\n" + descriptions_str

    # Enhanced logging to debug content availability
    logging.debug(f"[AI_CAT] Tweet {tweet_id} - Raw tweet text for context: '''{raw_tweet_text[:200]}...''' (Length: {len(raw_tweet_text)})")
    logging.debug(f"[AI_CAT] Tweet {tweet_id} - Image descriptions for context: {image_descriptions}")
    logging.debug(f"[AI_CAT] Tweet {tweet_id} - Final context_content before strip: '''{context_content[:300]}...''' (Length: {len(context_content)})")

    if not context_content.strip():
        logging.error(f"No text or image description content found for tweet {tweet_id}. Cannot categorize.")
        raise AIError(f"Cannot categorize tweet {tweet_id}: No content available.")

    # category_manager here is an instance of CategoryManager passed from content_processor
    # We can use its get_all_categories() method to provide existing categories to the LLM.
    # This helps the LLM choose existing ones or create compatible new ones.
    existing_categories_structure = category_manager.get_categories() # Gets the dict
    # Format existing categories for the prompt to be more helpful
    formatted_existing_categories = "\n".join(
        [f"- {main_cat}: {', '.join(sub_cats) if isinstance(sub_cats, list) else list(sub_cats.keys()) if isinstance(sub_cats, dict) else ''}"
         for main_cat, sub_cats in existing_categories_structure.items()]
    )
    if not formatted_existing_categories:
        formatted_existing_categories = "No existing categories defined yet. You can define new ones."

    # Determine if the content is a thread for the prompt
    source_type_indicator = "Tweet Thread Content" if thread_segments else "Tweet Content"

    prompt_text = (
        "You are an expert technical content curator specializing in software engineering, system design, and technical management. "
        f"Your task is to categorize the following content ({source_type_indicator} and any associated media insights) and suggest a filename-compatible item name.\n\n"
        f"{source_type_indicator}:\n---\n{context_content}\n---\n\n"
        f"Existing Categories (use these as a guide or create specific new ones if necessary):\n{formatted_existing_categories}\n\n"
        "Instructions:\n"
        "1. Main Category:\n"
        "   - Choose a HIGHLY SPECIFIC technical domain (e.g., \"backend_frameworks\", \"devops_automation\", \"cloud_architecture\", \"testing_patterns\").\n"
        "   - **CRITICAL: DO NOT use generic top-level terms like \"software_engineering\", \"programming\", \"devops\", \"cloud_computing\".**\n"
        "   - The main category should represent the most specific technical area that is relevant, not a broad discipline.\n"
        "   - Example: Use \"concurrency_models\" instead of \"software_engineering\", use \"api_design\" instead of \"programming\".\n"
        "2. Sub Category:\n"
        "   - Specify an even more precise technical area (e.g., \"thread_safety\", \"circuit_breaker_pattern\", \"terraform_modules\").\n"
        "   - **CRITICAL: Sub-categories must be highly specific. Never use generic terms.**\n"
        "3. Item Name:\n"
        "   - Create a concise, descriptive, filesystem-friendly title (2-5 words, e.g., \"java_thread_synchronization\", \"gpt4_fine_tuning_guide\", \"terraform_state_locking\").\n"
        "   - Format: lowercase with underscores, no special characters other than underscore.\n"
        "   - Avoid generic terms like \"guide\", \"overview\", \"notes\", \"details\", \"insights\". Focus on keywords.\n\n"
        "**Response Format (MUST be a valid JSON object, on a single line if possible, or pretty-printed):**\n"
        "```json\n"
        "{\n"
        "  \"main_category\": \"example_main_category\",\n"
        "  \"sub_category\": \"example_sub_category\",\n"
        "  \"item_name\": \"example_item_name_topic\"\n"
        "}\n"
        "```\n\n"
        "Examples of good JSON responses:\n"
        "```json\n"
        "{\n"
        "  \"main_category\": \"concurrency_patterns\",\n"
        "  \"sub_category\": \"thread_synchronization\",\n"
        "  \"item_name\": \"java_atomic_variables_usage\"\n"
        "}\n"
        "```\n"
        "```json\n"
        "{\n"
        "  \"main_category\": \"ci_cd_automation\",\n"
        "  \"sub_category\": \"github_actions\",\n"
        "  \"item_name\": \"secure_environment_secrets\"\n"
        "}\n"
        "```\n"
        "```json\n"
        "{\n"
        "  \"main_category\": \"database_optimization\",\n"
        "  \"sub_category\": \"query_performance\",\n"
        "  \"item_name\": \"postgresql_indexing_strategies\"\n"
        "}\n"
        "```\n"
        "Respond ONLY with the JSON object."
    )

    current_model = text_model
    last_error = None

    for attempt in range(max_retries * 2): # Total attempts considering primary and fallback
        model_to_use = current_model
        is_primary_model_attempt = (model_to_use == text_model)
        
        # Determine if this is a retry with the current model or a switch to fallback
        # Switch to fallback after 'max_retries' with the primary model
        if not is_primary_model_attempt and attempt < max_retries: # Should not happen if logic is correct
             pass # Still on primary
        elif is_primary_model_attempt and attempt >= max_retries and fallback_model and fallback_model != text_model:
            logging.info(f"Switching to fallback model {fallback_model} for tweet {tweet_id} after {max_retries} attempts with {text_model}.")
            current_model = fallback_model
            model_to_use = current_model # Update for this iteration
        
        try:
            logging.info(f"Categorization Attempt {(attempt % max_retries) + 1 if is_primary_model_attempt else (attempt - max_retries) + 1}/{max_retries} using model {model_to_use} for tweet {tweet_id}")
            
            raw_response = await http_client.ollama_generate(
                model=model_to_use,
                prompt=prompt_text,
                temperature=0.05, # Very low temperature for strict format adherence
                options={"json_mode": True} if http_client.config.ollama_supports_json_mode else {} # Use if supported
            )

            if not raw_response:
                last_error = ValueError("Empty response from AI model")
                logging.warning(f"{last_error} on attempt {attempt + 1} with {model_to_use} for tweet {tweet_id}")
                # Continue to error handling for retry/fallback logic
                raise last_error

            main_cat, sub_cat, item_name = process_category_response(raw_response, tweet_id)
            logging.info(f"Successfully categorized tweet {tweet_id} as {main_cat}/{sub_cat}/{item_name} using {model_to_use}")
            return main_cat, sub_cat, item_name

        except ValueError as ve:
            last_error = ve
            logging.warning(f"Validation failed for tweet {tweet_id} on attempt {attempt + 1} with {model_to_use}: {ve}. Raw response: '{raw_response.strip() if 'raw_response' in locals() and raw_response else 'EMPTY_OR_PRE_RESPONSE_ERROR'}'")
            # Fallback/retry logic handled by the loop structure
        except Exception as e: # Catch other unexpected errors
            last_error = e
            logging.error(f"Unexpected error during categorization attempt {attempt + 1} with {model_to_use} for tweet {tweet_id}: {e}")
            # Fallback/retry logic handled by the loop structure
        
        # If we are here, an error occurred. Check if it's the last attempt for the current model type.
        is_last_attempt_for_primary = is_primary_model_attempt and (attempt == max_retries - 1)
        is_last_attempt_overall = (attempt == (max_retries * 2) - 1)

        if is_last_attempt_overall or (is_last_attempt_for_primary and not (fallback_model and fallback_model != text_model)):
            # This is the absolute final attempt, or final for primary and no fallback.
            logging.error(f"All categorization attempts failed for tweet {tweet_id}. Last error: {last_error}")
            raise AIError(f"Categorization failed for tweet {tweet_id} after all retries. Last error: {last_error}")
        
        # If not the absolute last attempt, sleep and continue the loop
        # The model switch logic at the beginning of the loop will handle changing to fallback if necessary.
        await asyncio.sleep(1.5 ** (attempt % max_retries)) # Exponential backoff based on attempts for the current model type

    # Should not be reached if logic is correct
    logging.critical(f"Categorization logic ended unexpectedly for tweet {tweet_id} without success or error.")
    raise AIError(f"Categorization failed for tweet {tweet_id} unexpectedly (flow error). Last error: {last_error}")


# --- Keep infer_basic_category and re_categorize_offline as they might be used elsewhere, ---
# --- but they are NOT used as fallbacks in the main categorize_and_name_content anymore. ---
def infer_basic_category(text: str) -> Tuple[str, str]:
    """
    Infer a basic category and subcategory based on content keywords.
    
    Args:
        text: The content text to analyze
        
    Returns:
        Tuple of (main_category, sub_category)
    """
    text = text.lower()
    if "machine learning" in text or "neural" in text or "model" in text:
        return ("machine_learning", "models")
    elif "devops" in text or "ci/cd" in text or "pipeline" in text:
        return ("devops", "ci_cd")
    elif "database" in text or "sql" in text or "query" in text:
        return ("databases", "query_processing")
    elif "python" in text or "javascript" in text or "code" in text:
        return ("software_engineering", "programming")
    else:
        return ("software_engineering", "best_practices")

def re_categorize_offline(
    content_text: str, 
    snippet_length: int = 120, 
    ollama_url: str = "", 
    text_model: str = "", 
    category_manager = None,
    http_client: Optional[requests.Session] = None
) -> Tuple[str, str, str]:
    snippet = content_text[:snippet_length].replace('\n', ' ')
    suggestions = category_manager.get_category_suggestions(content_text) if category_manager else []
    suggested_cats = ", ".join([f"{cat}/{sub}" for cat, sub, _ in suggestions])
    prompt_text = (
        "You are an expert technical content curator specializing in software engineering, "
        "system design, and technical management.\n\n"
        f"Based on initial analysis, these categories were suggested: {suggested_cats}\n\n"
        "Task 1 - Choose or refine the categorization:\n"
        "- Confirm one of the suggested categories.\n"
        "- Or propose a more accurate category.\n"
        "- Do not use 'general' or 'other' as categories.\n"
        "- Keep category names short and specific.\n\n"
        "Task 2 - Create a specific technical title:\n"
        "- Make it clear, unique, and descriptive.\n"
        f"- Reflect the key technical concept from this snippet:\n\"{snippet}\".\n"
        "- Avoid placeholders like 'tech insight' or 'note'.\n"
        "- Use 2-5 words maximum.\n"
        "- Keep it concise.\n\n"
        "Response Format:\n"
        "Category/Subcategory | Title\n\n"
        f"Content to Categorize:\n{content_text}\n\n"
        "Response:"
    )
    try:
        client = http_client or requests
        resp = client.post(
            f"{ollama_url}/api/generate",
            json={"prompt": prompt_text, "model": text_model, "stream": False},
            timeout=120
        )
        resp.raise_for_status()
        raw_response = resp.json().get("response", "").strip()
        main_cat, sub_cat, item_name = process_category_response(raw_response, "offline")
        return (main_cat, sub_cat, item_name)
    except Exception as e:
        logging.error(f"Offline recategorization failed: {e}")

    if suggestions:
        mc, sc, _ = suggestions[0]
        fallback_title = (content_text[:30].strip() or 'offline').replace(' ', '_')
        fallback_title = normalize_name_for_filesystem(fallback_title)
        return (mc, sc, fallback_title)
    return ("software_engineering", "best_practices", "fallback_offline")
