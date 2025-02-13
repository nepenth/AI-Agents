import re
import logging
from pathlib import Path
from typing import Optional, List

def parse_tweet_id_from_url(url: str) -> Optional[str]:
    """Extract tweet ID from a tweet URL."""
    match = re.search(r"/status/(\d+)", url)
    if match:
        return match.group(1)
    else:
        logging.warning(f"Could not parse tweet ID from URL: {url}")
        return None

def sanitize_filename(filename: str, max_length: Optional[int] = 50) -> str:
    """
    Sanitize a string to be used as a filename.
    
    Args:
        filename: The string to sanitize
        max_length: Maximum length of the resulting filename
        
    Returns:
        A sanitized string safe for use as a filename
    """
    sanitized = re.sub(r'[<>:"/\\|?*]', '', filename)
    sanitized = re.sub(r'\s+', '_', sanitized.strip())
    
    if max_length and len(sanitized) > max_length:
        sanitized = sanitized[:max_length]
    
    return sanitized.lower()

def load_tweet_urls_from_links(file_path: Path) -> List[str]:
    """Load tweet URLs from a file."""
    tweet_urls = []
    if not file_path.exists():
        logging.error(f"Tweet links file {file_path} does not exist.")
        return tweet_urls
    try:
        with file_path.open('r', encoding='utf-8') as f:
            for line_number, line in enumerate(f, start=1):
                url = line.strip()
                if not url:
                    continue
                tweet_id = parse_tweet_id_from_url(url)
                if tweet_id:
                    tweet_urls.append(url)
                else:
                    logging.warning(f"Line {line_number}: Invalid URL format: {url}")
    except Exception as e:
        logging.error(f"Error reading tweet links from {file_path}: {e}")
    return tweet_urls
