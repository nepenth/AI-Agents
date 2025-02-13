from pathlib import Path
import logging
import asyncio
from typing import Optional

from .config import Config
from .category_manager import CategoryManager
from .markdown_writer import MarkdownWriter
from .git_helper import push_to_github
from .exceptions import KnowledgeBaseError
from .fetch_bookmarks import fetch_bookmarks
from .tweet_utils import load_tweet_urls_from_links, parse_tweet_id_from_url
from .state_manager import load_processed_tweets
from .http_client import create_http_client, OllamaClient
from .cache_manager import load_cache, save_cache
from .prompts import prompt_yes_no
from .migration import migrate_content_to_readme
from .reprocess import reprocess_existing_items
from .markdown_writer import generate_root_readme
from .tweet_processor import process_tweets

class KnowledgeBaseAgent:
    def __init__(self, config: Config):
        self.config = config
        self.category_manager = CategoryManager(config.categories_file)
        self.markdown_writer = MarkdownWriter()
        self.http_client = create_http_client()
        self.ollama_client = OllamaClient(
            base_url=config.ollama_url,
            timeout=config.request_timeout,
            max_pool_size=config.max_pool_size
        )
        self.tweet_cache = load_cache()

    async def initialize(self):
        """Initialize the agent and ensure all required directories exist."""
        self.config.knowledge_base_dir.mkdir(parents=True, exist_ok=True)
        self.config.media_cache_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize cache and state
        self.processed_tweets = load_processed_tweets(self.config.processed_tweets_file)

    async def run(self, update_bookmarks: bool = True, process_new: bool = True,
                 update_readme: bool = True, push_changes: bool = True) -> None:
        """Main execution flow of the agent."""
        try:
            await self.initialize()

            # 1. Check for content migration
            if any(Path(self.config.knowledge_base_dir).rglob('content.md')):
                if prompt_yes_no("Found existing content.md files. Migrate to README.md?"):
                    await migrate_content_to_readme(self.config.knowledge_base_dir)

            # 2. Update bookmarks if requested
            if update_bookmarks:
                success = fetch_bookmarks(self.config)
                if not success:
                    logging.warning("Failed to update bookmarks. Proceeding with existing bookmarks.")

            # 3. Process new tweets
            if process_new:
                tweet_urls = load_tweet_urls_from_links(self.config.bookmarks_file)
                await process_tweets(tweet_urls, self.config, self.category_manager,
                                  self.http_client, self.tweet_cache)
                save_cache(self.tweet_cache)

            # 4. Update README if requested
            if update_readme:
                generate_root_readme(self.config.knowledge_base_dir, self.category_manager)

            # 5. Push changes if requested
            if push_changes:
                push_to_github(
                    knowledge_base_dir=self.config.knowledge_base_dir,
                    github_repo_url=self.config.github_repo_url,
                    github_token=self.config.github_token,
                    git_user_name=self.config.github_user_name,
                    git_user_email=self.config.github_user_email
                )

        except Exception as e:
            logging.error(f"Agent execution failed: {e}")
            raise KnowledgeBaseError(f"Agent execution failed: {e}")

    def _filter_new_tweets(self, tweet_urls: list) -> list:
        """Filter out already processed tweets."""
        return [url for url in tweet_urls 
                if parse_tweet_id_from_url(url) not in self.processed_tweets]

    async def _process_new_tweets(self, urls: list):
        """Process new tweets with proper error handling."""
        if prompt_yes_no("Cache tweet data for new tweets?"):
            # Implement caching logic
            pass
        await process_tweets(urls, self.config, self.category_manager, 
                           self.http_client, self.tweet_cache)

    async def _perform_maintenance(self):
        """Handle maintenance operations."""
        operations = [
            ("Re-review existing items?", 
             lambda: reprocess_existing_items(self.config.knowledge_base_dir, self.category_manager)),
            ("Regenerate root README?", 
             lambda: generate_root_readme(self.config.knowledge_base_dir, self.category_manager)),
            ("Push changes to GitHub?", 
             lambda: self._git_push_changes())
        ]

        for prompt, operation in operations:
            if prompt_yes_no(prompt):
                try:
                    operation()
                except Exception as e:
                    logging.error(f"Maintenance operation failed: {e}")

    def _git_push_changes(self) -> bool:
        """Push changes to the git repository."""
        try:
            push_to_github(
                knowledge_base_dir=self.config.knowledge_base_dir,
                github_repo_url=self.config.github_repo_url,
                github_token=self.config.github_token,
                git_user_name=self.config.github_user_name,
                git_user_email=self.config.github_user_email
            )
            return True
        except Exception as e:
            logging.error(f"Failed to push to GitHub: {e}")
            return False 