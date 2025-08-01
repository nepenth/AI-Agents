from pathlib import Path
from typing import List, Dict, Any, Callable, Optional, NamedTuple
import logging
import re # For filename sanitization
from knowledge_base_agent.config import Config
from knowledge_base_agent.http_client import HTTPClient
from knowledge_base_agent.database_state_manager import DatabaseStateManager
from knowledge_base_agent.playwright_fetcher import fetch_tweet_data_playwright, expand_url
from urllib.parse import urlparse
import json
import os
from typing import Tuple
from dataclasses import dataclass

@dataclass
class CacheTweetsSummary:
    total_processed: int = 0
    successfully_cached: int = 0 # Includes newly cached and already_complete_skipped
    newly_cached_or_updated: int = 0 # Specifically those that went through the caching logic
    failed_cache: int = 0
    skipped_already_complete: int = 0

async def cache_tweets(
    tweet_ids: List[str], 
    config: Config, 
    http_client: HTTPClient, 
    state_manager: DatabaseStateManager, 
    force_recache: bool = False,
    progress_callback: Optional[Callable[[str, str, str, bool, Optional[int], Optional[int], Optional[int]], None]] = None,
    phase_id_for_progress: str = "subphase_cp_cache" # Default phase_id for progress reporting
) -> CacheTweetsSummary:
    """Cache tweet data including expanded URLs and verifying/downloading all media. Handles threads."""
    summary = CacheTweetsSummary(total_processed=len(tweet_ids))
    
    for idx, bookmarked_tweet_id in enumerate(tweet_ids):
        current_processed_for_callback = idx + 1

        if progress_callback:
            progress_callback(
                phase_id_for_progress,
                'active', # status
                f'Caching tweet {bookmarked_tweet_id}', # message (status_message for client)
                True, # is_sub_step_update
                current_processed_for_callback, # processed_count
                summary.total_processed, # total_count
                summary.failed_cache # error_count (cumulative)
            )

        overall_cache_success_for_thread = True
        try:
            # Get existing state for the bookmarked tweet ID
            # This tweet_data will store the entire thread's information if it's a thread.
            tweet_data = state_manager.get_tweet(bookmarked_tweet_id) or {}

            needs_processing = force_recache or not tweet_data.get('cache_complete', False)

            if not needs_processing:
                logging.info(f"Thread/Tweet {bookmarked_tweet_id} already fully cached (cache_complete=True), skipping...")
                summary.skipped_already_complete += 1
                summary.successfully_cached += 1 # Count skips as successful from caching point of view
                continue

            logging.info(f"Processing cache for thread/tweet {bookmarked_tweet_id} (force_recache={force_recache}, cache_complete={tweet_data.get('cache_complete', False)})")
            summary.newly_cached_or_updated += 1 # It's being processed now

            # --- Fetch Core Tweet Data (potentially a thread) ---
            # If force_recache or no thread_tweets key (means it was never fetched or is old format)
            if force_recache or not tweet_data.get('thread_tweets'):
                tweet_url = f"https://twitter.com/i/web/status/{bookmarked_tweet_id}"
                logging.info(f"Fetching core data for thread/tweet {bookmarked_tweet_id} from {tweet_url}")
                
                # fetch_tweet_data_playwright now returns List[Dict[str, Any]]
                fetched_thread_segments = await fetch_tweet_data_playwright(tweet_url, config)
                
                if not fetched_thread_segments:
                    logging.error(f"Failed to fetch any data for tweet/thread {bookmarked_tweet_id}, skipping.")
                    overall_cache_success_for_thread = False
                    # Update state to reflect failure before continuing
                    tweet_data['cache_complete'] = False
                    state_manager.update_tweet_data(bookmarked_tweet_id, tweet_data)
                    summary.failed_cache += 1
                    continue 

                # Initialize or reset tweet_data structure for thread
                tweet_data = {
                    'bookmarked_tweet_id': bookmarked_tweet_id,
                    'is_thread': len(fetched_thread_segments) > 1,
                    'thread_tweets': fetched_thread_segments, # List of dicts, each a tweet segment
                    'all_downloaded_media_for_thread': [],
                    'urls_expanded': False,
                    'media_processed': False,
                    'cache_complete': False, # Will be set to True at the end if all steps succeed
                    # Preserve other potential flags if they exist from a previous partial run
                    'categories_processed': tweet_data.get('categories_processed', False),
                    'kb_item_created': tweet_data.get('kb_item_created', False),
                    'raw_json_content': tweet_data.get('raw_json_content', None),
                    'kb_media_paths': tweet_data.get('kb_media_paths', None),
                    'display_title': tweet_data.get('display_title', None)
                }
                logging.info(f"Fetched {len(fetched_thread_segments)} segments for tweet/thread {bookmarked_tweet_id}. Main author: {fetched_thread_segments[0].get('author_handle') if fetched_thread_segments else 'N/A'}")
            else:
                 logging.debug(f"Using existing fetched thread_tweets data for {bookmarked_tweet_id}")

            # --- Expand URLs (for each tweet segment in the thread) ---
            # Needs expansion if forced OR if the 'urls_expanded' flag is false
            if force_recache or not tweet_data.get('urls_expanded', False):
                logging.info(f"Expanding URLs for thread {bookmarked_tweet_id}")
                all_urls_expanded_successfully = True
                for segment_idx, segment_data in enumerate(tweet_data.get('thread_tweets', [])):
                    segment_data['expanded_urls'] = [] # Initialize/reset
                    if not segment_data.get('urls'): # Ensure 'urls' key exists
                        segment_data['urls'] = []

                    for original_url in segment_data.get('urls', []):
                        try:
                            expanded = await expand_url(original_url)
                            segment_data['expanded_urls'].append(expanded)
                        except Exception as e:
                            logging.warning(f"Failed to expand URL {original_url} in segment {segment_idx} for thread {bookmarked_tweet_id}: {e}")
                            segment_data['expanded_urls'].append(original_url) # Keep original on failure
                            all_urls_expanded_successfully = False # Mark overall expansion as potentially incomplete
                
                tweet_data['urls_expanded'] = True # Mark as attempted. Success depends on individual items.
                if not all_urls_expanded_successfully:
                    logging.warning(f"One or more URLs failed to expand for thread {bookmarked_tweet_id}")
                    # overall_cache_success_for_thread = False # Decided not to fail cache for this
            else:
                logging.debug(f"URLs already marked as expanded for thread {bookmarked_tweet_id}")

            # --- Download/Verify Media (for each tweet segment in the thread) ---
            # Needs media processing if forced OR if 'media_processed' flag is false
            if force_recache or not tweet_data.get('media_processed', False):
                logging.info(f"Verifying/downloading media for thread {bookmarked_tweet_id}")
                # config.media_cache_dir is now an absolute path
                media_base_dir_abs = config.media_cache_dir 
                media_dir_for_tweet_abs = media_base_dir_abs / bookmarked_tweet_id 
                media_dir_for_tweet_abs.mkdir(parents=True, exist_ok=True)
                
                # Reset aggregated list if forcing recache
                if force_recache:
                    tweet_data['all_downloaded_media_for_thread'] = []
                
                # Store relative paths in current_thread_media_paths_set
                current_thread_media_paths_set = set(tweet_data.get('all_downloaded_media_for_thread', []))
                any_media_download_failed_in_thread = False

                for segment_idx, segment_data in enumerate(tweet_data.get('thread_tweets', [])):
                    # Store relative paths in downloaded_media_paths_for_segment
                    segment_data['downloaded_media_paths_for_segment'] = [] 
                    if not segment_data.get('media_item_details'): # Ensure key exists
                        segment_data['media_item_details'] = []

                    for media_idx, media_item in enumerate(segment_data.get('media_item_details', [])):
                        try:
                            url = media_item.get('url')
                            media_type = media_item.get('type', 'image')
                            if not url:
                                logging.warning(f"No URL in media_item {media_idx} for segment {segment_idx}, thread {bookmarked_tweet_id}")
                                continue

                            parsed_url = urlparse(url)
                            original_ext = Path(parsed_url.path).suffix or ('.mp4' if media_type == 'video' else '.jpg')
                            sane_ext = ''.join(c for c in original_ext if c.isalnum() or c == '.').lower()[:10]
                            if not sane_ext.startswith('.'): sane_ext = '.' + sane_ext

                            media_filename = f"media_seg{segment_idx}_item{media_idx}{sane_ext}"
                            # Absolute path for download operation
                            media_path_abs = media_dir_for_tweet_abs / media_filename
                            # Relative path for storage in tweet_cache.json
                            media_path_rel_to_project = config.get_relative_path(media_path_abs)

                            should_download = force_recache or not media_path_abs.exists()
                            if should_download:
                                if not media_path_abs.exists():
                                    logging.info(f"Media missing: {media_path_abs}. Downloading {url}...")
                                else: # force_recache must be true
                                    logging.info(f"Forcing re-download of: {media_path_abs} from {url}")
                                
                                await http_client.download_media(url, media_path_abs)
                                if not media_path_abs.exists():
                                    logging.error(f"Media download FAILED for {url} (-> {media_path_abs}) for thread {bookmarked_tweet_id}")
                                    any_media_download_failed_in_thread = True
                                    current_thread_media_paths_set.discard(str(media_path_rel_to_project))
                                    continue # Skip adding path if download failed
                            
                            # If file exists (either pre-existing or just downloaded)
                            if media_path_abs.exists():
                                segment_data['downloaded_media_paths_for_segment'].append(str(media_path_rel_to_project))
                                current_thread_media_paths_set.add(str(media_path_rel_to_project))
                            else:
                                logging.warning(f"Media path {media_path_abs} confirmed non-existent after check/download for thread {bookmarked_tweet_id}")
                                any_media_download_failed_in_thread = True
                                current_thread_media_paths_set.discard(str(media_path_rel_to_project))

                        except Exception as e:
                            logging.error(f"Error processing media_item {media_idx} in segment {segment_idx} for thread {bookmarked_tweet_id}: {e}", exc_info=True)
                            any_media_download_failed_in_thread = True
                            continue
                
                tweet_data['all_downloaded_media_for_thread'] = sorted(list(current_thread_media_paths_set))
                tweet_data['media_processed'] = True # Mark as attempted
                if any_media_download_failed_in_thread:
                    logging.warning(f"One or more media downloads/verifications failed for thread {bookmarked_tweet_id}")
                    overall_cache_success_for_thread = False
            else:
                logging.debug(f"Media already marked as processed for thread {bookmarked_tweet_id}")

            # --- Final Update for this thread/tweet ---
            if overall_cache_success_for_thread and tweet_data.get('urls_expanded') and tweet_data.get('media_processed'):
                 # Check if thread_tweets is populated - essential for cache to be complete
                 if tweet_data.get('thread_tweets'):
                    # CRITICAL FIX: Populate top-level full_text field from thread segments
                    # This ensures compatibility with downstream processing (AI categorization, DB sync, etc.)
                    thread_segments = tweet_data.get('thread_tweets', [])
                    if thread_segments:
                        all_texts = []
                        for i, segment in enumerate(thread_segments):
                            segment_text = segment.get("full_text", "") or segment.get("text_content", "")
                            if segment_text and segment_text.strip():
                                if len(thread_segments) > 1:
                                    all_texts.append(f"Segment {i+1}: {segment_text}")
                                else:
                                    all_texts.append(segment_text)
                        
                        combined_text = "\n\n".join(all_texts)
                        if combined_text.strip():
                            tweet_data['full_text'] = combined_text
                            logging.info(f"✅ Populated top-level full_text for {bookmarked_tweet_id} (length: {len(combined_text)})")
                        else:
                            tweet_data['full_text'] = f"Tweet {bookmarked_tweet_id} (content not available)"
                            logging.warning(f"⚠️ No usable text content found in thread segments for {bookmarked_tweet_id}")
                    else:
                        tweet_data['full_text'] = f"Tweet {bookmarked_tweet_id} (content not available)"
                        logging.warning(f"⚠️ No thread segments found for {bookmarked_tweet_id}")
                    
                    tweet_data['cache_complete'] = True
                    logging.info(f"Successfully processed cache for thread/tweet {bookmarked_tweet_id}")
                    summary.successfully_cached += 1 # Add to successful count
                 else:
                    tweet_data['cache_complete'] = False
                    logging.warning(f"Cache for thread/tweet {bookmarked_tweet_id} incomplete: thread_tweets list is empty/missing.")
            else:
                 tweet_data['cache_complete'] = False
                 logging.warning(f"Cache processing for thread/tweet {bookmarked_tweet_id} marked incomplete. Success: {overall_cache_success_for_thread}, URLs Expanded: {tweet_data.get('urls_expanded')}, Media Processed: {tweet_data.get('media_processed')}")

            state_manager.update_tweet_data(bookmarked_tweet_id, tweet_data)

        except Exception as e:
            logging.error(f"Unhandled exception caching thread/tweet {bookmarked_tweet_id}: {e}", exc_info=True)
            try:
                # Attempt to get the latest state and mark as incomplete
                current_data = state_manager.get_tweet(bookmarked_tweet_id) or {}
                current_data['cache_complete'] = False
                state_manager.update_tweet_data(bookmarked_tweet_id, current_data)
                logging.info(f"Marked thread/tweet {bookmarked_tweet_id} cache_complete=False due to unhandled exception during caching.")
                summary.failed_cache += 1
            except Exception as inner_e:
                 logging.error(f"Failed to mark thread/tweet {bookmarked_tweet_id} as incomplete after outer exception: {inner_e}")
            continue # Move to next bookmarked_tweet_id
    
    if progress_callback: # Final update for the caching phase
        final_status = 'completed' if summary.failed_cache == 0 else 'completed_with_errors'
        progress_callback(
            phase_id_for_progress,
            final_status, 
            f'Tweet caching finished. Processed: {summary.total_processed}, Cached/Updated: {summary.newly_cached_or_updated}, Skipped: {summary.skipped_already_complete}, Errors: {summary.failed_cache}',
            False, # This is a final update for the main step associated with this batch
            summary.successfully_cached, # Processed for callback: successfully_cached includes skipped
            summary.total_processed,
            summary.failed_cache
        )
    return summary

class TweetCacheValidator:
    """Validates the integrity of the tweet cache and fixes inconsistencies.
    
    Retained for compatibility but likely redundant since StateManager now handles comprehensive validation.
    Consider removing if no other code references this class explicitly.
    """
    
    def __init__(self, config: Config): # Takes Config now
        self.config = config # Store config
        # Note: tweet_cache_file removed - now using database
        self.media_cache_dir = config.media_cache_dir # Absolute path
        self.kb_base_dir = config.knowledge_base_dir # Absolute path
        self.tweet_cache = {}
        self.modified_tweets = set()
        self.validation_results = {
            'media_files_missing': [],
            'image_descriptions_missing': [], # This might map to alt_text in media_item_details now
            'categories_incomplete': [],
            'kb_items_missing': []
        }
        
    async def load_tweet_cache(self) -> Dict[str, Any]:
        """Load the tweet cache from database."""
        try:
            from flask import current_app
            from .models import TweetCache
            
            if not current_app:
                logging.warning("No Flask app context available, returning empty cache")
                return {}
                
            with current_app.app_context():
                # Load all tweets from database
                cached_tweets = TweetCache.query.all()
                tweet_cache = {}
                
                for tweet in cached_tweets:
                    tweet_cache[tweet.tweet_id] = {
                        'cache_complete': tweet.cache_complete,
                        'categories_processed': tweet.categories_processed,
                        'kb_item_created': tweet.kb_item_created,
                        'kb_item_path': tweet.kb_item_path,
                        'categories': tweet.categories or {},
                        'all_downloaded_media_for_thread': tweet.all_downloaded_media_for_thread or [],
                        'is_thread': tweet.is_thread,
                        # Add other fields as needed
                    }
                
                logging.info(f"Loaded {len(tweet_cache)} tweets from database")
                return tweet_cache
                
        except Exception as e:
            logging.error(f"Failed to load tweet cache from database: {e}")
            return {}
    
    async def save_tweet_cache(self) -> None:
        """Save the tweet cache to database."""
        try:
            from flask import current_app
            from .models import TweetCache, db
            
            if not current_app:
                logging.warning("No Flask app context available, cannot save tweet cache to database")
                return
                
            with current_app.app_context():
                # Update modified tweets in database
                for tweet_id in self.modified_tweets:
                    if tweet_id in self.tweet_cache:
                        tweet_data = self.tweet_cache[tweet_id]
                        
                        # Find existing tweet or create new one
                        existing_tweet = TweetCache.query.filter_by(tweet_id=tweet_id).first()
                        if existing_tweet:
                            # Update existing tweet
                            existing_tweet.cache_complete = tweet_data.get('cache_complete', False)
                            existing_tweet.categories_processed = tweet_data.get('categories_processed', False)
                            existing_tweet.kb_item_created = tweet_data.get('kb_item_created', False)
                            existing_tweet.kb_item_path = tweet_data.get('kb_item_path')
                            existing_tweet.categories = tweet_data.get('categories', {})
                            existing_tweet.all_downloaded_media_for_thread = tweet_data.get('all_downloaded_media_for_thread', [])
                            existing_tweet.is_thread = tweet_data.get('is_thread', False)
                        else:
                            # Create new tweet (though this shouldn't happen in validation)
                            logging.warning(f"Creating new tweet record during validation for {tweet_id}")
                
                db.session.commit()
                logging.info(f"Saved validated tweet cache with {len(self.modified_tweets)} modifications to database")
                
        except Exception as e:
            logging.error(f"Failed to save tweet cache to database: {e}")
            raise
    
    async def validate(self) -> Tuple[int, int]:
        """
        Validate the tweet cache and fix inconsistencies.
        
        Returns:
            Tuple containing (total_tweets, modified_tweets)
        """
        self.tweet_cache = await self.load_tweet_cache()
        total_tweets = len(self.tweet_cache)
        self.modified_tweets = set()
        
        # Print KB directory structure for debugging
        self.print_kb_directory_structure()
        
        # Reset validation results
        for key in self.validation_results:
            self.validation_results[key] = []
        
        for tweet_id, tweet_data in self.tweet_cache.items():
            # Skip tweets that aren't marked as complete
            if not tweet_data.get('cache_complete', False):
                continue
            
            # THIS VALIDATION LOGIC NEEDS TO BE UPDATED FOR THREADS
            # For now, it will likely misinterpret the new structure.
            # Placeholder: just log that it needs update
            if tweet_data.get('is_thread', False):
                logging.debug(f"TweetCacheValidator: Validation for thread {tweet_id} needs update.")

            # Validate downloaded media (old logic, needs update for threads)
            if self._validate_media(tweet_id, tweet_data): # This will use 'downloaded_media' key which is removed/renamed
                self.modified_tweets.add(tweet_id)
                
            # Validate image descriptions (old logic)
            # if self._validate_image_descriptions(tweet_id, tweet_data):
            #     self.modified_tweets.add(tweet_id)
                
            # Validate categories (likely still okay if categories apply to whole thread)
            if self._validate_categories(tweet_id, tweet_data):
                self.modified_tweets.add(tweet_id)
                
            # Validate KB item (likely still okay if kb_item_path applies to whole thread)
            if self._validate_kb_item(tweet_id, tweet_data):
                self.modified_tweets.add(tweet_id)
        
        # Log detailed validation results
        self._log_validation_results()
        
        if self.modified_tweets:
            await self.save_tweet_cache()
            
        return total_tweets, len(self.modified_tweets)
    
    def _validate_media(self, tweet_id: str, tweet_data: Dict[str, Any]) -> bool:
        # THIS METHOD IS NOW OUTDATED FOR THREADS. IT EXPECTS a flat 'downloaded_media' list.
        # It should iterate through 'all_downloaded_media_for_thread' if validating threads.
        modified = False
        
        # If it's a thread, use the new field, otherwise try the old field for non-thread items (if any exist)
        media_list_to_check = tweet_data.get('all_downloaded_media_for_thread') # New field for threads
        if media_list_to_check is None: # Fallback for potentially old, non-thread items
            media_list_to_check = tweet_data.get('downloaded_media', [])

        if not media_list_to_check and tweet_data.get('is_thread'): # For threads, this list should exist
            logging.debug(f"Thread {tweet_id} has no 'all_downloaded_media_for_thread' list. Marking modified.")
            # tweet_data['cache_complete'] = False # Handled by main cache_tweets logic
            # self.validation_results['media_files_missing'].append({'tweet_id': tweet_id, 'reason': 'missing aggregated list'})
            # modified = True
            # return modified # No media to check

        for i, media_path_rel_str in enumerate(media_list_to_check):
            # Resolve the relative path to absolute for checking existence
            media_file_abs = self.config.resolve_path_from_project_root(media_path_rel_str)
            if not media_file_abs.exists():
                logging.debug(f"Media file {media_file_abs} (from relative {media_path_rel_str}) for tweet/thread {tweet_id} not found")
                self.validation_results['media_files_missing'].append({
                    'tweet_id': tweet_id,
                    'media_path': media_path_rel_str # Store the relative path
                })
                modified = True # A file is missing
        
        return modified
    
    def _validate_image_descriptions(self, tweet_id: str, tweet_data: Dict[str, Any]) -> bool:
        # THIS METHOD IS OUTDATED. Descriptions are now 'alt_text' within 'media_item_details' per segment.
        # Needs to iterate through tweet_data['thread_tweets'][segment_idx]['media_item_details']
        modified = False
        # logging.debug(f"Skipping _validate_image_descriptions for {tweet_id} as it needs update for threads.")
        return modified 
    # ... rest of TweetCacheValidator (likely needs significant review/removal) ...
    def _validate_categories(self, tweet_id: str, tweet_data: Dict[str, Any]) -> bool:
        # ... existing code ...
        modified = False
        
        if tweet_data.get('categories_processed', False):
            categories = tweet_data.get('categories', {})
            required_fields = ['main_category', 'sub_category', 'item_name']
            
            if not categories or not all(field in categories for field in required_fields):
                logging.debug(f"Tweet {tweet_id} marked as categories_processed but missing required category fields")
                tweet_data['categories_processed'] = False
                missing_fields = [field for field in required_fields if field not in categories]
                self.validation_results['categories_incomplete'].append({
                    'tweet_id': tweet_id,
                    'missing_fields': missing_fields
                })
                modified = True
        
        return modified
    
    def _validate_kb_item(self, tweet_id: str, tweet_data: Dict[str, Any]) -> bool:
        # ... existing code ...
        modified = False
        
        if tweet_data.get('kb_item_created', False):
            kb_path = tweet_data.get('kb_item_path')
            
            if not kb_path:
                logging.warning(f"Tweet {tweet_id} marked as kb_item_created but missing kb_item_path")
                tweet_data['kb_item_created'] = False
                self.validation_results['kb_items_missing'].append({
                    'tweet_id': tweet_id,
                    'reason': 'missing_path'
                })
                modified = True
            else:
                # Normalize the path from cache (relative to project root)
                kb_path_rel_str = kb_path.rstrip('/')
                
                # Resolve to absolute path for checking
                full_path_abs = self.config.resolve_path_from_project_root(kb_path_rel_str)
                
                logging.debug(f"Checking KB item existence: {full_path_abs} (from relative path {kb_path_rel_str})")
                
                path_exists = False
                
                if full_path_abs.exists():
                    path_exists = True
                    logging.debug(f"KB item exists at exact path: {full_path_abs}")
                
                elif full_path_abs.is_dir() and (full_path_abs / "README.md").exists():
                    path_exists = True
                    logging.debug(f"KB item exists as README.md in directory: {full_path_abs / 'README.md'}")
                
                if not path_exists:
                    logging.warning(f"KB item {kb_path_rel_str} for tweet {tweet_id} not found at resolved path {full_path_abs}")
                    tweet_data['kb_item_created'] = False
                    self.validation_results['kb_items_missing'].append({
                        'tweet_id': tweet_id,
                        'kb_path': kb_path_rel_str,
                        'reason': 'file_not_found'
                    })
                    modified = True
        
        return modified
    
    def _log_validation_results(self) -> None:
        # ... existing code ...
        logging.info("=== Knowledge Base Directory Structure ===")
        # These attributes kb_categories, etc. are not set in this class, they were part of an older context.
        # This method needs to be updated or removed if the validator is refactored.
        # For now, commenting out potentially problematic lines.
        # logging.info(f"Categories: {len(self.kb_categories)}") 
        # logging.info(f"Subcategories: {len(self.kb_subcategories)}")
        # logging.info(f"README.md files: {self.kb_readme_count}")
        # logging.info(f"Other Markdown files: {self.kb_other_md_count}")
        # logging.info(f"Media files: {self.kb_media_count}")
        # logging.info(f"Other files: {self.kb_other_files_count}")
        pass

    def print_kb_directory_structure(self) -> None:
        # ... existing code ...
        logging.info("=== Knowledge Base Directory Structure ===")
        
        # Count files by type
        md_files = 0
        readme_files = 0
        media_files = 0
        other_files = 0
        
        # Track categories and subcategories
        categories = set()
        subcategories = set()
        
        for root, dirs, files in os.walk(self.kb_base_dir): # kb_base_dir is absolute
            root_path = Path(root)
            # Make rel_path relative to kb_base_dir for category/subcategory logic
            rel_path = root_path.relative_to(self.kb_base_dir) 
            
            # Skip hidden directories
            if any(part.startswith('.') for part in rel_path.parts):
                continue
            
            # Track categories and subcategories
            if len(rel_path.parts) >= 1 and rel_path.parts[0]:
                categories.add(rel_path.parts[0])
            if len(rel_path.parts) >= 2:
                subcategories.add(f"{rel_path.parts[0]}/{rel_path.parts[1]}")
            
            # Count files by type
            for file in files:
                if file.lower() == "readme.md":
                    readme_files += 1
                elif file.lower().endswith('.md'):
                    md_files += 1
                elif any(file.lower().endswith(ext) for ext in ['.jpg', '.jpeg', '.png', '.gif', '.webp']):
                    media_files += 1
                else:
                    other_files += 1
        
        logging.info(f"Categories: {len(categories)}")
        logging.info(f"Subcategories: {len(subcategories)}")
        logging.info(f"README.md files: {readme_files}")
        logging.info(f"Other Markdown files: {md_files}")
        logging.info(f"Media files: {media_files}")
        logging.info(f"Other files: {other_files}")
        
        if categories:
            logging.info("Sample categories:")
            for category in sorted(list(categories))[:5]:
                logging.info(f"  - {category}")
        
        if subcategories:
            logging.info("Sample subcategories:")
            for subcategory in sorted(list(subcategories))[:5]:
                logging.info(f"  - {subcategory}")