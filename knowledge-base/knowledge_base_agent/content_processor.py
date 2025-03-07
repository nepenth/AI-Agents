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
    def __init__(self, config: Config, http_client: HTTPClient, state_manager: StateManager):
        self.config = config
        self.http_client = http_client
        self.category_manager = CategoryManager(config, http_client=http_client)
        self.state_manager = state_manager
        self.stats = ProcessingStats()
        self.text_model = self.http_client.config.text_model
        logging.info(f"Initialized ContentProcessor with model: {self.text_model}")

    async def process_all_tweets(
        self,
        preferences,
        unprocessed_tweets: List[str],
        total_tweets: int,
        stats: ProcessingStats,
        category_manager: CategoryManager
    ) -> None:
        """Process all tweets through various phases."""
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

            # Phase 1.5: Re-cache tweets with incomplete cache
            logging.info("=== Phase 1.5: Re-caching Incomplete Tweets ===")
            uncached_tweets = [tid for tid in unprocessed if not all_tweets.get(tid, {}).get('cache_complete', False)]
            if uncached_tweets:
                logging.info(f"Re-caching {len(uncached_tweets)} tweets with incomplete cache")
                await cache_tweets(uncached_tweets, self.config, self.http_client, self.state_manager, force_recache=True)
                await asyncio.sleep(1)
                all_tweets = await self.state_manager.get_all_tweets()
                for tweet_id in uncached_tweets:
                    tweet_data = all_tweets.get(tweet_id, {})
                    media_files = [Path(p) for p in tweet_data.get('downloaded_media', []) if Path(p).exists()]
                    if tweet_data.get('media', []) and not media_files:
                        logging.warning(f"Tweet {tweet_id} re-caching failed; retrying")
                        await cache_tweets([tweet_id], self.config, self.http_client, self.state_manager, force_recache=True)
                        await asyncio.sleep(1)
                        all_tweets = await self.state_manager.get_all_tweets()
                        logging.debug(f"Retried caching for tweet {tweet_id}")

            # Phase 2: Media Processing
            logging.info("=== Phase 2: Media Processing ===")
            media_todo = sum(1 for tid in unprocessed if not all_tweets.get(tid, {}).get('media_processed', False))
            logging.info(f"Media Processing Needed: {media_todo} tweets")
            for tweet_id in unprocessed:
                tweet_data = all_tweets.get(tweet_id, {})
                if not tweet_data.get('media_processed', False):
                    logging.debug(f"Processing media for tweet {tweet_id}")
                    try:
                        updated_data = await process_media(tweet_data, self.http_client, self.config)
                        await self.state_manager.update_tweet_data(tweet_id, updated_data)
                        await self.state_manager.mark_media_processed(tweet_id)
                        stats.media_processed += len(updated_data.get('downloaded_media', []))
                        logging.debug(f"Completed media processing for tweet {tweet_id}")
                    except Exception as e:
                        logging.error(f"Failed to process media for tweet {tweet_id}: {e}")
                        stats.error_count += 1

            # Phase 3: Category Processing
            logging.info("=== Phase 3: Category Processing ===")
            cat_todo = sum(1 for tid in unprocessed if not all_tweets.get(tid, {}).get('categories_processed', False))
            logging.info(f"Category Processing Needed: {cat_todo} tweets")
            for tweet_id in unprocessed:
                tweet_data = all_tweets.get(tweet_id, {})
                if not tweet_data.get('categories_processed', False) or self.config.reprocess_categories:
                    logging.debug(f"Processing categories for tweet {tweet_id}")
                    try:
                        updated_data = await process_categories(tweet_id, tweet_data, self.config, self.http_client, self.state_manager)
                        await self.state_manager.update_tweet_data(tweet_id, updated_data)
                        await self.state_manager.mark_categories_processed(tweet_id)
                        stats.categories_processed += 1
                        logging.debug(f"Completed category processing for tweet {tweet_id}")
                    except Exception as e:
                        logging.error(f"Failed to process categories for tweet {tweet_id}: {e}")
                        stats.error_count += 1

            # Phase 4: Knowledge Base Creation
            logging.info("=== Phase 4: Knowledge Base Creation ===")
            kb_todo = sum(1 for tid in unprocessed if not all_tweets.get(tid, {}).get('kb_item_created', False))
            logging.info(f"KB Items Needed: {kb_todo} tweets")
            processed_in_phase = 0
            for tweet_id in unprocessed:
                tweet_data = all_tweets.get(tweet_id, {})
                try:
                    # Check if KB item needs creation or reprocessing
                    if not tweet_data.get('kb_item_created', False) or self.config.reprocess_kb_items:
                        logging.debug(f"Creating KB item for tweet {tweet_id}")
                        media_files = [Path(p) for p in tweet_data.get('downloaded_media', []) if Path(p).exists()]
                        if tweet_data.get('media', []):
                            if not media_files:
                                logging.warning(f"Tweet {tweet_id} has media but no files exist; re-caching")
                                await cache_tweets([tweet_id], self.config, self.http_client, self.state_manager, force_recache=True)
                                await asyncio.sleep(1)
                                tweet_data = await self.state_manager.get_tweet(tweet_id)
                                media_files = [Path(p) for p in tweet_data.get('downloaded_media', []) if Path(p).exists()]
                                if not media_files:
                                    logging.error(f"Tweet {tweet_id} still has no media files after re-caching: {tweet_data.get('downloaded_media', [])}")
                                    stats.error_count += 1
                                    continue
                            if media_files and (not tweet_data.get('image_descriptions') or len(tweet_data.get('image_descriptions', [])) < len(media_files)):
                                logging.debug(f"Tweet {tweet_id} re-processing media due to new files or missing descriptions")
                                updated_data = await process_media(tweet_data, self.http_client, self.config)
                                await self.state_manager.update_tweet_data(tweet_id, updated_data)
                                await self.state_manager.mark_media_processed(tweet_id)
                                stats.media_processed += len(updated_data.get('downloaded_media', []))
                                tweet_data = updated_data
                                media_files = [Path(p) for p in tweet_data.get('downloaded_media', []) if Path(p).exists()]

                        kb_item = await self.create_knowledge_base_item(tweet_id, tweet_data)
                        markdown_writer = MarkdownWriter(self.config)
                        kb_path = await markdown_writer.write_kb_item(
                            item=kb_item,
                            media_files=media_files,
                            media_descriptions=tweet_data.get('image_descriptions', []),
                            root_dir=Path(self.config.knowledge_base_dir)
                        )
                        tweet_data['kb_item_created'] = True
                        tweet_data['kb_item_path'] = str(kb_path)
                        await self.state_manager.update_tweet_data(tweet_id, tweet_data)
                        stats.processed_count += 1
                        logging.debug(f"Created KB item for tweet {tweet_id} at {kb_path}")
                        
                        for media_file in media_files:
                            if not media_file.exists():
                                logging.error(f"Media file {media_file} missing before copy for tweet {tweet_id}")
                                continue
                            dest = kb_path / media_file.name
                            if not dest.exists():
                                shutil.copy2(media_file, dest)
                                logging.debug(f"Copied media {media_file.name} to {dest}")

                    # Move fully processed tweets regardless of KB creation
                    if (tweet_data.get('media_processed', True) and 
                        tweet_data.get('categories_processed', True) and 
                        tweet_data.get('kb_item_created', True) and 
                        tweet_data.get('kb_item_path') and 
                        Path(tweet_data['kb_item_path']).exists()):
                        await self.state_manager.mark_tweet_processed(tweet_id, tweet_data)
                        stats.processed_count += 1
                        processed_in_phase += 1
                        logging.debug(f"Tweet {tweet_id} fully processed and moved to processed tweets")
                    else:
                        logging.warning(f"Tweet {tweet_id} not fully processed: media_processed={tweet_data.get('media_processed', False)}, "
                                       f"categories_processed={tweet_data.get('categories_processed', False)}, "
                                       f"kb_item_created={tweet_data.get('kb_item_created', False)}")
                except Exception as e:
                    logging.error(f"Failed to process tweet {tweet_id}: {e}")
                    stats.error_count += 1
            logging.info(f"Processed {processed_in_phase} tweets in Phase 4")

            # Phase 5: README Generation
            logging.info("=== Phase 5: README Generation ===")
            if preferences.regenerate_readme or not (self.config.knowledge_base_dir / "README.md").exists() or kb_todo > 0:
                logging.info(f"Phase 5:Generating root README for {len(all_tweets)} items...")
                await self._regenerate_readme()
                stats.readme_generated = True
            else:
                logging.info("No README regeneration needed")

            # Phase 6: Final Validation
            logging.info("\n=== Phase 6: Final Validation ===")
            await self.state_manager.finalize_processing()

        except asyncio.CancelledError:
            logging.warning("Agent run cancelled by user")
            raise
        except Exception as e:
            logging.error(f"Processing failed: {str(e)}")
            raise ContentProcessingError(f"Processing failed: {e}")

    async def _regenerate_readme(self) -> None:
        """Regenerate the root README file."""
        try:
            await generate_root_readme(
                self.config.knowledge_base_dir,
                self.category_manager,
                self.http_client,
                self.config
            )
            logging.info("README regeneration completed")
        except Exception as e:
            logging.warning(f"Intelligent README generation failed: {e}")
            content = await generate_static_root_readme(
                self.config.knowledge_base_dir,
                self.category_manager
            )
            async with aiofiles.open(self.config.knowledge_base_dir / "README.md", 'w', encoding='utf-8') as f:
                await f.write(content)
            logging.info("Generated static README as fallback")

    async def get_tweets_with_media(self) -> Dict[str, Any]:
        """Get tweets that have unprocessed media."""
        tweets = await self.state_manager.get_all_tweets()
        media_tweets = {
            tweet_id: tweet_data 
            for tweet_id, tweet_data in tweets.items() 
            if has_unprocessed_non_video_media(tweet_data)
        }
        logging.debug(f"Found {len(media_tweets)} tweets with unprocessed media")
        return media_tweets

    async def _count_media_items(self) -> int:
        """Count total media items across all tweets."""
        tweets = await self.state_manager.get_all_tweets()
        count = await count_media_items(tweets)
        logging.debug(f"Counted {count} media items across all tweets")
        return count

    async def create_knowledge_base_item(self, tweet_id: str, tweet_data: Dict[str, Any]) -> KnowledgeBaseItem:
        """Create a knowledge base item for a tweet."""
        logging.debug(f"Generating KB item for tweet {tweet_id}")
        return await create_knowledge_base_item(tweet_id, tweet_data, self.config, self.http_client)

    def _is_video_file(self, path: str) -> bool:
        """Check if a file is a video based on MIME type or extension."""
        path_obj = Path(path)
        mime_type, _ = guess_type(str(path_obj))
        is_video = (mime_type in VIDEO_MIME_TYPES or 
                    path_obj.suffix.lower() in {'.mp4', '.mov', '.avi', '.mkv'})
        logging.debug(f"Checked if {path} is video: {is_video}")
        return is_video