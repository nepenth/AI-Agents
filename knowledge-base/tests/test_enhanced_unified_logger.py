"""
Unit tests for Enhanced Unified Logger

Tests the comprehensive event emission capabilities and backward compatibility
of the EnhancedUnifiedLogger implementation.
"""

import pytest
import asyncio
import json
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from datetime import datetime
from knowledge_base_agent.unified_logging import EnhancedUnifiedLogger, StructuredEventEmitter, get_unified_logger
from knowledge_base_agent.config import Config


class TestStructuredEventEmitter:
    """Test the StructuredEventEmitter class."""
    
    @pytest.fixture
    def mock_progress_manager(self):
        """Create a mock progress manager."""
        manager = Mock()
        manager.log_message = AsyncMock()
        manager.publish_phase_event = AsyncMock()
        manager.publish_progress_update = AsyncMock()
        manager.publish_agent_status_update = AsyncMock()
        return manager
    
    @pytest.fixture
    def event_emitter(self, mock_progress_manager):
        """Create a StructuredEventEmitter instance."""
        return StructuredEventEmitter("test-task-123", mock_progress_manager)
    
    def test_emit_log_event_basic(self, event_emitter, mock_progress_manager):
        """Test basic log event emission."""
        event_emitter.emit_log_event("Test message", "INFO", "test_component")
        
        # Verify the async call was made
        mock_progress_manager.log_message.assert_called_once()
        call_args = mock_progress_manager.log_message.call_args
        
        assert call_args[0][0] == "test-task-123"  # task_id
        assert call_args[0][1] == "Test message"   # message
        assert call_args[0][2] == "INFO"           # level
        assert call_args[1]["component"] == "test_component"
    
    def test_emit_log_event_with_structured_data(self, event_emitter, mock_progress_manager):
        """Test log event emission with structured data."""
        structured_data = {"key1": "value1", "key2": 42}
        event_emitter.emit_log_event(
            "Test message", "ERROR", "test_component", 
            structured_data=structured_data, traceback_info="test traceback"
        )
        
        mock_progress_manager.log_message.assert_called_once()
        call_args = mock_progress_manager.log_message.call_args
        
        assert call_args[1]["structured_data"] == structured_data
        assert call_args[1]["traceback"] == "test traceback"
    
    def test_emit_phase_event_start(self, event_emitter, mock_progress_manager):
        """Test phase start event emission."""
        event_emitter.emit_phase_event(
            "phase_start", "test_phase", "Test phase description", 
            estimated_duration=60
        )
        
        mock_progress_manager.publish_phase_event.assert_called_once()
        call_args = mock_progress_manager.publish_phase_event.call_args
        
        assert call_args[0][0] == "test-task-123"  # task_id
        assert call_args[0][1] == "phase_start"    # event_type
        
        phase_data = call_args[0][2]
        assert phase_data["phase_name"] == "test_phase"
        assert phase_data["phase_description"] == "Test phase description"
        assert phase_data["estimated_duration"] == 60
        assert "timestamp" in phase_data
    
    def test_emit_progress_event(self, event_emitter, mock_progress_manager):
        """Test progress event emission."""
        event_emitter.emit_progress_event(50, 100, "test_operation", eta="5 minutes")
        
        mock_progress_manager.publish_progress_update.assert_called_once()
        call_args = mock_progress_manager.publish_progress_update.call_args
        
        assert call_args[0][0] == "test-task-123"  # task_id
        
        progress_data = call_args[0][1]
        assert progress_data["current"] == 50
        assert progress_data["total"] == 100
        assert progress_data["percentage"] == 50.0
        assert progress_data["operation"] == "test_operation"
        assert progress_data["eta"] == "5 minutes"
    
    def test_emit_status_event(self, event_emitter, mock_progress_manager):
        """Test status event emission."""
        details = {"detail1": "value1"}
        event_emitter.emit_status_event(
            "running", details=details, phase="test_phase", message="Test message"
        )
        
        mock_progress_manager.publish_agent_status_update.assert_called_once()
        call_args = mock_progress_manager.publish_agent_status_update.call_args
        
        status_data = call_args[0][0]
        assert status_data["task_id"] == "test-task-123"
        assert status_data["status"] == "running"
        assert status_data["phase"] == "test_phase"
        assert status_data["message"] == "Test message"
        assert status_data["details"] == details


class TestEnhancedUnifiedLogger:
    """Test the EnhancedUnifiedLogger class."""
    
    @pytest.fixture
    def mock_config(self):
        """Create a mock config."""
        config = Mock(spec=Config)
        return config
    
    @pytest.fixture
    def mock_progress_manager(self):
        """Create a mock progress manager."""
        manager = Mock()
        manager.log_message = AsyncMock()
        manager.publish_phase_event = AsyncMock()
        manager.publish_progress_update = AsyncMock()
        manager.publish_agent_status_update = AsyncMock()
        manager.update_progress = AsyncMock()
        manager.publish_phase_update = AsyncMock()
        return manager
    
    @pytest.fixture
    def logger(self, mock_config, mock_progress_manager):
        """Create an EnhancedUnifiedLogger instance."""
        with patch('knowledge_base_agent.unified_logging.get_progress_manager', return_value=mock_progress_manager):
            return EnhancedUnifiedLogger("test-task-123", mock_config)
    
    def test_initialization(self, logger):
        """Test logger initialization."""
        assert logger.task_id == "test-task-123"
        assert isinstance(logger.event_emitter, StructuredEventEmitter)
        assert logger._active_phases == {}
        assert logger._phase_start_times == {}
    
    def test_log_structured(self, logger):
        """Test structured logging."""
        structured_data = {"key": "value"}
        logger.log_structured("Test message", "INFO", "test_component", structured_data)
        
        # Verify the event emitter was called
        assert logger.event_emitter.progress_manager.log_message.called
    
    def test_log_error_with_exception(self, logger):
        """Test error logging with exception."""
        test_exception = ValueError("Test error")
        logger.log_error("Test error message", test_exception, "test_component")
        
        # Verify the event emitter was called
        assert logger.event_emitter.progress_manager.log_message.called
    
    def test_emit_phase_start(self, logger):
        """Test phase start emission."""
        logger.emit_phase_start("test_phase", "Test description", 60)
        
        # Verify phase tracking
        assert "test_phase" in logger._active_phases
        assert "test_phase" in logger._phase_start_times
        
        # Verify event emission
        assert logger.event_emitter.progress_manager.publish_phase_event.called
        assert logger.event_emitter.progress_manager.log_message.called
    
    def test_emit_phase_complete(self, logger):
        """Test phase completion emission."""
        # First start a phase
        logger.emit_phase_start("test_phase", "Test description")
        
        # Then complete it
        result = {"items_processed": 10}
        logger.emit_phase_complete("test_phase", result)
        
        # Verify phase tracking cleanup
        assert "test_phase" not in logger._active_phases
        assert "test_phase" not in logger._phase_start_times
        
        # Verify event emission
        assert logger.event_emitter.progress_manager.publish_phase_event.called
    
    def test_emit_phase_error(self, logger):
        """Test phase error emission."""
        # First start a phase
        logger.emit_phase_start("test_phase", "Test description")
        
        # Then emit error
        test_error = RuntimeError("Test error")
        logger.emit_phase_error("test_phase", test_error)
        
        # Verify phase tracking cleanup
        assert "test_phase" not in logger._active_phases
        assert "test_phase" not in logger._phase_start_times
        
        # Verify event emission
        assert logger.event_emitter.progress_manager.publish_phase_event.called
    
    def test_emit_progress_update(self, logger, mock_progress_manager):
        """Test progress update emission."""
        logger.emit_progress_update(25, 100, "test_operation")
        
        # Verify both new and legacy progress systems called
        assert logger.event_emitter.progress_manager.publish_progress_update.called
        mock_progress_manager.update_progress.assert_called()
    
    def test_emit_status_update(self, logger):
        """Test status update emission."""
        details = {"detail": "value"}
        logger.emit_status_update("running", "test_phase", "Test message", details)
        
        # Verify event emission
        assert logger.event_emitter.progress_manager.publish_agent_status_update.called
        assert logger.event_emitter.progress_manager.log_message.called
    
    def test_backward_compatibility_log(self, logger):
        """Test backward compatible log method."""
        logger.log("Test message", "INFO", extra_key="extra_value")
        
        # Verify the structured logging was called
        assert logger.event_emitter.progress_manager.log_message.called
    
    def test_backward_compatibility_update_progress(self, logger, mock_progress_manager):
        """Test backward compatible update_progress method."""
        logger.update_progress(50, "test_phase", "Test message", "running")
        
        # Verify the progress manager was called
        mock_progress_manager.update_progress.assert_called()
    
    def test_backward_compatibility_emit_phase_update(self, logger, mock_progress_manager):
        """Test backward compatible emit_phase_update method."""
        logger.emit_phase_update("test_phase", "running", "Test message", 50)
        
        # Verify the progress manager was called
        mock_progress_manager.publish_phase_update.assert_called()
    
    def test_backward_compatibility_emit_agent_status(self, logger, mock_progress_manager):
        """Test backward compatible emit_agent_status method."""
        status_data = {"is_running": True}
        logger.emit_agent_status(status_data)
        
        # Verify task_id was added and progress manager was called
        mock_progress_manager.publish_agent_status_update.assert_called()
        call_args = mock_progress_manager.publish_agent_status_update.call_args
        assert call_args[0][0]["task_id"] == "test-task-123"
    
    def test_get_caller_component(self, logger):
        """Test automatic component detection."""
        component = logger._get_caller_component()
        assert isinstance(component, str)
        # Should return the test file name without .py extension
        assert "test_enhanced_unified_logger" in component or component == "unknown"


class TestGlobalLoggerRegistry:
    """Test the global logger registry functions."""
    
    def test_get_unified_logger_creates_new(self):
        """Test that get_unified_logger creates a new logger."""
        with patch('knowledge_base_agent.unified_logging.get_progress_manager'):
            logger = get_unified_logger("test-task-456")
            assert isinstance(logger, EnhancedUnifiedLogger)
            assert logger.task_id == "test-task-456"
    
    def test_get_unified_logger_returns_existing(self):
        """Test that get_unified_logger returns existing logger."""
        with patch('knowledge_base_agent.unified_logging.get_progress_manager'):
            logger1 = get_unified_logger("test-task-789")
            logger2 = get_unified_logger("test-task-789")
            assert logger1 is logger2
    
    def test_cleanup_task_logger(self):
        """Test logger cleanup."""
        from knowledge_base_agent.unified_logging import cleanup_task_logger, _task_loggers
        
        with patch('knowledge_base_agent.unified_logging.get_progress_manager'):
            logger = get_unified_logger("test-task-cleanup")
            assert "test-task-cleanup" in _task_loggers
            
            cleanup_task_logger("test-task-cleanup")
            assert "test-task-cleanup" not in _task_loggers


class TestAsyncIntegration:
    """Test async integration and error handling."""
    
    @pytest.fixture
    def logger_with_failing_progress_manager(self):
        """Create logger with a progress manager that fails."""
        failing_manager = Mock()
        failing_manager.log_message = AsyncMock(side_effect=Exception("Redis connection failed"))
        failing_manager.publish_phase_event = AsyncMock(side_effect=Exception("Redis connection failed"))
        
        with patch('knowledge_base_agent.unified_logging.get_progress_manager', return_value=failing_manager):
            return EnhancedUnifiedLogger("test-task-fail", Config())
    
    def test_error_handling_in_log_emission(self, logger_with_failing_progress_manager):
        """Test that logger handles Redis failures gracefully."""
        # This should not raise an exception
        logger_with_failing_progress_manager.log("Test message", "INFO")
        
        # Verify the failing manager was called
        assert logger_with_failing_progress_manager.progress_manager.log_message.called
    
    def test_error_handling_in_phase_emission(self, logger_with_failing_progress_manager):
        """Test that logger handles Redis failures in phase events gracefully."""
        # This should not raise an exception
        logger_with_failing_progress_manager.emit_phase_start("test_phase", "Test description")
        
        # Verify the failing manager was called
        assert logger_with_failing_progress_manager.event_emitter.progress_manager.publish_phase_event.called


if __name__ == "__main__":
    pytest.main([__file__])