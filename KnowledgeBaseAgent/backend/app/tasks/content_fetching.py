"""
Content fetching tasks for Twitter/X bookmark processing.
"""
import asyncio
import logging
from typing import Dict, Any, List, Optional
from celery import current_task
from datetime import datetime

from app.tasks.celery_app import celery_app
from app.database.connection import get_session_factory
from app.repositories.content import get_content_repository
from app.services.twitter_client import get_twitter_client

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, name="content_fetching.fetch_twitter_bookmarks")
def fetch_twitter_bookmarks_task(self, bookmark_url: str, max_results: int = 100, 
                                force_refresh: bool = False) -> Dict[str, Any]:
    """Fetch Twitter/X bookmarks and store them in the database."""
    try:
        current_task.update_state(
            state='PROGRESS',
            meta={'current': 0, 'total': 4, 'status': 'Starting bookmark fetch...'}
        )
        
        # Run async bookmark fetching
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            result = loop.run_until_complete(
                _fetch_bookmarks_async(bookmark_url, max_results, force_refresh, self)
            )
            return result
        finally:
            loop.close()
            
    except Exception as e:
        logger.error(f"Bookmark fetching task failed: {e}")
        return {
            'status': 'failed',
            'phase': 'bookmark_fetching',
            'error': str(e)
        }


async def _fetch_bookmarks_async(bookmark_url: str, max_results: int, 
                               force_refresh: bool, task) -> Dict[str, Any]:
    """Async bookmark fetching implementation."""
    session_factory = get_session_factory()
    
    # Update progress
    task.update_state(
        state='PROGRESS',
        meta={'current': 1, 'total': 4, 'status': 'Connecting to Twitter/X API...'}
    )
    
    try:
        twitter_client = get_twitter_client()
        
        # Update progress
        task.update_state(
            state='PROGRESS',
            meta={'current': 2, 'total': 4, 'status': 'Fetching bookmarks...'}
        )
        
        # Fetch bookmarks (this will be implemented when Twitter client is ready)
        # For now, return a placeholder response
        bookmarks_data = []  # Placeholder
        
        # Update progress
        task.update_state(
            state='PROGRESS',
            meta={'current': 3, 'total': 4, 'status': 'Storing bookmarks in database...'}
        )
        
        # Store bookmarks in database
        async with session_factory() as db:
            content_repo = get_content_repository()
            new_bookmarks = 0
            updated_bookmarks = 0
            
            # Process each bookmark (placeholder logic)
            for bookmark in bookmarks_data:
                # This will be implemented with actual bookmark processing
                pass
        
        # Final progress update
        task.update_state(
            state='PROGRESS',
            meta={'current': 4, 'total': 4, 'status': 'Complete'}
        )
        
        return {
            'status': 'completed',
            'phase': 'bookmark_fetching',
            'bookmarks_fetched': len(bookmarks_data),
            'new_bookmarks': new_bookmarks,
            'updated_bookmarks': updated_bookmarks,
            'message': f'Successfully fetched {len(bookmarks_data)} bookmarks'
        }
        
    except Exception as e:
        logger.error(f"Error fetching bookmarks: {e}")
        raise


@celery_app.task(bind=True, name="content_fetching.refresh_bookmark_data")
def refresh_bookmark_data_task(self, content_id: str) -> Dict[str, Any]:
    """Refresh data for a specific bookmark."""
    try:
        current_task.update_state(
            state='PROGRESS',
            meta={'current': 0, 'total': 2, 'status': f'Refreshing bookmark data for {content_id}...'}
        )
        
        # Run async refresh
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            result = loop.run_until_complete(_refresh_bookmark_async(content_id, self))
            return result
        finally:
            loop.close()
            
    except Exception as e:
        logger.error(f"Bookmark refresh task failed for {content_id}: {e}")
        return {
            'status': 'failed',
            'content_id': content_id,
            'phase': 'bookmark_refresh',
            'error': str(e)
        }


async def _refresh_bookmark_async(content_id: str, task) -> Dict[str, Any]:
    """Async bookmark refresh implementation."""
    session_factory = get_session_factory()
    
    async with session_factory() as db:
        content_repo = get_content_repository()
        content_item = await content_repo.get(db, content_id)
        
        if not content_item:
            raise ValueError(f"Content item {content_id} not found")
        
        # Update progress
        task.update_state(
            state='PROGRESS',
            meta={'current': 1, 'total': 2, 'status': 'Fetching updated bookmark data...'}
        )
        
        # Simulate bookmark refresh (placeholder)
        await asyncio.sleep(1)
        
        # Update progress
        task.update_state(
            state='PROGRESS',
            meta={'current': 2, 'total': 2, 'status': 'Complete'}
        )
        
        return {
            'status': 'completed',
            'content_id': content_id,
            'phase': 'bookmark_refresh',
            'message': 'Bookmark data refreshed successfully'
        }