from typing import Callable, Any
import logging

def prompt_yes_no(question: str) -> bool:
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