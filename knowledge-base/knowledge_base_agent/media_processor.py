from pathlib import Path
from typing import Dict, Any
import logging
from knowledge_base_agent.config import Config
from knowledge_base_agent.http_client import HTTPClient
from knowledge_base_agent.image_interpreter import interpret_image
from knowledge_base_agent.exceptions import ContentProcessingError
from mimetypes import guess_type

VIDEO_MIME_TYPES = {'video/mp4', 'video/quicktime', 'video/x-msvideo', 'video/x-matroska'}

async def process_media(tweet_data: Dict[str, Any], http_client: HTTPClient, config: Config) -> Dict[str, Any]:
    """Process non-video media content for a tweet, skipping videos."""
    try:
        if tweet_data.get('media_processed', False):
            logging.info("Media already processed, skipping...")
            return tweet_data

        media_paths = tweet_data.get('downloaded_media', [])
        if not media_paths:
            tweet_data['media_processed'] = True
            return tweet_data

        image_descriptions = []
        has_unprocessed_images = False

        for media_path in media_paths:
            media_path = Path(media_path)
            if not media_path.exists():
                raise ContentProcessingError(f"Media file not found: {media_path}")

            mime_type, _ = guess_type(str(media_path))
            is_video_file = mime_type in VIDEO_MIME_TYPES or media_path.suffix.lower() in {'.mp4', '.mov', '.avi', '.mkv'}

            if is_video_file:
                logging.info(f"Skipping video analysis for {media_path}")
                image_descriptions.append(f"Video file: {media_path.name}")
                continue

            # Process only non-video (image) files
            has_unprocessed_images = True
            try:
                description = await interpret_image(
                    http_client=http_client,
                    image_path=media_path,
                    vision_model=config.vision_model
                )
                if description:
                    image_descriptions.append(description)
            except Exception as e:
                logging.error(f"Failed to process image {media_path}: {e}")
                image_descriptions.append(f"Failed to process image: {media_path.name}")

        tweet_data['image_descriptions'] = image_descriptions
        tweet_data['media_processed'] = not has_unprocessed_images
        return tweet_data

    except Exception as e:
        raise ContentProcessingError(f"Failed to process media content: {e}")

async def process_media_content(tweet_data: Dict[str, Any], http_client: HTTPClient, config: Config) -> Dict[str, Any]:
    """Process non-video media content, preserving video references without analysis."""
    try:
        if tweet_data.get('media_processed', False):
            logging.info("Media already processed, skipping...")
            return tweet_data

        media_paths = tweet_data.get('downloaded_media', [])
        if not media_paths:
            tweet_data['media_processed'] = True
            return tweet_data

        image_descriptions = []
        has_unprocessed_images = False

        for media_path in media_paths:
            media_path = Path(media_path)
            if not media_path.exists():
                raise ContentProcessingError(f"Media file not found: {media_path}")

            mime_type, _ = guess_type(str(media_path))
            is_video_file = mime_type in VIDEO_MIME_TYPES or media_path.suffix.lower() in {'.mp4', '.mov', '.avi', '.mkv'}

            if is_video_file:
                logging.info(f"Skipping video analysis for {media_path}")
                # Preserve video reference without description
                image_descriptions.append(f"Video file: {media_path.name}")
                continue

            # Process only non-video (image) files
            has_unprocessed_images = True
            try:
                description = await interpret_image(
                    http_client=http_client,
                    image_path=media_path,
                    vision_model=config.vision_model
                )
                if description:
                    image_descriptions.append(description)
            except Exception as e:
                logging.error(f"Failed to process image {media_path}: {e}")
                image_descriptions.append(f"Failed to process image: {media_path.name}")

        # Update tweet data
        tweet_data['image_descriptions'] = image_descriptions
        # Mark as processed if no unprocessed images remain
        tweet_data['media_processed'] = not has_unprocessed_images
        return tweet_data

    except Exception as e:
        raise ContentProcessingError(f"Failed to process media content: {e}")

def has_unprocessed_non_video_media(tweet_data: Dict[str, Any]) -> bool:
    """Check if tweet has any unprocessed non-video media."""
    if tweet_data.get('media_processed', False):
        return False
    
    media_paths = tweet_data.get('downloaded_media', [])
    if not media_paths:
        return False

    return any(
        not (guess_type(str(media_path))[0] in VIDEO_MIME_TYPES or 
             Path(media_path).suffix.lower() in {'.mp4', '.mov', '.avi', '.mkv'})
        for media_path in media_paths
    )

async def count_media_items(tweets: Dict[str, Any]) -> int:
    """Count total number of unprocessed non-video media items."""
    count = 0
    for tweet_data in tweets.values():
        if not tweet_data.get('media_processed', False):
            count += sum(1 for media_path in tweet_data.get('downloaded_media', []) 
                        if not (guess_type(str(media_path))[0] in VIDEO_MIME_TYPES or 
                                Path(media_path).suffix.lower() in {'.mp4', '.mov', '.avi', '.mkv'}))
    return count