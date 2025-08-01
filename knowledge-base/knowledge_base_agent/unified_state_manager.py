"""
Unified State Manager - Clean Implementation

This module provides state management using the UnifiedTweet model as the single source of truth.
No legacy code, no backward compatibility - just clean, unified operations.
"""

import logging
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timezone

from .models import db, UnifiedTweet
from .config import Config
from .exceptions import StateError, StateManagerError

logger = logging.getLogger(__name__)


class UnifiedStateManager:
    """
    Clean state manager that works directly with the UnifiedTweet model.
    
    Provides organized validation phases and processing state management
    using the unified architecture.
    """
    
    def __init__(self, config: Config, task_id: Optional[str] = None):
        self.config = config
        self.task_id = task_id
        self.validation_stats = {
            "total_tweets": 0,
            "cache_complete": 0,
            "media_processed": 0,
            "categories_processed": 0,
            "kb_item_created": 0,
            "processing_complete": 0,
            "validation_fixes": 0,
            "errors": 0
        }
    
    def initialize(self) -> Dict[str, Any]:
        """
        Initialize and validate the current processing state.
        
        Returns comprehensive state information for all tweets.
        """
        logger.info("🔄 Initializing unified state manager...")
        
        try:
            # Get all tweets from unified table
            all_tweets = UnifiedTweet.query.all()
            self.validation_stats["total_tweets"] = len(all_tweets)
            
            # Calculate processing statistics
            for tweet in all_tweets:
                if tweet.cache_complete:
                    self.validation_stats["cache_complete"] += 1
                if tweet.media_processed:
                    self.validation_stats["media_processed"] += 1
                if tweet.categories_processed:
                    self.validation_stats["categories_processed"] += 1
                if tweet.kb_item_created:
                    self.validation_stats["kb_item_created"] += 1
                if tweet.processing_complete:
                    self.validation_stats["processing_complete"] += 1
            
            logger.info(f"✅ State initialized: {self.validation_stats}")
            
            return {
                "success": True,
                "stats": self.validation_stats,
                "total_tweets": len(all_tweets)
            }
            
        except Exception as e:
            logger.error(f"❌ Failed to initialize state manager: {e}")
            raise StateManagerError(f"State initialization failed: {e}")
    
    def get_processing_state(self) -> Dict[str, Any]:
        """Get current processing state for all tweets."""
        try:
            all_tweets = UnifiedTweet.query.all()
            
            # Convert to dictionary format for compatibility
            tweets_dict = {}
            for tweet in all_tweets:
                tweets_dict[tweet.tweet_id] = self._tweet_to_dict(tweet)
            
            return {
                "tweets": tweets_dict,
                "stats": self.validation_stats
            }
            
        except Exception as e:
            logger.error(f"❌ Failed to get processing state: {e}")
            raise StateManagerError(f"Failed to get processing state: {e}")
    
    def update_tweet_data(self, tweet_id: str, updates: Dict[str, Any]) -> bool:
        """
        Update tweet data in the unified model.
        
        Args:
            tweet_id: Tweet ID to update
            updates: Dictionary of field updates
            
        Returns:
            True if successful, False otherwise
        """
        try:
            tweet = UnifiedTweet.query.filter_by(tweet_id=tweet_id).first()
            if not tweet:
                logger.error(f"Tweet {tweet_id} not found in unified table")
                return False
            
            # Apply updates
            for field, value in updates.items():
                if hasattr(tweet, field):
                    setattr(tweet, field, value)
                else:
                    logger.warning(f"Field {field} not found in UnifiedTweet model")
            
            # Update timestamp
            tweet.updated_at = datetime.now(timezone.utc)
            
            db.session.commit()
            logger.debug(f"✅ Updated tweet {tweet_id} with {len(updates)} fields")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to update tweet {tweet_id}: {e}")
            db.session.rollback()
            return False
    
    def get_tweets_for_phase(self, phase: str) -> List[UnifiedTweet]:
        """
        Get tweets that need processing for a specific phase.
        
        Args:
            phase: Processing phase ('cache', 'media', 'categorization', 'kb_generation')
            
        Returns:
            List of UnifiedTweet objects ready for processing
        """
        try:
            if phase == "cache":
                return UnifiedTweet.query.filter_by(cache_complete=False).all()
            elif phase == "media":
                return UnifiedTweet.query.filter_by(
                    cache_complete=True, 
                    media_processed=False
                ).all()
            elif phase == "categorization":
                return UnifiedTweet.query.filter_by(
                    media_processed=True, 
                    categories_processed=False
                ).all()
            elif phase == "kb_generation":
                return UnifiedTweet.query.filter_by(
                    categories_processed=True, 
                    kb_item_created=False
                ).all()
            else:
                logger.error(f"Unknown processing phase: {phase}")
                return []
                
        except Exception as e:
            logger.error(f"❌ Failed to get tweets for phase {phase}: {e}")
            return []
    
    def get_tweets_needing_reprocessing(self) -> List[UnifiedTweet]:
        """Get tweets that need reprocessing."""
        try:
            return UnifiedTweet.query.filter(
                (UnifiedTweet.force_reprocess_pipeline == True) |
                (UnifiedTweet.force_recache == True)
            ).all()
        except Exception as e:
            logger.error(f"❌ Failed to get tweets needing reprocessing: {e}")
            return []
    
    def mark_phase_complete(self, tweet_id: str, phase: str, success: bool = True) -> bool:
        """
        Mark a processing phase as complete for a tweet.
        
        Args:
            tweet_id: Tweet ID
            phase: Phase name ('cache', 'media', 'categorization', 'kb_generation')
            success: Whether the phase completed successfully
            
        Returns:
            True if successful, False otherwise
        """
        try:
            tweet = UnifiedTweet.query.filter_by(tweet_id=tweet_id).first()
            if not tweet:
                logger.error(f"Tweet {tweet_id} not found")
                return False
            
            # Update phase flags
            if phase == "cache" and success:
                tweet.cache_complete = True
                tweet.cached_at = datetime.now(timezone.utc)
            elif phase == "media" and success:
                tweet.media_processed = True
            elif phase == "categorization" and success:
                tweet.categories_processed = True
            elif phase == "kb_generation" and success:
                tweet.kb_item_created = True
                tweet.kb_generated_at = datetime.now(timezone.utc)
                
                # Check if entire pipeline is complete
                if (tweet.cache_complete and tweet.media_processed and 
                    tweet.categories_processed and tweet.kb_item_created):
                    tweet.processing_complete = True
                    tweet.processed_at = datetime.now(timezone.utc)
            
            # Update runtime flags
            if phase == "cache":
                tweet.cache_succeeded_this_run = success
            elif phase == "media":
                tweet.media_succeeded_this_run = success
            elif phase == "categorization":
                tweet.llm_succeeded_this_run = success
            elif phase == "kb_generation":
                tweet.kbitem_succeeded_this_run = success
            
            tweet.updated_at = datetime.now(timezone.utc)
            db.session.commit()
            
            logger.debug(f"✅ Marked phase {phase} as {'complete' if success else 'failed'} for tweet {tweet_id}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to mark phase {phase} complete for tweet {tweet_id}: {e}")
            db.session.rollback()
            return False
    
    def get_processing_statistics(self) -> Dict[str, Any]:
        """Get comprehensive processing statistics."""
        try:
            stats = {
                "total_tweets": UnifiedTweet.query.count(),
                "cache_complete": UnifiedTweet.query.filter_by(cache_complete=True).count(),
                "media_processed": UnifiedTweet.query.filter_by(media_processed=True).count(),
                "categories_processed": UnifiedTweet.query.filter_by(categories_processed=True).count(),
                "kb_item_created": UnifiedTweet.query.filter_by(kb_item_created=True).count(),
                "processing_complete": UnifiedTweet.query.filter_by(processing_complete=True).count(),
                "needs_reprocessing": UnifiedTweet.query.filter(
                    (UnifiedTweet.force_reprocess_pipeline == True) |
                    (UnifiedTweet.force_recache == True)
                ).count()
            }
            
            # Calculate percentages
            total = stats["total_tweets"]
            if total > 0:
                stats["completion_percentages"] = {
                    "cache": round((stats["cache_complete"] / total) * 100, 1),
                    "media": round((stats["media_processed"] / total) * 100, 1),
                    "categorization": round((stats["categories_processed"] / total) * 100, 1),
                    "kb_generation": round((stats["kb_item_created"] / total) * 100, 1),
                    "overall": round((stats["processing_complete"] / total) * 100, 1)
                }
            
            return stats
            
        except Exception as e:
            logger.error(f"❌ Failed to get processing statistics: {e}")
            return {}
    
    def get_all_tweets(self) -> Dict[str, Dict[str, Any]]:
        """
        Get all tweets in dictionary format for backward compatibility.
        
        Returns:
            Dictionary mapping tweet_id to tweet data
        """
        try:
            all_tweets = UnifiedTweet.query.all()
            tweets_dict = {}
            
            for tweet in all_tweets:
                tweets_dict[tweet.tweet_id] = self._tweet_to_dict(tweet)
            
            logger.debug(f"✅ Retrieved {len(tweets_dict)} tweets from unified model")
            return tweets_dict
            
        except Exception as e:
            logger.error(f"❌ Failed to get all tweets: {e}")
            return {}
    
    def get_unprocessed_tweets(self) -> List[str]:
        """
        Get list of tweet IDs that are not fully processed.
        
        Returns:
            List of tweet IDs that need processing
        """
        try:
            unprocessed_tweets = UnifiedTweet.query.filter_by(processing_complete=False).all()
            tweet_ids = [tweet.tweet_id for tweet in unprocessed_tweets]
            logger.debug(f"✅ Found {len(tweet_ids)} unprocessed tweets")
            return tweet_ids
        except Exception as e:
            logger.error(f"❌ Failed to get unprocessed tweets: {e}")
            return []
    
    def get_processed_tweets(self) -> List[str]:
        """
        Get list of tweet IDs that are fully processed.
        
        Returns:
            List of tweet IDs that are fully processed
        """
        try:
            processed_tweets = UnifiedTweet.query.filter_by(processing_complete=True).all()
            tweet_ids = [tweet.tweet_id for tweet in processed_tweets]
            logger.debug(f"✅ Found {len(tweet_ids)} processed tweets")
            return tweet_ids
        except Exception as e:
            logger.error(f"❌ Failed to get processed tweets: {e}")
            return []
    
    def add_tweets_to_unprocessed(self, tweet_ids: List[str]) -> bool:
        """
        Add tweets to the unprocessed queue by ensuring they exist and are not marked as complete.
        
        Args:
            tweet_ids: List of tweet IDs to add to unprocessed queue
            
        Returns:
            True if successful, False otherwise
        """
        try:
            added_count = 0
            for tweet_id in tweet_ids:
                tweet = UnifiedTweet.query.filter_by(tweet_id=tweet_id).first()
                if tweet and tweet.processing_complete:
                    # Reset processing flags to make it unprocessed
                    tweet.processing_complete = False
                    tweet.updated_at = datetime.now(timezone.utc)
                    added_count += 1
                elif not tweet:
                    logger.warning(f"Tweet {tweet_id} not found in unified table")
            
            if added_count > 0:
                db.session.commit()
                logger.info(f"✅ Added {added_count} tweets to unprocessed queue")
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to add tweets to unprocessed queue: {e}")
            db.session.rollback()
            return False
    
    def get_tweet(self, tweet_id: str) -> Optional[Dict[str, Any]]:
        """
        Get a single tweet by ID in dictionary format.
        
        Args:
            tweet_id: Tweet ID to retrieve
            
        Returns:
            Tweet data dictionary or None if not found
        """
        try:
            tweet = UnifiedTweet.query.filter_by(tweet_id=tweet_id).first()
            if tweet:
                return self._tweet_to_dict(tweet)
            else:
                logger.warning(f"Tweet {tweet_id} not found")
                return None
        except Exception as e:
            logger.error(f"❌ Failed to get tweet {tweet_id}: {e}")
            return None
    
    def get_processing_state(self, tweet_id: str) -> Dict[str, Any]:
        """
        Get processing state for a specific tweet.
        
        Args:
            tweet_id: Tweet ID to check
            
        Returns:
            Dictionary with processing state information
        """
        try:
            tweet = UnifiedTweet.query.filter_by(tweet_id=tweet_id).first()
            if not tweet:
                return {"fully_processed": False, "exists": False}
            
            return {
                "fully_processed": tweet.processing_complete or False,
                "exists": True,
                "cache_complete": tweet.cache_complete or False,
                "media_processed": tweet.media_processed or False,
                "categories_processed": tweet.categories_processed or False,
                "kb_item_created": tweet.kb_item_created or False
            }
        except Exception as e:
            logger.error(f"❌ Failed to get processing state for tweet {tweet_id}: {e}")
            return {"fully_processed": False, "exists": False, "error": str(e)}
    
    def mark_tweet_processed(self, tweet_id: str) -> bool:
        """
        Mark a tweet as fully processed.
        
        This method marks all processing phases as complete and sets the 
        processing_complete flag to True.
        
        Args:
            tweet_id: Tweet ID to mark as processed
            
        Returns:
            True if successful, False otherwise
        """
        try:
            tweet = UnifiedTweet.query.filter_by(tweet_id=tweet_id).first()
            if not tweet:
                logger.error(f"Tweet {tweet_id} not found in unified table")
                return False
            
            # Mark all phases as complete
            tweet.cache_complete = True
            tweet.media_processed = True
            tweet.categories_processed = True
            tweet.kb_item_created = True
            tweet.processing_complete = True
            
            # Update timestamps
            now = datetime.now(timezone.utc)
            tweet.processed_at = now
            tweet.updated_at = now
            
            # Set runtime success flags
            tweet.cache_succeeded_this_run = True
            tweet.media_succeeded_this_run = True
            tweet.llm_succeeded_this_run = True
            tweet.kbitem_succeeded_this_run = True
            
            db.session.commit()
            logger.debug(f"✅ Marked tweet {tweet_id} as fully processed")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to mark tweet {tweet_id} as processed: {e}")
            db.session.rollback()
            return False

    def _tweet_to_dict(self, tweet: UnifiedTweet) -> Dict[str, Any]:
        """Convert UnifiedTweet to dictionary format."""
        return {
            "tweet_id": tweet.tweet_id,
            "bookmarked_tweet_id": tweet.bookmarked_tweet_id,
            "is_thread": tweet.is_thread or False,
            
            # Processing flags
            "cache_complete": tweet.cache_complete or False,
            "media_processed": tweet.media_processed or False,
            "categories_processed": tweet.categories_processed or False,
            "kb_item_created": tweet.kb_item_created or False,
            "processing_complete": tweet.processing_complete or False,
            
            # Content data
            "thread_tweets": tweet.thread_tweets or [],
            "all_downloaded_media_for_thread": tweet.media_files or [],
            "full_text": tweet.full_text or "",
            "image_descriptions": tweet.image_descriptions or [],
            "raw_json_content": tweet.raw_tweet_data,
            
            # Categorization
            "main_category": tweet.main_category or "",
            "sub_category": tweet.sub_category or "",
            "item_name_suggestion": tweet.kb_item_name or "",
            "categories": tweet.categories_raw_response or {},
            
            # KB data
            "kb_item_path": tweet.kb_file_path or "",
            "kb_media_paths": tweet.kb_media_paths or [],
            "display_title": tweet.kb_display_title or "",
            
            # Error tracking
            "kbitem_error": tweet.kbitem_error,
            "llm_error": tweet.llm_error,
            "recategorization_attempts": tweet.recategorization_attempts or 0,
            
            # Reprocessing controls
            "force_reprocess_pipeline": tweet.force_reprocess_pipeline or False,
            "force_recache": tweet.force_recache or False,
            
            # Runtime flags
            "cache_succeeded_this_run": tweet.cache_succeeded_this_run or False,
            "media_succeeded_this_run": tweet.media_succeeded_this_run or False,
            "llm_succeeded_this_run": tweet.llm_succeeded_this_run or False,
            "kbitem_succeeded_this_run": tweet.kbitem_succeeded_this_run or False,
            "db_synced": True,  # Always true for unified model
            
            # Metadata
            "source": tweet.source or "twitter",
            "url": tweet.source_url or "",
            
            # Timestamps
            "created_at": tweet.created_at.isoformat() if tweet.created_at else None,
            "updated_at": tweet.updated_at.isoformat() if tweet.updated_at else None,
        }


class UnifiedPhaseExecutionHelper:
    """
    Clean phase execution helper that works with UnifiedTweet model.
    
    Creates execution plans for processing phases without any validation logic.
    """
    
    def __init__(self, config: Config):
        self.config = config
    
    def create_cache_execution_plan(self) -> List[UnifiedTweet]:
        """Get tweets that need caching."""
        return UnifiedTweet.query.filter_by(cache_complete=False).all()
    
    def create_media_execution_plan(self) -> List[UnifiedTweet]:
        """Get tweets that need media processing."""
        return UnifiedTweet.query.filter_by(
            cache_complete=True, 
            media_processed=False
        ).all()
    
    def create_categorization_execution_plan(self) -> List[UnifiedTweet]:
        """Get tweets that need categorization."""
        return UnifiedTweet.query.filter_by(
            media_processed=True, 
            categories_processed=False
        ).all()
    
    def create_kb_generation_execution_plan(self) -> List[UnifiedTweet]:
        """Get tweets that need KB item generation."""
        return UnifiedTweet.query.filter_by(
            categories_processed=True, 
            kb_item_created=False
        ).all()
    
    def create_all_execution_plans(self) -> Dict[str, List[UnifiedTweet]]:
        """Create execution plans for all phases."""
        return {
            "cache": self.create_cache_execution_plan(),
            "media": self.create_media_execution_plan(),
            "categorization": self.create_categorization_execution_plan(),
            "kb_generation": self.create_kb_generation_execution_plan()
        }