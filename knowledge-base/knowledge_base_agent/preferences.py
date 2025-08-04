"""
User Preferences Management

This module handles user preferences for agent execution, including configuration
loading, validation, and persistence. It provides a clean interface for managing
agent execution preferences separate from prompt generation functionality.
"""

from pathlib import Path
from typing import Optional, Dict, Any
import logging
from dataclasses import dataclass
from .config import Config


@dataclass
class UserPreferences:
    """
    Defines user preferences for an agent run, controlling which phases are executed
    and whether certain operations should be forced.
    """
    run_mode: str = "full_pipeline"  # Options: 'full_pipeline', 'fetch_only', 'git_sync_only', 'synthesis_only', 'embedding_only'
    
    # Skip flags, primarily for 'full_pipeline' mode
    skip_fetch_bookmarks: bool = False  # If True, fetching new bookmarks is skipped.
    skip_process_content: bool = False # If True, processing of queued/selected content is skipped.
    skip_readme_generation: bool = False  # If True, README regeneration is skipped unless other conditions force it (e.g., new items and no skip flag). (Default False to enable README generation)
    skip_git_push: bool = False         # If True, Git push is skipped. (Default False to enable pushing if git is configured)
    skip_synthesis_generation: bool = False  # If True, synthesis generation is skipped.
    skip_embedding_generation: bool = False # If True, embedding generation is skipped.

    # Force flags
    force_recache_tweets: bool = False     # If True, forces re-downloading of tweet data during content processing.
    force_regenerate_synthesis: bool = False  # If True, forces regeneration of existing synthesis documents.
    force_regenerate_embeddings: bool = False # If True, forces regeneration of embeddings.
    force_regenerate_readme: bool = False  # If True, forces regeneration of README even if up to date.
    
    # Granular force flags for content processing phases
    force_reprocess_media: bool = False    # If True, forces re-analyzing media even if already processed
    force_reprocess_llm: bool = False      # If True, forces re-running LLM categorization & naming
    force_reprocess_kb_item: bool = False  # If True, forces regeneration of KB items
    # force_reprocess_db_sync removed - using unified database approach
    
    # Legacy/combined flag - maintained for backward compatibility
    # When set to True, it will activate all the granular force flags above
    force_reprocess_content: bool = False  # If True, forces reprocessing all content phases

    # Synthesis configuration
    synthesis_mode: str = "comprehensive"  # Options: 'comprehensive', 'technical_deep_dive', 'practical_guide'
    synthesis_min_items: int = 3           # Minimum items required for synthesis generation
    synthesis_max_items: int = 50          # Maximum items to include in single synthesis

    def __post_init__(self):
        # Convert string 'on'/'off' (typically from HTML forms) to boolean for flag fields.
        # This ensures that values coming from web forms are correctly interpreted.
        
        # If the combined force_reprocess_content is True, set all granular force flags
        if self.force_reprocess_content:
            self.force_reprocess_media = True
            self.force_reprocess_llm = True
            self.force_reprocess_kb_item = True
            # force_reprocess_db_sync removed - using unified database approach
        
        bool_flags = [
            'skip_fetch_bookmarks',
            'skip_process_content',
            'skip_readme_generation',
            'skip_git_push',
            'skip_synthesis_generation',
            'skip_embedding_generation',
            'force_recache_tweets',
            'force_reprocess_content',
            'force_reprocess_media',
            'force_reprocess_llm', 
            'force_reprocess_kb_item',
            # force_reprocess_db_sync removed - using unified database approach
            'force_regenerate_synthesis',
            'force_regenerate_embeddings',
            'force_regenerate_readme'
        ]

        for flag_name in bool_flags:
            value = getattr(self, flag_name)
            if isinstance(value, str):
                # If the attribute is a string, convert 'on' (case-insensitive) to True,
                # and anything else (like 'off' or other strings) to False.
                setattr(self, flag_name, value.lower() == 'on')
            elif not isinstance(value, bool):
                # If it's not a string and not a bool (e.g., None or some other type),
                # coerce it to bool using Python's standard truthiness,
                # then ensure it's explicitly True/False. This handles cases where
                # the default value might be None and we want a clear boolean.
                # However, given the type hints, this path should ideally not be hit
                # if inputs conform to string or boolean.
                # For safety, we default to False if it's an unexpected type after initial coercion.
                setattr(self, flag_name, bool(value))


def load_user_preferences(config: Optional[Config] = None) -> UserPreferences:
    """
    Loads default UserPreferences.
    
    Currently, this returns a new UserPreferences object with default values.
    It can be extended to load preferences from a file if needed, using the config.
    The `config` parameter is optional and not used in the current basic implementation
    but is included for future extensibility (e.g., loading from a path in config).
    """
    # logging.debug(f"Loading default UserPreferences. Config provided: {bool(config)}")
    return UserPreferences()


def save_user_preferences(preferences: dict, config: Optional[Config] = None) -> UserPreferences:
    """
    Validates and saves user preferences.
    For now, this validates and returns the dataclass.
    Can be extended to save to a file.
    """
    try:
        # Validate by creating a UserPreferences instance
        prefs_instance = UserPreferences(**preferences)
        return prefs_instance
    except TypeError as e:
        raise ValueError(f"Invalid preferences data provided: {e}")