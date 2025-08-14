"""
Celery tasks for synthesis document generation with timeout handling.
"""

import asyncio
import logging
from typing import Dict, Any, List, Optional, Tuple
from celery import current_task
from celery.exceptions import SoftTimeLimitExceeded

from app.tasks.celery_app import celery_app
from app.tasks.base import SynthesisTask, TaskResult
from app.services.synthesis_generator import get_synthesis_generator
from app.repositories.knowledge import get_knowledge_repository
from app.repositories.synthesis import get_synthesis_repository
from app.database.connection import get_db_session

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, base=SynthesisTask, name="generate_synthesis_document")
def generate_synthesis_document(
    self, 
    main_category: str, 
    sub_category: str,
    knowledge_item_ids: Optional[List[str]] = None
) -> Dict[str, Any]:
    """
    Generate a synthesis document for a category.
    
    Args:
        main_category: Main category name
        sub_category: Sub-category name
        knowledge_item_ids: Optional list of specific knowledge item IDs to include
        
    Returns:
        Dict containing synthesis generation results
    """
    try:
        self.update_progress(0, 4, f"Starting synthesis for {main_category}/{sub_category}...")
        
        # Run async synthesis generation with timeout handling
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            result = loop.run_until_complete(
                _generate_synthesis_async(main_category, sub_category, knowledge_item_ids, self)
            )
            
            return TaskResult(
                success=True,
                data=result
            ).to_dict()
            
        finally:
            loop.close()
            
    except SoftTimeLimitExceeded:
        logger.warning(f"Synthesis generation for {main_category}/{sub_category} exceeded time limit")
        return TaskResult(
            success=False,
            error="Synthesis generation exceeded time limit",
            error_type="SoftTimeLimitExceeded"
        ).to_dict()
        
    except Exception as e:
        logger.error(f"Synthesis generation failed for {main_category}/{sub_category}: {e}")
        return TaskResult(
            success=False,
            error=str(e),
            error_type=type(e).__name__
        ).to_dict()


async def _generate_synthesis_async(
    main_category: str, 
    sub_category: str,
    knowledge_item_ids: Optional[List[str]],
    task
) -> Dict[str, Any]:
    """Async implementation of synthesis generation."""
    knowledge_repo = get_knowledge_repository()
    synthesis_repo = get_synthesis_repository()
    synthesis_generator = get_synthesis_generator()
    
    async with get_db_session() as db:
        # Step 1: Load knowledge items
        task.update_progress(1, 4, "Loading knowledge items for synthesis...")
        
        if knowledge_item_ids:
            # Load specific knowledge items
            knowledge_items = []
            for item_id in knowledge_item_ids:
                item = await knowledge_repo.get(db, item_id)
                if item:
                    knowledge_items.append(item)
        else:
            # Load all knowledge items for the category
            # This would require a method to query by category
            # For now, we'll assume we get them somehow
            knowledge_items = []  # TODO: Implement category-based query
        
        if not knowledge_items:
            return {
                "main_category": main_category,
                "sub_category": sub_category,
                "synthesis_id": None,
                "message": "No knowledge items found for synthesis",
                "item_count": 0
            }
        
        # Step 2: Check for existing synthesis
        task.update_progress(2, 4, "Checking for existing synthesis...")
        # This would check if synthesis already exists and is up to date
        # For now, we'll always generate new synthesis
        
        # Step 3: Generate synthesis
        task.update_progress(3, 4, f"Generating synthesis from {len(knowledge_items)} items...", 
                           phase="ai_synthesis")
        
        synthesis_result = await synthesis_generator.generate_synthesis_document(
            main_category, sub_category, knowledge_items
        )
        
        # Step 4: Save synthesis document
        task.update_progress(4, 4, "Saving synthesis document...")
        synthesis_doc = await synthesis_repo.create(db, synthesis_result.synthesis_document)
    
    return {
        "main_category": main_category,
        "sub_category": sub_category,
        "synthesis_id": synthesis_doc.id,
        "title": synthesis_doc.title,
        "item_count": synthesis_doc.item_count,
        "word_count": synthesis_doc.word_count,
        "coherence_score": synthesis_doc.coherence_score,
        "completeness_score": synthesis_doc.completeness_score,
        "generation_time": synthesis_result.generation_stats.get("generation_duration"),
        "markdown_path": synthesis_doc.markdown_path
    }


@celery_app.task(bind=True, base=SynthesisTask, name="batch_generate_synthesis")
def batch_generate_synthesis(
    self, 
    category_pairs: List[Tuple[str, str]]
) -> Dict[str, Any]:
    """
    Generate synthesis documents for multiple categories.
    
    Args:
        category_pairs: List of (main_category, sub_category) tuples
        
    Returns:
        Dict containing batch synthesis results
    """
    try:
        self.update_progress(0, len(category_pairs), "Starting batch synthesis generation...")
        
        successful_synthesis = []
        failed_synthesis = []
        
        for i, (main_category, sub_category) in enumerate(category_pairs):
            try:
                self.update_progress(
                    i, len(category_pairs),
                    f"Generating synthesis {i + 1}/{len(category_pairs)}: {main_category}/{sub_category}",
                    phase="batch_processing"
                )
                
                # Generate synthesis for this category
                result = generate_synthesis_document.apply_async(
                    args=[main_category, sub_category]
                ).get()
                
                if result.get("success", False):
                    successful_synthesis.append(result["data"])
                else:
                    failed_synthesis.append({
                        "main_category": main_category,
                        "sub_category": sub_category,
                        "error": result.get("error", "Unknown error")
                    })
                
                # Small delay between synthesis generations
                import time
                time.sleep(2)
                
            except Exception as e:
                logger.error(f"Failed to generate synthesis for {main_category}/{sub_category}: {e}")
                failed_synthesis.append({
                    "main_category": main_category,
                    "sub_category": sub_category,
                    "error": str(e)
                })
        
        self.update_progress(
            len(category_pairs), len(category_pairs),
            "Batch synthesis generation completed",
            details={
                "successful": len(successful_synthesis),
                "failed": len(failed_synthesis)
            }
        )
        
        return TaskResult(
            success=True,
            data={
                "successful_synthesis": successful_synthesis,
                "failed_synthesis": failed_synthesis,
                "success_count": len(successful_synthesis),
                "failure_count": len(failed_synthesis),
                "total_categories": len(category_pairs)
            }
        ).to_dict()
        
    except Exception as e:
        logger.error(f"Batch synthesis generation failed: {e}")
        return TaskResult(
            success=False,
            error=str(e),
            error_type=type(e).__name__
        ).to_dict()


@celery_app.task(bind=True, base=SynthesisTask, name="update_stale_synthesis")
def update_stale_synthesis(self, synthesis_id: str) -> Dict[str, Any]:
    """
    Update a stale synthesis document.
    
    Args:
        synthesis_id: ID of the synthesis document to update
        
    Returns:
        Dict containing update results
    """
    try:
        self.update_progress(0, 3, "Loading synthesis document...")
        
        # Run async synthesis update
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            result = loop.run_until_complete(
                _update_synthesis_async(synthesis_id, self)
            )
            
            return TaskResult(
                success=True,
                data=result
            ).to_dict()
            
        finally:
            loop.close()
            
    except Exception as e:
        logger.error(f"Synthesis update failed for {synthesis_id}: {e}")
        return TaskResult(
            success=False,
            error=str(e),
            error_type=type(e).__name__
        ).to_dict()


async def _update_synthesis_async(synthesis_id: str, task) -> Dict[str, Any]:
    """Async implementation of synthesis update."""
    synthesis_repo = get_synthesis_repository()
    knowledge_repo = get_knowledge_repository()
    synthesis_generator = get_synthesis_generator()
    
    async with get_db_session() as db:
        # Load existing synthesis
        task.update_progress(1, 3, "Loading existing synthesis document...")
        synthesis_doc = await synthesis_repo.get(db, synthesis_id)
        
        if not synthesis_doc:
            raise ValueError(f"Synthesis document {synthesis_id} not found")
        
        # Load current knowledge items for the category
        task.update_progress(2, 3, "Loading current knowledge items...")
        # This would load knowledge items by category
        # For now, we'll assume we get them somehow
        current_knowledge_items = []  # TODO: Implement category-based query
        
        if not current_knowledge_items:
            return {
                "synthesis_id": synthesis_id,
                "updated": False,
                "message": "No knowledge items found for category"
            }
        
        # Update synthesis if needed
        task.update_progress(3, 3, "Updating synthesis document...", phase="ai_synthesis")
        update_result = await synthesis_generator.update_synthesis_if_stale(
            synthesis_doc, current_knowledge_items
        )
        
        if update_result:
            # Save updated synthesis
            updated_synthesis = await synthesis_repo.update(
                db, synthesis_id, update_result.synthesis_document.__dict__
            )
            
            return {
                "synthesis_id": synthesis_id,
                "updated": True,
                "title": updated_synthesis.title,
                "item_count": updated_synthesis.item_count,
                "generation_time": update_result.generation_stats.get("generation_duration")
            }
        else:
            return {
                "synthesis_id": synthesis_id,
                "updated": False,
                "message": "Synthesis is already up to date"
            }


@celery_app.task(bind=True, base=SynthesisTask, name="cleanup_old_synthesis")
def cleanup_old_synthesis(self, days_old: int = 30) -> Dict[str, Any]:
    """
    Clean up old synthesis documents that are no longer needed.
    
    Args:
        days_old: Number of days old for synthesis to be considered for cleanup
        
    Returns:
        Dict containing cleanup results
    """
    try:
        self.update_progress(0, 2, "Starting synthesis cleanup...")
        
        # Run async cleanup
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            result = loop.run_until_complete(
                _cleanup_synthesis_async(days_old, self)
            )
            
            return TaskResult(
                success=True,
                data=result
            ).to_dict()
            
        finally:
            loop.close()
            
    except Exception as e:
        logger.error(f"Synthesis cleanup failed: {e}")
        return TaskResult(
            success=False,
            error=str(e),
            error_type=type(e).__name__
        ).to_dict()


async def _cleanup_synthesis_async(days_old: int, task) -> Dict[str, Any]:
    """Async implementation of synthesis cleanup."""
    synthesis_repo = get_synthesis_repository()
    
    async with get_db_session() as db:
        # Find old synthesis documents
        task.update_progress(1, 2, f"Finding synthesis documents older than {days_old} days...")
        
        # This would query for old synthesis documents
        # For now, we'll return a placeholder result
        old_synthesis_count = 0  # TODO: Implement query for old synthesis
        
        task.update_progress(2, 2, "Cleanup completed")
        
        return {
            "days_old_threshold": days_old,
            "documents_cleaned": old_synthesis_count,
            "message": f"Cleaned up {old_synthesis_count} old synthesis documents"
        }