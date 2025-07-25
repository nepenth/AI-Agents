"""
Processing Phase Tasks for Celery

This module contains individual processing phase tasks that can be run
independently or as part of the main agent pipeline.
"""

import logging
import uuid
import asyncio
from datetime import datetime
from typing import Dict, Any, Optional, List

from ..celery_app import celery_app
from ..task_progress import get_progress_manager
from ..config import Config
from ..shared_globals import sg_set_project_root
from ..exceptions import KnowledgeBaseError


@celery_app.task(bind=True, name='knowledge_base_agent.tasks.processing.process_tweets')
def process_tweets_task(self, task_id: str, tweet_ids: List[str], phase: str, preferences_dict: Dict[str, Any]):
    """
    Individual tweet processing task for parallel execution.
    
    Migrates StreamlinedContentProcessor phase execution to 
    individual Celery tasks for better parallelization.
    
    Args:
        task_id: Unique task identifier for progress tracking
        tweet_ids: List of tweet IDs to process
        phase: Processing phase ('cache', 'media', 'llm', 'kb_item')
        preferences_dict: UserPreferences as dictionary
        
    Returns:
        Dict with processing results
    """
    progress_manager = get_progress_manager()
    
    async def _async_process():
        from ..preferences import UserPreferences
        
        config = Config.from_env()
        config.ensure_directories()
        sg_set_project_root(config.project_root)
        
        # Convert dict back to UserPreferences
        preferences = UserPreferences(**preferences_dict)
        
        processed_tweets = []
        
        if phase == 'cache':
            from ..tweet_cacher import TweetCacher
            cacher = TweetCacher(config)
            
            for i, tweet_id in enumerate(tweet_ids):
                progress_manager.update_progress(
                    task_id, 
                    int((i + 1) / len(tweet_ids) * 100), 
                    f"cache_tweets",
                    f"Caching tweet {i+1}/{len(tweet_ids)}: {tweet_id}"
                )
                
                try:
                    await cacher.cache_tweet(tweet_id, force_recache=preferences.force_recache_tweets)
                    processed_tweets.append(tweet_id)
                    progress_manager.log_message(task_id, f"Cached tweet {tweet_id}", "INFO")
                except Exception as e:
                    progress_manager.log_message(task_id, f"Failed to cache tweet {tweet_id}: {e}", "ERROR")
                    
        elif phase == 'media':
            from ..media_processor import MediaProcessor
            
            processor = MediaProcessor(config)
            
            for i, tweet_id in enumerate(tweet_ids):
                progress_manager.update_progress(
                    task_id, 
                    int((i + 1) / len(tweet_ids) * 100), 
                    f"process_media",
                    f"Processing media for tweet {i+1}/{len(tweet_ids)}: {tweet_id}"
                )
                
                try:
                    await processor.process_tweet_media(tweet_id, force_reprocess=preferences.force_reprocess_media)
                    processed_tweets.append(tweet_id)
                    progress_manager.log_message(task_id, f"Processed media for tweet {tweet_id}", "INFO")
                except Exception as e:
                    progress_manager.log_message(task_id, f"Failed to process media for tweet {tweet_id}: {e}", "ERROR")
                    
        elif phase == 'llm':
            from ..ai_categorization import LLMProcessor
            
            processor = LLMProcessor(config)
            
            for i, tweet_id in enumerate(tweet_ids):
                progress_manager.update_progress(
                    task_id, 
                    int((i + 1) / len(tweet_ids) * 100), 
                    f"llm_processing",
                    f"LLM processing tweet {i+1}/{len(tweet_ids)}: {tweet_id}"
                )
                
                try:
                    await processor.process_tweet_categorization(tweet_id, force_reprocess=preferences.force_reprocess_llm)
                    processed_tweets.append(tweet_id)
                    progress_manager.log_message(task_id, f"LLM processed tweet {tweet_id}", "INFO")
                except Exception as e:
                    progress_manager.log_message(task_id, f"Failed to LLM process tweet {tweet_id}: {e}", "ERROR")
                    
        elif phase == 'kb_item':
            from ..kb_item_generator import KBItemGenerator
            
            generator = KBItemGenerator(config)
            
            for i, tweet_id in enumerate(tweet_ids):
                progress_manager.update_progress(
                    task_id, 
                    int((i + 1) / len(tweet_ids) * 100), 
                    f"generate_kb_items",
                    f"Generating KB item for tweet {i+1}/{len(tweet_ids)}: {tweet_id}"
                )
                
                try:
                    await generator.generate_kb_item(tweet_id, force_regenerate=preferences.force_reprocess_kb_item)
                    processed_tweets.append(tweet_id)
                    progress_manager.log_message(task_id, f"Generated KB item for tweet {tweet_id}", "INFO")
                except Exception as e:
                    progress_manager.log_message(task_id, f"Failed to generate KB item for tweet {tweet_id}: {e}", "ERROR")
        else:
            raise ValueError(f"Unknown processing phase: {phase}")
            
        return processed_tweets
    
    try:
        progress_manager.log_message(task_id, f"🔄 Starting {phase} processing for {len(tweet_ids)} tweets", "INFO")
        progress_manager.update_progress(task_id, 0, f"process_tweets_{phase}", f"Starting {phase} processing")
        
        # Create event loop for async operations
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            processed_tweets = loop.run_until_complete(_async_process())
        finally:
            loop.close()
        
        progress_manager.update_progress(task_id, 100, f"process_tweets_{phase}", f"Completed {phase} processing")
        progress_manager.log_message(task_id, f"✅ {phase} processing completed: {len(processed_tweets)}/{len(tweet_ids)} tweets", "INFO")
        
        return {
            'status': 'completed',
            'task_id': task_id,
            'phase': phase,
            'processed_tweets': processed_tweets,
            'total_tweets': len(tweet_ids),
            'success_count': len(processed_tweets),
            'message': f'{phase} processing completed successfully'
        }
        
    except Exception as e:
        error_msg = f"{phase} processing failed: {str(e)}"
        progress_manager.log_message(task_id, f"❌ {error_msg}", "ERROR")
        progress_manager.update_progress(task_id, 0, "error", error_msg)
        
        logging.error(f"{phase} processing task failed: {error_msg}", exc_info=True)
        
        self.update_state(
            state='FAILURE',
            meta={
                'error': error_msg,
                'task_id': task_id,
                'phase': phase,
                'timestamp': datetime.utcnow().isoformat()
            }
        )
        
        raise


@celery_app.task(bind=True, name='knowledge_base_agent.tasks.processing.generate_synthesis')
def generate_synthesis_task(self, task_id: str, category: str, subcategory: str, preferences_dict: Dict[str, Any]):
    """
    Synthesis generation as independent task.
    
    Args:
        task_id: Unique task identifier for progress tracking
        category: Main category for synthesis
        subcategory: Subcategory for synthesis
        preferences_dict: UserPreferences as dictionary
        
    Returns:
        Dict with synthesis results
    """
    progress_manager = get_progress_manager()
    
    async def _async_synthesis():
        from ..synthesis_generator import SynthesisGenerator
        from ..preferences import UserPreferences
        
        config = Config.from_env()
        config.ensure_directories()
        sg_set_project_root(config.project_root)
        
        # Convert dict back to UserPreferences
        preferences = UserPreferences(**preferences_dict)
        
        # Initialize synthesis generator
        generator = SynthesisGenerator(config)
        
        # Generate synthesis for the specified category/subcategory
        result = await generator.generate_synthesis(
            category, 
            subcategory, 
            force_regenerate=preferences.force_regenerate_synthesis,
            synthesis_mode=preferences.synthesis_mode
        )
        
        return result
    
    try:
        progress_manager.log_message(task_id, f"📚 Starting synthesis generation for {category}/{subcategory}", "INFO")
        progress_manager.update_progress(task_id, 0, "generate_synthesis", f"Starting synthesis generation")
        
        # Create event loop for async operations
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            progress_manager.update_progress(task_id, 50, "generate_synthesis", f"Generating synthesis...")
            result = loop.run_until_complete(_async_synthesis())
        finally:
            loop.close()
        
        progress_manager.update_progress(task_id, 100, "generate_synthesis", "Synthesis generation completed")
        progress_manager.log_message(task_id, f"✅ Synthesis generated for {category}/{subcategory}", "INFO")
        
        return {
            'status': 'completed',
            'task_id': task_id,
            'category': category,
            'subcategory': subcategory,
            'result': result,
            'message': 'Synthesis generation completed successfully'
        }
        
    except Exception as e:
        error_msg = f"Synthesis generation failed: {str(e)}"
        progress_manager.log_message(task_id, f"❌ {error_msg}", "ERROR")
        progress_manager.update_progress(task_id, 0, "error", error_msg)
        
        logging.error(f"Synthesis generation task failed: {error_msg}", exc_info=True)
        
        self.update_state(
            state='FAILURE',
            meta={
                'error': error_msg,
                'task_id': task_id,
                'category': category,
                'subcategory': subcategory,
                'timestamp': datetime.utcnow().isoformat()
            }
        )
        
        raise


@celery_app.task(bind=True, name='knowledge_base_agent.tasks.processing.generate_embeddings')  
def generate_embeddings_task(self, task_id: str, content_ids: List[str], preferences_dict: Dict[str, Any]):
    """
    Embedding generation as independent task.
    
    Args:
        task_id: Unique task identifier for progress tracking
        content_ids: List of content IDs to generate embeddings for
        preferences_dict: UserPreferences as dictionary
        
    Returns:
        Dict with embedding results
    """
    progress_manager = get_progress_manager()
    
    async def _async_embeddings():
        from ..embedding_manager import EmbeddingManager
        from ..http_client import HTTPClient
        from ..preferences import UserPreferences
        
        config = Config.from_env()
        config.ensure_directories()
        sg_set_project_root(config.project_root)
        
        # Convert dict back to UserPreferences
        preferences = UserPreferences(**preferences_dict)
        
        # Initialize embedding manager
        http_client = HTTPClient(config)
        embedding_manager = EmbeddingManager(config, http_client)
        
        # Generate embeddings for content IDs
        generated_count = 0
        for i, content_id in enumerate(content_ids):
            progress_manager.update_progress(
                task_id, 
                int((i + 1) / len(content_ids) * 100), 
                "generate_embeddings",
                f"Generating embeddings {i+1}/{len(content_ids)}: {content_id}"
            )
            
            try:
                await embedding_manager.generate_embeddings_for_content(
                    content_id, 
                    force_regenerate=preferences.force_regenerate_embeddings
                )
                generated_count += 1
                progress_manager.log_message(task_id, f"Generated embeddings for {content_id}", "INFO")
            except Exception as e:
                progress_manager.log_message(task_id, f"Failed to generate embeddings for {content_id}: {e}", "ERROR")
        
        return generated_count
    
    try:
        progress_manager.log_message(task_id, f"🧠 Starting embedding generation for {len(content_ids)} items", "INFO")
        progress_manager.update_progress(task_id, 0, "generate_embeddings", "Starting embedding generation")
        
        # Create event loop for async operations
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            generated_count = loop.run_until_complete(_async_embeddings())
        finally:
            loop.close()
        
        progress_manager.update_progress(task_id, 100, "generate_embeddings", "Embedding generation completed")
        progress_manager.log_message(task_id, f"✅ Generated embeddings for {generated_count}/{len(content_ids)} items", "INFO")
        
        return {
            'status': 'completed',
            'task_id': task_id,
            'content_ids': content_ids,
            'generated_count': generated_count,
            'total_count': len(content_ids),
            'message': 'Embedding generation completed successfully'
        }
        
    except Exception as e:
        error_msg = f"Embedding generation failed: {str(e)}"
        progress_manager.log_message(task_id, f"❌ {error_msg}", "ERROR")
        progress_manager.update_progress(task_id, 0, "error", error_msg)
        
        logging.error(f"Embedding generation task failed: {error_msg}", exc_info=True)
        
        self.update_state(
            state='FAILURE',
            meta={
                'error': error_msg,
                'task_id': task_id,
                'content_ids': content_ids,
                'timestamp': datetime.utcnow().isoformat()
            }
        )
        
        raise


@celery_app.task(bind=True, name='knowledge_base_agent.tasks.processing.generate_readme')
def generate_readme_task(self, task_id: str, preferences_dict: Dict[str, Any]):
    """
    README generation as independent task.
    
    Args:
        task_id: Unique task identifier for progress tracking
        preferences_dict: UserPreferences as dictionary
        
    Returns:
        Dict with README generation results
    """
    progress_manager = get_progress_manager()
    
    async def _async_readme():
        from ..readme_generator import ReadmeGenerator
        from ..preferences import UserPreferences
        
        config = Config.from_env()
        config.ensure_directories()
        sg_set_project_root(config.project_root)
        
        # Convert dict back to UserPreferences
        preferences = UserPreferences(**preferences_dict)
        
        # Initialize README generator
        generator = ReadmeGenerator(config)
        
        # Generate README
        result = await generator.regenerate_readme(force_regenerate=preferences.force_regenerate_readme)
        
        return result
    
    try:
        progress_manager.log_message(task_id, "📝 Starting README generation", "INFO")
        progress_manager.update_progress(task_id, 0, "generate_readme", "Starting README generation")
        
        # Create event loop for async operations
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            progress_manager.update_progress(task_id, 50, "generate_readme", "Generating README...")
            result = loop.run_until_complete(_async_readme())
        finally:
            loop.close()
        
        progress_manager.update_progress(task_id, 100, "generate_readme", "README generation completed")
        progress_manager.log_message(task_id, "✅ README generation completed", "INFO")
        
        return {
            'status': 'completed',
            'task_id': task_id,
            'result': result,
            'message': 'README generation completed successfully'
        }
        
    except Exception as e:
        error_msg = f"README generation failed: {str(e)}"
        progress_manager.log_message(task_id, f"❌ {error_msg}", "ERROR")
        progress_manager.update_progress(task_id, 0, "error", error_msg)
        
        logging.error(f"README generation task failed: {error_msg}", exc_info=True)
        
        self.update_state(
            state='FAILURE',
            meta={
                'error': error_msg,
                'task_id': task_id,
                'timestamp': datetime.utcnow().isoformat()
            }
        )
        
        raise


def generate_task_id() -> str:
    """Generate a unique task ID for tracking purposes."""
    return str(uuid.uuid4()) 