"""
Main agent module coordinating knowledge base operations.
"""

import logging
from typing import Set, List, Dict, Any
from pathlib import Path
import asyncio
from datetime import datetime
import time

from .config import Config
from .exceptions import AgentError
from .state_manager import StateManager
from .tweet_processor import TweetProcessor
from .git_helper import GitSyncHandler
from .fetch_bookmarks import BookmarksFetcher
from .markdown_writer import MarkdownWriter, generate_root_readme
from .category_manager import CategoryManager
from .types import TweetData, KnowledgeBaseItem
from .prompts import UserPreferences
from .progress import ProcessingStats

class KnowledgeBaseAgent:
    """
    Main agent coordinating knowledge base operations.
    
    Handles the complete flow of fetching tweets, processing them,
    and maintaining the knowledge base structure.
    """
    
    def __init__(self, config: Config):
        self.config = config
        self.state_manager = StateManager(config)
        self.tweet_processor = TweetProcessor(config)
        self.markdown_writer = MarkdownWriter(config)
        self.category_manager = CategoryManager(config)
        self._processing_lock = asyncio.Lock()
        self.git_handler = None  # Initialize only when needed
        self.stats = ProcessingStats(start_time=datetime.now())

    async def initialize(self) -> None:
        """Initialize all components and ensure directory structure."""
        try:
            logging.info("Creating required directories...")
            try:
                self.config.knowledge_base_dir.mkdir(parents=True, exist_ok=True)
                logging.debug(f"Created knowledge base dir: {self.config.knowledge_base_dir}")
                
                self.config.data_processing_dir.mkdir(parents=True, exist_ok=True)
                logging.debug(f"Created processing dir: {self.config.data_processing_dir}")
                
                self.config.media_cache_dir.mkdir(parents=True, exist_ok=True)
                logging.debug(f"Created media cache dir: {self.config.media_cache_dir}")
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
            
            logging.info("Agent initialization complete")
        except Exception as e:
            logging.exception(f"Agent initialization failed: {str(e)}")
            raise AgentError(f"Failed to initialize agent: {str(e)}") from e

    async def process_bookmarks(self) -> None:
        """Process bookmarks with detailed error logging."""
        try:
            logging.info("Starting bookmark processing")
            
            # Initialize bookmark fetcher
            logging.debug("Initializing bookmark fetcher")
            bookmark_fetcher = BookmarksFetcher(self.config)
            
            try:
                # Initialize browser
                logging.debug("Initializing browser")
                await bookmark_fetcher.initialize()
                
                # Fetch bookmarks
                logging.debug("Fetching bookmarks")
                bookmarks = await bookmark_fetcher.fetch_bookmarks()
                logging.info(f"Fetched {len(bookmarks)} bookmarks")
                
                # Process each bookmark
                for bookmark in bookmarks:
                    try:
                        start_time = time.time()
                        await self.process_tweet(bookmark)
                        self.stats.success_count += 1
                        self.stats.add_processing_time(time.time() - start_time)
                    except Exception as e:
                        self.stats.error_count += 1
                        logging.error(f"Failed to process bookmark {bookmark}: {e}")
                        
            except Exception as e:
                logging.exception("Bookmark fetching failed")
                raise AgentError(f"Failed to fetch bookmarks: {str(e)}")
                
            finally:
                # Ensure cleanup
                logging.debug("Cleaning up bookmark fetcher")
                await bookmark_fetcher.cleanup()
                
        except Exception as e:
            logging.exception("Bookmark processing failed")
            raise AgentError(f"Failed to process bookmarks: {str(e)}")

    async def update_indexes(self) -> None:
        """Update category indexes."""
        try:
            logging.info("Starting index update")
            categories = self.category_manager.get_all_categories()  # Remove await
            
            # Process each category
            for category in categories:
                try:
                    # Category-specific processing
                    pass
                except Exception as e:
                    logging.error(f"Failed to process category {category}: {e}")
                    
            logging.info("Index update completed")
        except Exception as e:
            logging.error(f"Index update failed: {e}")
            raise AgentError("Failed to update indexes") from e

    async def sync_changes(self) -> None:
        """Sync changes to GitHub repository."""
        try:
            logging.info("Starting GitHub sync...")
            if self.git_handler is None:
                self.git_handler = GitSyncHandler(self.config)
            await self.git_handler.sync_to_github("Update knowledge base content")
            logging.info("GitHub sync completed successfully")
        except Exception as e:
            logging.error(f"GitHub sync failed: {str(e)}")
            raise AgentError("Failed to sync changes to GitHub") from e

    async def cleanup(self) -> None:
        """Cleanup temporary files and resources."""
        try:
            temp_files = list(self.config.data_processing_dir.glob("*.temp"))
            for temp_file in temp_files:
                temp_file.unlink()
            logging.info("Cleanup completed")
        except Exception as e:
            logging.warning(f"Cleanup failed: {e}")

    async def run(self, preferences: UserPreferences) -> None:
        """Run the agent with the specified preferences."""
        try:
            logging.info("Starting agent run...")
            
            # 1. Check for new bookmarks/tweets to process
            has_new_content = False
            if preferences.update_bookmarks:
                await self.process_bookmarks()  # This updates has_new_content internally
            
            # 2. Get unprocessed tweets from state manager
            unprocessed_tweets = await self.state_manager.get_unprocessed_tweets(
                set(await self.tweet_processor.get_cached_tweet_ids())  # Use cached tweet IDs instead
            )
            
            if not unprocessed_tweets and not preferences.review_existing:
                logging.info("No new content to process")
                return
            
            # 3. Cache tweets and process media
            if unprocessed_tweets or preferences.recreate_tweet_cache:
                await self.tweet_processor.cache_tweets(unprocessed_tweets)
                await self.tweet_processor.process_media()  # This runs vision model on images
            
            # 4. Process tweets into knowledge base items
            if unprocessed_tweets or preferences.review_existing:
                await self.tweet_processor.process_tweets(unprocessed_tweets)
            
            # 5. Generate/Update README
            if has_new_content or preferences.regenerate_readme:
                await self.regenerate_readme()
            
            # 6. Sync to GitHub if requested
            if preferences.sync_to_github:
                await self.sync_changes()
                
            logging.info("Agent run completed successfully")
            
        except Exception as e:
            logging.error(f"Agent run failed: {str(e)}")
            raise AgentError("Agent run failed") from e

    async def process_tweet(self, tweet_url: str) -> None:
        """Process a single tweet."""
        try:
            if await self.state_manager.is_processed(tweet_url):
                logging.debug(f"Tweet already processed: {tweet_url}")
                return

            # Process tweet logic here
            logging.info(f"Processing tweet: {tweet_url}")
            
            # Mark as processed
            await self.state_manager.mark_tweet_processed(tweet_url)
            
        except Exception as e:
            logging.error(f"Failed to process tweet {tweet_url}: {str(e)}")
            raise AgentError(f"Failed to process tweet {tweet_url}: {str(e)}")

    async def regenerate_readme(self) -> None:
        """Regenerate the root README file."""
        try:
            logging.info("Starting README regeneration")
            await generate_root_readme(self.config.knowledge_base_dir, self.category_manager)
            logging.info("README regeneration completed")
        except Exception as e:
            logging.error(f"Failed to regenerate README: {str(e)}")
            raise