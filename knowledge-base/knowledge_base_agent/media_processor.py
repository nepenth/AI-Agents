from pathlib import Path
from typing import Dict, Any
import logging
from knowledge_base_agent.config import Config
from knowledge_base_agent.http_client import HTTPClient
from knowledge_base_agent.image_interpreter import interpret_image
from knowledge_base_agent.video_interpreter import interpret_video
from knowledge_base_agent.exceptions import ContentProcessingError
from mimetypes import guess_type

VIDEO_MIME_TYPES = {'video/mp4', 'video/quicktime', 'video/x-msvideo', 'video/x-matroska'}

async def process_media(tweet_data: Dict[str, Any], http_client: HTTPClient, config: Config, force_reprocess: bool = False) -> Dict[str, Any]:
    """Process media content for a tweet, including both images and videos."""
    try:
        if tweet_data.get('media_processed', False) and not force_reprocess:
            logging.info("Media already processed and force_reprocess not enabled, skipping...")
            return tweet_data

        # 'all_downloaded_media_for_thread' contains paths relative to project_root
        media_paths_rel = tweet_data.get('all_downloaded_media_for_thread', []) 
        if not media_paths_rel:
            tweet_data['media_processed'] = True
            logging.debug(f"No media paths found for tweet {tweet_data.get('tweet_id')}, marking media_processed=True")
            return tweet_data

        image_descriptions = []
        has_unprocessed_media = False
        process_videos = config.process_videos if hasattr(config, 'process_videos') else True

        for media_path_rel_str in media_paths_rel:
            # Resolve relative path to absolute path
            media_path_abs = config.resolve_path_from_project_root(media_path_rel_str)
            
            if not media_path_abs.exists():
                # Log error and continue, or raise? For now, log and skip this media.
                logging.error(f"Media file not found at resolved path: {media_path_abs} (from relative: {media_path_rel_str}). Skipping this media.")
                image_descriptions.append(f"Missing media file: {media_path_rel_str}") # Placeholder for missing
                has_unprocessed_media = True # Consider it unprocessed if linked media is missing
                continue

            mime_type, _ = guess_type(str(media_path_abs))
            is_video_file = mime_type in VIDEO_MIME_TYPES or media_path_abs.suffix.lower() in {'.mp4', '.mov', '.avi', '.mkv'}

            if is_video_file:
                if process_videos:
                    logging.info(f"Processing video file: {media_path_abs}")
                    try:
                        video_description = await interpret_video(
                            http_client=http_client,
                            video_path=media_path_abs,
                            vision_model=config.vision_model
                        )
                        if video_description:
                            image_descriptions.append(video_description)
                        else:
                            image_descriptions.append(f"Unable to analyze video: {media_path_abs.name}")
                    except Exception as e:
                        logging.error(f"Failed to process video {media_path_abs}: {e}")
                        image_descriptions.append(f"Error analyzing video: {media_path_abs.name}")
                else:
                    logging.info(f"Video processing disabled, skipping video analysis for {media_path_abs}")
                    image_descriptions.append(f"Video file: {media_path_abs.name}")
                continue

            has_unprocessed_media = True
            try:
                description = await interpret_image(
                    http_client=http_client,
                    image_path=media_path_abs, # Pass absolute path to interpreter
                    vision_model=config.vision_model
                )
                if description:
                    image_descriptions.append(description)
                else:
                    image_descriptions.append(f"No description generated for image: {media_path_abs.name}")
            except Exception as e:
                logging.error(f"Failed to process image {media_path_abs}: {e}")
                image_descriptions.append(f"Failed to process image: {media_path_abs.name}")

        tweet_data['image_descriptions'] = image_descriptions
        tweet_data['media_processed'] = True 
        logging.debug(f"Finished media processing for tweet {tweet_data.get('tweet_id')}. Descriptions: {len(image_descriptions)}. Marked media_processed=True")
        return tweet_data

    except Exception as e:
        # Ensure media_processed is False if an unexpected error occurs mid-processing
        tweet_data['media_processed'] = False 
        logging.error(f"Error in process_media for tweet {tweet_data.get('tweet_id')}: {e}", exc_info=True)
        raise ContentProcessingError(f"Failed to process media content for tweet {tweet_data.get('tweet_id')}: {e}")

async def process_media_content(tweet_data: Dict[str, Any], http_client: HTTPClient, config: Config, force_reprocess: bool = False) -> Dict[str, Any]:
    """Process non-video media content, preserving video references without analysis."""
    # This is a legacy function, prefer using process_media
    return await process_media(tweet_data, http_client, config, force_reprocess)

async def has_unprocessed_non_video_media(tweet_data: Dict[str, Any], config: Config) -> bool:
    """
    Check if tweet has any unprocessed non-video media.
    Uses config to resolve relative paths from 'all_downloaded_media_for_thread'.
    """
    # If already marked media_processed, then there's nothing unprocessed *according to prior steps*.
    if tweet_data.get('media_processed', False):
        logging.debug(f"Tweet {tweet_data.get('tweet_id')} marked media_processed=True, so no unprocessed media.")
        return False
    
    # 'all_downloaded_media_for_thread' contains paths relative to project_root
    media_paths_rel = tweet_data.get('all_downloaded_media_for_thread', [])
    if not media_paths_rel:
        logging.debug(f"No media paths in 'all_downloaded_media_for_thread' for tweet {tweet_data.get('tweet_id')}, so no unprocessed media.")
        return False # No media means no unprocessed media

    for media_path_rel_str in media_paths_rel:
        media_path_abs = config.resolve_path_from_project_root(media_path_rel_str)
        if not media_path_abs.exists():
            logging.warning(f"Media file {media_path_rel_str} (abs: {media_path_abs}) referenced in tweet {tweet_data.get('tweet_id')} not found. Counting as unprocessed/problematic.")
            return True # Missing media is effectively unprocessed/problematic

        mime_type, _ = guess_type(str(media_path_abs))
        is_video_file = mime_type in VIDEO_MIME_TYPES or media_path_abs.suffix.lower() in {'.mp4', '.mov', '.avi', '.mkv'}
        
        if not is_video_file:
            # Found a non-video file. Since 'media_processed' is False (checked at start),
            # this non-video file is considered unprocessed.
            logging.debug(f"Tweet {tweet_data.get('tweet_id')} has unprocessed non-video media: {media_path_rel_str}")
            return True 

    logging.debug(f"Tweet {tweet_data.get('tweet_id')} has no unprocessed non-video media (all items are videos or processed). Flag media_processed was {tweet_data.get('media_processed')}.")
    return False # All media items are videos, or media_processed was already true

async def count_media_items(tweets: Dict[str, Any], config: Config) -> int:
    """
    Count total number of non-video media items that are considered unprocessed or problematic (e.g. missing).
    Uses config to resolve relative paths.
    """
    count = 0
    for tweet_id, tweet_data in tweets.items():
        # If media_processed is True, assume all its media items are handled/accounted for.
        if tweet_data.get('media_processed', False):
            continue

        media_paths_rel = tweet_data.get('all_downloaded_media_for_thread', [])
        for media_path_rel_str in media_paths_rel:
            media_path_abs = config.resolve_path_from_project_root(media_path_rel_str)
            
            if not media_path_abs.exists():
                logging.warning(f"Media file {media_path_rel_str} (abs: {media_path_abs}) for tweet {tweet_id} not found. Counting as an item to process/address.")
                count += 1
                continue

            mime_type, _ = guess_type(str(media_path_abs))
            is_video_file = mime_type in VIDEO_MIME_TYPES or media_path_abs.suffix.lower() in {'.mp4', '.mov', '.avi', '.mkv'}
            
            if not is_video_file:
                # This is a non-video file, and the tweet's media_processed flag is False.
                # So, this specific non-video media item is considered for counting.
                count += 1
    logging.debug(f"Counted {count} non-video media items from tweets not marked media_processed.")
    return count