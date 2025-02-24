from pathlib import Path
from typing import List, Dict, Any
import logging
from knowledge_base_agent.config import Config
from knowledge_base_agent.http_client import HTTPClient
from knowledge_base_agent.state_manager import StateManager
from knowledge_base_agent.playwright_fetcher import fetch_tweet_data_playwright, expand_url
from urllib.parse import urlparse

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