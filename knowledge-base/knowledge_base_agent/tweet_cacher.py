from pathlib import Path
from typing import List, Dict, Any
import logging
from knowledge_base_agent.config import Config
from knowledge_base_agent.http_client import HTTPClient
from knowledge_base_agent.state_manager import StateManager
from knowledge_base_agent.playwright_fetcher import fetch_tweet_data_playwright, expand_url
from urllib.parse import urlparse
import json
import os
from typing import Tuple

async def cache_tweets(tweet_ids: List[str], config: Config, http_client: HTTPClient, state_manager: StateManager, force_recache: bool = False) -> None:
    """Cache tweet data including expanded URLs and verifying/downloading all media."""
    cached_tweets = await state_manager.get_all_tweets()

    for tweet_id in tweet_ids:
        tweet_successfully_cached_this_run = True # Flag for this specific attempt
        try:
            existing_tweet = cached_tweets.get(tweet_id, {})
            # Determine if processing is needed based on force flag or incomplete cache state
            needs_processing = force_recache or not existing_tweet.get('cache_complete', False)

            if not needs_processing:
                logging.info(f"Tweet {tweet_id} already fully cached (cache_complete=True), skipping...")
                continue

            logging.info(f"Processing cache for tweet {tweet_id} (force_recache={force_recache}, cache_complete={existing_tweet.get('cache_complete', False)})")

            # --- Fetch Core Tweet Data (if needed) ---
            tweet_data = existing_tweet if existing_tweet else {}
            if not tweet_data or force_recache:
                tweet_url = f"https://twitter.com/i/web/status/{tweet_id}"
                logging.info(f"Fetching core data for tweet {tweet_id}")
                fetched_data = await fetch_tweet_data_playwright(tweet_url, config)
                if not fetched_data:
                    logging.error(f"Failed to fetch core data for tweet {tweet_id}, skipping")
                    tweet_successfully_cached_this_run = False
                    continue # Cannot proceed without core data
                # Merge fetched data
                tweet_data.update(fetched_data)
                # Reset dependent flags if forcing a full recache
                if force_recache:
                    tweet_data['urls_expanded'] = False
                    tweet_data['downloaded_media'] = []
                    tweet_data['media_processed'] = False
                    tweet_data['categories_processed'] = False
                    tweet_data['kb_item_created'] = False
            else:
                 logging.debug(f"Using existing core data for tweet {tweet_id}")

            # --- Expand URLs (if needed) ---
            urls_present = 'urls' in tweet_data and tweet_data['urls']
            needs_url_expansion = urls_present and (force_recache or not tweet_data.get('urls_expanded', False))

            if needs_url_expansion:
                logging.info(f"Expanding URLs for tweet {tweet_id}")
                expanded_urls = []
                # url_expansion_failed = False # Optional: track if any single URL fails
                for url in tweet_data.get('urls', []):
                    try:
                        expanded = await expand_url(url)
                        expanded_urls.append(expanded)
                    except Exception as e:
                        logging.warning(f"Failed to expand URL {url} for tweet {tweet_id}: {e}")
                        expanded_urls.append(url) # Keep original on failure
                        # url_expansion_failed = True
                # if url_expansion_failed: tweet_successfully_cached_this_run = False
                tweet_data['urls'] = expanded_urls
                tweet_data['urls_expanded'] = True # Mark expanded even if some failed to expand
            elif urls_present:
                 logging.debug(f"URLs already expanded for tweet {tweet_id}")

            # --- Download/Verify Media (if needed) ---
            media_present = 'media' in tweet_data and tweet_data['media']
            # Trigger media check/download if media exists AND (forced or cache was incomplete)
            needs_media_processing = media_present and needs_processing

            if needs_media_processing:
                logging.info(f"Verifying/downloading media for tweet {tweet_id}")
                media_dir = Path(config.media_cache_dir) / tweet_id
                media_dir.mkdir(parents=True, exist_ok=True)
                # Start with existing list unless forcing full recache
                downloaded_media_paths = tweet_data.get('downloaded_media', []) if not force_recache else []
                current_media_paths_set = set(downloaded_media_paths) # For efficient adding check
                media_download_failed = False

                for idx, media_item in enumerate(tweet_data.get('media', [])):
                    try:
                        url = media_item.get('url', '') if isinstance(media_item, dict) else str(media_item)
                        media_type = media_item.get('type', 'image') if isinstance(media_item, dict) else 'image'
                        if not url:
                            logging.warning(f"No valid URL in media item {idx} for tweet {tweet_id}")
                            continue

                        # Determine expected filename
                        ext = '.mp4' if media_type == 'video' else (Path(urlparse(url).path).suffix or '.jpg')
                        ext = ''.join(c for c in ext if c.isalnum() or c == '.')[:5] # Sanitize extension
                        media_filename = f"media_{idx}{ext}"
                        media_path = media_dir / media_filename
                        media_path_str = str(media_path)

                        # Download if forced OR if the file doesn't exist
                        if force_recache or not media_path.exists():
                             if not media_path.exists():
                                 logging.info(f"Media file missing: {media_path}. Downloading...")
                             else: # force_recache must be true
                                 logging.info(f"Forcing re-download of media: {media_path}")

                             await http_client.download_media(url, media_path)
                             if not media_path.exists():
                                 logging.error(f"Media download FAILED for {url} (-> {media_path})")
                                 media_download_failed = True
                                 # Remove path from set if download failed and it was there before (e.g. during force_recache)
                                 current_media_paths_set.discard(media_path_str)
                                 continue # Skip adding path if download failed

                        # Ensure path is in the list if the file exists now
                        if media_path.exists():
                            current_media_paths_set.add(media_path_str)
                        else:
                            # If file doesn't exist after check/download attempt, something is wrong
                            logging.warning(f"Media path {media_path_str} confirmed non-existent after check/download attempt for tweet {tweet_id}")
                            media_download_failed = True
                            current_media_paths_set.discard(media_path_str) # Ensure it's not in the final list

                    except Exception as e:
                        logging.error(f"Error processing media item {idx} for tweet {tweet_id}: {e}", exc_info=True)
                        media_download_failed = True
                        continue # Skip this item on error

                # Update the list in tweet_data based on the final set of existing files
                tweet_data['downloaded_media'] = sorted(list(current_media_paths_set)) # Sort for consistency

                # If any download/check failed, the overall cache isn't complete for this run
                if media_download_failed:
                    tweet_successfully_cached_this_run = False
                    logging.warning(f"One or more media downloads/verifications failed for tweet {tweet_id}, marking cache incomplete for this run.")

            elif media_present:
                 logging.debug(f"Media check skipped for tweet {tweet_id} as cache was already complete and force_recache=False.")

            # --- Final Update ---
            # Only mark cache_complete True if all required steps *for this run* succeeded
            if tweet_successfully_cached_this_run:
                 tweet_data['cache_complete'] = True
                 logging.info(f"Successfully processed cache for tweet {tweet_id}")
            else:
                 # Ensure cache_complete is false if any step failed
                 tweet_data['cache_complete'] = False
                 logging.warning(f"Cache processing incomplete for tweet {tweet_id} in this run, cache_complete set to False.")

            # Always save the latest state back to StateManager
            await state_manager.update_tweet_data(tweet_id, tweet_data)

        except Exception as e:
            logging.error(f"Unhandled exception caching tweet {tweet_id}: {e}", exc_info=True)
            # Attempt to mark as incomplete in state manager on unexpected error
            try:
                failed_tweet_data = await state_manager.get_tweet(tweet_id) # Get latest state again
                if failed_tweet_data:
                     failed_tweet_data['cache_complete'] = False
                     await state_manager.update_tweet_data(tweet_id, failed_tweet_data)
                     logging.info(f"Marked tweet {tweet_id} cache_complete=False due to unhandled exception.")
            except Exception as inner_e:
                 logging.error(f"Failed to mark tweet {tweet_id} as incomplete after outer exception: {inner_e}")
            continue # Move to next tweet

class TweetCacheValidator:
    """Validates the integrity of the tweet cache and fixes inconsistencies.
    
    Retained for compatibility but likely redundant since StateManager now handles comprehensive validation.
    Consider removing if no other code references this class explicitly.
    """
    
    def __init__(self, tweet_cache_path: Path, media_cache_dir: Path, kb_base_dir: Path):
        self.tweet_cache_path = tweet_cache_path
        self.media_cache_dir = media_cache_dir
        self.kb_base_dir = kb_base_dir
        self.tweet_cache = {}
        self.modified_tweets = set()
        self.validation_results = {
            'media_files_missing': [],
            'image_descriptions_missing': [],
            'categories_incomplete': [],
            'kb_items_missing': []
        }
        
    async def load_tweet_cache(self) -> Dict[str, Any]:
        """Load the tweet cache from disk."""
        if not self.tweet_cache_path.exists():
            logging.warning(f"Tweet cache file not found at {self.tweet_cache_path}")
            return {}
            
        try:
            with open(self.tweet_cache_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except json.JSONDecodeError:
            logging.error(f"Failed to parse tweet cache JSON at {self.tweet_cache_path}")
            return {}
    
    async def save_tweet_cache(self) -> None:
        """Save the tweet cache to disk."""
        with open(self.tweet_cache_path, 'w', encoding='utf-8') as f:
            json.dump(self.tweet_cache, f, indent=2)
        logging.info(f"Saved validated tweet cache with {len(self.modified_tweets)} modifications")
    
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
                
            # Validate downloaded media
            if self._validate_media(tweet_id, tweet_data):
                self.modified_tweets.add(tweet_id)
                
            # Validate image descriptions
            if self._validate_image_descriptions(tweet_id, tweet_data):
                self.modified_tweets.add(tweet_id)
                
            # Validate categories
            if self._validate_categories(tweet_id, tweet_data):
                self.modified_tweets.add(tweet_id)
                
            # Validate KB item
            if self._validate_kb_item(tweet_id, tweet_data):
                self.modified_tweets.add(tweet_id)
        
        # Log detailed validation results
        self._log_validation_results()
        
        if self.modified_tweets:
            await self.save_tweet_cache()
            
        return total_tweets, len(self.modified_tweets)
    
    def _validate_media(self, tweet_id: str, tweet_data: Dict[str, Any]) -> bool:
        """
        Validate that all downloaded media files exist.
        
        Returns:
            True if modifications were made, False otherwise
        """
        modified = False
        
        if 'downloaded_media' not in tweet_data:
            return modified
            
        for i, media_path in enumerate(tweet_data['downloaded_media']):
            media_file = Path(media_path)
            if not media_file.exists():
                logging.debug(f"Media file {media_path} for tweet {tweet_id} not found")
                tweet_data['cache_complete'] = False
                self.validation_results['media_files_missing'].append({
                    'tweet_id': tweet_id,
                    'media_path': media_path
                })
                modified = True
        
        return modified
    
    def _validate_image_descriptions(self, tweet_id: str, tweet_data: Dict[str, Any]) -> bool:
        """
        Validate that image descriptions exist for all media.
        
        Returns:
            True if modifications were made, False otherwise
        """
        modified = False
        
        if 'media' not in tweet_data or not tweet_data.get('media'):
            return modified
            
        # Check if we have descriptions for all media
        if not tweet_data.get('image_descriptions') or len(tweet_data.get('image_descriptions', [])) < len(tweet_data.get('media', [])):
            if tweet_data.get('media_processed', False):
                logging.debug(f"Tweet {tweet_id} marked as media_processed but missing image descriptions")
                tweet_data['media_processed'] = False
                self.validation_results['image_descriptions_missing'].append({
                    'tweet_id': tweet_id,
                    'media_count': len(tweet_data.get('media', [])),
                    'descriptions_count': len(tweet_data.get('image_descriptions', []))
                })
                modified = True
        
        return modified
    
    def _validate_categories(self, tweet_id: str, tweet_data: Dict[str, Any]) -> bool:
        """
        Validate that categories are properly set.
        
        Returns:
            True if modifications were made, False otherwise
        """
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
        """
        Validate that KB item exists if marked as created.
        
        Returns:
            True if modifications were made, False otherwise
        """
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
                # Normalize the path
                kb_path = kb_path.rstrip('/')
                
                # Check if the path already includes kb-generated prefix
                if kb_path.startswith('kb-generated/'):
                    check_path = kb_path[len('kb-generated/'):]
                    full_path = self.kb_base_dir / check_path
                else:
                    full_path = self.kb_base_dir / kb_path
                
                # Debug output to see what we're checking
                logging.debug(f"Checking KB item existence: {full_path} (from path {kb_path})")
                
                # Try different path variations
                path_exists = False
                
                # Check if the exact path exists (file or directory)
                if full_path.exists():
                    path_exists = True
                    logging.debug(f"KB item exists at exact path: {full_path}")
                
                # Check if it's a directory with README.md inside
                elif full_path.is_dir() and (full_path / "README.md").exists():
                    path_exists = True
                    logging.debug(f"KB item exists as README.md in directory: {full_path / 'README.md'}")
                
                # Check if the parent directory exists with README.md
                elif full_path.parent.exists() and (full_path.parent / "README.md").exists():
                    path_exists = True
                    logging.debug(f"KB item exists as README.md in parent directory: {full_path.parent / 'README.md'}")
                
                # If we still haven't found it, try with the original path
                if not path_exists:
                    direct_path = Path(self.kb_base_dir.parent) / kb_path
                    if direct_path.exists():
                        path_exists = True
                        logging.debug(f"KB item exists at direct path: {direct_path}")
                    elif direct_path.is_dir() and (direct_path / "README.md").exists():
                        path_exists = True
                        logging.debug(f"KB item exists as README.md in direct path directory: {direct_path / 'README.md'}")
                
                if not path_exists:
                    repo_root = self.kb_base_dir.parent
                    repo_path = repo_root / kb_path
                    
                    if repo_path.exists():
                        path_exists = True
                        logging.debug(f"KB item exists at repository root: {repo_path}")
                    elif kb_path.endswith('README.md') and repo_path.parent.exists():
                        if repo_path.parent.is_dir() and (repo_path.parent / "README.md").exists():
                            path_exists = True
                            logging.debug(f"KB item exists as README.md in repository root directory: {repo_path.parent / 'README.md'}")
                
                if not path_exists:
                    logging.warning(f"KB item {kb_path} for tweet {tweet_id} not found at any expected location")
                    tweet_data['kb_item_created'] = False
                    self.validation_results['kb_items_missing'].append({
                        'tweet_id': tweet_id,
                        'kb_path': kb_path,
                        'reason': 'file_not_found'
                    })
                    modified = True
        
        return modified
    
    def _log_validation_results(self) -> None:
        """Log validation results."""
        logging.info("=== Knowledge Base Directory Structure ===")
        logging.info(f"Categories: {len(self.kb_categories)}")
        logging.info(f"Subcategories: {len(self.kb_subcategories)}")
        logging.info(f"README.md files: {self.kb_readme_count}")
        logging.info(f"Other Markdown files: {self.kb_other_md_count}")
        logging.info(f"Media files: {self.kb_media_count}")
        logging.info(f"Other files: {self.kb_other_files_count}")
        
        # Remove these lines that print sample categories and subcategories
        # logging.info("Sample categories:")
        # for category in list(self.kb_categories)[:5]:
        #     logging.info(f"  - {category}")
        # logging.info("Sample subcategories:")
        # for subcategory in list(self.kb_subcategories)[:5]:
        #     logging.info(f"  - {subcategory}")

    def print_kb_directory_structure(self) -> None:
        """Print the knowledge base directory structure for debugging."""
        logging.info("=== Knowledge Base Directory Structure ===")
        
        # Count files by type
        md_files = 0
        readme_files = 0
        media_files = 0
        other_files = 0
        
        # Track categories and subcategories
        categories = set()
        subcategories = set()
        
        for root, dirs, files in os.walk(self.kb_base_dir):
            root_path = Path(root)
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