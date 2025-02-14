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

from typing import List, Dict, Any, Optional
import logging
import asyncio
from pathlib import Path
import datetime
import httpx
from asyncio import Semaphore

from knowledge_base_agent.config import Config
from knowledge_base_agent.category_manager import CategoryManager
from knowledge_base_agent.exceptions import ProcessingError, AIError, StorageError, TweetProcessingError, ModelInferenceError
from knowledge_base_agent.tweet_utils import parse_tweet_id_from_url
from knowledge_base_agent.cache_manager import get_cached_tweet, update_cache, save_cache, load_cache
from knowledge_base_agent.content_processor import categorize_and_name_content, create_knowledge_base_entry
from knowledge_base_agent.markdown_writer import MarkdownWriter, MarkdownGenerator
from knowledge_base_agent.http_client import HTTPClient, OllamaClient
from knowledge_base_agent.file_utils import async_json_load, async_json_dump, async_read_text, async_write_text
from knowledge_base_agent.state_manager import StateManager
from knowledge_base_agent.types import TweetData, KnowledgeBaseItem, CategoryInfo

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
        self.markdown_gen = MarkdownGenerator(config)
    
    async def process_tweets(self, tweets: List[Dict[str, Any]]) -> None:
        """Process multiple tweets with state tracking."""
        for tweet in tweets:
            tweet_id = tweet['id']
            if await self.state_manager.is_processed(tweet_id):
                logging.info(f"Skipping already processed tweet {tweet_id}")
                continue
                
            try:
                await self.process_single_tweet(tweet)
                await self.state_manager.mark_tweet_processed(tweet_id)
            except Exception as e:
                logging.exception(f"Failed to process tweet {tweet_id}")
                raise

    async def process_single_tweet(self, tweet: TweetData) -> KnowledgeBaseItem:
        """
        Process a single tweet into a knowledge base item.
        
        Args:
            tweet: TweetData object containing tweet information
            
        Returns:
            KnowledgeBaseItem: Generated knowledge base item
            
        Raises:
            ModelInferenceError: If AI model processing fails
            TweetProcessingError: If general processing fails
        """
        try:
            # Process media if present
            media_results = await self._process_media(tweet['media'])
            
            # Generate category information
            category_info = await self._categorize_content(tweet, media_results)
            
            # Generate knowledge base item
            return await self._generate_kb_item(tweet, media_results, category_info)
            
        except Exception as e:
            logging.exception(f"Failed to process tweet {tweet['id']}")
            raise TweetProcessingError(f"Failed to process tweet {tweet['id']}") from e

    async def _process_media(self, media_items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Process media items using vision model.
        
        Args:
            media_items: List of media items from tweet
            
        Returns:
            List[Dict[str, Any]]: Analysis results for each media item
            
        Raises:
            ModelInferenceError: If vision model processing fails
        """
        # Implementation details...

    async def _generate_kb_item(self, tweet_data: dict, vision_results: List[str], text_model: str) -> Dict[str, Any]:
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

    async def process_media_item(self, media: Dict[str, Any], model: str) -> Dict[str, Any]:
        """Process media with vision model"""
        media_data = await self.fetch_tweet_media(media['url'])
        return await self.ollama_client.analyze_image(
            model,
            media_data,
            "Describe this image in detail"
        )

    async def generate_kb_entry(self, tweet_data: Dict[str, Any], media_results: List[Dict[str, Any]], 
                              category_info: Dict[str, str], model: str) -> Dict[str, Any]:
        """Generate KB entry using text model"""
        return await self.ollama_client.generate(
            model,
            self._build_kb_prompt(tweet_data, media_results, category_info)
        )

    async def categorize_content(
        self, 
        tweet_data: Dict[str, Any],
        media_results: List[Dict[str, str]]
    ) -> CategoryInfo:
        """
        Determine appropriate category for content using the text model.
        
        Args:
            tweet_data: Complete tweet information
            media_results: Results from media analysis
            
        Returns:
            CategoryInfo containing category, subcategory, and name
            
        Raises:
            ModelInferenceError: If categorization fails
        """
        pass  # Implementation details...

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
        self.markdown_gen = MarkdownGenerator(config)
    
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
            category_info = await self.categorize_content(tweet_data, media_results)
            
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
                media_items = tweet_data.get('media', [])
                results = []
                for media in media_items:
                    vision_result = await self.tweet_processor.process_media_item(
                        media,
                        self.config.vision_model
                    )
                    results.append(vision_result)
                return results
            except Exception as e:
                raise ModelInferenceError("Vision model processing failed") from e

    async def categorize_content(
        self, 
        tweet_data: Dict[str, Any], 
        media_results: List[Dict[str, str]]
    ) -> CategoryInfo:
        """Step 2b: Determine content categories."""
        async with self.ollama_semaphore:
            try:
                return await self.tweet_processor.categorize_content(
                    tweet_data,
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
            await self.markdown_gen.write_kb_item(kb_entry)
            await self.category_manager.update_categories(kb_entry['category_info'])
        except Exception as e:
            raise TweetProcessingError("Failed to save KB entry") from e 