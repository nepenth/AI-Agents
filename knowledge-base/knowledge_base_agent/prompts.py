from pathlib import Path
from typing import Callable, Any, Dict
import logging
from dataclasses import dataclass

@dataclass
class UserPreferences:
    """Store user preferences for agent operation."""
    update_bookmarks: bool = False
    review_existing: bool = False
    regenerate_readme: bool = False
    sync_to_github: bool = False
    recreate_tweet_cache: bool = False

def check_knowledge_base_state(config) -> Dict[str, bool]:
    """Check the current state of the knowledge base."""
    state = {
        'has_processed_tweets': False,
        'has_cached_tweets': False,
        'has_readme': False,
        'has_kb_items': False
    }
    
    # Check for processed tweets in state
    if Path(config.data_processing_dir / "processed_tweets.json").exists():
        state['has_processed_tweets'] = True
    
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

def prompt_for_preferences(config) -> UserPreferences:
    """Prompt user for their preferences based on current knowledge base state."""
    print("\n=== Knowledge Base Agent Configuration ===")
    print("Please answer the following questions to configure this run:\n")
    
    kb_state = check_knowledge_base_state(config)
    prefs = UserPreferences()
    
    # Always prompt for bookmarks update
    prefs.update_bookmarks = input("Fetch new bookmarks? (y/n): ").lower().startswith('y')
    
    # Only prompt for review if there are processed tweets
    if kb_state['has_processed_tweets']:
        prefs.review_existing = input("Re-review previously processed tweets? (y/n): ").lower().startswith('y')
    
    # Only prompt for cache refresh if there is cached data
    if kb_state['has_cached_tweets']:
        prefs.recreate_tweet_cache = input("Re-cache all tweet data? (y/n): ").lower().startswith('y')
    
    # README generation is automatic if it doesn't exist
    prefs.regenerate_readme = not kb_state['has_readme']
    
    # Only prompt for GitHub sync if we have knowledge base items
    if kb_state['has_kb_items']:
        prefs.sync_to_github = input("Sync changes to GitHub? (y/n): ").lower().startswith('y')
    
    print("\nConfiguration complete. Starting agent...\n")
    return prefs 