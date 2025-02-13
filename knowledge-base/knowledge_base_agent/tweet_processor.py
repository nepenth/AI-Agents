from typing import List, Dict, Any, Optional
import logging
import asyncio
from pathlib import Path
import datetime

from knowledge_base_agent.config import Config
from knowledge_base_agent.category_manager import CategoryManager
from knowledge_base_agent.exceptions import ProcessingError, AIError, StorageError
from knowledge_base_agent.state_manager import save_processed_tweets, load_processed_tweets
from knowledge_base_agent.tweet_utils import parse_tweet_id_from_url
from knowledge_base_agent.cache_manager import get_cached_tweet, update_cache, save_cache
from knowledge_base_agent.ai_categorization import categorize_and_name_content
from knowledge_base_agent.markdown_writer import MarkdownWriter

async def process_tweets(
    urls: List[str],
    config: Config,
    category_manager: CategoryManager,
    http_client: Any,
    tweet_cache: Dict[str, Any]
) -> None:
    """Process a list of tweet URLs, categorizing and storing them."""
    markdown_writer = MarkdownWriter()
    
    for url in urls:
        try:
            tweet_id = url.split('/')[-1]
            tweet_data = get_cached_tweet(tweet_id, tweet_cache)
            
            if not tweet_data:
                logging.warning(f"No cached data found for tweet {tweet_id}")
                continue

            # Combine tweet text and image descriptions for categorization
            content_text = tweet_data.get('full_text', '')
            image_descriptions = tweet_data.get('image_descriptions', [])
            combined_text = f"{content_text}\n\n" + "\n".join(image_descriptions)

            # Get AI categorization
            main_cat, sub_cat, item_name = await categorize_and_name_content(
                text=combined_text,
                category_manager=category_manager,
                http_client=http_client,
                ollama_url=config.ollama_url,
                model=config.text_model
            )

            # Write to knowledge base
            image_files = [Path(p) for p in tweet_data.get('downloaded_media', [])]
            await markdown_writer.write_tweet_markdown(
                config=config,
                tweet_id=tweet_id,
                main_category=main_cat,
                sub_category=sub_cat,
                item_name=item_name,
                tweet_text=content_text,
                tweet_url=url,
                image_files=image_files,
                image_descriptions=image_descriptions
            )
            
            logging.info(f"Successfully processed tweet {tweet_id}")
            
        except Exception as e:
            logging.error(f"Failed to process tweet {url}: {e}")
            continue

async def process_single_tweet(
    tweet_id: str,
    url: str,
    config: Config,
    category_manager: CategoryManager,
    http_client: Any,
    tweet_cache: Dict[str, Any],
    processed_tweets: Dict[str, Any]
) -> None:
    """
    Process a single tweet, handling categorization and storage.
    
    Raises:
        AIError: If AI-related operations fail
        StorageError: If storage operations fail
    """
    try:
        tweet_data = get_cached_tweet(tweet_id, tweet_cache)
        if not tweet_data:
            raise ProcessingError(f"No cached data found for tweet {tweet_id}")

        # Combine tweet text and image descriptions
        combined_text = _prepare_tweet_content(tweet_data)
        
        # Get categorization from AI
        try:
            main_cat, sub_cat, item_name = await categorize_and_name_content(
                text=combined_text,
                category_manager=category_manager,
                http_client=http_client,
                ollama_url=config.ollama_url,
                model=config.text_model
            )
        except Exception as e:
            raise AIError(f"Failed to categorize tweet {tweet_id}: {e}")

        # Write to knowledge base
        try:
            await write_to_knowledge_base(
                tweet_id=tweet_id,
                tweet_data=tweet_data,
                categories=(main_cat, sub_cat, item_name),
                config=config
            )
        except Exception as e:
            raise StorageError(f"Failed to write tweet {tweet_id} to knowledge base: {e}")

        # Update processed state
        processed_tweets[tweet_id] = {
            "item_name": item_name,
            "main_category": main_cat,
            "sub_category": sub_cat,
            "timestamp": datetime.datetime.now().isoformat()
        }
        
    except Exception as e:
        raise ProcessingError(f"Failed to process tweet {tweet_id}: {e}")

def _prepare_tweet_content(tweet_data: Dict[str, Any]) -> str:
    """Prepare tweet content by combining text and image descriptions."""
    content_parts = []
    
    if tweet_text := tweet_data.get("full_text"):
        content_parts.append(f"Tweet text: {tweet_text}")
        
    for idx, desc in enumerate(tweet_data.get("image_descriptions", []), 1):
        content_parts.append(f"Image {idx} interpretation: {desc}")
        
    return "\n\n".join(content_parts)

async def write_to_knowledge_base(
    tweet_id: str,
    tweet_data: Dict[str, Any],
    categories: tuple[str, str, str],
    config: Config
) -> None:
    """
    Write tweet data to the knowledge base.
    
    Raises:
        StorageError: If writing fails
    """
    try:
        # Knowledge base writing logic here
        pass
    except Exception as e:
        raise StorageError(f"Failed to write to knowledge base: {e}") 