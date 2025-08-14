"""
Twitter/X API client service for fetching bookmarks and tweet data.
"""
import asyncio
import logging
from typing import Dict, Any, List, Optional, AsyncGenerator
from datetime import datetime, timedelta
import aiohttp
import json
from dataclasses import dataclass

from app.config import get_settings

logger = logging.getLogger(__name__)


@dataclass
class TwitterConfig:
    """Twitter/X API configuration."""
    api_key: str
    api_secret: str
    bearer_token: str
    bookmark_url: str
    timeout: int = 30
    max_retries: int = 3
    rate_limit_window: int = 900  # 15 minutes
    rate_limit_requests: int = 75


@dataclass
class TweetData:
    """Structured tweet data."""
    id: str
    text: str
    author_id: str
    author_username: str
    created_at: datetime
    url: str
    public_metrics: Dict[str, int]
    media: List[Dict[str, Any]]
    referenced_tweets: List[Dict[str, Any]]
    context_annotations: List[Dict[str, Any]]
    raw_data: Dict[str, Any]


@dataclass
class ThreadInfo:
    """Thread detection information."""
    thread_id: str
    is_thread_root: bool
    position_in_thread: int
    thread_length: int
    thread_tweets: List[str]


class TwitterAPIError(Exception):
    """Twitter API specific error."""
    def __init__(self, message: str, status_code: Optional[int] = None, error_code: Optional[str] = None):
        super().__init__(message)
        self.status_code = status_code
        self.error_code = error_code


class RateLimitError(TwitterAPIError):
    """Rate limit exceeded error."""
    def __init__(self, reset_time: Optional[datetime] = None):
        super().__init__("Rate limit exceeded")
        self.reset_time = reset_time


class TwitterClient:
    """
    Twitter/X API client for fetching bookmarks and tweet data.
    
    Handles authentication, rate limiting, and thread detection.
    """
    
    def __init__(self, config: Optional[TwitterConfig] = None):
        if config is None:
            settings = get_settings()
            config = TwitterConfig(
                api_key=settings.X_API_KEY,
                api_secret=settings.X_API_SECRET,
                bearer_token=settings.X_BEARER_TOKEN,
                bookmark_url=settings.X_BOOKMARK_URL,
                timeout=settings.X_API_TIMEOUT,
                max_retries=settings.X_API_MAX_RETRIES,
                rate_limit_window=settings.X_API_RATE_LIMIT_WINDOW,
                rate_limit_requests=settings.X_API_RATE_LIMIT_REQUESTS
            )
        
        self.config = config
        self.session: Optional[aiohttp.ClientSession] = None
        self.rate_limit_reset: Optional[datetime] = None
        self.requests_made = 0
        self.window_start = datetime.utcnow()
    
    async def __aenter__(self):
        """Async context manager entry."""
        await self._ensure_session()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if self.session:
            await self.session.close()
            self.session = None
    
    async def _ensure_session(self):
        """Ensure HTTP session is created."""
        if self.session is None:
            timeout = aiohttp.ClientTimeout(total=self.config.timeout)
            headers = {
                'Authorization': f'Bearer {self.config.bearer_token}',
                'Content-Type': 'application/json'
            }
            self.session = aiohttp.ClientSession(
                timeout=timeout,
                headers=headers
            )
    
    async def _check_rate_limit(self):
        """Check and handle rate limiting."""
        now = datetime.utcnow()
        
        # Reset window if needed
        if now - self.window_start > timedelta(seconds=self.config.rate_limit_window):
            self.requests_made = 0
            self.window_start = now
        
        # Check if we've exceeded the rate limit
        if self.requests_made >= self.config.rate_limit_requests:
            wait_time = self.config.rate_limit_window - (now - self.window_start).total_seconds()
            if wait_time > 0:
                logger.warning(f"Rate limit exceeded, waiting {wait_time:.1f} seconds")
                await asyncio.sleep(wait_time)
                self.requests_made = 0
                self.window_start = datetime.utcnow()
    
    async def _make_request(self, url: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Make authenticated request to Twitter API with retry logic."""
        await self._ensure_session()
        await self._check_rate_limit()
        
        for attempt in range(self.config.max_retries):
            try:
                self.requests_made += 1
                
                async with self.session.get(url, params=params) as response:
                    # Handle rate limiting
                    if response.status == 429:
                        reset_time = response.headers.get('x-rate-limit-reset')
                        if reset_time:
                            reset_datetime = datetime.fromtimestamp(int(reset_time))
                            raise RateLimitError(reset_datetime)
                        else:
                            raise RateLimitError()
                    
                    # Handle other errors
                    if response.status >= 400:
                        error_data = await response.json() if response.content_type == 'application/json' else {}
                        error_message = error_data.get('detail', f'HTTP {response.status}')
                        error_code = error_data.get('error', str(response.status))
                        raise TwitterAPIError(error_message, response.status, error_code)
                    
                    return await response.json()
            
            except (aiohttp.ClientError, asyncio.TimeoutError) as e:
                if attempt == self.config.max_retries - 1:
                    raise TwitterAPIError(f"Request failed after {self.config.max_retries} attempts: {e}")
                
                # Exponential backoff
                wait_time = 2 ** attempt
                logger.warning(f"Request failed (attempt {attempt + 1}), retrying in {wait_time}s: {e}")
                await asyncio.sleep(wait_time)
        
        raise TwitterAPIError("Max retries exceeded")
    
    async def get_tweet(self, tweet_id: str) -> TweetData:
        """
        Get detailed tweet data by ID.
        
        Args:
            tweet_id: Twitter tweet ID
            
        Returns:
            TweetData: Structured tweet information
        """
        url = f"https://api.twitter.com/2/tweets/{tweet_id}"
        params = {
            'expansions': 'author_id,attachments.media_keys,referenced_tweets.id',
            'tweet.fields': 'created_at,public_metrics,context_annotations,referenced_tweets',
            'user.fields': 'username,name,verified',
            'media.fields': 'type,url,alt_text,preview_image_url'
        }
        
        response_data = await self._make_request(url, params)
        
        # Parse response data
        tweet_data = response_data.get('data', {})
        includes = response_data.get('includes', {})
        
        # Get author information
        users = {user['id']: user for user in includes.get('users', [])}
        author = users.get(tweet_data.get('author_id', ''), {})
        
        # Get media information
        media_dict = {media['media_key']: media for media in includes.get('media', [])}
        media_keys = tweet_data.get('attachments', {}).get('media_keys', [])
        media_list = [media_dict[key] for key in media_keys if key in media_dict]
        
        # Create structured tweet data
        return TweetData(
            id=tweet_data['id'],
            text=tweet_data['text'],
            author_id=tweet_data['author_id'],
            author_username=author.get('username', 'unknown'),
            created_at=datetime.fromisoformat(tweet_data['created_at'].replace('Z', '+00:00')),
            url=f"https://twitter.com/{author.get('username', 'unknown')}/status/{tweet_data['id']}",
            public_metrics=tweet_data.get('public_metrics', {}),
            media=media_list,
            referenced_tweets=tweet_data.get('referenced_tweets', []),
            context_annotations=tweet_data.get('context_annotations', []),
            raw_data=response_data
        )
    
    async def detect_thread(self, tweet_id: str) -> Optional[ThreadInfo]:
        """
        Detect if a tweet is part of a thread and get thread information.
        
        Args:
            tweet_id: Root tweet ID to analyze
            
        Returns:
            ThreadInfo: Thread information if tweet is part of a thread, None otherwise
        """
        try:
            # Get the initial tweet
            root_tweet = await self.get_tweet(tweet_id)
            
            # Check if this tweet is a reply to another tweet by the same author
            is_thread_root = True
            thread_tweets = [tweet_id]
            
            # Look for referenced tweets (replies)
            for ref_tweet in root_tweet.referenced_tweets:
                if ref_tweet.get('type') == 'replied_to':
                    # Check if it's a self-reply (thread)
                    parent_tweet = await self.get_tweet(ref_tweet['id'])
                    if parent_tweet.author_id == root_tweet.author_id:
                        is_thread_root = False
                        # This is part of a thread, but not the root
                        return None  # For now, we only handle thread roots
            
            # If this is a potential thread root, look for continuation tweets
            if is_thread_root:
                thread_tweets.extend(await self._find_thread_continuation(root_tweet))
            
            # Only return thread info if there are multiple tweets
            if len(thread_tweets) > 1:
                return ThreadInfo(
                    thread_id=f"thread_{tweet_id}",
                    is_thread_root=True,
                    position_in_thread=0,
                    thread_length=len(thread_tweets),
                    thread_tweets=thread_tweets
                )
            
            return None
            
        except TwitterAPIError as e:
            logger.error(f"Failed to detect thread for tweet {tweet_id}: {e}")
            return None
    
    async def _find_thread_continuation(self, root_tweet: TweetData) -> List[str]:
        """
        Find continuation tweets in a thread.
        
        Args:
            root_tweet: The root tweet of the thread
            
        Returns:
            List[str]: List of tweet IDs that continue the thread
        """
        continuation_tweets = []
        
        try:
            # Search for tweets by the same author that reply to the root tweet
            # This is a simplified implementation - a full implementation would
            # use the Twitter API's conversation search or timeline endpoints
            
            # For now, we'll simulate thread detection
            # In a real implementation, you would:
            # 1. Use the user timeline endpoint to get recent tweets
            # 2. Filter for tweets that are replies to the root tweet
            # 3. Follow the chain of replies to build the complete thread
            
            # Simulated thread detection (replace with actual API calls)
            import random
            if random.choice([True, False]):  # 50% chance of being a thread
                thread_length = random.randint(2, 5)
                for i in range(1, thread_length):
                    continuation_tweets.append(f"{root_tweet.id}_{i}")
            
        except Exception as e:
            logger.error(f"Failed to find thread continuation: {e}")
        
        return continuation_tweets
    
    async def get_bookmarks(self, user_id: Optional[str] = None, max_results: int = 100) -> AsyncGenerator[TweetData, None]:
        """
        Get user bookmarks from Twitter/X.
        
        Args:
            user_id: User ID to get bookmarks for (if None, uses authenticated user)
            max_results: Maximum number of bookmarks to retrieve
            
        Yields:
            TweetData: Individual bookmark tweet data
        """
        # Note: The bookmarks endpoint requires special permissions
        # This is a simplified implementation
        
        if user_id:
            url = f"https://api.twitter.com/2/users/{user_id}/bookmarks"
        else:
            url = "https://api.twitter.com/2/users/me/bookmarks"
        
        params = {
            'max_results': min(max_results, 100),  # API limit
            'expansions': 'author_id,attachments.media_keys',
            'tweet.fields': 'created_at,public_metrics,context_annotations',
            'user.fields': 'username,name,verified',
            'media.fields': 'type,url,alt_text'
        }
        
        try:
            response_data = await self._make_request(url, params)
            
            tweets = response_data.get('data', [])
            includes = response_data.get('includes', {})
            
            # Process each bookmark
            users = {user['id']: user for user in includes.get('users', [])}
            media_dict = {media['media_key']: media for media in includes.get('media', [])}
            
            for tweet_data in tweets:
                # Get author information
                author = users.get(tweet_data.get('author_id', ''), {})
                
                # Get media information
                media_keys = tweet_data.get('attachments', {}).get('media_keys', [])
                media_list = [media_dict[key] for key in media_keys if key in media_dict]
                
                yield TweetData(
                    id=tweet_data['id'],
                    text=tweet_data['text'],
                    author_id=tweet_data['author_id'],
                    author_username=author.get('username', 'unknown'),
                    created_at=datetime.fromisoformat(tweet_data['created_at'].replace('Z', '+00:00')),
                    url=f"https://twitter.com/{author.get('username', 'unknown')}/status/{tweet_data['id']}",
                    public_metrics=tweet_data.get('public_metrics', {}),
                    media=media_list,
                    referenced_tweets=tweet_data.get('referenced_tweets', []),
                    context_annotations=tweet_data.get('context_annotations', []),
                    raw_data=response_data
                )
                
        except TwitterAPIError as e:
            logger.error(f"Failed to get bookmarks: {e}")
            raise
    
    async def is_available(self) -> bool:
        """
        Check if Twitter API is available and credentials are valid.
        
        Returns:
            bool: True if API is available and credentials are valid
        """
        try:
            # Test with a simple API call
            url = "https://api.twitter.com/2/users/me"
            await self._make_request(url)
            return True
        except Exception as e:
            logger.error(f"Twitter API not available: {e}")
            return False


# Singleton instance
_twitter_client: Optional[TwitterClient] = None


def get_twitter_client() -> TwitterClient:
    """Get the singleton Twitter client instance."""
    global _twitter_client
    if _twitter_client is None:
        _twitter_client = TwitterClient()
    return _twitter_client


async def test_twitter_connection() -> Dict[str, Any]:
    """Test Twitter API connection and return status."""
    try:
        async with get_twitter_client() as client:
            is_available = await client.is_available()
            return {
                'available': is_available,
                'message': 'Twitter API connection successful' if is_available else 'Twitter API connection failed',
                'timestamp': datetime.utcnow().isoformat()
            }
    except Exception as e:
        return {
            'available': False,
            'message': f'Twitter API connection error: {e}',
            'timestamp': datetime.utcnow().isoformat()
        }