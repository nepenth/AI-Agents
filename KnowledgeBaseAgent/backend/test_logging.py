#!/usr/bin/env python3
"""
Test script to generate various types of logs to test the logging system.
"""
import asyncio
import logging
import sys
import os
from datetime import datetime

# Add the backend directory to the path
sys.path.insert(0, '/home/nepenthe/git_repos/AI-Agents/KnowledgeBaseAgent/backend')

from app.logging_config import setup_logging
from app.services.log_service import (
    get_log_service, 
    log_with_context, 
    log_pipeline_progress, 
    log_task_status
)

async def test_logging_system():
    """Test the logging system with various log types."""
    
    # Setup logging
    setup_logging()
    
    # Initialize log service
    log_service = get_log_service()
    print("Log service initialized")
    
    # Test basic logging
    logger = logging.getLogger("test.logging")
    
    print("Generating test logs...")
    
    # Basic logs
    logger.info("Testing basic INFO log")
    logger.warning("Testing WARNING log with some details")
    logger.error("Testing ERROR log for demonstration")
    
    # Pipeline logs
    task_id = "test-task-12345"
    
    log_task_status(
        task_id=task_id,
        status="STARTED",
        message="Started test pipeline execution",
        task_type="PIPELINE_EXECUTION",
        parameters={"source": "test", "model": "gpt-4"}
    )
    
    log_pipeline_progress(
        task_id=task_id,
        phase="Initialization",
        message="Initializing test pipeline components",
        progress=10.0,
        total_phases=7
    )
    
    log_pipeline_progress(
        task_id=task_id,
        phase="Content Processing",
        message="Processing 15 content items",
        progress=30.0,
        items_processed=5,
        total_items=15
    )
    
    log_pipeline_progress(
        task_id=task_id,
        phase="AI Analysis",
        message="Running AI analysis on processed content",
        progress=60.0,
        model_used="gpt-4-turbo",
        tokens_used=2500
    )
    
    log_pipeline_progress(
        task_id=task_id,
        phase="Synthesis Generation",
        message="Generating synthesis document from analyzed content",
        progress=80.0,
        synthesis_type="comprehensive"
    )
    
    log_task_status(
        task_id=task_id,
        status="COMPLETED",
        message="Pipeline execution completed successfully",
        execution_time_seconds=120.5,
        items_processed=15,
        total_tokens=5200
    )
    
    # More diverse logs
    app_logger = logging.getLogger("app.services.content_processing")
    app_logger.info("Content processing service initialized")
    
    api_logger = logging.getLogger("api.v1.agent")
    api_logger.info("Agent API endpoint called", extra={
        'task_id': task_id,
        'details': {'endpoint': '/api/v1/agent/start', 'user_id': 'user123'}
    })
    
    # Celery task logs
    celery_logger = logging.getLogger("app.tasks.ai_processing")
    celery_logger.info("Starting AI processing task", extra={
        'task_id': task_id,
        'pipeline_phase': 'AI Analysis',
        'details': {'content_items': 15, 'model': 'gpt-4-turbo'}
    })
    
    # System logs
    system_logger = logging.getLogger("app.system")
    system_logger.warning("High memory usage detected", extra={
        'details': {'memory_usage': 85.2, 'threshold': 80.0, 'action': 'cleanup_initiated'}
    })
    
    # Error logs with traceback info
    try:
        raise ValueError("Test error for logging demonstration")
    except ValueError as e:
        error_logger = logging.getLogger("app.error_handling")
        error_logger.error(f"Test error occurred: {e}", extra={
            'task_id': task_id,
            'details': {'error_type': 'ValueError', 'context': 'test_logging'}
        }, exc_info=True)
    
    print("Test logs generated successfully!")
    
    # Wait a bit to let async processing complete
    await asyncio.sleep(2)
    
    # Show current log count
    total_logs = log_service.get_log_count()
    print(f"Total logs in service: {total_logs}")
    
    # Get recent logs
    recent_logs = log_service.get_logs(limit=10)
    print(f"\nRecent logs ({len(recent_logs)}):")
    for log in recent_logs:
        print(f"  {log.timestamp.strftime('%H:%M:%S')} [{log.level}] {log.module}: {log.message}")
        if log.task_id:
            print(f"    Task: {log.task_id}")
        if log.pipeline_phase:
            print(f"    Phase: {log.pipeline_phase}")


if __name__ == "__main__":
    asyncio.run(test_logging_system())