from pathlib import Path
from typing import Dict, Any, Optional
import logging
from datetime import datetime
from knowledge_base_agent.exceptions import StorageError, ContentProcessingError, ContentGenerationError, KnowledgeBaseItemCreationError
from knowledge_base_agent.config import Config
from knowledge_base_agent.http_client import HTTPClient
from knowledge_base_agent.state_manager import StateManager
from knowledge_base_agent.types import KnowledgeBaseItem, CategoryInfo
import copy

async def generate_content(tweet_data: Dict[str, Any], http_client: HTTPClient, text_model: str) -> str:
    """Generate knowledge base content from tweet data."""
    try:
        # Prepare context including tweet text, URLs, and media descriptions
        context = f"Tweet: {tweet_data.get('full_text', '')}\n\n"  # Updated to full_text
        
        # Add URLs if present
        if tweet_data.get('urls'):
            context += "Related Links:\n"
            for url in tweet_data['urls']:
                context += f"- {url}\n"
            context += "\n"
        
        # Add media descriptions if present
        if tweet_data.get('media'):
            context += "Media:\n"
            for i, media in enumerate(tweet_data['media'], 1):
                if isinstance(media, dict) and media.get('alt_text'):
                    context += f"{i}. {media['alt_text']}\n"

        prompt = (
            f"Based on this content:\n\n{context}\n\n"
            "Generate a detailed technical knowledge base entry that:\n"
            "1. Explains the main technical concepts\n"
            "2. Provides relevant code examples if applicable\n"
            "3. Lists key points and takeaways\n"
            "4. Includes relevant technical details and references\n"
            "\nFormat in Markdown with proper headers and sections."
        )

        logging.debug(f"Sending content generation prompt: {prompt[:200]}...")
        
        content = await http_client.ollama_generate(
            model=text_model,
            prompt=prompt
        )
        
        if not content:
            raise ContentGenerationError("Generated content is empty")
        
        if len(content.strip()) < 50:
            raise ContentGenerationError("Generated content is too short")
        
        if not content.startswith('#'):
            content = f"# Technical Note\n\n{content}"
        
        logging.info(f"Successfully generated content of length: {len(content)}")
        return content.strip()
        
    except Exception as e:
        logging.error(f"Content generation failed: {str(e)}")
        raise ContentGenerationError(f"Failed to generate content: {str(e)}")

async def create_knowledge_base_item(tweet_id: str, tweet_data: Dict[str, Any], config: Config, http_client: HTTPClient) -> KnowledgeBaseItem:
    """Create a knowledge base item from a tweet."""
    try:
        # Get categories data
        categories = tweet_data.get('categories', {})
        
        # Prepare context for LLM
        context = {
            'tweet_text': tweet_data.get('full_text', ''),
            'urls': tweet_data.get('urls', []),
            'media_descriptions': tweet_data.get('image_descriptions', []),
            'main_category': categories.get('main_category', ''),
            'sub_category': categories.get('sub_category', ''),
            'item_name': categories.get('item_name', '')
        }
        
        # Generate comprehensive content using LLM
        prompt = (
            "As a technical knowledge base writer, create a comprehensive entry using this information:\n\n"
            f"Tweet: {context['tweet_text']}\n"
            f"Category: {context['main_category']}/{context['sub_category']}\n"
            f"Topic: {context['item_name']}\n\n"
            "Additional Context:\n"
            f"URLs: {', '.join(context['urls'])}\n"
            "Media Descriptions:\n" + 
            '\n'.join([f"- {desc}" for desc in context['media_descriptions']]) + "\n\n"
            "Generate a detailed technical knowledge base entry that includes:\n"
            "1. A clear title\n"
            "2. A concise description\n"
            "3. Detailed technical content with examples if applicable\n"
            "4. Key takeaways and best practices\n"
            "5. References to any tools or technologies mentioned\n"
            "\nFormat the response in markdown with appropriate sections."
        )
        
        # Generate content using LLM
        generated_content = await http_client.ollama_generate(
            model=config.text_model,
            prompt=prompt
        )
        
        if not generated_content:
            raise ContentGenerationError("Generated content is empty")
        
        # Parse generated content to extract title and description
        content_parts = generated_content.split('\n', 2)
        title = content_parts[0].lstrip('#').strip() if content_parts else context['item_name']
        description = content_parts[1].strip() if len(content_parts) > 1 else context['tweet_text'][:200]
        main_content = content_parts[2] if len(content_parts) > 2 else generated_content
        
        # Create CategoryInfo object
        category_info = CategoryInfo(
            main_category=str(categories.get('main_category', '')),
            sub_category=str(categories.get('sub_category', '')),
            item_name=str(categories.get('item_name', '')),
            description=description
        )
        
        # Get current timestamp
        current_time = datetime.now()
        
        # Create KnowledgeBaseItem with generated content
        kb_item = KnowledgeBaseItem(
            title=title,
            description=description,
            content=main_content,
            category_info=category_info,
            source_tweet={
                'url': f"https://twitter.com/i/web/status/{tweet_id}",
                'author': tweet_data.get('author', ''),
                'created_at': current_time
            },
            media_urls=tweet_data.get('downloaded_media', []),
            image_descriptions=tweet_data.get('image_descriptions', []),
            created_at=current_time,
            last_updated=current_time
        )
        
        return kb_item
        
    except Exception as e:
        logging.error(f"Failed to create knowledge base item for tweet {tweet_id}: {e}")
        raise KnowledgeBaseItemCreationError(f"Failed to create knowledge base item: {str(e)}")

async def create_knowledge_base_entry(
    tweet_id: str,
    tweet_data: Dict[str, Any],
    config: Config,
    http_client: HTTPClient,
    state_manager: Optional[StateManager] = None
) -> None:
    """Create a knowledge base entry for a tweet."""
    from .text_processor import categorize_and_name_content
    from .media_processor import process_media_content
    from .markdown_writer import MarkdownWriter
    
    original_state = copy.deepcopy(tweet_data)
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

        # Combine tweet text and image descriptions
        content_text = tweet_data.get('full_text', '')
        image_descriptions = tweet_data.get('image_descriptions', [])
        combined_text = f"{content_text}\n\n" + "\n".join(image_descriptions) if image_descriptions else content_text

        if not combined_text:
            raise ContentProcessingError(f"No content found for tweet {tweet_id}")

        # Use cached or generate categories
        categories = tweet_data.get('categories')
        if not categories:
            try:
                category_manager = CategoryManager(config, http_client=http_client)
            except Exception as e:
                logging.error(f"Failed to initialize CategoryManager: {e}")
                raise ContentProcessingError(f"Category manager initialization failed: {e}")
            
            main_cat, sub_cat, item_name = await categorize_and_name_content(
                ollama_url=config.ollama_url,
                text=combined_text,
                text_model=config.text_model,
                tweet_id=tweet_id,
                category_manager=category_manager,
                http_client=http_client
            )
            
            categories = {
                'main_category': main_cat,
                'sub_category': sub_cat,
                'item_name': item_name,
                'model_used': config.text_model,
                'categorized_at': datetime.now().isoformat()
            }
            tweet_data['categories'] = categories
            if state_manager:
                await state_manager.update_tweet_data(tweet_id, tweet_data)
        else:
            logging.info(f"Using cached categories for tweet {tweet_id}: {categories}")
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
        
        # Only update state AFTER successful completion
        if state_manager:
            await state_manager.mark_tweet_processed(tweet_id)
            
    except Exception as e:
        logging.error(f"Failed to create knowledge base entry for {tweet_id}: {str(e)}")
        # Restore original state on failure
        if state_manager:
            await state_manager.update_tweet_data(tweet_id, original_state)
            await state_manager.add_unprocessed_tweet(tweet_id)  # Requeue
        raise StorageError(f"Failed to create knowledge base entry: {e}")