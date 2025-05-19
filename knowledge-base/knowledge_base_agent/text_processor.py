from typing import Dict, Any, Tuple, Optional
import logging
from datetime import datetime
from knowledge_base_agent.exceptions import CategoryGenerationError
from knowledge_base_agent.category_manager import CategoryManager
from knowledge_base_agent.config import Config
from knowledge_base_agent.http_client import HTTPClient
from knowledge_base_agent.state_manager import StateManager
from knowledge_base_agent.types import CategoryInfo
import json
import re

async def categorize_and_name_content(
    ollama_url: str,
    text: str,
    text_model: str,
    tweet_id: str,
    category_manager: CategoryManager,
    http_client: HTTPClient
) -> Tuple[str, str, str]:
    """Categorize content and generate item name."""
    try:
        # Get categories using the category manager
        main_cat, sub_cat = await category_manager.classify_content(
            text=text,
            tweet_id=tweet_id
        )

        # Normalize categories
        main_cat = main_cat.lower().replace(' ', '_')
        sub_cat = sub_cat.lower().replace(' ', '_')
        
        # Generate item name
        item_name = await category_manager.generate_item_name(
            text=text,
            main_category=main_cat,
            sub_category=sub_cat,
            tweet_id=tweet_id
        )
        
        # Ensure category exists
        if not category_manager.category_exists(main_cat, sub_cat):
            category_manager.add_category(main_cat, sub_cat)
            
        return main_cat, sub_cat, item_name
        
    except Exception as e:
        logging.error(f"Failed to categorize content for tweet {tweet_id}: {e}")
        raise CategoryGenerationError(f"Failed to categorize content for tweet {tweet_id}: {e}")