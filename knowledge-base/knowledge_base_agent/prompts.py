from pathlib import Path
from typing import Callable, Any, Dict, List, Optional
import logging
from dataclasses import dataclass, field
import json
from knowledge_base_agent.config import Config

# Default User Preferences (can be overridden by UI)
# These guide the agent's operational choices during a run.
@dataclass
class UserPreferences:
    """
    Defines user preferences for an agent run, controlling which phases are executed
    and whether certain operations should be forced.
    """
    run_mode: str = "full_pipeline"  # Options: 'full_pipeline', 'fetch_only', 'git_sync_only'
    
    # Skip flags, primarily for 'full_pipeline' mode
    skip_fetch_bookmarks: bool = False  # If True, fetching new bookmarks is skipped.
    skip_process_content: bool = False # If True, processing of queued/selected content is skipped.
    skip_readme_generation: bool = True  # If True, README regeneration is skipped unless other conditions force it (e.g., new items and no skip flag). (Default True as README regen is not always desired)
    skip_git_push: bool = False         # If True, Git push is skipped. (Default False to enable pushing if git is configured)

    # Force flags
    force_recache_tweets: bool = False     # If True, forces re-downloading of tweet data during content processing.
    force_reprocess_content: bool = False  # If True, forces LLM categorization/naming and KB item generation for content being processed, even if previously processed.

    # Legacy fields for reference or potential future granular control, currently superseded by the above.
    # update_bookmarks: bool = True 
    # process_queued_content: bool = True
    # force_recache: bool = False # Replaced by force_recache_tweets
    # regenerate_readme: bool = False # Covered by skip_readme_generation logic
    # git_push: bool = True # Covered by skip_git_push logic

    def __post_init__(self):
        # Convert string 'on'/'off' (typically from HTML forms) to boolean for flag fields.
        # This ensures that values coming from web forms are correctly interpreted.
        
        bool_flags = [
            'skip_fetch_bookmarks',
            'skip_process_content',
            'skip_readme_generation',
            'skip_git_push',
            'force_recache_tweets',
            'force_reprocess_content'
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
        # No explicit pass needed here

def check_knowledge_base_state(config) -> Dict[str, bool]:
    """Check the current state of the knowledge base."""
    state = {
        'has_kb_items': False,
        'has_readme': False,
        'has_processed_tweets': False,
        'has_cached_tweets': False
    }
    
    # Check for processed tweets in state file and its content
    if Path(config.processed_tweets_file).exists():
        try:
            with open(config.processed_tweets_file, 'r') as f:
                processed_tweets = json.load(f)
                state['has_processed_tweets'] = bool(processed_tweets)  # True only if there are actual tweets
        except (FileNotFoundError, json.JSONDecodeError):
            state['has_processed_tweets'] = False
    
    # Check for cached tweet data
    if list(config.media_cache_dir.glob("*.json")):
        state['has_cached_tweets'] = True
    
    # Check for README
    if (config.knowledge_base_dir / "README.md").exists():
        state['has_readme'] = True
    
    # Check for knowledge base items
    if list(config.knowledge_base_dir.glob("**/*.md")):
        state['has_kb_items'] = True
    
    return state

def prompt_for_preferences(config: Config) -> UserPreferences:
    """Prompt user for preferences."""
    prefs = UserPreferences()
    kb_state = check_knowledge_base_state(config)

    prefs.update_bookmarks = input("Fetch new bookmarks? (y/n): ").lower().startswith('y')
    
    # Prompt for processing queued content
    prefs.process_queued_content = input("Process all queued/unprocessed content? (y/n, default y): ").lower() not in ['n', 'no']

    # Only prompt for cache refresh if there is cached data
    if kb_state['has_cached_tweets']:
        prefs.force_recache_tweets = input("Force re-cache of all tweet data for unprocessed items? (y/n): ").lower().startswith('y')
    
    # README generation can be forced
    prefs.skip_readme_generation = input("Skip regeneration of all README files? (y/n): ").lower().startswith('y')

    # Git push preference
    if config.git_enabled:
        prefs.skip_git_push = input("Skip pushing changes to Git repository after processing? (y/n, default n): ").lower() not in ['n', 'no']
    else:
        prefs.skip_git_push = True # Ensure it's True if git is not enabled globally

    logging.info(f"User preferences set: {prefs}")
    return prefs 

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

class LLMPrompts:
    # ... (existing content)
    pass 