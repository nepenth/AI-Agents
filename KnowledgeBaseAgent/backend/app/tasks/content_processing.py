"""
Content processing tasks for the seven-phase pipeline.
"""
import asyncio
import logging
from typing import Dict, Any, List, Optional
from celery import current_task
from datetime import datetime

from app.tasks.celery_app import celery_app
from app.database.connection import get_session_factory
from app.repositories.content import get_content_repository
from app.services.model_router import get_model_router
from app.services.model_settings import ModelPhase
from app.services.ai_service import get_ai_service

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, name="content_processing.process_content_item")
def process_content_item_task(self, content_id: str, force_reprocess: bool = False) -> Dict[str, Any]:
    """Process a single content item through all sub-phases."""
    try:
        current_task.update_state(
            state='PROGRESS',
            meta={'current': 0, 'total': 3, 'status': f'Starting content processing for {content_id}...'}
        )
        
        # Run async content processing
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            result = loop.run_until_complete(_process_content_async(content_id, force_reprocess, self))
            return result
        finally:
            loop.close()
            
    except Exception as e:
        logger.error(f"Content processing task failed for {content_id}: {e}")
        return {
            'status': 'failed',
            'content_id': content_id,
            'phase': 'content_processing',
            'error': str(e)
        }


async def _process_content_async(content_id: str, force_reprocess: bool, task) -> Dict[str, Any]:
    """Async content processing implementation."""
    session_factory = get_session_factory()
    
    async with session_factory() as db:
        content_repo = get_content_repository()
        content_item = await content_repo.get(db, content_id)
        
        if not content_item:
            raise ValueError(f"Content item {content_id} not found")
        
        # Update progress
        task.update_state(
            state='PROGRESS',
            meta={'current': 1, 'total': 3, 'status': 'Processing content...'}
        )
        
        # Simulate content processing
        await asyncio.sleep(1)  # Placeholder for actual processing
        
        # Update progress
        task.update_state(
            state='PROGRESS',
            meta={'current': 2, 'total': 3, 'status': 'Finalizing...'}
        )
        
        # Mark as processed
        content_item.processing_state = "processed"
        await content_repo.update(db, content_item)
        
        # Final progress update
        task.update_state(
            state='PROGRESS',
            meta={'current': 3, 'total': 3, 'status': 'Complete'}
        )
        
        return {
            'status': 'completed',
            'content_id': content_id,
            'phase': 'content_processing',
            'message': 'Content processing completed successfully'
        }


@celery_app.task(bind=True, name="content_processing.batch_process")
def batch_process_content_task(self, content_ids: List[str], force_reprocess: bool = False) -> Dict[str, Any]:
    """Process multiple content items in batch."""
    try:
        total_items = len(content_ids)
        processed_items = 0
        failed_items = 0
        
        for i, content_id in enumerate(content_ids):
            try:
                # Update progress
                current_task.update_state(
                    state='PROGRESS',
                    meta={
                        'current': i + 1,
                        'total': total_items,
                        'status': f'Processing item {i + 1}/{total_items}: {content_id}'
                    }
                )
                
                # Process individual item
                result = process_content_item_task.apply(args=[content_id, force_reprocess])
                
                if result.get('status') == 'completed':
                    processed_items += 1
                else:
                    failed_items += 1
                    
            except Exception as e:
                logger.error(f"Failed to process content item {content_id}: {e}")
                failed_items += 1
        
        return {
            'status': 'completed',
            'phase': 'batch_content_processing',
            'total_items': total_items,
            'processed_items': processed_items,
            'failed_items': failed_items,
            'message': f'Batch processing completed: {processed_items} processed, {failed_items} failed'
        }
        
    except Exception as e:
        logger.error(f"Batch content processing failed: {e}")
        return {
            'status': 'failed',
            'phase': 'batch_content_processing',
            'error': str(e)
        }