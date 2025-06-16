import re
import uuid
import logging
import requests
from typing import Optional, Any
from pathlib import Path

from .http_client import HTTPClient
from .prompts import LLMPrompts

def validate_directory_name(name: str, max_length: int = 50) -> bool:
    if len(name) > max_length:
        return False
    if re.search(r'[<>:"/\\|?*]', name):
        return False
    return True

def normalize_name_for_filesystem(name: str, max_length: int = 30) -> str:
    # First remove any .md extension and apostrophes
    name = name.replace('.md', '').replace("'", "")
    
    # Then process as before
    name = ' '.join(name.split())
    name = name.lower().replace(' ', '_')
    name = re.sub(r"[^\w-]", '', name)  # Remove all non-word chars except hyphens
    name = re.sub(r"[-_]+", '_', name)
    if len(name) > max_length:
        name = name[:max_length].rsplit('_', 1)[0]
    name = name.strip('_-')
    if not name:
        return f"unnamed_{uuid.uuid4().hex[:8]}"
    return name

def safe_directory_name(name: str, existing_path: Optional[Path] = None) -> str:
    safe_name = normalize_name_for_filesystem(name)
    if not safe_name:
        return f"unnamed_{uuid.uuid4().hex[:8]}"
    
    if existing_path and (existing_path / safe_name).exists():
        base_name = safe_name
        counter = 1
        while (existing_path / f"{base_name}_{counter}").exists():
            counter += 1
        safe_name = f"{base_name}_{counter}"
    
    return safe_name

def is_valid_item_name(item_name: str) -> bool:
    if item_name.startswith("fallback_"):
        return False
    parts = item_name.split('_')
    if len(parts) < 2 or len(parts) > 4:
        return False
    forbidden_words = {"generic", "fallback", "overview", "guide", "note"}
    for p in parts:
        if p.lower() in forbidden_words:
            return False
    return True

def fallback_snippet_based_name(snippet: str) -> str:
    words = re.findall(r"\w+", snippet.lower())
    big_words = [w for w in words if len(w) >= 4][:4]
    if not big_words:
        return f"auto_{uuid.uuid4().hex[:6]}"
    return "_".join(big_words)

def fix_invalid_name(
    current_name: str,
    snippet: str,
    main_cat: str,
    sub_cat: str,
    text_model: str,
    ollama_url: str,
    max_retries: int = 3,
    timeout: int = 300,  # extended timeout in seconds
    http_client: Optional[requests.Session] = None
) -> str:
    """
    Calls an external AI API to fix an invalid item name. If the AI returns an invalid name,
    it retries up to max_retries times. If all attempts fail, returns a fallback name based on the snippet.
    
    Parameters:
        current_name: The original, invalid name.
        snippet: The content snippet from which a fallback name may be derived.
        main_cat: The main category of the content.
        sub_cat: The subcategory of the content.
        text_model: The text model to use for generation.
        ollama_url: The base URL for the AI API.
        max_retries: Number of attempts to fix the name.
        timeout: Read timeout for the HTTP call (in seconds).
        http_client: An optional injected HTTP client (defaults to requests if None).
    
    Returns:
        A valid item name as a string.
    """
    client = http_client or requests
    fix_prompt = (
        f"You previously suggested the item name: '{current_name}'. That is invalid.\n"
        f"Category: {main_cat}, SubCategory: {sub_cat}\n\n"
        "Please provide a NEW item name, in EXACTLY 2-4 technical words:\n"
        "- No placeholders like 'fallback' or 'generic'\n"
        "- Example: 'Kubernetes Pod Networking', 'Redis Cache Patterns'\n"
        "- If uncertain, pick relevant keywords from snippet.\n\n"
        f"Snippet:\n{snippet}\n\n"
        "Answer with item name only (2-4 words)."
    )

    for attempt in range(max_retries):
        try:
            resp = client.post(
                f"{ollama_url}/api/generate",
                json={"prompt": fix_prompt, "model": text_model, "stream": False},
                timeout=timeout 
            )
            resp.raise_for_status()
            raw_response = resp.json().get("response", "").strip()
            lines = raw_response.split('\n', 1)
            new_name = lines[0].strip().lower().replace(' ', '_')
            new_name = normalize_name_for_filesystem(new_name)
            if is_valid_item_name(new_name):
                return new_name
        except Exception as e:
            logging.error(f"Renaming attempt {attempt+1} failed: {e}")

    # If all attempts fail, return a fallback based on the snippet.
    return fallback_snippet_based_name(snippet)

async def generate_short_name(
    http_client: HTTPClient,
    name: str,
    is_main_category: bool = False
) -> str:
    """
    Generates a short, UI-friendly name for a category or sub-category using an LLM.
    """
    try:
        system_prompt = LLMPrompts.get_short_name_generation_prompt()
        
        user_message = (
            f"Please generate a short, catchy, and UI-friendly name (2-3 words, max 25 characters) for the "
            f"{'main category' if is_main_category else 'sub-category'}: '{name}'"
        )

        llm_response = await http_client.send_llm_request(
            # Using text model for this simple task
            model=http_client.config.text_model, 
            system_prompt=system_prompt,
            user_message=user_message,
            temperature=0.7,
            max_tokens=20,
        )
        
        if llm_response and llm_response.get("success"):
            short_name = llm_response.get("content", "").strip().replace('"', '')
            if 1 < len(short_name) <= 25:
                return short_name

        logging.warning(f"Failed to generate a valid short name for '{name}'. Using a normalized version as fallback.")
        return normalize_name_for_filesystem(name, 25)

    except Exception as e:
        logging.error(f"Error generating short name for '{name}': {e}", exc_info=True)
        # Fallback to a normalized version of the original name
        return normalize_name_for_filesystem(name, 25)
