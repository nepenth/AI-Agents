import requests
import logging
import asyncio
from typing import Tuple, Optional, Dict, Any
from knowledge_base_agent.naming_utils import normalize_name_for_filesystem, is_valid_item_name, fix_invalid_name, fallback_snippet_based_name
from knowledge_base_agent.exceptions import KnowledgeBaseError, AIError
from knowledge_base_agent.http_client import HTTPClient

def process_category_response(response: str, tweet_id: str) -> Tuple[str, str, str]:
    """Process the category response from the AI model."""
    try:
        parts = [x.strip() for x in response.split('|', 2)]
        if len(parts) != 3:
            logging.warning(f"Invalid category response format for tweet {tweet_id}")
            raise ValueError("Response must have three parts")
        
        main_category, sub_category, item_name = parts
        
        # Validate each part before normalizing
        if not all(parts) or any(p.lower() in ['fallback', 'generic'] for p in parts):
            raise ValueError("Invalid category parts detected")
            
        return (
            normalize_name_for_filesystem(main_category),
            normalize_name_for_filesystem(sub_category),
            normalize_name_for_filesystem(item_name)
        )
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
    """Categorizes and names content using an AI model."""
    snippet = combined_text[:120].replace('\n', ' ')
    suggestions = category_manager.get_category_suggestions(combined_text)
    suggested_cats = ", ".join([f"{cat}/{sub}" for cat, sub, _ in suggestions])

    prompt_text = (
        "You are an expert technical content curator. Format response exactly as: "
        "MainCategory | SubCategory | ItemName\n\n"
        f"Suggested categories: {suggested_cats}\n\n"
        "Rules:\n"
        "1. MainCategory: Choose from suggested or propose better match\n"
        "2. SubCategory: Must be specific technical area (no 'general' or 'misc').\n"
        "3. ItemName:\n"
        "4. REQUIRED format: [Technology/Tool] + [Specific Concept/Action]\n\n"
        "- EXACTLY 2-4 technical words\n"
        "- Examples: 'Kubernetes Pod Networking', 'Redis Cache Patterns'\n"
        "   - Do NOT use placeholders like 'fallback', 'generic', 'note', etc.\n"
        "   - If uncertain, pick the most relevant 2-4 keywords from the content.\n\n"
        "   - Example of badly named knowledge base item 'software_engineering/best_practices/fallback_18819340', item name should always be relevant.\n"
        "- NO generic words (guide, overview, etc)\n"
        "- NO articles (the, a, an)\n\n"
        f"Content:\n{combined_text}\n\n"
        "Response (remember: concrete technical terms only):"
    )

    for attempt in range(max_retries):
        try:
            response = await http_client.post(
                f"{http_client.config.ollama_url}/api/generate",
                json={"prompt": prompt_text, "model": text_model, "stream": False}
            )
            
            raw_response = response.json().get("response", "").strip()
            main_cat, sub_cat, item_name = process_category_response(raw_response, tweet_id)
            
            if not is_valid_item_name(item_name):
                item_name = await fix_invalid_name(
                    http_client=http_client,
                    current_name=item_name,
                    snippet=combined_text,
                    main_cat=main_cat,
                    sub_cat=sub_cat,
                    text_model=text_model
                )
                
            if main_cat in category_manager.get_all_categories():
                valid_subs = category_manager.get_subcategories(main_cat)
                if not valid_subs or sub_cat in valid_subs:
                    return (main_cat, sub_cat, item_name)
                    
        except Exception as e:
            logging.error(f"Attempt {attempt + 1} for tweet {tweet_id} failed: {e}")
            await asyncio.sleep(2 ** attempt)

    if suggestions:
        main_cat, sub_cat, _ = suggestions[0]
        snippet_title = (combined_text[:30].strip() or 'fallback').replace(' ', '_')
        snippet_title = normalize_name_for_filesystem(snippet_title)
        if not is_valid_item_name(snippet_title):
            snippet_title = fallback_snippet_based_name(combined_text)
        return (main_cat, sub_cat, snippet_title)

    return ("software_engineering", "best_practices", fallback_snippet_based_name(combined_text))

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
    
    Args:
        text: The text to classify
        text_model: The AI model to use
        ollama_url: The URL for the Ollama API
        category_manager: CategoryManager instance for suggestions
        http_client: Optional HTTP client for requests
    """
    suggestions = category_manager.get_category_suggestions(text)
    suggested_cats = ", ".join([f"{cat}/{sub}" for cat, sub, _ in suggestions])

    prompt_text = (
        "You are an expert technical content curator. Categorize this content.\n\n"
        f"Suggested categories: {suggested_cats}\n\n"
        "Rules:\n"
        "1. MainCategory: Choose from suggested or propose better match\n"
        "2. SubCategory: Must be specific technical area (no 'general' or 'misc')\n"
        f"Content to categorize:\n{text}\n\n"
        "Response format: MainCategory | SubCategory"
    )

    try:
        client = http_client or requests
        resp = client.post(
            f"{ollama_url}/api/generate",
            json={"prompt": prompt_text, "model": text_model, "stream": False},
            timeout=60
        )
        resp.raise_for_status()
        raw_response = resp.json().get("response", "").strip()
        
        parts = [x.strip() for x in raw_response.split('|', 1)]
        if len(parts) != 2:
            raise ValueError("Invalid classification response format")
            
        main_cat, sub_cat = parts
        return {
            'main_category': normalize_name_for_filesystem(main_cat),
            'sub_category': normalize_name_for_filesystem(sub_cat)
        }
    except Exception as e:
        logging.error(f"Classification failed: {e}")
        if suggestions:
            return {
                'main_category': suggestions[0][0],
                'sub_category': suggestions[0][1]
            }
        raise AIError(f"Failed to classify content: {e}")

async def generate_content_name(text: str, text_model: str, ollama_url: str, http_client: Optional[requests.Session] = None) -> str:
    """
    Generate a name for the content using AI.
    
    Args:
        text: The text to generate a name from
        text_model: The AI model to use
        ollama_url: The URL for the Ollama API
        http_client: Optional HTTP client for requests
    """
    snippet = text[:120].replace('\n', ' ')
    prompt_text = (
        "Generate a concise technical name for this content.\n\n"
        "Rules:\n"
        "1. Use 2-4 technical words only\n"
        "2. Format: [Technology/Tool] + [Specific Concept/Action]\n"
        "3. NO generic words (guide, overview, etc)\n"
        "4. NO articles (the, a, an)\n"
        f"Content snippet:\n{snippet}\n\n"
        "Response (technical name only):"
    )

    try:
        client = http_client or requests
        resp = client.post(
            f"{ollama_url}/api/generate",
            json={"prompt": prompt_text, "model": text_model, "stream": False},
            timeout=60
        )
        resp.raise_for_status()
        name = resp.json().get("response", "").strip()
        
        if not is_valid_item_name(name):
            return fallback_snippet_based_name(text)
            
        return normalize_name_for_filesystem(name)
    except Exception as e:
        logging.error(f"Name generation failed: {e}")
        return fallback_snippet_based_name(text)
