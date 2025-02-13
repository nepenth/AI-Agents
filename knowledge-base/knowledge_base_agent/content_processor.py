from pathlib import Path
from typing import Dict, Any, Tuple
import logging
from knowledge_base_agent.markdown_writer import MarkdownWriter
from knowledge_base_agent.exceptions import StorageError, ContentProcessingError
from knowledge_base_agent.category_manager import CategoryManager
from knowledge_base_agent.config import Config
from knowledge_base_agent.ai_categorization import classify_content, generate_content_name
from knowledge_base_agent.tweet_utils import sanitize_filename

async def categorize_and_name_content(
    ollama_url: str,
    text: str,
    text_model: str,
    tweet_id: str,
    category_manager: CategoryManager
) -> Tuple[str, str, str]:
    """
    Categorize and name content for a tweet using AI.

    Args:
        ollama_url: URL for the AI service.
        text: The text to categorize.
        text_model: The AI text model to use.
        tweet_id: The tweet identifier.
        category_manager: The category manager instance.

    Returns:
        A tuple of (main_category, sub_category, name).
    """
    if not text:
        raise ContentProcessingError("No text content found for tweet")

    try:
        categories = await classify_content(text, text_model)
        main_cat = categories['main_category'].lower().replace(' ', '_')
        sub_cat = categories['sub_category'].lower().replace(' ', '_')
        
        if not category_manager.category_exists(main_cat, sub_cat):
            category_manager.add_category(main_cat, sub_cat)
            
        name = await generate_content_name(text, text_model)
        name = sanitize_filename(name)
        
        return main_cat, sub_cat, name
        
    except Exception as e:
        raise ContentProcessingError(f"Failed to categorize content for tweet {tweet_id}: {e}")

async def create_knowledge_base_entry(
    tweet_id: str,
    tweet_data: Dict[str, Any],
    categories: Tuple[str, str, str],
    config: Config
) -> None:
    """
    Create a knowledge base entry for a tweet.
    
    Args:
        tweet_id: The ID of the tweet
        tweet_data: The tweet data including text and media
        categories: Tuple of (main_category, sub_category, item_name)
        config: Configuration object
        
    Raises:
        StorageError: If writing to knowledge base fails
    """
    try:
        main_cat, sub_cat, item_name = categories
        markdown_writer = MarkdownWriter()
        
        # Extract necessary data
        content_text = tweet_data.get('full_text', '')
        tweet_url = tweet_data.get('tweet_url', '')
        image_files = [Path(p) for p in tweet_data.get('downloaded_media', [])]
        image_descriptions = tweet_data.get('image_descriptions', [])
        
        # Write markdown content
        await markdown_writer.write_tweet_markdown(
            config=config,
            tweet_id=tweet_id,
            main_category=main_cat,
            sub_category=sub_cat,
            item_name=item_name,
            tweet_text=content_text,
            tweet_url=tweet_url,
            image_files=image_files,
            image_descriptions=image_descriptions
        )
        
        logging.info(f"Created knowledge base entry for tweet {tweet_id}")
        
    except Exception as e:
        raise StorageError(f"Failed to create knowledge base entry: {e}") 