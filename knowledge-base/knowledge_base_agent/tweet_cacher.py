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

async def cache_tweets(tweet_ids: List[str], config: Config, http_client: HTTPClient, state_manager: StateManager) -> None:
    """Cache tweet data including expanded URLs and all media."""
    cached_tweets = await state_manager.get_all_tweets()

    for tweet_id in tweet_ids:
        try:
            # Check if tweet exists and is fully cached
            existing_tweet = cached_tweets.get(tweet_id, {})
            if existing_tweet and existing_tweet.get('cache_complete', False):
                logging.info(f"Tweet {tweet_id} already fully cached, skipping...")
                continue

            # If we have partial data, preserve it
            if existing_tweet:
                logging.info(f"Found partial cache for tweet {tweet_id}, completing cache...")
                tweet_data = existing_tweet
            else:
                # Fetch new tweet data
                tweet_url = f"https://twitter.com/i/web/status/{tweet_id}"
                tweet_data = await fetch_tweet_data_playwright(tweet_url, config)
                if not tweet_data:
                    logging.error(f"Failed to fetch tweet {tweet_id}")
                    continue

            # Expand URLs if present
            if 'urls' in tweet_data:
                expanded_urls = []
                for url in tweet_data.get('urls', []):
                    try:
                        expanded = await expand_url(url)  # Use playwright_fetcher.expand_url
                        expanded_urls.append(expanded)
                    except Exception as e:
                        logging.warning(f"Failed to expand URL {url}: {e}")
                        expanded_urls.append(url)  # Fallback to original
                tweet_data['urls'] = expanded_urls

            # Download media if present and not already downloaded
            if 'media' in tweet_data and not tweet_data.get('downloaded_media'):
                media_dir = Path(config.media_cache_dir) / tweet_id
                media_dir.mkdir(parents=True, exist_ok=True)
                
                media_paths = []
                for idx, media_item in enumerate(tweet_data['media']):
                    try:
                        # Extract URL and type from media item
                        if isinstance(media_item, dict):
                            url = media_item.get('url', '')
                            media_type = media_item.get('type', 'image')
                        else:
                            url = str(media_item)
                            media_type = 'image'  # Default to image
                            
                        if not url:
                            logging.warning(f"No valid URL in media item {idx} for tweet {tweet_id}: {media_item}")
                            continue

                        # Determine file extension
                        ext = '.mp4' if media_type == 'video' else (Path(urlparse(url).path).suffix or '.jpg')
                        media_path = media_dir / f"media_{idx}{ext}"
                        
                        # Download if not exists
                        if not media_path.exists():
                            logging.info(f"Downloading media from {url} to {media_path}")
                            await http_client.download_media(url, media_path)
                            logging.info(f"Successfully downloaded media to {media_path}")
                        else:
                            logging.debug(f"Media already exists at {media_path}, skipping download")
                        
                        media_paths.append(str(media_path))
                        
                    except Exception as e:
                        logging.error(f"Failed to process media item {idx} for tweet {tweet_id}: {e}")
                        continue

                tweet_data['downloaded_media'] = media_paths
                logging.info(f"Downloaded {len(media_paths)} media files for tweet {tweet_id}")

            # Mark as fully cached and save
            tweet_data['cache_complete'] = True
            await state_manager.update_tweet_data(tweet_id, tweet_data)
            logging.info(f"Cached tweet {tweet_id}: {len(tweet_data.get('urls', []))} URLs, {len(tweet_data.get('downloaded_media', []))} media items")

        except Exception as e:
            logging.error(f"Failed to cache tweet {tweet_id}: {e}")
            continue

class TweetCacheValidator:
    """Validates the integrity of the tweet cache and fixes inconsistencies."""
    
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
                logging.debug(f"Tweet {tweet_id} marked as kb_item_created but missing kb_item_path")
                tweet_data['kb_item_created'] = False
                self.validation_results['kb_items_missing'].append({
                    'tweet_id': tweet_id,
                    'reason': 'missing_path'
                })
                modified = True
            else:
                # Check if the KB item exists
                full_path = self.kb_base_dir / kb_path
                if not full_path.exists() and not (full_path.parent / "README.md").exists():
                    logging.debug(f"KB item {kb_path} for tweet {tweet_id} not found")
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
        # Detailed logging to file
        if any(len(items) > 0 for items in self.validation_results.values()):
            logging.info("=== Tweet Cache Validation Results ===")
            
            # Media files
            if self.validation_results['media_files_missing']:
                media_count = len(self.validation_results['media_files_missing'])
                affected_tweets = {item['tweet_id'] for item in self.validation_results['media_files_missing']}
                logging.info(f"🖼️  Media files missing: {media_count} files from {len(affected_tweets)} tweets")
                for item in self.validation_results['media_files_missing'][:5]:  # Log first 5 only
                    logging.debug(f"  - Tweet {item['tweet_id']}: Missing media {item['media_path']}")
                if media_count > 5:
                    logging.debug(f"  - ... and {media_count - 5} more")
            
            # Image descriptions
            if self.validation_results['image_descriptions_missing']:
                desc_count = len(self.validation_results['image_descriptions_missing'])
                logging.info(f"📝 Image descriptions missing: {desc_count} tweets need media processing")
                for item in self.validation_results['image_descriptions_missing'][:5]:
                    logging.debug(f"  - Tweet {item['tweet_id']}: Has {item['media_count']} media but only {item['descriptions_count']} descriptions")
                if desc_count > 5:
                    logging.debug(f"  - ... and {desc_count - 5} more")
            
            # Categories
            if self.validation_results['categories_incomplete']:
                cat_count = len(self.validation_results['categories_incomplete'])
                logging.info(f"🏷️  Categories incomplete: {cat_count} tweets need category processing")
                for item in self.validation_results['categories_incomplete'][:5]:
                    logging.debug(f"  - Tweet {item['tweet_id']}: Missing fields {', '.join(item['missing_fields'])}")
                if cat_count > 5:
                    logging.debug(f"  - ... and {cat_count - 5} more")
            
            # KB items
            if self.validation_results['kb_items_missing']:
                kb_count = len(self.validation_results['kb_items_missing'])
                logging.info(f"📚 KB items missing: {kb_count} tweets need KB item creation")
                for item in self.validation_results['kb_items_missing'][:5]:
                    reason = "missing path" if item.get('reason') == 'missing_path' else f"file not found at {item.get('kb_path', 'unknown')}"
                    logging.debug(f"  - Tweet {item['tweet_id']}: {reason}")
                if kb_count > 5:
                    logging.debug(f"  - ... and {kb_count - 5} more")
            
            # Summary for console
            total_issues = sum(len(items) for items in self.validation_results.values())
            affected_tweets = set()
            for category in self.validation_results.values():
                for item in category:
                    affected_tweets.add(item['tweet_id'])
            
            logging.info(f"Total validation issues: {total_issues} across {len(affected_tweets)} tweets")
            logging.info("These tweets will be reprocessed in the appropriate phases")