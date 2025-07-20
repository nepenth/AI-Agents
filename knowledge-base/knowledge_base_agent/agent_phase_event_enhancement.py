"""Agent Processing Phase Event Enhancement

This module provides comprehensive event emission for all agent processing phases,
including the 7 main phases and 5 content processing sub-phases.
"""

import time
import traceback
from typing import Dict, Any, Optional, List, Callable
from datetime import datetime

from .unified_logging import EnhancedUnifiedLogger, get_unified_logger
from .config import Config


class AgentPhaseEventEnhancement:
    """
    Enhancement layer for Agent processing phases to emit comprehensive events.
    
    This class wraps agent processing phases with comprehensive event emission
    using the Enhanced Unified Logger for all 7 main phases and 5 sub-phases.
    """
    
    def __init__(self, agent, task_id: str, config: Optional[Config] = None):
        """
        Initialize the phase event enhancement.
        
        Args:
            agent: The Agent instance to enhance
            task_id: The task ID for event emission
            config: Optional configuration object
        """
        self.agent = agent
        self.task_id = task_id
        self.config = config or agent.config
        self.logger = get_unified_logger(task_id, self.config)
        
        # Track phase timing and metrics
        self.phase_start_times = {}
        self.phase_metrics = {}
        
        # Define the 7 main processing phases
        self.main_phases = [
            {
                "id": "user_input_parsing",
                "name": "User Input Parsing",
                "description": "Parsing and validating user preferences and configuration",
                "estimated_duration": 2
            },
            {
                "id": "fetch_bookmarks",
                "name": "Fetch Bookmarks",
                "description": "Fetching new bookmarks from configured sources",
                "estimated_duration": 30
            },
            {
                "id": "content_processing_overall",
                "name": "Content Processing",
                "description": "Processing tweet content through the complete pipeline",
                "estimated_duration": 300
            },
            {
                "id": "synthesis_generation",
                "name": "Synthesis Generation",
                "description": "Generating synthesis documents for categories",
                "estimated_duration": 120
            },
            {
                "id": "embedding_generation",
                "name": "Embedding Generation",
                "description": "Generating vector embeddings for knowledge base items",
                "estimated_duration": 180
            },
            {
                "id": "readme_generation",
                "name": "README Generation",
                "description": "Generating README files for knowledge base structure",
                "estimated_duration": 60
            },
            {
                "id": "git_sync",
                "name": "Git Synchronization",
                "description": "Synchronizing changes to Git repository",
                "estimated_duration": 30
            }
        ]
        
        # Define the 5 content processing sub-phases
        self.content_sub_phases = [
            {
                "id": "subphase_cp_cache",
                "name": "Tweet Caching",
                "description": "Caching tweet data and validating cache integrity",
                "estimated_duration": 30
            },
            {
                "id": "subphase_cp_media",
                "name": "Media Analysis",
                "description": "Analyzing and processing media content from tweets",
                "estimated_duration": 120
            },
            {
                "id": "subphase_cp_llm",
                "name": "LLM Processing",
                "description": "Processing tweets through language models for categorization",
                "estimated_duration": 180
            },
            {
                "id": "subphase_cp_kb_item",
                "name": "KB Item Generation",
                "description": "Generating knowledge base items from processed tweets",
                "estimated_duration": 90
            },
            {
                "id": "subphase_cp_db_sync",
                "name": "Database Sync",
                "description": "Synchronizing processed data to database",
                "estimated_duration": 30
            }
        ]
    
    def emit_phase_start(self, phase_id: str, message: str = None, estimated_duration: int = None, **kwargs) -> None:
        """
        Emit a phase start event with comprehensive data.
        
        Args:
            phase_id: The phase identifier
            message: Optional custom message
            estimated_duration: Optional estimated duration in seconds
            **kwargs: Additional data to include in the event
        """
        # Find phase info
        phase_info = self._get_phase_info(phase_id)
        
        # Use provided message or default from phase info
        if not message and phase_info:
            message = phase_info["description"]
        elif not message:
            message = f"Starting {phase_id}"
        
        # Use provided duration or default from phase info
        if not estimated_duration and phase_info:
            estimated_duration = phase_info["estimated_duration"]
        
        # Record start time
        self.phase_start_times[phase_id] = time.time()
        
        # Initialize metrics
        self.phase_metrics[phase_id] = {
            "start_time": self.phase_start_times[phase_id],
            "items_processed": 0,
            "total_items": kwargs.get("total_items", 0),
            "errors": 0
        }
        
        # Emit phase start event
        self.logger.emit_phase_start(
            phase_id,
            message,
            estimated_duration=estimated_duration
        )
        
        # Log structured data
        phase_data = {
            "phase_id": phase_id,
            "phase_name": phase_info["name"] if phase_info else phase_id,
            "estimated_duration": estimated_duration,
            "total_items": kwargs.get("total_items", 0)
        }
        phase_data.update(kwargs)
        
        self.logger.log_structured(
            f"Phase started: {phase_info['name'] if phase_info else phase_id}",
            "INFO",
            "agent_phase",
            phase_data
        )
    
    def emit_phase_progress(self, phase_id: str, processed_count: int, total_count: int = None, message: str = None) -> None:
        """
        Emit a phase progress update.
        
        Args:
            phase_id: The phase identifier
            processed_count: Number of items processed
            total_count: Total number of items to process
            message: Optional progress message
        """
        # Update metrics
        if phase_id in self.phase_metrics:
            self.phase_metrics[phase_id]["items_processed"] = processed_count
            if total_count is not None:
                self.phase_metrics[phase_id]["total_items"] = total_count
        
        # Use stored total if not provided
        if total_count is None and phase_id in self.phase_metrics:
            total_count = self.phase_metrics[phase_id]["total_items"]
        
        # Generate default message if not provided
        if not message:
            if total_count and total_count > 0:
                percentage = int((processed_count / total_count) * 100)
                message = f"Processing items: {processed_count}/{total_count} ({percentage}%)"
            else:
                message = f"Processed {processed_count} items"
        
        # Emit progress update
        if total_count and total_count > 0:
            self.logger.emit_progress_update(
                processed_count,
                total_count,
                phase_id
            )
        
        # Log progress
        self.logger.log_structured(
            message,
            "INFO",
            "agent_phase",
            {
                "phase_id": phase_id,
                "processed_count": processed_count,
                "total_count": total_count,
                "progress_percentage": int((processed_count / total_count) * 100) if total_count and total_count > 0 else 0
            }
        )
    
    def emit_phase_complete(self, phase_id: str, result: Any = None, message: str = None, **kwargs) -> None:
        """
        Emit a phase completion event.
        
        Args:
            phase_id: The phase identifier
            result: The result of the phase processing
            message: Optional completion message
            **kwargs: Additional data to include in the event
        """
        # Calculate duration
        duration = 0
        if phase_id in self.phase_start_times:
            duration = time.time() - self.phase_start_times[phase_id]
        
        # Get phase info
        phase_info = self._get_phase_info(phase_id)
        
        # Generate default message if not provided
        if not message:
            if phase_info:
                message = f"{phase_info['name']} completed successfully"
            else:
                message = f"Phase {phase_id} completed"
        
        # Prepare result data
        result_data = {
            "duration_seconds": duration,
            "phase_id": phase_id,
            "phase_name": phase_info["name"] if phase_info else phase_id
        }
        
        # Add metrics if available
        if phase_id in self.phase_metrics:
            metrics = self.phase_metrics[phase_id]
            result_data.update({
                "items_processed": metrics["items_processed"],
                "total_items": metrics["total_items"],
                "errors": metrics["errors"]
            })
        
        # Add result if provided
        if result is not None:
            result_data["result"] = result
        
        # Add additional kwargs
        result_data.update(kwargs)
        
        # Emit phase complete event
        self.logger.emit_phase_complete(
            phase_id,
            result_data,
            "agent_phase",
            {"duration_seconds": duration}
        )
        
        # Log completion
        self.logger.log_structured(
            message,
            "INFO",
            "agent_phase",
            result_data
        )
    
    def emit_phase_error(self, phase_id: str, error: Exception, message: str = None, **kwargs) -> None:
        """
        Emit a phase error event.
        
        Args:
            phase_id: The phase identifier
            error: The exception that occurred
            message: Optional error message
            **kwargs: Additional data to include in the event
        """
        # Calculate duration
        duration = 0
        if phase_id in self.phase_start_times:
            duration = time.time() - self.phase_start_times[phase_id]
        
        # Get phase info
        phase_info = self._get_phase_info(phase_id)
        
        # Generate default message if not provided
        if not message:
            if phase_info:
                message = f"{phase_info['name']} failed with error: {str(error)}"
            else:
                message = f"Phase {phase_id} failed: {str(error)}"
        
        # Update error count in metrics
        if phase_id in self.phase_metrics:
            self.phase_metrics[phase_id]["errors"] += 1
        
        # Prepare error data
        error_data = {
            "duration_seconds": duration,
            "phase_id": phase_id,
            "phase_name": phase_info["name"] if phase_info else phase_id,
            "error_type": type(error).__name__,
            "error_message": str(error),
            "traceback": traceback.format_exc()
        }
        error_data.update(kwargs)
        
        # Emit phase error event
        self.logger.emit_phase_error(
            phase_id,
            error,
            "agent_phase",
            error_data
        )
        
        # Log error
        self.logger.log_error(message, error)
    
    def emit_sub_phase_start(self, parent_phase_id: str, sub_phase_id: str, message: str = None, **kwargs) -> None:
        """
        Emit a sub-phase start event.
        
        Args:
            parent_phase_id: The parent phase identifier
            sub_phase_id: The sub-phase identifier
            message: Optional custom message
            **kwargs: Additional data to include in the event
        """
        # Find sub-phase info
        sub_phase_info = self._get_phase_info(sub_phase_id)
        
        # Use provided message or default from sub-phase info
        if not message and sub_phase_info:
            message = sub_phase_info["description"]
        elif not message:
            message = f"Starting {sub_phase_id}"
        
        # Record start time
        self.phase_start_times[sub_phase_id] = time.time()
        
        # Initialize metrics
        self.phase_metrics[sub_phase_id] = {
            "start_time": self.phase_start_times[sub_phase_id],
            "parent_phase": parent_phase_id,
            "items_processed": 0,
            "total_items": kwargs.get("total_items", 0),
            "errors": 0
        }
        
        # Emit sub-phase start event
        self.logger.emit_phase_start(
            sub_phase_id,
            message,
            estimated_duration=sub_phase_info["estimated_duration"] if sub_phase_info else None
        )
        
        # Log structured data
        sub_phase_data = {
            "parent_phase_id": parent_phase_id,
            "sub_phase_id": sub_phase_id,
            "sub_phase_name": sub_phase_info["name"] if sub_phase_info else sub_phase_id
        }
        sub_phase_data.update(kwargs)
        
        self.logger.log_structured(
            f"Sub-phase started: {sub_phase_info['name'] if sub_phase_info else sub_phase_id}",
            "INFO",
            "agent_sub_phase",
            sub_phase_data
        )
    
    def get_phase_metrics(self, phase_id: str) -> Dict[str, Any]:
        """
        Get metrics for a specific phase.
        
        Args:
            phase_id: The phase identifier
            
        Returns:
            Dict[str, Any]: Phase metrics
        """
        return self.phase_metrics.get(phase_id, {})
    
    def get_all_phase_metrics(self) -> Dict[str, Dict[str, Any]]:
        """
        Get metrics for all phases.
        
        Returns:
            Dict[str, Dict[str, Any]]: All phase metrics
        """
        return self.phase_metrics.copy()
    
    def _get_phase_info(self, phase_id: str) -> Optional[Dict[str, Any]]:
        """
        Get phase information by ID.
        
        Args:
            phase_id: The phase identifier
            
        Returns:
            Optional[Dict[str, Any]]: Phase information or None if not found
        """
        # Check main phases
        for phase in self.main_phases:
            if phase["id"] == phase_id:
                return phase
        
        # Check sub-phases
        for phase in self.content_sub_phases:
            if phase["id"] == phase_id:
                return phase
        
        return None
    
    def get_phase_info_list(self) -> List[Dict[str, Any]]:
        """
        Get information about all phases.
        
        Returns:
            List[Dict[str, Any]]: List of all phase information
        """
        return self.main_phases + self.content_sub_phases


def create_agent_phase_enhancement(agent, task_id: str) -> AgentPhaseEventEnhancement:
    """
    Factory function to create an AgentPhaseEventEnhancement.
    
    Args:
        agent: The Agent instance to enhance
        task_id: Task ID for event emission
        
    Returns:
        AgentPhaseEventEnhancement: Enhanced agent phase handler
    """
    return AgentPhaseEventEnhancement(agent, task_id)