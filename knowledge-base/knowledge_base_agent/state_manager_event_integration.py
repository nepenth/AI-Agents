"""State Manager Event Integration

This module provides integration between StateManager validation phases
and the Enhanced Unified Logger for comprehensive event emission.
"""

import time
import traceback
from typing import Dict, Any, Optional, List

from .database_state_manager import DatabaseStateManager
from .unified_logging import EnhancedUnifiedLogger, get_unified_logger
from .config import Config


class StateManagerEventIntegration:
    """
    Integration layer for StateManager to emit validation phase events.
    
    This class wraps the StateManager validation phases with comprehensive
    event emission using the Enhanced Unified Logger.
    """
    
    def __init__(self, state_manager: DatabaseStateManager, task_id: str, config: Optional[Config] = None):
        """
        Initialize the integration layer.
        
        Args:
            state_manager: The StateManager instance to wrap
            task_id: The task ID for event emission
            config: Optional configuration object
        """
        self.state_manager = state_manager
        self.task_id = task_id
        self.config = config or state_manager.config
        self.logger = get_unified_logger(task_id, self.config)
        
        # Define validation phases with descriptions and estimated durations
        self.validation_phases = [
            {
                "id": "initial_state_validation",
                "name": "Initial State Validation",
                "description": "Validating initial state and ensuring all sets are properly initialized",
                "method": "_run_initial_state_validation",
                "estimated_duration": 2
            },
            {
                "id": "cache_phase_validation",
                "name": "Cache Phase Validation",
                "description": "Validating cached tweets and corresponding JSON files",
                "method": "_run_cache_phase_validation",
                "estimated_duration": 5
            },
            {
                "id": "media_phase_validation",
                "name": "Media Phase Validation",
                "description": "Validating media processing state and dependencies",
                "method": "_run_media_phase_validation",
                "estimated_duration": 3
            },
            {
                "id": "category_phase_validation",
                "name": "Category Phase Validation",
                "description": "Validating categorization state and category data",
                "method": "_run_category_phase_validation",
                "estimated_duration": 3
            },
            {
                "id": "kb_item_phase_validation",
                "name": "KB Item Phase Validation",
                "description": "Validating KB item generation state and KB data",
                "method": "_run_kb_item_phase_validation",
                "estimated_duration": 3
            },
            {
                "id": "final_processing_validation",
                "name": "Final Processing Validation",
                "description": "Validating processed tweets and pipeline completion",
                "method": "_run_final_processing_validation",
                "estimated_duration": 2
            }
        ]
    
    def run_validation_with_events(self) -> Dict[str, Any]:
        """
        Run StateManager validation with comprehensive event emission.
        
        This method wraps the StateManager.initialize() method with events
        for each validation phase, including start, progress, complete, and error events.
        
        Returns:
            Dict[str, Any]: Validation statistics
        """
        # Start overall validation phase
        self.logger.emit_phase_start(
            "state_validation",
            "Running comprehensive state validation",
            estimated_duration=sum(phase["estimated_duration"] for phase in self.validation_phases)
        )
        
        validation_stats = {
            "initial_state_fixes": 0,
            "cache_phase_fixes": 0,
            "media_phase_fixes": 0,
            "category_phase_fixes": 0,
            "kb_item_phase_fixes": 0,
            "tweets_moved_to_unprocessed": 0,
            "tweets_moved_to_processed": 0
        }
        
        # Run each validation phase with events
        for i, phase in enumerate(self.validation_phases):
            phase_id = phase["id"]
            phase_name = phase["name"]
            phase_description = phase["description"]
            method_name = phase["method"]
            
            # Emit phase start event
            self.logger.emit_phase_start(
                phase_id,
                phase_description,
                estimated_duration=phase["estimated_duration"]
            )
            
            try:
                # Run the validation phase
                start_time = time.time()
                
                if phase_id == "final_processing_validation":
                    # Special handling for final phase that returns a tuple
                    unprocessed_to_processed, processed_to_unprocessed = getattr(self.state_manager, method_name)()
                    validation_stats["tweets_moved_to_processed"] = len(unprocessed_to_processed)
                    validation_stats["tweets_moved_to_unprocessed"] = len(processed_to_unprocessed)
                    result = {
                        "tweets_moved_to_processed": len(unprocessed_to_processed),
                        "tweets_moved_to_unprocessed": len(processed_to_unprocessed)
                    }
                else:
                    # Standard phases return number of fixes
                    fixes = getattr(self.state_manager, method_name)()
                    validation_stats[f"{phase_id.replace('_validation', '_fixes')}"] = fixes
                    result = {"fixes_applied": fixes}
                
                duration = time.time() - start_time
                
                # Emit phase complete event
                self.logger.emit_phase_complete(
                    phase_id,
                    result,
                    "state_manager",
                    {"duration_seconds": duration}
                )
                
                # Emit progress update for overall validation
                self.logger.emit_progress_update(
                    i + 1,
                    len(self.validation_phases),
                    "state_validation"
                )
                
            except Exception as e:
                # Emit phase error event
                self.logger.emit_phase_error(
                    phase_id,
                    e,
                    "state_manager",
                    {"error_phase": phase_name}
                )
                
                # Re-raise the exception to maintain original behavior
                raise
        
        # Save validated state
        self.state_manager._save_state()
        
        # Emit overall validation complete event
        self.logger.emit_phase_complete(
            "state_validation",
            validation_stats,
            "state_manager",
            {"total_fixes": sum(val for key, val in validation_stats.items() if key.endswith('_fixes'))}
        )
        
        return validation_stats
    
    def initialize_with_events(self) -> Dict[str, Any]:
        """
        Initialize the StateManager with comprehensive event emission.
        
        This is a drop-in replacement for StateManager.initialize() that adds
        comprehensive event emission for all validation phases.
        
        Returns:
            Dict[str, Any]: Validation statistics
        """
        # Create directories if they don't exist (copied from StateManager.initialize)
        import os
        os.makedirs(self.state_manager.data_processing_dir, exist_ok=True)
        os.makedirs(self.state_manager.tweets_dir, exist_ok=True)
        
        # Load state file if it exists (copied from StateManager.initialize)
        if os.path.exists(self.state_manager.state_file_path):
            try:
                with open(self.state_manager.state_file_path, 'r') as f:
                    import json
                    loaded_state = json.load(f)
                
                # Convert lists to sets for efficient operations
                for key in self.state_manager.state:
                    if key in loaded_state and key != "tweet_data":
                        self.state_manager.state[key] = set(loaded_state[key])
                
                # Load tweet data
                if "tweet_data" in loaded_state:
                    self.state_manager.state["tweet_data"] = loaded_state["tweet_data"]
                    
            except Exception as e:
                self.logger.log_error("Failed to load state file", e)
                # Continue with empty state
        
        # Run validation phases with events
        return self.run_validation_with_events()
    
    def get_tweet_counts(self) -> Dict[str, int]:
        """
        Get counts of tweets in each processing state.
        
        Returns:
            Dict[str, int]: Counts of tweets in each state
        """
        counts = {}
        for key, value in self.state_manager.state.items():
            if key != "tweet_data" and isinstance(value, set):
                counts[key] = len(value)
        return counts
    
    def get_validation_phase_info(self) -> List[Dict[str, Any]]:
        """
        Get information about validation phases.
        
        Returns:
            List[Dict[str, Any]]: Information about each validation phase
        """
        return self.validation_phases.copy()
    
    def emit_validation_summary(self, validation_stats: Dict[str, Any]) -> None:
        """
        Emit a comprehensive validation summary event.
        
        Args:
            validation_stats: The validation statistics to summarize
        """
        total_fixes = sum(val for key, val in validation_stats.items() if key.endswith('_fixes'))
        tweet_counts = self.get_tweet_counts()
        
        summary_data = {
            "validation_stats": validation_stats,
            "tweet_counts": tweet_counts,
            "total_fixes_applied": total_fixes,
            "validation_phases_completed": len(self.validation_phases)
        }
        
        self.logger.log_structured(
            f"State validation completed with {total_fixes} total fixes applied",
            "INFO",
            "state_manager",
            summary_data
        )
        
        # Emit status update for frontend
        self.logger.emit_status_update(
            "completed",
            "state_validation",
            f"State validation completed successfully with {total_fixes} fixes",
            summary_data
        )


def create_state_manager_with_events(config: Config, task_id: str) -> StateManagerEventIntegration:
    """
    Factory function to create a StateManager with event integration.
    
    Args:
        config: Configuration object
        task_id: Task ID for event emission
        
    Returns:
        StateManagerEventIntegration: Integrated state manager
    """
    state_manager = DatabaseStateManager(config, task_id)
    return StateManagerEventIntegration(state_manager, task_id, config)