#!/usr/bin/env python3
"""
Test Logging Pipeline

This script demonstrates that our logging fixes are working correctly
by simulating an agent run with proper logging.
"""

import asyncio
import sys
import os
from datetime import datetime

# Add the project root to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from knowledge_base_agent.config import Config
from knowledge_base_agent.unified_logging import get_unified_logger
from knowledge_base_agent.tasks import generate_task_id


async def test_logging_pipeline():
    """Test the complete logging pipeline with realistic agent messages."""
    
    # Generate a test task ID
    task_id = generate_task_id()
    config = Config.from_env()
    
    print(f"🧪 Testing logging pipeline with task_id: {task_id}")
    
    # Get unified logger (this should work now with our fixes)
    unified_logger = get_unified_logger(task_id, config)
    
    # Simulate agent startup
    unified_logger.log_structured(
        "🚀 Starting agent execution...",
        "INFO", "agent",
        {"run_mode": "test_pipeline", "task_id": task_id}
    )
    
    # Simulate initialization phase
    unified_logger.emit_phase_start(
        "initialization", 
        "Initializing agent components", 
        estimated_duration=30
    )
    
    await asyncio.sleep(0.5)
    
    unified_logger.log_structured(
        "✅ UserPreferences loaded: test_pipeline",
        "INFO", "agent",
        {"preferences": {"run_mode": "test_pipeline"}}
    )
    
    unified_logger.log_structured(
        "💾 Flask app context created for database operations",
        "INFO", "agent"
    )
    
    # Complete initialization
    unified_logger.emit_phase_complete(
        "initialization",
        result={"components_loaded": 3, "duration_seconds": 2.1}
    )
    
    # Simulate validation phases
    validation_phases = [
        ("initial_state_validation", "Initial State Validation", "Ensuring data structure integrity"),
        ("cache_phase_validation", "Tweet Cache Phase Validation", "Validating cache completeness"),
        ("media_phase_validation", "Media Processing Phase Validation", "Validating media processing")
    ]
    
    for phase_id, phase_name, description in validation_phases:
        unified_logger.emit_phase_start(phase_id, description, estimated_duration=15)
        
        await asyncio.sleep(0.3)
        
        # Simulate finding items to process
        items_found = 12 if phase_id == "cache_phase_validation" else 0
        
        unified_logger.log_structured(
            f"{phase_name}: Found {items_found} items needing processing",
            "INFO", "state_manager",
            {"phase": phase_id, "items_found": items_found}
        )
        
        unified_logger.emit_phase_complete(
            phase_id,
            result={"items_found": items_found, "fixes_applied": 0}
        )
    
    # Simulate content processing phase
    if True:  # Simulate having items to process
        unified_logger.emit_phase_start(
            "content_processing",
            "Processing content for 12 tweets",
            estimated_duration=120
        )
        
        # Simulate progress updates
        for i in range(0, 13, 3):
            unified_logger.emit_progress_update(
                i, 12, "content_processing",
                eta=f"{max(0, 12-i)*10}s"
            )
            await asyncio.sleep(0.2)
        
        unified_logger.emit_phase_complete(
            "content_processing",
            result={"tweets_processed": 12, "success_rate": 100}
        )
    
    # Simulate completion
    unified_logger.log_structured(
        "[completed] Agent execution completed successfully",
        "INFO", "agent",
        {"total_duration": 180, "phases_completed": 4}
    )
    
    unified_logger.emit_status_update(
        "completed",
        message="Agent execution completed successfully",
        details={"total_phases": 4, "success": True}
    )
    
    print(f"✅ Test completed! Check the Live Logs for task_id: {task_id}")
    print(f"   The logs should show:")
    print(f"   • Agent startup message")
    print(f"   • Initialization phase with timing")
    print(f"   • 3 validation phases with results")
    print(f"   • Content processing with progress updates")
    print(f"   • Completion message")
    
    return task_id


if __name__ == "__main__":
    task_id = asyncio.run(test_logging_pipeline())
    print(f"\n🔍 To verify the logs, run:")
    print(f"   curl -s http://localhost:5000/api/v2/agent/status/{task_id} | python -m json.tool")