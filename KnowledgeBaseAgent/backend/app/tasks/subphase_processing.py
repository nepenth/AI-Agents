"""
Celery tasks for sub-phase processing in the seven-phase pipeline.
"""
import asyncio
import logging
from typing import Dict, Any, List, Optional
from celery import current_task
from datetime import datetime

from app.tasks.celery_app import celery_app
from app.database.connection import get_db_session
from app.repositories.content import get_content_repository
from app.services.model_router import get_model_router
from app.services.model_settings import ModelPhase
from app.services.ai_service import get_ai_service

logger = logging.getLogger(__name__)


@celery_app.task(bind=True)
def phase_2_1_bookmark_caching_task(self, content_id: str, force_refresh: bool = False) -> Dict[str, Any]:
    """Phase 2.1: Cache bookmark content, detect threads, and store media."""
    try:
        current_task.update_state(
            state='PROGRESS',
            meta={'current': 0, 'total': 4, 'status': f'Starting bookmark caching for {content_id}...'}
        )
        
        # Run async bookmark caching
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            result = loop.run_until_complete(_bookmark_caching_async(content_id, force_refresh, self))
            return result
        finally:
            loop.close()
            
    except Exception as e:
        logger.error(f"Bookmark caching task failed for {content_id}: {e}")
        return {
            'status': 'failed',
            'content_id': content_id,
            'phase': 'bookmark_caching',
            'error': str(e)
        }


async def _bookmark_caching_async(content_id: str, force_refresh: bool, task) -> Dict[str, Any]:
    """Async bookmark caching implementation."""
    content_repo = get_content_repository()
    
    async with get_db_session() as db:
        # Step 1: Load content item
        task.update_state(
            state='PROGRESS',
            meta={'current': 1, 'total': 4, 'status': 'Loading content item...'}
        )
        
        content_item = await content_repo.get(db, content_id)
        if not content_item:
            raise ValueError(f"Content item {content_id} not found")
        
        # Check if already cached and not forcing refresh
        if content_item.bookmark_cached and not force_refresh:
            return {
                'status': 'skipped',
                'content_id': content_id,
                'phase': 'bookmark_caching',
                'message': 'Bookmark already cached, use force_refresh=true to re-cache'
            }
        
        # Step 2: Fetch tweet data from Twitter/X API
        task.update_state(
            state='PROGRESS',
            meta={'current': 2, 'total': 4, 'status': 'Fetching tweet data from Twitter/X API...'}
        )
        
        # TODO: Implement actual Twitter/X API integration
        # For now, simulate the data fetching
        tweet_data = await _simulate_twitter_api_fetch(content_item.tweet_id)
        
        # Step 3: Detect thread and cache media
        task.update_state(
            state='PROGRESS',
            meta={'current': 3, 'total': 4, 'status': 'Detecting thread and caching media...'}
        )
        
        thread_info = await _detect_thread(tweet_data)
        media_content = await _cache_media_content(tweet_data.get('media', []))
        
        # Step 4: Update content item with cached data
        task.update_state(
            state='PROGRESS',
            meta={'current': 4, 'total': 4, 'status': 'Updating content item...'}
        )
        
        update_data = {
            'title': tweet_data.get('text', '')[:100] + '...' if len(tweet_data.get('text', '')) > 100 else tweet_data.get('text', ''),
            'content': tweet_data.get('text', ''),
            'author_username': tweet_data.get('author_username'),
            'author_id': tweet_data.get('author_id'),
            'tweet_url': tweet_data.get('url'),
            'like_count': tweet_data.get('public_metrics', {}).get('like_count', 0),
            'retweet_count': tweet_data.get('public_metrics', {}).get('retweet_count', 0),
            'reply_count': tweet_data.get('public_metrics', {}).get('reply_count', 0),
            'quote_count': tweet_data.get('public_metrics', {}).get('quote_count', 0),
            'original_tweet_created_at': datetime.fromisoformat(tweet_data.get('created_at', datetime.utcnow().isoformat())),
            'media_content': media_content,
            'bookmark_cached': True,
            **thread_info
        }
        
        updated_item = await content_repo.update(db, content_id, update_data)
    
    return {
        'status': 'completed',
        'content_id': content_id,
        'phase': 'bookmark_caching',
        'tweet_id': content_item.tweet_id,
        'author_username': tweet_data.get('author_username'),
        'is_thread': thread_info.get('thread_id') is not None,
        'thread_length': thread_info.get('thread_length', 1),
        'media_count': len(media_content),
        'engagement_total': sum([
            tweet_data.get('public_metrics', {}).get('like_count', 0),
            tweet_data.get('public_metrics', {}).get('retweet_count', 0),
            tweet_data.get('public_metrics', {}).get('reply_count', 0),
            tweet_data.get('public_metrics', {}).get('quote_count', 0)
        ]),
        'message': f'Successfully cached bookmark for tweet {content_item.tweet_id}'
    }


@celery_app.task(bind=True)
def phase_3_1_media_analysis_task(self, content_id: str, models_override: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Phase 3.1: Analyze media content using vision models."""
    try:
        current_task.update_state(
            state='PROGRESS',
            meta={'current': 0, 'total': 3, 'status': f'Starting media analysis for {content_id}...'}
        )
        
        # Run async media analysis
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            result = loop.run_until_complete(_media_analysis_async(content_id, models_override, self))
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


async def _media_analysis_async(content_id: str, models_override: Optional[Dict[str, Any]], task) -> Dict[str, Any]:
    """Async media analysis implementation."""
    content_repo = get_content_repository()
    model_router = get_model_router()
    ai_service = get_ai_service()
    
    async with get_db_session() as db:
        # Step 1: Load content item
        task.update_state(
            state='PROGRESS',
            meta={'current': 1, 'total': 3, 'status': 'Loading content item...'}
        )
        
        content_item = await content_repo.get(db, content_id)
        if not content_item:
            raise ValueError(f"Content item {content_id} not found")
        
        # Check if already analyzed
        if content_item.media_analyzed and not models_override:
            return {
                'status': 'skipped',
                'content_id': content_id,
                'phase': 'media_analysis',
                'message': 'Media already analyzed'
            }
        
        # Check if there's media to analyze
        if not content_item.media_content:
            # Mark as analyzed even though no media exists
            await content_repo.update(db, content_id, {'media_analyzed': True})
            return {
                'status': 'completed',
                'content_id': content_id,
                'phase': 'media_analysis',
                'media_count': 0,
                'message': 'No media content to analyze'
            }
        
        # Step 2: Resolve vision model
        task.update_state(
            state='PROGRESS',
            meta={'current': 2, 'total': 3, 'status': 'Analyzing media with vision model...'}
        )
        
        override_selector = models_override.get('vision') if models_override else None
        backend, model, params = await model_router.resolve(ModelPhase.vision, override=override_selector)
        
        # Analyze each media item
        media_analysis_results = []
        for i, media_item in enumerate(content_item.media_content):
            # TODO: Implement actual vision model analysis with XML prompts
            # For now, simulate the analysis
            analysis_result = await _simulate_media_analysis(media_item, content_item.content, backend, model, params)
            media_analysis_results.append(analysis_result)
        
        # Step 3: Update content item with analysis results
        task.update_state(
            state='PROGRESS',
            meta={'current': 3, 'total': 3, 'status': 'Saving analysis results...'}
        )
        
        update_data = {
            'media_analysis_results': {
                'analyses': media_analysis_results,
                'model_used': model,
                'analysis_timestamp': datetime.utcnow().isoformat()
            },
            'media_analyzed': True,
            'vision_model_used': model
        }
        
        updated_item = await content_repo.update(db, content_id, update_data)
    
    return {
        'status': 'completed',
        'content_id': content_id,
        'phase': 'media_analysis',
        'media_count': len(content_item.media_content),
        'model_used': model,
        'analysis_results': len(media_analysis_results),
        'message': f'Successfully analyzed {len(media_analysis_results)} media items'
    }


@celery_app.task(bind=True)
def phase_3_2_content_understanding_task(self, content_id: str, models_override: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Phase 3.2: Generate collective understanding of bookmark content."""
    try:
        current_task.update_state(
            state='PROGRESS',
            meta={'current': 0, 'total': 3, 'status': f'Starting content understanding for {content_id}...'}
        )
        
        # Run async content understanding
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            result = loop.run_until_complete(_content_understanding_async(content_id, models_override, self))
            return result
        finally:
            loop.close()
            
    except Exception as e:
        logger.error(f"Content understanding task failed for {content_id}: {e}")
        return {
            'status': 'failed',
            'content_id': content_id,
            'phase': 'content_understanding',
            'error': str(e)
        }


async def _content_understanding_async(content_id: str, models_override: Optional[Dict[str, Any]], task) -> Dict[str, Any]:
    """Async content understanding implementation."""
    content_repo = get_content_repository()
    model_router = get_model_router()
    ai_service = get_ai_service()
    
    async with get_db_session() as db:
        # Step 1: Load content item
        task.update_state(
            state='PROGRESS',
            meta={'current': 1, 'total': 3, 'status': 'Loading content item...'}
        )
        
        content_item = await content_repo.get(db, content_id)
        if not content_item:
            raise ValueError(f"Content item {content_id} not found")
        
        # Check if already understood
        if content_item.content_understood and not models_override:
            return {
                'status': 'skipped',
                'content_id': content_id,
                'phase': 'content_understanding',
                'message': 'Content already understood'
            }
        
        # Step 2: Resolve understanding model and generate collective understanding
        task.update_state(
            state='PROGRESS',
            meta={'current': 2, 'total': 3, 'status': 'Generating collective understanding...'}
        )
        
        override_selector = models_override.get('kb_generation') if models_override else None
        backend, model, params = await model_router.resolve(ModelPhase.kb_generation, override=override_selector)
        
        # TODO: Implement actual content understanding with XML prompts
        # For now, simulate the understanding generation
        understanding_result = await _simulate_content_understanding(
            content_item.content,
            content_item.media_analysis_results,
            backend, model, params
        )
        
        # Step 3: Update content item with understanding results
        task.update_state(
            state='PROGRESS',
            meta={'current': 3, 'total': 3, 'status': 'Saving understanding results...'}
        )
        
        update_data = {
            'collective_understanding': understanding_result['collective_understanding'],
            'content_understood': True,
            'understanding_model_used': model
        }
        
        updated_item = await content_repo.update(db, content_id, update_data)
    
    return {
        'status': 'completed',
        'content_id': content_id,
        'phase': 'content_understanding',
        'model_used': model,
        'understanding_length': len(understanding_result['collective_understanding']),
        'key_concepts': understanding_result.get('key_concepts', []),
        'technical_domain': understanding_result.get('technical_domain', 'general'),
        'message': f'Successfully generated collective understanding'
    }


@celery_app.task(bind=True)
def phase_3_3_categorization_task(self, content_id: str, models_override: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Phase 3.3: Generate categories and sub-categories with existing category intelligence."""
    try:
        current_task.update_state(
            state='PROGRESS',
            meta={'current': 0, 'total': 4, 'status': f'Starting categorization for {content_id}...'}
        )
        
        # Run async categorization
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            result = loop.run_until_complete(_categorization_async(content_id, models_override, self))
            return result
        finally:
            loop.close()
            
    except Exception as e:
        logger.error(f"Categorization task failed for {content_id}: {e}")
        return {
            'status': 'failed',
            'content_id': content_id,
            'phase': 'categorization',
            'error': str(e)
        }


async def _categorization_async(content_id: str, models_override: Optional[Dict[str, Any]], task) -> Dict[str, Any]:
    """Async categorization implementation."""
    content_repo = get_content_repository()
    model_router = get_model_router()
    ai_service = get_ai_service()
    
    async with get_db_session() as db:
        # Step 1: Load content item
        task.update_state(
            state='PROGRESS',
            meta={'current': 1, 'total': 4, 'status': 'Loading content item...'}
        )
        
        content_item = await content_repo.get(db, content_id)
        if not content_item:
            raise ValueError(f"Content item {content_id} not found")
        
        # Check if already categorized
        if content_item.categorized and not models_override:
            return {
                'status': 'skipped',
                'content_id': content_id,
                'phase': 'categorization',
                'message': 'Content already categorized'
            }
        
        # Step 2: Get existing categories for intelligence
        task.update_state(
            state='PROGRESS',
            meta={'current': 2, 'total': 4, 'status': 'Loading existing categories...'}
        )
        
        existing_categories = await _get_existing_categories(content_repo, db)
        
        # Step 3: Resolve categorization model and generate categories
        task.update_state(
            state='PROGRESS',
            meta={'current': 3, 'total': 4, 'status': 'Generating categories...'}
        )
        
        override_selector = models_override.get('kb_generation') if models_override else None
        backend, model, params = await model_router.resolve(ModelPhase.kb_generation, override=override_selector)
        
        # TODO: Implement actual categorization with XML prompts and existing category intelligence
        # For now, simulate the categorization
        categorization_result = await _simulate_categorization(
            content_item.collective_understanding or content_item.content,
            existing_categories,
            backend, model, params
        )
        
        # Step 4: Update content item with categorization results
        task.update_state(
            state='PROGRESS',
            meta={'current': 4, 'total': 4, 'status': 'Saving categorization results...'}
        )
        
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
            'categorization_model_used': model
        }
        
        updated_item = await content_repo.update(db, content_id, update_data)
    
    return {
        'status': 'completed',
        'content_id': content_id,
        'phase': 'categorization',
        'category': categorization_result['category'],
        'subcategory': categorization_result['subcategory'],
        'is_new_category': categorization_result['is_new_category'],
        'confidence_score': categorization_result['confidence_score'],
        'model_used': model,
        'message': f'Successfully categorized as {categorization_result["category"]}/{categorization_result["subcategory"]}'
    }


# CLI testing task
@celery_app.task(bind=True)
def test_subphase_task(self, content_id: str, phase_name: str, force: bool = False, models_override: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Test individual sub-phase processing (for CLI testing)."""
    try:
        phase_tasks = {
            'bookmark_caching': phase_2_1_bookmark_caching_task,
            'media_analysis': phase_3_1_media_analysis_task,
            'content_understanding': phase_3_2_content_understanding_task,
            'categorization': phase_3_3_categorization_task
        }
        
        if phase_name not in phase_tasks:
            return {
                'status': 'failed',
                'error': f'Invalid phase name. Must be one of: {", ".join(phase_tasks.keys())}'
            }
        
        # Execute the specific phase task
        if phase_name == 'bookmark_caching':
            result = phase_tasks[phase_name].apply_async(args=[content_id, force])
        else:
            result = phase_tasks[phase_name].apply_async(args=[content_id, models_override])
        
        return result.get()
        
    except Exception as e:
        logger.error(f"Test sub-phase task failed: {e}")
        return {
            'status': 'failed',
            'content_id': content_id,
            'phase': phase_name,
            'error': str(e)
        }


# Helper functions (simulated implementations)
async def _simulate_twitter_api_fetch(tweet_id: str) -> Dict[str, Any]:
    """Simulate Twitter/X API data fetching."""
    return {
        'id': tweet_id,
        'text': f'This is simulated tweet content for {tweet_id}. It contains some technical information about AI and machine learning.',
        'author_username': 'test_user',
        'author_id': '123456789',
        'url': f'https://twitter.com/test_user/status/{tweet_id}',
        'created_at': datetime.utcnow().isoformat(),
        'public_metrics': {
            'like_count': 42,
            'retweet_count': 12,
            'reply_count': 5,
            'quote_count': 3
        },
        'media': [
            {
                'type': 'image',
                'url': f'https://example.com/media/{tweet_id}_1.jpg',
                'alt_text': 'Screenshot of code'
            }
        ]
    }


async def _detect_thread(tweet_data: Dict[str, Any]) -> Dict[str, Any]:
    """Simulate thread detection."""
    # For simulation, randomly decide if it's part of a thread
    import random
    is_thread = random.choice([True, False])
    
    if is_thread:
        return {
            'thread_id': f"thread_{tweet_data['id'][:8]}",
            'is_thread_root': True,
            'position_in_thread': 0,
            'thread_length': random.randint(2, 8)
        }
    else:
        return {
            'thread_id': None,
            'is_thread_root': False,
            'position_in_thread': None,
            'thread_length': 1
        }


async def _cache_media_content(media_list: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Simulate media content caching."""
    cached_media = []
    for media in media_list:
        cached_media.append({
            'type': media['type'],
            'original_url': media['url'],
            'alt_text': media.get('alt_text', ''),
            'cached_data': f'base64_encoded_data_for_{media["url"].split("/")[-1]}',
            'cached_at': datetime.utcnow().isoformat()
        })
    return cached_media


async def _simulate_media_analysis(media_item: Dict[str, Any], tweet_text: str, backend, model: str, params: Dict[str, Any]) -> Dict[str, Any]:
    """Simulate media analysis with vision model."""
    return {
        'media_id': media_item.get('original_url', '').split('/')[-1],
        'media_type': media_item['type'],
        'description': f'This {media_item["type"]} shows technical content related to the tweet about AI and machine learning.',
        'technical_analysis': 'The image contains code snippets and technical diagrams that illustrate machine learning concepts.',
        'key_insights': ['Code examples', 'Technical diagrams', 'Machine learning concepts'],
        'confidence_score': 0.85
    }


async def _simulate_content_understanding(content: str, media_analysis: Optional[Dict[str, Any]], backend, model: str, params: Dict[str, Any]) -> Dict[str, Any]:
    """Simulate content understanding generation."""
    return {
        'collective_understanding': f'This content discusses technical aspects of AI and machine learning, providing insights into implementation details and best practices. The content combines textual information with visual elements to create a comprehensive understanding of the topic.',
        'key_concepts': ['artificial intelligence', 'machine learning', 'technical implementation', 'best practices'],
        'technical_domain': 'machine-learning',
        'actionable_insights': ['Implementation guidance', 'Best practice recommendations', 'Technical examples']
    }


async def _get_existing_categories(content_repo, db) -> List[Dict[str, Any]]:
    """Get existing categories for intelligence."""
    # TODO: Implement actual category statistics query
    return [
        {'name': 'machine-learning', 'count': 15, 'subcategories': [{'name': 'neural-networks', 'count': 8}]},
        {'name': 'web-development', 'count': 12, 'subcategories': [{'name': 'frontend', 'count': 7}]},
        {'name': 'data-science', 'count': 10, 'subcategories': [{'name': 'analytics', 'count': 5}]}
    ]


async def _simulate_categorization(content: str, existing_categories: List[Dict[str, Any]], backend, model: str, params: Dict[str, Any]) -> Dict[str, Any]:
    """Simulate categorization with existing category intelligence."""
    # For simulation, choose from existing categories or create new ones
    import random
    
    if random.choice([True, False]) and existing_categories:
        # Use existing category
        category = random.choice(existing_categories)
        subcategory = random.choice(category['subcategories']) if category['subcategories'] else {'name': 'general'}
        return {
            'category': category['name'],
            'subcategory': subcategory['name'],
            'reasoning': f'Content matches existing category {category["name"]} based on technical domain analysis.',
            'is_new_category': False,
            'confidence_score': 0.9
        }
    else:
        # Create new category
        return {
            'category': 'ai-research',
            'subcategory': 'emerging-tech',
            'reasoning': 'Content discusses emerging AI research topics not covered by existing categories.',
            'is_new_category': True,
            'confidence_score': 0.75
        }