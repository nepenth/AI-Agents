"""
Phase Execution Helper for ContentProcessor

This helper analyzes tweet processing states and creates execution plans
for each processing phase, eliminating the need for validation logic
in ContentProcessor.
"""

from typing import Dict, List, Any, NamedTuple
from enum import Enum
from dataclasses import dataclass
import logging


class ProcessingPhase(Enum):
    """Processing phases in order."""
    CACHE = "cache"
    MEDIA = "media" 
    LLM = "llm"
    KB_ITEM = "kb_item"
    DB_SYNC = "db_sync"
    SYNTHESIS = "synthesis"
    EMBEDDING = "embedding"


@dataclass
class PhaseExecutionPlan:
    """Execution plan for a specific processing phase."""
    phase: ProcessingPhase
    total_eligible_tweets: int
    tweets_needing_processing: List[str]
    tweets_already_complete: List[str]
    tweets_ineligible: List[str]  # Due to missing prerequisites
    
    @property
    def needs_processing_count(self) -> int:
        return len(self.tweets_needing_processing)
    
    @property
    def already_complete_count(self) -> int:
        return len(self.tweets_already_complete)
    
    @property
    def ineligible_count(self) -> int:
        return len(self.tweets_ineligible)
    
    @property
    def should_skip_phase(self) -> bool:
        """True if no tweets need processing for this phase."""
        return self.needs_processing_count == 0


class PhaseExecutionHelper:
    """Helper for creating phase execution plans."""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def create_all_execution_plans(
        self, 
        tweets_data_map: Dict[str, Dict[str, Any]], 
        force_flags: Dict[str, bool]
    ) -> Dict[ProcessingPhase, PhaseExecutionPlan]:
        """
        Create execution plans for all processing phases.
        
        Args:
            tweets_data_map: Tweet ID -> tweet data mapping
            force_flags: Dictionary of force reprocessing flags
            
        Returns:
            Dictionary mapping each phase to its execution plan
        """
        plans = {}
        
        for phase in ProcessingPhase:
            plan = self.create_phase_execution_plan(phase, tweets_data_map, force_flags)
            plans[phase] = plan
            
            self.logger.info(
                f"Phase {phase.value}: {plan.needs_processing_count} need processing, "
                f"{plan.already_complete_count} already complete, "
                f"{plan.ineligible_count} ineligible"
            )
        
        return plans
    
    def create_phase_execution_plan(
        self,
        phase: ProcessingPhase,
        tweets_data_map: Dict[str, Dict[str, Any]],
        force_flags: Dict[str, bool]
    ) -> PhaseExecutionPlan:
        """Create execution plan for a specific phase."""
        
        tweets_needing_processing = []
        tweets_already_complete = []
        tweets_ineligible = []
        
        # Global phases are handled differently
        if phase in [ProcessingPhase.SYNTHESIS, ProcessingPhase.EMBEDDING]:
            # For global phases, we don't iterate per tweet.
            # We just check the force flag. If not forced, we assume it doesn't need processing
            # unless a more sophisticated check is implemented later.
            # The 'tweets' lists will be empty, which is fine.
            if self._does_tweet_need_processing(phase, {}, force_flags):
                 # We can use a dummy entry to indicate the phase should run.
                 tweets_needing_processing.append("global_phase")
            else:
                 tweets_already_complete.append("global_phase")
            total_eligible = 1
        else:
            for tweet_id, tweet_data in tweets_data_map.items():
                # Check if tweet is eligible for this phase
                if not self._is_tweet_eligible_for_phase(phase, tweet_data):
                    tweets_ineligible.append(tweet_id)
                    continue
                
                # Check if tweet needs processing for this phase
                if self._does_tweet_need_processing(phase, tweet_data, force_flags):
                    tweets_needing_processing.append(tweet_id)
                else:
                    tweets_already_complete.append(tweet_id)
            
            total_eligible = len(tweets_needing_processing) + len(tweets_already_complete)

        return PhaseExecutionPlan(
            phase=phase,
            total_eligible_tweets=total_eligible,
            tweets_needing_processing=tweets_needing_processing,
            tweets_already_complete=tweets_already_complete,
            tweets_ineligible=tweets_ineligible
        )
    
    def _is_tweet_eligible_for_phase(self, phase: ProcessingPhase, tweet_data: Dict[str, Any]) -> bool:
        """Check if a tweet is eligible for a specific processing phase."""
        
        # Cache phase: All tweets are eligible
        if phase == ProcessingPhase.CACHE:
            return True
        
        # Media phase: Requires cache completion
        if phase == ProcessingPhase.MEDIA:
            return (
                not tweet_data.get('_cache_error') and 
                tweet_data.get('cache_complete', False)
            )
        
        # LLM phase: Requires cache completion and no media errors
        if phase == ProcessingPhase.LLM:
            return (
                not tweet_data.get('_cache_error') and
                not tweet_data.get('_media_error') and
                tweet_data.get('cache_complete', False)
            )
        
        # KB Item phase: Requires successful LLM categorization
        if phase == ProcessingPhase.KB_ITEM:
            return (
                not tweet_data.get('_cache_error') and
                not tweet_data.get('_media_error') and
                not tweet_data.get('_llm_error') and
                tweet_data.get('categories_processed', False) and
                tweet_data.get('main_category') and
                tweet_data.get('item_name_suggestion')
            )
        
        # DB Sync phase: Requires successful KB item creation
        if phase == ProcessingPhase.DB_SYNC:
            return (
                not tweet_data.get('_cache_error') and
                not tweet_data.get('_media_error') and
                not tweet_data.get('_llm_error') and
                not tweet_data.get('_kbitem_error') and
                tweet_data.get('kb_item_created', False) and
                tweet_data.get('main_category') and
                tweet_data.get('item_name_suggestion') and
                tweet_data.get('kb_item_path')
            )

        # Global phases are not per-tweet, so they are not eligible in a per-tweet context.
        # The create_phase_execution_plan handles them separately.
        if phase in [ProcessingPhase.SYNTHESIS, ProcessingPhase.EMBEDDING]:
            return False

        return False
    
    def _does_tweet_need_processing(
        self, 
        phase: ProcessingPhase, 
        tweet_data: Dict[str, Any], 
        force_flags: Dict[str, bool]
    ) -> bool:
        """Check if a tweet needs processing for a specific phase."""
        
        if phase == ProcessingPhase.CACHE:
            force_recache = force_flags.get('force_recache_tweets', False)
            cache_complete = tweet_data.get('cache_complete', False)
            return force_recache or not cache_complete
        
        if phase == ProcessingPhase.MEDIA:
            force_media = force_flags.get('force_reprocess_media', False)
            media_processed = tweet_data.get('media_processed', False)
            return force_media or not media_processed
        
        if phase == ProcessingPhase.LLM:
            force_llm = force_flags.get('force_reprocess_llm', False)
            categories_processed = tweet_data.get('categories_processed', False)
            # LLM phase CREATES category data, so we only check if categories_processed flag is set
            # No need to check for existing category data since LLM creates it
            return force_llm or not categories_processed
        
        if phase == ProcessingPhase.KB_ITEM:
            force_kb = force_flags.get('force_reprocess_kb_item', False)
            kb_item_created = tweet_data.get('kb_item_created', False)
            
            # Additional validation: check if file actually exists
            if kb_item_created and tweet_data.get('kb_item_path'):
                # This would need config to resolve path, but for now assume path validation
                # is handled by StateManager during initialization
                pass
            
            return force_kb or not kb_item_created
        
        if phase == ProcessingPhase.DB_SYNC:
            force_kb = force_flags.get('force_reprocess_kb_item', False)  # KB regeneration implies DB re-sync
            db_synced = tweet_data.get('db_synced', False)
            return force_kb or not db_synced

        if phase == ProcessingPhase.SYNTHESIS:
            force_synthesis = force_flags.get('force_regenerate_synthesis', False)
            # This is a global phase. It needs processing if forced.
            # A more complex check could see if new items have been added since last run.
            return force_synthesis

        if phase == ProcessingPhase.EMBEDDING:
            force_embedding = force_flags.get('force_regenerate_embeddings', False)
            # This is a global phase. It needs processing if forced.
            return force_embedding

        return False
    
    def get_phase_dependencies(self, phase: ProcessingPhase) -> List[ProcessingPhase]:
        """Get the phases that must complete before this phase can run."""
        dependencies = {
            ProcessingPhase.CACHE: [],
            ProcessingPhase.MEDIA: [ProcessingPhase.CACHE],
            ProcessingPhase.LLM: [ProcessingPhase.CACHE, ProcessingPhase.MEDIA],
            ProcessingPhase.KB_ITEM: [ProcessingPhase.CACHE, ProcessingPhase.MEDIA, ProcessingPhase.LLM],
            ProcessingPhase.DB_SYNC: [ProcessingPhase.CACHE, ProcessingPhase.MEDIA, ProcessingPhase.LLM, ProcessingPhase.KB_ITEM],
            ProcessingPhase.SYNTHESIS: [ProcessingPhase.DB_SYNC], # Depends on all items being in DB
            ProcessingPhase.EMBEDDING: [ProcessingPhase.SYNTHESIS] # Depends on synthesis also being generated
        }
        return dependencies.get(phase, [])
    
    def validate_phase_prerequisites(
        self, 
        phase: ProcessingPhase, 
        tweet_data: Dict[str, Any]
    ) -> List[str]:
        """
        Validate that all prerequisite phases are complete for a tweet.
        Returns list of missing prerequisites.
        """
        missing = []
        
        if phase in [ProcessingPhase.MEDIA, ProcessingPhase.LLM, ProcessingPhase.KB_ITEM, ProcessingPhase.DB_SYNC]:
            if not tweet_data.get('cache_complete'):
                missing.append('cache_complete')
        
        if phase in [ProcessingPhase.LLM, ProcessingPhase.KB_ITEM, ProcessingPhase.DB_SYNC]:
            if not tweet_data.get('media_processed'):
                missing.append('media_processed')
        
        if phase in [ProcessingPhase.KB_ITEM, ProcessingPhase.DB_SYNC]:
            if not tweet_data.get('categories_processed'):
                missing.append('categories_processed')
            if not tweet_data.get('main_category'):
                missing.append('main_category')
            if not tweet_data.get('item_name_suggestion'):
                missing.append('item_name_suggestion')
        
        if phase == ProcessingPhase.DB_SYNC:
            if not tweet_data.get('kb_item_created'):
                missing.append('kb_item_created')
            if not tweet_data.get('kb_item_path'):
                missing.append('kb_item_path')
        
        # Prerequisites for global phases would be checked differently, not per-tweet.
        # This function is per-tweet, so we can't validate SYNTHESIS or EMBEDDING here effectively.
        
        return missing
    
    def analyze_processing_state(self, tweets_data_map: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
        """
        Analyze the overall processing state across all tweets.
        Useful for reporting and debugging.
        """
        analysis = {
            'total_tweets': len(tweets_data_map),
            'phase_completion': {},
            'tweets_by_stage': {
                'not_started': [],
                'cache_only': [],
                'cache_and_media': [],
                'through_llm': [],
                'through_kb_item': [],
                'fully_complete': []
            },
            'error_summary': {
                'cache_errors': 0,
                'media_errors': 0,
                'llm_errors': 0,
                'kb_item_errors': 0,
                'db_errors': 0
            }
        }
        
        # Count completion for each phase
        for phase in ProcessingPhase:
            # Global phases are not tracked per tweet, so we can't count them here.
            if phase in [ProcessingPhase.SYNTHESIS, ProcessingPhase.EMBEDDING]:
                continue

            completed_count = 0
            for tweet_data in tweets_data_map.values():
                if self._is_phase_complete(phase, tweet_data):
                    completed_count += 1
            analysis['phase_completion'][phase.value] = {
                'completed': completed_count,
                'total': len(tweets_data_map),
                'percentage': (completed_count / len(tweets_data_map) * 100) if tweets_data_map else 0
            }
        
        # Categorize tweets by processing stage
        for tweet_id, tweet_data in tweets_data_map.items():
            if tweet_data.get('db_synced'):
                analysis['tweets_by_stage']['fully_complete'].append(tweet_id)
            elif tweet_data.get('kb_item_created'):
                analysis['tweets_by_stage']['through_kb_item'].append(tweet_id)
            elif tweet_data.get('categories_processed'):
                analysis['tweets_by_stage']['through_llm'].append(tweet_id)
            elif tweet_data.get('media_processed'):
                analysis['tweets_by_stage']['cache_and_media'].append(tweet_id)
            elif tweet_data.get('cache_complete'):
                analysis['tweets_by_stage']['cache_only'].append(tweet_id)
            else:
                analysis['tweets_by_stage']['not_started'].append(tweet_id)
        
        # Count errors
        for tweet_data in tweets_data_map.values():
            if tweet_data.get('_cache_error'):
                analysis['error_summary']['cache_errors'] += 1
            if tweet_data.get('_media_error'):
                analysis['error_summary']['media_errors'] += 1
            if tweet_data.get('_llm_error'):
                analysis['error_summary']['llm_errors'] += 1
            if tweet_data.get('_kbitem_error'):
                analysis['error_summary']['kb_item_errors'] += 1
            if tweet_data.get('_db_error'):
                analysis['error_summary']['db_errors'] += 1
        
        return analysis
    
    def _is_phase_complete(self, phase: ProcessingPhase, tweet_data: Dict[str, Any]) -> bool:
        """Check if a specific phase is complete for a tweet."""
        if phase == ProcessingPhase.CACHE:
            return tweet_data.get('cache_complete', False)
        elif phase == ProcessingPhase.MEDIA:
            return tweet_data.get('media_processed', False)
        elif phase == ProcessingPhase.LLM:
            return tweet_data.get('categories_processed', False)
        elif phase == ProcessingPhase.KB_ITEM:
            return tweet_data.get('kb_item_created', False)
        elif phase == ProcessingPhase.DB_SYNC:
            return tweet_data.get('db_synced', False)
        # Global phases' completion status is not stored per tweet.
        # This would need to be checked via a different mechanism.
        elif phase in [ProcessingPhase.SYNTHESIS, ProcessingPhase.EMBEDDING]:
            return False # Placeholder
        return False