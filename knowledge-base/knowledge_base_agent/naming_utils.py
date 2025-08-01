import re
import uuid
import logging
import requests
from typing import Optional, Any
from pathlib import Path

from .http_client import HTTPClient
from .prompts_replacement import LLMPrompts

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

def create_fallback_short_name(name: str) -> str:
    """Create a user-friendly fallback short name from the original name."""
    # Convert underscores to spaces and title case
    readable_name = name.replace('_', ' ').title()
    
    # Handle common technical abbreviations
    replacements = {
        'Api': 'API',
        'Ai': 'AI', 
        'Ml': 'ML',
        'Ui': 'UI',
        'Ux': 'UX',
        'Db': 'DB',
        'Sql': 'SQL',
        'Http': 'HTTP',
        'Json': 'JSON',
        'Xml': 'XML',
        'Css': 'CSS',
        'Html': 'HTML',
        'Js': 'JS',
        'Ts': 'TS'
    }
    
    for old, new in replacements.items():
        readable_name = readable_name.replace(old, new)
    
    # If too long, try to abbreviate intelligently
    if len(readable_name) > 25:
        words = readable_name.split()
        if len(words) > 2:
            # Take first word and abbreviate others
            first_word = words[0]
            abbreviated = first_word + ' ' + ''.join(w[0] for w in words[1:])
            if len(abbreviated) <= 25:
                return abbreviated
        
        # Simple truncation as last resort
        return readable_name[:22] + "..."
    
    return readable_name

def validate_short_name(short_name: str) -> bool:
    """Validate that a short name meets our criteria."""
    if not short_name or len(short_name) < 2:
        return False
    if len(short_name) > 25:
        return False
    # Should contain at least one letter
    if not re.search(r'[a-zA-Z]', short_name):
        return False
    # Shouldn't be just underscores or special characters
    if re.match(r'^[_\-\s]*$', short_name):
        return False
    return True

async def generate_short_name(
    http_client: HTTPClient,
    name: str,
    is_main_category: bool = False,
    max_retries: int = 2
) -> str:
    """
    Generates a short, UI-friendly name for a category or sub-category using an LLM.
    """
    logging.debug(f"Generating short name for: '{name}' (is_main_category: {is_main_category})")
    
    for attempt in range(max_retries):
        try:
            # Check if we're using JSON prompts and pass the required parameter
            from .prompts_replacement import LLMPrompts
            manager = LLMPrompts._get_manager()
            
            if hasattr(manager, 'render_prompt'):
                # Using JSON prompts - pass category_name parameter
                try:
                    prompt_result = manager.render_prompt("short_name_generation", {
                        "category_name": name
                    }, "standard")
                    system_prompt = prompt_result.content
                except Exception as e:
                    logging.warning(f"JSON prompt failed, falling back to original: {e}")
                    system_prompt = LLMPrompts.get_short_name_generation_prompt()
            else:
                # Using original prompts
                system_prompt = LLMPrompts.get_short_name_generation_prompt()
            
            user_message = (
                f"Generate a short, catchy name (2-3 words, max 25 characters) for the "
                f"{'main category' if is_main_category else 'sub-category'}: '{name}'\n\n"
                f"Examples:\n"
                f"- 'machine_learning' → 'ML & AI'\n"
                f"- 'web_development' → 'Web Dev'\n"
                f"- 'data_structures' → 'Data Structures'\n"
                f"- 'agent_frameworks' → 'AI Agents'\n\n"
                f"Respond with ONLY the short name, no quotes or explanation."
            )

            # Combine system and user prompts for ollama_generate
            full_prompt = f"{system_prompt}\n\n{user_message}"

            response_content = await http_client.ollama_generate(
                model=http_client.config.text_model, 
                prompt=full_prompt,
                temperature=0.7,
                max_tokens=30,  # Increased token limit
                timeout=None  # Use default timeout from http_client config (180s)
            )
            
            if response_content:
                # Clean up the response
                short_name = response_content.strip()
                short_name = re.sub(r'^["\']|["\']$', '', short_name)  # Remove quotes
                short_name = short_name.split('\n')[0].strip()  # Take first line only
                
                logging.debug(f"LLM response for '{name}': '{short_name}'")
                
                # Check if the LLM just returned the same name (indicates failure)
                if short_name.lower().replace(' ', '_') == name.lower():
                    logging.debug(f"LLM returned same name '{short_name}' for '{name}', attempt {attempt + 1}")
                elif validate_short_name(short_name):
                    logging.debug(f"Successfully generated short name for '{name}': '{short_name}'")
                    return short_name
                else:
                    logging.debug(f"Invalid short name '{short_name}' for '{name}', attempt {attempt + 1}")

        except Exception as e:
            logging.warning(f"Error generating short name for '{name}' (attempt {attempt + 1}): {e}")

    # All attempts failed, use fallback
    fallback_name = create_fallback_short_name(name)
    logging.info(f"Using fallback short name for '{name}': '{fallback_name}'")
    return fallback_name
