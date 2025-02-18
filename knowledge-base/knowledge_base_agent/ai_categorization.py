import requests
import logging
import asyncio
from typing import Tuple, Optional, Dict, Any, List
from knowledge_base_agent.naming_utils import normalize_name_for_filesystem, is_valid_item_name, fix_invalid_name, fallback_snippet_based_name
from knowledge_base_agent.exceptions import KnowledgeBaseError, AIError
from knowledge_base_agent.http_client import HTTPClient

def process_category_response(response: str, tweet_id: str) -> Tuple[str, str, str]:
    """
    Process and validate the category response from the AI model.
    
    Args:
        response: Raw response string from the AI model
        tweet_id: Tweet identifier for logging purposes
        
    Returns:
        Tuple of (main_category, sub_category, item_name)
        
    Raises:
        AIError: If the response cannot be processed or is invalid
    """
    try:
        response = response.strip().replace('\n', ' ')
        parts = [x.strip() for x in response.split('|', 2)]
        
        if len(parts) != 3:
            logging.warning(f"Invalid category response format for tweet {tweet_id}: {response}")
            raise ValueError("Response must have three parts")
        
        main_category, sub_category, item_name = parts
        
        # Basic validation
        if not all(p.strip() for p in parts):
            raise ValueError("Empty category parts detected")
            
        # Normalize and fix
        main_category = normalize_name_for_filesystem(main_category or "software_engineering")
        sub_category = normalize_name_for_filesystem(sub_category or "general")
        item_name = normalize_name_for_filesystem(item_name or fallback_snippet_based_name(response))
        
        # Warn instead of fail for questionable values
        if any(p.lower() in ['fallback', 'generic', 'undefined'] for p in [main_category, sub_category]):
            logging.warning(f"Questionable category values for tweet {tweet_id}: {main_category}/{sub_category}")
            
        return (main_category, sub_category, item_name)
    except Exception as e:
        logging.error(f"Error processing category response for tweet {tweet_id}: {e}")
        raise AIError(f"Failed to process category response: {e}")

async def categorize_and_name_content(
    http_client: HTTPClient,
    combined_text: str,
    text_model: str,
    tweet_id: str,
    category_manager,
    max_retries: int = 3
) -> Tuple[str, str, str]:
    suggestions = category_manager.get_category_suggestions(combined_text)
    suggested_cats = ", ".join([f"{cat}/{sub}" for cat, sub, _ in suggestions]) if suggestions else "None"

    prompt_text = (
        "You are an expert technical content curator specializing in software engineering, system design, and technical management. "
        "Your task is to categorize and name the following content.\n\n"
        f"Content: \"{combined_text}\"\n\n"
        f"Suggested categories (if any): {suggested_cats}\n\n"
        "Instructions:\n"
        "1. Main Category:\n"
        "   - Choose a broad technical domain (e.g., \"software_engineering\", \"machine_learning\", \"devops\").\n"
        "   - Use an existing suggestion if appropriate or propose a better match.\n"
        "   - Avoid vague terms like \"general\" or \"miscellaneous\".\n"
        "2. Sub Category:\n"
        "   - Specify a precise technical area within the main category (e.g., \"concurrency\", \"neural_networks\", \"ci_cd\").\n"
        "   - Ensure it's detailed and context-specific.\n"
        "3. Item Name:\n"
        "   - Create a concise, technical title (2-4 words, e.g., \"thread_synchronization\", \"gradient_descent_optimizers\").\n"
        "   - Format: [Technology/Tool]_[Specific_Concept/Action], lowercase with underscores.\n"
        "   - Avoid generic terms like \"guide\", \"overview\", or \"note\".\n\n"
        "Response Format:\n"
        "MainCategory | SubCategory | ItemName"
    )

    for attempt in range(max_retries):
        try:
            response = await http_client.post(
                f"{http_client.config.ollama_url}/api/generate",
                json={
                    "prompt": prompt_text,
                    "model": text_model,
                    "stream": False,
                    "temperature": 0.5,  # Lowered for more deterministic output
                    "max_tokens": 100
                }
            )
            raw_response = response.json().get("response", "").strip()
            if not raw_response:
                raise ValueError("Empty response from AI model")

            main_cat, sub_cat, item_name = process_category_response(raw_response, tweet_id)
            return (main_cat, sub_cat, item_name)

        except Exception as e:
            logging.error(f"Attempt {attempt + 1} for tweet {tweet_id} failed: {e}")
            if attempt < max_retries - 1:
                await asyncio.sleep(2 ** attempt)
                continue

            # Adaptive fallback based on content analysis
            if suggestions:
                main_cat, sub_cat, _ = suggestions[0]
            else:
                main_cat, sub_cat = infer_basic_category(combined_text)  # New helper function
            item_name = fallback_snippet_based_name(combined_text)
            logging.info(f"Using fallback categorization for tweet {tweet_id}: {main_cat}/{sub_cat}/{item_name}")
            return (main_cat, sub_cat, item_name)
        
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

async def classify_content(text: str, text_model: str, ollama_url: str, category_manager, http_client: Optional[requests.Session] = None) -> Dict[str, str]:
    """
    Classify content using AI to determine main and sub categories.
    """
    # Remove this function as it's now redundant with categorize_and_name_content
    raise DeprecationWarning("Use categorize_and_name_content instead")

async def generate_content_name(text: str, text_model: str, ollama_url: str, http_client: Optional[requests.Session] = None) -> str:
    """
    Generate a name for the content using AI.
    """
    # Remove this function as it's now handled within categorize_and_name_content
    raise DeprecationWarning("Use categorize_and_name_content instead")
