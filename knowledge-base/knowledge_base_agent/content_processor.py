from pathlib import Path
from typing import Dict, Any, Tuple, Optional, List
import logging
from datetime import datetime
from knowledge_base_agent.exceptions import StorageError, ContentProcessingError, ContentGenerationError, CategoryGenerationError, KnowledgeBaseItemCreationError
from knowledge_base_agent.category_manager import CategoryManager
from knowledge_base_agent.config import Config
from knowledge_base_agent.ai_categorization import classify_content, generate_content_name
from knowledge_base_agent.tweet_utils import sanitize_filename
from knowledge_base_agent.image_interpreter import interpret_image
from knowledge_base_agent.http_client import HTTPClient
from knowledge_base_agent.file_utils import async_json_load, async_json_dump
from knowledge_base_agent.state_manager import StateManager
from knowledge_base_agent.types import TweetData, KnowledgeBaseItem, CategoryInfo
import json
import re
from knowledge_base_agent.progress import ProcessingStats
from knowledge_base_agent.prompts import UserPreferences
from knowledge_base_agent.playwright_fetcher import fetch_tweet_data_playwright

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
        # Skip if already processed
        if tweet_data.get('media_processed', False):
            logging.info("Media already processed, skipping...")
            return tweet_data
            
        media_paths = tweet_data.get('downloaded_media', [])
        if not media_paths:
            tweet_data['media_processed'] = True
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
        tweet_data['media_processed'] = True
        return tweet_data
        
    except Exception as e:
        raise ContentProcessingError(f"Failed to process media content: {e}")

async def process_categories(
    tweet_id: str,
    tweet_data: Dict[str, Any],
    config: Config,
    http_client: HTTPClient,
    state_manager: Optional[StateManager] = None
) -> Dict[str, Any]:
    """Process and assign categories to a tweet."""
    try:
        # Skip if already categorized
        if tweet_data.get('categories_processed', False):
            logging.info(f"Categories already processed for tweet {tweet_id}, skipping...")
            return tweet_data

        # Ensure media is processed first
        if not tweet_data.get('media_processed', False):
            logging.info(f"Media not yet processed for tweet {tweet_id}, processing now...")
            tweet_data = await process_media_content(tweet_data, http_client, config)

        # Generate categories
        tweet_text = tweet_data.get('full_text', '')
        image_descriptions = tweet_data.get('image_descriptions', [])
        combined_text = f"{tweet_text}\n\nImage Descriptions:\n" + "\n".join(image_descriptions)

        category_manager = CategoryManager(config)
        main_cat, sub_cat, item_name = await categorize_and_name_content(
            ollama_url=config.ollama_url,
            text=combined_text,
            text_model=config.text_model,
            tweet_id=tweet_id,
            category_manager=category_manager
        )
        
        # Save categories
        tweet_data['categories'] = {
            'main_category': main_cat,
            'sub_category': sub_cat,
            'item_name': item_name,
            'model_used': config.text_model,
            'categorized_at': datetime.now().isoformat()
        }
        tweet_data['categories_processed'] = True

        # Update state if manager provided
        if state_manager:
            await state_manager.update_tweet_data(tweet_id, tweet_data)

        return tweet_data

    except Exception as e:
        logging.error(f"Failed to process categories for tweet {tweet_id}: {str(e)}")
        raise CategoryGenerationError(f"Failed to process categories: {str(e)}")

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
                category_manager = CategoryManager(config)
            except Exception as e:
                logging.error(f"Failed to initialize CategoryManager: {e}")
                raise ContentProcessingError(f"Category manager initialization failed: {e}")
            
            main_cat, sub_cat, item_name = await categorize_and_name_content(
                ollama_url=config.ollama_url,
                text=combined_text,
                text_model=config.text_model,
                tweet_id=tweet_id,
                category_manager=category_manager
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
            # Import here to avoid circular import
            from knowledge_base_agent.markdown_writer import MarkdownWriter
            
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
    
    def __init__(self, config: Config, http_client: HTTPClient):
        """Initialize the content processor with configuration."""
        if not http_client:
            raise ValueError("HTTP client is required")
            
        self.config = config
        self.http_client = http_client
        self.text_model = self.http_client.config.text_model
        logging.info(f"Initialized ContentProcessor with model: {self.text_model}")
        self.category_manager = CategoryManager(config)
        self.state_manager = StateManager(config)

    @classmethod
    async def create_knowledge_base_entry(cls, tweet_data: Dict[str, Any], http_client: HTTPClient, tweet_cache: Dict[str, Any]) -> KnowledgeBaseItem:
        """Factory method to create a knowledge base entry from tweet data."""
        # Get tweet ID from the cache key instead of looking inside tweet_data
        tweet_id = next((k for k, v in tweet_cache.items() if v is tweet_data), None)
        if not tweet_id:
            logging.error("Could not find tweet ID in cache")
            raise ValueError("Tweet data not found in cache")
        
        try:
            # Log the raw tweet data structure
            logging.debug(f"Raw tweet data for {tweet_id}: {tweet_data}")
            
            # Validate tweet data
            if not isinstance(tweet_data, dict):
                raise ValueError(f"Tweet data must be a dictionary, got {type(tweet_data)}")
            
            # Create processor instance
            try:
                processor = cls(http_client)
                logging.info(f"Created processor instance for tweet {tweet_id}")
            except Exception as e:
                logging.error(f"Failed to create processor instance for tweet {tweet_id}: {str(e)}")
                raise
            
            # Create knowledge base item
            try:
                kb_item = await processor.create_knowledge_base_item(tweet_id, tweet_data, processor.http_client.config)
                logging.info(f"Successfully created knowledge base item for tweet {tweet_id}")
                return kb_item
            except Exception as e:
                logging.error(f"Failed in create_knowledge_base_item for tweet {tweet_id}: {str(e)}")
                raise
            
        except Exception as e:
            error_msg = f"Failed to create knowledge base entry for tweet {tweet_id}: {str(e)}"
            logging.error(error_msg)
            raise KnowledgeBaseItemCreationError(error_msg)

    async def generate_categories(self, tweet_text: str, tweet_id: str) -> CategoryInfo:
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
            # Use the rate-limited http_client
            response_text = await self.http_client.ollama_generate(
                model=self.text_model,
                prompt=prompt,
                temperature=0.7  # More deterministic for categories
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
            if isinstance(tweet_data, str):
                context = f"Tweet: {tweet_data}\n\n"
            else:
                context = f"Tweet: {tweet_data.get('text', '')}\n\n"
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
                "4. Includes relevant technical details\n"
                "\nFormat in Markdown with proper headers and sections."
            )

            logging.debug(f"Sending content generation prompt: {prompt[:200]}...")
            
            content = await self.http_client.ollama_generate(
                model=self.text_model,
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

    async def create_knowledge_base_item(self, tweet_id: str, tweet_data: TweetData, config: Config) -> KnowledgeBaseItem:
        """Create a complete knowledge base item from tweet data."""
        try:
            tweet_text = tweet_data.get('full_text', tweet_data.get('text', ''))
            if not tweet_text:
                raise ContentGenerationError("No text content found in tweet {}".format(tweet_id))
            
            # Generate categories first and save them
            category_info = await self.generate_categories(tweet_text, tweet_id)
            
            # Save categories even if content generation fails
            tweet_data['categories'] = {
                'main_category': category_info.category,
                'sub_category': category_info.subcategory,
                'name': category_info.name
            }
            
            try:
                context = {
                    'id': tweet_id,
                    'text': tweet_text,
                    'media': tweet_data.get('media', []),
                    'image_descriptions': tweet_data.get('image_descriptions', [])
                }
                content = await self.generate_content(context)
            except Exception as e:
                logging.error(f"Content generation failed for tweet {tweet_id}: {str(e)}")
                # Use a simplified content if generation fails
                content = f"Original Tweet: {tweet_text}"
            
            # Create KB item with whatever content we have
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
            
            # Update tweet data with KB item creation status and path
            tweet_data['kb_item_created'] = True
            tweet_data['kb_item_path'] = str(Path(
                config.knowledge_base_dir,
                kb_item.category_info['main_category'],
                kb_item.category_info['sub_category'],
                f"{kb_item.category_info['item_name']}.md"
            ))
            tweet_data['kb_item_created_at'] = datetime.now().isoformat()
            
            return kb_item

        except Exception as e:
            error_msg = "Failed in create_knowledge_base_item for tweet {}: {}".format(tweet_id, e)
            logging.error(error_msg)
            logging.error("Available tweet data keys: {}".format(list(tweet_data.keys())))
            raise KnowledgeBaseItemCreationError(error_msg)

    async def process_media(self, tweet_data: Dict[str, Any]) -> None:
        """Process media content for a tweet."""
        try:
            if tweet_data.get('media_processed', False):
                logging.info("Media already processed, skipping...")
                return tweet_data

            media_paths = tweet_data.get('downloaded_media', [])
            if not media_paths:
                tweet_data['media_processed'] = True
                return tweet_data

            image_descriptions = []
            for media_path in media_paths:
                if not Path(media_path).exists():
                    raise ContentProcessingError(f"Media file not found: {media_path}")

                description = await interpret_image(
                    http_client=self.http_client,
                    image_path=Path(media_path),
                    vision_model=self.config.vision_model
                )
                if description:
                    image_descriptions.append(description)

            tweet_data['image_descriptions'] = image_descriptions
            tweet_data['media_processed'] = True
            return tweet_data

        except Exception as e:
            raise ContentProcessingError(f"Failed to process media content: {e}")

    async def process_all_tweets(
        self,
        config: Config,
        http_client: HTTPClient,
        state_manager: StateManager,
        stats: ProcessingStats,
        preferences: UserPreferences
    ) -> None:
        """Process all tweets in phases: caching, media, categories, KB items, and README."""
        try:
            # Import here to avoid circular import
            from knowledge_base_agent.markdown_writer import generate_root_readme
            tweets = await state_manager.get_all_tweets()
            unprocessed_tweets = await state_manager.get_unprocessed_tweets()
            total_tweets = len(unprocessed_tweets)
            
            # Phase 1: Cache tweets
            logging.info("=== Phase 1: Tweet Caching ===")
            for idx, tweet_id in enumerate(unprocessed_tweets, 1):
                logging.info(f"[{idx}/{total_tweets}] Caching tweet {tweet_id}")
                try:
                    await self.cache_tweets([tweet_id])
                    stats.success_count += 1
                    logging.info(f"✓ Cached tweet {tweet_id}")
                except Exception as e:
                    logging.error(f"✗ Failed to cache tweet {tweet_id}: {e}")
                    stats.error_count += 1
                    continue

            # Phase 2: Process media
            logging.info("=== Phase 2: Media Processing ===")
            media_items = await self._count_media_items()
            if media_items > 0:
                logging.info(f"Processing {media_items} media items...")
                tweets_with_media = await self.get_tweets_with_media()
                for tweet_id, tweet_data in tweets_with_media.items():
                    if not tweet_data.get('media_processed', False):
                        try:
                            updated_data = await process_media_content(tweet_data, http_client, config)
                            await state_manager.update_tweet_data(tweet_id, updated_data)
                            stats.media_processed += len(tweet_data.get('media', []))
                        except Exception as e:
                            logging.error(f"Failed to process media for tweet {tweet_id}: {e}")
                            stats.error_count += 1
                            continue

            # Phase 3: Process categories
            logging.info("=== Phase 3: Category Processing ===")
            for tweet_id, tweet_data in tweets.items():
                if not tweet_data.get('categories_processed', False):
                    try:
                        updated_data = await process_categories(tweet_id, tweet_data, config, http_client, state_manager)
                        await state_manager.update_tweet_data(tweet_id, updated_data)
                        stats.categories_processed += 1
                    except Exception as e:
                        logging.error(f"Failed to process categories for tweet {tweet_id}: {e}")
                        stats.error_count += 1
                        continue

            # Phase 4: Create knowledge base items
            logging.info("=== Phase 4: Knowledge Base Creation ===")
            for tweet_id, tweet_data in tweets.items():
                if not tweet_data.get('kb_item_created', False):
                    try:
                        kb_item = await self.create_knowledge_base_item(tweet_id, tweet_data, config)
                        # Update tweet data with KB creation status
                        tweet_data['kb_item_created'] = True
                        await state_manager.update_tweet_data(tweet_id, tweet_data)
                        
                        # Move to processed tweets if all phases are complete
                        if (tweet_data.get('media_processed', True) and 
                            tweet_data.get('categories_processed', False) and 
                            tweet_data.get('kb_item_created', False)):
                            await state_manager.mark_tweet_processed(tweet_id, tweet_data)
                            logging.info(f"Tweet {tweet_id} fully processed and moved to processed tweets")
                        
                        stats.processed_count += 1
                    except Exception as e:
                        logging.error(f"Failed to create KB item for tweet {tweet_id}: {e}")
                        stats.error_count += 1
                        continue

            # Phase 5: Generate README
            if preferences.regenerate_readme:
                logging.info("=== Phase 5: README Generation ===")
                try:
                    category_manager = CategoryManager(config)
                    await generate_root_readme(config.knowledge_base_dir, category_manager)
                    logging.info("✓ Successfully regenerated README")
                    stats.readme_generated = True
                except Exception as e:
                    logging.error(f"Failed to regenerate README: {e}")
                    stats.error_count += 1

        except Exception as e:
            logging.error(f"Failed to process all tweets: {str(e)}")
            raise ContentProcessingError(f"Failed to process all tweets: {str(e)}")

    async def cache_tweets(self, tweet_ids: List[str]) -> None:
        """Cache tweet data including media."""
        cached_tweets = await self.state_manager.get_all_tweets()
        
        for tweet_id in tweet_ids:
            # Skip if tweet is already fully cached
            if tweet_id in cached_tweets and cached_tweets[tweet_id].get('cache_complete', False):
                logging.debug(f"Tweet {tweet_id} already fully cached, skipping...")
                continue
            
            try:
                tweet_url = f"https://twitter.com/i/web/status/{tweet_id}"
                tweet_data = await fetch_tweet_data_playwright(tweet_url, self.config)
                
                if tweet_data:
                    # Download media if present
                    if 'media' in tweet_data:
                        media_dir = Path(self.config.media_cache_dir) / tweet_id
                        media_dir.mkdir(parents=True, exist_ok=True)
                        
                        media_paths = []
                        for idx, media_item in enumerate(tweet_data['media']):
                            if isinstance(media_item, str):
                                url = media_item
                            else:
                                url = media_item.get('url', '')
                                
                            if url:
                                media_path = media_dir / f"media_{idx}{Path(url).suffix}"
                                await self.http_client.download_media(url, media_path)
                                media_paths.append(str(media_path))
                        
                        tweet_data['downloaded_media'] = media_paths
                    
                    # Mark as fully cached
                    tweet_data['cache_complete'] = True
                    await self.state_manager.update_tweet_data(tweet_id, tweet_data)
                    logging.info(f"Successfully cached tweet {tweet_id} and its media")
                    
            except Exception as e:
                logging.error(f"Failed to cache tweet {tweet_id}: {e}")
                raise ContentProcessingError(f"Failed to cache tweet {tweet_id}: {e}")

    async def _count_media_items(self) -> int:
        """Count total number of media items to process."""
        tweets = await self.state_manager.get_all_tweets()
        count = 0
        for tweet_data in tweets.values():
            if not tweet_data.get('media_processed', False):
                count += len(tweet_data.get('media', []))
        return count

    async def get_tweets_with_media(self) -> Dict[str, Any]:
        """Get all tweets that have unprocessed media."""
        tweets = await self.state_manager.get_all_tweets()
        return {
            tweet_id: tweet_data 
            for tweet_id, tweet_data in tweets.items() 
            if tweet_data.get('media', []) and not tweet_data.get('media_processed', False)
        }
