from typing import Optional
from pathlib import Path
import re

def validate_tweet_url(url: str) -> bool:
    """Validate tweet URL format."""
    twitter_pattern = r'https?://(?:mobile\.)?twitter\.com/\w+/status/\d+'
    return bool(re.match(twitter_pattern, url))

def validate_category_name(name: str) -> bool:
    """Validate category name format."""
    return bool(name and len(name) <= 100 and not any(c in r'\/:*?"<>|' for c in name))

def validate_file_structure(root_dir: Path) -> list[str]:
    """Validate knowledge base directory structure."""
    errors = []
    if not root_dir.exists():
        errors.append(f"Root directory {root_dir} does not exist")
        return errors
    
    for main_cat in root_dir.iterdir():
        if not main_cat.is_dir():
            continue
        for sub_cat in main_cat.iterdir():
            if not sub_cat.is_dir():
                continue
            for item_dir in sub_cat.iterdir():
                if not item_dir.is_dir():
                    continue
                # Check for required files
                if not (item_dir / "README.md").exists():
                    errors.append(f"Missing README.md in {item_dir}")
                
    return errors