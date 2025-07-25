#!/usr/bin/env python3
"""
Tests for StateManager Event Integration

Tests the integration between StateManager validation phases
and the Enhanced Unified Logger for comprehensive event emission.
"""

import pytest
import asyncio
import tempfile
import json
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

import sys
sys.path.append('.')

from knowledge_base_agent.config import Config
from knowledge_base_agent.database_state_manager import DatabaseStateManager
from knowledge_base_agent.state_manager_event_integration import StateManagerEventIntegration, create_state_manager_with_events


class TestStateManagerEventIntegration:
    """Test StateManager event integration functionality."""
    
    @pytest.fixture
    def temp_config(self):
        """Create a temporary configuration for testing."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Create mock config
            config = Mock(spec=Config)
            config.project_root = temp_path
            config.tweet_cache_file = temp_path / "tweet_cache.json"
            config.unprocessed_tweets_file = temp_path / "unprocessed_tweets.json"
            config.processed_tweets_file = temp_path / "processed_tweets.json"
            config.bookmarks_file = temp_path / "bookmarks.json"
            config.resolve_path_from_project_root = lambda x: temp_path / x
            
            yield config
    
    @pytest.fixture
    def mock_logger(self):
        """Create a mock enhanced unified logger."""
        logger = Mock()
        logger.emit_phase_start = Mock()
        logger.emit_phase_complete = Mock()
        logger.emit_phase_error = Mock()
        logger.emit_progress_update = Mock()
        logger.log_structured = Mock()
        logger.emit_status_update = Mock()
        logger.log_error = Mock()
        return logger
    
    @pytest.fixture
    def state_manager(self, temp_config):
        """Create a DatabaseStateManager instance for testing."""
        return DatabaseStateManager(temp_config, task_id="test-task-123")
    
    @pytest.fixture
    def event_integration(self, state_manager, mock_logger):
        """Create a StateManagerEventIntegration instance for testing."""
        with patch('knowledge_base_agent.state_manager_event_integration.get_unified_logger', return_value=mock_logger):
            integration = StateManagerEventIntegration(state_manager, "test-task-123", state_manager.config)
            return integration
    
    def test_initialization(self, event_integration, mock_logger):
        """Test StateManagerEventIntegration initialization."""
        assert event_integration.task_id == "test-task-123"
        assert event_integration.logger == mock_logger
        assert len(event_integration.validation_phases) == 6
        
        # Check validation phases are properly defined
        phase_ids = [phase["id"] for phase in event_integration.validation_phases]
        expected_phases = [
            "initial_state_validation",
            "cache_phase_validation", 
            "media_phase_validation",
            "category_phase_validation",
            "kb_item_phase_validation",
            "final_processing_validation"
        ]
        assert phase_ids == expected_phases
    
    def test_get_validation_phase_info(self, event_integration):
        """Test getting validation phase information."""
        phase_info = event_integration.get_validation_phase_info()
        
        assert len(phase_info) == 6
        assert all("id" in phase for phase in phase_info)
        assert all("name" in phase for phase in phase_info)
        assert all("description" in phase for phase in phase_info)
        assert all("estimated_duration" in phase for phase in phase_info)
    
    def test_get_tweet_counts(self, event_integration):
        """Test getting tweet counts from state manager."""
        # Add some test data to state manager
        event_integration.state_manager._tweet_cache = {
            "tweet1": {"tweet_id": "tweet1"},
            "tweet2": {"tweet_id": "tweet2"}
        }
        event_integration.state_manager._unprocessed_tweets = ["tweet1", "tweet2"]
        event_integration.state_manager._processed_tweets = {}
        
        counts = event_integration.get_tweet_counts()
        
        # Note: get_tweet_counts looks at state_manager.state, not the private attributes
        # So we need to set up the state properly
        event_integration.state_manager.state = {
            "unprocessed_tweets": {"tweet1", "tweet2"},
            "processed_tweets": set(),
            "cached_tweets": {"tweet1", "tweet2"},
            "tweet_data": {}
        }
        
        counts = event_integration.get_tweet_counts()
        assert "unprocessed_tweets" in counts
        assert "processed_tweets" in counts
        assert "cached_tweets" in counts
    
    @patch('knowledge_base_agent.state_manager_event_integration.time.time')
    def test_run_validation_with_events_success(self, mock_time, event_integration, mock_logger):
        """Test successful validation with event emission."""
        # Mock time for duration calculation
        mock_time.side_effect = [1000.0, 1001.0, 1002.0, 1003.0, 1004.0, 1005.0, 1006.0, 1007.0, 1008.0, 1009.0, 1010.0, 1011.0, 1012.0]
        
        # Mock the validation methods to return test data
        event_integration.state_manager._run_initial_state_validation = Mock(return_value=2)
        event_integration.state_manager._run_cache_phase_validation = Mock(return_value=1)
        event_integration.state_manager._run_media_phase_validation = Mock(return_value=0)
        event_integration.state_manager._run_category_phase_validation = Mock(return_value=3)
        event_integration.state_manager._run_kb_item_phase_validation = Mock(return_value=1)
        event_integration.state_manager._run_final_processing_validation = Mock(return_value=({"tweet1"}, {"tweet2"}))
        event_integration.state_manager._save_state = Mock()
        
        # Run validation with events
        stats = event_integration.run_validation_with_events()
        
        # Verify event emissions
        assert mock_logger.emit_phase_start.call_count == 7  # 6 phases + overall
        assert mock_logger.emit_phase_complete.call_count == 7  # 6 phases + overall
        assert mock_logger.emit_progress_update.call_count == 6  # One per phase
        
        # Verify validation stats
        assert stats["initial_state_fixes"] == 2
        assert stats["cache_phase_fixes"] == 1
        assert stats["media_phase_fixes"] == 0
        assert stats["category_phase_fixes"] == 3
        assert stats["kb_item_phase_fixes"] == 1
        assert stats["tweets_moved_to_processed"] == 1
        assert stats["tweets_moved_to_unprocessed"] == 1
    
    def test_run_validation_with_events_error(self, event_integration, mock_logger):
        """Test validation with error handling."""
        # Mock a validation method to raise an exception
        error = Exception("Test validation error")
        event_integration.state_manager._run_initial_state_validation = Mock(side_effect=error)
        
        # Run validation and expect exception to be re-raised
        with pytest.raises(Exception, match="Test validation error"):
            event_integration.run_validation_with_events()
        
        # Verify error event was emitted
        mock_logger.emit_phase_error.assert_called_once()
        call_args = mock_logger.emit_phase_error.call_args
        assert call_args[0][0] == "initial_state_validation"  # phase_id
        assert call_args[0][1] == error  # exception
        assert call_args[0][2] == "state_manager"  # component
    
    @patch('os.makedirs')
    @patch('os.path.exists')
    @patch('builtins.open')
    def test_initialize_with_events(self, mock_open, mock_exists, mock_makedirs, event_integration, mock_logger):
        """Test initialization with events."""
        # Mock file operations
        mock_exists.return_value = False
        mock_open.return_value.__enter__.return_value.read.return_value = "{}"
        
        # Mock validation methods
        event_integration.run_validation_with_events = Mock(return_value={"test": "stats"})
        
        # Run initialization with events
        stats = event_integration.initialize_with_events()
        
        # Verify directories were created
        assert mock_makedirs.call_count >= 2
        
        # Verify validation was run
        event_integration.run_validation_with_events.assert_called_once()
        assert stats == {"test": "stats"}
    
    def test_emit_validation_summary(self, event_integration, mock_logger):
        """Test validation summary emission."""
        # Set up test data
        validation_stats = {
            "initial_state_fixes": 2,
            "cache_phase_fixes": 1,
            "media_phase_fixes": 0,
            "category_phase_fixes": 3,
            "kb_item_phase_fixes": 1,
            "tweets_moved_to_processed": 5,
            "tweets_moved_to_unprocessed": 2
        }
        
        # Mock get_tweet_counts
        event_integration.get_tweet_counts = Mock(return_value={
            "unprocessed_tweets": 10,
            "processed_tweets": 5,
            "cached_tweets": 15
        })
        
        # Emit validation summary
        event_integration.emit_validation_summary(validation_stats)
        
        # Verify structured log was emitted
        mock_logger.log_structured.assert_called_once()
        call_args = mock_logger.log_structured.call_args
        assert "7 total fixes applied" in call_args[0][0]  # message
        assert call_args[0][1] == "INFO"  # level
        assert call_args[0][2] == "state_manager"  # component
        
        # Verify status update was emitted
        mock_logger.emit_status_update.assert_called_once()
        status_call_args = mock_logger.emit_status_update.call_args
        assert status_call_args[0][0] == "completed"  # status
        assert status_call_args[0][1] == "state_validation"  # phase
        assert "7 fixes" in status_call_args[0][2]  # message
    
    def test_create_state_manager_with_events(self, temp_config):
        """Test factory function for creating StateManager with events."""
        with patch('knowledge_base_agent.state_manager_event_integration.get_unified_logger'):
            integration = create_state_manager_with_events(temp_config, "test-task-456")
            
            assert isinstance(integration, StateManagerEventIntegration)
            assert integration.task_id == "test-task-456"
            assert integration.config == temp_config


class TestStateManagerIntegration:
    """Test integration with actual StateManager methods."""
    
    @pytest.fixture
    def temp_config(self):
        """Create a temporary configuration for testing."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Create mock config
            config = Mock(spec=Config)
            config.project_root = temp_path
            config.tweet_cache_file = temp_path / "tweet_cache.json"
            config.unprocessed_tweets_file = temp_path / "unprocessed_tweets.json"
            config.processed_tweets_file = temp_path / "processed_tweets.json"
            config.bookmarks_file = temp_path / "bookmarks.json"
            config.resolve_path_from_project_root = lambda x: temp_path / x
            
            yield config
    
    def test_state_manager_initialize_with_events_method(self, temp_config):
        """Test DatabaseStateManager.initialize_with_events method."""
        state_manager = DatabaseStateManager(temp_config, task_id="test-task-789")
        
        with patch('knowledge_base_agent.state_manager_event_integration.get_unified_logger') as mock_get_logger:
            mock_logger = Mock()
            mock_get_logger.return_value = mock_logger
            
            with patch.object(StateManagerEventIntegration, 'initialize_with_events') as mock_init:
                mock_init.return_value = {"test": "result"}
                
                result = state_manager.initialize_with_events("test-task-789")
                
                # Verify the method was called
                mock_init.assert_called_once()
                assert result == {"test": "result"}


if __name__ == "__main__":
    pytest.main([__file__, "-v"])