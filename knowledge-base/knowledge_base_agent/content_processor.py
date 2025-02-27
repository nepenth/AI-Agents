from pathlib import Path
from typing import Dict, Any, List
import logging
from dataclasses import dataclass
from knowledge_base_agent.config import Config
from knowledge_base_agent.http_client import HTTPClient
from knowledge_base_agent.state_manager import StateManager
from knowledge_base_agent.category_manager import CategoryManager
from knowledge_base_agent.exceptions import ContentProcessingError, KnowledgeBaseItemCreationError
from knowledge_base_agent.tweet_cacher import cache_tweets
from knowledge_base_agent.media_processor import process_media, has_unprocessed_non_video_media, count_media_items, VIDEO_MIME_TYPES
from knowledge_base_agent.text_processor import process_categories
from knowledge_base_agent.kb_item_generator import create_knowledge_base_item
from knowledge_base_agent.readme_generator import generate_root_readme, generate_static_root_readme
from knowledge_base_agent.markdown_writer import MarkdownWriter
from knowledge_base_agent.types import KnowledgeBaseItem
import aiofiles
import asyncio
import re
from mimetypes import guess_type
import shutil

@dataclass
class ProcessingStats:
    media_processed: int = 0
    categories_processed: int = 0
    processed_count: int = 0
    error_count: int = 0
    readme_generated: bool = False

class ContentProcessor:
    """Orchestrates processing of tweet content into knowledge base items."""
    
    def __init__(self, config: Config, http_client: HTTPClient):
        """Initialize the content processor."""
        self.config = config
        self.http_client = http_client
        self.category_manager = CategoryManager(config, http_client=http_client)
        self.state_manager = StateManager(config)
        self.stats = ProcessingStats()
        self.text_model = self.http_client.config.text_model
        logging.info(f"Initialized ContentProcessor with model: {self.text_model}")

    @classmethod
    async def create_knowledge_base_entry(cls, tweet_data: Dict[str, Any], http_client: HTTPClient, tweet_cache: Dict[str, Any]) -> 'KnowledgeBaseItem':
        """Factory method to create a knowledge base entry from tweet data."""
        from .kb_item_generator import create_knowledge_base_item as create_kb_item
        
        tweet_id = next((k for k, v in tweet_cache.items() if v is tweet_data), None)
        if not tweet_id:
            logging.error("Could not find tweet ID in cache")
            raise ValueError("Tweet data not found in cache")
        
        try:
            logging.debug(f"Raw tweet data for {tweet_id}: {tweet_data}")
            
            if not isinstance(tweet_data, dict):
                raise ValueError(f"Tweet data must be a dictionary, got {type(tweet_data)}")
            
            processor = cls(http_client.config, http_client)
            logging.info(f"Created processor instance for tweet {tweet_id}")
            
            kb_item = await create_kb_item(tweet_id, tweet_data, processor.config, processor.http_client)
            logging.info(f"Successfully created knowledge base item for tweet {tweet_id}")
            return kb_item
            
        except Exception as e:
            error_msg = f"Failed to create knowledge base entry for tweet {tweet_id}: {str(e)}"
            logging.error(error_msg)
            raise KnowledgeBaseItemCreationError(error_msg)

    async def process_all_tweets(
        self,
        preferences, 
        unprocessed_tweets: List[str],
        total_tweets: int,
        stats: ProcessingStats,
        category_manager: CategoryManager
    ) -> None:
        """Process all tweets through the pipeline."""
        try:
            # Phase 1: Tweet Cache Initialization
            logging.info("=== Phase 1: Tweet Cache Initialization ===")
            all_tweets = await self.state_manager.get_all_tweets()
            unprocessed = self.state_manager.unprocessed_tweets
            processed = list(self.state_manager.processed_tweets.keys())
            
            logging.info(f"Tweet Status:\n"
                        f"- Total: {len(all_tweets)}\n"
                        f"- Unprocessed: {len(unprocessed)}\n"
                        f"- Processed: {len(processed)}\n"
                        f"- Incomplete Cache: {sum(1 for t in all_tweets.values() if not t.get('cache_complete'))}")

            # Validate tweet states
            logging.info("=== Pre-processing: Tweet State Validation ===")
            if all_tweets:
                for tweet_id, tweet_data in all_tweets.items():
                    await self._validate_tweet_state(tweet_id, tweet_data)
            else:
                logging.warning("No tweets found in cache for validation")

            # Phase 2: Media Processing
            logging.info("\n=== Phase 2: Media Processing ===")
            media_todo = sum(1 for t in all_tweets.values() if not t.get('media_processed'))
            logging.info(f"Media Processing Needed: {media_todo} tweets")
            
            for tweet_id, tweet_data in all_tweets.items():
                if not tweet_data.get('media_processed', False):
                    try:
                        updated_data = await process_media(tweet_data, self.http_client, self.config)
                        await self.state_manager.update_tweet_data(tweet_id, updated_data)
                        await self.state_manager.mark_media_processed(tweet_id)
                        stats.media_processed += len(tweet_data.get('downloaded_media', []))
                    except Exception as e:
                        logging.error(f"Failed to process media for tweet {tweet_id}: {e}")
                        stats.error_count += 1
                        continue

            if not all(tweet.get('media_processed', False) for tweet in all_tweets.values()):
                logging.warning("Media processing incomplete, proceeding anyway")

            # Phase 3: Category Processing
            logging.info("\n=== Phase 3: Category Processing ===")
            cat_todo = sum(1 for t in all_tweets.values() if not t.get('categories_processed'))
            logging.info(f"Category Processing Needed: {cat_todo} tweets")
            
            for tweet_id, tweet_data in all_tweets.items():
                if not tweet_data.get('categories_processed', False) or self.config.reprocess_categories:
                    try:
                        updated_data = await process_categories(tweet_id, tweet_data, self.config, self.http_client, self.state_manager)
                        await self.state_manager.update_tweet_data(tweet_id, updated_data)
                        await self.state_manager.mark_categories_processed(tweet_id)
                        stats.categories_processed += 1
                    except Exception as e:
                        logging.error(f"Failed to process categories for tweet {tweet_id}: {e}")
                        stats.error_count += 1
                        continue

            if not all(tweet.get('categories_processed', False) for tweet in all_tweets.values()):
                logging.warning("Category processing incomplete, proceeding anyway")

            # Phase 4: Knowledge Base Creation
            logging.info("\n=== Phase 4: Knowledge Base Creation ===")
            kb_todo = sum(1 for t in all_tweets.values() if not t.get('kb_item_created'))
            logging.info(f"KB Items Needed: {kb_todo} tweets")
            
            for tweet_id, tweet_data in all_tweets.items():
                if tweet_data.get('kb_item_created', False):
                    kb_path = tweet_data.get('kb_item_path')
                    if not kb_path or not Path(kb_path).exists():
                        logging.warning(f"KB item marked as created but missing for tweet {tweet_id} at {kb_path}")
                        tweet_data['kb_item_created'] = False
                        await self.state_manager.update_tweet_data(tweet_id, tweet_data)

                if not tweet_data.get('kb_item_created', False) or self.config.reprocess_kb_items:
                    try:
                        kb_item = await self.create_knowledge_base_item(tweet_id, tweet_data)
                        markdown_writer = MarkdownWriter(self.config)
                        kb_path = await markdown_writer.write_kb_item(
                            item=kb_item,
                            media_files=[Path(p) for p in tweet_data.get('downloaded_media', [])],
                            media_descriptions=tweet_data.get('image_descriptions', []),
                            root_dir=Path(self.config.knowledge_base_dir)
                        )
                        tweet_data['kb_item_created'] = True
                        tweet_data['kb_item_path'] = str(kb_path)
                        await self.state_manager.update_tweet_data(tweet_id, tweet_data)
                        stats.processed_count += 1
                        
                        if (tweet_data.get('media_processed', True) and 
                            tweet_data.get('categories_processed', True) and 
                            tweet_data.get('kb_item_created', True)):
                            await self.state_manager.mark_tweet_processed(tweet_id, tweet_data)
                            logging.info(f"Tweet {tweet_id} fully processed and moved to processed tweets")
                        else:
                            logging.warning(f"Tweet {tweet_id} has not completed all processing steps")
                            logging.warning("Missing steps: ")
                            if not tweet_data.get('media_processed', True):
                                logging.warning("- Media processing")
                            if not tweet_data.get('categories_processed', True):
                                logging.warning("- Category processing")
                            if not tweet_data.get('kb_item_created', True):
                                logging.warning("- KB item creation")
                        
                        # Verify media files are present and correctly linked
                        kb_path = Path(tweet_data['kb_item_path'])
                        media_files = [p for p in tweet_data.get('downloaded_media', []) 
                                      if not self._is_video_file(p)]
                        
                        for media_file in media_files:
                            source = Path(media_file)
                            dest = kb_path / source.name
                            if not dest.exists():
                                logging.warning(f"Media file missing from KB item: {dest}")
                                try:
                                    shutil.copy2(source, dest)
                                    logging.info(f"Copied missing media file: {source.name}")
                                except Exception as e:
                                    logging.error(f"Failed to copy media file: {e}")
                                    stats.error_count += 1
                        
                    except Exception as e:
                        logging.error(f"Failed to create KB item for tweet {tweet_id}: {e}")
                        stats.error_count += 1
                        continue

            if not all(tweet.get('kb_item_created', False) for tweet in all_tweets.values()):
                logging.warning("Knowledge base creation incomplete, proceeding anyway")

            # Phase 5: Validation & Cleanup
            logging.info("\n=== Phase 5: Validation & Cleanup ===")
            validation_results = []
            kb_dir = Path(self.config.knowledge_base_dir)
            
            for tweet_id, tweet_data in all_tweets.items():
                if tweet_data.get('kb_item_created', False):
                    valid = await self._validate_kb_item(tweet_id, tweet_data, kb_dir)
                    if not valid:
                        validation_results.append(tweet_id)
                        await self.state_manager.mark_tweet_unprocessed(tweet_id)
                        stats.processed_count -= 1
                        stats.error_count += 1

            if validation_results:
                logging.warning(f"Validation Issues Found: {len(validation_results)} tweets")
                logging.info(f"Invalidated tweets: {validation_results}")
            else:
                logging.info("All KB items validated successfully")

            # Phase 6: README Generation
            logging.info("\n=== Phase 6: README Generation ===")
            kb_dir = Path(self.config.knowledge_base_dir)
            readme_path = kb_dir / "README.md"

            # Check if README exists
            readme_exists = readme_path.exists()
            
            # Generate README if it doesn't exist, REGENERATE_ROOT_README is True, or new KB items were created
            if not readme_exists or self.config.regenerate_root_readme or kb_todo > 0:
                reasons = []
                if not readme_exists:
                    reasons.append("README.md does not exist")
                if self.config.regenerate_root_readme:
                    reasons.append("REGENERATE_ROOT_README is True")
                if kb_todo > 0:
                    reasons.append("new KB items were created")
                reason_str = " and ".join(reasons)
                logging.info(f"Generating README because {reason_str}")
                try:
                    await self._regenerate_readme()
                    stats.readme_generated = True
                    logging.info("Successfully generated root README.md")
                except Exception as e:
                    logging.error(f"Failed to generate root README: {e}")
                    stats.error_count += 1
            else:
                logging.info("Skipping README generation (README exists, no new items, and not explicitly requested)")

            # Always regenerate README at the end
            if preferences.regenerate_readme or not (self.config.knowledge_base_dir / "README.md").exists():
                await self._regenerate_readme()
                stats.readme_generated = True
            
        except asyncio.CancelledError:
            logging.warning("Agent run cancelled by user")
            raise
        except Exception as e:
            logging.error(f"Processing failed: {str(e)}")
            raise

    async def _regenerate_readme(self) -> None:
        """Regenerate the README file."""
        try:
            await generate_root_readme(
                self.config.knowledge_base_dir,
                self.category_manager,
                self.http_client,
                self.config
            )
        except Exception as e:
            logging.warning(f"Intelligent README generation failed: {e}")
            content = await generate_static_root_readme(
                self.config.knowledge_base_dir,
                self.category_manager
            )
            async with aiofiles.open(self.config.knowledge_base_dir / "README.md", 'w', encoding='utf-8') as f:
                await f.write(content)

    async def get_tweets_with_media(self) -> Dict[str, Any]:
        """Get all tweets that have unprocessed non-video media."""
        tweets = await self.state_manager.get_all_tweets()
        return {
            tweet_id: tweet_data 
            for tweet_id, tweet_data in tweets.items() 
            if has_unprocessed_non_video_media(tweet_data)
        }

    async def _count_media_items(self) -> int:
        """Count total number of unprocessed non-video media items."""
        tweets = await self.state_manager.get_all_tweets()
        return await count_media_items(tweets)

    async def create_knowledge_base_item(self, tweet_id: str, tweet_data: Dict[str, Any]) -> KnowledgeBaseItem:
        """Create a knowledge base item from tweet data."""
        return await create_knowledge_base_item(tweet_id, tweet_data, self.config, self.http_client)

    async def _validate_kb_item(self, tweet_id: str, tweet_data: dict, kb_dir: Path) -> bool:
        """Validate that a created KB item actually exists and is correct."""
        try:
            kb_path_str = tweet_data.get('kb_item_path')
            if not kb_path_str:
                logging.warning(f"Tweet {tweet_id} marked as processed but has no KB path")
                return False

            kb_path = kb_dir / kb_path_str
            if not kb_path.exists():
                logging.warning(f"KB path does not exist for {tweet_id}: {kb_path}")
                return False

            # Verify the README contains the tweet URL and check media files
            async with aiofiles.open(kb_path / "README.md", 'r') as f:
                content = await f.read()
                if f"https://twitter.com/i/web/status/{tweet_id}" not in content:
                    logging.warning(f"Tweet URL missing in KB item for {tweet_id}")
                    return False
                
                # Extract media references from markdown
                media_refs = re.findall(r'!\[.*?\]\((.*?)\)', content)
                for media_ref in media_refs:
                    media_path = kb_path / media_ref
                    if not media_path.exists():
                        logging.warning(f"Referenced media file missing: {media_path}")
                        return False
                
                # Check if all downloaded media is referenced
                downloaded_media = tweet_data.get('downloaded_media', [])
                media_files = [Path(p).name for p in downloaded_media if not self._is_video_file(p)]
                referenced_files = [Path(ref).name for ref in media_refs]
                
                missing_refs = set(media_files) - set(referenced_files)
                if missing_refs:
                    logging.warning(f"Media files not referenced in KB item: {missing_refs}")
                    return False

            return True
        except Exception as e:
            logging.error(f"Validation failed for {tweet_id}: {str(e)}")
            return False

    def _is_video_file(self, path: str) -> bool:
        """Check if file is a video based on extension or mime type."""
        path_obj = Path(path)
        mime_type, _ = guess_type(str(path_obj))
        return (mime_type in VIDEO_MIME_TYPES or 
                path_obj.suffix.lower() in {'.mp4', '.mov', '.avi', '.mkv'})

    async def _cleanup_orphaned_items(self, kb_dir: Path):
        """Identify and handle KB items without corresponding tweets"""
        # This could be extended to archive/move orphaned items
        logging.info("Checking for orphaned media references...")
        all_tweets = await self.state_manager.get_all_tweets()
        
        # Build set of all referenced media files
        referenced_media = set()
        for tweet_data in all_tweets.values():
            referenced_media.update(Path(p).name for p in tweet_data.get('downloaded_media', []))
        
        # Check all media files in KB directory
        media_dir = kb_dir / "_media"
        if media_dir.exists():
            for media_file in media_dir.iterdir():
                if media_file.name not in referenced_media:
                    logging.warning(f"Found orphaned media file: {media_file}")
                    # Consider moving to archive or deleting

    async def _validate_tweet_state(self, tweet_id: str, tweet_data: Dict[str, Any]) -> bool:
        """Validate and fix inconsistencies in tweet processing state."""
        try:
            needs_update = False
            
            # Check if KB item exists despite being marked as not created
            if not tweet_data.get('kb_item_created') and tweet_data.get('kb_item_path'):
                kb_path = Path(tweet_data['kb_item_path'])
                if kb_path.exists() and (kb_path / "README.md").exists():
                    tweet_data['kb_item_created'] = True
                    needs_update = True
                else:
                    # Path doesn't exist, remove invalid path
                    tweet_data.pop('kb_item_path', None)
            
            # Check cache completion state
            if not tweet_data.get('cache_complete'):
                if (tweet_data.get('media_processed') and 
                    tweet_data.get('categories_processed')):
                    tweet_data['cache_complete'] = True
                    needs_update = True
            
            if needs_update:
                await self.state_manager.update_tweet_data(tweet_id, tweet_data)
                
                # If all processing is complete, mark as processed
                if (tweet_data.get('media_processed') and 
                    tweet_data.get('categories_processed') and 
                    tweet_data.get('kb_item_created') and 
                    tweet_data.get('cache_complete')):
                    await self.state_manager.mark_tweet_processed(tweet_id)
                    logging.info(f"Tweet {tweet_id} state validated and marked as processed")
            
            return True
        except Exception as e:
            logging.error(f"State validation failed for tweet {tweet_id}: {e}")
            return False