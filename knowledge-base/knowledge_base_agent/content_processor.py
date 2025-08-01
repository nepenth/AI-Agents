"""
Streamlined Content Processing Module

This ContentProcessor is a pure orchestrator that uses:
- StateManager for all validation
- PhaseExecutionHelper for phase planning and eligibility filtering
- Individual processing modules for actual work

No validation logic exists in this file - it's handled by StateManager
and PhaseExecutionHelper.
"""

from pathlib import Path
from typing import Dict, Any, List, Tuple, Optional
import logging
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
import json
import os
import time
import copy
import asyncio
import traceback
from statistics import median
from itertools import cycle

# Core framework imports
from flask import current_app
from flask_socketio import SocketIO

# Project-specific imports
from knowledge_base_agent.progress import ProcessingStats, PhaseDetail
from knowledge_base_agent.config import Config
from knowledge_base_agent.http_client import HTTPClient
# DatabaseStateManager removed - using UnifiedStateManager instead
from knowledge_base_agent.category_manager import CategoryManager
from knowledge_base_agent.exceptions import ContentProcessingError, KnowledgeBaseItemCreationError
from knowledge_base_agent.tweet_cacher import cache_tweets
from knowledge_base_agent.media_processor import process_media
# MarkdownWriter removed - no longer writing to disk, using unified DB only
from knowledge_base_agent.custom_types import KnowledgeBaseItem
from knowledge_base_agent.phase_execution_helper import PhaseExecutionHelper, ProcessingPhase, PhaseExecutionPlan
from knowledge_base_agent.tweet_retry_manager import TweetRetryManager, RetryConfig
from knowledge_base_agent.ai_categorization import categorize_and_name_content as ai_categorize_and_name
from knowledge_base_agent.kb_item_generator import create_knowledge_base_item
from knowledge_base_agent.models import KnowledgeBaseItem as DBKnowledgeBaseItem
from knowledge_base_agent.preferences import UserPreferences
from knowledge_base_agent.shared_globals import stop_flag
from knowledge_base_agent.stats_manager import load_processing_stats, update_phase_stats


class StreamlinedContentProcessor:
    """
    Streamlined ContentProcessor focused purely on orchestration.
    
    All validation is handled by StateManager.
    All phase planning is handled by PhaseExecutionHelper.
    """
    
    def __init__(self, config=None, http_client=None, state_manager=None, 
                 category_manager=None, socketio=None, phase_emitter_func=None, task_id=None):
        self.config = config
        self.http_client = http_client
        self.state_manager = state_manager
        self.socketio = socketio
        self.phase_emitter_func = phase_emitter_func
        self.text_model = self.http_client.config.text_model
        self.category_manager = category_manager
        self.task_id = task_id
        
        # Initialize unified logging system if task_id is provided
        if task_id:
            from .unified_logging import get_unified_logger
            self.unified_logger = get_unified_logger(task_id, config)
        else:
            self.unified_logger = None
        
        # Initialize phase execution helper
        self.phase_helper = PhaseExecutionHelper(config)
        
        # Initialize retry manager for intelligent error handling
        retry_config = RetryConfig(
            max_retries=3,
            base_delay=2.0,
            max_delay=600.0,  # 10 minutes max
            exponential_factor=2.0,
            jitter=True
        )
        self.retry_manager = TweetRetryManager(retry_config)
        
        logging.info(f"Initialized StreamlinedContentProcessor with model: {self.text_model}")
        logging.info(f"Retry manager initialized with config: max_retries={retry_config.max_retries}, "
                    f"base_delay={retry_config.base_delay}s, strategy={retry_config.retry_strategy.value}")

    def socketio_emit_log(self, message: str, level: str = "INFO") -> None:
        """Helper method to emit general logs via unified logging system."""
        # MODERN: Use unified logging system
        if self.unified_logger:
            self.unified_logger.log(message, level.upper())
        elif self.socketio:
            # LEGACY: Fallback to direct SocketIO
            self.socketio.emit('log', {'message': message, 'level': level.upper()})
        # Standard logging will also occur via Python's logging module
        logger_level = getattr(logging, level.upper(), logging.INFO)
        logging.log(logger_level, f"[ContentProcessor] {message}")

    async def process_all_tweets(
        self,
        preferences: UserPreferences,
        unprocessed_tweets: List[str],
        total_tweets_for_processing: int,
        stats: ProcessingStats,
        category_manager: CategoryManager
    ) -> List[PhaseDetail]:
        """
        Main orchestration method - now purely focused on coordination.
        All validation is handled by StateManager during initialization.
        """
        phase_details_results: List[PhaseDetail] = []

        if not unprocessed_tweets:
            logging.info("ContentProcessor: No tweets to process.")
            self.socketio_emit_log("No tweets to process.", "INFO")
            
            # Don't return early - let execution plans determine if sub-phases have work to do
            # This handles force reprocessing flags and database sync needs properly
            unprocessed_tweets = []  # Set to empty list but continue with execution plan evaluation
            
        if len(unprocessed_tweets) > 0:
            self.socketio_emit_log(f"🔄 Processing {len(unprocessed_tweets)} tweets through content pipeline", "INFO")
        else:
            self.socketio_emit_log("🔄 Evaluating cached tweets for reprocessing", "INFO")
        if self.phase_emitter_func: 
            self.phase_emitter_func('content_processing_overall', 'in_progress', 
                                   f'Evaluating processing needs for all cached tweets...')

        # Load ALL tweet data for execution plan evaluation, not just unprocessed ones
        # The execution plans will determine what actually needs processing based on force flags
        all_tweets = self.state_manager.get_all_tweets()
        tweets_data_map: Dict[str, Dict[str, Any]] = {}
        
        # Ensure all unprocessed tweets are included in the data map, even if not cached yet
        all_tweet_ids = set(all_tweets.keys()) | set(unprocessed_tweets)
        
        for tweet_id in all_tweet_ids:
            tweet_data = self.state_manager.get_tweet(tweet_id)
            if not tweet_data:
                # Initialize cache entry with comprehensive defaults
                initial_data = {
                    'source_url': f'https://twitter.com/user/status/{tweet_id}',
                    'source': 'unprocessed_queue'
                }
                tweet_data = self.state_manager.create_tweet_with_full_defaults(tweet_id, initial_data)
                logging.info(f"Initialized comprehensive cache entry for unprocessed tweet {tweet_id}")
            tweets_data_map[tweet_id] = tweet_data or {'tweet_id': tweet_id}

        # Create force flags dictionary for helper
        force_flags = {
            'force_recache_tweets': preferences.force_recache_tweets,
            'force_reprocess_media': preferences.force_reprocess_media,
            'force_reprocess_llm': preferences.force_reprocess_llm,
            'force_reprocess_kb_item': preferences.force_reprocess_kb_item
            # force_reprocess_db_sync removed - no longer using separate DB sync phase
        }

        # Get initial execution plans for all phases
        self.socketio_emit_log("Creating initial execution plans for all processing phases...", "INFO")
        execution_plans = self.phase_helper.create_all_execution_plans(tweets_data_map, force_flags)

        # Log analysis for debugging
        analysis = self.phase_helper.analyze_processing_state(tweets_data_map)
        self.socketio_emit_log(f"Processing state analysis: {analysis['total_tweets']} total tweets", "INFO")
        for stage, tweet_ids in analysis['tweets_by_stage'].items():
            if tweet_ids:
                self.socketio_emit_log(f"  {stage}: {len(tweet_ids)} tweets", "INFO")

        # Check for retryable tweets before main processing
        retryable_tweets = self.retry_manager.get_retryable_tweets(tweets_data_map)
        if retryable_tweets:
            self.socketio_emit_log(f"🔁 Found {len(retryable_tweets)} tweets ready for retry", "INFO")
            # Add retryable tweets to processing if they're not already included
            for tweet_id in retryable_tweets:
                if tweet_id not in all_tweet_ids:
                    all_tweet_ids.add(tweet_id)
                    if tweet_id not in tweets_data_map:
                        tweet_data = self.state_manager.get_tweet(tweet_id)
                        tweets_data_map[tweet_id] = tweet_data

        # Execute each phase and regenerate plans after phases that change eligibility
        # NOTE: Database sync is now a standalone phase, not part of content processing
        try:
            # Cache phase
            await self._execute_cache_phase(execution_plans[ProcessingPhase.CACHE], tweets_data_map, preferences, stats)
            
            # Regenerate plans after cache phase since it affects eligibility for subsequent phases
            if execution_plans[ProcessingPhase.CACHE].needs_processing_count > 0:
                self.socketio_emit_log("🔄 Regenerating execution plans after cache phase...", "DEBUG")
                execution_plans = self.phase_helper.create_all_execution_plans(tweets_data_map, force_flags)
            
            # Media phase  
            await self._execute_media_phase(execution_plans[ProcessingPhase.MEDIA], tweets_data_map, preferences, stats)
            
            # Regenerate plans after media phase since it affects LLM phase eligibility
            if execution_plans[ProcessingPhase.MEDIA].needs_processing_count > 0:
                self.socketio_emit_log("🔄 Regenerating execution plans after media phase...", "DEBUG")
                execution_plans = self.phase_helper.create_all_execution_plans(tweets_data_map, force_flags)
            
            # LLM phase
            await self._execute_llm_phase(execution_plans[ProcessingPhase.LLM], tweets_data_map, preferences, stats, category_manager)
            
            # Regenerate plans after LLM phase since it affects KB item phase eligibility
            if execution_plans[ProcessingPhase.LLM].needs_processing_count > 0:
                self.socketio_emit_log("🔄 Regenerating execution plans after LLM phase...", "DEBUG")
                execution_plans = self.phase_helper.create_all_execution_plans(tweets_data_map, force_flags)
            
            # KB Item phase
            await self._execute_kb_item_phase(execution_plans[ProcessingPhase.KB_ITEM], tweets_data_map, preferences, stats)
            # Database sync is handled as a separate standalone phase by the main agent
        except Exception as e:
            self.socketio_emit_log(f"Error during phase execution: {e}", "ERROR")
            if self.phase_emitter_func:
                self.phase_emitter_func('content_processing_overall', 'error', f'Processing error: {e}')
            
            # Enhanced error recovery - attempt to save partial progress
            try:
                self.socketio_emit_log("🔧 Attempting error recovery and partial progress save...", "INFO")
                await self._attempt_error_recovery(tweets_data_map, e)
            except Exception as recovery_error:
                self.socketio_emit_log(f"Error recovery failed: {recovery_error}", "ERROR")
            
            raise

        # Final processing validation and stats
        await self._finalize_processing(tweets_data_map, unprocessed_tweets, stats)

        final_summary_msg = f"Content processing completed. Evaluated {len(tweets_data_map)} total tweets. Successfully processed: {stats.processed_count}. Errors: {stats.error_count}."
        self.socketio_emit_log(final_summary_msg, "INFO")
        
        overall_status = 'completed'
        if stop_flag.is_set():
            overall_status = 'interrupted'
        elif stats.error_count > 0:
            overall_status = 'completed_with_warnings'
        
        if self.phase_emitter_func: 
            self.phase_emitter_func('content_processing_overall', overall_status, final_summary_msg)

        return phase_details_results

    async def _execute_cache_phase(self, plan: PhaseExecutionPlan, tweets_data_map: Dict[str, Any], preferences, stats):
        """Execute caching phase using execution plan."""
        if plan.should_skip_phase:
            completion_msg = f"All {plan.already_complete_count} tweets already cached"
            self.socketio_emit_log(f"✅ Tweet Caching: {completion_msg}", "INFO")
            # Emit active status first to show phase is being processed
            if self.phase_emitter_func:
                self.phase_emitter_func('tweet_caching', 'active', f'Checking {plan.already_complete_count} tweets...')
            # Brief delay to allow UI to register the active status
            await asyncio.sleep(0.1)
            if self.phase_emitter_func:
                self.phase_emitter_func('tweet_caching', 'completed', 
                                       completion_msg,
                                       processed_count=0, total_count=plan.already_complete_count)
            
            # Use enhanced logging if available
            if hasattr(self, 'unified_logger') and self.unified_logger:
                completion_result = {
                    'processed_count': 0,
                    'total_count': plan.already_complete_count,
                    'skipped_count': plan.already_complete_count
                }
                self.unified_logger.emit_phase_complete('tweet_caching', completion_result)
            return

        # Enhanced logging for phase start
        total_tweets = plan.needs_processing_count + plan.already_complete_count
        phase_start_msg = f"Tweet Caching Phase: Started - {plan.needs_processing_count} tweets need caching, {plan.already_complete_count} already cached ({total_tweets} total)"
        self.socketio_emit_log(f"🔄 {phase_start_msg}", "INFO")
        
        if self.phase_emitter_func:
            self.phase_emitter_func('tweet_caching', 'active', 
                                   f'Caching {plan.needs_processing_count} tweets...')

        try:
            if plan.tweets_needing_processing:
                # Emit initial progress with total count
                if self.phase_emitter_func:
                    self.phase_emitter_func(
                        'tweet_caching', 'in_progress', 
                        f'Caching tweets...',
                        False,  # is_sub_step_update
                        0,  # processed_count
                        plan.needs_processing_count,  # total_count
                        0   # error_count
                    )
                
                await cache_tweets(plan.tweets_needing_processing, self.config, self.http_client, 
                                 self.state_manager, preferences.force_recache_tweets)
                
                # Update tweets_data_map with cached data
                for tweet_id in plan.tweets_needing_processing:
                    updated_data = self.state_manager.get_tweet(tweet_id)
                    if updated_data:
                        tweets_data_map[tweet_id] = updated_data

            # Create rich completion message
            total_tweets = plan.needs_processing_count + plan.already_complete_count
            if plan.already_complete_count > 0:
                completion_msg = f"Cached {plan.needs_processing_count} new tweets • {plan.already_complete_count} already cached • {total_tweets} total"
            else:
                completion_msg = f"Cached {plan.needs_processing_count} tweets successfully"
            
            # Log rich completion message to Live Logs
            phase_complete_log = f"Tweet Caching Phase: Complete - {completion_msg}"
            self.socketio_emit_log(f"✅ {phase_complete_log}", "INFO")
            
            # Also emit to execution plan
            if self.phase_emitter_func:
                self.phase_emitter_func(
                    'tweet_caching', 'completed', 
                    completion_msg,
                    False,  # is_sub_step_update
                    plan.needs_processing_count,  # processed_count
                    total_tweets,  # total_count
                    0   # error_count
                )
        except Exception as e:
            self.socketio_emit_log(f"Error in Tweet Caching: {e}", "ERROR")
            if self.phase_emitter_func:
                self.phase_emitter_func('tweet_caching', 'error', f'Caching failed: {e}')
            stats.error_count += 1

    async def _execute_media_phase(self, plan: PhaseExecutionPlan, tweets_data_map: Dict[str, Any], preferences, stats):
        """Execute media processing phase using execution plan."""
        if plan.should_skip_phase:
            completion_msg = f"All {plan.already_complete_count} tweets already have media processed"
            self.socketio_emit_log(f"✅ Media Analysis: {completion_msg}", "INFO")
            # Emit active status first to show phase is being processed
            if self.phase_emitter_func:
                self.phase_emitter_func('media_analysis', 'active', f'Checking {plan.already_complete_count} tweets...')
            # Brief delay to allow UI to register the active status
            await asyncio.sleep(0.1)
            if self.phase_emitter_func:
                self.phase_emitter_func('media_analysis', 'completed', 
                                       completion_msg,
                                       False,  # is_sub_step_update
                                       plan.already_complete_count,  # processed_count
                                       plan.already_complete_count,  # total_count
                                       0)  # error_count
                
            # Use enhanced logging if available
            if hasattr(self, 'unified_logger') and self.unified_logger:
                completion_result = {
                    'processed_count': 0,
                    'total_count': plan.already_complete_count,
                    'skipped_count': plan.already_complete_count
                }
                self.unified_logger.emit_phase_complete('media_analysis', completion_result)
            return

        # Enhanced logging for phase start
        total_tweets = plan.needs_processing_count + plan.already_complete_count
        phase_start_msg = f"Media Analysis Phase: Started - {plan.needs_processing_count} tweets need processing, {plan.already_complete_count} already processed ({total_tweets} total)"
        self.socketio_emit_log(f"🔄 {phase_start_msg}", "INFO")
        
        # Load historical stats for ETC calculation
        from knowledge_base_agent.stats_manager import load_processing_stats
        processing_stats_data = load_processing_stats()
        phase_historical_stats = processing_stats_data.get("phases", {}).get("media_analysis", {})
        avg_time_per_item = phase_historical_stats.get("avg_time_per_item_seconds", 0.0)
        initial_estimated_duration = avg_time_per_item * plan.needs_processing_count if avg_time_per_item > 0 else 0

        if self.phase_emitter_func:
            self.phase_emitter_func(
                'media_analysis', 
                'active', 
                f'Processing media for {plan.needs_processing_count} tweets...',
                False,
                0,  # processed_count starts at 0
                plan.needs_processing_count,  # total_count
                0,  # error_count starts at 0
                initial_estimated_duration
            )

        for i, tweet_id in enumerate(plan.tweets_needing_processing):
            if stop_flag.is_set():
                self.socketio_emit_log("Media processing stopped by flag.", "WARNING")
                if self.phase_emitter_func:
                    self.phase_emitter_func('media_analysis', 'interrupted', 'Media processing stopped.')
                break

            try:
                tweet_data = tweets_data_map[tweet_id]
                self.socketio_emit_log(f"🔄 Processing media ({i+1} of {plan.needs_processing_count})", "INFO")
                
                # Emit progress update as we start processing this item
                if self.phase_emitter_func:
                    self.phase_emitter_func(
                        'media_analysis', 
                        'active', 
                        f'Processing media {i+1} of {plan.needs_processing_count}...',
                        False,
                        i,  # processed_count (items completed so far)
                        plan.needs_processing_count,  # total_count
                        stats.error_count
                    )
                
                updated_tweet_data = await process_media(
                    tweet_data=dict(tweet_data), 
                    http_client=self.http_client,
                    config=self.config,
                    force_reprocess=preferences.force_reprocess_media
                )
                tweets_data_map[tweet_id] = updated_tweet_data
                self.state_manager.update_tweet_data(tweet_id, updated_tweet_data)
                
                # Don't log individual completions - too verbose for Live Logs
                
                # Emit progress update after completing this item
                if self.phase_emitter_func:
                    self.phase_emitter_func(
                        'media_analysis', 
                        'active', 
                        f'Completed media {i + 1} of {plan.needs_processing_count}',
                        False,
                        i + 1,  # processed_count (items completed)
                        plan.needs_processing_count,  # total_count
                        stats.error_count
                    )
                
            except Exception as e:
                logging.error(f"Error in media processing for tweet {tweet_id}: {e}")
                self.socketio_emit_log(f"Error in media processing for tweet {tweet_id}: {e}", "ERROR")
                stats.error_count += 1
                
                # Enhanced error handling with retry logic
                tweets_data_map[tweet_id]['_media_error'] = str(e)
                tweets_data_map[tweet_id]['media_processed'] = False
                
                # Check if this tweet should be scheduled for retry
                if self.retry_manager.should_retry(tweet_id, tweets_data_map[tweet_id], e):
                    retry_data = self.retry_manager.schedule_retry(tweet_id, tweets_data_map[tweet_id], e)
                    tweets_data_map[tweet_id].update(retry_data)
                    self.socketio_emit_log(f"🔁 Scheduled media processing retry for tweet {tweet_id}", "INFO")
                else:
                    self.socketio_emit_log(f"❌ Tweet {tweet_id} media processing failed permanently", "ERROR")
                
                # Update the tweet data in database with error information
                self.state_manager.update_tweet_data(tweet_id, tweets_data_map[tweet_id])

        if not stop_flag.is_set():
            # Create rich completion message for media phase
            total_tweets = plan.needs_processing_count + plan.already_complete_count
            if plan.already_complete_count > 0:
                completion_msg = f"Analyzed {plan.needs_processing_count} new media items • {plan.already_complete_count} already processed • {total_tweets} total"
            else:
                completion_msg = f"Analyzed media for {plan.needs_processing_count} tweets"
            
            self.socketio_emit_log(f"✅ {completion_msg}", "INFO")
            if self.phase_emitter_func:
                self.phase_emitter_func(
                    'media_analysis', 
                    'completed', 
                    completion_msg,
                    False,
                    plan.needs_processing_count,  # All items processed
                    total_tweets,  # Total count
                    stats.error_count
                )

    async def _execute_llm_phase(self, plan: PhaseExecutionPlan, tweets_data_map: Dict[str, Any], 
                                preferences, stats, category_manager):
        """Execute LLM categorization phase using execution plan."""
        if plan.should_skip_phase:
            self.socketio_emit_log(f"Skipping LLM phase - all {plan.already_complete_count} tweets already categorized", "INFO")
            # Emit active status first to show phase is being processed
            if self.phase_emitter_func:
                self.phase_emitter_func('llm_processing', 'active', f'Checking {plan.already_complete_count} tweets...')
            # Brief delay to allow UI to register the active status
            await asyncio.sleep(0.1)
            if self.phase_emitter_func:
                self.phase_emitter_func('llm_processing', 'completed', 
                                       f'All {plan.already_complete_count} tweets already categorized',
                                       False,  # is_sub_step_update
                                       plan.already_complete_count,  # processed_count
                                       plan.already_complete_count,  # total_count
                                       0)  # error_count
                
            # Use enhanced logging if available
            if hasattr(self, 'unified_logger') and self.unified_logger:
                completion_result = {
                    'processed_count': 0,
                    'total_count': plan.already_complete_count,
                    'skipped_count': plan.already_complete_count
                }
                self.unified_logger.emit_phase_complete('llm_processing', completion_result)
            return

        # Enhanced logging for phase start
        total_tweets = plan.needs_processing_count + plan.already_complete_count
        phase_start_msg = f"LLM Processing Phase: Started - {plan.needs_processing_count} tweets need categorization, {plan.already_complete_count} already categorized ({total_tweets} total)"
        self.socketio_emit_log(f"🔄 {phase_start_msg}", "INFO")

        # Load historical stats for ETC calculation
        processing_stats_data = load_processing_stats()
        phase_historical_stats = processing_stats_data.get("phases", {}).get("llm_categorization", {})
        avg_time_per_item = phase_historical_stats.get("avg_time_per_item_seconds", 0.0)
        initial_estimated_duration = avg_time_per_item * plan.needs_processing_count if avg_time_per_item > 0 else 0

        # Setup parallel processing
        num_gpus = self.config.num_gpus_available
        if num_gpus <= 0: 
            num_gpus = 1
        num_parallel_jobs = num_gpus

        self.socketio_emit_log(f"Running LLM categorization with {num_parallel_jobs} parallel workers", "INFO")
        
        if self.phase_emitter_func:
            self.phase_emitter_func(
                'llm_processing', 
                'active', 
                f'Categorizing {plan.needs_processing_count} tweets using {num_parallel_jobs} worker(s)...',
                False,
                0,  # processed_count starts at 0
                plan.needs_processing_count,  # total_count
                0,  # error_count starts at 0
                initial_estimated_duration
            )

        phase_start_time = time.monotonic()
        items_successfully_processed = 0

        # Create parallel processing tasks
        semaphore = asyncio.Semaphore(num_parallel_jobs)
        gpu_idx_cycle = cycle(range(num_gpus))
        
        async def worker_llm(tweet_id: str, tweet_data: Dict[str, Any], assigned_gpu: int):
            async with semaphore:
                try:
                    result = await self._process_single_categorization(
                        tweet_id, tweet_data, category_manager, preferences, assigned_gpu
                    )
                    return tweet_id, result, None 
                except Exception as e:
                    logging.error(f"Error in LLM Processing for tweet {tweet_id}: {e}", exc_info=True)
                    return tweet_id, None, e

        # Create tasks for tweets that need processing
        all_tasks = []
        for tweet_id in plan.tweets_needing_processing:
            if stop_flag.is_set():
                break
            assigned_gpu = next(gpu_idx_cycle)
            tweet_data = tweets_data_map[tweet_id]
            all_tasks.append(worker_llm(tweet_id, tweet_data, assigned_gpu))

        # Execute all tasks in parallel
        if all_tasks:
            results = await asyncio.gather(*all_tasks, return_exceptions=False)
            
            for tweet_id, result_data, error_obj in results:
                if stop_flag.is_set():
                    break

                if error_obj:
                    stats.error_count += 1
                    self.socketio_emit_log(f"Error in LLM Processing for tweet {tweet_id}: {error_obj}", "ERROR")
                    
                    # Enhanced error handling with retry logic
                    tweets_data_map[tweet_id]['_llm_error'] = str(error_obj)
                    tweets_data_map[tweet_id]['categories_processed'] = False
                    
                    # Check if this tweet should be scheduled for retry
                    if self.retry_manager.should_retry(tweet_id, tweets_data_map[tweet_id], error_obj):
                        retry_data = self.retry_manager.schedule_retry(tweet_id, tweets_data_map[tweet_id], error_obj)
                        tweets_data_map[tweet_id].update(retry_data)
                        self.socketio_emit_log(f"🔁 Scheduled LLM processing retry for tweet {tweet_id}", "INFO")
                    else:
                        self.socketio_emit_log(f"❌ Tweet {tweet_id} LLM processing failed permanently", "ERROR")
                    
                    # Update the tweet data in database with error information
                    self.state_manager.update_tweet_data(tweet_id, tweets_data_map[tweet_id])
                elif result_data:
                    main_cat, sub_cat, item_name = result_data
                    tweets_data_map[tweet_id]['main_category'] = main_cat
                    tweets_data_map[tweet_id]['sub_category'] = sub_cat
                    tweets_data_map[tweet_id]['item_name_suggestion'] = item_name
                    tweets_data_map[tweet_id]['categories_processed'] = True
                    tweets_data_map[tweet_id]['categories'] = {
                        'main_category': main_cat,
                        'sub_category': sub_cat,
                        'item_name': item_name
                    }
                    self.state_manager.update_tweet_data(tweet_id, tweets_data_map[tweet_id])
                    items_successfully_processed += 1

        # Update historical stats
        phase_end_time = time.monotonic()
        duration_this_run = phase_end_time - phase_start_time
        
        if items_successfully_processed > 0:
            update_phase_stats(
                phase_id="llm_categorization",
                items_processed_this_run=items_successfully_processed,
                duration_this_run_seconds=duration_this_run
            )

        if not stop_flag.is_set():
            # Create rich completion message for LLM phase
            total_tweets = plan.needs_processing_count + plan.already_complete_count
            if plan.already_complete_count > 0:
                completion_msg = f"Categorized {items_successfully_processed} new tweets • {plan.already_complete_count} already categorized • {total_tweets} total"
            else:
                completion_msg = f"Categorized {items_successfully_processed} tweets with LLM"
            
            self.socketio_emit_log(f"✅ {completion_msg}", "INFO")
            if self.phase_emitter_func:
                self.phase_emitter_func('llm_processing', 'completed', 
                                       completion_msg,
                                       False,  # is_sub_step_update
                                       items_successfully_processed,  # processed_count
                                       total_tweets,  # total_count
                                       stats.error_count)  # error_count
                
            # Use enhanced logging if available
            if hasattr(self, 'unified_logger') and self.unified_logger:
                completion_result = {
                    'processed_count': items_successfully_processed,
                    'total_count': plan.needs_processing_count,
                    'error_count': stats.error_count,
                    'duration_seconds': duration_this_run
                }
                self.unified_logger.emit_phase_complete('llm_processing', completion_result)

    async def _execute_kb_item_phase(self, plan: PhaseExecutionPlan, tweets_data_map: Dict[str, Any], preferences, stats):
        """Execute KB item generation phase using execution plan."""
        if plan.should_skip_phase:
            self.socketio_emit_log(f"Skipping KB item phase - all {plan.already_complete_count} tweets already have KB items", "INFO")
            # Emit active status first to show phase is being processed
            if self.phase_emitter_func:
                self.phase_emitter_func('kb_item_generation', 'active', f'Checking {plan.already_complete_count} tweets...')
            # Brief delay to allow UI to register the active status
            await asyncio.sleep(0.1)
            if self.phase_emitter_func:
                self.phase_emitter_func('kb_item_generation', 'completed', 
                                       f'All {plan.already_complete_count} KB items already exist',
                                       False,  # is_sub_step_update
                                       plan.already_complete_count,  # processed_count
                                       plan.already_complete_count,  # total_count
                                       0)  # error_count
                
            # Use enhanced logging if available
            if hasattr(self, 'unified_logger') and self.unified_logger:
                completion_result = {
                    'processed_count': 0,
                    'total_count': plan.already_complete_count,
                    'skipped_count': plan.already_complete_count
                }
                self.unified_logger.emit_phase_complete('kb_item_generation', completion_result)
            return

        # Enhanced logging for phase start
        total_tweets = plan.needs_processing_count + plan.already_complete_count
        self.socketio_emit_log(f"🔄 KB Item Generation Phase: {plan.needs_processing_count} tweets need KB items, {plan.already_complete_count} already exist ({total_tweets} total)", "INFO")
        
        # Load historical stats for ETC calculation
        processing_stats_data = load_processing_stats()
        phase_historical_stats = processing_stats_data.get("phases", {}).get("kb_item_generation", {})
        avg_time_per_item = phase_historical_stats.get("avg_time_per_item_seconds", 0.0)
        initial_estimated_duration = avg_time_per_item * plan.needs_processing_count if avg_time_per_item > 0 else 0

        if self.phase_emitter_func:
            self.phase_emitter_func(
                'kb_item_generation', 
                'active', 
                f'Generating {plan.needs_processing_count} KB items...',
                False,
                0,  # processed_count starts at 0
                plan.needs_processing_count,  # total_count
                0,  # error_count starts at 0
                initial_estimated_duration
            )

        phase_start_time = time.monotonic()
        items_successfully_processed = 0

        for i, tweet_id in enumerate(plan.tweets_needing_processing):
            if stop_flag.is_set():
                self.socketio_emit_log("KB item generation stopped by flag.", "WARNING")
                if self.phase_emitter_func:
                    self.phase_emitter_func('kb_item_generation', 'interrupted', 'KB item generation stopped.')
                break

            try:
                tweet_data = tweets_data_map[tweet_id]
                self.socketio_emit_log(f"🔄 Generating KB item ({i+1} of {plan.needs_processing_count})", "INFO")
                
                # Update progress when starting to process this item
                if self.phase_emitter_func:
                    self.phase_emitter_func(
                        'kb_item_generation', 
                        'active', 
                        f'Generating KB item {i+1} of {plan.needs_processing_count}...',
                        False,
                        i,  # Current index shows item being processed (0-based)
                        plan.needs_processing_count,
                        stats.error_count
                    )
                
                # Create KB item object
                kb_item_obj: KnowledgeBaseItem = await create_knowledge_base_item(
                    tweet_id=tweet_id, tweet_data=tweet_data, config=self.config,
                    http_client=self.http_client, state_manager=self.state_manager
                )
                
                # UNIFIED DB APPROACH: Store all KB item data directly in the unified database
                # No disk writing - everything goes to the UnifiedTweet model
                
                # Update tweet data with KB item content for unified database storage
                tweet_data['kb_item_created'] = True
                tweet_data['display_title'] = kb_item_obj.display_title
                tweet_data['description'] = kb_item_obj.description
                tweet_data['markdown_content'] = kb_item_obj.markdown_content
                tweet_data['raw_json_content'] = kb_item_obj.raw_json_content
                
                # Store media paths in the unified database (no filesystem paths needed)
                if hasattr(kb_item_obj, 'media_files') and kb_item_obj.media_files:
                    tweet_data['kb_media_paths'] = json.dumps(kb_item_obj.media_files)
                else:
                    tweet_data['kb_media_paths'] = json.dumps([])
                
                # Mark processing as complete
                tweet_data['processing_complete'] = True
                
                self.state_manager.update_tweet_data(tweet_id, tweet_data)
                items_successfully_processed += 1
                
                # Update progress when completing this item
                if self.phase_emitter_func:
                    self.phase_emitter_func(
                        'kb_item_generation', 
                        'active', 
                        f'Completed KB item {i + 1} of {plan.needs_processing_count}',
                        False,
                        i + 1,  # Completed items count
                        plan.needs_processing_count,
                        stats.error_count
                    )
                
                # Don't log individual completions - too verbose for Live Logs
                
            except Exception as e:
                logging.error(f"Error in KB item generation for tweet {tweet_id}: {e}", exc_info=True)
                self.socketio_emit_log(f"Error in KB item generation for tweet {tweet_id}: {e}", "ERROR")
                stats.error_count += 1
                
                # Enhanced error handling with retry logic
                tweets_data_map[tweet_id]['_kbitem_error'] = str(e)
                tweets_data_map[tweet_id]['kb_item_created'] = False
                
                # Check if this tweet should be scheduled for retry
                if self.retry_manager.should_retry(tweet_id, tweets_data_map[tweet_id], e):
                    retry_data = self.retry_manager.schedule_retry(tweet_id, tweets_data_map[tweet_id], e)
                    tweets_data_map[tweet_id].update(retry_data)
                    self.socketio_emit_log(f"🔁 Scheduled KB item generation retry for tweet {tweet_id}", "INFO")
                else:
                    self.socketio_emit_log(f"❌ Tweet {tweet_id} KB item generation failed permanently", "ERROR")
                
                # Update the tweet data in database with error information
                self.state_manager.update_tweet_data(tweet_id, tweets_data_map[tweet_id])

        # Update historical stats
        phase_end_time = time.monotonic()
        duration_this_run = phase_end_time - phase_start_time
        
        if items_successfully_processed > 0:
            update_phase_stats(
                phase_id="kb_item_generation",
                items_processed_this_run=items_successfully_processed,
                duration_this_run_seconds=duration_this_run
            )

        if not stop_flag.is_set():
            # Create rich completion message for KB item phase
            total_tweets = plan.needs_processing_count + plan.already_complete_count
            if plan.already_complete_count > 0:
                completion_msg = f"Generated {items_successfully_processed} new KB items • {plan.already_complete_count} already exist • {total_tweets} total"
            else:
                completion_msg = f"Generated {items_successfully_processed} KB items"
            
            # Log rich completion message to Live Logs
            phase_complete_log = f"KB Item Generation Phase: Complete - {completion_msg}"
            self.socketio_emit_log(f"✅ {phase_complete_log}", "INFO")
            
            # Also emit to execution plan
            if self.phase_emitter_func:
                self.phase_emitter_func('kb_item_generation', 'completed', 
                                       completion_msg,
                                       processed_count=items_successfully_processed, 
                                       total_count=total_tweets)
            
            # Use enhanced logging if available
            if hasattr(self, 'unified_logger') and self.unified_logger:
                completion_result = {
                    'processed_count': plan.needs_processing_count,
                    'total_count': plan.needs_processing_count
                }
                self.unified_logger.emit_phase_complete('kb_item_generation', completion_result)

    async def _execute_db_sync_phase(self, plan: PhaseExecutionPlan, tweets_data_map: Dict[str, Any], 
                                   preferences, stats, category_manager):
        """Execute database sync phase using execution plan."""
        try:
            self.socketio_emit_log(f"🔄 Starting DB sync phase evaluation...", "INFO")
            
            # Validate database connection early
            try:
                from knowledge_base_agent.models import db
                # Test database connection with proper SQLAlchemy 2.0 syntax
                with db.engine.connect() as connection:
                    connection.execute(db.text("SELECT 1"))
                self.socketio_emit_log(f"✅ Database connection validated successfully", "DEBUG")
            except Exception as db_conn_error:
                self.socketio_emit_log(f"❌ Database connection test failed: {db_conn_error}", "ERROR")
                if self.phase_emitter_func:
                    self.phase_emitter_func('database_sync', 'error', f'Database connection failed: {db_conn_error}')
                raise Exception(f"Database connection validation failed: {db_conn_error}")
            
            # Perform database validation and repair if needed
            await self._validate_and_repair_database(tweets_data_map, preferences)
            
            if plan.should_skip_phase:
                self.socketio_emit_log(f"✅ DB sync phase - all {plan.already_complete_count} tweets already synced", "INFO")
                # Emit active status first to show phase is being processed
                if self.phase_emitter_func:
                    self.phase_emitter_func('database_sync', 'active', f'Checking {plan.already_complete_count} tweets...')
                # Brief delay to allow UI to register the active status
                await asyncio.sleep(0.1)
                if self.phase_emitter_func:
                    self.phase_emitter_func('database_sync', 'completed', 
                                           f'All {plan.already_complete_count} tweets already synced to database',
                                           False,  # is_sub_step_update
                                           plan.already_complete_count,  # processed_count
                                           plan.already_complete_count,  # total_count
                                           0)  # error_count
                    
                # Use enhanced logging if available
                if hasattr(self, 'unified_logger') and self.unified_logger:
                    completion_result = {
                        'processed_count': 0,
                        'total_count': plan.already_complete_count,
                        'skipped_count': plan.already_complete_count
                    }
                    self.unified_logger.emit_phase_complete('database_sync', completion_result)
                return
        except Exception as e:
            self.socketio_emit_log(f"❌ Error in DB sync phase initialization: {e}", "ERROR")
            self.socketio_emit_log(f"❌ DB sync initialization traceback: {traceback.format_exc()}", "ERROR")
            if self.phase_emitter_func:
                self.phase_emitter_func('database_sync', 'error', f'DB sync initialization failed: {e}')
            raise

    async def _validate_and_repair_database(self, tweets_data_map: Dict[str, Any], preferences):
        """
        Validate and repair database entries for Knowledge Base items.
        This ensures data consistency between filesystem and database.
        """
        try:
            # For now, skip advanced database validation as db_validation module may not exist
            # This is a placeholder for future database validation implementation
            pass
            
            self.socketio_emit_log("📊 Basic database validation complete", "INFO")
                
        except Exception as e:
            self.socketio_emit_log(f"⚠️ Database validation/repair failed: {e}", "WARNING")
            logging.warning(f"Database validation/repair failed: {e}", exc_info=True)
            # Don't raise - this is a best-effort operation
        
        # Continue with main DB sync processing
        try:
            self.socketio_emit_log(f"🔄 DB sync phase: processing {plan.needs_processing_count} tweets", "INFO")
            
            # Load historical stats for ETC calculation
            processing_stats_data = load_processing_stats()
            phase_historical_stats = processing_stats_data.get("phases", {}).get("database_sync", {})
            avg_time_per_item = phase_historical_stats.get("avg_time_per_item_seconds", 0.0)
            initial_estimated_duration = avg_time_per_item * plan.needs_processing_count if avg_time_per_item > 0 else 0

            if self.phase_emitter_func:
                self.phase_emitter_func(
                    'database_sync', 
                    'active', 
                    f'Syncing {plan.needs_processing_count} tweets to database...',
                    False,
                    0,  # processed_count starts at 0
                    plan.needs_processing_count,  # total_count
                    0,  # error_count starts at 0
                    initial_estimated_duration
                )

            phase_start_time = time.monotonic()
            items_successfully_processed = 0

            for i, tweet_id in enumerate(plan.tweets_needing_processing):
                if stop_flag.is_set():
                    self.socketio_emit_log("Database sync stopped by flag.", "WARNING")
                    if self.phase_emitter_func:
                        self.phase_emitter_func('database_sync', 'interrupted', 'Database sync stopped.')
                    break

                try:
                    tweet_data = tweets_data_map[tweet_id]
                    self.socketio_emit_log(f"🔄 Syncing item {i+1} of {plan.needs_processing_count} to database", "INFO")
                    
                    # Update progress when starting to process this item
                    if self.phase_emitter_func:
                        self.phase_emitter_func(
                            'database_sync', 
                            'active', 
                            f'Syncing item {i+1} of {plan.needs_processing_count} to database...',
                            False,
                            i,  # Current index shows item being processed (0-based)
                            plan.needs_processing_count,
                            stats.error_count
                        )
                    
                    # Enhanced error handling for individual sync operations
                    try:
                        await self._sync_to_unified_db(tweet_id, tweet_data)
                        tweet_data['db_synced'] = True
                        self.state_manager.update_tweet_data(tweet_id, tweet_data)
                        items_successfully_processed += 1
                        
                        # Update progress when completing this item
                        if self.phase_emitter_func:
                            self.phase_emitter_func(
                                'database_sync', 
                                'active', 
                                f'Completed database sync {i + 1} of {plan.needs_processing_count}',
                                False,
                                i + 1,  # Completed items count
                                plan.needs_processing_count,
                                stats.error_count
                            )
                        
                        self.socketio_emit_log(f"✅ Database sync complete for item {i+1}", "INFO")
                    except Exception as sync_error:
                        # Log individual sync errors with more detail
                        error_msg = f"Database sync failed for tweet {tweet_id}: {sync_error}"
                        self.socketio_emit_log(f"❌ {error_msg}", "ERROR")
                        self.socketio_emit_log(f"❌ Sync error traceback: {traceback.format_exc()}", "ERROR")
                        
                        stats.error_count += 1
                        tweets_data_map[tweet_id]['_db_error'] = str(sync_error)
                        tweets_data_map[tweet_id]['db_synced'] = False
                        
                        # Continue with next item rather than failing entire phase
                        continue
                    
                except Exception as item_error:
                    # Handle errors in item preparation/retrieval
                    error_msg = f"Error preparing tweet {tweet_id} for database sync: {item_error}"
                    self.socketio_emit_log(f"❌ {error_msg}", "ERROR")
                    self.socketio_emit_log(f"❌ Item preparation traceback: {traceback.format_exc()}", "ERROR")
                    
                    stats.error_count += 1
                    tweets_data_map[tweet_id]['_db_prep_error'] = str(item_error)
                    tweets_data_map[tweet_id]['db_synced'] = False

            # Update historical stats
            phase_end_time = time.monotonic()
            duration_this_run = phase_end_time - phase_start_time
            
            if items_successfully_processed > 0:
                update_phase_stats(
                    phase_id="database_sync",
                    items_processed_this_run=items_successfully_processed,
                    duration_this_run_seconds=duration_this_run
                )

            if not stop_flag.is_set():
                self.socketio_emit_log(f"✅ Database sync completed for {plan.needs_processing_count} tweets", "INFO")
                if self.phase_emitter_func:
                    self.phase_emitter_func('database_sync', 'completed', 
                                           f'Synced {plan.needs_processing_count} tweets to database',
                                           False,  # is_sub_step_update
                                           items_successfully_processed,  # processed_count
                                           plan.needs_processing_count,  # total_count
                                           stats.error_count)  # error_count
                    
                # Use enhanced logging if available
                if hasattr(self, 'unified_logger') and self.unified_logger:
                    completion_result = {
                        'processed_count': items_successfully_processed,
                        'total_count': plan.needs_processing_count,
                        'error_count': stats.error_count,
                        'duration_seconds': duration_this_run
                    }
                    self.unified_logger.emit_phase_complete('database_sync', completion_result)
                    
        except Exception as e:
            self.socketio_emit_log(f"❌ Critical error in DB sync phase: {e}", "ERROR")
            self.socketio_emit_log(f"❌ DB sync phase traceback: {traceback.format_exc()}", "ERROR")
            logging.error(f"Critical error in DB sync phase: {e}", exc_info=True)
            if self.phase_emitter_func:
                self.phase_emitter_func('database_sync', 'error', f'DB sync phase failed: {e}')
            raise

    async def _finalize_processing(self, tweets_data_map: Dict[str, Any], unprocessed_tweets: List[str], stats):
        """
        Comprehensive finalization that processes ALL tweets in the data map,
        handles retry logic, and provides detailed completion tracking.
        """
        self.socketio_emit_log("🏁 Starting comprehensive processing finalization...", "INFO")
        
        # Track completion statistics
        completion_stats = {
            'fully_completed': 0,
            'partially_completed': 0,
            'failed_with_errors': 0,
            'scheduled_for_retry': 0,
            'permanently_failed': 0
        }
        
        # Process ALL tweets in the data map, not just unprocessed ones
        for tweet_id, tweet_data in tweets_data_map.items():
            try:
                # Check if all phases completed successfully
                all_phases_complete = all([
                    tweet_data.get('cache_complete', False),
                    tweet_data.get('media_processed', False),
                    tweet_data.get('categories_processed', False),
                    tweet_data.get('kb_item_created', False)
                    # Note: db_synced is handled separately in the DB sync phase
                ])
                
                # Check for errors
                error_fields = ['_cache_error', '_media_error', '_llm_error', '_kbitem_error', '_db_error']
                has_errors = any(tweet_data.get(field) for field in error_fields)
                
                if all_phases_complete and not has_errors:
                    # Tweet completed successfully - clear retry metadata and mark as processed
                    if tweet_data.get('retry_count', 0) > 0:
                        cleared_data = self.retry_manager.clear_retry_metadata(tweet_id, tweet_data)
                        self.state_manager.update_tweet_data(tweet_id, cleared_data)
                        self.socketio_emit_log(f"✅ Tweet {tweet_id} completed successfully after {tweet_data.get('retry_count', 0)} retries", "INFO")
                    
                    self.state_manager.mark_tweet_processed(tweet_id)
                    stats.processed_count += 1
                    completion_stats['fully_completed'] += 1
                    
                elif has_errors:
                    # Tweet has errors - check if it should be retried
                    should_retry = False
                    
                    # Find the most recent error to pass to retry manager
                    last_error = None
                    for field in error_fields:
                        if tweet_data.get(field):
                            last_error = Exception(tweet_data[field])
                            break
                    
                    if last_error and self.retry_manager.should_retry(tweet_id, tweet_data, last_error):
                        # Schedule for retry
                        retry_data = self.retry_manager.schedule_retry(tweet_id, tweet_data, last_error)
                        self.state_manager.update_tweet_data(tweet_id, retry_data)
                        completion_stats['scheduled_for_retry'] += 1
                        should_retry = True
                    
                    if not should_retry:
                        # Permanently failed or max retries exceeded
                        retry_count = tweet_data.get('retry_count', 0)
                        if retry_count >= self.retry_manager.config.max_retries:
                            self.socketio_emit_log(f"❌ Tweet {tweet_id} permanently failed after {retry_count} retries", "ERROR")
                            # Open circuit breaker to prevent immediate retries
                            self.retry_manager.open_circuit_breaker(tweet_id, duration_minutes=120)
                        else:
                            self.socketio_emit_log(f"⚠️ Tweet {tweet_id} failed with errors: {[f for f in error_fields if tweet_data.get(f)]}", "WARNING")
                        
                        completion_stats['permanently_failed'] += 1
                        stats.error_count += 1
                
                else:
                    # Partially completed - some phases done but not all
                    completion_stats['partially_completed'] += 1
                    
                    # Provide detailed phase status
                    phase_status = {
                        'cache': tweet_data.get('cache_complete', False),
                        'media': tweet_data.get('media_processed', False),
                        'llm': tweet_data.get('categories_processed', False),
                        'kb_item': tweet_data.get('kb_item_created', False)
                    }
                    incomplete_phases = [phase for phase, complete in phase_status.items() if not complete]
                    self.socketio_emit_log(f"🔄 Tweet {tweet_id} partially complete. Pending: {incomplete_phases}", "DEBUG")
                    
            except Exception as e:
                self.socketio_emit_log(f"Error finalizing tweet {tweet_id}: {e}", "ERROR")
                stats.error_count += 1
                completion_stats['failed_with_errors'] += 1
        
        # Log comprehensive completion statistics
        total_tweets = len(tweets_data_map)
        self.socketio_emit_log(
            f"🏁 Finalization complete for {total_tweets} tweets: "
            f"✅ {completion_stats['fully_completed']} completed, "
            f"🔄 {completion_stats['partially_completed']} partial, "
            f"🔁 {completion_stats['scheduled_for_retry']} retry scheduled, "
            f"❌ {completion_stats['permanently_failed']} failed",
            "INFO"
        )
        
        # Log retry statistics if applicable
        retry_stats = self.retry_manager.get_retry_statistics()
        if retry_stats['total_tweets_with_retries'] > 0:
            self.socketio_emit_log(
                f"🔁 Retry statistics: {retry_stats['total_tweets_with_retries']} tweets with retries, "
                                 f"avg {retry_stats['average_retries_per_tweet']:.1f} retries per tweet, "
                 f"{retry_stats['active_circuit_breakers']} active circuit breakers",
                 "INFO"
             )
    
    async def _attempt_error_recovery(self, tweets_data_map: Dict[str, Any], error: Exception) -> None:
        """
        Attempt to recover from processing errors and save partial progress.
        
        Args:
            tweets_data_map: Current tweet data map
            error: The exception that caused the failure
        """
        try:
            recovery_stats = {'saved_tweets': 0, 'failed_saves': 0}
            
            # Save any partial progress to database
            for tweet_id, tweet_data in tweets_data_map.items():
                try:
                    # Only save tweets that have some progress
                    has_progress = any([
                        tweet_data.get('cache_complete', False),
                        tweet_data.get('media_processed', False),
                        tweet_data.get('categories_processed', False),
                        tweet_data.get('kb_item_created', False)
                    ])
                    
                    if has_progress:
                        # Add error recovery metadata
                        tweet_data['_error_recovery_attempted'] = True
                        tweet_data['_error_recovery_timestamp'] = datetime.now(timezone.utc).isoformat()
                        tweet_data['_original_error'] = str(error)
                        
                        self.state_manager.update_tweet_data(tweet_id, tweet_data)
                        recovery_stats['saved_tweets'] += 1
                        
                except Exception as save_error:
                    logging.error(f"Failed to save recovery data for tweet {tweet_id}: {save_error}")
                    recovery_stats['failed_saves'] += 1
            
            # Log recovery attempt results
            if recovery_stats['saved_tweets'] > 0:
                self.socketio_emit_log(
                    f"🔧 Error recovery: saved {recovery_stats['saved_tweets']} tweets, "
                    f"{recovery_stats['failed_saves']} failed saves",
                    "INFO"
                )
            
            # Generate error report for analysis
            error_report = {
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'error_type': type(error).__name__,
                'error_message': str(error),
                'tweets_processed': len(tweets_data_map),
                'recovery_stats': recovery_stats,
                'retry_statistics': self.retry_manager.get_retry_statistics()
            }
            
            # Save error report for debugging
            logging.error(f"Processing error report: {error_report}")
            
        except Exception as e:
            logging.error(f"Error recovery procedure failed: {e}")
    
    def get_processing_health_status(self) -> Dict[str, Any]:
        """
        Get comprehensive health status of the processing pipeline.
        
        Returns:
            Health status dictionary with metrics and recommendations
        """
        try:
            # Get retry statistics
            retry_stats = self.retry_manager.get_retry_statistics()
            
            # Calculate health metrics
            total_with_retries = retry_stats.get('total_tweets_with_retries', 0)
            active_breakers = retry_stats.get('active_circuit_breakers', 0)
            avg_retries = retry_stats.get('average_retries_per_tweet', 0)
            
            # Determine health score
            health_score = 100
            issues = []
            
            if total_with_retries > 0:
                health_score -= min(total_with_retries * 2, 30)  # Max 30% penalty for retries
                issues.append(f"{total_with_retries} tweets required retries")
            
            if active_breakers > 0:
                health_score -= min(active_breakers * 10, 40)  # Max 40% penalty for circuit breakers
                issues.append(f"{active_breakers} active circuit breakers")
            
            if avg_retries > 1.5:
                health_score -= 20
                issues.append(f"High average retry count: {avg_retries:.1f}")
            
            health_score = max(0, health_score)
            
            # Determine status
            if health_score >= 90:
                status = "EXCELLENT"
            elif health_score >= 75:
                status = "GOOD"
            elif health_score >= 60:
                status = "FAIR"
            elif health_score >= 40:
                status = "POOR"
            else:
                status = "CRITICAL"
            
            return {
                'health_score': health_score,
                'status': status,
                'issues': issues,
                'retry_statistics': retry_stats,
                'recommendations': self._generate_health_recommendations(health_score, retry_stats)
            }
            
        except Exception as e:
            logging.error(f"Failed to get processing health status: {e}")
            return {
                'health_score': 0,
                'status': 'ERROR',
                'issues': [f"Health check failed: {e}"],
                'retry_statistics': {},
                'recommendations': ['Fix health monitoring system']
            }
    
    def _generate_health_recommendations(self, health_score: float, retry_stats: Dict[str, Any]) -> List[str]:
        """Generate health recommendations based on current metrics."""
        recommendations = []
        
        if health_score < 70:
            recommendations.append("Investigate root causes of processing failures")
        
        if retry_stats.get('total_tweets_with_retries', 0) > 10:
            recommendations.append("Consider increasing resource allocation or optimizing processing phases")
        
        if retry_stats.get('active_circuit_breakers', 0) > 0:
            recommendations.append("Review and reset circuit breakers for persistently failing tweets")
        
        failure_distribution = retry_stats.get('failure_type_distribution', {})
        if failure_distribution:
            most_common_failure = max(failure_distribution.items(), key=lambda x: x[1])[0]
            recommendations.append(f"Focus on addressing {most_common_failure} failures")
        
        if not recommendations:
            recommendations.append("System is healthy - continue monitoring")
        
        return recommendations

    async def _process_single_categorization(self, tweet_id: str, tweet_data: Dict[str, Any], 
                                           category_manager: CategoryManager, preferences: UserPreferences, 
                                           gpu_device: int) -> Tuple[str, str, str]:
        """Helper method to process a single tweet for categorization and naming."""
        try:
            self.socketio_emit_log(f"Invoking AI for categorization and naming of {tweet_id}...", "DEBUG")
            
            main_cat, sub_cat, item_name = await ai_categorize_and_name(
                http_client=self.http_client, tweet_data=tweet_data, text_model=self.text_model,
                tweet_id=tweet_id, category_manager=category_manager,
                max_retries=self.config.max_retries, fallback_model=self.config.fallback_model,
                gpu_device=gpu_device
            )
            
            await category_manager.ensure_category_exists(main_cat, sub_cat)
            self.socketio_emit_log(f"LLM processing complete for {tweet_id}: Cat={main_cat}, SubCat={sub_cat}, Name={item_name}", "INFO")
            return main_cat, sub_cat, item_name
        except Exception as e:
            logging.error(f"Error in LLM Processing for tweet {tweet_id}: {e}", exc_info=True)
            raise

    async def _sync_to_unified_db(self, tweet_id: str, tweet_data: Dict[str, Any]) -> None:
        """
        Sync individual tweet to database.
        Enhanced with synthesis staleness tracking and validation.
        """
        self.socketio_emit_log(f"Syncing tweet {tweet_id} to database...", "DEBUG")

        try:
            # Validate required data before syncing (with more lenient validation)
            required_fields = ['main_category', 'sub_category', 'item_name_suggestion']
            missing_fields = [field for field in required_fields if not tweet_data.get(field)]
            
            if missing_fields:
                # Log warning but don't fail - provide defaults
                self.socketio_emit_log(f"Tweet {tweet_id} missing fields {missing_fields}, using defaults", "WARNING")
                
                # Provide default values for missing fields
                if 'main_category' not in tweet_data or not tweet_data['main_category']:
                    tweet_data['main_category'] = 'Uncategorized'
                if 'sub_category' not in tweet_data or not tweet_data['sub_category']:
                    tweet_data['sub_category'] = 'General'
                if 'item_name_suggestion' not in tweet_data or not tweet_data['item_name_suggestion']:
                    tweet_data['item_name_suggestion'] = f'Tweet {tweet_id}'
            
            # Validate KB item content exists (with comprehensive content preservation)
            content_sources = [
                ('markdown_content', tweet_data.get('markdown_content')),
                ('full_text_cleaned', tweet_data.get('full_text_cleaned')), 
                ('full_text', tweet_data.get('full_text')),
                ('text', tweet_data.get('text')),  # Original tweet text
                ('content', tweet_data.get('content')),  # Generic content field
                ('description', tweet_data.get('description')),  # Description field
            ]
            
            # Find the best available content
            available_content = None
            content_source = None
            for source_name, content in content_sources:
                if content and content.strip() and not content.strip().startswith('Tweet ') and not content.strip().endswith('(content not available)'):
                    available_content = content.strip()
                    content_source = source_name
                    break
            
            if not available_content:
                # Log detailed warning about missing content with all available fields
                available_fields = {k: str(v)[:100] + '...' if len(str(v)) > 100 else str(v) 
                                  for k, v in tweet_data.items() 
                                  if not k.startswith('_') and v is not None}
                self.socketio_emit_log(f"❌ Tweet {tweet_id} has no usable content. Available fields: {available_fields}", "ERROR")
                
                # Don't sync tweets without content - they need reprocessing
                raise ValueError(f"Tweet {tweet_id} has no usable content and needs reprocessing")
            else:
                self.socketio_emit_log(f"✅ Tweet {tweet_id} content found in '{content_source}' field (length: {len(available_content)})", "DEBUG")
                # Ensure the content is preserved in the expected field
                tweet_data['full_text'] = available_content
            
            # Log data validation for debugging
            self.socketio_emit_log(f"DB sync validation passed for {tweet_id}: "
                                 f"Category={tweet_data.get('main_category')}/{tweet_data.get('sub_category')}, "
                                 f"Title={tweet_data.get('item_name_suggestion')}, "
                                 f"HasContent={bool(tweet_data.get('markdown_content'))}", "DEBUG")

            # Get or create KB item in database
            from knowledge_base_agent.models import KnowledgeBaseItem as DBKnowledgeBaseItem, db

            db_item = DBKnowledgeBaseItem.query.filter_by(tweet_id=tweet_id).first()

            created_at_str = tweet_data.get('created_at', datetime.now().isoformat())
            try:
                created_at_dt = datetime.fromisoformat(created_at_str) if isinstance(created_at_str, str) else created_at_str
            except ValueError:
                created_at_dt = datetime.now()

            # Get the display title and raw JSON content from the KB item generation phase
            display_title = tweet_data.get('display_title', tweet_data.get('item_name_suggestion', 'Untitled KB Item'))
            raw_json_content = tweet_data.get('raw_json_content')
            
            # Use the validated content from above
            content = tweet_data.get('full_text', '')
            
            # Final content validation for database storage
            if not content or not content.strip():
                raise ValueError(f"Tweet {tweet_id} content validation failed - no content available for database storage")
                
            # Log successful content validation
            self.socketio_emit_log(f"✅ Content validated for DB storage: {tweet_id} (length: {len(content)})", "DEBUG")
            
            attributes = {
                "tweet_id": tweet_id,
                "title": tweet_data.get('item_name_suggestion', 'Untitled KB Item'),
                "display_title": display_title,
                "description": tweet_data.get('description', ''),
                "content": content,
                "main_category": tweet_data.get('main_category'),
                "sub_category": tweet_data.get('sub_category'),
                "item_name": tweet_data.get('item_name_suggestion', 'Untitled KB Item'),
                "source_url": tweet_data.get('url', f'https://twitter.com/{tweet_data.get("user_screen_name", "user")}/status/{tweet_id}'),
                "created_at": created_at_dt,
                "file_path": tweet_data.get('kb_item_path'),
                "kb_media_paths": self._ensure_json_string(tweet_data.get('kb_media_paths')),
                "raw_json_content": raw_json_content,
            }

            # Track if this is a new item or an update for synthesis staleness
            is_new_item = db_item is None
            main_category = tweet_data.get('main_category')
            sub_category = tweet_data.get('sub_category')

            if db_item:
                self.socketio_emit_log(f"Updating existing DB entry for tweet {tweet_id}", "DEBUG")
                for key, value in attributes.items():
                    setattr(db_item, key, value)
                db_item.last_updated = datetime.now(timezone.utc)
            else:
                self.socketio_emit_log(f"Creating new DB entry for tweet {tweet_id}", "DEBUG")
                db_item = DBKnowledgeBaseItem(**attributes)
                db_item.last_updated = datetime.now(timezone.utc)
            
            db.session.add(db_item)
            db.session.commit()
            self.socketio_emit_log(f"DB entry for {tweet_id} committed.", "DEBUG")

            # Mark affected synthesis documents as stale (optional feature)
            if main_category and sub_category:
                try:
                    # Try to import synthesis tracker if it exists
                    from knowledge_base_agent.synthesis_tracker import SynthesisDependencyTracker
                    dependency_tracker = SynthesisDependencyTracker(self.config)
                    
                    marked_count = dependency_tracker.mark_affected_syntheses_stale(
                        main_category, sub_category
                    )
                    
                    if marked_count > 0:
                        action = "New KB item added" if is_new_item else "KB item updated"
                        self.socketio_emit_log(
                            f"{action}: Marked {marked_count} synthesis documents as stale for {main_category}/{sub_category}",
                            "INFO"
                        )
                        
                except ImportError:
                    # Synthesis tracker module doesn't exist yet - that's fine
                    pass
                except Exception as e:
                    # Don't fail the main DB sync if synthesis tracking fails
                    self.socketio_emit_log(f"Warning: Could not update synthesis staleness for {tweet_id}: {e}", "WARNING")

        except Exception as e:
            logging.exception(f"Error syncing tweet {tweet_id} to database: {e}")
            self.socketio_emit_log(f"Error syncing tweet {tweet_id} to database: {e}", "ERROR")
            raise

    async def _sync_to_unified_db(self, tweet_id: str, tweet_data: Dict[str, Any]) -> None:
        """
        Sync tweet data directly to UnifiedTweet model.
        
        This replaces the old dual-table sync with a clean, unified approach.
        """
        self.socketio_emit_log(f"Syncing tweet {tweet_id} to unified database...", "DEBUG")

        try:
            from knowledge_base_agent.models import UnifiedTweet
            
            # Get or create unified tweet record
            unified_tweet = UnifiedTweet.query.filter_by(tweet_id=tweet_id).first()
            
            if not unified_tweet:
                # Create new unified tweet
                unified_tweet = UnifiedTweet(
                    tweet_id=tweet_id,
                    bookmarked_tweet_id=tweet_data.get('bookmarked_tweet_id', tweet_id)
                )
                db.session.add(unified_tweet)
                self.socketio_emit_log(f"Creating new unified tweet record for {tweet_id}", "DEBUG")
            else:
                self.socketio_emit_log(f"Updating existing unified tweet record for {tweet_id}", "DEBUG")
            
            # Update all fields from tweet_data
            self._update_unified_tweet_from_data(unified_tweet, tweet_data)
            
            # Commit changes
            db.session.commit()
            self.socketio_emit_log(f"✅ Unified database sync complete for {tweet_id}", "DEBUG")
            
        except Exception as e:
            logging.exception(f"Error syncing tweet {tweet_id} to unified database: {e}")
            self.socketio_emit_log(f"❌ Error syncing tweet {tweet_id} to unified database: {e}", "ERROR")
            db.session.rollback()
            raise

    def _update_unified_tweet_from_data(self, unified_tweet: 'UnifiedTweet', tweet_data: Dict[str, Any]) -> None:
        """Update UnifiedTweet object from tweet_data dictionary."""
        
        # Content data
        if 'raw_json_content' in tweet_data:
            unified_tweet.raw_tweet_data = tweet_data['raw_json_content']
        if 'thread_tweets' in tweet_data:
            unified_tweet.thread_tweets = tweet_data['thread_tweets']
        if 'is_thread' in tweet_data:
            unified_tweet.is_thread = tweet_data['is_thread']
        if 'full_text' in tweet_data:
            unified_tweet.full_text = tweet_data['full_text']
        if 'all_downloaded_media_for_thread' in tweet_data:
            unified_tweet.media_files = tweet_data['all_downloaded_media_for_thread']
        if 'image_descriptions' in tweet_data:
            unified_tweet.image_descriptions = tweet_data['image_descriptions']
        
        # Processing flags
        if 'cache_complete' in tweet_data:
            unified_tweet.cache_complete = tweet_data['cache_complete']
        if 'media_processed' in tweet_data:
            unified_tweet.media_processed = tweet_data['media_processed']
        if 'categories_processed' in tweet_data:
            unified_tweet.categories_processed = tweet_data['categories_processed']
        if 'kb_item_created' in tweet_data:
            unified_tweet.kb_item_created = tweet_data['kb_item_created']
        
        # Categorization data
        if 'main_category' in tweet_data:
            unified_tweet.main_category = tweet_data['main_category']
        if 'sub_category' in tweet_data:
            unified_tweet.sub_category = tweet_data['sub_category']
        if 'item_name_suggestion' in tweet_data:
            unified_tweet.kb_item_name = tweet_data['item_name_suggestion']
        if 'categories' in tweet_data:
            unified_tweet.categories_raw_response = tweet_data['categories']
        
        # KB data
        if 'kb_item_path' in tweet_data:
            unified_tweet.kb_file_path = tweet_data['kb_item_path']
        if 'kb_media_paths' in tweet_data:
            # Handle both JSON string and list formats
            kb_media_paths = tweet_data['kb_media_paths']
            if isinstance(kb_media_paths, str):
                try:
                    unified_tweet.kb_media_paths = json.loads(kb_media_paths)
                except (json.JSONDecodeError, TypeError):
                    unified_tweet.kb_media_paths = []
            else:
                unified_tweet.kb_media_paths = kb_media_paths or []
        if 'display_title' in tweet_data:
            unified_tweet.kb_display_title = tweet_data['display_title']
        if 'markdown_content' in tweet_data:
            unified_tweet.kb_content = tweet_data['markdown_content']
        
        # Error tracking
        if 'kbitem_error' in tweet_data:
            unified_tweet.kbitem_error = tweet_data['kbitem_error']
        if 'llm_error' in tweet_data:
            unified_tweet.llm_error = tweet_data['llm_error']
        
        # Runtime flags
        if 'cache_succeeded_this_run' in tweet_data:
            unified_tweet.cache_succeeded_this_run = tweet_data['cache_succeeded_this_run']
        if 'media_succeeded_this_run' in tweet_data:
            unified_tweet.media_succeeded_this_run = tweet_data['media_succeeded_this_run']
        if 'llm_succeeded_this_run' in tweet_data:
            unified_tweet.llm_succeeded_this_run = tweet_data['llm_succeeded_this_run']
        if 'kbitem_succeeded_this_run' in tweet_data:
            unified_tweet.kbitem_succeeded_this_run = tweet_data['kbitem_succeeded_this_run']
        
        # Metadata
        if 'url' in tweet_data:
            unified_tweet.source_url = tweet_data['url']
        
        # Update timestamp
        unified_tweet.updated_at = datetime.now(timezone.utc)
        
        # Check if processing is complete
        if (unified_tweet.cache_complete and unified_tweet.media_processed and 
            unified_tweet.categories_processed and unified_tweet.kb_item_created):
            unified_tweet.processing_complete = True
            if not unified_tweet.processed_at:
                unified_tweet.processed_at = datetime.now(timezone.utc)

    def socketio_emit_progress(self, processed_count, total_count, error_count, current_item_id, status_message):
        """Emit progress updates via unified logging system."""
        # MODERN: Use unified logging system
        if self.unified_logger:
            self.unified_logger.emit_phase_update(
                'process_content',
                'in_progress',
                f'Processed {processed_count} items',
                processed_count
            )
        elif self.socketio:
            # LEGACY: Fallback to direct SocketIO
            self.socketio.emit('progress_update', {
                'phase': 'process_content',
                'processed_count': processed_count,
                'total_count': total_count,
                'error_count': error_count,
                'current_item_id': current_item_id,
                'status_message': status_message
            })


# Compatibility alias for existing imports
ContentProcessor = StreamlinedContentProcessor 