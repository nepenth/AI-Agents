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
from knowledge_base_agent.ai_categorization import categorize_and_name_content, AIError

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
        """Process all tweets through various phases with enhanced error handling and parallelism."""
        try:
            # Phase 1: Tweet Cache Initialization (and validation via StateManager.initialize)
            logging.info("=== Phase 1: Tweet Cache Initialization & Validation ===")
            # StateManager.initialize() should have run before this, performing validation
            all_tweets = await self.state_manager.get_all_tweets()
            unprocessed = await self.state_manager.get_unprocessed_tweets() # Get fresh list after validation
            processed = list(self.state_manager.processed_tweets.keys())
            total_tweets = len(unprocessed) # Update total based on validated list
            logging.info(f"Tweet Status After Initial Validation:\n"
                        f"- Total in Cache: {len(all_tweets)}\n"
                        f"- Unprocessed: {len(unprocessed)}\n"
                        f"- Processed: {len(processed)}\n"
                        f"- Incomplete Cache: {sum(1 for t in all_tweets.values() if not t.get('cache_complete'))}")

            # Phase 1.5: Re-caching Incomplete Tweets ===
            logging.info("=== Phase 1.5: Re-caching Incomplete Tweets ===")
            uncached_tweets = [tid for tid in unprocessed if not all_tweets.get(tid, {}).get('cache_complete', False)]
            if uncached_tweets:
                logging.info(f"Attempting to re-cache {len(uncached_tweets)} tweets with incomplete cache")
                max_retries = 3
                caching_errors = 0 # Track caching errors separately
                for attempt in range(max_retries):
                    try:
                        # Pass only the tweets needing caching for this attempt
                        await cache_tweets(uncached_tweets, self.config, self.http_client, self.state_manager, force_recache=True)
                        await asyncio.sleep(1) # Give some time for state to potentially update
                        all_tweets = await self.state_manager.get_all_tweets() # Refresh after caching attempt
                        remaining_uncached = [tid for tid in uncached_tweets if not all_tweets.get(tid, {}).get('cache_complete', False)]

                        if not remaining_uncached:
                            logging.info(f"Successfully cached remaining {len(uncached_tweets)} tweets.")
                            uncached_tweets = [] # Clear the list
                            break # Exit retry loop

                        logging.warning(f"Retry {attempt + 1}/{max_retries}: {len(remaining_uncached)} tweets still uncached.")
                        uncached_tweets = remaining_uncached # Update list for next retry

                    except Exception as cache_exc:
                         # Log the error during the caching call itself
                         logging.error(f"Error during cache_tweets call (Attempt {attempt + 1}): {cache_exc}")
                         # Decide if we should wait/retry or just note the failure for this attempt
                         if attempt < max_retries - 1:
                              await asyncio.sleep(2 ** attempt) # Basic backoff before next retry
                         # Don't break here, let the loop check remaining_uncached

                if uncached_tweets:
                    caching_errors = len(uncached_tweets)
                    logging.error(f"Failed to cache {caching_errors} tweets after {max_retries} attempts. These specific tweets will be skipped in subsequent phases.")
                    # Do NOT add to the main stats.error_count here
                    # stats.cache_error_count = caching_errors # Optional: track separately

            # Get the latest list of tweets to process after potential caching failures
            unprocessed = await self.state_manager.get_unprocessed_tweets()
            all_tweets = await self.state_manager.get_all_tweets() # Refresh state

            # --- Subsequent phases (Media, Category, KB Creation) should only operate on ---
            # --- tweets that have cache_complete = True ---

            # Phase 2: Media Processing with parallelism
            logging.info("=== Phase 2: Media Processing ===")
            # Filter for tweets that are in unprocessed list AND have cache_complete = True
            media_todo_ids = [
                tid for tid in unprocessed
                if all_tweets.get(tid, {}).get('cache_complete', False) # Ensure cache is complete
                and not all_tweets.get(tid, {}).get('media_processed', False)
            ]
            logging.info(f"Media Processing Needed: {len(media_todo_ids)} tweets")
            if media_todo_ids:
                async def process_media_task(tweet_id):
                    tweet_data = all_tweets.get(tweet_id, {}) # Use latest state
                    # Double check conditions inside task
                    if tweet_data.get('cache_complete', False) and not tweet_data.get('media_processed', False):
                        logging.debug(f"Processing media for tweet {tweet_id}")
                        try:
                            updated_data = await process_media(tweet_data, self.http_client, self.config)
                            # Use StateManager method to update and save atomically
                            await self.state_manager.update_tweet_data(tweet_id, updated_data)
                            await self.state_manager.mark_media_processed(tweet_id) # Updates flag and saves
                            stats.media_processed += len(updated_data.get('downloaded_media', []))
                            logging.debug(f"Completed media processing for tweet {tweet_id}")
                        except Exception as e:
                            logging.error(f"Failed to process media for tweet {tweet_id}: {e}")
                            stats.error_count += 1
                tasks = [process_media_task(tweet_id) for tweet_id in media_todo_ids]
                await asyncio.gather(*tasks, return_exceptions=True)
                all_tweets = await self.state_manager.get_all_tweets() # Refresh state again

            # Phase 3: Category Processing with parallelism
            logging.info("=== Phase 3: Category Processing ===")
            cat_todo_ids = [
                tid for tid in unprocessed
                if all_tweets.get(tid, {}).get('cache_complete', False) # Ensure cache is complete
                and all_tweets.get(tid, {}).get('media_processed', False)
                and not all_tweets.get(tid, {}).get('categories_processed', False)
            ]
            logging.info(f"Category Processing Needed: {len(cat_todo_ids)} tweets")
            if cat_todo_ids:
                async def process_categories_task(tweet_id):
                    tweet_data = all_tweets.get(tweet_id, {})
                    if (tweet_data.get('cache_complete', False) and
                        tweet_data.get('media_processed', False) and
                        not tweet_data.get('categories_processed', False)):
                        logging.debug(f"Processing categories for tweet {tweet_id}")
                        try:
                            # category_manager.process_categories calls categorize_and_name_content
                            updated_data = await category_manager.process_categories(tweet_id, tweet_data)
                            # These lines are reached ONLY if process_categories doesn't raise an error
                            await self.state_manager.update_tweet_data(tweet_id, updated_data) # Save successful categorization
                            await self.state_manager.mark_categories_processed(tweet_id) # Mark success
                            stats.categories_processed += 1
                            logging.debug(f"Completed category processing for tweet {tweet_id}")
                        except AIError as ai_err: # Catch the specific error from categorization failing
                            logging.error(f"Categorization failed permanently for tweet {tweet_id} after retries: {ai_err}")
                            stats.error_count += 1
                            # DO NOT mark categories_processed = True
                        except Exception as e: # Catch other unexpected errors
                            logging.error(f"Unexpected error during category processing task for tweet {tweet_id}: {e}")
                            stats.error_count += 1
                            # DO NOT mark categories_processed = True
                tasks = [process_categories_task(tweet_id) for tweet_id in cat_todo_ids]
                await asyncio.gather(*tasks, return_exceptions=False) # Don't return exceptions, handle within task
                all_tweets = await self.state_manager.get_all_tweets() # Refresh state

            # Phase 4: Knowledge Base Creation
            logging.info("=== Phase 4: Knowledge Base Creation ===")
            kb_todo_ids = [
                tid for tid in unprocessed
                if all_tweets.get(tid, {}).get('cache_complete', False) # Ensure cache is complete
                and all_tweets.get(tid, {}).get('media_processed', False)
                and all_tweets.get(tid, {}).get('categories_processed', False)
                and not all_tweets.get(tid, {}).get('kb_item_created', False)
            ]
            logging.info(f"KB Items Needed: {len(kb_todo_ids)} tweets")
            processed_in_phase = 0
            if kb_todo_ids:
                # Process KB items sequentially for now to avoid FS race conditions? Or use locks?
                # Let's try sequential for stability first.
                for tweet_id in kb_todo_ids:
                    # Refresh data just before processing
                    tweet_data = await self.state_manager.get_tweet(tweet_id)
                    if not tweet_data: continue # Should not happen if in unprocessed list

                    # Check conditions again before expensive operation
                    if not (tweet_data.get('cache_complete', False) and
                            tweet_data.get('media_processed', False) and
                            tweet_data.get('categories_processed', False) and
                            not tweet_data.get('kb_item_created', False)):
                        logging.debug(f"Skipping KB creation for {tweet_id}, prerequisites not met.")
                        continue

                    try:
                        logging.debug(f"Creating KB item for tweet {tweet_id}")
                        media_files = [Path(p) for p in tweet_data.get('downloaded_media', []) if Path(p).exists()]

                        # Generate the KB item structure
                        kb_item = await create_knowledge_base_item(tweet_id, tweet_data, self.config, self.http_client, self.state_manager)

                        # Write the markdown file and copy media
                        markdown_writer = MarkdownWriter(self.config)
                        kb_path_dir = await markdown_writer.write_kb_item(
                            item=kb_item,
                            media_files=media_files,
                            media_descriptions=tweet_data.get('image_descriptions', []),
                            root_dir=Path(self.config.knowledge_base_dir)
                        )

                        # Update state: mark KB created and store path (relative to project root preferably)
                        # Convert absolute path returned by writer to relative for storage consistency
                        try:
                            relative_kb_path = kb_path_dir.relative_to(Path(self.config.knowledge_base_dir).parent)
                        except ValueError:
                             logging.warning(f"Could not make KB path {kb_path_dir} relative to {Path(self.config.knowledge_base_dir).parent}. Storing absolute.")
                             relative_kb_path = kb_path_dir # Store absolute path as fallback

                        await self.state_manager.mark_kb_item_created(tweet_id, str(relative_kb_path))
                        stats.processed_count += 1 # Increment only on successful KB item creation?
                        logging.debug(f"Created KB item for tweet {tweet_id} at {kb_path_dir}")
                        processed_in_phase += 1

                        # Note: Copying media is handled within write_kb_item now

                    except Exception as e:
                        logging.error(f"Failed to create KB item for tweet {tweet_id}: {e}")
                        stats.error_count += 1
                        # Do not mark as processed, leave in unprocessed

            logging.info(f"Processed {processed_in_phase} tweets in Phase 4")
            all_tweets = await self.state_manager.get_all_tweets() # Refresh state

            # Phase 5: README Generation
            logging.info("=== Phase 5: README Generation ===")
            # Regenerate if forced, file missing, or new KB items were created
            should_regenerate = (preferences.regenerate_readme or
                                not (self.config.knowledge_base_dir / "README.md").exists() or
                                processed_in_phase > 0)
            if should_regenerate:
                logging.info(f"Phase 5: Generating root README...")
                try:
                    await self._regenerate_readme()
                    stats.readme_generated = True
                except Exception as e:
                    logging.error(f"README generation failed: {e}")
                    # Continue processing other tweets
            else:
                logging.info("No README regeneration needed based on flags and KB item changes.")

            # Phase 6: Final Validation (Using StateManager's finalization)
            logging.info("\n=== Phase 6: Final Validation and State Update ===")
            await self.state_manager.finalize_processing()
            # This moves fully validated items to processed list.

        except asyncio.CancelledError:
            logging.warning("Agent run cancelled by user")
            raise
        except Exception as e:
            logging.exception(f"Content processing failed unexpectedly: {str(e)}") # Log traceback
            raise ContentProcessingError(f"Processing failed: {e}") from e

    async def _regenerate_readme(self) -> None:
        """Regenerate the root README file."""
        try:
            # Re-initialize category manager to pick up new items before generating README
            await self.category_manager.initialize()
            await generate_root_readme(
                self.config.knowledge_base_dir,
                self.category_manager,
                self.http_client,
                self.config
            )
            logging.info("README regeneration completed")
        except Exception as e:
            logging.warning(f"Intelligent README generation failed: {e}")
            try:
                content = await generate_static_root_readme(
                    self.config.knowledge_base_dir,
                    self.category_manager
                )
                readme_path = self.config.knowledge_base_dir / "README.md"
                async with aiofiles.open(readme_path, 'w', encoding='utf-8') as f:
                    await f.write(content)
                logging.info("Generated static README as fallback")
            except Exception as static_e:
                 logging.error(f"Static README generation also failed: {static_e}")
                 # Raise the original error or a new one
                 raise e from static_e

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