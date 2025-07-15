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
from knowledge_base_agent.progress import ProcessingStats, PhaseDetail
from knowledge_base_agent.config import Config
from knowledge_base_agent.http_client import HTTPClient
from knowledge_base_agent.state_manager import StateManager
from knowledge_base_agent.category_manager import CategoryManager
from knowledge_base_agent.exceptions import ContentProcessingError, KnowledgeBaseItemCreationError
from knowledge_base_agent.tweet_cacher import cache_tweets
from knowledge_base_agent.media_processor import process_media
from knowledge_base_agent.markdown_writer import MarkdownWriter
from knowledge_base_agent.custom_types import KnowledgeBaseItem
from knowledge_base_agent.phase_execution_helper import PhaseExecutionHelper, ProcessingPhase, PhaseExecutionPlan
import aiofiles
import asyncio
import re
from mimetypes import guess_type
import shutil
from knowledge_base_agent.ai_categorization import categorize_and_name_content as ai_categorize_and_name
from knowledge_base_agent.kb_item_generator import create_knowledge_base_item
from flask import current_app
from knowledge_base_agent.models import KnowledgeBaseItem as DBKnowledgeBaseItem
from datetime import datetime, timezone
from flask_socketio import SocketIO
import json
from knowledge_base_agent.prompts import UserPreferences
from knowledge_base_agent.shared_globals import stop_flag
import os
import time
import copy
from statistics import median
import subprocess
from itertools import cycle
from knowledge_base_agent.stats_manager import load_processing_stats, update_phase_stats


class StreamlinedContentProcessor:
    """
    Streamlined ContentProcessor focused purely on orchestration.
    
    All validation is handled by StateManager.
    All phase planning is handled by PhaseExecutionHelper.
    """
    
    def __init__(self, config=None, http_client=None, state_manager=None, 
                 markdown_writer=None, category_manager=None,
                 socketio=None, phase_emitter_func=None, task_id=None):
        self.config = config
        self.http_client = http_client
        self.state_manager = state_manager
        self.socketio = socketio
        self.phase_emitter_func = phase_emitter_func
        self.text_model = self.http_client.config.text_model
        self.category_manager = category_manager
        self.markdown_writer = markdown_writer
        self.task_id = task_id
        
        # Initialize unified logging system if task_id is provided
        if task_id:
            from .unified_logging import get_unified_logger
            self.unified_logger = get_unified_logger(task_id, config)
        else:
            self.unified_logger = None
        
        # Initialize phase execution helper
        self.phase_helper = PhaseExecutionHelper()
        
        logging.info(f"Initialized StreamlinedContentProcessor with model: {self.text_model}")

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
        all_tweets = await self.state_manager.get_all_tweets()
        tweets_data_map: Dict[str, Dict[str, Any]] = {}
        
        # Ensure all unprocessed tweets are included in the data map, even if not cached yet
        all_tweet_ids = set(all_tweets.keys()) | set(unprocessed_tweets)
        
        for tweet_id in all_tweet_ids:
            tweet_data = await self.state_manager.get_tweet(tweet_id)
            if not tweet_data:
                # Initialize cache entry for tweets that are in unprocessed queue but not cached
                tweet_data = {'tweet_id': tweet_id, 'url': f'https://twitter.com/user/status/{tweet_id}'}
                await self.state_manager.initialize_tweet_cache(tweet_id, tweet_data)
                tweet_data = await self.state_manager.get_tweet(tweet_id)
                logging.info(f"Initialized cache entry for unprocessed tweet {tweet_id}")
            tweets_data_map[tweet_id] = tweet_data or {'tweet_id': tweet_id}

        # Create force flags dictionary for helper
        force_flags = {
            'force_recache_tweets': preferences.force_recache_tweets,
            'force_reprocess_media': preferences.force_reprocess_media,
            'force_reprocess_llm': preferences.force_reprocess_llm,
            'force_reprocess_kb_item': preferences.force_reprocess_kb_item
        }

        # Get execution plans for all phases - this replaces all validation logic!
        self.socketio_emit_log("Creating execution plans for all processing phases...", "INFO")
        execution_plans = self.phase_helper.create_all_execution_plans(tweets_data_map, force_flags)

        # Log analysis for debugging
        analysis = self.phase_helper.analyze_processing_state(tweets_data_map)
        self.socketio_emit_log(f"Processing state analysis: {analysis['total_tweets']} total tweets", "INFO")
        for stage, tweet_ids in analysis['tweets_by_stage'].items():
            if tweet_ids:
                self.socketio_emit_log(f"  {stage}: {len(tweet_ids)} tweets", "INFO")

        # Execute each phase using the execution plans
        try:
            await self._execute_cache_phase(execution_plans[ProcessingPhase.CACHE], tweets_data_map, preferences, stats)
            await self._execute_media_phase(execution_plans[ProcessingPhase.MEDIA], tweets_data_map, preferences, stats)
            await self._execute_llm_phase(execution_plans[ProcessingPhase.LLM], tweets_data_map, preferences, stats, category_manager)
            await self._execute_kb_item_phase(execution_plans[ProcessingPhase.KB_ITEM], tweets_data_map, preferences, stats)
            await self._execute_db_sync_phase(execution_plans[ProcessingPhase.DB_SYNC], tweets_data_map, preferences, stats, category_manager)
        except Exception as e:
            self.socketio_emit_log(f"Error during phase execution: {e}", "ERROR")
            if self.phase_emitter_func:
                self.phase_emitter_func('content_processing_overall', 'error', f'Processing error: {e}')
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
            self.socketio_emit_log(f"Skipping cache phase - all {plan.already_complete_count} tweets already cached", "INFO")
            # Emit active status first to show phase is being processed
            if self.phase_emitter_func:
                self.phase_emitter_func('tweet_caching', 'active', f'Checking {plan.already_complete_count} tweets...')
            # Brief delay to allow UI to register the active status
            await asyncio.sleep(0.1)
            if self.phase_emitter_func:
                self.phase_emitter_func('tweet_caching', 'completed', 
                                       f'All {plan.already_complete_count} tweets already cached')
            return

        self.socketio_emit_log(f"Cache phase: processing {plan.needs_processing_count} tweets, {plan.already_complete_count} already complete", "INFO")
        
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
                    updated_data = await self.state_manager.get_tweet(tweet_id)
                    if updated_data:
                        tweets_data_map[tweet_id] = updated_data

            self.socketio_emit_log(f"✅ Cached {plan.needs_processing_count} tweets successfully", "INFO")
            if self.phase_emitter_func:
                self.phase_emitter_func(
                    'tweet_caching', 'completed', 
                    f'Cached {plan.needs_processing_count} tweets',
                    False,  # is_sub_step_update
                    plan.needs_processing_count,  # processed_count
                    plan.needs_processing_count,  # total_count
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
            self.socketio_emit_log(f"Skipping media phase - all {plan.already_complete_count} tweets already processed", "INFO")
            # Emit active status first to show phase is being processed
            if self.phase_emitter_func:
                self.phase_emitter_func('media_analysis', 'active', f'Checking {plan.already_complete_count} tweets...')
            # Brief delay to allow UI to register the active status
            await asyncio.sleep(0.1)
            if self.phase_emitter_func:
                self.phase_emitter_func('media_analysis', 'completed', 
                                       f'All {plan.already_complete_count} tweets already have media processed')
            return

        self.socketio_emit_log(f"Media phase: processing {plan.needs_processing_count} tweets", "INFO")
        
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
                        'in_progress', 
                        f'Processing media for tweet {tweet_id}...',
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
                await self.state_manager.update_tweet_data(tweet_id, updated_tweet_data)
                
                # Don't log individual completions - too verbose for Live Logs
                
                # Emit progress update after completing this item
                if self.phase_emitter_func:
                    self.phase_emitter_func(
                        'media_analysis', 
                        'in_progress', 
                        f'Completed media processing for tweet {tweet_id}',
                        False,
                        i + 1,  # processed_count (items completed)
                        plan.needs_processing_count,  # total_count
                        stats.error_count
                    )
                
            except Exception as e:
                logging.error(f"Error in media processing for tweet {tweet_id}: {e}")
                self.socketio_emit_log(f"Error in media processing for tweet {tweet_id}: {e}", "ERROR")
                stats.error_count += 1
                tweets_data_map[tweet_id]['_media_error'] = str(e)
                tweets_data_map[tweet_id]['media_processed'] = False

        if not stop_flag.is_set():
            self.socketio_emit_log(f"✅ Media processed for {plan.needs_processing_count} tweets", "INFO")
            if self.phase_emitter_func:
                self.phase_emitter_func(
                    'media_analysis', 
                    'completed', 
                    f'Processed media for {plan.needs_processing_count} tweets',
                    False,
                    plan.needs_processing_count,  # All items processed
                    plan.needs_processing_count,  # Total count
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
                                       f'All {plan.already_complete_count} tweets already categorized')
            return

        self.socketio_emit_log(f"LLM phase: processing {plan.needs_processing_count} tweets", "INFO")

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
                    tweets_data_map[tweet_id]['_llm_error'] = str(error_obj)
                    tweets_data_map[tweet_id]['categories_processed'] = False
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
                    await self.state_manager.update_tweet_data(tweet_id, tweets_data_map[tweet_id])
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
            self.socketio_emit_log(f"✅ Categorized {plan.needs_processing_count} tweets with LLM", "INFO")
            if self.phase_emitter_func:
                self.phase_emitter_func('llm_processing', 'completed', 
                                       f'Categorized {plan.needs_processing_count} tweets')

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
                                       f'All {plan.already_complete_count} KB items already exist')
            return

        self.socketio_emit_log(f"KB item phase: processing {plan.needs_processing_count} tweets", "INFO")
        
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
                        f'Generating KB item for tweet {tweet_id}...',
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
                
                # Write to filesystem
                kb_item_dir_rel_project, media_paths_rel_kb_item_dir = await self.markdown_writer.write_kb_item(kb_item_obj)
                
                # Validate file creation
                readme_path_rel_project = kb_item_dir_rel_project / "README.md"
                readme_abs_path = self.config.resolve_path_from_project_root(str(readme_path_rel_project))
                if not readme_abs_path.exists():
                    raise Exception(f"KB item README was not created at expected path: {readme_abs_path}")
                
                # Update tweet data
                tweet_data['kb_item_path'] = str(readme_path_rel_project)
                tweet_data['kb_media_paths'] = json.dumps(media_paths_rel_kb_item_dir)
                tweet_data['kb_item_created'] = True
                
                await self.state_manager.update_tweet_data(tweet_id, tweet_data)
                items_successfully_processed += 1
                
                # Update progress when completing this item
                if self.phase_emitter_func:
                    self.phase_emitter_func(
                        'kb_item_generation', 
                        'active', 
                        f'Completed KB item for tweet {tweet_id}',
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
                tweets_data_map[tweet_id]['_kbitem_error'] = str(e)
                tweets_data_map[tweet_id]['kb_item_created'] = False

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
            self.socketio_emit_log(f"✅ Generated {plan.needs_processing_count} KB items", "INFO")
            if self.phase_emitter_func:
                self.phase_emitter_func('kb_item_generation', 'completed', 
                                       f'Generated {plan.needs_processing_count} KB items')

    async def _execute_db_sync_phase(self, plan: PhaseExecutionPlan, tweets_data_map: Dict[str, Any], 
                                   preferences, stats, category_manager):
        """Execute database sync phase using execution plan."""
        if plan.should_skip_phase:
            self.socketio_emit_log(f"Skipping DB sync phase - all {plan.already_complete_count} tweets already synced", "INFO")
            # Emit active status first to show phase is being processed
            if self.phase_emitter_func:
                self.phase_emitter_func('database_sync', 'active', f'Checking {plan.already_complete_count} tweets...')
            # Brief delay to allow UI to register the active status
            await asyncio.sleep(0.1)
            if self.phase_emitter_func:
                self.phase_emitter_func('database_sync', 'completed', 
                                       f'All {plan.already_complete_count} tweets already synced to database')
            return

        self.socketio_emit_log(f"DB sync phase: processing {plan.needs_processing_count} tweets", "INFO")
        
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
                self.socketio_emit_log(f"Syncing tweet {tweet_id} to database ({i+1}/{plan.needs_processing_count})", "DEBUG")
                
                # Update progress when starting to process this item
                if self.phase_emitter_func:
                    self.phase_emitter_func(
                        'database_sync', 
                        'active', 
                        f'Syncing tweet {tweet_id} to database...',
                        False,
                        i,  # Current index shows item being processed (0-based)
                        plan.needs_processing_count,
                        stats.error_count
                    )
                
                await self._sync_to_db(tweet_id, tweet_data, category_manager)
                tweet_data['db_synced'] = True
                await self.state_manager.update_tweet_data(tweet_id, tweet_data)
                items_successfully_processed += 1
                
                # Update progress when completing this item
                if self.phase_emitter_func:
                    self.phase_emitter_func(
                        'database_sync', 
                        'active', 
                        f'Completed database sync for tweet {tweet_id}',
                        False,
                        i + 1,  # Completed items count
                        plan.needs_processing_count,
                        stats.error_count
                    )
                
                self.socketio_emit_log(f"Database sync complete for {tweet_id}", "INFO")
                
            except Exception as e:
                logging.error(f"Error in database sync for tweet {tweet_id}: {e}", exc_info=True)
                self.socketio_emit_log(f"Error in database sync for tweet {tweet_id}: {e}", "ERROR")
                stats.error_count += 1
                tweets_data_map[tweet_id]['_db_error'] = str(e)
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
                                       f'Synced {plan.needs_processing_count} tweets to database')

    async def _finalize_processing(self, tweets_data_map: Dict[str, Any], unprocessed_tweets: List[str], stats):
        """Finalize processing and update stats."""
        for tweet_id in unprocessed_tweets:
            tweet_data = tweets_data_map[tweet_id]
            
            # Check if all phases completed successfully
            all_phases_complete = all([
                tweet_data.get('cache_complete', False),
                tweet_data.get('media_processed', False),
                tweet_data.get('categories_processed', False),
                tweet_data.get('kb_item_created', False),
                tweet_data.get('db_synced', False)
            ])
            
            # Check for errors
            has_errors = any([
                tweet_data.get('_cache_error'),
                tweet_data.get('_media_error'),
                tweet_data.get('_llm_error'),
                tweet_data.get('_kbitem_error'),
                tweet_data.get('_db_error')
            ])
            
            if all_phases_complete and not has_errors:
                await self.state_manager.mark_tweet_processed(tweet_id)
                stats.processed_count += 1
                logging.info(f"Tweet {tweet_id} successfully completed all phases")
            elif has_errors:
                logging.warning(f"Tweet {tweet_id} had errors in one or more phases")

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

    async def _sync_to_db(self, tweet_id: str, tweet_data: Dict[str, Any], category_manager: CategoryManager) -> None:
        """
        Sync individual tweet to database.
        Enhanced with synthesis staleness tracking.
        """
        self.socketio_emit_log(f"Syncing tweet {tweet_id} to database...", "DEBUG")

        try:
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
            
            # Get content from markdown content if available, otherwise fall back to tweet text
            content = tweet_data.get('markdown_content', tweet_data.get('full_text_cleaned', tweet_data.get('full_text', '')))
            
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
                "kb_media_paths": json.dumps(tweet_data.get('kb_media_paths', [])) if tweet_data.get('kb_media_paths') else None,
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

            # Mark affected synthesis documents as stale
            if main_category and sub_category:
                try:
                    from .synthesis_tracker import SynthesisDependencyTracker
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
                        
                except Exception as e:
                    # Don't fail the main DB sync if synthesis tracking fails
                    self.socketio_emit_log(f"Warning: Could not update synthesis staleness for {tweet_id}", "WARNING")

        except Exception as e:
            logging.exception(f"Error syncing tweet {tweet_id} to database: {e}")
            self.socketio_emit_log(f"Error syncing tweet {tweet_id} to database: {e}", "ERROR")
            raise

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