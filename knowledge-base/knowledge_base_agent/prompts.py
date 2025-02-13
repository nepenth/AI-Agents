from typing import Callable, Any, Dict
import logging
from dataclasses import dataclass

@dataclass
class UserPreferences:
    """Store user preferences for agent operation."""
    update_bookmarks: bool
    review_existing: bool
    update_readme: bool
    push_changes: bool
    recreate_cache: bool

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
    """Prompt user for all agent preferences."""
    print("\n=== Knowledge Base Agent Configuration ===\n")
    return UserPreferences(
        update_bookmarks=prompt_yes_no("Update bookmarks?"),
        review_existing=prompt_yes_no("Re-review existing items?"),
        update_readme=prompt_yes_no("Regenerate root README?"),
        push_changes=prompt_yes_no("Push changes to GitHub?"),
        recreate_cache=prompt_yes_no("Recreate all tweet cache data?")
    )

def prompt_for_maintenance() -> Dict[str, bool]:
    """Prompt user for maintenance operations."""
    return {
        "reprocess": prompt_yes_no("Re-review existing items?"),
        "regenerate_readme": prompt_yes_no("Regenerate root README?"),
        "push_changes": prompt_yes_no("Push changes to GitHub?")
    } 