import requests
import logging
import asyncio
import json
import re
from typing import Tuple, Optional, Dict, Any, List
from knowledge_base_agent.naming_utils import normalize_name_for_filesystem, is_valid_item_name, fix_invalid_name, fallback_snippet_based_name
from knowledge_base_agent.exceptions import KnowledgeBaseError, AIError
from knowledge_base_agent.http_client import HTTPClient
from knowledge_base_agent.prompts_replacement import LLMPrompts

def process_category_response(response_text: str, tweet_id: str) -> Tuple[str, str, str]:
    """
    Process and validate the category JSON response from the AI model strictly.
    Validation for generic terms has been removed.

    Args:
        response_text: Raw response string from the AI model, expected to be a JSON object.
        tweet_id: Tweet identifier for logging purposes

    Returns:
        Tuple of (main_category, sub_category, item_name)

    Raises:
        ValueError: If the response format is invalid JSON, missing required keys, or contains empty parts.
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

        # Logic for rejecting generic terms has been removed.
        # Rely on prompting to guide the model.

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
    text_model: str,  # Keep for backward compatibility
    tweet_id: str,
    category_manager, # Instance of CategoryManager
    max_retries: int = 5,
    fallback_model: str = "",
    gpu_device: int = 0
) -> Tuple[str, str, str]:
    """Categorize content using text and image descriptions, with robust retries, expecting JSON output."""
    
    # Use categorization_model if available, otherwise fall back to text_model
    model_to_use = getattr(http_client.config, 'categorization_model', text_model)
    if model_to_use != text_model:
        logging.info(f"Using dedicated categorization model: {model_to_use} for tweet {tweet_id}")
    
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

    # Check if the model supports reasoning mode - prioritize categorization model setting
    use_reasoning = False
    if hasattr(http_client.config, 'categorization_model_thinking') and http_client.config.categorization_model_thinking:
        use_reasoning = True
        logging.info(f"Using dedicated reasoning mode for categorization model ({model_to_use}) for tweet {tweet_id}")
    elif hasattr(http_client.config, 'text_model_thinking') and http_client.config.text_model_thinking:
        use_reasoning = True
        logging.info(f"Using reasoning mode from text_model_thinking setting for tweet {tweet_id}")
    
    is_thread = bool(thread_segments)

    if use_reasoning:
        from knowledge_base_agent.prompts_replacement import ReasoningPrompts
        
        logging.info(f"Using reasoning mode for categorization of tweet {tweet_id}")
        
        # Create the messages list with system message and user prompt
        messages = [
            ReasoningPrompts.get_system_message(),
            ReasoningPrompts.get_categorization_prompt(context_content, formatted_existing_categories, is_thread)
        ]
        
        # Loop for retries
        for attempt in range(max_retries):
            try:
                # Use the chat endpoint for reasoning models
                response = await http_client.ollama_chat(
                    model=model_to_use,
                    messages=messages,
                    temperature=0.7,
                    top_p=0.9,
                    timeout=http_client.config.content_generation_timeout,
                    options={"gpu_device": gpu_device}
                )
                
                if response and response.strip():
                    try:
                        main_cat, sub_cat, item_name = process_category_response(response, tweet_id)
                        logging.info(f"Categorization successful for tweet {tweet_id}: {main_cat}/{sub_cat}/{item_name}")
                        return main_cat, sub_cat, item_name
                    except ValueError as validation_error:
                        logging.warning(f"Attempt {attempt+1}/{max_retries}: Invalid category response: {validation_error}")
                        # Add a correction message for the next attempt
                        if attempt < max_retries - 1:
                            messages.append({
                                "role": "user", 
                                "content": f"Your previous response had an issue: {validation_error}. Please try again with a valid JSON response."
                            })
                else:
                    logging.warning(f"Attempt {attempt+1}/{max_retries}: Empty response for tweet {tweet_id}")
            except AIError as e:
                logging.warning(f"Attempt {attempt+1}/{max_retries}: AI error during categorization for tweet {tweet_id}: {e}")
                # If we've reached max retries, try fallback model if available
                if attempt == max_retries - 1 and fallback_model:
                    logging.info(f"Trying fallback model {fallback_model} for tweet {tweet_id}")
                    try:
                        response = await http_client.ollama_chat(
                            model=fallback_model,
                            messages=messages,
                            temperature=0.7,
                            top_p=0.9,
                            timeout=http_client.config.content_generation_timeout,
                            options={"gpu_device": gpu_device}
                        )
                        
                        if response and response.strip():
                            main_cat, sub_cat, item_name = process_category_response(response, tweet_id)
                            logging.info(f"Fallback categorization successful for tweet {tweet_id}: {main_cat}/{sub_cat}/{item_name}")
                            return main_cat, sub_cat, item_name
                    except Exception as fallback_error:
                        logging.error(f"Fallback categorization also failed for tweet {tweet_id}: {fallback_error}")
                
                # Add exponential backoff delay
                await asyncio.sleep(2 ** attempt)
        
        # If we exhausted retries and fallbacks
        raise AIError(f"Failed to categorize tweet {tweet_id} after {max_retries} attempts")
    else:
        # Determine if the content is a thread for the prompt
        source_type_indicator = "Tweet Thread Content" if thread_segments else "Tweet Content"

        # Use the centralized prompt
        prompt_text = LLMPrompts.get_categorization_prompt_standard(
            context_content=context_content,
            formatted_existing_categories=formatted_existing_categories,
            is_thread=bool(thread_segments) # Pass is_thread directly
        )

        # Loop for retries
        for attempt in range(max_retries):
            try:
                use_json_mode = hasattr(http_client.config, 'ollama_supports_json_mode') and http_client.config.ollama_supports_json_mode
                response = await http_client.ollama_generate(
                    model=model_to_use,
                    prompt=prompt_text,
                    temperature=0.7,
                    top_p=0.9,
                    timeout=http_client.config.content_generation_timeout,
                    options={"json_mode": use_json_mode, "gpu_device": gpu_device} if use_json_mode else {"gpu_device": gpu_device}
                )
                
                if response and response.strip():
                    try:
                        main_cat, sub_cat, item_name = process_category_response(response, tweet_id)
                        logging.info(f"Categorization successful for tweet {tweet_id}: {main_cat}/{sub_cat}/{item_name}")
                        return main_cat, sub_cat, item_name
                    except ValueError as validation_error:
                        logging.warning(f"Attempt {attempt+1}/{max_retries}: Invalid category response: {validation_error}")
                else:
                    logging.warning(f"Attempt {attempt+1}/{max_retries}: Empty response for tweet {tweet_id}")
            except AIError as e:
                logging.warning(f"Attempt {attempt+1}/{max_retries}: AI error during categorization for tweet {tweet_id}: {e}")
                # If we've reached max retries, try fallback model if available
                if attempt == max_retries - 1 and fallback_model:
                    logging.info(f"Trying fallback model {fallback_model} for tweet {tweet_id}")
                    try:
                        response = await http_client.ollama_generate(
                            model=fallback_model,
                            prompt=prompt_text,
                            temperature=0.7,
                            top_p=0.9,
                            timeout=http_client.config.content_generation_timeout,
                            options={"json_mode": use_json_mode, "gpu_device": gpu_device} if use_json_mode else {"gpu_device": gpu_device}
                        )
                        
                        if response and response.strip():
                            main_cat, sub_cat, item_name = process_category_response(response, tweet_id)
                            logging.info(f"Fallback categorization successful for tweet {tweet_id}: {main_cat}/{sub_cat}/{item_name}")
                            return main_cat, sub_cat, item_name
                    except Exception as fallback_error:
                        logging.error(f"Fallback categorization also failed for tweet {tweet_id}: {fallback_error}")
                
                # Add exponential backoff delay
                await asyncio.sleep(2 ** attempt)
        
        # If we exhausted retries and fallbacks
        raise AIError(f"Failed to categorize tweet {tweet_id} after {max_retries} attempts")


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
