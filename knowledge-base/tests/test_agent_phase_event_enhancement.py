#!/usr/bin/env python3
"""
Tests for Agent Processing Phase Event Enhancement

Tests the comprehensive event emission for all agent processing phases,
including the 7 main phases and 5 content processing sub-phases.
"""

import pytest
import time
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime

import sys
sys.path.append('.')

from knowledge_base_agent.agent_phase_event_enhancement import AgentPhaseEventEnhancement, create_agent_phase_enhancement


class TestAgentPhaseEventEnhancement:
    """Test Agent Processing Phase Event Enhancement functionality."""
    
    @pytest.fixture
    def mock_agent(self):
        """Create a mock agent for testing."""
        agent = Mock()
        agent.config = Mock()
        agent.task_id = "test-task-123"
        return agent
    
    @pytest.fixture
    def mock_logger(self):
        """Create a mock enhanced unified logger."""
        logger = Mock()
        logger.emit_phase_start = Mock()
        logger.emit_phase_complete = Mock()
        logger.emit_phase_error = Mock()
        logger.emit_progress_update = Mock()
        logger.log_structured = Mock()
        logger.log_error = Mock()
        return logger
    
    @pytest.fixture
    def phase_enhancement(self, mock_agent, mock_logger):
        """Create an AgentPhaseEventEnhancement instance for testing."""
        with patch('knowledge_base_agent.agent_phase_event_enhancement.get_unified_logger', return_value=mock_logger):
            enhancement = AgentPhaseEventEnhancement(mock_agent, "test-task-123", mock_agent.config)
            return enhancement
    
    def test_initialization(self, phase_enhancement, mock_logger):
        """Test AgentPhaseEventEnhancement initialization."""
        assert phase_enhancement.task_id == "test-task-123"
        assert phase_enhancement.logger == mock_logger
        assert len(phase_enhancement.main_phases) == 7
        assert len(phase_enhancement.content_sub_phases) == 5
        
        # Check main phases are properly defined
        main_phase_ids = [phase["id"] for phase in phase_enhancement.main_phases]
        expected_main_phases = [
            "user_input_parsing",
            "fetch_bookmarks",
            "content_processing_overall",
            "synthesis_generation",
            "embedding_generation",
            "readme_generation",
            "git_sync"
        ]
        assert main_phase_ids == expected_main_phases
        
        # Check sub-phases are properly defined
        sub_phase_ids = [phase["id"] for phase in phase_enhancement.content_sub_phases]
        expected_sub_phases = [
            "subphase_cp_cache",
            "subphase_cp_media",
            "subphase_cp_llm",
            "subphase_cp_kb_item",
            "subphase_cp_db_sync"
        ]
        assert sub_phase_ids == expected_sub_phases
    
    def test_get_phase_info(self, phase_enhancement):
        """Test getting phase information by ID."""
        # Test main phase
        main_phase_info = phase_enhancement._get_phase_info("fetch_bookmarks")
        assert main_phase_info is not None
        assert main_phase_info["id"] == "fetch_bookmarks"
        assert main_phase_info["name"] == "Fetch Bookmarks"
        assert "description" in main_phase_info
        assert "estimated_duration" in main_phase_info
        
        # Test sub-phase
        sub_phase_info = phase_enhancement._get_phase_info("subphase_cp_media")
        assert sub_phase_info is not None
        assert sub_phase_info["id"] == "subphase_cp_media"
        assert sub_phase_info["name"] == "Media Analysis"
        
        # Test non-existent phase
        non_existent = phase_enhancement._get_phase_info("non_existent_phase")
        assert non_existent is None
    
    def test_get_phase_info_list(self, phase_enhancement):
        """Test getting all phase information."""
        all_phases = phase_enhancement.get_phase_info_list()
        assert len(all_phases) == 12  # 7 main + 5 sub
        
        # Check that all phases have required fields
        for phase in all_phases:
            assert "id" in phase
            assert "name" in phase
            assert "description" in phase
            assert "estimated_duration" in phase
    
    @patch('knowledge_base_agent.agent_phase_event_enhancement.time.time')
    def test_emit_phase_start(self, mock_time, phase_enhancement, mock_logger):
        """Test emitting phase start events."""
        mock_time.return_value = 1000.0
        
        # Test with known phase
        phase_enhancement.emit_phase_start("fetch_bookmarks", total_items=100)
        
        # Verify logger calls
        mock_logger.emit_phase_start.assert_called_once()
        call_args = mock_logger.emit_phase_start.call_args
        assert call_args[0][0] == "fetch_bookmarks"  # phase_id
        assert "Fetching new bookmarks" in call_args[0][1]  # message
        assert call_args[1]["estimated_duration"] == 30  # from phase definition
        
        mock_logger.log_structured.assert_called_once()
        
        # Verify internal tracking
        assert "fetch_bookmarks" in phase_enhancement.phase_start_times
        assert "fetch_bookmarks" in phase_enhancement.phase_metrics
        assert phase_enhancement.phase_metrics["fetch_bookmarks"]["total_items"] == 100
    
    def test_emit_phase_progress(self, phase_enhancement, mock_logger):
        """Test emitting phase progress updates."""
        # Initialize phase first
        phase_enhancement.phase_metrics["content_processing_overall"] = {
            "items_processed": 0,
            "total_items": 100,
            "errors": 0
        }
        
        # Emit progress
        phase_enhancement.emit_phase_progress("content_processing_overall", 50, 100)
        
        # Verify logger calls
        mock_logger.emit_progress_update.assert_called_once_with(50, 100, "content_processing_overall")
        mock_logger.log_structured.assert_called_once()
        
        # Verify metrics update
        assert phase_enhancement.phase_metrics["content_processing_overall"]["items_processed"] == 50
    
    @patch('knowledge_base_agent.agent_phase_event_enhancement.time.time')
    def test_emit_phase_complete(self, mock_time, phase_enhancement, mock_logger):
        """Test emitting phase completion events."""
        # Setup phase start time
        phase_enhancement.phase_start_times["synthesis_generation"] = 1000.0
        phase_enhancement.phase_metrics["synthesis_generation"] = {
            "items_processed": 25,
            "total_items": 25,
            "errors": 0
        }
        mock_time.return_value = 1120.0  # 2 minutes later
        
        # Emit completion
        result_data = {"syntheses_generated": 25}
        phase_enhancement.emit_phase_complete("synthesis_generation", result_data)
        
        # Verify logger calls
        mock_logger.emit_phase_complete.assert_called_once()
        call_args = mock_logger.emit_phase_complete.call_args
        assert call_args[0][0] == "synthesis_generation"  # phase_id
        assert call_args[0][2] == "agent_phase"  # component
        
        # Check result data includes duration and metrics
        result = call_args[0][1]
        assert result["duration_seconds"] == 120.0
        assert result["items_processed"] == 25
        assert result["total_items"] == 25
        assert result["result"] == result_data
        
        mock_logger.log_structured.assert_called_once()
    
    def test_emit_phase_error(self, phase_enhancement, mock_logger):
        """Test emitting phase error events."""
        # Setup phase start time
        phase_enhancement.phase_start_times["embedding_generation"] = 1000.0
        phase_enhancement.phase_metrics["embedding_generation"] = {
            "errors": 0
        }
        
        # Create test exception
        test_error = Exception("Test embedding error")
        
        # Emit error
        with patch('knowledge_base_agent.agent_phase_event_enhancement.time.time', return_value=1060.0):
            phase_enhancement.emit_phase_error("embedding_generation", test_error)
        
        # Verify logger calls
        mock_logger.emit_phase_error.assert_called_once()
        call_args = mock_logger.emit_phase_error.call_args
        assert call_args[0][0] == "embedding_generation"  # phase_id
        assert call_args[0][1] == test_error  # exception
        assert call_args[0][2] == "agent_phase"  # component
        
        # Check error data
        error_data = call_args[0][3]
        assert error_data["duration_seconds"] == 60.0
        assert error_data["error_type"] == "Exception"
        assert error_data["error_message"] == "Test embedding error"
        assert "traceback" in error_data
        
        mock_logger.log_error.assert_called_once()
        
        # Verify error count updated
        assert phase_enhancement.phase_metrics["embedding_generation"]["errors"] == 1
    
    def test_emit_sub_phase_start(self, phase_enhancement, mock_logger):
        """Test emitting sub-phase start events."""
        # Emit sub-phase start
        phase_enhancement.emit_sub_phase_start(
            "content_processing_overall",
            "subphase_cp_media",
            total_items=50
        )
        
        # Verify logger calls
        mock_logger.emit_phase_start.assert_called_once()
        call_args = mock_logger.emit_phase_start.call_args
        assert call_args[0][0] == "subphase_cp_media"  # phase_id
        assert "media content" in call_args[0][1].lower()  # message
        assert call_args[1]["estimated_duration"] == 120  # from sub-phase definition
        
        mock_logger.log_structured.assert_called_once()
        
        # Verify internal tracking
        assert "subphase_cp_media" in phase_enhancement.phase_start_times
        assert "subphase_cp_media" in phase_enhancement.phase_metrics
        metrics = phase_enhancement.phase_metrics["subphase_cp_media"]
        assert metrics["parent_phase"] == "content_processing_overall"
        assert metrics["total_items"] == 50
    
    def test_get_phase_metrics(self, phase_enhancement):
        """Test getting phase metrics."""
        # Setup test metrics
        test_metrics = {
            "start_time": 1000.0,
            "items_processed": 10,
            "total_items": 20,
            "errors": 1
        }
        phase_enhancement.phase_metrics["test_phase"] = test_metrics
        
        # Get metrics
        metrics = phase_enhancement.get_phase_metrics("test_phase")
        assert metrics == test_metrics
        
        # Test non-existent phase
        empty_metrics = phase_enhancement.get_phase_metrics("non_existent")
        assert empty_metrics == {}
    
    def test_get_all_phase_metrics(self, phase_enhancement):
        """Test getting all phase metrics."""
        # Setup test metrics
        phase_enhancement.phase_metrics["phase1"] = {"items": 10}
        phase_enhancement.phase_metrics["phase2"] = {"items": 20}
        
        # Get all metrics
        all_metrics = phase_enhancement.get_all_phase_metrics()
        assert len(all_metrics) == 2
        assert all_metrics["phase1"]["items"] == 10
        assert all_metrics["phase2"]["items"] == 20
        
        # Verify it's a copy (not reference)
        all_metrics["phase1"]["items"] = 999
        assert phase_enhancement.phase_metrics["phase1"]["items"] == 10
    
    def test_create_agent_phase_enhancement_factory(self, mock_agent):
        """Test factory function for creating AgentPhaseEventEnhancement."""
        with patch('knowledge_base_agent.agent_phase_event_enhancement.get_unified_logger'):
            enhancement = create_agent_phase_enhancement(mock_agent, "test-task-456")
            
            assert isinstance(enhancement, AgentPhaseEventEnhancement)
            assert enhancement.task_id == "test-task-456"
            assert enhancement.agent == mock_agent


class TestAgentIntegration:
    """Test integration with actual Agent methods."""
    
    def test_agent_create_phase_enhancement_method(self):
        """Test Agent.create_phase_enhancement method."""
        # Create mock agent with required attributes
        mock_agent = Mock()
        mock_agent.task_id = "test-task-789"
        mock_agent.config = Mock()
        
        # Import and patch the Agent class method
        from knowledge_base_agent.agent import KnowledgeBaseAgent
        
        # Create a real agent instance for testing the method
        with patch('knowledge_base_agent.agent.StateManager'), \
             patch('knowledge_base_agent.agent.CategoryManager'), \
             patch('knowledge_base_agent.agent.HTTPClient'), \
             patch('knowledge_base_agent.agent.GitSyncHandler'), \
             patch('knowledge_base_agent.agent.get_unified_logger'):
            
            agent = KnowledgeBaseAgent(
                app=Mock(),
                config=Mock(),
                task_id="test-task-789"
            )
            
            with patch('knowledge_base_agent.agent_phase_event_enhancement.get_unified_logger'):
                enhancement = agent.create_phase_enhancement()
                
                assert isinstance(enhancement, AgentPhaseEventEnhancement)
                assert enhancement.task_id == "test-task-789"
    
    def test_agent_create_phase_enhancement_no_task_id(self):
        """Test Agent.create_phase_enhancement method without task_id."""
        with patch('knowledge_base_agent.agent.StateManager'), \
             patch('knowledge_base_agent.agent.CategoryManager'), \
             patch('knowledge_base_agent.agent.HTTPClient'), \
             patch('knowledge_base_agent.agent.GitSyncHandler'):
            
            agent = KnowledgeBaseAgent(
                app=Mock(),
                config=Mock(),
                task_id=None  # No task_id
            )
            
            with pytest.raises(ValueError, match="Cannot create phase enhancement without task_id"):
                agent.create_phase_enhancement()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])