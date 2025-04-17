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
REJECTED_CATEGORY_TERMS = {'general', 'default', 'uncategorized', 'miscellaneous', 'other', 'fallback', 'undefined'}

def process_category_response(response: str, tweet_id: str) -> Tuple[str, str, str]:
    """
    Process and validate the category response from the AI model strictly.

    Args:
        response: Raw response string from the AI model
        tweet_id: Tweet identifier for logging purposes

    Returns:
        Tuple of (main_category, sub_category, item_name)

    Raises:
        ValueError: If the response format is invalid, contains empty parts,
                    or uses rejected generic terms.
    """
    try:
        # Clean up potential markdown fences or extra text
        if "```" in response:
             response = response.split("```")[1].strip() # Try to extract from code block
        response = response.strip().replace('\n', '') # Remove newlines

        # Check for the separator
        if '|' not in response:
             raise ValueError(f"Response missing '|' separator: '{response}'")

        parts = [x.strip() for x in response.split('|')]

        if len(parts) != 3:
            logging.warning(f"Invalid category response format for tweet {tweet_id}: Expected 3 parts, got {len(parts)} in '{response}'")
            raise ValueError(f"Response must have exactly three parts separated by '|', got {len(parts)}")

        main_category, sub_category, item_name = parts

        # Stricter validation: Ensure no part is empty
        if not all(p for p in parts):
            logging.warning(f"Empty category part detected for tweet {tweet_id}: {parts}")
            raise ValueError("Empty category parts are not allowed")

        # Normalize names early
        main_category_norm = normalize_name_for_filesystem(main_category)
        sub_category_norm = normalize_name_for_filesystem(sub_category)
        item_name_norm = normalize_name_for_filesystem(item_name)

        # Reject common unwanted generic terms
        if main_category_norm.lower() in REJECTED_CATEGORY_TERMS or sub_category_norm.lower() in REJECTED_CATEGORY_TERMS:
             logging.warning(f"Rejected generic category term for tweet {tweet_id}: {main_category}/{sub_category}")
             raise ValueError(f"Rejected generic category term used: {main_category}/{sub_category}")

        # Final check on normalized names (redundant with above check but safe)
        if not main_category_norm or not sub_category_norm or not item_name_norm:
             logging.warning(f"Empty normalized category part after processing for tweet {tweet_id}: {main_category_norm}/{sub_category_norm}/{item_name_norm}")
             raise ValueError("Empty normalized category parts are not allowed")

        # Use normalized names if validation passes
        return (main_category_norm, sub_category_norm, item_name_norm)

    except ValueError as ve:
         # Re-raise ValueError to be caught by the retry loop
         raise ve
    except Exception as e:
        logging.error(f"Unexpected error processing category response for tweet {tweet_id}: {e} (Response: '{response}')")
        # Wrap unexpected errors in ValueError to also trigger retry
        raise ValueError(f"Unexpected error processing category response: {e}")


async def categorize_and_name_content(
    http_client: HTTPClient,
    tweet_data: Dict[str, Any], # Accept full tweet_data
    text_model: str,
    tweet_id: str,
    category_manager,
    max_retries: int = 5,
    fallback_model: str = ""
) -> Tuple[str, str, str]:
    """Categorize content using text and image descriptions, with robust retries."""
    combined_text = tweet_data.get('full_text', '')
    image_descriptions = tweet_data.get('image_descriptions', [])

    # Combine text and image descriptions for context
    context_content = combined_text
    if image_descriptions:
         # Join descriptions, ensuring they are strings
         descriptions_str = "\n".join([str(desc) for desc in image_descriptions if desc])
         if descriptions_str:
              context_content += "\n\nImage Content:\n" + descriptions_str

    if not context_content.strip():
         logging.error(f"No text or image description content found for tweet {tweet_id}. Cannot categorize.")
         raise AIError(f"Cannot categorize tweet {tweet_id}: No content available.")


    suggestions = category_manager.get_category_suggestions(context_content)
    suggested_cats = ", ".join([f"{s.get('main_category', 'Unknown')}/{s.get('sub_category', 'Unknown')}" for s in suggestions]) if suggestions else "None"

    prompt_text = (
        "You are an expert technical content curator specializing in software engineering, system design, and technical management. "
        "Your task is to categorize and name the following content, which includes tweet text and potentially descriptions of associated images.\n\n"
        f"Content Context:\n---\n{context_content}\n---\n\n" # Use context_content
        f"Suggested categories based on initial analysis (ignore if irrelevant): {suggested_cats}\n\n"
        "Instructions:\n"
        "1. Main Category:\n"
        "   - Choose a specific, relevant technical domain (e.g., \"software_engineering\", \"machine_learning\", \"devops\", \"cloud_computing\", \"cybersecurity\").\n"
        "   - Use an existing suggestion ONLY if it's accurate and specific.\n"
        "   - **CRITICAL: Avoid generic terms like \"general\", \"uncategorized\", \"default\", \"other\", \"technology\". Be specific.**\n"
        "2. Sub Category:\n"
        "   - Specify a precise technical area within the main category (e.g., \"concurrency\", \"neural_networks\", \"ci_cd\", \"aws_lambda\", \"penetration_testing\").\n"
        "   - Ensure it's detailed and context-specific.\n"
        "   - **CRITICAL: Avoid generic terms.**\n"
        "3. Item Name:\n"
        "   - Create a concise, descriptive, filesystem-friendly title (2-5 words, e.g., \"thread_synchronization_java\", \"gpt4_fine_tuning_guide\", \"terraform_state_locking\").\n"
        "   - Format: [Topic/Tool]_[SpecificConcept/Action], lowercase with underscores.\n"
        "   - Avoid generic terms like \"guide\", \"overview\", \"notes\", \"details\", \"insights\".\n\n"
        "**Response Format (MUST use this exact format with '|' separator, single line only):**\n"
        "MainCategory | SubCategory | ItemName\n\n"
        "Examples:\n"
        "software_engineering | concurrency | thread_synchronization_java\n"
        "devops | ci_cd | github_actions_secrets\n"
        "machine_learning | large_language_models | llama3_quantization_tutorial\n\n"
        "Respond ONLY with the single formatted line."
    )

    current_model = text_model
    for attempt in range(max_retries * 2): # Allow attempts for both models potentially
        model_to_use = current_model
        try:
            logging.debug(f"Categorization Attempt {attempt + 1}/{max_retries * 2} using model {model_to_use} for tweet {tweet_id}")
            raw_response = await http_client.ollama_generate(
                model=model_to_use,
                prompt=prompt_text,
                temperature=0.1, # Keep temperature low for format adherence
            )
            if not raw_response:
                # Treat empty response as a validation failure
                raise ValueError("Empty response from AI model")

            # Process and validate STRICTLY using the updated function
            main_cat, sub_cat, item_name = process_category_response(raw_response, tweet_id)

            # If validation passes, return the result
            logging.info(f"Successfully categorized tweet {tweet_id} as {main_cat}/{sub_cat}/{item_name} using {model_to_use}")
            return (main_cat, sub_cat, item_name)

        except ValueError as ve:
            # Catch specific format/validation errors from process_category_response
            logging.warning(f"Validation failed for tweet {tweet_id} on attempt {attempt + 1} with {model_to_use}: {ve}. Raw response: '{raw_response.strip() if raw_response else 'EMPTY'}'")
            # Decide whether to switch model based on attempt number
            if fallback_model and model_to_use == text_model and attempt >= max_retries // 2:
                 logging.info(f"Switching to fallback model {fallback_model} for tweet {tweet_id} after validation failures.")
                 current_model = fallback_model
            elif model_to_use == fallback_model and attempt >= max_retries + (max_retries // 2): # Check attempts for fallback
                 logging.warning(f"Fallback model {fallback_model} also failed validation for {tweet_id}. Continuing retries if any left.")

            # Wait and retry if attempts remain
            if attempt < (max_retries * 2) - 1:
                await asyncio.sleep(2 ** (attempt % max_retries) * 0.5) # Shorter backoff maybe
                continue
            else:
                logging.error(f"All {max_retries * 2} categorization attempts failed for tweet {tweet_id} due to validation errors.")
                raise AIError(f"Categorization failed for tweet {tweet_id} after all retries due to format/validation issues.")

        except Exception as e:
            # Catch other unexpected errors during generation/processing
            logging.error(f"Unexpected error during categorization attempt {attempt + 1}/{max_retries * 2} with {model_to_use} for tweet {tweet_id}: {e}")
            # Decide on model switching similar to ValueError case
            if fallback_model and model_to_use == text_model and attempt >= max_retries // 2:
                 logging.info(f"Switching to fallback model {fallback_model} for tweet {tweet_id} after error: {e}")
                 current_model = fallback_model

            if attempt < (max_retries * 2) - 1:
                 await asyncio.sleep(2 ** (attempt % max_retries))
                 continue
            else:
                 logging.error(f"All {max_retries * 2} categorization attempts failed for tweet {tweet_id} due to unexpected errors.")
                 raise AIError(f"Categorization failed for tweet {tweet_id} after all retries: {e}")

    # This part should theoretically not be reached if AIError is raised above
    logging.critical(f"Categorization logic ended unexpectedly for tweet {tweet_id} without success or error.")
    raise AIError(f"Categorization failed for tweet {tweet_id} unexpectedly.")


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
