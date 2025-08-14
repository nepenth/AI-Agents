"""
AI processing tasks for content analysis and generation.
"""
import asyncio
import logging
from typing import Dict, Any, List, Optional
from celery import current_task
from datetime import datetime

from app.tasks.celery_app import celery_app
from app.database.connection import get_session_factory
from app.repositories.content import get_content_repository
from app.repositories.knowledge import get_knowledge_repository
from app.services.model_router import get_model_router
from app.services.model_settings import ModelPhase
from app.services.ai_service import get_ai_service
from app.services.xml_prompting_system import get_xml_prompting_system

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, name="ai_processing.analyze_media")
def analyze_media_task(self, content_id: str, force_reprocess: bool = False) -> Dict[str, Any]:
    """Analyze media content using vision models."""
    try:
        current_task.update_state(
            state='PROGRESS',
            meta={'current': 0, 'total': 3, 'status': f'Starting media analysis for {content_id}...'}
        )
        
        # Run async media analysis
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            result = loop.run_until_complete(_analyze_media_async(content_id, force_reprocess, self))
            return result
        finally:
            loop.close()
            
    except Exception as e:
        logger.error(f"Media analysis task failed for {content_id}: {e}")
        return {
            'status': 'failed',
            'content_id': content_id,
            'phase': 'media_analysis',
            'error': str(e)
        }


async def _analyze_media_async(content_id: str, force_reprocess: bool, task) -> Dict[str, Any]:
    """Async media analysis implementation."""
    session_factory = get_session_factory()
    
    async with session_factory() as db:
        content_repo = get_content_repository()
        content_item = await content_repo.get(db, content_id)
        
        if not content_item:
            raise ValueError(f"Content item {content_id} not found")
        
        # Check if already processed
        if content_item.media_analyzed and not force_reprocess:
            return {
                'status': 'skipped',
                'content_id': content_id,
                'phase': 'media_analysis',
                'message': 'Media already analyzed'
            }
        
        # Update progress
        task.update_state(
            state='PROGRESS',
            meta={'current': 1, 'total': 3, 'status': 'Analyzing media content...'}
        )
        
        # Check if content has media
        if not content_item.media_content:
            content_item.media_analyzed = True
            await content_repo.update(db, content_item)
            return {
                'status': 'completed',
                'content_id': content_id,
                'phase': 'media_analysis',
                'message': 'No media content to analyze'
            }
        
        try:
            # Get model router and XML prompting system
            model_router = get_model_router()
            xml_system = get_xml_prompting_system()
            
            # Resolve vision model
            backend, model, params = await model_router.resolve(ModelPhase.vision)
            
            # Analyze each media item
            media_analyses = []
            for media_item in content_item.media_content:
                # Generate XML prompt for media analysis
                prompt = xml_system.create_media_analysis_prompt(
                    media_url=media_item.get('url', ''),
                    media_type=media_item.get('type', 'unknown'),
                    tweet_context=content_item.content or '',
                    author_username=content_item.author_username or 'unknown'
                )
                
                # Analyze media (placeholder - will be implemented with actual AI service)
                analysis = f"Media analysis placeholder for {media_item.get('id', 'unknown')}"
                
                media_analyses.append({
                    'media_id': media_item.get('id'),
                    'analysis': analysis,
                    'model_used': model
                })
            
            # Update progress
            task.update_state(
                state='PROGRESS',
                meta={'current': 2, 'total': 3, 'status': 'Storing analysis results...'}
            )
            
            # Store results
            content_item.media_analysis_results = media_analyses
            content_item.vision_model_used = model
            content_item.media_analyzed = True
            await content_repo.update(db, content_item)
            
            # Final progress update
            task.update_state(
                state='PROGRESS',
                meta={'current': 3, 'total': 3, 'status': 'Complete'}
            )
            
            return {
                'status': 'completed',
                'content_id': content_id,
                'phase': 'media_analysis',
                'media_items_analyzed': len(media_analyses),
                'model_used': model,
                'message': f'Successfully analyzed {len(media_analyses)} media items'
            }
            
        except Exception as e:
            logger.error(f"Error during media analysis: {e}")
            raise


@celery_app.task(bind=True, name="ai_processing.generate_understanding")
def generate_understanding_task(self, content_id: str, force_reprocess: bool = False) -> Dict[str, Any]:
    """Generate collective understanding of content."""
    try:
        current_task.update_state(
            state='PROGRESS',
            meta={'current': 0, 'total': 3, 'status': f'Generating understanding for {content_id}...'}
        )
        
        # Run async understanding generation
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            result = loop.run_until_complete(_generate_understanding_async(content_id, force_reprocess, self))
            return result
        finally:
            loop.close()
            
    except Exception as e:
        logger.error(f"Understanding generation task failed for {content_id}: {e}")
        return {
            'status': 'failed',
            'content_id': content_id,
            'phase': 'understanding_generation',
            'error': str(e)
        }


async def _generate_understanding_async(content_id: str, force_reprocess: bool, task) -> Dict[str, Any]:
    """Async understanding generation implementation."""
    session_factory = get_session_factory()
    
    async with session_factory() as db:
        content_repo = get_content_repository()
        content_item = await content_repo.get(db, content_id)
        
        if not content_item:
            raise ValueError(f"Content item {content_id} not found")
        
        # Check if already processed
        if content_item.content_understood and not force_reprocess:
            return {
                'status': 'skipped',
                'content_id': content_id,
                'phase': 'understanding_generation',
                'message': 'Understanding already generated'
            }
        
        # Update progress
        task.update_state(
            state='PROGRESS',
            meta={'current': 1, 'total': 3, 'status': 'Generating content understanding...'}
        )
        
        try:
            # Get model router and XML prompting system
            model_router = get_model_router()
            xml_system = get_xml_prompting_system()
            
            # Resolve knowledge generation model
            backend, model, params = await model_router.resolve(ModelPhase.kb_generation)
            
            # Extract media analysis if available
            media_analysis = None
            if content_item.media_analysis_results:
                media_analysis = "\n".join([
                    result.get('analysis', '') for result in content_item.media_analysis_results
                ])
            
            # Generate understanding prompt
            prompt = xml_system.create_content_understanding_prompt(
                tweet_content=content_item.content or '',
                author_username=content_item.author_username or 'unknown',
                media_analysis=media_analysis
            )
            
            # Generate understanding (placeholder - will be implemented with actual AI service)
            understanding = f"Content understanding placeholder for {content_id}"
            
            # Update progress
            task.update_state(
                state='PROGRESS',
                meta={'current': 2, 'total': 3, 'status': 'Storing understanding...'}
            )
            
            # Store results
            content_item.collective_understanding = understanding
            content_item.understanding_model_used = model
            content_item.content_understood = True
            content_item.has_collective_understanding = True
            await content_repo.update(db, content_item)
            
            # Final progress update
            task.update_state(
                state='PROGRESS',
                meta={'current': 3, 'total': 3, 'status': 'Complete'}
            )
            
            return {
                'status': 'completed',
                'content_id': content_id,
                'phase': 'understanding_generation',
                'model_used': model,
                'message': 'Content understanding generated successfully'
            }
            
        except Exception as e:
            logger.error(f"Error during understanding generation: {e}")
            raise


@celery_app.task(bind=True, name="ai_processing.categorize_content")
def categorize_content_task(self, content_id: str, force_reprocess: bool = False) -> Dict[str, Any]:
    """Categorize content using AI."""
    try:
        current_task.update_state(
            state='PROGRESS',
            meta={'current': 0, 'total': 3, 'status': f'Categorizing content {content_id}...'}
        )
        
        # Run async categorization
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            result = loop.run_until_complete(_categorize_content_async(content_id, force_reprocess, self))
            return result
        finally:
            loop.close()
            
    except Exception as e:
        logger.error(f"Content categorization task failed for {content_id}: {e}")
        return {
            'status': 'failed',
            'content_id': content_id,
            'phase': 'content_categorization',
            'error': str(e)
        }


async def _categorize_content_async(content_id: str, force_reprocess: bool, task) -> Dict[str, Any]:
    """Async content categorization implementation."""
    session_factory = get_session_factory()
    
    async with session_factory() as db:
        content_repo = get_content_repository()
        content_item = await content_repo.get(db, content_id)
        
        if not content_item:
            raise ValueError(f"Content item {content_id} not found")
        
        # Check if already processed
        if content_item.categorized and not force_reprocess:
            return {
                'status': 'skipped',
                'content_id': content_id,
                'phase': 'content_categorization',
                'message': 'Content already categorized'
            }
        
        # Update progress
        task.update_state(
            state='PROGRESS',
            meta={'current': 1, 'total': 3, 'status': 'Categorizing content...'}
        )
        
        try:
            # Get model router and XML prompting system
            model_router = get_model_router()
            xml_system = get_xml_prompting_system()
            
            # Resolve knowledge generation model
            backend, model, params = await model_router.resolve(ModelPhase.kb_generation)
            
            # Get existing categories (placeholder)
            existing_categories = ["ai", "ml", "tech", "programming", "data-science"]
            
            # Generate categorization prompt
            prompt = xml_system.create_categorization_prompt(
                content=content_item.content or '',
                collective_understanding=content_item.collective_understanding or '',
                existing_categories=existing_categories
            )
            
            # Generate categorization (placeholder - will be implemented with actual AI service)
            category = "tech"  # Placeholder
            sub_category = "ai"  # Placeholder
            
            # Update progress
            task.update_state(
                state='PROGRESS',
                meta={'current': 2, 'total': 3, 'status': 'Storing categorization...'}
            )
            
            # Store results
            content_item.main_category = category
            content_item.sub_category = sub_category
            content_item.categorization_model_used = model
            content_item.categorized = True
            await content_repo.update(db, content_item)
            
            # Final progress update
            task.update_state(
                state='PROGRESS',
                meta={'current': 3, 'total': 3, 'status': 'Complete'}
            )
            
            return {
                'status': 'completed',
                'content_id': content_id,
                'phase': 'content_categorization',
                'main_category': category,
                'sub_category': sub_category,
                'model_used': model,
                'message': f'Content categorized as {category}/{sub_category}'
            }
            
        except Exception as e:
            logger.error(f"Error during content categorization: {e}")
            raise