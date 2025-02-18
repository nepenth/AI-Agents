"""
Tweet Processing Module

This module handles the processing of tweets into knowledge base items. It manages
the pipeline from raw tweet data through media analysis and content generation
to final knowledge base item creation.

The processing pipeline includes:
1. Media content analysis using vision models
2. Content categorization
3. Knowledge base item generation
4. State management for processed tweets
"""

from typing import List, Dict, Any, Optional, Set
import logging
import asyncio
from pathlib import Path
import datetime
import httpx
from asyncio import Semaphore
import time
import json
import aiofiles

from knowledge_base_agent.config import Config
from knowledge_base_agent.category_manager import CategoryManager
from knowledge_base_agent.exceptions import ProcessingError, AIError, StorageError, TweetProcessingError, ModelInferenceError, NetworkError, VisionModelError
from knowledge_base_agent.tweet_utils import parse_tweet_id_from_url
from knowledge_base_agent.cache_manager import get_cached_tweet, update_cache, save_cache, load_cache, CacheManager, cache_tweet_data
from knowledge_base_agent.content_processor import categorize_and_name_content, create_knowledge_base_entry
from knowledge_base_agent.markdown_writer import MarkdownWriter
from knowledge_base_agent.http_client import HTTPClient, OllamaClient
from knowledge_base_agent.file_utils import async_json_load, async_json_dump, async_read_text, async_write_text
from knowledge_base_agent.state_manager import StateManager
from knowledge_base_agent.types import TweetData, KnowledgeBaseItem, CategoryInfo
from knowledge_base_agent.progress import ProcessingStats
from knowledge_base_agent.playwright_fetcher import fetch_tweet_data_playwright

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

            # Get AI categorization (pass positional arguments only)
            main_cat, sub_cat, item_name = await categorize_and_name_content(
                config.ollama_url,
                combined_text,
                config.text_model,
                tweet_id,
                category_manager
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
        
        # Get categorization from AI (using positional arguments)
        main_cat, sub_cat, item_name = await categorize_and_name_content(
            config.ollama_url,
            combined_text,
            config.text_model,
            tweet_id,
            category_manager
        )

        # Write to knowledge base
        await write_to_knowledge_base(
            tweet_id=tweet_id,
            tweet_data=tweet_data,
            categories=(main_cat, sub_cat, item_name),
            config=config
        )

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
        await create_knowledge_base_entry(
            tweet_id=tweet_id,
            tweet_data=tweet_data,
            categories=categories,
            config=config
        )
    except Exception as e:
        raise StorageError(f"Failed to write to knowledge base: {e}")

class TweetProcessor:
    """
    Handles the processing of tweets into knowledge base items.
    
    The processor manages the complete pipeline from raw tweet data through
    media analysis and content generation to final knowledge base item creation.
    
    Attributes:
        config: Configuration instance containing processing settings
        state_manager: StateManager instance for tracking processed tweets
        ollama: OllamaClient instance for AI model interactions
    """

    def __init__(self, config: Config):
        self.config = config
        self.state_manager = StateManager(config)
        self.http_client = HTTPClient(config)
        self.ollama_client = OllamaClient(config)
        self.category_manager = CategoryManager(config)
        self.stats = ProcessingStats(start_time=datetime.datetime.now())
        self.cache_manager = CacheManager(config.tweet_cache_file)
        self.vision_model = None
        self.text_model = None
    
    async def process_tweets(self, tweet_ids: List[str]) -> None:
        """Process multiple tweets with state tracking."""
        for tweet_id in tweet_ids:
            if await self.state_manager.is_processed(tweet_id):
                logging.info(f"Skipping already processed tweet {tweet_id}")
                continue
                
            try:
                tweet_data = await self.state_manager.get_tweet(tweet_id)
                if tweet_data:
                    await self.process_single_tweet(tweet_id)
                    await self.state_manager.mark_tweet_processed(tweet_id)
            except Exception as e:
                logging.exception(f"Failed to process tweet {tweet_id}")
                raise

    async def process_single_tweet(self, tweet_id: str) -> KnowledgeBaseItem:
        """
        Process a single tweet into a knowledge base item.
        
        Args:
            tweet_id: ID of the tweet to process
            
        Returns:
            KnowledgeBaseItem: Generated knowledge base item
            
        Raises:
            ModelInferenceError: If AI model processing fails
            TweetProcessingError: If general processing fails
        """
        try:
            start_time = time.time()
            
            # Process media if present
            media_results = await self._process_media(tweet_id)
            if media_results:
                self.stats.media_processed += len(media_results)
            
            # Check cache
            if await self._check_cache(tweet_id):
                self.stats.cache_hits += 1
            else:
                self.stats.cache_misses += 1
            
            # Generate category information
            category_info = await self.categorize_content(tweet_id, media_results)
            
            # Generate knowledge base item
            kb_item = await self._generate_kb_item(tweet_id, media_results, category_info)
            
            self.stats.add_processing_time(time.time() - start_time)
            return kb_item
            
        except NetworkError:
            self.stats.network_errors += 1
            raise
        except Exception as e:
            logging.exception(f"Failed to process tweet {tweet_id}")
            raise TweetProcessingError(f"Failed to process tweet {tweet_id}") from e

    async def _process_media(self, tweet_id: str) -> List[Dict[str, Any]]:
        """
        Process media items using vision model.
        
        Args:
            tweet_id: ID of the tweet to process
            
        Returns:
            List[Dict[str, Any]]: Analysis results for each media item
            
        Raises:
            ModelInferenceError: If vision model processing fails
        """
        # Implementation details...

    async def _generate_kb_item(self, tweet_id: str, vision_results: List[str], text_model: str) -> Dict[str, Any]:
        # Implementation of _generate_kb_item method
        pass

    async def _save_kb_item(self, kb_item: Dict[str, Any], knowledge_base_dir: Path) -> None:
        # Implementation of _save_kb_item method
        pass

    async def load_cache(self) -> dict:
        """Load tweet cache asynchronously."""
        try:
            return await async_json_load(self.config.tweet_cache_file)
        except FileNotFoundError:
            return {}

    async def save_cache(self, cache_data: dict) -> None:
        """Save tweet cache asynchronously."""
        await async_json_dump(cache_data, self.config.tweet_cache_file)

    async def update_processed_tweets(self, tweet_id: str) -> None:
        """Update processed tweets list asynchronously."""
        processed = await async_json_load(self.config.processed_tweets_file)
        processed.append(tweet_id)
        await async_json_dump(processed, self.config.processed_tweets_file)

    async def fetch_tweet_media(self, media_url: str) -> bytes:
        """Fetch media with retry logic"""
        async with HTTPClient() as client:
            response = await client.get(media_url)
            return response.content

    async def process_media_item(self, media_url: str, vision_model: str) -> Dict[str, str]:
        """
        Process a single media item using the vision model.
        
        Args:
            media_url: URL of the media to process
            vision_model: Name of the vision model to use
            
        Returns:
            Dict containing vision model analysis results
            
        Raises:
            ModelInferenceError: If vision model processing fails
        """
        try:
            # Download media to temp location if needed
            media_path = self.config.data_processing_dir / f"temp_media_{int(time.time())}.jpg"
            await self.http_client.download_media(media_url, media_path)
            
            try:
                # Get image description from vision model using local file
                description = await self.ollama_client.generate(
                    model=vision_model,
                    prompt="Describe this image in detail, focusing on technical content and any visible text.",
                    images=[str(media_path)]  # Pass local file path as list
                )
                
                result = {
                    "media_url": media_url,
                    "description": description,
                    "model_used": vision_model
                }
                
                # Cleanup temp file
                if media_path.exists():
                    media_path.unlink()
                    
                return result
                
            except Exception as e:
                logging.error(f"Vision model processing failed for {media_url}: {e}")
                if media_path.exists():
                    media_path.unlink()
                raise ModelInferenceError(f"Failed to process media with vision model: {e}")
                
        except Exception as e:
            logging.error(f"Failed to process media item {media_url}: {e}")
            raise ModelInferenceError(f"Media processing failed: {e}")

    async def process_tweet_media(self, tweet_data: Dict[str, Any], vision_model: str) -> List[Dict[str, str]]:
        """
        Process all media items in a tweet using vision model.
        
        Args:
            tweet_data: Complete tweet data including media URLs
            vision_model: Name of vision model to use
            
        Returns:
            List of vision model results for each media item
        """
        try:
            media_items = tweet_data.get('media', [])
            results = []
            
            for media in media_items:
                result = await self.process_media_item(media, vision_model)
                results.append(result)
                
            return results
            
        except Exception as e:
            logging.error(f"Failed to process tweet media: {e}")
            raise ModelInferenceError(f"Media processing pipeline failed: {e}")

    async def generate_kb_entry(self, tweet_data: Dict[str, Any], media_results: List[Dict[str, Any]], 
                              category_info: Dict[str, str], model: str) -> Dict[str, Any]:
        """Generate KB entry using text model"""
        return await self.ollama_client.generate(
            model,
            self._build_kb_prompt(tweet_data, media_results, category_info)
        )

    async def categorize_content(
        self, 
        tweet_id: str,
        media_results: List[Dict[str, str]]
    ) -> CategoryInfo:
        """
        Determine appropriate category for content using the text model.
        
        Args:
            tweet_id: ID of the tweet to process
            media_results: Results from media analysis
            
        Returns:
            CategoryInfo containing category, subcategory, and name
            
        Raises:
            ModelInferenceError: If categorization fails
        """
        pass  # Implementation details...

    async def _check_cache(self, tweet_id: str) -> bool:
        # Implementation of _check_cache method
        pass

    async def get_cached_tweet_ids(self) -> Set[str]:
        """Get the set of cached tweet IDs."""
        try:
            if self.config.tweet_cache_file.exists():
                async with aiofiles.open(self.config.tweet_cache_file, 'r') as f:
                    content = await f.read()
                    cache = json.loads(content)
                    return set(cache.keys())
            return set()
        except Exception as e:
            logging.error(f"Failed to get cached tweet IDs: {e}")
            return set()

    async def cache_tweets(self, tweet_ids: List[str]) -> None:
        """Cache tweet data for the given tweet IDs using CacheManager."""
        try:
            logging.info(f"Caching data for {len(tweet_ids)} tweets")
            for tweet_id in tweet_ids:
                if not self.cache_manager.is_cached(tweet_id):
                    try:
                        await cache_tweet_data(tweet_id, self.config, self.cache_manager._cache, self.http_client)
                        logging.debug(f"Cached tweet {tweet_id}")
                        await self.cache_manager.save_cache()
                    except Exception as e:
                        logging.error(f"Failed to cache tweet {tweet_id}: {e}")
                        raise
            logging.info("Tweet caching completed")
        except Exception as e:
            logging.error(f"Tweet caching failed: {e}")
            raise TweetProcessingError(f"Failed to cache tweets: {e}")

    async def process_media(self, tweet_data: Dict[str, Any]) -> List[Dict[str, str]]:
        """Process media items in a tweet."""
        results = []
        
        # Get tweet ID from the data or cache key
        tweet_id = str(tweet_data.get('id', ''))  # Convert to string in case it's numeric
        if not tweet_id:
            # Try to find the tweet ID from the media paths
            if 'downloaded_media' in tweet_data:
                first_media = tweet_data['downloaded_media'][0]
                # Extract ID from path like "data/media_cache/1234567890/media_0"
                try:
                    tweet_id = first_media.split('/')[2]  # Get the ID from the path
                except (IndexError, AttributeError):
                    logging.error(f"Could not extract tweet ID from media path: {first_media}")
        
        if not tweet_id:
            logging.error("No tweet ID found in data:", tweet_data)
            return results
        
        logging.info(f"Processing media for tweet {tweet_id}")
        
        if 'media' in tweet_data:
            downloaded_media = tweet_data.get('downloaded_media', [])
            media_items = tweet_data.get('media', [])
            
            logging.info(f"Found {len(downloaded_media)} media items for tweet {tweet_id}")
            
            if not downloaded_media:
                logging.warning(f"No cached media found for tweet {tweet_id}")
                return results
            
            for idx, (media_item, cached_path) in enumerate(zip(media_items, downloaded_media)):
                try:
                    url = media_item if isinstance(media_item, str) else media_item.get('url', '')
                    
                    if not Path(cached_path).exists():
                        logging.warning(f"Cached media not found at {cached_path}, skipping")
                        continue
                    
                    logging.info(f"Processing media {idx+1}/{len(downloaded_media)} for tweet {tweet_id}")
                    logging.debug(f"Using cached file: {cached_path}")
                    
                    try:
                        description = await self.ollama_client.generate(
                            model=self.config.vision_model,
                            prompt="Describe this image in detail, focusing on technical content and any visible text.",
                            images=[str(cached_path)]
                        )
                        
                        if description:
                            result = {
                                'url': url,
                                'cached_path': cached_path,
                                'description': description
                            }
                            results.append(result)
                            
                            # Update tweet cache with the new description
                            if 'media_analysis' not in tweet_data:
                                tweet_data['media_analysis'] = []
                            tweet_data['media_analysis'].append(result)
                            
                            # Save updated cache
                            await self.cache_manager.update_cache(tweet_id, tweet_data)
                            
                            logging.info(f"Successfully processed media {idx+1} for tweet {tweet_id}")
                            logging.debug(f"Description: {description[:100]}...")
                        else:
                            logging.warning(f"Empty description returned for {cached_path}")
                            
                    except Exception as e:
                        logging.error(f"Vision model failed for {cached_path}: {e}")
                        continue
                    
                except Exception as e:
                    logging.error(f"Failed to process media item {idx+1} for tweet {tweet_id}: {e}")
                    continue
                
        return results

    async def _process_media_with_vision(self, image_url: str) -> str:
        """Process media with vision model."""
        try:
            # Download image to temporary file
            temp_path = self.config.data_processing_dir / f"temp_image_{int(time.time())}.jpg"
            await self.http_client.download_media(image_url, temp_path)
            
            # Process with vision model
            async with OllamaClient(config=self.config) as ollama:
                response = await ollama.generate(
                    model=self.config.vision_model,
                    prompt="Describe this image in detail, focusing on any text content, technical details, or programming concepts shown.",
                    images=[str(temp_path)]
                )
                
            # Cleanup temp file
            temp_path.unlink()
            return response
            
        except Exception as e:
            logging.error(f"Vision model processing failed for {image_url}: {e}")
            raise VisionModelError(f"Failed to process media with vision model: {e}")

    async def process_tweet(self, tweet_id: str) -> Dict[str, Any]:
        """Process a single tweet through the pipeline."""
        try:
            # Get cached tweet data
            cache = await self.cache_manager.load_cache()  # Load the entire cache
            tweet_data = cache.get(tweet_id)  # Get specific tweet data
            
            if not tweet_data:
                logging.error(f"No cached data found for tweet {tweet_id}")
                return None
            
            # Process media if present
            media_results = []
            if tweet_data.get('media'):
                try:
                    media_results = await self.process_media(tweet_data)
                    tweet_data['media_analysis'] = media_results
                except Exception as e:
                    logging.error(f"Failed to process media for tweet {tweet_id}: {e}")
                    # Continue processing even if media fails
            
            # Get content categorization
            try:
                category_info = await self.categorize_content(tweet_id, media_results)
                
                # Generate KB entry
                kb_item = await self.generate_kb_entry(tweet_data, media_results, category_info)
                
                # Save KB entry
                await self.save_kb_entry(kb_item)
                
                # Mark as processed only if everything succeeded
                await self.mark_processed(tweet_id)
                
                return tweet_data
                
            except Exception as e:
                logging.error(f"Failed to process tweet content for {tweet_id}: {e}")
                raise
            
        except Exception as e:
            logging.error(f"Failed to process tweet {tweet_id}: {e}")
            raise TweetProcessingError(f"Failed to process tweet: {e}")

    async def get_tweets_with_media(self) -> Dict[str, Dict]:
        """Get all cached tweets that have media."""
        tweets_with_media = {}
        cache = await self.cache_manager.load_cache()  # Use the public method
        for tweet_id, tweet_data in cache.items():
            if tweet_data.get('media'):
                tweets_with_media[tweet_id] = tweet_data
        return tweets_with_media

class BookmarksProcessor:
    async def load_bookmarks(self) -> list[str]:
        """Load bookmarks asynchronously."""
        content = await async_read_text(self.config.bookmarks_file)
        return [url.strip() for url in content.splitlines() if url.strip()]

    async def save_bookmarks(self, urls: list[str]) -> None:
        """Save bookmarks asynchronously."""
        content = '\n'.join(urls)
        await async_write_text(content, self.config.bookmarks_file)

class ProcessingPipeline:
    def __init__(self, config: Config):
        self.config = config
        # Limit concurrent Ollama requests
        self.ollama_semaphore = Semaphore(3)
        self.tweet_processor = TweetProcessor(config)
        self.category_manager = CategoryManager(config)
    
    async def process_bookmarks(self, bookmark_urls: List[str]) -> None:
        """Main processing pipeline coordinator."""
        for url in bookmark_urls:
            try:
                tweet_data = await self.fetch_and_cache_tweet(url)
                if tweet_data:
                    await self.process_single_tweet(tweet_data)
            except Exception as e:
                logging.exception(f"Failed processing bookmark {url}")
                continue

    async def fetch_and_cache_tweet(self, url: str) -> Optional[Dict[str, Any]]:
        """Step 1: Fetch and cache tweet data."""
        try:
            tweet_data = await self.tweet_processor.fetch_tweet(url)
            await self.tweet_processor.cache_tweet(tweet_data)
            return tweet_data
        except Exception as e:
            logging.exception(f"Failed to fetch/cache tweet: {url}")
            return None

    async def process_single_tweet(self, tweet_data: Dict[str, Any]) -> None:
        """Step 2: Process a single tweet through the pipeline."""
        tweet_id = tweet_data.get('id', 'unknown')
        try:
            # Step 2a: Process media with vision model
            media_results = await self.process_media(tweet_data)
            
            # Step 2b: Categorize content
            category_info = await self.categorize_content(tweet_id, media_results)
            
            # Step 2c: Generate KB entry
            kb_entry = await self.generate_kb_entry(tweet_data, media_results, category_info)
            
            # Step 2d: Save KB entry
            await self.save_kb_entry(kb_entry)
            
            # Mark as processed
            await self.tweet_processor.mark_processed(tweet_id)
            
        except Exception as e:
            logging.exception(f"Failed to process tweet {tweet_id}")
            raise TweetProcessingError(f"Pipeline failed for tweet {tweet_id}") from e

    async def process_media(self, tweet_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Step 2a: Process media with vision model."""
        async with self.ollama_semaphore:
            try:
                # Process all media items with vision model
                media_results = await self.tweet_processor.process_tweet_media(
                    tweet_data,
                    self.config.vision_model
                )
                
                # Cache the vision model results
                tweet_data['media_analysis'] = media_results
                
                return media_results
                
            except Exception as e:
                logging.error(f"Media processing failed: {e}")
                raise ModelInferenceError("Vision model processing failed") from e

    async def categorize_content(
        self, 
        tweet_id: str,
        media_results: List[Dict[str, str]]
    ) -> CategoryInfo:
        """Step 2b: Determine content categories."""
        async with self.ollama_semaphore:
            try:
                return await self.tweet_processor.categorize_content(
                    tweet_id,
                    media_results
                )
            except Exception as e:
                raise ModelInferenceError("Content categorization failed") from e

    async def generate_kb_entry(self, tweet_data: Dict[str, Any], media_results: List[Dict[str, str]], 
                              category_info: CategoryInfo) -> KnowledgeBaseItem:
        """Step 2c: Generate knowledge base entry."""
        async with self.ollama_semaphore:
            try:
                return await self.tweet_processor.generate_kb_entry(
                    tweet_data,
                    media_results,
                    category_info,
                    self.config.text_model
                )
            except Exception as e:
                raise ModelInferenceError("KB entry generation failed") from e

    async def save_kb_entry(self, kb_entry: Dict[str, Any]) -> None:
        """Step 2d: Save knowledge base entry."""
        try:
            await self.category_manager.update_categories(kb_entry['category_info'])
        except Exception as e:
            raise TweetProcessingError("Failed to save KB entry") from e

async def cache_tweet_data(tweet_id: str, config: Config, cache: Dict, http_client: HTTPClient) -> None:
    """Cache tweet data including media."""
    try:
        tweet_url = f"https://twitter.com/i/web/status/{tweet_id}"
        tweet_data = await fetch_tweet_data_playwright(tweet_url, config)
        if not tweet_data:
            raise ValueError(f"No data returned for tweet {tweet_id}")
            
        # Download any media if present
        if 'media' in tweet_data:
            media_dir = Path(config.media_cache_dir) / tweet_id
            media_dir.mkdir(parents=True, exist_ok=True)
            
            media_paths = []
            for idx, media_item in enumerate(tweet_data['media']):
                if isinstance(media_item, str):
                    url = media_item
                else:
                    url = media_item.get('url', '')
                    
                if url:
                    media_path = media_dir / f"media_{idx}{Path(url).suffix}"
                    await http_client.download_media(url, media_path)
                    media_paths.append(str(media_path))
                
            tweet_data['downloaded_media'] = media_paths
            
        # Update cache
        cache[tweet_id] = tweet_data
        logging.info(f"Successfully cached tweet {tweet_id}")
        
    except Exception as e:
        logging.error(f"Failed to cache tweet {tweet_id}: {e}")
        raise 