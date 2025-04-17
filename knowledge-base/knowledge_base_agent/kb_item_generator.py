from pathlib import Path
from typing import Dict, Any, Optional, Tuple
import logging
from datetime import datetime
from knowledge_base_agent.exceptions import StorageError, ContentProcessingError, ContentGenerationError, KnowledgeBaseItemCreationError
from knowledge_base_agent.config import Config
from knowledge_base_agent.http_client import HTTPClient
from knowledge_base_agent.state_manager import StateManager
from knowledge_base_agent.types import KnowledgeBaseItem, CategoryInfo
from knowledge_base_agent.category_manager import CategoryManager
import copy
from mimetypes import guess_type
from knowledge_base_agent.media_processor import VIDEO_MIME_TYPES
import asyncio

async def generate_content(tweet_data: Dict[str, Any], http_client: HTTPClient, text_model: str, fallback_model: str = "") -> str:
    """Generate knowledge base content from tweet data with enhanced validation and fallback."""
    try:
        # Prepare context including tweet text, URLs, and media descriptions
        context = f"Tweet: {tweet_data.get('full_text', '')}\n\n"
        
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

        # Dynamically adjust prompt based on content
        is_technical = any(keyword in context.lower() for keyword in ['code', 'programming', 'api', 'framework', 'library'])
        prompt_focus = "technical concepts with code examples" if is_technical else "key ideas and practical insights"
        prompt = (
            f"Based on this content:\n\n{context}\n\n"
            f"Generate a detailed knowledge base entry that focuses on {prompt_focus}:\n"
            "1. Explains the main concepts or ideas\n"
            "2. Provides relevant examples if applicable\n"
            "3. Lists key points and takeaways\n"
            "4. Includes relevant details and references\n"
            "\nFormat in Markdown with proper headers and sections."
        )

        logging.debug(f"Sending content generation prompt: {prompt[:200]}...")
        
        max_retries = 3
        for attempt in range(max_retries):
            try:
                content = await http_client.ollama_generate(
                    model=text_model,
                    prompt=prompt,
                    temperature=0.3  # Moderate temperature for content generation
                )
                
                if not content:
                    raise ContentGenerationError("Generated content is empty")
                
                if len(content.strip()) < 50:
                    raise ContentGenerationError("Generated content is too short")
                
                # Enhanced validation for content structure
                if not content.startswith('#') or '##' not in content or '-' not in content:
                    logging.warning("Generated content lacks proper structure, adding basic formatting")
                    content = f"# Knowledge Base Entry\n\n## Overview\n\n{content}\n\n## Key Takeaways\n\n- To be updated."

                logging.info(f"Successfully generated content of length: {len(content)}")
                return content.strip()
            except Exception as e:
                logging.error(f"Attempt {attempt + 1} with {text_model} for content generation failed: {e}")
                if attempt < max_retries - 1:
                    await asyncio.sleep(2 ** attempt)
                    continue
                
                # Try fallback model if available and this is the last attempt
                if fallback_model and fallback_model != text_model:
                    logging.info(f"Switching to fallback model {fallback_model} for content generation")
                    for fallback_attempt in range(max_retries):
                        try:
                            content = await http_client.ollama_generate(
                                model=fallback_model,
                                prompt=prompt,
                                temperature=0.3
                            )
                            
                            if not content:
                                raise ContentGenerationError("Generated content is empty from fallback model")
                            
                            if len(content.strip()) < 50:
                                raise ContentGenerationError("Generated content is too short from fallback model")
                            
                            # Enhanced validation for content structure
                            if not content.startswith('#') or '##' not in content or '-' not in content:
                                logging.warning("Generated content lacks proper structure from fallback, adding basic formatting")
                                content = f"# Knowledge Base Entry\n\n## Overview\n\n{content}\n\n## Key Takeaways\n\n- To be updated."

                            logging.info(f"Successfully generated content with fallback model, length: {len(content)}")
                            return content.strip()
                        except Exception as fe:
                            logging.error(f"Fallback attempt {fallback_attempt + 1} with {fallback_model} failed: {fe}")
                            if fallback_attempt < max_retries - 1:
                                await asyncio.sleep(2 ** fallback_attempt)
                                continue

        # If all retries and fallback fail, use fallback content
        logging.error("All attempts failed, using fallback content")
        fallback_content = f"# Tweet Summary\n\n## Content\n\n{tweet_data.get('full_text', 'No content available')}\n\n## Key Takeaways\n\n- Tweet content preserved as-is due to generation failure."
        logging.info(f"Using fallback content for tweet due to generation failure")
        return fallback_content
        
    except Exception as e:
        logging.error(f"Content generation failed: {str(e)}")
        # Fallback to a basic template using raw tweet data
        fallback_content = f"# Tweet Summary\n\n## Content\n\n{tweet_data.get('full_text', 'No content available')}\n\n## Key Takeaways\n\n- Tweet content preserved as-is due to generation failure."
        logging.info(f"Using fallback content for tweet due to generation failure")
        return fallback_content

async def create_knowledge_base_item(tweet_id: str, tweet_data: Dict[str, Any], config: Config, http_client: HTTPClient, state_manager: Optional[StateManager] = None) -> KnowledgeBaseItem:
    """Create a knowledge base item from a tweet. Requires categories to be processed."""
    try:
        # Categories MUST exist and be processed before this step
        categories = tweet_data.get('categories', {})
        if not categories or not all(categories.get(key) for key in ['main_category', 'sub_category', 'item_name']) or not tweet_data.get('categories_processed'):
            logging.error(f"Cannot create KB item for tweet {tweet_id}: Categories are missing or incomplete. Tweet data: {tweet_data.get('categories')}, Processed Flag: {tweet_data.get('categories_processed')}")
            raise KnowledgeBaseItemCreationError(f"Categories not processed or incomplete for tweet {tweet_id}")

        # Prepare context for LLM (using guaranteed categories)
        context = {
            'tweet_text': tweet_data.get('full_text', ''),
            'urls': tweet_data.get('urls', []),
            'media_descriptions': tweet_data.get('image_descriptions', []),
            'main_category': categories['main_category'], # Use directly
            'sub_category': categories['sub_category'],
            'item_name': categories['item_name']
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
        generated_content = await generate_content(tweet_data, http_client, config.text_model, config.fallback_model) # Pass fallback model from config

        if not generated_content:
            # generate_content now returns a fallback template if it truly fails,
            # but we might still want stricter checking here if needed.
            logging.warning(f"Content generation returned potentially empty or minimal content for tweet {tweet_id}")
            # Let's proceed but rely on the fallback content from generate_content

        # Parse generated content to extract title and description
        content_parts = generated_content.split('\n', 2)
        title = content_parts[0].lstrip('#').strip() if content_parts else context['item_name']
        description = content_parts[1].strip() if len(content_parts) > 1 else context['tweet_text'][:200]
        main_content = content_parts[2] if len(content_parts) > 2 else generated_content
        
        # Create CategoryInfo object
        category_info = CategoryInfo(
            main_category=str(categories['main_category']),
            sub_category=str(categories['sub_category']),
            item_name=str(categories['item_name']),
            description=description # Use parsed description
        )
        
        # Get current timestamp
        current_time = datetime.now()
        
        # Create KnowledgeBaseItem with generated content
        kb_item = KnowledgeBaseItem(
            title=title, # Use parsed title
            description=description,
            content=main_content,
            category_info=category_info,
            source_tweet={
                'url': f"https://twitter.com/i/web/status/{tweet_id}",
                'author': tweet_data.get('author', ''),
                'created_at': tweet_data.get('created_at') or current_time.isoformat() # Use original creation time if available
            },
            media_urls=tweet_data.get('downloaded_media', []),
            image_descriptions=tweet_data.get('image_descriptions', []),
            created_at=current_time,
            last_updated=current_time
        )
        
        return kb_item

    except KnowledgeBaseItemCreationError: # Re-raise specific error
        raise
    except Exception as e:
        logging.exception(f"Unexpected error creating knowledge base item for tweet {tweet_id}: {e}") # Log traceback
        raise KnowledgeBaseItemCreationError(f"Failed to create knowledge base item: {str(e)}") from e

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
        
        # Filter out video files before passing to markdown writer
        media_paths = tweet_data.get('downloaded_media', [])
        image_files = []
        for media_path in media_paths:
            path_obj = Path(media_path)
            mime_type, _ = guess_type(str(path_obj))
            is_video = mime_type in VIDEO_MIME_TYPES or path_obj.suffix.lower() in {'.mp4', '.mov', '.avi', '.mkv'}
            if not is_video and path_obj.exists():  # Only include non-video files that exist
                image_files.append(path_obj)
        
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