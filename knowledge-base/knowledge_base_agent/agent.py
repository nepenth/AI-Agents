"""
Main agent module coordinating knowledge base operations.
"""

import logging
from typing import Set, List, Dict, Any
from pathlib import Path
import asyncio
from datetime import datetime

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
        self.git_handler = GitSyncHandler(config)
        self.markdown_writer = MarkdownWriter(config)
        self.category_manager = CategoryManager(config)
        self._processing_lock = asyncio.Lock()

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
                        await self.process_tweet(bookmark)
                    except Exception as e:
                        logging.error(f"Failed to process bookmark {bookmark}: {str(e)}")
                        
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
        """Sync changes to remote repository with commit message."""
        try:
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            message = f"Update knowledge base - {timestamp}"
            await self.git_handler.sync_to_github(message)
            logging.info("Changes synced to GitHub")
        except Exception as e:
            logging.exception("Git sync failed")
            raise AgentError("Failed to sync changes") from e

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
        """
        Run the agent with the specified preferences.
        
        Args:
            preferences: User preferences for this run
        """
        try:
            logging.info("Agent initialization complete")
            
            if preferences.update_bookmarks:
                logging.info("Starting bookmark processing")
                await self.process_bookmarks()
                
            if preferences.review_existing:
                logging.info("Starting review of existing items")
                await self.review_existing_items()
                
            if preferences.regenerate_readme:
                logging.info("Regenerating README")
                await self.regenerate_readme()
                
            if preferences.push_to_github:
                logging.info("Pushing changes to GitHub")
                await self.push_changes()
                
            if preferences.recreate_tweet_cache:
                logging.info("Reprocessing cached tweets")
                await self.reprocess_tweet_cache()
                
        except Exception as e:
            logging.error(f"Agent run failed: {str(e)}")
            raise

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