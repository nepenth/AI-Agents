"""
Content processing module for the Knowledge Base Agent.
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
from knowledge_base_agent.media_processor import process_media, has_unprocessed_non_video_media, count_media_items, VIDEO_MIME_TYPES
from knowledge_base_agent.readme_generator import generate_root_readme, generate_static_root_readme
from knowledge_base_agent.markdown_writer import MarkdownWriter
from knowledge_base_agent.types import KnowledgeBaseItem
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

STATS_FILE_PATH = Path("data/processing_stats.json")

class ContentProcessingError(Exception):
    """Custom exception for content processing errors."""
    pass

class ContentProcessor:
    """Content processor class."""
    
    def __init__(self, config=None, http_client=None, state_manager=None, socketio=None, phase_emitter_func=None):
        self.config = config
        self.http_client = http_client
        self.state_manager = state_manager
        self.socketio = socketio
        self.phase_emitter_func = phase_emitter_func
        self.text_model = self.http_client.config.text_model
        self.category_manager = CategoryManager(config, http_client=http_client)
        self.markdown_writer = MarkdownWriter(config)
        
        logging.info(f"Initialized ContentProcessor with model: {self.text_model}")

    def socketio_emit_log(self, message: str, level: str = "INFO") -> None:
        """Helper method to emit general logs via SocketIO if available."""
        if self.socketio:
            self.socketio.emit('log', {'message': message, 'level': level.upper()})
        # Standard logging will also occur via Python's logging module
        logger_level = getattr(logging, level.upper(), logging.INFO)
        logging.log(logger_level, f"[ContentProcessor] {message}") # Add prefix for clarity in combined logs

    async def process_all_tweets(
        self,
        preferences: UserPreferences,
        unprocessed_tweets: List[str],
        total_tweets_for_processing: int,
        stats: ProcessingStats,
        category_manager: CategoryManager
    ) -> List[PhaseDetail]:
        phase_details_results: List[PhaseDetail] = []

        if not unprocessed_tweets:
            logging.info("ContentProcessor: No tweets to process.")
            self.socketio_emit_log("No tweets to process.", "INFO")
            if self.phase_emitter_func: self.phase_emitter_func('content_processing_overall', 'skipped', 'No tweets in queue.')
            return phase_details_results

        self.socketio_emit_log(
            f"Starting to process {len(unprocessed_tweets)} tweets phase-by-phase. "
            f"Force flags: recache={preferences.force_recache_tweets}, "
            f"media={preferences.force_reprocess_media}, "
            f"llm={preferences.force_reprocess_llm}, "
            f"kb_item={preferences.force_reprocess_kb_item}", 
            "INFO"
        )
        if self.phase_emitter_func: self.phase_emitter_func('content_processing_overall', 'in_progress', f'Processing {len(unprocessed_tweets)} tweets phase-by-phase...')
        
        tweets_data_map: Dict[str, Dict[str, Any]] = {}
        for tweet_id in unprocessed_tweets:
            tweet_data = await self.state_manager.get_tweet(tweet_id)
            if not tweet_data:
                tweet_data = {'tweet_id': tweet_id, 'url': f'https://twitter.com/user/status/{tweet_id}'}
                await self.state_manager.initialize_tweet_cache(tweet_id, tweet_data)
                tweet_data = await self.state_manager.get_tweet(tweet_id)
            tweets_data_map[tweet_id] = tweet_data or {'tweet_id': tweet_id}

        # Check if we can skip caching and media phases
        # We can skip these if we're only doing LLM/KB processing and all tweets already have cache_complete=True
        skip_caching_phase = False
        skip_media_phase = False
        
        if preferences.force_reprocess_llm and not preferences.force_recache_tweets and not preferences.force_reprocess_media:
            # We're only doing LLM reprocessing - check if all tweets have complete cache
            all_tweets_cache_complete = all(
                tweets_data_map[tweet_id].get('cache_complete', False) 
                for tweet_id in unprocessed_tweets
            )
            
            if all_tweets_cache_complete:
                skip_caching_phase = True
                self.socketio_emit_log("Skipping Tweet Caching phase - all tweets already cached and only LLM reprocessing requested.", "INFO")
            
            # Similarly for media phase - check if all tweets already have media processed
            all_tweets_media_processed = all(
                tweets_data_map[tweet_id].get('media_processed', False) 
                for tweet_id in unprocessed_tweets
            )
            
            if all_tweets_media_processed:
                skip_media_phase = True
                self.socketio_emit_log("Skipping Media Analysis phase - all tweets already have media processed and only LLM reprocessing requested.", "INFO")

        # --- Phase 1: Tweet Caching ---
        cache_phase = PhaseDetail(name="Tweet Caching", total_eligible=len(unprocessed_tweets))
        
        if skip_caching_phase:
            # Mark phase as skipped if we're only doing LLM processing and all tweets are already cached
            cache_phase.attempted = len(unprocessed_tweets)
            cache_phase.skipped_already_done = len(unprocessed_tweets)
            cache_phase.succeeded = len(unprocessed_tweets)
            cache_phase.details = f"All {len(unprocessed_tweets)} tweets already cached. Skipped due to LLM-only reprocessing request."
            
            self.socketio_emit_log(f"--- Skipping Sub-Phase: {cache_phase.name} - {cache_phase.details} ---", "INFO")
            if self.phase_emitter_func:
                self.phase_emitter_func(
                    'subphase_cp_cache', 
                    'skipped', 
                    f'Skipped: {cache_phase.details}', 
                    False,
                    len(unprocessed_tweets),
                    len(unprocessed_tweets),
                    0
                )
        else:
            # Run caching phase normally
            self.socketio_emit_log(f"--- Starting Sub-Phase: {cache_phase.name} for {cache_phase.total_eligible} tweets ---", "INFO")
        if self.phase_emitter_func: 
            self.phase_emitter_func(
                'subphase_cp_cache', 
                'active', 
                f'Caching up to {cache_phase.total_eligible} tweets...', 
                    False,
                    0,
                    cache_phase.total_eligible,
                    0
            )
        
        # Call cache_tweets once for all unprocessed_tweets
        try:
            if unprocessed_tweets: # Only call if there are tweets to cache
                cache_summary = await cache_tweets(
                    tweet_ids=unprocessed_tweets,
                    config=self.config,
                    http_client=self.http_client,
                    state_manager=self.state_manager,
                    force_recache=preferences.force_recache_tweets,
                        progress_callback=self.phase_emitter_func,
                    phase_id_for_progress='subphase_cp_cache'
                )
                
                # Update PhaseDetail and stats from summary
                cache_phase.attempted = cache_summary.total_processed
                cache_phase.succeeded = cache_summary.successfully_cached
                cache_phase.failed = cache_summary.failed_cache
                cache_phase.newly_created_or_updated = cache_summary.newly_cached_or_updated
                cache_phase.skipped_already_done = cache_summary.skipped_already_complete
                stats.error_count += cache_summary.failed_cache

                # Update tweets_data_map for tweets that might have failed caching
                for tweet_id in unprocessed_tweets:
                    refreshed_data = await self.state_manager.get_tweet(tweet_id)
                    if refreshed_data:
                        tweets_data_map[tweet_id] = refreshed_data
                    else:
                        logging.warning(f"Tweet data for {tweet_id} missing after caching attempt.")
                        tweets_data_map[tweet_id]['_cache_error'] = "Data missing post-cache"
                        tweets_data_map[tweet_id]['cache_complete'] = False
            else:
                if self.phase_emitter_func:
                    self.phase_emitter_func('subphase_cp_cache', 'completed', 'No tweets to cache.', False, 0, 0, 0)

        except Exception as e:
            stats.error_count += len(unprocessed_tweets)
            cache_phase.failed = len(unprocessed_tweets)
            logging.error(f"Error during batch tweet caching: {e}", exc_info=True)
            self.socketio_emit_log(f"Critical error during batch tweet caching: {e}", "ERROR")
            if self.phase_emitter_func: 
                self.phase_emitter_func('subphase_cp_cache', 'error', f'Batch caching error: {e}', False, 0, len(unprocessed_tweets), len(unprocessed_tweets))
            # Mark all as cache error in tweets_data_map
            for tweet_id in unprocessed_tweets:
                tweets_data_map[tweet_id]['_cache_error'] = str(e)
                tweets_data_map[tweet_id]['cache_complete'] = False

        cache_phase.details = f"{cache_phase.newly_created_or_updated} newly cached/updated, {cache_phase.skipped_already_done} skipped, {cache_phase.failed} failed out of {cache_phase.attempted} attempted."
        self.socketio_emit_log(f"Caching sub-phase summary: {cache_phase.details}", "INFO")

        phase_details_results.append(cache_phase)

        if stop_flag.is_set():
            self.socketio_emit_log("Caching sub-phase potentially stopped by flag. Check logs from cache_tweets.", "WARNING")
            if self.phase_emitter_func:
                 current_cache_status = 'interrupted'
                 self.phase_emitter_func('subphase_cp_cache', current_cache_status, 'Caching stopped by user.')
                 self.phase_emitter_func('content_processing_overall', 'interrupted', 'Processing stopped during caching.')
            return phase_details_results

        # --- Phase 2: Media Analysis ---
        media_analysis_eligible_ids = [tid for tid, tdata in tweets_data_map.items() if not tdata.get('_cache_error') and tdata.get('cache_complete')]
        media_phase = PhaseDetail(name="Media Analysis", total_eligible=len(media_analysis_eligible_ids))
        
        if skip_media_phase:
            # Mark phase as skipped if we're only doing LLM processing and all tweets already have media processed
            media_phase.attempted = len(media_analysis_eligible_ids)
            media_phase.skipped_already_done = len(media_analysis_eligible_ids)
            media_phase.succeeded = len(media_analysis_eligible_ids)
            media_phase.details = f"All {len(media_analysis_eligible_ids)} tweets already have media processed. Skipped due to LLM-only reprocessing request."
            
            self.socketio_emit_log(f"--- Skipping Sub-Phase: {media_phase.name} - {media_phase.details} ---", "INFO")
            if self.phase_emitter_func:
                self.phase_emitter_func(
                    'subphase_cp_media', 
                    'skipped', 
                    f'Skipped: {media_phase.details}', 
                    False,
                    len(media_analysis_eligible_ids),
                    len(media_analysis_eligible_ids),
                    0
                )
        else:
            # Run media analysis phase normally
            self.socketio_emit_log(f"--- Starting Sub-Phase: {media_phase.name} for {media_phase.total_eligible} eligible tweets ---", "INFO")
            if self.phase_emitter_func: 
                self.phase_emitter_func(
                    'subphase_cp_media', 
                    'in_progress', 
                    f'Media Analysis for {media_phase.total_eligible} tweets...',
                    False,
                    0,
                    media_phase.total_eligible,
                    0
                )
        
        for i, tweet_id in enumerate(media_analysis_eligible_ids):
            if stop_flag.is_set():
                self.socketio_emit_log("Media Analysis sub-phase stopped by flag.", "WARNING")
                if self.phase_emitter_func: self.phase_emitter_func('subphase_cp_media', 'interrupted', 'Media analysis stopped.')
                break
            
            media_phase.attempted += 1
            current_item_progress_msg = f"Tweet {tweet_id} ({i+1}/{len(media_analysis_eligible_ids)})"
            if self.phase_emitter_func: self.phase_emitter_func('subphase_cp_media', 'in_progress', f'Analyzing media for {current_item_progress_msg}')
            
            tweet_data = tweets_data_map[tweet_id]
            try:
                media_already_processed = tweet_data.get('media_processed', False)
                if not media_already_processed or preferences.force_reprocess_media:
                    self.socketio_emit_log(f"Running media analysis for {tweet_id} (media_processed: {media_already_processed}, force: {preferences.force_reprocess_media})", "DEBUG")
                    updated_tweet_data_media = await process_media(
                        tweet_data=dict(tweet_data), 
                        http_client=self.http_client,
                        config=self.config,
                            force_reprocess=preferences.force_reprocess_media
                    )
                    tweets_data_map[tweet_id] = updated_tweet_data_media
                    await self.state_manager.update_tweet_data(tweet_id, updated_tweet_data_media)
                    self.socketio_emit_log(f"Media analysis complete for {tweet_id}. Processed flag: {updated_tweet_data_media.get('media_processed')}", "INFO")
                    if not media_already_processed or preferences.force_reprocess_media:
                        media_phase.newly_created_or_updated +=1
                else:
                    self.socketio_emit_log(f"Skipping media analysis for {tweet_id} as it's already processed and not forced.", "INFO")
                    media_phase.skipped_already_done += 1
                
                media_phase.succeeded += 1
                tweets_data_map[tweet_id]['_media_succeeded_this_run'] = True
            except Exception as e:
                stats.error_count += 1
                media_phase.failed += 1
                logging.error(f"Error in Media Analysis for {current_item_progress_msg}: {e}", exc_info=True)
                self.socketio_emit_log(f"Error in Media Analysis for {current_item_progress_msg}: {e}", "ERROR")
                tweets_data_map[tweet_id]['_media_error'] = str(e)
                if tweets_data_map[tweet_id].get('media_processed') is not False:
                    tweets_data_map[tweet_id]['media_processed'] = False
                    await self.state_manager.update_tweet_data(tweet_id, {'media_processed': False})

        media_phase.details = f"{media_phase.newly_created_or_updated} newly analyzed, {media_phase.skipped_already_done} skipped, {media_phase.failed} failed out of {media_phase.attempted} attempted."
        self.socketio_emit_log(f"Media Analysis sub-phase summary: {media_phase.details}", "INFO")

        if not stop_flag.is_set():
            self.socketio_emit_log(f"--- Sub-Phase: Media Analysis completed. Attempted: {media_phase.attempted}/{media_phase.total_eligible}, Succeeded: {media_phase.succeeded} ---", "INFO")
            if self.phase_emitter_func: self.phase_emitter_func('subphase_cp_media', 'completed', f'Media analysis done. {media_phase.details}')
        
        phase_details_results.append(media_phase)

        if stop_flag.is_set():
            if self.phase_emitter_func: self.phase_emitter_func('content_processing_overall', 'interrupted', 'Processing stopped during media analysis.')
            return phase_details_results

        # --- Phase 3: LLM Categorization & Naming ---
        current_phase_id_str_llm = "llm_categorization" # For stats tracking
        categorization_eligible_ids = [tid for tid, tdata in tweets_data_map.items() if not tdata.get('_cache_error') and tdata.get('cache_complete') and not tdata.get('_media_error')]
        llm_phase = PhaseDetail(name="LLM Categorization & Naming", total_eligible=len(categorization_eligible_ids))

        if not categorization_eligible_ids:
            llm_phase.details = "No tweets eligible for LLM processing after prior phases."
            self.socketio_emit_log(f"--- Skipping Sub-Phase: {llm_phase.name} - {llm_phase.details} ---", "INFO")
            if self.phase_emitter_func: self.phase_emitter_func('subphase_cp_llm', 'skipped', llm_phase.details)
        else:
            self.socketio_emit_log(f"--- Starting Sub-Phase: {llm_phase.name} for {llm_phase.total_eligible} eligible tweets ---", "INFO")
            
            # Filter tasks that actually need processing
            tasks_to_process_data = []
            for tweet_id in categorization_eligible_ids:
                tweet_data_for_categorization = tweets_data_map[tweet_id]
                force_this_tweet_llm = preferences.force_reprocess_llm
                categories_already_processed = tweet_data_for_categorization.get('categories_processed', False)
                has_existing_cat_data = tweet_data_for_categorization.get('main_category') and tweet_data_for_categorization.get('item_name_suggestion')
                should_run_llm_phase = force_this_tweet_llm or not (categories_already_processed and has_existing_cat_data)
                
                if should_run_llm_phase:
                    tasks_to_process_data.append((tweet_id, tweet_data_for_categorization))
                else:
                    llm_phase.attempted += 1 # Count as attempted even if skipped due to already done
                    llm_phase.skipped_already_done += 1
                    llm_phase.succeeded += 1 # Considered a success for this phase if correctly skipped
                    tweets_data_map[tweet_id]['_llm_succeeded_this_run'] = True
            
            actual_items_to_process_llm = len(tasks_to_process_data)

            if not actual_items_to_process_llm:
                logging.info("No tweets require LLM categorization in this batch after filtering (all eligible were already processed and not forced).")
                llm_phase.details = f"All {llm_phase.total_eligible} eligible tweets were already categorized and not forced for reprocessing."
                if self.phase_emitter_func: 
                    self.phase_emitter_func(
                        'subphase_cp_llm', 
                        'completed', # Mark as completed as no actual work needed
                        llm_phase.details,
                        False, # is_sub_step_update
                        llm_phase.total_eligible, # processed_count (all were effectively processed by skipping)
                        llm_phase.total_eligible, # total_count
                        0 # error_count
                    )
            else:
                # Load historical stats for ETC calculation
                processing_stats_data = load_processing_stats()
                phase_historical_stats = processing_stats_data.get("phases", {}).get(current_phase_id_str_llm, {})
                avg_time_per_item_llm = phase_historical_stats.get("avg_time_per_item_seconds", 0.0)
                initial_estimated_duration_llm = avg_time_per_item_llm * actual_items_to_process_llm if avg_time_per_item_llm > 0 else 0
                logging.info(f"CONTENT_PROCESSOR_ETC: Phase {current_phase_id_str_llm} - Avg time/item: {avg_time_per_item_llm:.2f}s, Items: {actual_items_to_process_llm}, Calculated Initial ETC: {initial_estimated_duration_llm:.0f}s")

                num_gpus = self.config.num_gpus_available
                logging.info(f"Configured num_gpus_available: {num_gpus}")
                if num_gpus <= 0: num_gpus = 1
                num_parallel_jobs = num_gpus
                logging.info(f"PARALLEL PROCESSING: Will run up to {num_parallel_jobs} parallel LLM categorization jobs for {actual_items_to_process_llm} tweets.")

                if self.phase_emitter_func: 
                    self.phase_emitter_func(
                        'subphase_cp_llm', 
                        'active', 
                        f'Categorizing {actual_items_to_process_llm} tweets (of {llm_phase.total_eligible} total eligible) using {num_parallel_jobs} worker(s)...',
                        False, # is_sub_step_update
                        0, # processed_count starts at 0 for items actively being processed
                        actual_items_to_process_llm, # total_count is items actively being processed
                        0, # error_count starts at 0
                        initial_estimated_duration_llm # Send historical ETC
                    )

                phase_start_time_monotonic_llm = time.monotonic()
                items_successfully_processed_this_run_llm = 0

                semaphore = asyncio.Semaphore(num_parallel_jobs)
                gpu_idx_cycle = cycle(range(num_gpus))
                all_tasks = []

                async def worker_llm(tweet_id: str, tweet_data: Dict[str, Any], assigned_gpu: int):
                    # Renamed worker to worker_llm to avoid potential scope issues if other workers are defined
                    async with semaphore:
                        logging.info(f"LLM worker: Processing {tweet_id} on GPU {assigned_gpu}. Slots used: {num_parallel_jobs - semaphore._value}/{num_parallel_jobs}")
                        # llm_phase.attempted is incremented when item is added to tasks_to_process_data or skipped
                        # Here we only deal with items that are *actually* processed by a worker
                        try:
                            result = await self._process_single_categorization(
                                tweet_id, tweet_data, category_manager, preferences, assigned_gpu
                            )
                            logging.info(f"LLM categorization for {tweet_id} completed successfully by worker.")
                            return tweet_id, result, None 
                        except Exception as e:
                            logging.error(f"Error in LLM Processing for tweet {tweet_id} (worker_llm): {e}", exc_info=True)
                            return tweet_id, None, e 
                        finally:
                            # Emit progress after each item processed by a worker
                            processed_count_for_emitter = llm_phase.succeeded - llm_phase.skipped_already_done + llm_phase.failed
                            if self.phase_emitter_func:
                                self.phase_emitter_func(
                                    'subphase_cp_llm',
                                    'in_progress',
                                    f'LLM: {processed_count_for_emitter}/{actual_items_to_process_llm}. Current: {tweet_id}',
                                    True, # is_sub_step_update
                                    processed_count_for_emitter, 
                                    actual_items_to_process_llm, 
                                    llm_phase.failed
                                )
                
                for tweet_id_to_process, data_for_categorization in tasks_to_process_data:
                    if stop_flag.is_set(): 
                        logging.warning("Stop flag detected before creating all LLM tasks. Remaining tasks will not be scheduled.")
                        break
                    llm_phase.attempted +=1 # Increment attempted for items that will be processed by a worker
                    assigned_gpu_for_task = next(gpu_idx_cycle)
                    all_tasks.append(worker_llm(tweet_id_to_process, data_for_categorization, assigned_gpu_for_task))

                if all_tasks:
                    results_from_workers = await asyncio.gather(*all_tasks, return_exceptions=False)
                    for processed_tweet_id, result_data, error_obj in results_from_workers:
                        if stop_flag.is_set() and not error_obj and not result_data: # Check if task was cancelled due to stop_flag
                            logging.info(f"LLM task for {processed_tweet_id} likely cancelled by stop_flag before completion.")
                            # Treat as error for accounting if it didn't complete, or decide on other handling
                            llm_phase.failed += 1 
                            stats.error_count += 1
                            tweets_data_map[processed_tweet_id]['_llm_error'] = "Processing stopped by user"
                            tweets_data_map[processed_tweet_id]['categories_processed'] = False
                            continue

                        if error_obj:
                            stats.error_count += 1
                            llm_phase.failed += 1
                            self.socketio_emit_log(f"Error in LLM Processing for tweet {processed_tweet_id}: {error_obj}", "ERROR")
                            tweets_data_map[processed_tweet_id]['_llm_error'] = str(error_obj)
                            tweets_data_map[processed_tweet_id]['categories_processed'] = False
                        elif result_data:
                            main_cat, sub_cat, item_name = result_data
                            tweets_data_map[processed_tweet_id]['main_category'] = main_cat
                            tweets_data_map[processed_tweet_id]['sub_category'] = sub_cat
                            tweets_data_map[processed_tweet_id]['item_name_suggestion'] = item_name
                            tweets_data_map[processed_tweet_id]['categories_processed'] = True
                            tweets_data_map[processed_tweet_id]['categories'] = {
                                'main_category': main_cat,
                                'sub_category': sub_cat,
                                'item_name': item_name
                            }
                            await self.state_manager.update_tweet_data(processed_tweet_id, tweets_data_map[processed_tweet_id])
                            llm_phase.newly_created_or_updated += 1
                            llm_phase.succeeded += 1
                            items_successfully_processed_this_run_llm +=1 # For historical stats
                            tweets_data_map[processed_tweet_id]['_llm_succeeded_this_run'] = True
                
                # After processing all tasks for this phase, update historical stats
                phase_end_time_monotonic_llm = time.monotonic()
                duration_this_run_llm = phase_end_time_monotonic_llm - phase_start_time_monotonic_llm
                
                if items_successfully_processed_this_run_llm > 0: # Only update stats if actual work was done
                    update_phase_stats(
                        phase_id=current_phase_id_str_llm,
                        items_processed_this_run=items_successfully_processed_this_run_llm,
                        duration_this_run_seconds=duration_this_run_llm
                    )

        # Final summary for the LLM phase based on llm_phase object which tracks all eligible items
        llm_phase.details = f"{llm_phase.newly_created_or_updated} newly categorized, {llm_phase.skipped_already_done} skipped (already processed), {llm_phase.failed} failed out of {llm_phase.total_eligible} total eligible."
        self.socketio_emit_log(f"LLM Processing sub-phase summary: {llm_phase.details}", "INFO")
        phase_details_results.append(llm_phase)

        if not stop_flag.is_set():
            self.socketio_emit_log(f"--- Sub-Phase: LLM Processing completed. Attempted: {llm_phase.attempted}/{llm_phase.total_eligible}, Succeeded: {llm_phase.succeeded} ---", "INFO")
            if self.phase_emitter_func: self.phase_emitter_func('subphase_cp_llm', 'completed', f'LLM done. {llm_phase.details}')
        if stop_flag.is_set():
            if self.phase_emitter_func: self.phase_emitter_func('content_processing_overall', 'interrupted', 'Processing stopped during LLM.')
            return phase_details_results

        # --- Phase 4: KB Item Generation ---
        kb_item_eligible_ids = [
            tid for tid, tdata in tweets_data_map.items() 
            if not tdata.get('_cache_error') and not tdata.get('_media_error') and \
               not tdata.get('_llm_error') and tdata.get('categories_processed') and \
               tdata.get('main_category') and tdata.get('item_name_suggestion')
        ]
        kb_item_phase = PhaseDetail(name="KB Item Generation", total_eligible=len(kb_item_eligible_ids))
        self.socketio_emit_log(f"--- Starting Sub-Phase: {kb_item_phase.name} for {kb_item_phase.total_eligible} eligible tweets ---", "INFO")
        
        # Load historical stats for ETC calculation (KB Item Generation)
        current_phase_id_str_kbitem = "subphase_cp_kbitem"
        processing_stats_data = load_processing_stats()
        phase_historical_stats = processing_stats_data.get("phases", {}).get(current_phase_id_str_kbitem, {})
        avg_time_per_item_kbitem = phase_historical_stats.get("avg_time_per_item_seconds", 0.0)
        initial_estimated_duration_kbitem = avg_time_per_item_kbitem * len(kb_item_eligible_ids) if avg_time_per_item_kbitem > 0 else 0
        logging.info(f"CONTENT_PROCESSOR_ETC: Phase {current_phase_id_str_kbitem} - Avg time/item: {avg_time_per_item_kbitem:.2f}s, Items: {len(kb_item_eligible_ids)}, Calculated Initial ETC: {initial_estimated_duration_kbitem:.0f}s")

        if self.phase_emitter_func: 
            self.phase_emitter_func(
                'subphase_cp_kbitem', 
                'active', 
                f'KB Item Gen for {kb_item_phase.total_eligible} tweets...',
                False,
                0, # processed_count starts at 0
                kb_item_phase.total_eligible, # total_count is the number of eligible tweets
                0, # error_count starts at 0
                initial_estimated_duration_kbitem # Send historical ETC
            )

        # Start timing for KB Item Generation phase
        phase_start_time_monotonic_kbitem = time.monotonic()
        items_successfully_processed_this_run_kbitem = 0

        for i, tweet_id in enumerate(kb_item_eligible_ids):
            if stop_flag.is_set():
                self.socketio_emit_log("KB Item Gen sub-phase stopped by flag.", "WARNING")
                if self.phase_emitter_func: self.phase_emitter_func('subphase_cp_kbitem', 'interrupted', 'KB Item generation stopped.')
                break
            
            kb_item_phase.attempted += 1
            current_item_progress_msg = f"Tweet {tweet_id} ({i+1}/{len(kb_item_eligible_ids)})"
            if self.phase_emitter_func: self.phase_emitter_func('subphase_cp_kbitem', 'in_progress', f'KB Item Gen for {current_item_progress_msg}')
            
            tweet_data = tweets_data_map[tweet_id]
            try:
                kb_item_path_rel_project = tweet_data.get('kb_item_path')
                kb_item_readme_abs_path = self.config.resolve_path_from_project_root(kb_item_path_rel_project) if kb_item_path_rel_project else None
                kb_item_file_exists = kb_item_readme_abs_path.is_file() if kb_item_readme_abs_path else False
                
                already_created_and_exists = tweet_data.get('kb_item_created', False) and kb_item_file_exists
                should_run_kb_gen = preferences.force_reprocess_kb_item or not already_created_and_exists
                                
                if should_run_kb_gen:
                    self.socketio_emit_log(f"Generating KB item structure for {tweet_id}... (Force: {preferences.force_reprocess_kb_item}, Exists&Flagged: {already_created_and_exists})", "DEBUG")
                    kb_item_obj: KnowledgeBaseItem = await create_knowledge_base_item(
                        tweet_id=tweet_id, tweet_data=tweet_data, config=self.config,
                        http_client=self.http_client, state_manager=self.state_manager
                    )
                    kb_item_dir_rel_project, media_paths_rel_kb_item_dir = await self.markdown_writer.write_kb_item(kb_item_obj)
                    tweet_data['kb_item_path'] = str(kb_item_dir_rel_project / "README.md") # Path relative to project root
                    tweet_data['kb_media_paths'] = json.dumps(media_paths_rel_kb_item_dir) # Paths relative to item's dir
                    tweet_data['kb_item_created'] = True
                    await self.state_manager.update_tweet_data(tweet_id, tweet_data)
                    kb_item_phase.newly_created_or_updated += 1
                    self.socketio_emit_log(f"KB Item generation complete for {tweet_id}. Path (rel to project): {tweet_data['kb_item_path']}", "INFO")
                    items_successfully_processed_this_run_kbitem += 1  # Track successful KB item generation
                else:
                    self.socketio_emit_log(f"Skipping KB Item Generation for {tweet_id} (complete, not forced, or prerequisites missing).", "INFO")
                    if not kb_item_file_exists and tweet_data.get('kb_item_path') and not should_run_kb_gen:
                        self.socketio_emit_log(f"KB item path {tweet_data['kb_item_path']} for {tweet_id} does not exist, but phase skipped.", "WARNING")
                    kb_item_phase.skipped_already_done += 1
                
                kb_item_phase.succeeded += 1
                tweets_data_map[tweet_id]['_kbitem_succeeded_this_run'] = True
            except Exception as e:
                stats.error_count += 1
                kb_item_phase.failed += 1
                logging.error(f"Error in KB Item Generation for {current_item_progress_msg}: {e}", exc_info=True)
                self.socketio_emit_log(f"Error in KB Item Generation for {current_item_progress_msg}: {e}", "ERROR")
                tweets_data_map[tweet_id]['_kbitem_error'] = str(e)
                tweets_data_map[tweet_id]['kb_item_created'] = False

        # After processing all tasks for this phase, update historical stats
        phase_end_time_monotonic_kbitem = time.monotonic()
        duration_this_run_kbitem = phase_end_time_monotonic_kbitem - phase_start_time_monotonic_kbitem
        
        if items_successfully_processed_this_run_kbitem > 0: # Only update stats if actual work was done
            update_phase_stats(
                phase_id=current_phase_id_str_kbitem,
                items_processed_this_run=items_successfully_processed_this_run_kbitem,
                duration_this_run_seconds=duration_this_run_kbitem
            )

        kb_item_phase.details = f"{kb_item_phase.newly_created_or_updated} newly generated, {kb_item_phase.skipped_already_done} skipped, {kb_item_phase.failed} failed out of {kb_item_phase.attempted} attempted."
        self.socketio_emit_log(f"KB Item Generation sub-phase summary: {kb_item_phase.details}", "INFO")
        phase_details_results.append(kb_item_phase)

        if not stop_flag.is_set():
            self.socketio_emit_log(f"--- Sub-Phase: KB Item Generation completed. Attempted: {kb_item_phase.attempted}/{kb_item_phase.total_eligible}, Succeeded: {kb_item_phase.succeeded} ---", "INFO")
            if self.phase_emitter_func: self.phase_emitter_func('subphase_cp_kbitem', 'completed', f'KB Gen done. {kb_item_phase.details}')
        if stop_flag.is_set():
            if self.phase_emitter_func: self.phase_emitter_func('content_processing_overall', 'interrupted', 'Processing stopped during KB item generation.')
            return phase_details_results

        # --- Phase 5: Database Sync ---
        db_sync_eligible_ids = [
            tid for tid, tdata in tweets_data_map.items() 
            if not tdata.get('_cache_error') and not tdata.get('_media_error') and \
               not tdata.get('_llm_error') and not tdata.get('_kbitem_error') and \
               tdata.get('kb_item_created') and tdata.get('main_category') and \
               tdata.get('item_name_suggestion') and tdata.get('kb_item_path')
        ]
        db_sync_phase = PhaseDetail(name="Database Sync", total_eligible=len(db_sync_eligible_ids))
        self.socketio_emit_log(f"--- Starting Sub-Phase: {db_sync_phase.name} for {db_sync_phase.total_eligible} eligible tweets ---", "INFO")
        
        # Load historical stats for ETC calculation (Database Sync)
        current_phase_id_str_db = "subphase_cp_db"
        processing_stats_data = load_processing_stats()
        phase_historical_stats = processing_stats_data.get("phases", {}).get(current_phase_id_str_db, {})
        avg_time_per_item_db = phase_historical_stats.get("avg_time_per_item_seconds", 0.0)
        initial_estimated_duration_db = avg_time_per_item_db * len(db_sync_eligible_ids) if avg_time_per_item_db > 0 else 0
        logging.info(f"CONTENT_PROCESSOR_ETC: Phase {current_phase_id_str_db} - Avg time/item: {avg_time_per_item_db:.2f}s, Items: {len(db_sync_eligible_ids)}, Calculated Initial ETC: {initial_estimated_duration_db:.0f}s")

        if self.phase_emitter_func: 
            self.phase_emitter_func(
                'subphase_cp_db', 
                'active', 
                f'DB Sync for {db_sync_phase.total_eligible} tweets...',
                False,
                0, # processed_count starts at 0
                db_sync_phase.total_eligible, # total_count is the number of eligible tweets
                0, # error_count starts at 0
                initial_estimated_duration_db # Send historical ETC
            )

        # Start timing for Database Sync phase
        phase_start_time_monotonic_db = time.monotonic()
        items_successfully_processed_this_run_db = 0

        for i, tweet_id in enumerate(db_sync_eligible_ids):
            if stop_flag.is_set():
                self.socketio_emit_log("DB Sync sub-phase stopped by flag.", "WARNING")
                if self.phase_emitter_func: self.phase_emitter_func('subphase_cp_db', 'interrupted', 'DB Sync stopped.')
                break
            
            db_sync_phase.attempted += 1
            current_item_progress_msg = f"Tweet {tweet_id} ({i+1}/{len(db_sync_eligible_ids)})"
            if self.phase_emitter_func: self.phase_emitter_func('subphase_cp_db', 'in_progress', f'DB Syncing {current_item_progress_msg}')
            
            tweet_data = tweets_data_map[tweet_id]
            try:
                # For DB sync, "force_reprocess_kb_item" implies we should re-sync even if 'db_synced' is true
                # since the KB item generation would have produced new content
                already_synced = tweet_data.get('db_synced', False)
                should_run_db_sync = preferences.force_reprocess_kb_item or not already_synced
                
                if should_run_db_sync:
                    self.socketio_emit_log(f"Attempting DB Sync for {current_item_progress_msg} (Force: {preferences.force_reprocess_kb_item}, Synced: {already_synced})", "DEBUG")
                    await self._sync_to_db(tweet_id, tweet_data, category_manager)
                    tweet_data['db_synced'] = True 
                    await self.state_manager.update_tweet_data(tweet_id, tweet_data) 
                    db_sync_phase.newly_created_or_updated += 1 # Consider this an update/creation for the phase
                    self.socketio_emit_log(f"Database sync complete for {tweet_id}", "INFO")
                    items_successfully_processed_this_run_db += 1  # Track successful DB sync
                else:
                    self.socketio_emit_log(f"Skipping Database Sync for {tweet_id} (already synced and not forced).", "INFO")
                    db_sync_phase.skipped_already_done += 1
                
                db_sync_phase.succeeded += 1
                tweets_data_map[tweet_id]['_db_succeeded_this_run'] = True
            except Exception as e:
                stats.error_count += 1
                db_sync_phase.failed += 1
                logging.error(f"Error in DB Sync for {current_item_progress_msg}: {e}", exc_info=True)
                self.socketio_emit_log(f"Error in DB Sync for {current_item_progress_msg}: {e}", "ERROR")
                tweets_data_map[tweet_id]['_db_error'] = str(e)
                tweets_data_map[tweet_id]['db_synced'] = False

        # After processing all tasks for this phase, update historical stats
        phase_end_time_monotonic_db = time.monotonic()
        duration_this_run_db = phase_end_time_monotonic_db - phase_start_time_monotonic_db
        
        if items_successfully_processed_this_run_db > 0: # Only update stats if actual work was done
            update_phase_stats(
                phase_id=current_phase_id_str_db,
                items_processed_this_run=items_successfully_processed_this_run_db,
                duration_this_run_seconds=duration_this_run_db
            )

        db_sync_phase.details = f"{db_sync_phase.newly_created_or_updated} newly synced/updated, {db_sync_phase.skipped_already_done} skipped, {db_sync_phase.failed} failed out of {db_sync_phase.attempted} attempted."
        self.socketio_emit_log(f"Database Sync sub-phase summary: {db_sync_phase.details}", "INFO")
        phase_details_results.append(db_sync_phase)

        if not stop_flag.is_set():
            self.socketio_emit_log(f"--- Sub-Phase: Database Sync completed. Attempted: {db_sync_phase.attempted}/{db_sync_phase.total_eligible}, Succeeded: {db_sync_phase.succeeded} ---", "INFO")
            if self.phase_emitter_func: self.phase_emitter_func('subphase_cp_db', 'completed', f'DB Sync done. {db_sync_phase.details}')
        if stop_flag.is_set():
            if self.phase_emitter_func: self.phase_emitter_func('content_processing_overall', 'interrupted', 'Processing stopped during DB sync.')
            return phase_details_results

        # Final pass to mark tweets as processed and update overall progress
        processed_item_overall_count = 0 # For socketio_emit_progress
        for tweet_id in unprocessed_tweets: 
            tweet_data = tweets_data_map[tweet_id]
            
            # Check if all attempted & applicable phases for THIS item in THIS run succeeded.
            # An item is considered fully processed in THIS run if it had no errors in any phase it was eligible for and attempted.
            item_had_error_this_run = any(key.endswith('_error') and tweet_data.get(key) for key in [
                '_cache_error', '_media_error', '_llm_error', '_kbitem_error', '_db_error'
            ])

            # Check final state flags as a safeguard, but primary success is no errors in this run for attempted phases.
            # This ensures that if a prerequisite phase failed, subsequent phases are not penalized if skipped.
            all_key_flags_set = (
                tweet_data.get('cache_complete') and
                tweet_data.get('media_processed') and 
                tweet_data.get('categories_processed') and
                tweet_data.get('kb_item_created') and
                tweet_data.get('db_synced')
            )
            # More precise: check _succeeded_this_run flags for phases that were attempted
            # For now, `not item_had_error_this_run` is the main driver if it was eligible for processing.
            
            is_successful_this_run = not item_had_error_this_run and all_key_flags_set

            if is_successful_this_run:
                await self.state_manager.mark_tweet_processed(tweet_id, tweet_data)
                stats.processed_count += 1 
                processed_item_overall_count += 1
                self.socketio_emit_progress(processed_item_overall_count, len(unprocessed_tweets), stats.error_count, tweet_id, "Completed All Phases")
                self.socketio_emit_log(f"Tweet {tweet_id} successfully completed all processing phases.", "INFO")
            elif item_had_error_this_run:
                 # Error already counted by the phase, error_count on stats is overall
                 self.socketio_emit_progress(processed_item_overall_count, len(unprocessed_tweets), stats.error_count, tweet_id, "Error in one or more phases")
                 self.socketio_emit_log(f"Tweet {tweet_id} had errors in one or more phases.", "WARNING")
            else: 
                # This case means no specific error flag, but not all key success flags are set.
                # Could be due to interruption, or a phase was skipped due to unmet prerequisites from a *prior non-error* skip.
                self.socketio_emit_log(f"Tweet {tweet_id} did not complete all phases (possibly skipped, interrupted, or prerequisites not met for all stages). Final flags: CC:{tweet_data.get('cache_complete')}, MP:{tweet_data.get('media_processed')}, CP:{tweet_data.get('categories_processed')}, KI:{tweet_data.get('kb_item_created')}, DS:{tweet_data.get('db_synced')}", "INFO")


        final_summary_msg = f"Content processing phase-by-phase finished. Successfully processed (overall): {stats.processed_count}/{len(unprocessed_tweets)}. Total errors encountered for items: {stats.error_count}."
        self.socketio_emit_log(final_summary_msg, "INFO")
        
        overall_status = 'completed'
        if stop_flag.is_set():
            overall_status = 'interrupted'
        # Items that are not (len(unprocessed_tweets) - stats.error_count) might be skipped due to non-error conditions
        elif stats.error_count > 0 and stats.processed_count < (len(unprocessed_tweets) - stats.error_count):
             overall_status = 'completed_with_errors'
        elif stats.error_count > 0: # All items processed or errored
            overall_status = 'completed_with_warnings' 
        elif stats.processed_count < len(unprocessed_tweets): # No errors, but not all processed (e.g. legitimate skips, or interrupted before final processed_count increment)
             overall_status = 'completed_partially'


        if self.phase_emitter_func: 
            self.phase_emitter_func('content_processing_overall', overall_status, final_summary_msg)
        
        logging.info(f"ContentProcessor: process_all_tweets completed. Stats: Processed={stats.processed_count}, Errors={stats.error_count}")
        return phase_details_results

    async def _sync_to_db(self, tweet_id: str, tweet_data: Dict[str, Any], category_manager: CategoryManager) -> None:
        try:
            app = current_app._get_current_object()
            with app.app_context():
                db_item: DBKnowledgeBaseItem = DBKnowledgeBaseItem.query.filter_by(tweet_id=tweet_id).first()

                created_at_dt = tweet_data.get('created_at_dt')
                if isinstance(created_at_dt, str):
                    try:
                        if created_at_dt.endswith('Z'):
                            created_at_dt_parsed = datetime.fromisoformat(created_at_dt[:-1] + '+00:00')
                        else:
                            created_at_dt_parsed = datetime.fromisoformat(created_at_dt)
                        created_at_dt = created_at_dt_parsed.replace(tzinfo=timezone.utc) if created_at_dt_parsed.tzinfo is None else created_at_dt_parsed
                    except ValueError:
                        self.socketio_emit_log(f"Could not parse date string '{created_at_dt}' for tweet {tweet_id}. Setting to None.", "WARNING")
                        created_at_dt = None
                elif isinstance(created_at_dt, datetime):
                    created_at_dt = created_at_dt.replace(tzinfo=timezone.utc) if created_at_dt.tzinfo is None else created_at_dt
                else: # Not str or datetime
                     self.socketio_emit_log(f"created_at_tweet for {tweet_id} is not a str or datetime. Type: {type(created_at_dt)}. Setting to None.", "WARNING")
                     created_at_dt = None

                attributes = {
                    "tweet_id": tweet_id,
                    "user_screen_name": tweet_data.get('user_screen_name', 'unknown'),
                    "content": tweet_data.get('full_text_cleaned', tweet_data.get('full_text', '')),
                    "main_category_name": tweet_data.get('main_category'),
                    "sub_category_name": tweet_data.get('sub_category'),
                    "item_name": tweet_data.get('item_name_suggestion', 'Untitled KB Item'),
                    "tweet_url": tweet_data.get('url', f'https://twitter.com/{tweet_data.get("user_screen_name", "user")}/status/{tweet_id}'),
                    "created_at_tweet": created_at_dt, # Ensure this is UTC aware
                    "tags_list": tweet_data.get('tags', []),
                    "source": "twitter_bookmark", # Default or derive from tweet_data if available
                    "file_path": tweet_data.get('kb_item_path'), # Relative to project root
                    "kb_media_paths": tweet_data.get('kb_media_paths'), # JSON string of paths relative to item's dir
                }

                if db_item:
                    self.socketio_emit_log(f"Updating existing DB entry for tweet {tweet_id}", "DEBUG")
                    for key, value in attributes.items():
                        setattr(db_item, key, value)
                    db_item.updated_at = datetime.now(timezone.utc)
                else:
                    self.socketio_emit_log(f"Creating new DB entry for tweet {tweet_id}", "DEBUG")
                    db_item = DBKnowledgeBaseItem(**attributes) # created_at will be set by default
                    db_item.updated_at = datetime.now(timezone.utc) # Explicitly set updated_at for new items too
                
                from knowledge_base_agent.models import db # Import here to avoid circular issues if models.py imports from agent components
                db.session.add(db_item)
                db.session.commit()
                self.socketio_emit_log(f"DB entry for {tweet_id} committed.", "DEBUG")

        except Exception as e:
            logging.exception(f"Error syncing tweet {tweet_id} to database: {e}") # Use logging.exception for stack trace
            self.socketio_emit_log(f"Error syncing tweet {tweet_id} to database: {e}", "ERROR")
            raise # Re-raise to be caught by the phase loop, so it's counted in PhaseDetail.failed

    def socketio_emit_progress(self, processed_count, total_count, error_count, current_item_id, status_message):
        if self.socketio:
            self.socketio.emit('progress_update', {
                'phase': 'process_content',
                'processed_count': processed_count,
                'total_count': total_count,
                'error_count': error_count,
                'current_item_id': current_item_id,
                'status_message': status_message
            })

    def get_model_parameter_size(self, model_name: str) -> int:
        """
        Estimate model parameter size based on model name.
        Returns parameter count (not in billions, but actual count)
        """
        if not model_name:
            return 0
            
        model_name = model_name.lower()
        
        # Look for patterns like "7b", "13b", "70b", etc.
        size_patterns = [r'(\d+)b', r'(\d+)-b', r'(\d+)_b', r'(\d+).b']
        for pattern in size_patterns:
            match = re.search(pattern, model_name)
            if match:
                try:
                    # Convert to actual parameter count (not billions)
                    return int(match.group(1)) * 1_000_000_000
                except ValueError:
                    pass
        
        # If we couldn't parse the size but have common model indicators
        if any(x in model_name for x in ['tiny', 'small', 'mini']):
            return 1_000_000_000  # Tiny models ~1B
        elif 'base' in model_name or 'medium' in model_name:
            return 7_000_000_000  # Base/medium models ~7B
        elif 'large' in model_name:
            return 13_000_000_000  # Large models ~13B
        elif 'xl' in model_name or 'huge' in model_name:
            return 20_000_000_000  # XL models ~20B
            
        # Default for unknown models
        return 7_000_000_000  # Assume 7B for safety
        
    def get_gpu_info(self) -> Dict[str, Any]:
        """
        Get GPU information using nvidia-smi if available.
        Returns a dictionary with GPU information or None if not available.
        """
        try:
            # Try to run nvidia-smi to get GPU information
            result = subprocess.run(
                ['nvidia-smi', '--query-gpu=memory.total,memory.used,memory.free,gpu_name', '--format=csv,noheader,nounits'],
                capture_output=True,
                text=True,
                check=True,
                timeout=5  # Add timeout to avoid hanging
            )
            
            # Parse the output (will be in MB)
            lines = [line.strip() for line in result.stdout.strip().split('\n') if line.strip()]
            
            if not lines:
                logging.warning("nvidia-smi returned empty output")
                return None
                
            gpu_info_list = []
            total_memory = 0
            
            for i, line in enumerate(lines):
                try:
                    parts = [part.strip() for part in line.split(',')]
                    if len(parts) >= 4:  # total, used, free, name
                        mem_total = int(parts[0])
                        mem_used = int(parts[1])
                        mem_free = int(parts[2])
                        gpu_name = parts[3]
                        
                        total_memory += mem_total
                        
                        gpu_info_list.append({
                            'index': i,
                            'name': gpu_name,
                            'memory_total_mb': mem_total,
                            'memory_used_mb': mem_used,
                            'memory_free_mb': mem_free
                        })
                        
                        logging.info(f"Detected GPU {i}: {gpu_name} with {mem_total}MB total memory ({mem_free}MB free)")
                except (ValueError, IndexError) as e:
                    logging.warning(f"Failed to parse GPU info from line '{line}': {e}")
            
            if gpu_info_list:
                # Check if Ollama can access these GPUs
                cuda_visible_devices = os.environ.get('CUDA_VISIBLE_DEVICES')
                if cuda_visible_devices is not None:
                    logging.info(f"CUDA_VISIBLE_DEVICES is set to: {cuda_visible_devices}")
                
                return {
                    'total_memory_mb': total_memory,
                    'num_gpus': len(gpu_info_list),
                    'gpus': gpu_info_list,
                    'cuda_visible_devices': cuda_visible_devices
                }
            else:
                logging.warning("No GPU information could be parsed from nvidia-smi output")
                return None
                
        except subprocess.TimeoutExpired:
            logging.warning("nvidia-smi command timed out")
            return None
        except subprocess.SubprocessError as e:
            logging.warning(f"nvidia-smi command failed: {e}")
            return None
        except FileNotFoundError:
            logging.warning("nvidia-smi not found, CUDA may not be installed or in PATH")
            return None
        except Exception as e:
            logging.warning(f"Unexpected error getting GPU information: {e}")
            return None

    async def _regenerate_readme(self) -> None:
        """Placeholder for potential future use if ContentProcessor needs to trigger this.
        Currently, README regeneration is handled by the main agent."""
        self.socketio_emit_log("ContentProcessor._regenerate_readme called (currently a placeholder).", "DEBUG")
        pass

    async def get_tweets_with_media(self) -> Dict[str, Any]:
        """Get tweets that have unprocessed media."""
        tweets = await self.state_manager.get_all_tweets()
        media_tweets = {
            tweet_id: tweet_data 
            for tweet_id, tweet_data in tweets.items() 
            # has_unprocessed_non_video_media needs to handle relative media paths
            if await has_unprocessed_non_video_media(tweet_data, self.config) # Pass config
        }
        self.socketio_emit_log(f"Found {len(media_tweets)} tweets with unprocessed media", "DEBUG")
        return media_tweets

    async def _count_media_items(self) -> int:
        """Count total media items across all tweets."""
        tweets = await self.state_manager.get_all_tweets()
        # count_media_items needs to handle relative media paths
        count = await count_media_items(tweets, self.config) # Pass config
        self.socketio_emit_log(f"Counted {count} media items across all tweets", "DEBUG")
        return count

    def _is_video_file(self, path_rel_to_project: str) -> bool:
        """Check if a file is a video based on MIME type or extension."""
        # Path is relative to project root, resolve it
        path_obj_abs = self.config.resolve_path_from_project_root(path_rel_to_project)
        mime_type, _ = guess_type(str(path_obj_abs))
        is_video = (mime_type in VIDEO_MIME_TYPES or 
                    path_obj_abs.suffix.lower() in {'.mp4', '.mov', '.avi', '.mkv'})
        self.socketio_emit_log(f"Checked if {path_rel_to_project} (resolved to {path_obj_abs}) is video: {is_video}", "DEBUG")
        return is_video

    async def _process_single_categorization(self, tweet_id: str, tweet_data: Dict[str, Any], category_manager: CategoryManager, preferences: UserPreferences, gpu_device: int) -> Tuple[str, str, str]:
        """Helper method to process a single tweet for categorization and naming."""
        try:
            self.socketio_emit_log(f"Invoking AI for categorization and naming of {tweet_id}... (Force: {preferences.force_reprocess_llm}, Already processed: {tweet_data.get('categories_processed', False)})", "DEBUG")
            
            # Check if tweet has no obvious text content but has image descriptions
            # to improve error reporting and potentially use that as context
            raw_text = tweet_data.get('full_text', '')
            has_image_descriptions = bool(tweet_data.get('image_descriptions') and any(tweet_data.get('image_descriptions')))
            
            if not raw_text.strip() and has_image_descriptions:
                logging.info(f"Tweet {tweet_id} has no text content but has image descriptions. Will proceed with categorization.")
            
            # If categories_processed is false, check if there was a previous error
            if not tweet_data.get('categories_processed', False) and '_llm_error' in tweet_data:
                logging.info(f"Tweet {tweet_id} previously had error: {tweet_data.get('_llm_error')}. Retrying categorization.")
                # Remove the error flag to ensure clean retry
                error_msg = tweet_data.pop('_llm_error', None)
                await self.state_manager.update_tweet_data(tweet_id, {'_llm_error': None})

            main_cat, sub_cat, item_name = await ai_categorize_and_name(
                http_client=self.http_client, tweet_data=tweet_data, text_model=self.text_model,
                tweet_id=tweet_id, category_manager=category_manager, # Pass the agent's category_manager
                max_retries=self.config.max_retries, fallback_model=self.config.fallback_model,
                gpu_device=gpu_device
            )
            tweet_data['main_category'] = main_cat
            tweet_data['sub_category'] = sub_cat
            tweet_data['item_name_suggestion'] = item_name
            tweet_data['categories_processed'] = True
            # Ensure the 'categories' sub-dictionary is also populated
            tweet_data['categories'] = {
                'main_category': main_cat,
                'sub_category': sub_cat,
                'item_name': item_name
            }
            await self.state_manager.update_tweet_data(tweet_id, tweet_data)
            await category_manager.ensure_category_exists(main_cat, sub_cat) # Use the passed category_manager
            self.socketio_emit_log(f"LLM processing complete for {tweet_id}: Cat={main_cat}, SubCat={sub_cat}, Name={item_name}", "INFO")
            return main_cat, sub_cat, item_name
        except Exception as e:
            logging.error(f"Error in LLM Processing for tweet {tweet_id}: {e}", exc_info=True)
            self.socketio_emit_log(f"Error in LLM Processing for tweet {tweet_id}: {e}", "ERROR")
            raise # Re-raise to be caught by the phase loop, so it's counted in PhaseDetail.failed