from typing import Callable, Any, Dict
import logging
from dataclasses import dataclass

@dataclass
class UserPreferences:
    """Store user preferences for agent operation."""
    update_bookmarks: bool
    review_existing: bool
    regenerate_readme: bool
    push_to_github: bool
    recreate_tweet_cache: bool

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
    print("\n=== Knowledge Base Agent Configuration ===\n")
    prefs = UserPreferences()
    
    prefs.update_bookmarks = input("Update bookmarks? (y/n): ").lower().startswith('y')
    prefs.review_existing = input("Re-review existing items? (y/n): ").lower().startswith('y')
    prefs.regenerate_readme = input("Regenerate root README? (y/n): ").lower().startswith('y')
    prefs.push_to_github = input("Push changes to GitHub? (y/n): ").lower().startswith('y')
    prefs.recreate_tweet_cache = input("Reprocess cached tweets? (y/n): ").lower().startswith('y')
    
    return prefs

def prompt_for_maintenance() -> Dict[str, bool]:
    """Prompt user for maintenance operations."""
    return {
        "reprocess": prompt_yes_no("Re-review existing items?"),
        "regenerate_readme": prompt_yes_no("Regenerate root README?"),
        "push_changes": prompt_yes_no("Push changes to GitHub?")
    } 