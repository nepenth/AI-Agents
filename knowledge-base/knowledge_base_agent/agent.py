from pathlib import Path
import logging
import asyncio
from typing import Optional, List
import shutil

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
from knowledge_base_agent.prompts import prompt_yes_no, prompt_with_retry, prompt_for_maintenance
from knowledge_base_agent.migration import migrate_content_to_readme
from knowledge_base_agent.reprocess import reprocess_existing_items
from knowledge_base_agent.markdown_writer import generate_root_readme
from knowledge_base_agent.tweet_processor import process_tweets
from knowledge_base_agent.ai_categorization import categorize_and_name_content
from knowledge_base_agent.content_processor import create_knowledge_base_entry
from knowledge_base_agent.utils import run_command

class KnowledgeBaseAgent:
    def __init__(self, config: Config):
        self.config = config
        
        # Ensure all required directories exist
        self.config.data_processing_dir.mkdir(parents=True, exist_ok=True)
        self.config.media_cache_dir.mkdir(parents=True, exist_ok=True)
        self.config.knowledge_base_dir.mkdir(parents=True, exist_ok=True)
        
        self.category_manager = CategoryManager(config.categories_file)
        self.markdown_writer = MarkdownWriter()
        self.http_client = create_http_client()
        self.ollama_client = OllamaClient(
            base_url=config.ollama_url,
            timeout=config.request_timeout,
            max_pool_size=config.max_pool_size
        )
        self.tweet_cache = load_cache(config.tweet_cache_file)
        self.processed_tweets = set()
        
        # Load processed tweets if file exists
        if self.config.processed_tweets_file.exists():
            self.processed_tweets = load_processed_tweets(self.config.processed_tweets_file)

    async def run(self, update_bookmarks: bool = True, process_new: bool = True,
                 update_readme: bool = True, push_changes: bool = True,
                 recreate_cache: bool = None) -> None:
        """
        Run the knowledge base agent.
        """
        try:
            # Handle cache recreation first
            if recreate_cache:
                logging.info("Recreating tweet cache...")
                # Clear tweet cache dictionary
                self.tweet_cache = {}
                
                # Remove existing cache files
                if self.config.tweet_cache_file.exists():
                    logging.info(f"Removing tweet cache file: {self.config.tweet_cache_file}")
                    self.config.tweet_cache_file.unlink()
                
                # Clear media cache directory
                if self.config.media_cache_dir.exists():
                    logging.info(f"Clearing media cache directory: {self.config.media_cache_dir}")
                    shutil.rmtree(self.config.media_cache_dir)
                self.config.media_cache_dir.mkdir(parents=True, exist_ok=True)
                
                # Load all tweet URLs and rebuild cache
                tweet_urls = load_tweet_urls_from_links(self.config.bookmarks_file)
                logging.info(f"Found {len(tweet_urls)} tweets to cache")
                for url in tweet_urls:
                    logging.info(f"Caching tweet data for: {url}")
                    await cache_tweet_data(url, self.config, self.tweet_cache, self.http_client)

            # Continue with other operations
            if update_bookmarks:
                await fetch_bookmarks(
                    self.config.x_username,
                    self.config.x_password,
                    self.config.bookmarks_file
                )

            # Process vision model for all cached images
            await self._process_cached_images()

            # Process new tweets if requested
            if process_new:
                tweet_urls = load_tweet_urls_from_links(self.config.bookmarks_file)
                new_urls = self._filter_new_tweets(tweet_urls)
                if new_urls:
                    await self._process_new_tweets(new_urls)

            # Update README if requested
            if update_readme:
                await generate_root_readme(self.config.knowledge_base_dir, self.category_manager)

            # Push changes if requested
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
                
                # Get categories and name using AI
                main_cat, sub_cat, name = await categorize_and_name_content(
                    self.config.ollama_url,
                    tweet_data.get('full_text', ''),  # Use .get() for dictionary access
                    self.config.text_model,
                    tweet_id,
                    self.category_manager
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
        prefs = prompt_for_maintenance()
        
        if prefs["reprocess"]:
            await reprocess_existing_items(self.config.knowledge_base_dir, self.category_manager)
            
        if prefs["regenerate_readme"]:
            await generate_root_readme(self.config.knowledge_base_dir, self.category_manager)
            
        if prefs["push_changes"]:
            await self._git_push_changes()

    async def _git_push_changes(self) -> None:
        """Initialize repo, commit and push changes to GitHub."""
        try:
            repo_dir = self.config.knowledge_base_dir
            logging.info(f"Pushing changes from {repo_dir}")
            
            # Set git credentials helper to store the token
            logging.info("Configuring git credentials")
            await run_command(['git', 'config', '--global', 'credential.helper', 'store'], cwd=repo_dir)
            
            # Store the credentials
            cred_string = f"https://{self.config.github_token}:x-oauth-basic@github.com\n"
            home = Path.home()
            cred_file = home / '.git-credentials'
            cred_file.write_text(cred_string)
            logging.info("Stored git credentials")
            
            # Initialize git if needed
            if not (repo_dir / '.git').exists():
                logging.info("Initializing new git repository")
                await run_command(['git', 'init'], cwd=repo_dir)
                await run_command(['git', 'remote', 'add', 'origin', self.config.github_repo_url], cwd=repo_dir)
            
            # Configure git
            logging.info("Configuring git user")
            await run_command(['git', 'config', 'user.email', self.config.github_user_email], cwd=repo_dir)
            await run_command(['git', 'config', 'user.name', self.config.github_user_name], cwd=repo_dir)
            
            # Stage and commit
            logging.info("Staging changes")
            await run_command(['git', 'add', '-A'], cwd=repo_dir)
            try:
                logging.info("Committing changes")
                await run_command(['git', 'commit', '-m', 'Update knowledge base'], cwd=repo_dir)
            except Exception as e:
                if 'nothing to commit' not in str(e):
                    raise
                logging.info("No changes to commit")
            
            # Push changes
            logging.info("Pushing to remote")
            await run_command(['git', 'checkout', '-B', 'main'], cwd=repo_dir)
            await run_command(['git', 'push', '-f', 'origin', 'main'], cwd=repo_dir)
            
            # Clean up credentials file
            if cred_file.exists():
                cred_file.unlink()
            logging.info("Successfully pushed changes to GitHub")
            
        except Exception as e:
            logging.error(f"Failed to push to GitHub: {e}")
            raise

    async def _process_cached_images(self) -> None:
        """Process all cached images through vision model."""
        try:
            for tweet_id, tweet_data in self.tweet_cache.items():
                if 'downloaded_media' in tweet_data and not tweet_data.get('image_descriptions'):
                    image_descriptions = []
                    for image_path in tweet_data['downloaded_media']:
                        if Path(image_path).exists():
                            # Process image through vision model
                            description = await self.ollama_client.analyze_image(
                                image_path=Path(image_path),
                                model=self.config.vision_model
                            )
                            image_descriptions.append(description)
                    
                    # Update cache with image descriptions
                    tweet_data['image_descriptions'] = image_descriptions
                    await save_cache(self.tweet_cache, self.config.tweet_cache_file)
                    logging.info(f"Added vision analysis for tweet {tweet_id}")
                    
        except Exception as e:
            logging.error(f"Failed to process cached images: {e}")
            raise 