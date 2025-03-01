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
    """Cache tweet data including expanded URLs and all media."""
    cached_tweets = await state_manager.get_all_tweets()

    for tweet_id in tweet_ids:
        try:
            existing_tweet = cached_tweets.get(tweet_id, {})
            if not force_recache and existing_tweet and existing_tweet.get('cache_complete', False):
                logging.info(f"Tweet {tweet_id} already fully cached, skipping...")
                continue

            tweet_data = existing_tweet if existing_tweet else {}
            if not tweet_data or force_recache:
                tweet_url = f"https://twitter.com/i/web/status/{tweet_id}"
                tweet_data = await fetch_tweet_data_playwright(tweet_url, config)
                if not tweet_data:
                    logging.error(f"Failed to fetch tweet {tweet_id}")
                    continue

            # Expand URLs if present and not already expanded
            if 'urls' in tweet_data and not tweet_data.get('urls_expanded', False):
                expanded_urls = []
                for url in tweet_data.get('urls', []):
                    try:
                        expanded = await expand_url(url)
                        expanded_urls.append(expanded)
                    except Exception as e:
                        logging.warning(f"Failed to expand URL {url}: {e}")
                        expanded_urls.append(url)
                tweet_data['urls'] = expanded_urls
                tweet_data['urls_expanded'] = True

            # Download media if present and not already downloaded or forced
            if 'media' in tweet_data and (force_recache or not tweet_data.get('downloaded_media')):
                media_dir = Path(config.media_cache_dir) / tweet_id
                media_dir.mkdir(parents=True, exist_ok=True)
                media_paths = []

                for idx, media_item in enumerate(tweet_data['media']):
                    try:
                        url = media_item.get('url', '') if isinstance(media_item, dict) else str(media_item)
                        media_type = media_item.get('type', 'image') if isinstance(media_item, dict) else 'image'
                        if not url:
                            logging.warning(f"No valid URL in media item {idx} for tweet {tweet_id}")
                            continue

                        ext = '.mp4' if media_type == 'video' else (Path(urlparse(url).path).suffix or '.jpg')
                        media_path = media_dir / f"media_{idx}{ext}"

                        if not media_path.exists():
                            logging.info(f"Downloading media from {url} to {media_path}")
                            await http_client.download_media(url, media_path)
                            if not media_path.exists():
                                logging.error(f"Media download failed for {url} at {media_path}")
                                continue
                        media_paths.append(str(media_path))
                    except Exception as e:
                        logging.error(f"Failed to download media item {idx} for tweet {tweet_id}: {e}")
                        continue

                tweet_data['downloaded_media'] = media_paths

            tweet_data['cache_complete'] = True
            await state_manager.update_tweet_data(tweet_id, tweet_data)
            logging.info(f"Cached tweet {tweet_id}: {len(tweet_data.get('urls', []))} URLs, {len(tweet_data.get('downloaded_media', []))} media items")

        except Exception as e:
            logging.error(f"Failed to cache tweet {tweet_id}: {e}")
            continue

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
        """Log detailed validation results to both file and console."""
        if any(len(items) > 0 for items in self.validation_results.values()):
            logging.info("=== Tweet Cache Validation Results ===")
            
            if self.validation_results['media_files_missing']:
                media_count = len(self.validation_results['media_files_missing'])
                affected_tweets = {item['tweet_id'] for item in self.validation_results['media_files_missing']}
                logging.info(f"🖼️  Media files missing: {media_count} files from {len(affected_tweets)} tweets")
                for item in self.validation_results['media_files_missing'][:5]:
                    logging.debug(f"  - Tweet {item['tweet_id']}: Missing media {item['media_path']}")
                if media_count > 5:
                    logging.debug(f"  - ... and {media_count - 5} more")
            
            if self.validation_results['image_descriptions_missing']:
                desc_count = len(self.validation_results['image_descriptions_missing'])
                logging.info(f"📝 Image descriptions missing: {desc_count} tweets need media processing")
                for item in self.validation_results['image_descriptions_missing'][:5]:
                    logging.debug(f"  - Tweet {item['tweet_id']}: Has {item['media_count']} media but only {item['descriptions_count']} descriptions")
                if desc_count > 5:
                    logging.debug(f"  - ... and {desc_count - 5} more")
            
            if self.validation_results['categories_incomplete']:
                cat_count = len(self.validation_results['categories_incomplete'])
                logging.info(f"🏷️  Categories incomplete: {cat_count} tweets need category processing")
                for item in self.validation_results['categories_incomplete'][:5]:
                    logging.debug(f"  - Tweet {item['tweet_id']}: Missing fields {', '.join(item['missing_fields'])}")
                if cat_count > 5:
                    logging.debug(f"  - ... and {cat_count - 5} more")
            
            if self.validation_results['kb_items_missing']:
                kb_count = len(self.validation_results['kb_items_missing'])
                logging.info(f"📚 KB items missing: {kb_count} tweets need KB item creation")
                for item in self.validation_results['kb_items_missing'][:5]:
                    reason = "missing path" if item.get('reason') == 'missing_path' else f"file not found at {item.get('kb_path', 'unknown')}"
                    logging.debug(f"  - Tweet {item['tweet_id']}: {reason}")
                if kb_count > 5:
                    logging.debug(f"  - ... and {kb_count - 5} more")
            
            total_issues = sum(len(items) for items in self.validation_results.values())
            affected_tweets = set()
            for category in self.validation_results.values():
                for item in category:
                    affected_tweets.add(item['tweet_id'])
            
            logging.info(f"Total validation issues: {total_issues} across {len(affected_tweets)} tweets")
            logging.info("These tweets will be reprocessed in the appropriate phases")

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