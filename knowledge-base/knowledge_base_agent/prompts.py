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

def prompt_yes_no(question: str) -> bool:
    """Standard yes/no prompt."""
    return input(f"{question} (y/n): ").strip().lower() == 'y'

def prompt_with_retry(operation: Callable, max_retries: int = 3) -> Any:
    """Execute an operation with retry prompts."""
    for attempt in range(max_retries):
        try:
            return operation()
        except Exception as e:
            if attempt < max_retries - 1:
                if prompt_yes_no(f"Operation failed: {e}. Retry?"):
                    continue
            raise

def prompt_for_preferences() -> UserPreferences:
    """Prompt user for their preferences on this run."""
    print("\n=== Knowledge Base Agent Configuration ===")
    print("Please answer the following questions to configure this run:\n")
    
    prefs = UserPreferences(
        update_bookmarks=input("Fetch new bookmarks? (y/n): ").lower().startswith('y'),
        review_existing=input("Re-review previously processed tweets? (y/n): ").lower().startswith('y'),
        recreate_tweet_cache=input("Re-cache all tweet data? (y/n): ").lower().startswith('y'),
        regenerate_readme=input("Regenerate knowledge base README? (y/n): ").lower().startswith('y'),
        sync_to_github=input("Sync changes to GitHub? (y/n): ").lower().startswith('y')
    )
    
    print("\nConfiguration complete. Starting agent...\n")
    return prefs 