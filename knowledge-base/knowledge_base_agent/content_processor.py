from pathlib import Path
from typing import Dict, Any, Tuple, Optional
import logging
from datetime import datetime
from knowledge_base_agent.markdown_writer import MarkdownWriter
from knowledge_base_agent.exceptions import StorageError, ContentProcessingError
from knowledge_base_agent.category_manager import CategoryManager
from knowledge_base_agent.config import Config
from knowledge_base_agent.ai_categorization import classify_content, generate_content_name
from knowledge_base_agent.tweet_utils import sanitize_filename
from knowledge_base_agent.image_interpreter import interpret_image
from knowledge_base_agent.http_client import HTTPClient
from knowledge_base_agent.file_utils import async_json_load, async_json_dump
from knowledge_base_agent.state_manager import StateManager

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

async def process_media_content(
    tweet_data: Dict[str, Any],
    http_client: HTTPClient,
    config: Config
) -> Dict[str, Any]:
    """Process media content including image interpretation."""
    try:
        media_paths = tweet_data.get('downloaded_media', [])
        if not media_paths:
            return tweet_data
            
        image_descriptions = []
        for media_path in media_paths:
            if not Path(media_path).exists():
                raise ContentProcessingError(f"Media file not found: {media_path}")
                
            description = await interpret_image(
                http_client=http_client,
                image_path=Path(media_path),
                vision_model=config.vision_model
            )
            if not description:
                raise ContentProcessingError(f"Failed to get image description for {media_path}")
            image_descriptions.append(description)
            
        tweet_data['image_descriptions'] = image_descriptions
        return tweet_data
        
    except Exception as e:
        raise ContentProcessingError(f"Failed to process media content: {e}")

async def create_knowledge_base_entry(
    tweet_id: str,
    tweet_data: Dict[str, Any],
    config: Config,
    http_client: HTTPClient,
    state_manager: Optional[StateManager] = None
) -> None:
    """Create a knowledge base entry for a tweet."""
    try:
        logging.info(f"Starting knowledge base entry creation for tweet {tweet_id}")
        
        # Process media content first
        logging.info(f"Processing media content for tweet {tweet_id}")
        try:
            tweet_data = await process_media_content(tweet_data, http_client, config)
            logging.info(f"Successfully processed media for tweet {tweet_id}")
        except Exception as e:
            logging.error(f"Failed to process media content for tweet {tweet_id}: {str(e)}")
            raise
        
        # Get or generate categories
        categories = tweet_data.get('categories')
        if not categories:
            logging.info(f"No cached categories found for tweet {tweet_id}, this is expected for first-time processing")
            try:
                # Combine tweet text and image descriptions for categorization
                content_text = tweet_data.get('full_text', '')
                image_descriptions = tweet_data.get('image_descriptions', [])
                
                if not content_text:
                    logging.error(f"No text content found for tweet {tweet_id}")
                    raise ContentProcessingError(f"No text content found for tweet {tweet_id}")
                    
                combined_text = f"{content_text}\n\n" + "\n".join(image_descriptions)
                logging.info(f"Combined text for categorization: {combined_text[:100]}...")
                
                # Get categorization
                main_cat, sub_cat, item_name = await categorize_and_name_content(
                    config.ollama_url,
                    combined_text,
                    config.text_model,
                    tweet_id,
                    CategoryManager(config)
                )
                logging.info(f"Generated new categories for tweet {tweet_id}: {main_cat}/{sub_cat}/{item_name}")
                
                # Store categories in tweet data
                categories = {
                    'main_category': main_cat,
                    'sub_category': sub_cat,
                    'item_name': item_name,
                    'model_used': config.text_model,
                    'categorized_at': datetime.now().isoformat()
                }
                tweet_data['categories'] = categories
                
                # Update cache with new categories
                if state_manager:
                    logging.info(f"Updating cache with new categories for tweet {tweet_id}")
                    await state_manager.update_tweet_data(tweet_id, tweet_data)
            except Exception as e:
                logging.error(f"Failed to generate categories for tweet {tweet_id}: {str(e)}")
                raise
        else:
            logging.info(f"Using cached categories for tweet {tweet_id}: {categories}")
        
        # Use stored categories
        main_cat = categories['main_category']
        sub_cat = categories['sub_category']
        item_name = categories['item_name']
        
        # Extract necessary data
        content_text = tweet_data.get('full_text', '')
        tweet_url = tweet_data.get('tweet_url', '')
        image_files = [Path(p) for p in tweet_data.get('downloaded_media', [])]
        image_descriptions = tweet_data.get('image_descriptions', [])
        
        logging.info(f"Preparing to write markdown for tweet {tweet_id}")
        logging.info(f"Categories: {main_cat}/{sub_cat}/{item_name}")
        logging.info(f"Content length: {len(content_text)}")
        logging.info(f"Number of images: {len(image_files)}")
        logging.info(f"Tweet data keys: {list(tweet_data.keys())}")
        
        if not content_text:
            raise ContentProcessingError(f"No text content found for tweet {tweet_id}")
            
        # Write markdown content
        try:
            markdown_writer = MarkdownWriter(config)
            await markdown_writer.write_tweet_markdown(
                config.knowledge_base_dir,
                tweet_id=tweet_id,
                tweet_data=tweet_data,
                image_files=image_files,
                image_descriptions=image_descriptions,
                main_category=main_cat,
                sub_category=sub_cat,
                item_name=item_name,
                tweet_text=content_text,
                tweet_url=tweet_url
            )
            logging.info(f"Successfully wrote markdown for tweet {tweet_id}")
        except Exception as e:
            logging.error(f"Failed to write markdown for tweet {tweet_id}: {str(e)}")
            raise
        
        logging.info(f"Successfully created knowledge base entry for tweet {tweet_id}")
        
    except Exception as e:
        logging.error(f"Failed to create knowledge base entry for {tweet_id}: {str(e)}")
        raise StorageError(f"Failed to create knowledge base entry: {e}") 