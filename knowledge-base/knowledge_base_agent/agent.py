from pathlib import Path
import logging
import asyncio
from typing import Optional, List

from knowledge_base_agent.config import Config
from knowledge_base_agent.category_manager import CategoryManager
from knowledge_base_agent.markdown_writer import MarkdownWriter
from knowledge_base_agent.git_helper import push_to_github
from knowledge_base_agent.exceptions import KnowledgeBaseError
from knowledge_base_agent.fetch_bookmarks import fetch_bookmarks
from knowledge_base_agent.tweet_utils import load_tweet_urls_from_links, parse_tweet_id_from_url
from knowledge_base_agent.state_manager import load_processed_tweets
from knowledge_base_agent.http_client import create_http_client, OllamaClient
from knowledge_base_agent.cache_manager import load_cache, save_cache, cache_tweet_data, get_cached_tweet
from knowledge_base_agent.prompts import prompt_yes_no
from knowledge_base_agent.migration import migrate_content_to_readme
from knowledge_base_agent.reprocess import reprocess_existing_items
from knowledge_base_agent.markdown_writer import generate_root_readme
from knowledge_base_agent.tweet_processor import process_tweets
from knowledge_base_agent.ai_categorization import categorize_and_name_content
from knowledge_base_agent.content_processor import create_knowledge_base_entry

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
        self.processed_tweets = set()  # Initialize empty set
        
        # Load processed tweets if file exists
        if self.config.processed_tweets_file.exists():
            with open(self.config.processed_tweets_file, 'r') as f:
                self.processed_tweets = set(line.strip() for line in f)

    async def run(self, update_bookmarks: bool = True, process_new: bool = True,
                 update_readme: bool = True, push_changes: bool = True) -> None:
        """Main execution flow of the agent."""
        try:
            # 1. Check for content migration
            if any(Path(self.config.knowledge_base_dir).rglob('content.md')):
                if prompt_yes_no("Found existing content.md files. Migrate to README.md?"):
                    await migrate_content_to_readme(self.config.knowledge_base_dir)

            # 2. Update bookmarks if requested
            if update_bookmarks:
                success = await fetch_bookmarks(self.config)
                if not success:
                    logging.warning("Failed to update bookmarks. Proceeding with existing bookmarks.")

            # 3. Process new tweets if requested
            if process_new:
                tweet_urls = load_tweet_urls_from_links(self.config.bookmarks_file)
                new_urls = self._filter_new_tweets(tweet_urls)
                if new_urls:
                    await self._process_new_tweets(new_urls)

            # 4. Update README if requested
            if update_readme:
                await generate_root_readme(self.config.knowledge_base_dir, self.category_manager)

            # 5. Push changes if requested
            if push_changes:
                await self._git_push_changes()

        except Exception as e:
            logging.error(f"Agent execution failed: {e}")
            raise KnowledgeBaseError(f"Agent execution failed: {e}")

    def _filter_new_tweets(self, tweet_urls: list) -> list:
        """Filter out already processed tweets."""
        return [url for url in tweet_urls 
                if parse_tweet_id_from_url(url) not in self.processed_tweets]

    async def _process_new_tweets(self, tweet_urls: List[str]) -> None:
        """Process new tweets and create knowledge base entries."""
        for tweet_url in tweet_urls:
            try:
                tweet_id = parse_tweet_id_from_url(tweet_url)
                if not tweet_id:
                    logging.warning(f"Invalid tweet URL: {tweet_url}")
                    continue
                    
                # Cache tweet data if not already cached
                await cache_tweet_data(tweet_url, self.config, self.tweet_cache, self.http_client)
                
                # Get tweet data from cache
                tweet_data = get_cached_tweet(tweet_id, self.tweet_cache)
                if not tweet_data:
                    logging.warning(f"No cached data found for tweet {tweet_id}")
                    continue
                
                # Categorize and process tweet - remove keyword arguments
                main_cat, sub_cat, name = await categorize_and_name_content(
                    tweet_data,
                    self.category_manager,
                    self.config.text_model,
                    tweet_id
                )
                
                # Create knowledge base entry
                await create_knowledge_base_entry(
                    tweet_id=tweet_id,
                    tweet_data=tweet_data,
                    categories=(main_cat, sub_cat, name),
                    config=self.config
                )
                
                # Mark tweet as processed
                self.processed_tweets.add(tweet_id)
                self._save_processed_tweets()
                
                logging.info(f"Successfully processed tweet {tweet_id}")
                
            except Exception as e:
                logging.error(f"Failed to process tweet {tweet_url}: {e}")
                continue

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

    async def _git_push_changes(self) -> bool:
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