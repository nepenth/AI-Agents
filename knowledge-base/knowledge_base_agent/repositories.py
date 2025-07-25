"""
Repository Classes for JSON to Database Migration

This module provides repository classes for data access layer operations,
implementing the repository pattern for clean separation of concerns.
"""

import logging
from typing import List, Optional, Dict, Any, Tuple, Union
from datetime import datetime, timezone, timedelta
from sqlalchemy import and_, or_, func, text, desc, asc
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError, IntegrityError

from .database import get_db_session_context, execute_with_retry
from .models import db, TweetCache, TweetProcessingQueue, CategoryHierarchy, ProcessingStatistics, RuntimeStatistics

logger = logging.getLogger(__name__)


class BaseRepository:
    """Base repository class with common database operations."""
    
    def __init__(self, model_class):
        self.model_class = model_class
    
    def _get_session(self):
        """Get database session using the connection manager."""
        return get_db_session_context()
    
    def _handle_db_error(self, operation: str, error: Exception):
        """Handle database errors with proper logging."""
        logger.error(f"Database error in {operation}: {error}", exc_info=True)
        raise


class TweetCacheRepository(BaseRepository):
    """
    Repository for TweetCache model operations.
    
    Provides comprehensive CRUD operations, bulk processing, full-text search,
    and reprocessing flag management for tweet cache data.
    """
    
    def __init__(self):
        super().__init__(TweetCache)
    
    # ===== BASIC CRUD OPERATIONS =====
    
    def create(self, tweet_data: Dict[str, Any]) -> TweetCache:
        """
        Create a new tweet cache entry.
        
        Args:
            tweet_data: Dictionary containing tweet data
            
        Returns:
            Created TweetCache instance
            
        Raises:
            IntegrityError: If tweet_id already exists
        """
        try:
            with self._get_session() as session:
                tweet = TweetCache(**tweet_data)
                session.add(tweet)
                session.flush()  # Get the ID without committing
                session.refresh(tweet)
                # Detach from session to return a detached instance
                session.expunge(tweet)
                return tweet
        except IntegrityError as e:
            self._handle_db_error("create tweet", e)
        except Exception as e:
            self._handle_db_error("create tweet", e)
    
    def get_by_id(self, tweet_id: str) -> Optional[TweetCache]:
        """
        Get tweet by tweet_id.
        
        Args:
            tweet_id: The tweet ID to search for
            
        Returns:
            TweetCache instance or None if not found
        """
        try:
            with self._get_session() as session:
                tweet = session.query(TweetCache).filter_by(tweet_id=tweet_id).first()
                if tweet:
                    # Detach from session to return a detached instance
                    session.expunge(tweet)
                return tweet
        except Exception as e:
            self._handle_db_error("get tweet by id", e)
    
    def get_by_tweet_id(self, tweet_id: str) -> Optional[TweetCache]:
        """
        Get tweet by tweet_id (alias for get_by_id for API compatibility).
        
        Args:
            tweet_id: The tweet ID to search for
            
        Returns:
            TweetCache instance or None if not found
        """
        return self.get_by_id(tweet_id)
    
    def get_all(self, limit: int = None, offset: int = 0) -> List[TweetCache]:
        """
        Get all tweets from the cache.
        
        Args:
            limit: Maximum number of tweets to return (None for all)
            offset: Number of tweets to skip
            
        Returns:
            List of TweetCache instances
        """
        try:
            with self._get_session() as session:
                query = session.query(TweetCache)
                
                if offset > 0:
                    query = query.offset(offset)
                
                if limit is not None:
                    query = query.limit(limit)
                
                tweets = query.all()
                
                # Detach from session
                for tweet in tweets:
                    session.expunge(tweet)
                
                return tweets
        except Exception as e:
            self._handle_db_error("get all tweets", e)
            return []
    
    def get_total_count(self) -> int:
        """
        Get total count of tweets in the cache.
        
        Returns:
            Total number of tweets
        """
        try:
            with self._get_session() as session:
                return session.query(TweetCache).count()
        except Exception as e:
            self._handle_db_error("get total count", e)
            return 0
    
    def get_by_primary_key(self, pk: int) -> Optional[TweetCache]:
        """
        Get tweet by primary key.
        
        Args:
            pk: Primary key ID
            
        Returns:
            TweetCache instance or None if not found
        """
        try:
            with self._get_session() as session:
                return session.query(TweetCache).get(pk)
        except Exception as e:
            self._handle_db_error("get tweet by primary key", e)
    
    def update(self, tweet_id: str, update_data: Dict[str, Any]) -> Optional[TweetCache]:
        """
        Update tweet cache entry.
        
        Args:
            tweet_id: Tweet ID to update
            update_data: Dictionary of fields to update
            
        Returns:
            Updated TweetCache instance or None if not found
        """
        try:
            with self._get_session() as session:
                tweet = session.query(TweetCache).filter_by(tweet_id=tweet_id).first()
                if tweet:
                    for key, value in update_data.items():
                        if hasattr(tweet, key):
                            setattr(tweet, key, value)
                    tweet.updated_at = datetime.now(timezone.utc)
                    session.flush()
                    session.refresh(tweet)
                    # Detach from session to return a detached instance
                    session.expunge(tweet)
                return tweet
        except Exception as e:
            self._handle_db_error("update tweet", e)
    
    def delete(self, tweet_id: str) -> bool:
        """
        Delete tweet cache entry.
        
        Args:
            tweet_id: Tweet ID to delete
            
        Returns:
            True if deleted, False if not found
        """
        try:
            with self._get_session() as session:
                tweet = session.query(TweetCache).filter_by(tweet_id=tweet_id).first()
                if tweet:
                    session.delete(tweet)
                    return True
                return False
        except Exception as e:
            self._handle_db_error("delete tweet", e)
    
    # ===== BULK OPERATIONS =====
    
    def bulk_create(self, tweets_data: List[Dict[str, Any]]) -> List[TweetCache]:
        """
        Create multiple tweet cache entries efficiently.
        
        Args:
            tweets_data: List of tweet data dictionaries
            
        Returns:
            List of created TweetCache instances
        """
        try:
            with self._get_session() as session:
                tweets = [TweetCache(**data) for data in tweets_data]
                session.add_all(tweets)
                session.flush()
                for tweet in tweets:
                    session.refresh(tweet)
                return tweets
        except Exception as e:
            self._handle_db_error("bulk create tweets", e)
    
    def bulk_update_processing_flags(self, updates: List[Dict[str, Any]]) -> int:
        """
        Bulk update processing flags for multiple tweets.
        
        Args:
            updates: List of dicts with 'tweet_id' and flag updates
            
        Returns:
            Number of tweets updated
        """
        try:
            updated_count = 0
            with self._get_session() as session:
                for update in updates:
                    tweet_id = update.pop('tweet_id')
                    result = session.query(TweetCache).filter_by(tweet_id=tweet_id).update(update)
                    updated_count += result
                return updated_count
        except Exception as e:
            self._handle_db_error("bulk update processing flags", e)
    
    def bulk_set_reprocessing_flags(self, tweet_ids: List[str], flag_type: str, 
                                   requested_by: str = None) -> int:
        """
        Bulk set reprocessing flags for multiple tweets.
        
        Args:
            tweet_ids: List of tweet IDs to update
            flag_type: 'force_reprocess_pipeline' or 'force_recache'
            requested_by: User who requested reprocessing
            
        Returns:
            Number of tweets updated
        """
        if flag_type not in ['force_reprocess_pipeline', 'force_recache']:
            raise ValueError("flag_type must be 'force_reprocess_pipeline' or 'force_recache'")
        
        try:
            with self._get_session() as session:
                update_data = {
                    flag_type: True,
                    'reprocess_requested_at': datetime.now(timezone.utc),
                    'updated_at': datetime.now(timezone.utc)
                }
                if requested_by:
                    update_data['reprocess_requested_by'] = requested_by
                
                result = session.query(TweetCache).filter(
                    TweetCache.tweet_id.in_(tweet_ids)
                ).update(update_data, synchronize_session=False)
                
                return result
        except Exception as e:
            self._handle_db_error("bulk set reprocessing flags", e)
    
    def get_by_tweet_ids(self, tweet_ids: List[str]) -> List[TweetCache]:
        """
        Get tweets by a list of tweet IDs.
        
        Args:
            tweet_ids: List of tweet IDs to retrieve
            
        Returns:
            List of TweetCache instances
        """
        try:
            with self._get_session() as session:
                tweets = session.query(TweetCache).filter(
                    TweetCache.tweet_id.in_(tweet_ids)
                ).all()
                
                # Detach from session
                for tweet in tweets:
                    session.expunge(tweet)
                
                return tweets
        except Exception as e:
            self._handle_db_error("get tweets by IDs", e)
            return []
    
    # ===== FILTERING AND SEARCH =====
    
    def get_filtered_tweets(self, filters: Dict[str, Any] = None, limit: int = 50, 
                           offset: int = 0, sort_by: str = 'updated_at', 
                           sort_order: str = 'desc') -> Tuple[List[TweetCache], int]:
        """
        Get filtered and paginated tweets with total count.
        
        Args:
            filters: Dictionary of filter criteria
            limit: Maximum number of tweets to return
            offset: Number of tweets to skip
            sort_by: Field to sort by
            sort_order: Sort order ('asc' or 'desc')
            
        Returns:
            Tuple of (tweets list, total count)
        """
        try:
            with self._get_session() as session:
                # Build base query
                query = session.query(TweetCache)
                count_query = session.query(func.count(TweetCache.id))
                
                if filters:
                    # Apply search filter
                    if 'search' in filters and filters['search']:
                        search_term = f"%{filters['search']}%"
                        search_filter = or_(
                            TweetCache.full_text.ilike(search_term),
                            TweetCache.display_title.ilike(search_term),
                            TweetCache.item_name_suggestion.ilike(search_term)
                        )
                        query = query.filter(search_filter)
                        count_query = count_query.filter(search_filter)
                    
                    # Apply category filters
                    if 'main_category' in filters and filters['main_category']:
                        query = query.filter(TweetCache.main_category == filters['main_category'])
                        count_query = count_query.filter(TweetCache.main_category == filters['main_category'])
                    
                    if 'sub_category' in filters and filters['sub_category']:
                        query = query.filter(TweetCache.sub_category == filters['sub_category'])
                        count_query = count_query.filter(TweetCache.sub_category == filters['sub_category'])
                    
                    # Apply boolean filters
                    if 'has_media' in filters:
                        if filters['has_media']:
                            query = query.filter(TweetCache.media_processed == True)
                            count_query = count_query.filter(TweetCache.media_processed == True)
                        else:
                            query = query.filter(TweetCache.media_processed == False)
                            count_query = count_query.filter(TweetCache.media_processed == False)
                    
                    if 'has_categories' in filters:
                        if filters['has_categories']:
                            query = query.filter(TweetCache.categories_processed == True)
                            count_query = count_query.filter(TweetCache.categories_processed == True)
                        else:
                            query = query.filter(TweetCache.categories_processed == False)
                            count_query = count_query.filter(TweetCache.categories_processed == False)
                    
                    if 'has_kb_item' in filters:
                        if filters['has_kb_item']:
                            query = query.filter(TweetCache.kb_item_created == True)
                            count_query = count_query.filter(TweetCache.kb_item_created == True)
                        else:
                            query = query.filter(TweetCache.kb_item_created == False)
                            count_query = count_query.filter(TweetCache.kb_item_created == False)
                    
                    # Apply date filters
                    if 'created_after' in filters and filters['created_after']:
                        query = query.filter(TweetCache.created_at >= filters['created_after'])
                        count_query = count_query.filter(TweetCache.created_at >= filters['created_after'])
                    
                    if 'created_before' in filters and filters['created_before']:
                        query = query.filter(TweetCache.created_at <= filters['created_before'])
                        count_query = count_query.filter(TweetCache.created_at <= filters['created_before'])
                
                # Get total count
                total_count = count_query.scalar()
                
                # Apply sorting
                if hasattr(TweetCache, sort_by):
                    sort_column = getattr(TweetCache, sort_by)
                    if sort_order.lower() == 'desc':
                        query = query.order_by(desc(sort_column))
                    else:
                        query = query.order_by(asc(sort_column))
                else:
                    # Default sort
                    query = query.order_by(desc(TweetCache.updated_at))
                
                # Apply pagination
                query = query.offset(offset).limit(limit)
                
                # Execute query and detach results
                tweets = query.all()
                for tweet in tweets:
                    session.expunge(tweet)
                
                return tweets, total_count
                
        except Exception as e:
            self._handle_db_error("get filtered tweets", e)
            return [], 0
    
    def get_by_processing_status(self, status_filters: Dict[str, bool], 
                               limit: int = 100, offset: int = 0) -> List[TweetCache]:
        """
        Get tweets by processing status flags.
        
        Args:
            status_filters: Dict of processing flags and their required values
            limit: Maximum number of results
            offset: Number of results to skip
            
        Returns:
            List of TweetCache instances
        """
        try:
            with self._get_session() as session:
                query = session.query(TweetCache)
                
                for flag, value in status_filters.items():
                    if hasattr(TweetCache, flag):
                        query = query.filter(getattr(TweetCache, flag) == value)
                
                return query.offset(offset).limit(limit).all()
        except Exception as e:
            self._handle_db_error("get tweets by processing status", e)
    
    def get_by_category(self, main_category: str = None, sub_category: str = None,
                       limit: int = 100, offset: int = 0) -> List[TweetCache]:
        """
        Get tweets by category.
        
        Args:
            main_category: Main category filter
            sub_category: Sub category filter
            limit: Maximum number of results
            offset: Number of results to skip
            
        Returns:
            List of TweetCache instances
        """
        try:
            with self._get_session() as session:
                query = session.query(TweetCache)
                
                if main_category:
                    query = query.filter(TweetCache.main_category == main_category)
                if sub_category:
                    query = query.filter(TweetCache.sub_category == sub_category)
                
                return query.offset(offset).limit(limit).all()
        except Exception as e:
            self._handle_db_error("get tweets by category", e)
    
    def full_text_search(self, search_term: str, limit: int = 100, 
                        offset: int = 0) -> List[TweetCache]:
        """
        Perform full-text search on tweet content.
        
        Args:
            search_term: Text to search for
            limit: Maximum number of results
            offset: Number of results to skip
            
        Returns:
            List of TweetCache instances
        """
        try:
            with self._get_session() as session:
                # Use database-specific full-text search
                if session.bind.dialect.name == 'postgresql':
                    # PostgreSQL full-text search
                    query = session.query(TweetCache).filter(
                        func.to_tsvector('english', TweetCache.full_text).match(search_term)
                    )
                else:
                    # SQLite LIKE search
                    query = session.query(TweetCache).filter(
                        TweetCache.full_text.contains(search_term)
                    )
                
                return query.offset(offset).limit(limit).all()
        except Exception as e:
            self._handle_db_error("full text search", e)
    
    def advanced_search(self, filters: Dict[str, Any], limit: int = 100, 
                       offset: int = 0, order_by: str = 'updated_at',
                       order_direction: str = 'desc') -> Tuple[List[TweetCache], int]:
        """
        Advanced search with multiple filters and sorting.
        
        Args:
            filters: Dictionary of search filters
            limit: Maximum number of results
            offset: Number of results to skip
            order_by: Field to order by
            order_direction: 'asc' or 'desc'
            
        Returns:
            Tuple of (results, total_count)
        """
        try:
            with self._get_session() as session:
                query = session.query(TweetCache)
                
                # Apply filters
                if 'search_text' in filters:
                    if session.bind.dialect.name == 'postgresql':
                        query = query.filter(
                            func.to_tsvector('english', TweetCache.full_text).match(filters['search_text'])
                        )
                    else:
                        query = query.filter(TweetCache.full_text.contains(filters['search_text']))
                
                if 'main_category' in filters:
                    query = query.filter(TweetCache.main_category == filters['main_category'])
                
                if 'sub_category' in filters:
                    query = query.filter(TweetCache.sub_category == filters['sub_category'])
                
                if 'source' in filters:
                    query = query.filter(TweetCache.source == filters['source'])
                
                if 'processing_complete' in filters:
                    if filters['processing_complete']:
                        query = query.filter(
                            and_(
                                TweetCache.cache_complete == True,
                                TweetCache.media_processed == True,
                                TweetCache.categories_processed == True,
                                TweetCache.kb_item_created == True
                            )
                        )
                    else:
                        query = query.filter(
                            or_(
                                TweetCache.cache_complete == False,
                                TweetCache.media_processed == False,
                                TweetCache.categories_processed == False,
                                TweetCache.kb_item_created == False
                            )
                        )
                
                if 'needs_reprocessing' in filters:
                    if filters['needs_reprocessing']:
                        query = query.filter(
                            or_(
                                TweetCache.force_reprocess_pipeline == True,
                                TweetCache.force_recache == True
                            )
                        )
                    else:
                        query = query.filter(
                            and_(
                                TweetCache.force_reprocess_pipeline == False,
                                TweetCache.force_recache == False
                            )
                        )
                
                if 'date_range' in filters:
                    date_range = filters['date_range']
                    if 'start' in date_range:
                        query = query.filter(TweetCache.created_at >= date_range['start'])
                    if 'end' in date_range:
                        query = query.filter(TweetCache.created_at <= date_range['end'])
                
                # Get total count before applying limit/offset
                total_count = query.count()
                
                # Apply ordering
                if hasattr(TweetCache, order_by):
                    order_field = getattr(TweetCache, order_by)
                    if order_direction.lower() == 'desc':
                        query = query.order_by(desc(order_field))
                    else:
                        query = query.order_by(asc(order_field))
                
                # Apply pagination
                results = query.offset(offset).limit(limit).all()
                
                return results, total_count
        except Exception as e:
            self._handle_db_error("advanced search", e)
    
    # ===== REPROCESSING FLAG MANAGEMENT =====
    
    def get_tweets_needing_reprocessing(self, flag_type: str = None) -> List[TweetCache]:
        """
        Get tweets that need reprocessing.
        
        Args:
            flag_type: Specific flag type to filter by, or None for all
            
        Returns:
            List of TweetCache instances needing reprocessing
        """
        try:
            with self._get_session() as session:
                query = session.query(TweetCache)
                
                if flag_type == 'force_reprocess_pipeline':
                    query = query.filter(TweetCache.force_reprocess_pipeline == True)
                elif flag_type == 'force_recache':
                    query = query.filter(TweetCache.force_recache == True)
                else:
                    # Get all tweets needing any type of reprocessing
                    query = query.filter(
                        or_(
                            TweetCache.force_reprocess_pipeline == True,
                            TweetCache.force_recache == True
                        )
                    )
                
                return query.all()
        except Exception as e:
            self._handle_db_error("get tweets needing reprocessing", e)
    
    def clear_reprocessing_flags(self, tweet_id: str, flag_type: str = None) -> bool:
        """
        Clear reprocessing flags for a tweet.
        
        Args:
            tweet_id: Tweet ID to update
            flag_type: Specific flag to clear, or None to clear all
            
        Returns:
            True if updated, False if tweet not found
        """
        try:
            with self._get_session() as session:
                tweet = session.query(TweetCache).filter_by(tweet_id=tweet_id).first()
                if not tweet:
                    return False
                
                if flag_type == 'force_reprocess_pipeline' or flag_type is None:
                    tweet.force_reprocess_pipeline = False
                
                if flag_type == 'force_recache' or flag_type is None:
                    tweet.force_recache = False
                
                if flag_type is None:
                    tweet.reprocess_requested_at = None
                    tweet.reprocess_requested_by = None
                
                tweet.updated_at = datetime.now(timezone.utc)
                return True
        except Exception as e:
            self._handle_db_error("clear reprocessing flags", e)
    
    def set_reprocessing_flag(self, tweet_id: str, flag_type: str, 
                             requested_by: str = None) -> bool:
        """
        Set reprocessing flag for a tweet with audit trail.
        
        Args:
            tweet_id: Tweet ID to update
            flag_type: 'force_reprocess_pipeline' or 'force_recache'
            requested_by: User who requested reprocessing
            
        Returns:
            True if updated, False if tweet not found
        """
        if flag_type not in ['force_reprocess_pipeline', 'force_recache']:
            raise ValueError("flag_type must be 'force_reprocess_pipeline' or 'force_recache'")
        
        try:
            with self._get_session() as session:
                tweet = session.query(TweetCache).filter_by(tweet_id=tweet_id).first()
                if not tweet:
                    return False
                
                setattr(tweet, flag_type, True)
                tweet.reprocess_requested_at = datetime.now(timezone.utc)
                if requested_by:
                    tweet.reprocess_requested_by = requested_by
                tweet.updated_at = datetime.now(timezone.utc)
                
                return True
        except Exception as e:
            self._handle_db_error("set reprocessing flag", e)
    
    # ===== STATISTICS AND REPORTING =====
    
    def get_processing_statistics(self) -> Dict[str, Any]:
        """
        Get comprehensive processing statistics.
        
        Returns:
            Dictionary with processing statistics
        """
        try:
            with self._get_session() as session:
                total_tweets = session.query(TweetCache).count()
                
                # Processing completion stats
                cache_complete = session.query(TweetCache).filter_by(cache_complete=True).count()
                media_processed = session.query(TweetCache).filter_by(media_processed=True).count()
                categories_processed = session.query(TweetCache).filter_by(categories_processed=True).count()
                kb_items_created = session.query(TweetCache).filter_by(kb_item_created=True).count()
                
                # Fully processed tweets
                fully_processed = session.query(TweetCache).filter(
                    and_(
                        TweetCache.cache_complete == True,
                        TweetCache.media_processed == True,
                        TweetCache.categories_processed == True,
                        TweetCache.kb_item_created == True
                    )
                ).count()
                
                # Reprocessing stats
                needs_reprocessing = session.query(TweetCache).filter(
                    or_(
                        TweetCache.force_reprocess_pipeline == True,
                        TweetCache.force_recache == True
                    )
                ).count()
                
                # Category distribution
                category_stats = session.query(
                    TweetCache.main_category,
                    func.count(TweetCache.id).label('count')
                ).filter(
                    TweetCache.main_category.isnot(None)
                ).group_by(TweetCache.main_category).all()
                
                return {
                    'total_tweets': total_tweets,
                    'processing_completion': {
                        'cache_complete': cache_complete,
                        'media_processed': media_processed,
                        'categories_processed': categories_processed,
                        'kb_items_created': kb_items_created,
                        'fully_processed': fully_processed,
                        'completion_rate': (fully_processed / total_tweets * 100) if total_tweets > 0 else 0
                    },
                    'reprocessing': {
                        'needs_reprocessing': needs_reprocessing,
                        'reprocessing_rate': (needs_reprocessing / total_tweets * 100) if total_tweets > 0 else 0
                    },
                    'categories': {
                        category: count for category, count in category_stats
                    }
                }
        except Exception as e:
            self._handle_db_error("get processing statistics", e)
    
    def get_tweets_by_date_range(self, start_date: datetime, end_date: datetime,
                                limit: int = 100, offset: int = 0) -> List[TweetCache]:
        """
        Get tweets within a date range.
        
        Args:
            start_date: Start of date range
            end_date: End of date range
            limit: Maximum number of results
            offset: Number of results to skip
            
        Returns:
            List of TweetCache instances
        """
        try:
            with self._get_session() as session:
                return session.query(TweetCache).filter(
                    and_(
                        TweetCache.created_at >= start_date,
                        TweetCache.created_at <= end_date
                    )
                ).offset(offset).limit(limit).all()
        except Exception as e:
            self._handle_db_error("get tweets by date range", e)


class TweetProcessingQueueRepository(BaseRepository):
    """
    Repository for TweetProcessingQueue model operations.
    
    Provides priority-based queue operations, retry logic, processing phase tracking,
    and bulk status update operations for tweet processing workflow management.
    """
    
    def __init__(self):
        super().__init__(TweetProcessingQueue)
    
    # ===== BASIC CRUD OPERATIONS =====
    
    def create(self, queue_data: Dict[str, Any]) -> TweetProcessingQueue:
        """
        Create a new processing queue entry.
        
        Args:
            queue_data: Dictionary containing queue entry data
            
        Returns:
            Created TweetProcessingQueue instance
            
        Raises:
            IntegrityError: If tweet_id already exists in queue
        """
        try:
            with self._get_session() as session:
                queue_entry = TweetProcessingQueue(**queue_data)
                session.add(queue_entry)
                session.flush()
                session.refresh(queue_entry)
                session.expunge(queue_entry)
                return queue_entry
        except IntegrityError as e:
            self._handle_db_error("create queue entry", e)
        except Exception as e:
            self._handle_db_error("create queue entry", e)
    
    def get_by_tweet_id(self, tweet_id: str) -> Optional[TweetProcessingQueue]:
        """
        Get queue entry by tweet_id.
        
        Args:
            tweet_id: The tweet ID to search for
            
        Returns:
            TweetProcessingQueue instance or None if not found
        """
        try:
            with self._get_session() as session:
                entry = session.query(TweetProcessingQueue).filter_by(tweet_id=tweet_id).first()
                if entry:
                    session.expunge(entry)
                return entry
        except Exception as e:
            self._handle_db_error("get queue entry by tweet id", e)
    
    def get_by_id(self, entry_id: int) -> Optional[TweetProcessingQueue]:
        """
        Get queue entry by primary key.
        
        Args:
            entry_id: Primary key ID
            
        Returns:
            TweetProcessingQueue instance or None if not found
        """
        try:
            with self._get_session() as session:
                entry = session.query(TweetProcessingQueue).get(entry_id)
                if entry:
                    session.expunge(entry)
                return entry
        except Exception as e:
            self._handle_db_error("get queue entry by id", e)
    
    def get_by_tweet_ids(self, tweet_ids: List[str]) -> List[TweetProcessingQueue]:
        """
        Get queue entries by a list of tweet IDs.
        
        Args:
            tweet_ids: List of tweet IDs to retrieve
            
        Returns:
            List of TweetProcessingQueue instances
        """
        try:
            with self._get_session() as session:
                entries = session.query(TweetProcessingQueue).filter(
                    TweetProcessingQueue.tweet_id.in_(tweet_ids)
                ).all()
                
                # Detach from session
                for entry in entries:
                    session.expunge(entry)
                
                return entries
        except Exception as e:
            self._handle_db_error("get queue entries by tweet IDs", e)
            return []
    
    def get_all(self, limit: int = None, offset: int = 0) -> List[TweetProcessingQueue]:
        """
        Get all queue entries.
        
        Args:
            limit: Maximum number of entries to return (None for all)
            offset: Number of entries to skip
            
        Returns:
            List of TweetProcessingQueue instances
        """
        try:
            with self._get_session() as session:
                query = session.query(TweetProcessingQueue)
                
                if offset > 0:
                    query = query.offset(offset)
                
                if limit is not None:
                    query = query.limit(limit)
                
                entries = query.all()
                
                # Detach from session
                for entry in entries:
                    session.expunge(entry)
                
                return entries
        except Exception as e:
            self._handle_db_error("get all queue entries", e)
            return []
    
    def update_status(self, tweet_id: str, status: str, processing_phase: str = None,
                     error_message: str = None, increment_retry: bool = False) -> Optional[TweetProcessingQueue]:
        """
        Update queue entry status and related fields.
        
        Args:
            tweet_id: Tweet ID to update
            status: New status ('unprocessed', 'processing', 'processed', 'failed')
            processing_phase: Current processing phase
            error_message: Error message if status is 'failed'
            increment_retry: Whether to increment retry count
            
        Returns:
            Updated TweetProcessingQueue instance or None if not found
        """
        try:
            with self._get_session() as session:
                entry = session.query(TweetProcessingQueue).filter_by(tweet_id=tweet_id).first()
                if entry:
                    entry.status = status
                    if processing_phase:
                        entry.processing_phase = processing_phase
                    if error_message:
                        entry.last_error = error_message
                    if increment_retry:
                        entry.retry_count += 1
                    if status == 'processed':
                        entry.processed_at = datetime.now(timezone.utc)
                    entry.updated_at = datetime.now(timezone.utc)
                    
                    session.flush()
                    session.refresh(entry)
                    session.expunge(entry)
                return entry
        except Exception as e:
            self._handle_db_error("update queue entry status", e)
    
    def delete(self, tweet_id: str) -> bool:
        """
        Delete queue entry.
        
        Args:
            tweet_id: Tweet ID to delete
            
        Returns:
            True if deleted, False if not found
        """
        try:
            with self._get_session() as session:
                entry = session.query(TweetProcessingQueue).filter_by(tweet_id=tweet_id).first()
                if entry:
                    session.delete(entry)
                    return True
                return False
        except Exception as e:
            self._handle_db_error("delete queue entry", e)
    
    # ===== QUEUE OPERATIONS =====
    
    def get_next_for_processing(self, limit: int = 10, processing_phase: str = None) -> List[TweetProcessingQueue]:
        """
        Get next tweets for processing based on priority and status.
        
        Args:
            limit: Maximum number of entries to return
            processing_phase: Filter by specific processing phase
            
        Returns:
            List of TweetProcessingQueue instances ready for processing
        """
        try:
            with self._get_session() as session:
                query = session.query(TweetProcessingQueue).filter(
                    TweetProcessingQueue.status == 'unprocessed'
                )
                
                if processing_phase:
                    query = query.filter(TweetProcessingQueue.processing_phase == processing_phase)
                
                # Order by priority (higher first), then by creation time (older first)
                entries = query.order_by(
                    desc(TweetProcessingQueue.priority),
                    asc(TweetProcessingQueue.created_at)
                ).limit(limit).all()
                
                # Detach from session
                for entry in entries:
                    session.expunge(entry)
                
                return entries
        except Exception as e:
            self._handle_db_error("get next for processing", e)
    
    def mark_as_processing(self, tweet_ids: List[str], processing_phase: str) -> int:
        """
        Mark multiple tweets as currently being processed.
        
        Args:
            tweet_ids: List of tweet IDs to mark as processing
            processing_phase: Current processing phase
            
        Returns:
            Number of entries updated
        """
        try:
            with self._get_session() as session:
                result = session.query(TweetProcessingQueue).filter(
                    TweetProcessingQueue.tweet_id.in_(tweet_ids),
                    TweetProcessingQueue.status == 'unprocessed'
                ).update({
                    'status': 'processing',
                    'processing_phase': processing_phase,
                    'updated_at': datetime.now(timezone.utc)
                }, synchronize_session=False)
                
                return result
        except Exception as e:
            self._handle_db_error("mark as processing", e)
    
    def get_by_status(self, status: str, limit: int = 100, offset: int = 0) -> List[TweetProcessingQueue]:
        """
        Get queue entries by status.
        
        Args:
            status: Status to filter by
            limit: Maximum number of results
            offset: Number of results to skip
            
        Returns:
            List of TweetProcessingQueue instances
        """
        try:
            with self._get_session() as session:
                entries = session.query(TweetProcessingQueue).filter_by(
                    status=status
                ).offset(offset).limit(limit).all()
                
                # Detach from session
                for entry in entries:
                    session.expunge(entry)
                
                return entries
        except Exception as e:
            self._handle_db_error("get by status", e)
    
    def get_by_processing_phase(self, processing_phase: str, limit: int = 100, 
                               offset: int = 0) -> List[TweetProcessingQueue]:
        """
        Get queue entries by processing phase.
        
        Args:
            processing_phase: Processing phase to filter by
            limit: Maximum number of results
            offset: Number of results to skip
            
        Returns:
            List of TweetProcessingQueue instances
        """
        try:
            with self._get_session() as session:
                entries = session.query(TweetProcessingQueue).filter_by(
                    processing_phase=processing_phase
                ).offset(offset).limit(limit).all()
                
                # Detach from session
                for entry in entries:
                    session.expunge(entry)
                
                return entries
        except Exception as e:
            self._handle_db_error("get by processing phase", e)
    
    # ===== BULK OPERATIONS =====
    
    def bulk_create(self, queue_entries: List[Dict[str, Any]]) -> List[TweetProcessingQueue]:
        """
        Create multiple queue entries efficiently.
        
        Args:
            queue_entries: List of queue entry data dictionaries
            
        Returns:
            List of created TweetProcessingQueue instances
        """
        try:
            with self._get_session() as session:
                entries = [TweetProcessingQueue(**data) for data in queue_entries]
                session.add_all(entries)
                session.flush()
                
                for entry in entries:
                    session.refresh(entry)
                    session.expunge(entry)
                
                return entries
        except Exception as e:
            self._handle_db_error("bulk create queue entries", e)
    
    def bulk_update_status(self, updates: List[Dict[str, Any]]) -> int:
        """
        Bulk update status for multiple queue entries.
        
        Args:
            updates: List of dicts with 'tweet_id' and status updates
            
        Returns:
            Number of entries updated
        """
        try:
            updated_count = 0
            with self._get_session() as session:
                for update in updates:
                    tweet_id = update.pop('tweet_id')
                    update['updated_at'] = datetime.now(timezone.utc)
                    
                    result = session.query(TweetProcessingQueue).filter_by(
                        tweet_id=tweet_id
                    ).update(update)
                    updated_count += result
                
                return updated_count
        except Exception as e:
            self._handle_db_error("bulk update status", e)
    
    def bulk_set_priority(self, tweet_ids: List[str], priority: int) -> int:
        """
        Bulk set priority for multiple queue entries.
        
        Args:
            tweet_ids: List of tweet IDs to update
            priority: New priority value
            
        Returns:
            Number of entries updated
        """
        try:
            with self._get_session() as session:
                result = session.query(TweetProcessingQueue).filter(
                    TweetProcessingQueue.tweet_id.in_(tweet_ids)
                ).update({
                    'priority': priority,
                    'updated_at': datetime.now(timezone.utc)
                }, synchronize_session=False)
                
                return result
        except Exception as e:
            self._handle_db_error("bulk set priority", e)
    
    # ===== RETRY LOGIC =====
    
    def get_failed_entries(self, max_retries: int = 3, limit: int = 100) -> List[TweetProcessingQueue]:
        """
        Get failed entries that can be retried.
        
        Args:
            max_retries: Maximum number of retries allowed
            limit: Maximum number of results
            
        Returns:
            List of TweetProcessingQueue instances that can be retried
        """
        try:
            with self._get_session() as session:
                entries = session.query(TweetProcessingQueue).filter(
                    and_(
                        TweetProcessingQueue.status == 'failed',
                        TweetProcessingQueue.retry_count < max_retries
                    )
                ).limit(limit).all()
                
                # Detach from session
                for entry in entries:
                    session.expunge(entry)
                
                return entries
        except Exception as e:
            self._handle_db_error("get failed entries", e)
    
    def reset_for_retry(self, tweet_id: str) -> bool:
        """
        Reset a failed entry for retry.
        
        Args:
            tweet_id: Tweet ID to reset
            
        Returns:
            True if reset successfully, False if not found
        """
        try:
            with self._get_session() as session:
                entry = session.query(TweetProcessingQueue).filter_by(tweet_id=tweet_id).first()
                if entry and entry.status == 'failed':
                    entry.status = 'unprocessed'
                    entry.last_error = None
                    entry.updated_at = datetime.now(timezone.utc)
                    return True
                return False
        except Exception as e:
            self._handle_db_error("reset for retry", e)
    
    def bulk_reset_for_retry(self, tweet_ids: List[str]) -> int:
        """
        Bulk reset failed entries for retry.
        
        Args:
            tweet_ids: List of tweet IDs to reset
            
        Returns:
            Number of entries reset
        """
        try:
            with self._get_session() as session:
                result = session.query(TweetProcessingQueue).filter(
                    and_(
                        TweetProcessingQueue.tweet_id.in_(tweet_ids),
                        TweetProcessingQueue.status == 'failed'
                    )
                ).update({
                    'status': 'unprocessed',
                    'last_error': None,
                    'updated_at': datetime.now(timezone.utc)
                }, synchronize_session=False)
                
                return result
        except Exception as e:
            self._handle_db_error("bulk reset for retry", e)
    
    # ===== STATISTICS AND MONITORING =====
    
    def get_queue_statistics(self) -> Dict[str, Any]:
        """
        Get comprehensive queue statistics.
        
        Returns:
            Dictionary with queue statistics
        """
        try:
            with self._get_session() as session:
                total_entries = session.query(TweetProcessingQueue).count()
                
                # Status distribution
                status_stats = session.query(
                    TweetProcessingQueue.status,
                    func.count(TweetProcessingQueue.id).label('count')
                ).group_by(TweetProcessingQueue.status).all()
                
                # Processing phase distribution
                phase_stats = session.query(
                    TweetProcessingQueue.processing_phase,
                    func.count(TweetProcessingQueue.id).label('count')
                ).filter(
                    TweetProcessingQueue.processing_phase.isnot(None)
                ).group_by(TweetProcessingQueue.processing_phase).all()
                
                # Priority distribution
                priority_stats = session.query(
                    TweetProcessingQueue.priority,
                    func.count(TweetProcessingQueue.id).label('count')
                ).group_by(TweetProcessingQueue.priority).all()
                
                # Retry statistics
                retry_stats = session.query(
                    func.avg(TweetProcessingQueue.retry_count).label('avg_retries'),
                    func.max(TweetProcessingQueue.retry_count).label('max_retries'),
                    func.count(TweetProcessingQueue.id).filter(
                        TweetProcessingQueue.retry_count > 0
                    ).label('entries_with_retries')
                ).first()
                
                return {
                    'total_entries': total_entries,
                    'status_distribution': {
                        status: count for status, count in status_stats
                    },
                    'phase_distribution': {
                        phase: count for phase, count in phase_stats
                    },
                    'priority_distribution': {
                        priority: count for priority, count in priority_stats
                    },
                    'retry_statistics': {
                        'average_retries': float(retry_stats.avg_retries) if retry_stats.avg_retries else 0,
                        'max_retries': retry_stats.max_retries or 0,
                        'entries_with_retries': retry_stats.entries_with_retries or 0
                    }
                }
        except Exception as e:
            self._handle_db_error("get queue statistics", e)
    
    def get_processing_performance(self, hours: int = 24) -> Dict[str, Any]:
        """
        Get processing performance metrics for the last N hours.
        
        Args:
            hours: Number of hours to look back
            
        Returns:
            Dictionary with performance metrics
        """
        try:
            with self._get_session() as session:
                cutoff_time = datetime.now(timezone.utc) - timedelta(hours=hours)
                
                # Processed in time period
                processed_count = session.query(TweetProcessingQueue).filter(
                    and_(
                        TweetProcessingQueue.status == 'processed',
                        TweetProcessingQueue.processed_at >= cutoff_time
                    )
                ).count()
                
                # Failed in time period
                failed_count = session.query(TweetProcessingQueue).filter(
                    and_(
                        TweetProcessingQueue.status == 'failed',
                        TweetProcessingQueue.updated_at >= cutoff_time
                    )
                ).count()
                
                # Average processing time (for completed items)
                avg_processing_time = session.query(
                    func.avg(
                        func.julianday(TweetProcessingQueue.processed_at) - 
                        func.julianday(TweetProcessingQueue.created_at)
                    ).label('avg_time_days')
                ).filter(
                    and_(
                        TweetProcessingQueue.status == 'processed',
                        TweetProcessingQueue.processed_at >= cutoff_time
                    )
                ).scalar()
                
                # Convert days to hours
                avg_processing_hours = (avg_processing_time * 24) if avg_processing_time else 0
                
                # Success rate
                total_completed = processed_count + failed_count
                success_rate = (processed_count / total_completed * 100) if total_completed > 0 else 0
                
                return {
                    'time_period_hours': hours,
                    'processed_count': processed_count,
                    'failed_count': failed_count,
                    'total_completed': total_completed,
                    'success_rate': success_rate,
                    'average_processing_time_hours': avg_processing_hours,
                    'throughput_per_hour': processed_count / hours if hours > 0 else 0
                }
        except Exception as e:
            self._handle_db_error("get processing performance", e)
    
    def cleanup_old_entries(self, days: int = 30, status_filter: List[str] = None) -> int:
        """
        Clean up old queue entries.
        
        Args:
            days: Delete entries older than this many days
            status_filter: Only delete entries with these statuses
            
        Returns:
            Number of entries deleted
        """
        try:
            with self._get_session() as session:
                cutoff_time = datetime.now(timezone.utc) - timedelta(days=days)
                
                query = session.query(TweetProcessingQueue).filter(
                    TweetProcessingQueue.created_at < cutoff_time
                )
                
                if status_filter:
                    query = query.filter(TweetProcessingQueue.status.in_(status_filter))
                
                # Get count before deletion
                count = query.count()
                
                # Delete entries
                query.delete(synchronize_session=False)
                
                return count
        except Exception as e:
            self._handle_db_error("cleanup old entries", e)


class CategoryRepository(BaseRepository):
    """
    Repository for CategoryHierarchy model operations.
    
    Provides hierarchical category management, item count maintenance,
    and category structure operations for content organization.
    """
    
    def __init__(self):
        super().__init__(CategoryHierarchy)
    
    # ===== BASIC CRUD OPERATIONS =====
    
    def create(self, category_data: Dict[str, Any]) -> CategoryHierarchy:
        """
        Create a new category hierarchy entry.
        
        Args:
            category_data: Dictionary containing category data
            
        Returns:
            Created CategoryHierarchy instance
            
        Raises:
            IntegrityError: If main_category/sub_category combination already exists
        """
        try:
            with self._get_session() as session:
                category = CategoryHierarchy(**category_data)
                session.add(category)
                session.flush()
                session.refresh(category)
                session.expunge(category)
                return category
        except IntegrityError as e:
            self._handle_db_error("create category", e)
        except Exception as e:
            self._handle_db_error("create category", e)
    
    def get_by_category_combination(self, main_category: str, sub_category: str) -> Optional[CategoryHierarchy]:
        """
        Get category by main_category and sub_category combination.
        
        Args:
            main_category: Main category name
            sub_category: Sub category name
            
        Returns:
            CategoryHierarchy instance or None if not found
        """
        try:
            with self._get_session() as session:
                category = session.query(CategoryHierarchy).filter_by(
                    main_category=main_category,
                    sub_category=sub_category
                ).first()
                if category:
                    session.expunge(category)
                return category
        except Exception as e:
            self._handle_db_error("get category by combination", e)
    
    def get_by_id(self, category_id: int) -> Optional[CategoryHierarchy]:
        """
        Get category by primary key.
        
        Args:
            category_id: Primary key ID
            
        Returns:
            CategoryHierarchy instance or None if not found
        """
        try:
            with self._get_session() as session:
                category = session.query(CategoryHierarchy).get(category_id)
                if category:
                    session.expunge(category)
                return category
        except Exception as e:
            self._handle_db_error("get category by id", e)
    
    def update(self, category_id: int, updates: Dict[str, Any]) -> Optional[CategoryHierarchy]:
        """
        Update category with new data.
        
        Args:
            category_id: Primary key ID
            updates: Dictionary of fields to update
            
        Returns:
            Updated CategoryHierarchy instance or None if not found
        """
        try:
            with self._get_session() as session:
                category = session.query(CategoryHierarchy).get(category_id)
                if category:
                    for key, value in updates.items():
                        if hasattr(category, key):
                            setattr(category, key, value)
                    
                    session.flush()
                    session.refresh(category)
                    session.expunge(category)
                return category
        except Exception as e:
            self._handle_db_error("update category", e)
    
    def delete(self, category_id: int) -> bool:
        """
        Delete category.
        
        Args:
            category_id: Primary key ID to delete
            
        Returns:
            True if deleted, False if not found
        """
        try:
            with self._get_session() as session:
                category = session.query(CategoryHierarchy).get(category_id)
                if category:
                    session.delete(category)
                    return True
                return False
        except Exception as e:
            self._handle_db_error("delete category", e)
    
    # ===== HIERARCHICAL OPERATIONS =====
    
    def get_all_main_categories(self, only_active: bool = True) -> List[str]:
        """
        Get list of all main categories.
        
        Args:
            only_active: Whether to include only active categories
            
        Returns:
            List of unique main category names
        """
        try:
            with self._get_session() as session:
                query = session.query(CategoryHierarchy.main_category).distinct()
                
                if only_active:
                    query = query.filter(CategoryHierarchy.is_active == True)
                
                results = query.all()
                return [row[0] for row in results]
        except Exception as e:
            self._handle_db_error("get all main categories", e)
    
    def get_sub_categories_for_main(self, main_category: str, only_active: bool = True) -> List[CategoryHierarchy]:
        """
        Get all sub-categories for a given main category.
        
        Args:
            main_category: Main category to get sub-categories for
            only_active: Whether to include only active categories
            
        Returns:
            List of CategoryHierarchy instances for the main category
        """
        try:
            with self._get_session() as session:
                query = session.query(CategoryHierarchy).filter_by(main_category=main_category)
                
                if only_active:
                    query = query.filter(CategoryHierarchy.is_active == True)
                
                categories = query.order_by(CategoryHierarchy.sort_order, CategoryHierarchy.sub_category).all()
                
                # Detach from session
                for category in categories:
                    session.expunge(category)
                
                return categories
        except Exception as e:
            self._handle_db_error("get sub categories for main", e)
    
    def get_full_hierarchy(self, only_active: bool = True) -> Dict[str, List[CategoryHierarchy]]:
        """
        Get complete category hierarchy organized by main category.
        
        Args:
            only_active: Whether to include only active categories
            
        Returns:
            Dictionary mapping main_category to list of CategoryHierarchy instances
        """
        try:
            with self._get_session() as session:
                query = session.query(CategoryHierarchy)
                
                if only_active:
                    query = query.filter(CategoryHierarchy.is_active == True)
                
                categories = query.order_by(
                    CategoryHierarchy.main_category,
                    CategoryHierarchy.sort_order,
                    CategoryHierarchy.sub_category
                ).all()
                
                # Detach from session
                for category in categories:
                    session.expunge(category)
                
                # Organize by main category
                hierarchy = {}
                for category in categories:
                    if category.main_category not in hierarchy:
                        hierarchy[category.main_category] = []
                    hierarchy[category.main_category].append(category)
                
                return hierarchy
        except Exception as e:
            self._handle_db_error("get full hierarchy", e)
    
    # ===== ITEM COUNT MANAGEMENT =====
    
    def update_item_count(self, main_category: str, sub_category: str, count: int) -> Optional[CategoryHierarchy]:
        """
        Update item count for a category.
        
        Args:
            main_category: Main category name
            sub_category: Sub category name
            count: New item count
            
        Returns:
            Updated CategoryHierarchy instance or None if not found
        """
        try:
            with self._get_session() as session:
                category = session.query(CategoryHierarchy).filter_by(
                    main_category=main_category,
                    sub_category=sub_category
                ).first()
                
                if category:
                    category.item_count = count
                    category.last_updated = datetime.now(timezone.utc)
                    
                    session.flush()
                    session.refresh(category)
                    session.expunge(category)
                return category
        except Exception as e:
            self._handle_db_error("update item count", e)
    
    def increment_item_count(self, main_category: str, sub_category: str, increment: int = 1) -> Optional[CategoryHierarchy]:
        """
        Increment item count for a category.
        
        Args:
            main_category: Main category name
            sub_category: Sub category name
            increment: Amount to increment (can be negative)
            
        Returns:
            Updated CategoryHierarchy instance or None if not found
        """
        try:
            with self._get_session() as session:
                category = session.query(CategoryHierarchy).filter_by(
                    main_category=main_category,
                    sub_category=sub_category
                ).first()
                
                if category:
                    category.item_count = max(0, category.item_count + increment)
                    category.last_updated = datetime.now(timezone.utc)
                    
                    session.flush()
                    session.refresh(category)
                    session.expunge(category)
                return category
        except Exception as e:
            self._handle_db_error("increment item count", e)
    
    def refresh_all_item_counts(self) -> Dict[str, int]:
        """
        Refresh item counts for all categories by counting actual knowledge base items.
        
        Returns:
            Dictionary mapping "main_category/sub_category" to updated count
        """
        try:
            with self._get_session() as session:
                # Get actual counts from knowledge base items
                from .models import KnowledgeBaseItem
                
                count_query = session.query(
                    KnowledgeBaseItem.main_category,
                    KnowledgeBaseItem.sub_category,
                    func.count(KnowledgeBaseItem.id).label('count')
                ).group_by(
                    KnowledgeBaseItem.main_category,
                    KnowledgeBaseItem.sub_category
                ).all()
                
                updated_counts = {}
                
                # Update each category's item count
                for main_cat, sub_cat, count in count_query:
                    category = session.query(CategoryHierarchy).filter_by(
                        main_category=main_cat,
                        sub_category=sub_cat
                    ).first()
                    
                    if category:
                        category.item_count = count
                        category.last_updated = datetime.now(timezone.utc)
                        updated_counts[f"{main_cat}/{sub_cat}"] = count
                
                # Set zero counts for categories with no items
                all_categories = session.query(CategoryHierarchy).all()
                for category in all_categories:
                    key = f"{category.main_category}/{category.sub_category}"
                    if key not in updated_counts:
                        category.item_count = 0
                        category.last_updated = datetime.now(timezone.utc)
                        updated_counts[key] = 0
                
                return updated_counts
        except Exception as e:
            self._handle_db_error("refresh all item counts", e)
    
    # ===== SEARCH AND FILTERING =====
    
    def search_categories(self, search_term: str, only_active: bool = True) -> List[CategoryHierarchy]:
        """
        Search categories by name or description.
        
        Args:
            search_term: Term to search for
            only_active: Whether to include only active categories
            
        Returns:
            List of matching CategoryHierarchy instances
        """
        try:
            with self._get_session() as session:
                search_pattern = f"%{search_term.lower()}%"
                
                query = session.query(CategoryHierarchy).filter(
                    or_(
                        func.lower(CategoryHierarchy.main_category).like(search_pattern),
                        func.lower(CategoryHierarchy.sub_category).like(search_pattern),
                        func.lower(CategoryHierarchy.display_name).like(search_pattern),
                        func.lower(CategoryHierarchy.description).like(search_pattern)
                    )
                )
                
                if only_active:
                    query = query.filter(CategoryHierarchy.is_active == True)
                
                categories = query.order_by(
                    CategoryHierarchy.main_category,
                    CategoryHierarchy.sort_order,
                    CategoryHierarchy.sub_category
                ).all()
                
                # Detach from session
                for category in categories:
                    session.expunge(category)
                
                return categories
        except Exception as e:
            self._handle_db_error("search categories", e)
    
    def get_categories_with_items(self, min_items: int = 1) -> List[CategoryHierarchy]:
        """
        Get categories that have at least the specified number of items.
        
        Args:
            min_items: Minimum number of items required
            
        Returns:
            List of CategoryHierarchy instances with sufficient items
        """
        try:
            with self._get_session() as session:
                categories = session.query(CategoryHierarchy).filter(
                    and_(
                        CategoryHierarchy.item_count >= min_items,
                        CategoryHierarchy.is_active == True
                    )
                ).order_by(
                    desc(CategoryHierarchy.item_count),
                    CategoryHierarchy.main_category,
                    CategoryHierarchy.sub_category
                ).all()
                
                # Detach from session
                for category in categories:
                    session.expunge(category)
                
                return categories
        except Exception as e:
            self._handle_db_error("get categories with items", e)
    
    def get_all(self, limit: int = None, offset: int = 0) -> List[CategoryHierarchy]:
        """
        Get all categories.
        
        Args:
            limit: Maximum number of categories to return (None for all)
            offset: Number of categories to skip
            
        Returns:
            List of CategoryHierarchy instances
        """
        try:
            with self._get_session() as session:
                query = session.query(CategoryHierarchy).order_by(
                    CategoryHierarchy.main_category,
                    CategoryHierarchy.sub_category
                )
                
                if offset > 0:
                    query = query.offset(offset)
                
                if limit is not None:
                    query = query.limit(limit)
                
                categories = query.all()
                
                # Detach from session
                for category in categories:
                    session.expunge(category)
                
                return categories
        except Exception as e:
            self._handle_db_error("get all categories", e)
            return []


class ProcessingStatisticsRepository(BaseRepository):
    """
    Repository for ProcessingStatistics model operations.
    
    Provides detailed phase-by-phase processing statistics and metrics
    with aggregation methods for performance reporting.
    """
    
    def __init__(self):
        super().__init__(ProcessingStatistics)
    
    # ===== BASIC CRUD OPERATIONS =====
    
    def create(self, stats_data: Dict[str, Any]) -> ProcessingStatistics:
        """
        Create a new processing statistics entry.
        
        Args:
            stats_data: Dictionary containing statistics data
            
        Returns:
            Created ProcessingStatistics instance
            
        Raises:
            IntegrityError: If phase_name/metric_name/run_id combination already exists
        """
        try:
            with self._get_session() as session:
                stats = ProcessingStatistics(**stats_data)
                session.add(stats)
                session.flush()
                session.refresh(stats)
                session.expunge(stats)
                return stats
        except IntegrityError as e:
            self._handle_db_error("create processing statistics", e)
        except Exception as e:
            self._handle_db_error("create processing statistics", e)
    
    def get_by_phase_and_metric(self, phase_name: str, metric_name: str, run_id: str = None) -> Optional[ProcessingStatistics]:
        """
        Get statistics by phase and metric name.
        
        Args:
            phase_name: Processing phase name
            metric_name: Metric name
            run_id: Optional run ID filter
            
        Returns:
            ProcessingStatistics instance or None if not found
        """
        try:
            with self._get_session() as session:
                query = session.query(ProcessingStatistics).filter_by(
                    phase_name=phase_name,
                    metric_name=metric_name
                )
                
                if run_id:
                    query = query.filter_by(run_id=run_id)
                
                stats = query.first()
                if stats:
                    session.expunge(stats)
                return stats
        except Exception as e:
            self._handle_db_error("get stats by phase and metric", e)
    
    def update_or_create(self, phase_name: str, metric_name: str, metric_value: float,
                        run_id: str = None, **kwargs) -> ProcessingStatistics:
        """
        Update existing statistics or create new entry.
        
        Args:
            phase_name: Processing phase name
            metric_name: Metric name
            metric_value: Metric value
            run_id: Run ID for this statistic
            **kwargs: Additional fields to set
            
        Returns:
            Updated or created ProcessingStatistics instance
        """
        try:
            with self._get_session() as session:
                # Try to find existing entry
                stats = session.query(ProcessingStatistics).filter_by(
                    phase_name=phase_name,
                    metric_name=metric_name,
                    run_id=run_id
                ).first()
                
                if stats:
                    # Update existing
                    stats.metric_value = metric_value
                    for key, value in kwargs.items():
                        if hasattr(stats, key):
                            setattr(stats, key, value)
                else:
                    # Create new
                    stats_data = {
                        'phase_name': phase_name,
                        'metric_name': metric_name,
                        'metric_value': metric_value,
                        'run_id': run_id,
                        **kwargs
                    }
                    stats = ProcessingStatistics(**stats_data)
                    session.add(stats)
                
                session.flush()
                session.refresh(stats)
                session.expunge(stats)
                return stats
        except Exception as e:
            self._handle_db_error("update or create statistics", e)
    
    # ===== PHASE-BASED OPERATIONS =====
    
    def get_phase_statistics(self, phase_name: str, run_id: str = None) -> List[ProcessingStatistics]:
        """
        Get all statistics for a specific phase.
        
        Args:
            phase_name: Processing phase name
            run_id: Optional run ID filter
            
        Returns:
            List of ProcessingStatistics instances for the phase
        """
        try:
            with self._get_session() as session:
                query = session.query(ProcessingStatistics).filter_by(phase_name=phase_name)
                
                if run_id:
                    query = query.filter_by(run_id=run_id)
                
                stats = query.order_by(ProcessingStatistics.recorded_at.desc()).all()
                
                # Detach from session
                for stat in stats:
                    session.expunge(stat)
                
                return stats
        except Exception as e:
            self._handle_db_error("get phase statistics", e)
    
    def get_run_statistics(self, run_id: str) -> List[ProcessingStatistics]:
        """
        Get all statistics for a specific run.
        
        Args:
            run_id: Run ID to get statistics for
            
        Returns:
            List of ProcessingStatistics instances for the run
        """
        try:
            with self._get_session() as session:
                stats = session.query(ProcessingStatistics).filter_by(run_id=run_id).order_by(
                    ProcessingStatistics.phase_name,
                    ProcessingStatistics.metric_name
                ).all()
                
                # Detach from session
                for stat in stats:
                    session.expunge(stat)
                
                return stats
        except Exception as e:
            self._handle_db_error("get run statistics", e)
    
    def get_latest_statistics(self, limit: int = 100) -> List[ProcessingStatistics]:
        """
        Get most recent statistics entries.
        
        Args:
            limit: Maximum number of entries to return
            
        Returns:
            List of most recent ProcessingStatistics instances
        """
        try:
            with self._get_session() as session:
                stats = session.query(ProcessingStatistics).order_by(
                    ProcessingStatistics.recorded_at.desc()
                ).limit(limit).all()
                
                # Detach from session
                for stat in stats:
                    session.expunge(stat)
                
                return stats
        except Exception as e:
            self._handle_db_error("get latest statistics", e)
    
    # ===== AGGREGATION AND REPORTING =====
    
    def get_phase_summary(self, phase_name: str, hours: int = 24) -> Dict[str, Any]:
        """
        Get summary statistics for a phase over the specified time period.
        
        Args:
            phase_name: Processing phase name
            hours: Number of hours to look back
            
        Returns:
            Dictionary containing aggregated statistics
        """
        try:
            with self._get_session() as session:
                cutoff_time = datetime.now(timezone.utc) - timedelta(hours=hours)
                
                # Get all metrics for this phase in the time period
                stats = session.query(ProcessingStatistics).filter(
                    and_(
                        ProcessingStatistics.phase_name == phase_name,
                        ProcessingStatistics.recorded_at >= cutoff_time
                    )
                ).all()
                
                if not stats:
                    return {'phase_name': phase_name, 'time_period_hours': hours, 'metrics': {}}
                
                # Aggregate by metric name
                metrics = {}
                for stat in stats:
                    metric_name = stat.metric_name
                    if metric_name not in metrics:
                        metrics[metric_name] = {
                            'values': [],
                            'total_items_processed': 0,
                            'total_duration_seconds': 0,
                            'unit': stat.metric_unit
                        }
                    
                    metrics[metric_name]['values'].append(float(stat.metric_value) if stat.metric_value else 0)
                    metrics[metric_name]['total_items_processed'] += stat.total_items_processed or 0
                    metrics[metric_name]['total_duration_seconds'] += float(stat.total_duration_seconds or 0)
                
                # Calculate aggregations
                for metric_name, data in metrics.items():
                    values = data['values']
                    metrics[metric_name].update({
                        'count': len(values),
                        'min': min(values) if values else 0,
                        'max': max(values) if values else 0,
                        'avg': sum(values) / len(values) if values else 0,
                        'latest': values[-1] if values else 0
                    })
                
                return {
                    'phase_name': phase_name,
                    'time_period_hours': hours,
                    'metrics': metrics,
                    'total_entries': len(stats)
                }
        except Exception as e:
            self._handle_db_error("get phase summary", e)
    
    def get_performance_trends(self, metric_name: str, days: int = 7) -> Dict[str, Any]:
        """
        Get performance trends for a specific metric over time.
        
        Args:
            metric_name: Metric name to analyze
            days: Number of days to analyze
            
        Returns:
            Dictionary containing trend analysis
        """
        try:
            with self._get_session() as session:
                cutoff_time = datetime.now(timezone.utc) - timedelta(days=days)
                
                # Get daily aggregations
                daily_stats = session.query(
                    func.date(ProcessingStatistics.recorded_at).label('date'),
                    func.avg(ProcessingStatistics.metric_value).label('avg_value'),
                    func.min(ProcessingStatistics.metric_value).label('min_value'),
                    func.max(ProcessingStatistics.metric_value).label('max_value'),
                    func.count(ProcessingStatistics.id).label('count')
                ).filter(
                    and_(
                        ProcessingStatistics.metric_name == metric_name,
                        ProcessingStatistics.recorded_at >= cutoff_time
                    )
                ).group_by(
                    func.date(ProcessingStatistics.recorded_at)
                ).order_by('date').all()
                
                # Format results
                trends = []
                for row in daily_stats:
                    trends.append({
                        'date': row.date.isoformat(),
                        'avg_value': float(row.avg_value) if row.avg_value else 0,
                        'min_value': float(row.min_value) if row.min_value else 0,
                        'max_value': float(row.max_value) if row.max_value else 0,
                        'count': row.count
                    })
                
                # Calculate overall trends
                if len(trends) >= 2:
                    first_avg = trends[0]['avg_value']
                    last_avg = trends[-1]['avg_value']
                    trend_direction = 'improving' if last_avg > first_avg else 'declining' if last_avg < first_avg else 'stable'
                    trend_percentage = ((last_avg - first_avg) / first_avg * 100) if first_avg > 0 else 0
                else:
                    trend_direction = 'insufficient_data'
                    trend_percentage = 0
                
                return {
                    'metric_name': metric_name,
                    'time_period_days': days,
                    'daily_trends': trends,
                    'trend_direction': trend_direction,
                    'trend_percentage': trend_percentage,
                    'total_data_points': len(trends)
                }
        except Exception as e:
            self._handle_db_error("get performance trends", e)
    
    def cleanup_old_statistics(self, days: int = 90) -> int:
        """
        Clean up old statistics entries.
        
        Args:
            days: Delete entries older than this many days
            
        Returns:
            Number of entries deleted
        """
        try:
            with self._get_session() as session:
                cutoff_time = datetime.now(timezone.utc) - timedelta(days=days)
                
                # Get count before deletion
                count = session.query(ProcessingStatistics).filter(
                    ProcessingStatistics.recorded_at < cutoff_time
                ).count()
                
                # Delete old entries
                session.query(ProcessingStatistics).filter(
                    ProcessingStatistics.recorded_at < cutoff_time
                ).delete(synchronize_session=False)
                
                return count
        except Exception as e:
            self._handle_db_error("cleanup old statistics", e)


class RuntimeStatisticsRepository(BaseRepository):
    """
    Repository for RuntimeStatistics model operations.
    
    Provides runtime statistics and performance metrics for agent runs
    with calculation and aggregation capabilities.
    """
    
    def __init__(self):
        super().__init__(RuntimeStatistics)
    
    # ===== BASIC CRUD OPERATIONS =====
    
    def create(self, stats_data: Dict[str, Any]) -> RuntimeStatistics:
        """
        Create a new runtime statistics entry.
        
        Args:
            stats_data: Dictionary containing runtime statistics data
            
        Returns:
            Created RuntimeStatistics instance
            
        Raises:
            IntegrityError: If run_id already exists
        """
        try:
            with self._get_session() as session:
                stats = RuntimeStatistics(**stats_data)
                session.add(stats)
                session.flush()
                session.refresh(stats)
                session.expunge(stats)
                return stats
        except IntegrityError as e:
            self._handle_db_error("create runtime statistics", e)
        except Exception as e:
            self._handle_db_error("create runtime statistics", e)
    
    def get_by_run_id(self, run_id: str) -> Optional[RuntimeStatistics]:
        """
        Get runtime statistics by run_id.
        
        Args:
            run_id: Run ID to search for
            
        Returns:
            RuntimeStatistics instance or None if not found
        """
        try:
            with self._get_session() as session:
                stats = session.query(RuntimeStatistics).filter_by(run_id=run_id).first()
                if stats:
                    session.expunge(stats)
                return stats
        except Exception as e:
            self._handle_db_error("get runtime stats by run id", e)
    
    def update(self, run_id: str, updates: Dict[str, Any]) -> Optional[RuntimeStatistics]:
        """
        Update runtime statistics.
        
        Args:
            run_id: Run ID to update
            updates: Dictionary of fields to update
            
        Returns:
            Updated RuntimeStatistics instance or None if not found
        """
        try:
            with self._get_session() as session:
                stats = session.query(RuntimeStatistics).filter_by(run_id=run_id).first()
                if stats:
                    for key, value in updates.items():
                        if hasattr(stats, key):
                            setattr(stats, key, value)
                    
                    # Recalculate derived metrics
                    self._calculate_derived_metrics(stats)
                    
                    session.flush()
                    session.refresh(stats)
                    session.expunge(stats)
                return stats
        except Exception as e:
            self._handle_db_error("update runtime statistics", e)
    
    def _calculate_derived_metrics(self, stats: RuntimeStatistics):
        """Calculate derived metrics for runtime statistics."""
        total_processed = stats.processed_count or 0
        
        # Success rate
        if total_processed > 0:
            stats.success_rate = (stats.success_count or 0) / total_processed * 100
        else:
            stats.success_rate = 0
        
        # Error rate
        if total_processed > 0:
            stats.error_rate = (stats.error_count or 0) / total_processed * 100
        else:
            stats.error_rate = 0
        
        # Cache hit rate
        total_cache_operations = (stats.cache_hits or 0) + (stats.cache_misses or 0)
        if total_cache_operations > 0:
            stats.cache_hit_rate = (stats.cache_hits or 0) / total_cache_operations * 100
        else:
            stats.cache_hit_rate = 0
        
        # Average retries
        if total_processed > 0:
            stats.average_retries = (stats.retry_count or 0) / total_processed
        else:
            stats.average_retries = 0
    
    # ===== AGGREGATION AND REPORTING =====
    
    def get_recent_runs(self, limit: int = 20) -> List[RuntimeStatistics]:
        """
        Get most recent runtime statistics.
        
        Args:
            limit: Maximum number of entries to return
            
        Returns:
            List of recent RuntimeStatistics instances
        """
        try:
            with self._get_session() as session:
                stats = session.query(RuntimeStatistics).order_by(
                    RuntimeStatistics.created_at.desc()
                ).limit(limit).all()
                
                # Detach from session
                for stat in stats:
                    session.expunge(stat)
                
                return stats
        except Exception as e:
            self._handle_db_error("get recent runs", e)
    
    def get_performance_summary(self, days: int = 7) -> Dict[str, Any]:
        """
        Get performance summary for the specified time period.
        
        Args:
            days: Number of days to analyze
            
        Returns:
            Dictionary containing performance summary
        """
        try:
            with self._get_session() as session:
                cutoff_time = datetime.now(timezone.utc) - timedelta(days=days)
                
                # Get aggregated statistics
                summary = session.query(
                    func.count(RuntimeStatistics.id).label('total_runs'),
                    func.sum(RuntimeStatistics.processed_count).label('total_processed'),
                    func.sum(RuntimeStatistics.success_count).label('total_success'),
                    func.sum(RuntimeStatistics.error_count).label('total_errors'),
                    func.avg(RuntimeStatistics.success_rate).label('avg_success_rate'),
                    func.avg(RuntimeStatistics.error_rate).label('avg_error_rate'),
                    func.avg(RuntimeStatistics.cache_hit_rate).label('avg_cache_hit_rate'),
                    func.sum(RuntimeStatistics.media_processed).label('total_media_processed')
                ).filter(
                    RuntimeStatistics.created_at >= cutoff_time
                ).first()
                
                # Calculate average run duration
                avg_duration = session.query(
                    func.avg(
                        func.extract('epoch', RuntimeStatistics.duration)
                    ).label('avg_duration_seconds')
                ).filter(
                    and_(
                        RuntimeStatistics.created_at >= cutoff_time,
                        RuntimeStatistics.duration.isnot(None)
                    )
                ).scalar()
                
                return {
                    'time_period_days': days,
                    'total_runs': summary.total_runs or 0,
                    'total_processed': summary.total_processed or 0,
                    'total_success': summary.total_success or 0,
                    'total_errors': summary.total_errors or 0,
                    'avg_success_rate': float(summary.avg_success_rate or 0),
                    'avg_error_rate': float(summary.avg_error_rate or 0),
                    'avg_cache_hit_rate': float(summary.avg_cache_hit_rate or 0),
                    'total_media_processed': summary.total_media_processed or 0,
                    'avg_duration_seconds': float(avg_duration or 0),
                    'throughput_per_day': (summary.total_processed or 0) / days if days > 0 else 0
                }
        except Exception as e:
            self._handle_db_error("get performance summary", e)
    
    def cleanup_old_runs(self, days: int = 30) -> int:
        """
        Clean up old runtime statistics.
        
        Args:
            days: Delete entries older than this many days
            
        Returns:
            Number of entries deleted
        """
        try:
            with self._get_session() as session:
                cutoff_time = datetime.now(timezone.utc) - timedelta(days=days)
                
                # Get count before deletion
                count = session.query(RuntimeStatistics).filter(
                    RuntimeStatistics.created_at < cutoff_time
                ).count()
                
                # Delete old entries
                session.query(RuntimeStatistics).filter(
                    RuntimeStatistics.created_at < cutoff_time
                ).delete(synchronize_session=False)
                
                return count
        except Exception as e:
            self._handle_db_error("cleanup old runs", e)