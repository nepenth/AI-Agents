"""
Main agent module coordinating knowledge base operations.
"""

import logging
from typing import Set, List, Dict, Any
from pathlib import Path
import asyncio
from datetime import datetime

from .config import Config
from .state_manager import StateManager
from .tweet_processor import TweetProcessor
from .git_helper import GitSyncHandler
from .fetch_bookmarks import fetch_all_bookmarks
from .markdown_writer import MarkdownWriter
from .category_manager import CategoryManager
from .exceptions import AgentError
from .types import TweetData, KnowledgeBaseItem

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
            # Ensure required directories exist
            self.config.knowledge_base_dir.mkdir(parents=True, exist_ok=True)
            self.config.data_processing_dir.mkdir(parents=True, exist_ok=True)
            
            # Initialize components
            await self.state_manager.initialize()
            await self.category_manager.initialize()
            
            logging.info("Agent initialization complete")
        except Exception as e:
            logging.exception("Agent initialization failed")
            raise AgentError("Failed to initialize agent") from e

    async def process_bookmarks(self) -> None:
        """Process new bookmarks into knowledge base entries."""
        async with self._processing_lock:
            try:
                # Fetch new bookmarks
                bookmarks = await fetch_all_bookmarks(self.config)
                if not bookmarks:
                    logging.info("No bookmarks found")
                    return

                # Filter out processed tweets
                unprocessed = await self.state_manager.get_unprocessed_tweets(set(bookmarks))
                if not unprocessed:
                    logging.info("No new tweets to process")
                    return

                # Process each tweet
                for tweet_url in unprocessed:
                    try:
                        # Process tweet
                        kb_item = await self.tweet_processor.process_tweet(tweet_url)
                        
                        # Generate markdown
                        await self.markdown_writer.write_kb_item(kb_item)
                        
                        # Update state
                        await self.state_manager.mark_tweet_processed(tweet_url)
                        
                        logging.info(f"Successfully processed tweet: {tweet_url}")
                        
                    except Exception as e:
                        logging.error(f"Failed to process tweet {tweet_url}: {e}")
                        continue

                logging.info(f"Processed {len(unprocessed)} new tweets")

            except Exception as e:
                logging.exception("Bookmark processing failed")
                raise AgentError("Failed to process bookmarks") from e

    async def update_indexes(self) -> None:
        """Update knowledge base indexes and category structure."""
        try:
            # Update main README
            await self.markdown_writer.generate_readme()
            
            # Update category indexes
            categories = await self.category_manager.get_all_categories()
            for category in categories:
                await self.markdown_writer.update_category_index(category)
            
            logging.info("Knowledge base indexes updated")
        except Exception as e:
            logging.exception("Index update failed")
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

    async def run(self) -> None:
        """Main execution flow with cleanup."""
        try:
            await self.initialize()
            await self.process_bookmarks()
            await self.update_indexes()
            await self.sync_changes()
            await self.cleanup()
            logging.info("Agent run completed successfully")
        except Exception as e:
            logging.exception("Agent execution failed")
            await self.cleanup()  # Ensure cleanup runs even on failure
            raise AgentError("Agent execution failed") from e