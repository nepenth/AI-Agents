from pathlib import Path
from typing import Dict, Any, Tuple, Optional
import logging
from datetime import datetime
from knowledge_base_agent.markdown_writer import MarkdownWriter
from knowledge_base_agent.exceptions import StorageError, ContentProcessingError, ContentGenerationError, CategoryGenerationError, KnowledgeBaseItemCreationError
from knowledge_base_agent.category_manager import CategoryManager
from knowledge_base_agent.config import Config
from knowledge_base_agent.ai_categorization import classify_content, generate_content_name
from knowledge_base_agent.tweet_utils import sanitize_filename
from knowledge_base_agent.image_interpreter import interpret_image
from knowledge_base_agent.http_client import HTTPClient
from knowledge_base_agent.file_utils import async_json_load, async_json_dump
from knowledge_base_agent.state_manager import StateManager
from .types import TweetData, KnowledgeBaseItem, CategoryInfo
import json
import aiohttp
import re

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
            logging.info(f"No cached categories found for tweet {tweet_id}")
            try:
                # Combine tweet text and image descriptions
                content_text = tweet_data.get('full_text', '')
                image_descriptions = tweet_data.get('image_descriptions', [])
                
                if not content_text:
                    raise ContentProcessingError(f"No text content found for tweet {tweet_id}")
                    
                combined_text = f"{content_text}\n\n" + "\n".join(image_descriptions)
                logging.info(f"Combined text for categorization: {combined_text[:100]}...")
                
                # Updated categorization call to use http_client
                logging.info(f"Calling categorize_and_name_content for tweet {tweet_id}")
                try:
                    main_cat, sub_cat, item_name = await categorize_and_name_content(
                        http_client=http_client,  # Changed: pass http_client instead of ollama_url
                        combined_text=combined_text,
                        text_model=config.text_model,
                        tweet_id=tweet_id,
                        category_manager=CategoryManager(config)
                    )
                    logging.info(f"Generated categories: {main_cat}/{sub_cat}/{item_name}")
                except Exception as e:
                    logging.error(f"Failed to generate categories: {str(e)}")
                    raise
                
                # Store categories in tweet data
                categories = {
                    'main_category': main_cat,
                    'sub_category': sub_cat,
                    'item_name': item_name,
                    'model_used': config.text_model,
                    'categorized_at': datetime.now().isoformat()
                }
                tweet_data['categories'] = categories
                
                # Update cache
                if state_manager:
                    await state_manager.update_tweet_data(tweet_id, tweet_data)
            except Exception as e:
                logging.error(f"Failed to generate categories for tweet {tweet_id}: {str(e)}")
                raise
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
        
    except Exception as e:
        logging.error(f"Failed to create knowledge base entry for {tweet_id}: {str(e)}")
        raise StorageError(f"Failed to create knowledge base entry: {e}")

class ContentProcessor:
    """Handles processing of tweet content into knowledge base items."""
    
    def __init__(self, http_client: HTTPClient):
        self.http_client = http_client
        self.text_model = self.http_client.config.text_model
        logging.info(f"Initialized ContentProcessor with model: {self.text_model}")

    @classmethod
    async def create_knowledge_base_entry(cls, tweet_data: Dict[str, Any], http_client: HTTPClient) -> KnowledgeBaseItem:
        """Factory method to create a knowledge base entry from tweet data."""
        tweet_id = tweet_data.get('id_str', tweet_data.get('id', 'unknown'))
        
        try:
            # Log the raw tweet data structure
            logging.debug(f"Raw tweet data for {tweet_id}: {tweet_data}")
            
            # Validate tweet data
            if not isinstance(tweet_data, dict):
                raise ValueError(f"Tweet data must be a dictionary, got {type(tweet_data)}")
            
            # Check for required fields
            required_fields = ['text', 'id']
            for field in required_fields:
                if field not in tweet_data:
                    raise ValueError(f"Missing required field '{field}' in tweet data")
            
            # Create processor instance
            try:
                processor = cls(http_client)
                logging.info(f"Created processor instance for tweet {tweet_id}")
            except Exception as e:
                logging.error(f"Failed to create processor instance: {str(e)}")
                raise
            
            # Create knowledge base item
            try:
                kb_item = await processor.create_knowledge_base_item(tweet_data)
                logging.info(f"Successfully created knowledge base item for tweet {tweet_id}")
                return kb_item
            except Exception as e:
                logging.error(f"Failed in create_knowledge_base_item: {str(e)}")
                logging.error(f"Tweet data keys: {list(tweet_data.keys())}")
                raise
            
        except Exception as e:
            error_msg = f"Failed to create knowledge base entry for tweet {tweet_id}: {str(e)}"
            logging.error(error_msg)
            logging.error(f"Tweet data keys available: {list(tweet_data.keys()) if isinstance(tweet_data, dict) else 'Invalid data'}")
            raise KnowledgeBaseItemCreationError(error_msg)

    async def generate_categories(self, tweet_text: str) -> CategoryInfo:
        """Generate category information from tweet text."""
        try:
            prompt = (
                "Analyze this tweet and provide category information in JSON format:\n\n"
                f"Tweet: {tweet_text}\n\n"
                "Required format:\n"
                "{\n"
                '  "category": "main technical category",\n'
                '  "subcategory": "specific technical subcategory",\n'
                '  "name": "concise_technical_name",\n'
                '  "description": "brief technical description"\n'
                "}\n\n"
                "Rules:\n"
                "- Categories should be technical and specific\n"
                "- Name should be 2-4 words, lowercase with underscores\n"
                "- Description should be 1-2 sentences\n"
            )

            logging.debug(f"Sending category generation prompt for tweet text: {tweet_text[:100]}...")
            
            # Use the ollama_generate method
            response_text = await self.http_client.ollama_generate(
                model=self.text_model,
                prompt=prompt
            )
            
            if not response_text:
                raise CategoryGenerationError("Empty response from Ollama")
            
            try:
                # Try to parse the JSON response
                result = json.loads(response_text)
            except json.JSONDecodeError:
                # If JSON parsing fails, try to extract JSON from the response
                # Sometimes the model might include additional text
                json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
                if json_match:
                    try:
                        result = json.loads(json_match.group(0))
                    except json.JSONDecodeError as e:
                        logging.error(f"Failed to parse extracted JSON: {e}")
                        logging.error(f"Raw response: {response_text}")
                        raise CategoryGenerationError("Invalid JSON format in response")
                else:
                    logging.error(f"No JSON found in response: {response_text}")
                    raise CategoryGenerationError("No valid JSON found in response")
            
            # Validate required fields
            required_fields = ["category", "subcategory", "name", "description"]
            if not all(field in result for field in required_fields):
                missing_fields = [field for field in required_fields if field not in result]
                raise CategoryGenerationError(f"Missing required fields: {missing_fields}")
            
            # Normalize field values
            result["category"] = result["category"].lower().replace(" ", "_")
            result["subcategory"] = result["subcategory"].lower().replace(" ", "_")
            result["name"] = result["name"].lower().replace(" ", "_")
            
            logging.info(f"Successfully generated categories: {result}")
            return CategoryInfo(**result)
            
        except Exception as e:
            logging.error(f"Category generation failed: {str(e)}")
            logging.error(f"Tweet text: {tweet_text[:100]}...")
            raise CategoryGenerationError(f"Failed to generate categories: {str(e)}")

    async def generate_content(self, tweet_data: Dict[str, Any]) -> str:
        """Generate knowledge base content from tweet data."""
        try:
            # Prepare context including tweet text and any media descriptions
            context = f"Tweet: {tweet_data['text']}\n\n"
            if tweet_data.get('media'):
                context += "Media:\n"
                for i, media in enumerate(tweet_data['media'], 1):
                    if media.get('alt_text'):
                        context += f"{i}. {media['alt_text']}\n"

            prompt = (
                f"Based on this content:\n\n{context}\n\n"
                "Generate a detailed technical knowledge base entry that:\n"
                "1. Explains the main technical concepts\n"
                "2. Provides relevant code examples if applicable\n"
                "3. Lists key points and takeaways\n"
                "4. Includes relevant technical details\n"
                "\nFormat in Markdown with proper headers and sections."
            )

            logging.debug(f"Sending content generation prompt: {prompt[:200]}...")
            
            # Use the ollama_generate method
            content = await self.http_client.ollama_generate(
                model=self.text_model,
                prompt=prompt
            )
            
            if not content:
                raise ContentGenerationError("Generated content is empty")
            
            # Basic content validation
            if len(content.strip()) < 50:
                raise ContentGenerationError("Generated content is too short")
            
            if not content.startswith('#'):
                content = f"# Technical Note\n\n{content}"
            
            logging.info(f"Successfully generated content of length: {len(content)}")
            return content.strip()
            
        except Exception as e:
            logging.error(f"Content generation failed: {str(e)}")
            raise ContentGenerationError(f"Failed to generate content: {str(e)}")

    async def create_knowledge_base_item(self, tweet_data: TweetData) -> KnowledgeBaseItem:
        """Create a complete knowledge base item from tweet data."""
        tweet_id = tweet_data.get('id_str', tweet_data.get('id', 'unknown'))
        logging.info(f"Starting create_knowledge_base_item for tweet {tweet_id}")
        
        try:
            # Extract and validate tweet text
            tweet_text = tweet_data.get('full_text', tweet_data.get('text', ''))
            if not tweet_text:
                raise ContentGenerationError(f"No text content found in tweet {tweet_id}")
            
            logging.info(f"Extracted text for tweet {tweet_id}: {tweet_text[:100]}...")
            
            # Generate categories
            try:
                category_info = await self.generate_categories(tweet_text)
                logging.info(f"Generated categories for tweet {tweet_id}: {category_info}")
            except Exception as e:
                logging.error(f"Category generation failed for tweet {tweet_id}: {str(e)}")
                raise
            
            # Generate content
            try:
                context = {
                    'text': tweet_text,
                    'media': tweet_data.get('media', []),
                    'image_descriptions': tweet_data.get('image_descriptions', [])
                }
                content = await self.generate_content(context)
                logging.info(f"Generated content for tweet {tweet_id}, length: {len(content)}")
            except Exception as e:
                logging.error(f"Content generation failed for tweet {tweet_id}: {str(e)}")
                raise
            
            # Create and return knowledge base item
            try:
                kb_item = KnowledgeBaseItem(
                    title=category_info.name.replace('_', ' ').title(),
                    description=category_info.description,
                    content=content,
                    category_info={
                        'main_category': category_info.category,
                        'sub_category': category_info.subcategory,
                        'item_name': category_info.name
                    },
                    source_tweet={
                        'id': tweet_id,
                        'text': tweet_text,
                        'url': tweet_data.get('tweet_url', ''),
                        'media': tweet_data.get('media', [])
                    },
                    media_analysis=tweet_data.get('image_descriptions', []),
                    created_at=datetime.now(),
                    last_updated=datetime.now()
                )
                logging.info(f"Created knowledge base item structure for tweet {tweet_id}")
                return kb_item
            except Exception as e:
                logging.error(f"Failed to create knowledge base item structure for tweet {tweet_id}: {str(e)}")
                raise
            
        except Exception as e:
            error_msg = f"Failed in create_knowledge_base_item for tweet {tweet_id}: {str(e)}"
            logging.error(error_msg)
            logging.error(f"Available tweet data keys: {list(tweet_data.keys())}")
            raise KnowledgeBaseItemCreationError(error_msg) 