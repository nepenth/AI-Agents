#!/usr/bin/env python3
"""
Tests for Enhanced RealtimeManager

Tests the comprehensive real-time communication system with
event validation, routing, batching, rate limiting, and connection health monitoring.
"""

import pytest
import json
import time
import threading
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta
from collections import deque

import sys
sys.path.append('.')

from knowledge_base_agent.enhanced_realtime_manager import (
    EventValidator, EventRouter, RateLimiter, ConnectionHealthMonitor,
    EnhancedRealtimeManager, EventBatch, RateLimitConfig
)


class TestEventValidator:
    """Test EventValidator functionality."""
    
    def test_validate_log_message_valid(self):
        """Test validation of valid log message."""
        data = {
            'message': 'Test log message',
            'level': 'INFO'
        }
        
        is_valid, error, sanitized = EventValidator.validate_event('log_message', data)
        
        assert is_valid
        assert error is None
        assert sanitized['message'] == 'Test log message'
        assert sanitized['level'] == 'INFO'
        assert 'timestamp' in sanitized
    
    def test_validate_log_message_invalid_level(self):
        """Test validation of log message with invalid level."""
        data = {
            'message': 'Test message',
            'level': 'INVALID_LEVEL'
        }
        
        is_valid, error, sanitized = EventValidator.validate_event('log_message', data)
        
        assert is_valid  # Should still be valid, but level corrected
        assert sanitized['level'] == 'INFO'  # Default level
    
    def test_validate_log_message_truncation(self):
        """Test log message truncation for very long messages."""
        long_message = 'x' * 15000
        data = {
            'message': long_message,
            'level': 'INFO'
        }
        
        is_valid, error, sanitized = EventValidator.validate_event('log_message', data)
        
        assert is_valid
        assert len(sanitized['message']) == 10000  # 9997 + '...'
        assert sanitized['message'].endswith('...')
        assert sanitized.get('truncated') is True
    
    def test_validate_phase_update_valid(self):
        """Test validation of valid phase update."""
        data = {
            'phase_id': 'test_phase',
            'status': 'in_progress',
            'message': 'Processing...',
            'processed_count': 5,
            'total_count': 10
        }
        
        is_valid, error, sanitized = EventValidator.validate_event('phase_update', data)
        
        assert is_valid
        assert error is None
        assert sanitized['phase_id'] == 'test_phase'
        assert sanitized['status'] == 'in_progress'
        assert sanitized['processed_count'] == 5
        assert sanitized['total_count'] == 10
    
    def test_validate_phase_update_invalid_status(self):
        """Test validation of phase update with invalid status."""
        data = {
            'phase_id': 'test_phase',
            'status': 'invalid_status'
        }
        
        is_valid, error, sanitized = EventValidator.validate_event('phase_update', data)
        
        assert not is_valid
        assert 'Invalid phase status' in error
    
    def test_validate_progress_update_valid(self):
        """Test validation of valid progress update."""
        data = {
            'processed_count': 7,
            'total_count': 10
        }
        
        is_valid, error, sanitized = EventValidator.validate_event('progress_update', data)
        
        assert is_valid
        assert error is None
        assert sanitized['processed_count'] == 7
        assert sanitized['total_count'] == 10
        assert sanitized['percentage'] == 70
    
    def test_validate_progress_update_invalid_counts(self):
        """Test validation of progress update with invalid counts."""
        data = {
            'processed_count': 15,
            'total_count': 10  # processed > total
        }
        
        is_valid, error, sanitized = EventValidator.validate_event('progress_update', data)
        
        assert not is_valid
        assert 'cannot exceed total' in error
    
    def test_validate_missing_required_fields(self):
        """Test validation with missing required fields."""
        data = {
            'message': 'Test message'
            # Missing 'level' field
        }
        
        is_valid, error, sanitized = EventValidator.validate_event('log_message', data)
        
        assert not is_valid
        assert 'Missing required field: level' in error


class TestEventRouter:
    """Test EventRouter functionality."""
    
    def test_get_socketio_events_realtime_channel(self):
        """Test getting SocketIO events for realtime channel."""
        events = EventRouter.get_socketio_events('realtime_events', 'log_message')
        
        assert 'log' in events
        assert 'live_log' in events
    
    def test_get_socketio_events_legacy_channel(self):
        """Test getting SocketIO events for legacy channels."""
        events = EventRouter.get_socketio_events('task_logs', 'log_message')
        
        assert 'log' in events
        assert 'live_log' in events
    
    def test_get_socketio_events_unknown(self):
        """Test getting SocketIO events for unknown channel/type."""
        events = EventRouter.get_socketio_events('unknown_channel', 'unknown_type')
        
        assert events == []


class TestRateLimiter:
    """Test RateLimiter functionality."""
    
    def test_rate_limiter_allows_normal_rate(self):
        """Test that rate limiter allows normal event rates."""
        config = RateLimitConfig(max_events_per_second=10, max_events_per_minute=100)
        limiter = RateLimiter(config)
        
        # Should allow several events
        for _ in range(5):
            assert limiter.is_allowed()
    
    def test_rate_limiter_blocks_high_rate(self):
        """Test that rate limiter blocks high event rates."""
        config = RateLimitConfig(max_events_per_second=2, max_events_per_minute=100)
        limiter = RateLimiter(config)
        
        # First 2 should be allowed
        assert limiter.is_allowed()
        assert limiter.is_allowed()
        
        # Third should be blocked
        assert not limiter.is_allowed()
    
    def test_rate_limiter_resets_after_time(self):
        """Test that rate limiter resets after time passes."""
        config = RateLimitConfig(max_events_per_second=1, max_events_per_minute=100)
        limiter = RateLimiter(config)
        
        # First event allowed
        assert limiter.is_allowed()
        
        # Second event blocked
        assert not limiter.is_allowed()
        
        # Mock time passage
        with patch('knowledge_base_agent.enhanced_realtime_manager.datetime') as mock_datetime:
            future_time = datetime.now() + timedelta(seconds=2)
            mock_datetime.now.return_value = future_time
            
            # Should be allowed after time passes
            assert limiter.is_allowed()


class TestEventBatch:
    """Test EventBatch functionality."""
    
    def test_event_batch_size_limit(self):
        """Test event batch reaches size limit."""
        batch = EventBatch(max_size=3, max_age_seconds=10)
        
        # Add events up to limit
        assert not batch.add_event({'test': 1})
        assert not batch.add_event({'test': 2})
        assert batch.add_event({'test': 3})  # Should trigger ready state
        
        assert batch.is_ready_to_send()
        assert len(batch.events) == 3
    
    def test_event_batch_age_limit(self):
        """Test event batch reaches age limit."""
        batch = EventBatch(max_size=10, max_age_seconds=1)
        
        # Add one event
        batch.add_event({'test': 1})
        
        # Should not be ready immediately
        assert not batch.is_ready_to_send()
        
        # Mock time passage
        with patch('knowledge_base_agent.enhanced_realtime_manager.datetime') as mock_datetime:
            future_time = datetime.now() + timedelta(seconds=2)
            mock_datetime.now.return_value = future_time
            
            # Should be ready after age limit
            assert batch.is_ready_to_send()
    
    def test_event_batch_clear(self):
        """Test event batch clearing."""
        batch = EventBatch()
        batch.add_event({'test': 1})
        batch.add_event({'test': 2})
        
        assert len(batch.events) == 2
        
        batch.clear()
        
        assert len(batch.events) == 0


class TestConnectionHealthMonitor:
    """Test ConnectionHealthMonitor functionality."""
    
    def test_health_monitor_healthy_connection(self):
        """Test health monitor with healthy connection."""
        mock_redis = Mock()
        mock_redis.ping.return_value = True
        
        monitor = ConnectionHealthMonitor(mock_redis)
        
        assert monitor.check_health()
        assert monitor.is_healthy
        assert monitor.consecutive_failures == 0
    
    def test_health_monitor_unhealthy_connection(self):
        """Test health monitor with unhealthy connection."""
        mock_redis = Mock()
        mock_redis.ping.side_effect = Exception("Connection failed")
        
        reconnect_callback = Mock()
        monitor = ConnectionHealthMonitor(mock_redis, reconnect_callback)
        monitor.max_consecutive_failures = 2
        
        # First failure
        assert not monitor.check_health()
        assert monitor.consecutive_failures == 1
        assert not reconnect_callback.called
        
        # Second failure should trigger callback
        assert not monitor.check_health()
        assert monitor.consecutive_failures == 2
        assert not monitor.is_healthy
        assert reconnect_callback.called
    
    def test_health_monitor_reset(self):
        """Test health monitor reset after reconnection."""
        mock_redis = Mock()
        monitor = ConnectionHealthMonitor(mock_redis)
        
        # Simulate unhealthy state
        monitor.is_healthy = False
        monitor.consecutive_failures = 5
        
        # Reset health
        monitor.reset_health()
        
        assert monitor.is_healthy
        assert monitor.consecutive_failures == 0


class TestEnhancedRealtimeManager:
    """Test EnhancedRealtimeManager functionality."""
    
    @pytest.fixture
    def mock_socketio(self):
        """Create a mock SocketIO instance."""
        socketio = Mock()
        socketio.emit = Mock()
        return socketio
    
    @pytest.fixture
    def mock_config(self):
        """Create a mock configuration."""
        config = Mock()
        config.redis_progress_url = "redis://localhost:6379/1"
        return config
    
    @pytest.fixture
    def realtime_manager(self, mock_socketio, mock_config):
        """Create an EnhancedRealtimeManager instance for testing."""
        with patch('knowledge_base_agent.enhanced_realtime_manager.redis.Redis'):
            manager = EnhancedRealtimeManager(mock_socketio, mock_config)
            return manager
    
    def test_initialization(self, realtime_manager, mock_socketio):
        """Test EnhancedRealtimeManager initialization."""
        assert realtime_manager.socketio == mock_socketio
        assert isinstance(realtime_manager.validator, EventValidator)
        assert isinstance(realtime_manager.router, EventRouter)
        assert isinstance(realtime_manager.rate_limiter, RateLimiter)
        assert isinstance(realtime_manager.health_monitor, ConnectionHealthMonitor)
    
    def test_handle_redis_message_valid(self, realtime_manager):
        """Test handling valid Redis message."""
        message = {
            'channel': 'realtime_events',
            'data': json.dumps({
                'type': 'log_message',
                'data': {
                    'message': 'Test log',
                    'level': 'INFO'
                }
            })
        }
        
        # Mock rate limiter to allow
        realtime_manager.rate_limiter.is_allowed = Mock(return_value=True)
        realtime_manager._add_to_batch = Mock()
        
        realtime_manager._handle_redis_message(message)
        
        assert realtime_manager.stats['events_processed'] == 1
        assert realtime_manager.stats['events_validated'] == 1
        assert realtime_manager._add_to_batch.called
    
    def test_handle_redis_message_invalid_json(self, realtime_manager):
        """Test handling Redis message with invalid JSON."""
        message = {
            'channel': 'realtime_events',
            'data': 'invalid json'
        }
        
        realtime_manager._handle_redis_message(message)
        
        assert realtime_manager.stats['events_processed'] == 1
        assert realtime_manager.stats['events_rejected'] == 1
    
    def test_handle_redis_message_validation_failure(self, realtime_manager):
        """Test handling Redis message that fails validation."""
        message = {
            'channel': 'realtime_events',
            'data': json.dumps({
                'type': 'log_message',
                'data': {
                    'message': 'Test log'
                    # Missing required 'level' field
                }
            })
        }
        
        realtime_manager._handle_redis_message(message)
        
        assert realtime_manager.stats['events_processed'] == 1
        assert realtime_manager.stats['events_rejected'] == 1
    
    def test_handle_redis_message_rate_limited(self, realtime_manager):
        """Test handling Redis message that gets rate limited."""
        message = {
            'channel': 'realtime_events',
            'data': json.dumps({
                'type': 'log_message',
                'data': {
                    'message': 'Test log',
                    'level': 'INFO'
                }
            })
        }
        
        # Mock rate limiter to block
        realtime_manager.rate_limiter.is_allowed = Mock(return_value=False)
        
        realtime_manager._handle_redis_message(message)
        
        assert realtime_manager.stats['events_processed'] == 1
        assert realtime_manager.stats['events_validated'] == 1
        assert realtime_manager.stats['events_rate_limited'] == 1
    
    def test_event_buffering(self, realtime_manager):
        """Test event buffering during connection issues."""
        # Enable buffering
        realtime_manager.buffer_enabled = True
        
        message = {
            'channel': 'realtime_events',
            'data': json.dumps({
                'type': 'log_message',
                'data': {
                    'message': 'Test log',
                    'level': 'INFO'
                }
            })
        }
        
        # Mock rate limiter to allow
        realtime_manager.rate_limiter.is_allowed = Mock(return_value=True)
        
        realtime_manager._handle_redis_message(message)
        
        assert len(realtime_manager.event_buffer) == 1
        assert realtime_manager.stats['events_buffered'] == 1
    
    def test_get_stats(self, realtime_manager):
        """Test getting statistics."""
        stats = realtime_manager.get_stats()
        
        assert 'events_processed' in stats
        assert 'events_validated' in stats
        assert 'events_rejected' in stats
        assert 'is_healthy' in stats
        assert 'buffer_size' in stats
    
    def test_reset_stats(self, realtime_manager):
        """Test resetting statistics."""
        # Set some stats
        realtime_manager.stats['events_processed'] = 100
        realtime_manager.stats['events_validated'] = 90
        
        realtime_manager.reset_stats()
        
        assert realtime_manager.stats['events_processed'] == 0
        assert realtime_manager.stats['events_validated'] == 0
    
    def test_emit_batch_single_event(self, realtime_manager, mock_socketio):
        """Test emitting batch with single event."""
        events = [{
            'type': 'log_message',
            'data': {'message': 'Test', 'level': 'INFO'},
            'socketio_events': ['log']
        }]
        
        realtime_manager._emit_batch(events)
        
        mock_socketio.emit.assert_called_once_with('log', {'message': 'Test', 'level': 'INFO'})
    
    def test_emit_batch_multiple_events(self, realtime_manager, mock_socketio):
        """Test emitting batch with multiple events."""
        events = [
            {
                'type': 'log_message',
                'data': {'message': 'Test1', 'level': 'INFO'},
                'socketio_events': ['log']
            },
            {
                'type': 'log_message',
                'data': {'message': 'Test2', 'level': 'INFO'},
                'socketio_events': ['log']
            }
        ]
        
        realtime_manager._emit_batch(events)
        
        # Should emit batch event
        mock_socketio.emit.assert_called_once()
        call_args = mock_socketio.emit.call_args
        assert call_args[0][0] == 'log_batch'
        assert call_args[0][1]['count'] == 2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])