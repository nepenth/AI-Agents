"""
Unit tests for TweetCache Repository

Tests the TweetCacheRepository class functionality including CRUD operations,
bulk operations, search capabilities, and reprocessing flag management.
"""

import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import Mock, patch, MagicMock
from sqlalchemy.exc import IntegrityError

from knowledge_base_agent.repositories import TweetCacheRepository
from knowledge_base_agent.models import TweetCache


class TestTweetCacheRepository:
    """Test suite for TweetCacheRepository."""
    
    @pytest.fixture
    def repository(self):
        """Create a TweetCacheRepository instance for testing."""
        return TweetCacheRepository()
    
    @pytest.fixture
    def sample_tweet_data(self):
        """Sample tweet data for testing."""
        return {
            'tweet_id': 'test_tweet_123',
            'bookmarked_tweet_id': 'bookmark_123',
            'is_thread': False,
            'source': 'twitter',
            'display_title': 'Test Tweet',
            'full_text': 'This is a test tweet content',
            'main_category': 'Technology',
            'sub_category': 'AI',
            'cache_complete': True,
            'media_processed': False
        }
    
    @pytest.fixture
    def mock_session(self):
        """Mock database session."""
        session = MagicMock()
        return session
    
    # ===== BASIC CRUD OPERATIONS TESTS =====
    
    @patch('knowledge_base_agent.repositories.get_db_session_context')
    def test_create_tweet_success(self, mock_get_session, repository, sample_tweet_data):
        """Test successful tweet creation."""
        mock_session = MagicMock()
        mock_get_session.return_value.__enter__.return_value = mock_session
        
        # Mock TweetCache creation
        mock_tweet = Mock(spec=TweetCache)
        mock_tweet.tweet_id = sample_tweet_data['tweet_id']
        
        with patch('knowledge_base_agent.repositories.TweetCache') as mock_tweet_class:
            mock_tweet_class.return_value = mock_tweet
            
            result = repository.create(sample_tweet_data)
            
            # Verify tweet was created with correct data
            mock_tweet_class.assert_called_once_with(**sample_tweet_data)
            mock_session.add.assert_called_once_with(mock_tweet)
            mock_session.flush.assert_called_once()
            mock_session.refresh.assert_called_once_with(mock_tweet)
            
            assert result == mock_tweet
    
    @patch('knowledge_base_agent.repositories.get_db_session_context')
    def test_create_tweet_integrity_error(self, mock_get_session, repository, sample_tweet_data):
        """Test tweet creation with duplicate tweet_id."""
        mock_session = MagicMock()
        mock_get_session.return_value.__enter__.return_value = mock_session
        mock_session.add.side_effect = IntegrityError("duplicate key", None, None)
        
        with patch('knowledge_base_agent.repositories.TweetCache'):
            with pytest.raises(Exception):  # Should re-raise the error
                repository.create(sample_tweet_data)
    
    @patch('knowledge_base_agent.repositories.get_db_session_context')
    def test_get_by_id_found(self, mock_get_session, repository):
        """Test getting tweet by ID when it exists."""
        mock_session = MagicMock()
        mock_get_session.return_value.__enter__.return_value = mock_session
        
        mock_tweet = Mock(spec=TweetCache)
        mock_tweet.tweet_id = 'test_tweet_123'
        mock_session.query.return_value.filter_by.return_value.first.return_value = mock_tweet
        
        result = repository.get_by_id('test_tweet_123')
        
        mock_session.query.assert_called_once_with(TweetCache)
        mock_session.query.return_value.filter_by.assert_called_once_with(tweet_id='test_tweet_123')
        assert result == mock_tweet
    
    @patch('knowledge_base_agent.repositories.get_db_session_context')
    def test_get_by_id_not_found(self, mock_get_session, repository):
        """Test getting tweet by ID when it doesn't exist."""
        mock_session = MagicMock()
        mock_get_session.return_value.__enter__.return_value = mock_session
        mock_session.query.return_value.filter_by.return_value.first.return_value = None
        
        result = repository.get_by_id('nonexistent_tweet')
        
        assert result is None
    
    @patch('knowledge_base_agent.repositories.get_db_session_context')
    def test_update_tweet_success(self, mock_get_session, repository):
        """Test successful tweet update."""
        mock_session = MagicMock()
        mock_get_session.return_value.__enter__.return_value = mock_session
        
        mock_tweet = Mock(spec=TweetCache)
        mock_tweet.tweet_id = 'test_tweet_123'
        mock_session.query.return_value.filter_by.return_value.first.return_value = mock_tweet
        
        update_data = {'cache_complete': True, 'media_processed': True}
        
        result = repository.update('test_tweet_123', update_data)
        
        # Verify attributes were updated
        assert mock_tweet.cache_complete == True
        assert mock_tweet.media_processed == True
        assert hasattr(mock_tweet, 'updated_at')
        
        mock_session.flush.assert_called_once()
        mock_session.refresh.assert_called_once_with(mock_tweet)
        assert result == mock_tweet
    
    @patch('knowledge_base_agent.repositories.get_db_session_context')
    def test_update_tweet_not_found(self, mock_get_session, repository):
        """Test updating non-existent tweet."""
        mock_session = MagicMock()
        mock_get_session.return_value.__enter__.return_value = mock_session
        mock_session.query.return_value.filter_by.return_value.first.return_value = None
        
        result = repository.update('nonexistent_tweet', {'cache_complete': True})
        
        assert result is None
    
    @patch('knowledge_base_agent.repositories.get_db_session_context')
    def test_delete_tweet_success(self, mock_get_session, repository):
        """Test successful tweet deletion."""
        mock_session = MagicMock()
        mock_get_session.return_value.__enter__.return_value = mock_session
        
        mock_tweet = Mock(spec=TweetCache)
        mock_session.query.return_value.filter_by.return_value.first.return_value = mock_tweet
        
        result = repository.delete('test_tweet_123')
        
        mock_session.delete.assert_called_once_with(mock_tweet)
        assert result == True
    
    @patch('knowledge_base_agent.repositories.get_db_session_context')
    def test_delete_tweet_not_found(self, mock_get_session, repository):
        """Test deleting non-existent tweet."""
        mock_session = MagicMock()
        mock_get_session.return_value.__enter__.return_value = mock_session
        mock_session.query.return_value.filter_by.return_value.first.return_value = None
        
        result = repository.delete('nonexistent_tweet')
        
        assert result == False
    
    # ===== BULK OPERATIONS TESTS =====
    
    @patch('knowledge_base_agent.repositories.get_db_session_context')
    def test_bulk_create_success(self, mock_get_session, repository):
        """Test successful bulk tweet creation."""
        mock_session = MagicMock()
        mock_get_session.return_value.__enter__.return_value = mock_session
        
        tweets_data = [
            {'tweet_id': 'tweet_1', 'bookmarked_tweet_id': 'bookmark_1'},
            {'tweet_id': 'tweet_2', 'bookmarked_tweet_id': 'bookmark_2'}
        ]
        
        mock_tweets = [Mock(spec=TweetCache), Mock(spec=TweetCache)]
        
        with patch('knowledge_base_agent.repositories.TweetCache', side_effect=mock_tweets):
            result = repository.bulk_create(tweets_data)
            
            mock_session.add_all.assert_called_once()
            mock_session.flush.assert_called_once()
            assert len(result) == 2
    
    @patch('knowledge_base_agent.repositories.get_db_session_context')
    def test_bulk_set_reprocessing_flags(self, mock_get_session, repository):
        """Test bulk setting of reprocessing flags."""
        mock_session = MagicMock()
        mock_get_session.return_value.__enter__.return_value = mock_session
        
        mock_query = mock_session.query.return_value
        mock_query.filter.return_value.update.return_value = 3  # 3 tweets updated
        
        tweet_ids = ['tweet_1', 'tweet_2', 'tweet_3']
        result = repository.bulk_set_reprocessing_flags(
            tweet_ids, 'force_reprocess_pipeline', 'test_user'
        )
        
        assert result == 3
        mock_session.query.assert_called_once_with(TweetCache)
    
    def test_bulk_set_reprocessing_flags_invalid_type(self, repository):
        """Test bulk setting with invalid flag type."""
        with pytest.raises(ValueError):
            repository.bulk_set_reprocessing_flags(['tweet_1'], 'invalid_flag')
    
    # ===== SEARCH AND FILTERING TESTS =====
    
    @patch('knowledge_base_agent.repositories.get_db_session_context')
    def test_get_by_processing_status(self, mock_get_session, repository):
        """Test filtering by processing status."""
        mock_session = MagicMock()
        mock_get_session.return_value.__enter__.return_value = mock_session
        
        mock_tweets = [Mock(spec=TweetCache), Mock(spec=TweetCache)]
        mock_query = mock_session.query.return_value
        mock_query.filter.return_value.offset.return_value.limit.return_value.all.return_value = mock_tweets
        
        status_filters = {'cache_complete': True, 'media_processed': False}
        result = repository.get_by_processing_status(status_filters, limit=50, offset=10)
        
        assert result == mock_tweets
        mock_query.offset.assert_called_once_with(10)
        mock_query.offset.return_value.limit.assert_called_once_with(50)
    
    @patch('knowledge_base_agent.repositories.get_db_session_context')
    def test_get_by_category(self, mock_get_session, repository):
        """Test filtering by category."""
        mock_session = MagicMock()
        mock_get_session.return_value.__enter__.return_value = mock_session
        
        mock_tweets = [Mock(spec=TweetCache)]
        mock_query = mock_session.query.return_value
        mock_query.filter.return_value.filter.return_value.offset.return_value.limit.return_value.all.return_value = mock_tweets
        
        result = repository.get_by_category('Technology', 'AI', limit=25)
        
        assert result == mock_tweets
    
    @patch('knowledge_base_agent.repositories.get_db_session_context')
    def test_full_text_search_postgresql(self, mock_get_session, repository):
        """Test full-text search with PostgreSQL."""
        mock_session = MagicMock()
        mock_session.bind.dialect.name = 'postgresql'
        mock_get_session.return_value.__enter__.return_value = mock_session
        
        mock_tweets = [Mock(spec=TweetCache)]
        mock_query = mock_session.query.return_value
        mock_query.filter.return_value.offset.return_value.limit.return_value.all.return_value = mock_tweets
        
        result = repository.full_text_search('test search', limit=20)
        
        assert result == mock_tweets
    
    @patch('knowledge_base_agent.repositories.get_db_session_context')
    def test_full_text_search_sqlite(self, mock_get_session, repository):
        """Test full-text search with SQLite."""
        mock_session = MagicMock()
        mock_session.bind.dialect.name = 'sqlite'
        mock_get_session.return_value.__enter__.return_value = mock_session
        
        mock_tweets = [Mock(spec=TweetCache)]
        mock_query = mock_session.query.return_value
        mock_query.filter.return_value.offset.return_value.limit.return_value.all.return_value = mock_tweets
        
        result = repository.full_text_search('test search', limit=20)
        
        assert result == mock_tweets
    
    # ===== REPROCESSING FLAG MANAGEMENT TESTS =====
    
    @patch('knowledge_base_agent.repositories.get_db_session_context')
    def test_set_reprocessing_flag_success(self, mock_get_session, repository):
        """Test setting reprocessing flag."""
        mock_session = MagicMock()
        mock_get_session.return_value.__enter__.return_value = mock_session
        
        mock_tweet = Mock(spec=TweetCache)
        mock_session.query.return_value.filter_by.return_value.first.return_value = mock_tweet
        
        result = repository.set_reprocessing_flag(
            'test_tweet_123', 'force_reprocess_pipeline', 'test_user'
        )
        
        assert result == True
        assert mock_tweet.force_reprocess_pipeline == True
        assert mock_tweet.reprocess_requested_by == 'test_user'
        assert hasattr(mock_tweet, 'reprocess_requested_at')
        assert hasattr(mock_tweet, 'updated_at')
    
    def test_set_reprocessing_flag_invalid_type(self, repository):
        """Test setting reprocessing flag with invalid type."""
        with pytest.raises(ValueError):
            repository.set_reprocessing_flag('tweet_1', 'invalid_flag')
    
    @patch('knowledge_base_agent.repositories.get_db_session_context')
    def test_clear_reprocessing_flags(self, mock_get_session, repository):
        """Test clearing reprocessing flags."""
        mock_session = MagicMock()
        mock_get_session.return_value.__enter__.return_value = mock_session
        
        mock_tweet = Mock(spec=TweetCache)
        mock_session.query.return_value.filter_by.return_value.first.return_value = mock_tweet
        
        result = repository.clear_reprocessing_flags('test_tweet_123')
        
        assert result == True
        assert mock_tweet.force_reprocess_pipeline == False
        assert mock_tweet.force_recache == False
        assert mock_tweet.reprocess_requested_at is None
        assert mock_tweet.reprocess_requested_by is None
    
    @patch('knowledge_base_agent.repositories.get_db_session_context')
    def test_get_tweets_needing_reprocessing(self, mock_get_session, repository):
        """Test getting tweets that need reprocessing."""
        mock_session = MagicMock()
        mock_get_session.return_value.__enter__.return_value = mock_session
        
        mock_tweets = [Mock(spec=TweetCache), Mock(spec=TweetCache)]
        mock_query = mock_session.query.return_value
        mock_query.filter.return_value.all.return_value = mock_tweets
        
        result = repository.get_tweets_needing_reprocessing('force_reprocess_pipeline')
        
        assert result == mock_tweets
    
    # ===== STATISTICS TESTS =====
    
    @patch('knowledge_base_agent.repositories.get_db_session_context')
    def test_get_processing_statistics(self, mock_get_session, repository):
        """Test getting processing statistics."""
        mock_session = MagicMock()
        mock_get_session.return_value.__enter__.return_value = mock_session
        
        # Mock count queries
        mock_session.query.return_value.count.return_value = 100  # total tweets
        mock_session.query.return_value.filter_by.return_value.count.return_value = 80  # various counts
        mock_session.query.return_value.filter.return_value.count.return_value = 75  # fully processed
        
        # Mock category stats
        mock_session.query.return_value.filter.return_value.group_by.return_value.all.return_value = [
            ('Technology', 50), ('Science', 30)
        ]
        
        result = repository.get_processing_statistics()
        
        assert 'total_tweets' in result
        assert 'processing_completion' in result
        assert 'reprocessing' in result
        assert 'categories' in result
        assert result['processing_completion']['completion_rate'] == 75.0
    
    # ===== ERROR HANDLING TESTS =====
    
    @patch('knowledge_base_agent.repositories.get_db_session_context')
    def test_database_error_handling(self, mock_get_session, repository):
        """Test database error handling."""
        mock_session = MagicMock()
        mock_get_session.return_value.__enter__.return_value = mock_session
        mock_session.query.side_effect = Exception("Database connection failed")
        
        with pytest.raises(Exception):
            repository.get_by_id('test_tweet_123')


if __name__ == '__main__':
    pytest.main([__file__])