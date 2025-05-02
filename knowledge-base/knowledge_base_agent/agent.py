"""
Main agent module coordinating knowledge base operations.

This module contains the core logic for the Knowledge Base Agent, which automates the process of fetching, processing, categorizing, and generating content for a structured knowledge base. It integrates various components to ensure seamless operation and data management.
"""

import logging
from typing import Set, List, Dict, Any
from pathlib import Path
import asyncio
from datetime import datetime, timezone
import time
import aiofiles
from flask_socketio import SocketIO

from knowledge_base_agent.config import Config
from knowledge_base_agent.exceptions import AgentError, MarkdownGenerationError
from knowledge_base_agent.state_manager import StateManager
from knowledge_base_agent.git_helper import GitSyncHandler
from knowledge_base_agent.fetch_bookmarks import BookmarksFetcher
from knowledge_base_agent.markdown_writer import MarkdownWriter
from knowledge_base_agent.readme_generator import generate_root_readme, generate_static_root_readme
from knowledge_base_agent.category_manager import CategoryManager
from knowledge_base_agent.types import TweetData, KnowledgeBaseItem
from knowledge_base_agent.prompts import UserPreferences
from knowledge_base_agent.progress import ProcessingStats
from knowledge_base_agent.content_processor import ContentProcessingError
from knowledge_base_agent.tweet_utils import parse_tweet_id_from_url
from knowledge_base_agent.file_utils import async_json_load
from knowledge_base_agent.http_client import HTTPClient
from knowledge_base_agent.content_processor import ContentProcessor
from knowledge_base_agent.tweet_cacher import cache_tweets, TweetCacheValidator

# Global stop flag for web frontend
stop_flag = False

# SocketIO instance (will be set by web.py)
socketio = None

def setup_logging(config: Config) -> None:
    """
    Configure logging with different levels for file and console.

    This function sets up logging handlers for both file and console output, with different
    formatting and filtering to ensure relevant information is logged appropriately.

    Args:
        config (Config): Configuration object containing logging settings, such as log file path.
    """
    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    
    file_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    console_formatter = logging.Formatter('%(message)s')

    file_handler = logging.FileHandler(config.log_file)
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(file_formatter)

    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(console_formatter)
    
    class TweetProgressFilter(logging.Filter):
        def filter(self, record):
            msg = record.getMessage()
            return not any(x in msg for x in [
                'Caching data for',
                'Tweet caching completed',
                '✓ Cached tweet'
            ])
    
    console_handler.addFilter(TweetProgressFilter())

    root_logger.setLevel(logging.DEBUG)
    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)

    logging.getLogger('httpx').setLevel(logging.WARNING)
    logging.getLogger('playwright').setLevel(logging.WARNING)

class KnowledgeBaseAgent:
    """
    Main agent coordinating knowledge base operations.

    The KnowledgeBaseAgent class is the central component of the knowledge base system. It orchestrates
    the fetching of content from various sources, processes and categorizes this content, manages state,
    and generates structured outputs. It integrates with other modules to ensure a seamless workflow.

    Attributes:
        config (Config): Configuration object for the agent.
        http_client (HTTPClient): Client for making HTTP requests.
        state_manager (StateManager): Manages the state of processed and unprocessed content.
        category_manager (CategoryManager): Handles content categorization.
        content_processor (ContentProcessor): Processes content for the knowledge base.
        _processing_lock (asyncio.Lock): Lock to prevent concurrent processing issues.
        git_handler (GitSyncHandler): Handles synchronization with Git repositories.
        stats (ProcessingStats): Tracks processing statistics.
        _initialized (bool): Flag indicating if the agent has been initialized.
    """
    
    def __init__(self, config: Config):
        """
        Initialize the agent with configuration.

        Args:
            config (Config): Configuration object containing settings for the agent.
        """
        self.config = config
        self.http_client = HTTPClient(config)
        self.state_manager = StateManager(config)
        self.category_manager = CategoryManager(config, http_client=self.http_client)
        self.content_processor = ContentProcessor(config, http_client=self.http_client, state_manager=self.state_manager)
        self._processing_lock = asyncio.Lock()
        self.git_handler = GitSyncHandler(config)
        self.stats = ProcessingStats(start_time=datetime.now())
        self._initialized = False
        # Add initialization for tweet caching/processing
        self.tweet_processor = TweetCacheValidator(
            tweet_cache_path=Path(config.tweet_cache_file),
            media_cache_dir=Path(config.media_cache_dir),
            kb_base_dir=Path(config.knowledge_base_dir)
        )
        logging.info("KnowledgeBaseAgent initialized")

    async def initialize(self) -> None:
        """
        Initialize all components and ensure directory structure.

        This method sets up the necessary directories and initializes the state and category managers.
        It ensures that the agent is ready to process content.

        Raises:
            AgentError: If initialization fails due to directory creation or component setup issues.
        """
        try:
            logging.info("Creating required directories...")
            try:
                self.config.knowledge_base_dir.mkdir(parents=True, exist_ok=True)
                self.config.data_processing_dir.mkdir(parents=True, exist_ok=True)
                self.config.media_cache_dir.mkdir(parents=True, exist_ok=True)
            except Exception as e:
                logging.exception("Failed to create directories")
                raise AgentError(f"Failed to create directories: {e}")
            
            logging.info("Initializing state manager...")
            try:
                await self.state_manager.initialize()
            except Exception as e:
                logging.exception("State manager initialization failed")
                raise AgentError(f"State manager initialization failed: {e}")
            
            logging.info("Initializing category manager...")
            try:
                await self.category_manager.initialize()
            except Exception as e:
                logging.exception("Category manager initialization failed")
                raise AgentError(f"Category manager initialization failed: {e}")
            
            self._initialized = True
            logging.info("Agent initialization complete")
        except Exception as e:
            logging.exception(f"Agent initialization failed: {str(e)}")
            raise AgentError(f"Failed to initialize agent: {str(e)}") from e

    async def process_bookmarks(self) -> None:
        """
        Process bookmarks using the phased approach.

        This method fetches bookmarks, adds new tweet IDs to the unprocessed list,
        and processes them through the standard phased approach in ContentProcessor.

        Raises:
            AgentError: If bookmark fetching or processing fails.
        """
        global stop_flag
        try:
            logging.info("Starting bookmark processing")
            bookmark_fetcher = BookmarksFetcher(self.config)
            try:
                await bookmark_fetcher.initialize()
                bookmarks = await bookmark_fetcher.fetch_bookmarks()
                logging.info(f"Fetched {len(bookmarks)} bookmarks")
                
                new_tweet_ids = []
                for bookmark in bookmarks:
                    if stop_flag:
                        logging.info("Stopping bookmark processing due to stop request")
                        break
                    tweet_id = parse_tweet_id_from_url(bookmark)
                    if not tweet_id:
                        logging.warning(f"Invalid tweet URL in bookmark: {bookmark}")
                        continue
                    
                    if not await self.state_manager.is_tweet_processed(tweet_id):
                        if tweet_id not in self.state_manager.unprocessed_tweets:
                            self.state_manager.unprocessed_tweets.append(tweet_id)
                            new_tweet_ids.append(tweet_id)
                            logging.info(f"Added tweet {tweet_id} from bookmark to unprocessed list")
                        else:
                            logging.info(f"Tweet {tweet_id} from bookmark already in unprocessed list")
                    else:
                        logging.info(f"Tweet {tweet_id} from bookmark already processed, skipping")
                
                if new_tweet_ids:
                    await self.state_manager.save_unprocessed()
                    logging.info(f"Processing {len(new_tweet_ids)} new tweets from bookmarks")
                    await self.content_processor.process_all_tweets(
                        preferences=UserPreferences(update_bookmarks=True, regenerate_readme=False),
                        unprocessed_tweets=new_tweet_ids,
                        total_tweets=len(new_tweet_ids),
                        stats=self.stats,
                        category_manager=self.category_manager
                    )
                    logging.info(f"Completed phased processing of {len(new_tweet_ids)} tweets from bookmarks")
                else:
                    logging.info("No new tweets to process from bookmarks")
                
            except Exception as e:
                logging.exception("Bookmark fetching failed")
                raise AgentError(f"Failed to fetch bookmarks: {str(e)}")
            finally:
                await bookmark_fetcher.cleanup()
        except Exception as e:
            logging.exception("Bookmark processing failed")
            raise AgentError(f"Failed to process bookmarks: {str(e)}")

    async def update_indexes(self) -> None:
        """
        Update category indexes.

        This method iterates through all categories to update their indexes, ensuring the knowledge base
        structure is current. It respects the global stop flag for interruption.

        Raises:
            AgentError: If index update fails.
        """
        global stop_flag
        try:
            if stop_flag:
                logging.info("Skipping index update due to stop request")
                return
            logging.info("Starting index update")
            categories = self.category_manager.get_all_categories()
            for category in categories:
                if stop_flag:
                    logging.info("Stopping index update due to stop request")
                    break
                try:
                    pass  # Category-specific processing
                except Exception as e:
                    logging.error(f"Failed to process category {category}: {e}")
            logging.info("Index update completed")
        except Exception as e:
            logging.error(f"Index update failed: {e}")
            raise AgentError("Failed to update indexes") from e

    async def sync_changes(self) -> None:
        """
        Sync changes to GitHub repository.

        This method synchronizes the local knowledge base changes to a remote GitHub repository.
        It respects the global stop flag for interruption.

        Raises:
            AgentError: If synchronization fails.
        """
        global stop_flag
        try:
            if stop_flag:
                logging.info("Skipping GitHub sync due to stop request")
                return
            logging.info("Starting GitHub sync...")
            await self.git_handler.sync_to_github("Update knowledge base content")
            logging.info("GitHub sync completed successfully")
        except Exception as e:
            logging.error(f"GitHub sync failed: {str(e)}")
            raise AgentError("Failed to sync changes to GitHub") from e

    async def cleanup(self) -> None:
        """
        Cleanup temporary files and resources.

        This method removes temporary files created during processing to maintain a clean environment.

        Raises:
            None: Exceptions are logged but not raised to prevent disruption.
        """
        try:
            temp_files = list(self.config.data_processing_dir.glob("*.temp"))
            for temp_file in temp_files:
                temp_file.unlink()
            logging.info("Cleanup completed")
        except Exception as e:
            logging.warning(f"Cleanup failed: {e}")

    async def run(self, preferences: UserPreferences) -> None:
        """
        Run the agent with the given preferences.

        This is the main execution method for the agent, orchestrating the full workflow from initialization,
        content processing, README regeneration, to Git synchronization. It updates progress via SocketIO if available.

        Args:
            preferences (UserPreferences): User-defined preferences for processing.

        Raises:
            RuntimeError: If processing encounters errors, a summary error is raised at the end.
            Exception: Any unhandled exceptions during execution are logged and re-raised.
        """
        global stop_flag, socketio
        try:
            stats = ProcessingStats(start_time=datetime.now())
            
            logging.info("1. Initializing state and checking for new content...")
            from knowledge_base_agent.web import app  # Import app here to avoid circular import
            with app.app_context():  # Ensure DB operations are in context
                await self.state_manager.initialize()
            stats.validation_count = getattr(self.state_manager, 'validation_fixes', 0)
            
            unprocessed_tweets = await self.state_manager.get_unprocessed_tweets()
            has_work_to_do = bool(unprocessed_tweets)
            total_tweets = len(unprocessed_tweets)
            
            if preferences.update_bookmarks and not stop_flag:
                logging.info("2. Processing bookmarks for new tweets...")
                with app.app_context():  # Ensure DB operations are in context
                    await self.process_bookmarks()
                    await self.state_manager.update_from_bookmarks()
                unprocessed_tweets = await self.state_manager.get_unprocessed_tweets()
                total_tweets = len(unprocessed_tweets)
            
            if has_work_to_do and not stop_flag:
                logging.info(f"Processing {total_tweets} tweets...")
                with app.app_context():  # Ensure DB operations are in context
                    await self.content_processor.process_all_tweets(
                        preferences,
                        unprocessed_tweets,
                        stats.validation_count,
                        stats,
                        self.category_manager
                    )
                # Emit progress after processing
                if socketio:
                    progress = {
                        'processed': stats.processed_count,
                        'total': total_tweets + stats.processed_count,
                        'errors': stats.error_count
                    }
                    socketio.emit('progress', progress)
            else:
                logging.info("No tweets to process")
            
            if not stop_flag:
                logging.info("3. Regenerating README...")
                await self.regenerate_readme()
                self.stats.readme_generated = True
                if socketio:
                    socketio.emit('progress', {'processed': stats.processed_count, 'total': total_tweets + stats.processed_count, 'errors': stats.error_count})
            
            if self.config.git_enabled and not stop_flag:
                logging.info("4. Syncing to GitHub...")
                await self.git_handler.sync_to_github("Update knowledge base with new items and README")
                if socketio:
                    socketio.emit('progress', {'processed': stats.processed_count, 'total': total_tweets + stats.processed_count, 'errors': stats.error_count})
            
            if not stop_flag:
                logging.info("Finalizing state...")
                await self.state_manager.cleanup_unprocessed_tweets()
            
            logging.info("\n=== Processing Summary ===")
            logging.info(f"Cache validation fixes: {stats.validation_count}")
            logging.info(f"Total tweets processed: {stats.processed_count}")
            logging.info(f"Media items processed: {stats.media_processed}")
            logging.info(f"Categories processed: {stats.categories_processed}")
            logging.info(f"README generated: {'Yes' if self.stats.readme_generated else 'No'}")
            logging.info(f"Errors encountered: {stats.error_count}")
            
            stats.save_report(Path("data/processing_stats.json"))
            
            processing_errors = stats.error_count
            if processing_errors > 0:
                if stats.processed_count < total_tweets:
                    logging.error(f"Agent run completed with {processing_errors} errors during processing phases.")
                    raise RuntimeError(f"Failed to fully process {processing_errors} tweets. Check logs for details.")
                else:
                    logging.warning(f"Agent run completed, but encountered {processing_errors} non-critical errors (e.g., initial caching). Check logs.")
            else:
                logging.info("Agent run completed successfully.")
                
        except Exception as e:
            logging.error(f"Agent run failed: {str(e)}", exc_info=True)
            raise
        finally:
            logging.info(f"Final state: {len(self.state_manager.unprocessed_tweets)} unprocessed, {len(self.state_manager.processed_tweets)} processed")
            with app.app_context():  # Ensure cleanup is in context
                await self.cleanup()

    async def process_tweet(self, tweet_url: str) -> None:
        """
        Process a single tweet using the phased approach in ContentProcessor.

        This method extracts the tweet ID from the URL, ensures the tweet data is cached,
        and adds it to the unprocessed list for processing through the standard phased approach.

        Args:
            tweet_url (str): The URL or ID of the tweet to process.

        Raises:
            ValueError: If the tweet URL is invalid.
            ContentProcessingError: If tweet data fetching or processing fails.
        """
        global stop_flag
        if stop_flag:
            logging.info(f"Skipping tweet {tweet_url} due to stop request")
            return
        try:
            if tweet_url.isdigit():
                tweet_url = f"https://twitter.com/i/web/status/{tweet_url}"
            
            tweet_id = parse_tweet_id_from_url(tweet_url)
            if not tweet_id:
                raise ValueError(f"Invalid tweet URL: {tweet_url}")
            
            from knowledge_base_agent.web import app  # Import app here to avoid circular import
            with app.app_context():  # Ensure DB operations are in context
                tweet_data = await self.state_manager.get_tweet(tweet_id)
                if not tweet_data:
                    logging.info(f"Tweet {tweet_id} not found in cache, fetching data...")
                    await cache_tweets([tweet_id], self.config, self.http_client, self.state_manager)
                    tweet_data = await self.state_manager.get_tweet(tweet_id)
                    if not tweet_data:
                        raise ContentProcessingError(f"Failed to fetch and cache tweet {tweet_id}")
            
            # Add to unprocessed list if not already processed
            if not await self.state_manager.is_tweet_processed(tweet_id):
                if tweet_id not in self.state_manager.unprocessed_tweets:
                    self.state_manager.unprocessed_tweets.append(tweet_id)
                    await self.state_manager.save_unprocessed()
                    logging.info(f"Added tweet {tweet_id} to unprocessed list for phased processing")
                else:
                    logging.info(f"Tweet {tweet_id} already in unprocessed list, skipping addition")
            else:
                logging.info(f"Tweet {tweet_id} already processed, skipping")
                return
            
            # Trigger phased processing for this tweet
            unprocessed_tweets = [tweet_id]
            await self.content_processor.process_all_tweets(
                preferences=UserPreferences(update_bookmarks=False, regenerate_readme=False),
                unprocessed_tweets=unprocessed_tweets,
                total_tweets=1,
                stats=self.stats,
                category_manager=self.category_manager
            )
            
            # Verify processing completion
            if await self._verify_kb_item_created(tweet_id):
                await self.state_manager.mark_tweet_processed(tweet_id, tweet_data)
                logging.info(f"Successfully processed tweet {tweet_id} through phased approach")
                
                # Data for database storage will be handled elsewhere
                kb_item_path = tweet_data.get('kb_item_path')
                if kb_item_path:
                    logging.info(f"Processed tweet {tweet_id} with KB item path {kb_item_path}")
            else:
                raise ContentProcessingError(f"Failed to create knowledge base item for tweet {tweet_id}")
            
        except Exception as e:
            logging.error(f"Failed to process tweet {tweet_url}: {e}")
            raise

    async def regenerate_readme(self) -> None:
        """
        Regenerate the root README file.

        This method regenerates the main README file for the knowledge base, attempting to create
        an intelligent version first, falling back to a static version if that fails.

        Raises:
            MarkdownGenerationError: If README regeneration fails completely.
        """
        global stop_flag
        if stop_flag:
            logging.info("Skipping README regeneration due to stop request")
            return
        try:
            logging.info("Starting README regeneration")
            readme_path = self.config.knowledge_base_dir / "README.md"
            
            try:
                await generate_root_readme(
                    self.config.knowledge_base_dir,
                    self.category_manager,
                    self.http_client,
                    self.config
                )
                logging.info("Generated intelligent README")
            except Exception as e:
                logging.warning(f"Intelligent README generation failed: {e}")
                content = await generate_static_root_readme(
                    self.config.knowledge_base_dir,
                    self.category_manager
                )
                async with aiofiles.open(readme_path, 'w', encoding='utf-8') as f:
                    await f.write(content)
                logging.info("Generated static README as fallback")
                
        except Exception as e:
            logging.error(f"README regeneration failed: {e}")
            raise MarkdownGenerationError(f"Failed to regenerate README: {e}")

    async def _verify_tweet_cached(self, tweet_id: str) -> bool:
        """
        Verify that a tweet exists in the cache.

        Args:
            tweet_id (str): The ID of the tweet to verify.

        Returns:
            bool: True if the tweet is in the cache, False otherwise.
        """
        try:
            cache_file = Path(self.config.tweet_cache_file)
            if not cache_file.exists():
                logging.error("Tweet cache file does not exist")
                return False
            
            cache_data = await async_json_load(cache_file)
            return tweet_id in cache_data
            
        except Exception as e:
            logging.error(f"Error verifying tweet cache for {tweet_id}: {e}")
            return False

    async def _verify_kb_item_created(self, tweet_id: str) -> bool:
        """
        Verify that a knowledge base item was created for the tweet.

        Args:
            tweet_id (str): The ID of the tweet to verify.

        Returns:
            bool: True if a knowledge base item exists for the tweet, False otherwise.
        """
        try:
            cache_file = Path(self.config.tweet_cache_file)
            if not cache_file.exists():
                logging.error("Tweet cache file does not exist")
                return False
            
            cache_data = await async_json_load(cache_file)
            if tweet_id not in cache_data:
                logging.error(f"Tweet {tweet_id} not found in cache")
                return False
            
            tweet_data = cache_data[tweet_id]
            if 'kb_item_path' in tweet_data:
                kb_path = Path(tweet_data['kb_item_path'])
                if kb_path.exists():
                    return True
            
            logging.error(f"No knowledge base item found for tweet {tweet_id}")
            return False
            
        except Exception as e:
            logging.error(f"Error verifying KB item for tweet {tweet_id}: {e}")
            return False

    async def _count_media_items(self) -> int:
        """
        Count total media items that need processing.

        Returns:
            int: The number of media items across all tweets in the cache.
        """
        try:
            cache_data = await async_json_load(self.config.tweet_cache_file)
            return sum(len(tweet_data.get('media', [])) for tweet_data in cache_data.values())
        except Exception:
            return 0

    async def process_tweets(self, tweet_urls: List[str]) -> None:
        """
        Process tweets while preserving existing cache.

        This method processes a list of tweet URLs, skipping already processed tweets unless forced,
        and updates progress via SocketIO if available.

        Args:
            tweet_urls (List[str]): List of tweet URLs or IDs to process.
        """
        global stop_flag, socketio
        if not self._initialized:
            await self.initialize()

        stats = ProcessingStats(datetime.now())
        total_tweets = len(tweet_urls)
        
        for i, tweet_url in enumerate(tweet_urls):
            if stop_flag:
                logging.info("Stopping tweet processing due to stop request")
                break
            tweet_id = parse_tweet_id_from_url(tweet_url)
            if not tweet_id:
                continue

            if await self.state_manager.is_tweet_processed(tweet_id) and not self.config.force_update:
                logging.info(f"Tweet {tweet_id} already processed, skipping")
                stats.skipped_count += 1
                continue

            try:
                cached_data = await self.state_manager.get_tweet_cache(tweet_id)
                if cached_data and not self.config.force_update:
                    tweet_data = cached_data
                    stats.cache_hits += 1
                else:
                    tweet_data = await self._fetch_tweet_data(tweet_url)
                    await self.state_manager.save_tweet_cache(tweet_id, tweet_data)
                    stats.cache_misses += 1
                if socketio:
                    socketio.emit('progress', {'processed': stats.processed_count, 'total': total_tweets, 'errors': stats.error_count})
            except Exception as e:
                logging.error(f"Failed to process tweet {tweet_id}: {e}")
                stats.error_count += 1
                if socketio:
                    socketio.emit('progress', {'processed': stats.processed_count, 'total': total_tweets, 'errors': stats.error_count})
                continue