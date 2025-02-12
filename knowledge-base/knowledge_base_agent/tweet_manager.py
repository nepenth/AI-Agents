from pathlib import Path
from typing import List, Optional
from dataclasses import dataclass

@dataclass
class Tweet:
    id: str
    text: str
    processed: bool = False

class TweetManager:
    def __init__(self, root_dir: Path):
        self.root_dir = root_dir
        self.tweets: List[Tweet] = []  # In practice, you'd probably load these from storage
        
    def get_unprocessed_tweets(self) -> List[Tweet]:
        """Get list of unprocessed tweets"""
        return [t for t in self.tweets if not t.processed]
        
    def mark_processed(self, tweet: Tweet) -> None:
        """Mark a tweet as processed"""
        tweet.processed = True 