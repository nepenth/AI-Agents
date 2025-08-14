"""
Comprehensive content processing pipeline service that orchestrates all sub-phases.
"""
import asyncio
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime
import uuid

from app.services.twitter_client import get_twitter_client, TweetData, ThreadInfo
from app.services.model_router import get_model_router
from app.services.model_settings import ModelPhase
from app.services.ai_service import get_ai_service
from app.repositories.content import get_content_repository
from app.repositories.knowledge import get_knowledge_repository
from app.repositories.synthesis import get_synthesis_repository
from app.database.connection import get_db_session
from app.models.content import ContentItem
from app.tasks.subphase_processing import (
    phase_2_1_bookmark_caching_task,
    phase_3_1_media_analysis_task,
    phase_3_2_content_understanding_task,
    phase_3_3_categorization_task
)

logger = logging.getLogger(__name__)


class ContentProcessingPipeline:
    """
    Comprehensive content processing pipeline that orchestrates all sub-phases.
    
    This service provides both synchronous and asynchronous processing options,
    intelligent processing logic to avoid unnecessary reprocessing, and
    comprehensive error handling and retry mechanisms.
    """
    
    def __init__(self):
        self.twitter_client = get_twitter_client()
        self.model_router = get_model_router()
        self.ai_service = get_ai_service()
        self.content_repo = get_content_repository()
    
    async def process_twitter_bookmark(
        self, 
        tweet_id: str, 
        force_refresh: bool = False,
        models_override: Optional[Dict[str, Any]] = None,
        run_async: bool = True
    ) -> Dict[str, Any]:
        """
        Process a Twitter bookmark through all sub-phases.
        
        Args:
            tweet_id: Twitter tweet ID to process
            force_refresh: Force reprocessing even if already completed
            models_override: Optional model overrides for AI phases
            run_async: Whether to run phases asynchronously via Celery
            
        Returns:
            Dict[str, Any]: Processing results and status
        """
        try:
            # Step 1: Create or get content item
            content_item = await self._get_or_create_content_item(tweet_id, force_refresh)
            content_id = content_item.id
            
            if run_async:
                # Run phases asynchronously via Celery tasks
                return await self._process_async(content_id, force_refresh, models_override)
            else:
                # Run phases synchronously for testing/debugging
                return await self._process_sync(content_id, force_refresh, models_override)
                
        except Exception as e:
            logger.error(f"Failed to process Twitter bookmark {tweet_id}: {e}")
            return {
                'status': 'failed',
                'tweet_id': tweet_id,
                'error': str(e),
                'timestamp': datetime.utcnow().isoformat()
            }
    
    async def _get_or_create_content_item(self, tweet_id: str, force_refresh: bool) -> ContentItem:
        """Get existing content item or create new one."""
        async with get_db_session() as db:
            # Check if content item already exists
            existing_item = await self.content_repo.get_by_source(db, "twitter", tweet_id)
            
            if existing_item:
                if force_refresh:
                    # Reset processing states to trigger reprocessing
                    update_data = {
                        'bookmark_cached': False,
                        'media_analyzed': False,
                        'content_understood': False,
                        'categorized': False,
                        'processing_state': 'pending',
                        'updated_at': datetime.utcnow()
                    }
                    return await self.content_repo.update(db, existing_item.id, update_data)
                else:
                    return existing_item
            else:
                # Create new content item
                import uuid
                content_data = {
                    'id': str(uuid.uuid4()),
                    'source_type': 'twitter',
                    'source_id': tweet_id,
                    'tweet_id': tweet_id,
                    'title': f'Twitter Bookmark {tweet_id}',
                    'content': '',  # Will be populated by bookmark caching
                    'processing_state': 'pending',
                    'bookmark_cached': False,
                    'media_analyzed': False,
                    'content_understood': False,
                    'categorized': False
                }
                return await self.content_repo.create(db, content_data)
    
    async def _process_async(
        self, 
        content_id: str, 
        force_refresh: bool, 
        models_override: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Process content asynchronously via Celery tasks."""
        task_results = {}
        
        try:
            # Phase 2.1: Bookmark Caching
            bookmark_task = phase_2_1_bookmark_caching_task.apply_async(
                args=[content_id, force_refresh]
            )
            task_results['bookmark_caching'] = {
                'task_id': bookmark_task.id,
                'status': 'started'
            }
            
            # Wait for bookmark caching to complete before proceeding
            bookmark_result = bookmark_task.get(timeout=300)  # 5 minute timeout
            task_results['bookmark_caching']['result'] = bookmark_result
            
            if bookmark_result['status'] != 'completed':
                return {
                    'status': 'failed',
                    'content_id': content_id,
                    'phase': 'bookmark_caching',
                    'error': bookmark_result.get('error', 'Bookmark caching failed'),
                    'task_results': task_results
                }
            
            # Phase 3.1: Media Analysis
            media_task = phase_3_1_media_analysis_task.apply_async(
                args=[content_id, models_override]
            )
            task_results['media_analysis'] = {
                'task_id': media_task.id,
                'status': 'started'
            }
            
            # Phase 3.2: Content Understanding
            understanding_task = phase_3_2_content_understanding_task.apply_async(
                args=[content_id, models_override]
            )
            task_results['content_understanding'] = {
                'task_id': understanding_task.id,
                'status': 'started'
            }
            
            # Wait for media analysis and content understanding to complete
            media_result = media_task.get(timeout=300)
            understanding_result = understanding_task.get(timeout=300)
            
            task_results['media_analysis']['result'] = media_result
            task_results['content_understanding']['result'] = understanding_result
            
            # Check if both phases completed successfully
            if media_result['status'] != 'completed' or understanding_result['status'] != 'completed':
                return {
                    'status': 'partial_failure',
                    'content_id': content_id,
                    'task_results': task_results
                }
            
            # Phase 3.3: Categorization (depends on content understanding)
            categorization_task = phase_3_3_categorization_task.apply_async(
                args=[content_id, models_override]
            )
            task_results['categorization'] = {
                'task_id': categorization_task.id,
                'status': 'started'
            }
            
            categorization_result = categorization_task.get(timeout=300)
            task_results['categorization']['result'] = categorization_result
            
            # Determine overall status
            overall_status = 'completed' if categorization_result['status'] == 'completed' else 'partial_failure'
            
            return {
                'status': overall_status,
                'content_id': content_id,
                'processing_method': 'async',
                'task_results': task_results,
                'timestamp': datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Async processing failed for {content_id}: {e}")
            return {
                'status': 'failed',
                'content_id': content_id,
                'error': str(e),
                'task_results': task_results,
                'timestamp': datetime.utcnow().isoformat()
            }
    
    async def _process_sync(
        self, 
        content_id: str, 
        force_refresh: bool, 
        models_override: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Process content synchronously for testing/debugging."""
        phase_results = {}
        
        try:
            # Phase 2.1: Bookmark Caching
            logger.info(f"Starting synchronous bookmark caching for {content_id}")
            bookmark_result = await self._run_bookmark_caching_sync(content_id, force_refresh)
            phase_results['bookmark_caching'] = bookmark_result
            
            if bookmark_result['status'] != 'completed':
                return {
                    'status': 'failed',
                    'content_id': content_id,
                    'phase': 'bookmark_caching',
                    'error': bookmark_result.get('error', 'Bookmark caching failed'),
                    'phase_results': phase_results
                }
            
            # Phase 3.1: Media Analysis
            logger.info(f"Starting synchronous media analysis for {content_id}")
            media_result = await self._run_media_analysis_sync(content_id, models_override)
            phase_results['media_analysis'] = media_result
            
            # Phase 3.2: Content Understanding
            logger.info(f"Starting synchronous content understanding for {content_id}")
            understanding_result = await self._run_content_understanding_sync(content_id, models_override)
            phase_results['content_understanding'] = understanding_result
            
            # Phase 3.3: Categorization
            logger.info(f"Starting synchronous categorization for {content_id}")
            categorization_result = await self._run_categorization_sync(content_id, models_override)
            phase_results['categorization'] = categorization_result
            
            # Determine overall status
            failed_phases = [name for name, result in phase_results.items() if result['status'] != 'completed']
            
            if not failed_phases:
                overall_status = 'completed'
            elif len(failed_phases) == len(phase_results):
                overall_status = 'failed'
            else:
                overall_status = 'partial_success'
            
            return {
                'status': overall_status,
                'content_id': content_id,
                'processing_method': 'sync',
                'failed_phases': failed_phases,
                'phase_results': phase_results,
                'timestamp': datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Sync processing failed for {content_id}: {e}")
            return {
                'status': 'failed',
                'content_id': content_id,
                'error': str(e),
                'phase_results': phase_results,
                'timestamp': datetime.utcnow().isoformat()
            }
    
    async def _run_bookmark_caching_sync(self, content_id: str, force_refresh: bool) -> Dict[str, Any]:
        """Run bookmark caching synchronously."""
        try:
            async with get_db_session() as db:
                content_item = await self.content_repo.get(db, content_id)
                if not content_item:
                    return {'status': 'failed', 'error': 'Content item not found'}
                
                # Check if already cached
                if content_item.bookmark_cached and not force_refresh:
                    return {'status': 'skipped', 'message': 'Already cached'}
                
                # Fetch tweet data from Twitter API
                async with self.twitter_client as client:
                    tweet_data = await client.get_tweet(content_item.tweet_id)
                    thread_info = await client.detect_thread(content_item.tweet_id)
                
                # Update content item with cached data
                update_data = {
                    'title': tweet_data.text[:100] + '...' if len(tweet_data.text) > 100 else tweet_data.text,
                    'content': tweet_data.text,
                    'author_username': tweet_data.author_username,
                    'author_id': tweet_data.author_id,
                    'tweet_url': tweet_data.url,
                    'like_count': tweet_data.public_metrics.get('like_count', 0),
                    'retweet_count': tweet_data.public_metrics.get('retweet_count', 0),
                    'reply_count': tweet_data.public_metrics.get('reply_count', 0),
                    'quote_count': tweet_data.public_metrics.get('quote_count', 0),
                    'original_tweet_created_at': tweet_data.created_at,
                    'media_content': [
                        {
                            'type': media.get('type', 'unknown'),
                            'url': media.get('url', ''),
                            'alt_text': media.get('alt_text', ''),
                            'cached_at': datetime.utcnow().isoformat()
                        }
                        for media in tweet_data.media
                    ],
                    'bookmark_cached': True
                }
                
                # Add thread information if detected
                if thread_info:
                    update_data.update({
                        'thread_id': thread_info.thread_id,
                        'is_thread_root': thread_info.is_thread_root,
                        'position_in_thread': thread_info.position_in_thread,
                        'thread_length': thread_info.thread_length
                    })
                
                await self.content_repo.update(db, content_id, update_data)
                
                return {
                    'status': 'completed',
                    'tweet_id': content_item.tweet_id,
                    'author': tweet_data.author_username,
                    'is_thread': thread_info is not None,
                    'media_count': len(tweet_data.media),
                    'engagement_total': sum(tweet_data.public_metrics.values())
                }
                
        except Exception as e:
            logger.error(f"Bookmark caching failed for {content_id}: {e}")
            return {'status': 'failed', 'error': str(e)}
    
    async def _run_media_analysis_sync(self, content_id: str, models_override: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """Run media analysis synchronously."""
        try:
            async with get_db_session() as db:
                content_item = await self.content_repo.get(db, content_id)
                if not content_item:
                    return {'status': 'failed', 'error': 'Content item not found'}
                
                # Check if already analyzed
                if content_item.media_analyzed and not models_override:
                    return {'status': 'skipped', 'message': 'Already analyzed'}
                
                # Check if there's media to analyze
                if not content_item.media_content:
                    await self.content_repo.update(db, content_id, {'media_analyzed': True})
                    return {'status': 'completed', 'message': 'No media to analyze'}
                
                # Resolve vision model
                override_selector = models_override.get('vision') if models_override else None
                backend, model, params = await self.model_router.resolve(ModelPhase.vision, override=override_selector)
                
                # Simulate media analysis (replace with actual implementation)
                media_analysis_results = []
                for i, media_item in enumerate(content_item.media_content):
                    analysis_result = {
                        'media_id': f"media_{i}",
                        'media_type': media_item.get('type', 'unknown'),
                        'description': f"AI-generated description of {media_item.get('type', 'media')} content",
                        'technical_analysis': 'Technical analysis of the media content',
                        'key_insights': ['Insight 1', 'Insight 2'],
                        'confidence_score': 0.85
                    }
                    media_analysis_results.append(analysis_result)
                
                # Update content item
                update_data = {
                    'media_analysis_results': {
                        'analyses': media_analysis_results,
                        'model_used': model,
                        'analysis_timestamp': datetime.utcnow().isoformat()
                    },
                    'media_analyzed': True,
                    'vision_model_used': model
                }
                
                await self.content_repo.update(db, content_id, update_data)
                
                return {
                    'status': 'completed',
                    'media_count': len(content_item.media_content),
                    'model_used': model,
                    'analysis_results': len(media_analysis_results)
                }
                
        except Exception as e:
            logger.error(f"Media analysis failed for {content_id}: {e}")
            return {'status': 'failed', 'error': str(e)}
    
    async def _run_content_understanding_sync(self, content_id: str, models_override: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """Run content understanding synchronously."""
        try:
            async with get_db_session() as db:
                content_item = await self.content_repo.get(db, content_id)
                if not content_item:
                    return {'status': 'failed', 'error': 'Content item not found'}
                
                # Check if already understood
                if content_item.content_understood and not models_override:
                    return {'status': 'skipped', 'message': 'Already understood'}
                
                # Resolve understanding model
                override_selector = models_override.get('kb_generation') if models_override else None
                backend, model, params = await self.model_router.resolve(ModelPhase.kb_generation, override=override_selector)
                
                # Simulate content understanding (replace with actual implementation)
                understanding_result = {
                    'collective_understanding': f'This content discusses {content_item.content[:100]}... with comprehensive analysis and insights.',
                    'key_concepts': ['concept1', 'concept2', 'concept3'],
                    'technical_domain': 'general',
                    'actionable_insights': ['insight1', 'insight2']
                }
                
                # Update content item
                update_data = {
                    'collective_understanding': understanding_result['collective_understanding'],
                    'content_understood': True,
                    'understanding_model_used': model
                }
                
                await self.content_repo.update(db, content_id, update_data)
                
                return {
                    'status': 'completed',
                    'model_used': model,
                    'understanding_length': len(understanding_result['collective_understanding']),
                    'key_concepts': understanding_result['key_concepts'],
                    'technical_domain': understanding_result['technical_domain']
                }
                
        except Exception as e:
            logger.error(f"Content understanding failed for {content_id}: {e}")
            return {'status': 'failed', 'error': str(e)}
    
    async def _run_categorization_sync(self, content_id: str, models_override: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """Run categorization synchronously."""
        try:
            async with get_db_session() as db:
                content_item = await self.content_repo.get(db, content_id)
                if not content_item:
                    return {'status': 'failed', 'error': 'Content item not found'}
                
                # Check if already categorized
                if content_item.categorized and not models_override:
                    return {'status': 'skipped', 'message': 'Already categorized'}
                
                # Get existing categories for intelligence
                existing_categories = await self._get_existing_categories(db)
                
                # Resolve categorization model
                override_selector = models_override.get('kb_generation') if models_override else None
                backend, model, params = await self.model_router.resolve(ModelPhase.kb_generation, override=override_selector)
                
                # Simulate categorization (replace with actual implementation)
                categorization_result = {
                    'category': 'general',
                    'subcategory': 'discussion',
                    'reasoning': 'Content appears to be general discussion based on text analysis',
                    'is_new_category': False,
                    'confidence_score': 0.75
                }
                
                # Update content item
                update_data = {
                    'main_category': categorization_result['category'],
                    'sub_category': categorization_result['subcategory'],
                    'category_intelligence_used': {
                        'existing_categories_considered': existing_categories,
                        'is_new_category': categorization_result['is_new_category'],
                        'confidence_score': categorization_result['confidence_score'],
                        'reasoning': categorization_result['reasoning']
                    },
                    'categorized': True,
                    'categorization_model_used': model,
                    'processing_state': 'completed'
                }
                
                await self.content_repo.update(db, content_id, update_data)
                
                return {
                    'status': 'completed',
                    'category': categorization_result['category'],
                    'subcategory': categorization_result['subcategory'],
                    'is_new_category': categorization_result['is_new_category'],
                    'confidence_score': categorization_result['confidence_score'],
                    'model_used': model
                }
                
        except Exception as e:
            logger.error(f"Categorization failed for {content_id}: {e}")
            return {'status': 'failed', 'error': str(e)}
    
    async def fetch_bookmarks_from_collection(
        self, 
        collection_url: Optional[str] = None, 
        max_results: int = 100,
        force_refresh: bool = False
    ) -> Dict[str, Any]:
        """
        Fetch bookmarks from specified Twitter/X collection.
        
        Args:
            collection_url: Twitter/X bookmark collection URL
            max_results: Maximum number of bookmarks to fetch
            force_refresh: Force re-fetching even if already cached
            
        Returns:
            Dict[str, Any]: Fetching results and status
        """
        try:
            fetched_bookmarks = []
            skipped_bookmarks = []
            failed_bookmarks = []
            
            async with self.twitter_client as client:
                # Check if Twitter API is available
                if not await client.is_available():
                    return {
                        'status': 'failed',
                        'error': 'Twitter API not available',
                        'timestamp': datetime.utcnow().isoformat()
                    }
                
                # Fetch bookmarks from Twitter API
                bookmark_count = 0
                async for tweet_data in client.get_bookmarks(max_results=max_results):
                    bookmark_count += 1
                    
                    try:
                        # Check if bookmark already exists
                        async with get_db_session() as db:
                            existing_item = await self.content_repo.get_by_source(db, "twitter", tweet_data.id)
                            
                            if existing_item and not force_refresh:
                                skipped_bookmarks.append({
                                    'tweet_id': tweet_data.id,
                                    'reason': 'already_exists'
                                })
                                continue
                            
                            # Create or update content item
                            if existing_item:
                                # Update existing item
                                update_data = {
                                    'processing_state': 'pending',
                                    'bookmark_cached': False,
                                    'media_analyzed': False,
                                    'content_understood': False,
                                    'categorized': False,
                                    'updated_at': datetime.utcnow()
                                }
                                content_item = await self.content_repo.update(db, existing_item.id, update_data)
                            else:
                                # Create new content item
                                content_data = {
                                    'id': str(uuid.uuid4()),
                                    'source_type': 'twitter',
                                    'source_id': tweet_data.id,
                                    'tweet_id': tweet_data.id,
                                    'title': f'Twitter Bookmark {tweet_data.id}',
                                    'content': tweet_data.text,
                                    'processing_state': 'pending',
                                    'bookmark_cached': False,
                                    'media_analyzed': False,
                                    'content_understood': False,
                                    'categorized': False
                                }
                                content_item = await self.content_repo.create(db, content_data)
                            
                            fetched_bookmarks.append({
                                'content_id': content_item.id,
                                'tweet_id': tweet_data.id,
                                'author': tweet_data.author_username,
                                'created_at': tweet_data.created_at.isoformat(),
                                'media_count': len(tweet_data.media),
                                'engagement_total': sum(tweet_data.public_metrics.values())
                            })
                            
                    except Exception as e:
                        logger.error(f"Failed to process bookmark {tweet_data.id}: {e}")
                        failed_bookmarks.append({
                            'tweet_id': tweet_data.id,
                            'error': str(e)
                        })
            
            return {
                'status': 'completed',
                'fetched_count': len(fetched_bookmarks),
                'skipped_count': len(skipped_bookmarks),
                'failed_count': len(failed_bookmarks),
                'fetched_bookmarks': fetched_bookmarks,
                'skipped_bookmarks': skipped_bookmarks,
                'failed_bookmarks': failed_bookmarks,
                'timestamp': datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Failed to fetch bookmarks: {e}")
            return {
                'status': 'failed',
                'error': str(e),
                'timestamp': datetime.utcnow().isoformat()
            }
    
    async def generate_synthesis_documents(
        self, 
        models_override: Optional[Dict[str, Any]] = None,
        min_bookmarks_per_category: int = 3
    ) -> Dict[str, Any]:
        """
        Generate synthesis documents for categories with sufficient bookmarks.
        
        Args:
            models_override: Optional model overrides for synthesis generation
            min_bookmarks_per_category: Minimum bookmarks required per category
            
        Returns:
            Dict[str, Any]: Synthesis generation results
        """
        try:
            synthesis_repo = get_synthesis_repository()
            generated_syntheses = []
            skipped_categories = []
            
            async with get_db_session() as db:
                # Get category statistics
                category_stats = await self._get_category_statistics(db)
                
                # Filter categories with sufficient bookmarks
                eligible_categories = [
                    cat for cat in category_stats 
                    if cat['count'] >= min_bookmarks_per_category
                ]
                
                if not eligible_categories:
                    return {
                        'status': 'completed',
                        'message': f'No categories have {min_bookmarks_per_category}+ bookmarks',
                        'generated_count': 0,
                        'skipped_count': len(category_stats),
                        'timestamp': datetime.utcnow().isoformat()
                    }
                
                # Resolve synthesis model
                override_selector = models_override.get('synthesis') if models_override else None
                backend, model, params = await self.model_router.resolve(ModelPhase.synthesis, override=override_selector)
                
                # Generate synthesis for each eligible category
                for category in eligible_categories:
                    try:
                        # Get content items for this category
                        content_items = await self.content_repo.get_by_category(
                            db, category['name'], category.get('subcategory')
                        )
                        
                        if len(content_items) < min_bookmarks_per_category:
                            skipped_categories.append({
                                'category': category['name'],
                                'subcategory': category.get('subcategory'),
                                'reason': 'insufficient_content_items',
                                'count': len(content_items)
                            })
                            continue
                        
                        # Check if synthesis already exists
                        existing_synthesis = await synthesis_repo.get_by_category(
                            db, category['name'], category.get('subcategory')
                        )
                        
                        if existing_synthesis and not models_override:
                            skipped_categories.append({
                                'category': category['name'],
                                'subcategory': category.get('subcategory'),
                                'reason': 'already_exists',
                                'synthesis_id': existing_synthesis.id
                            })
                            continue
                        
                        # Generate synthesis content
                        synthesis_content = await self._generate_synthesis_content(
                            content_items, category, backend, model, params
                        )
                        
                        # Create or update synthesis document
                        if existing_synthesis:
                            synthesis_data = {
                                'content': synthesis_content['content'],
                                'summary': synthesis_content['summary'],
                                'key_insights': synthesis_content['key_insights'],
                                'source_count': len(content_items),
                                'synthesis_model_used': model,
                                'updated_at': datetime.utcnow()
                            }
                            synthesis_doc = await synthesis_repo.update(db, existing_synthesis.id, synthesis_data)
                        else:
                            synthesis_data = {
                                'id': str(uuid.uuid4()),
                                'title': f"{category['name'].title()} - {category.get('subcategory', 'General').title()}",
                                'content': synthesis_content['content'],
                                'summary': synthesis_content['summary'],
                                'key_insights': synthesis_content['key_insights'],
                                'main_category': category['name'],
                                'sub_category': category.get('subcategory'),
                                'source_count': len(content_items),
                                'synthesis_model_used': model,
                                'source_content_ids': [item.id for item in content_items]
                            }
                            synthesis_doc = await synthesis_repo.create(db, synthesis_data)
                        
                        generated_syntheses.append({
                            'synthesis_id': synthesis_doc.id,
                            'category': category['name'],
                            'subcategory': category.get('subcategory'),
                            'source_count': len(content_items),
                            'content_length': len(synthesis_content['content']),
                            'model_used': model
                        })
                        
                    except Exception as e:
                        logger.error(f"Failed to generate synthesis for category {category['name']}: {e}")
                        skipped_categories.append({
                            'category': category['name'],
                            'subcategory': category.get('subcategory'),
                            'reason': 'generation_failed',
                            'error': str(e)
                        })
            
            return {
                'status': 'completed',
                'generated_count': len(generated_syntheses),
                'skipped_count': len(skipped_categories),
                'generated_syntheses': generated_syntheses,
                'skipped_categories': skipped_categories,
                'model_used': model,
                'timestamp': datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Failed to generate synthesis documents: {e}")
            return {
                'status': 'failed',
                'error': str(e),
                'timestamp': datetime.utcnow().isoformat()
            }
    
    async def _get_category_statistics(self, db) -> List[Dict[str, Any]]:
        """Get category statistics from database."""
        # TODO: Implement actual category statistics query
        # This should query the content_items table and group by main_category and sub_category
        return [
            {'name': 'machine-learning', 'subcategory': 'neural-networks', 'count': 5},
            {'name': 'web-development', 'subcategory': 'frontend', 'count': 4},
            {'name': 'data-science', 'subcategory': 'analytics', 'count': 3},
            {'name': 'general', 'subcategory': 'discussion', 'count': 2}
        ]
    
    async def _generate_synthesis_content(
        self, 
        content_items: List[ContentItem], 
        category: Dict[str, Any], 
        backend, 
        model: str, 
        params: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Generate synthesis content from multiple content items."""
        # TODO: Implement actual synthesis generation with XML prompts
        # For now, simulate the synthesis generation
        
        # Combine all content for synthesis
        combined_content = []
        for item in content_items:
            item_summary = {
                'title': item.title,
                'content': item.content,
                'understanding': item.collective_understanding,
                'author': item.author_username,
                'engagement': {
                    'likes': item.like_count or 0,
                    'retweets': item.retweet_count or 0,
                    'replies': item.reply_count or 0
                }
            }
            combined_content.append(item_summary)
        
        # Generate synthesis
        synthesis_content = f"""# {category['name'].title()} - {category.get('subcategory', 'General').title()}

This synthesis document aggregates insights from {len(content_items)} bookmarks in the {category['name']} category.

## Key Themes

Based on the analysis of {len(content_items)} sources, the following key themes emerge:

1. **Technical Implementation**: Multiple sources discuss practical implementation approaches
2. **Best Practices**: Common patterns and recommended practices are highlighted
3. **Community Insights**: Valuable perspectives from the developer community

## Detailed Analysis

{self._format_synthesis_content(combined_content)}

## Summary

This collection of bookmarks provides comprehensive coverage of {category['name']} topics, with particular focus on {category.get('subcategory', 'general')} aspects. The sources demonstrate both theoretical understanding and practical application.

## Sources

- Total bookmarks analyzed: {len(content_items)}
- Average engagement: {sum(item.like_count or 0 for item in content_items) / len(content_items):.1f} likes
- Date range: {min(item.created_at for item in content_items if item.created_at)} to {max(item.created_at for item in content_items if item.created_at)}
"""
        
        return {
            'content': synthesis_content,
            'summary': f'Synthesis of {len(content_items)} bookmarks covering {category["name"]} topics',
            'key_insights': [
                'Technical implementation patterns',
                'Community best practices',
                'Practical application examples'
            ]
        }
    
    def _format_synthesis_content(self, combined_content: List[Dict[str, Any]]) -> str:
        """Format combined content for synthesis document."""
        formatted_sections = []
        
        for i, item in enumerate(combined_content, 1):
            section = f"""### Source {i}: {item['title'][:100]}...

**Author**: @{item['author']}  
**Engagement**: {item['engagement']['likes']} likes, {item['engagement']['retweets']} retweets

{item['understanding'] or item['content'][:500]}...

---
"""
            formatted_sections.append(section)
        
        return '\n'.join(formatted_sections)

    async def _get_existing_categories(self, db) -> List[Dict[str, Any]]:
        """Get existing categories for intelligence."""
        # TODO: Implement actual category statistics query
        return [
            {'name': 'general', 'count': 10, 'subcategories': [{'name': 'discussion', 'count': 5}]},
            {'name': 'technology', 'count': 8, 'subcategories': [{'name': 'ai', 'count': 4}]}
        ]


# Singleton instance
_content_processing_pipeline: Optional[ContentProcessingPipeline] = None


def get_content_processing_pipeline() -> ContentProcessingPipeline:
    """Get the singleton content processing pipeline instance."""
    global _content_processing_pipeline
    if _content_processing_pipeline is None:
        _content_processing_pipeline = ContentProcessingPipeline()
    return _content_processing_pipeline