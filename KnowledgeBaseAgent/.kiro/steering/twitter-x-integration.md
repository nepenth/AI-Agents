# Twitter/X Integration Patterns

This document defines the patterns and best practices for integrating with Twitter/X API and processing Twitter/X-specific content.

## Twitter/X API Integration

### 1. Authentication and Rate Limiting

**API Authentication Pattern**:
```python
class TwitterClient:
    def __init__(self, bearer_token: str):
        self.bearer_token = bearer_token
        self.session = aiohttp.ClientSession(
            headers={"Authorization": f"Bearer {bearer_token}"}
        )
        self.rate_limiter = RateLimiter(
            requests_per_window=300,
            window_seconds=900  # 15 minutes
        )
    
    async def make_request(self, endpoint: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Make rate-limited request to Twitter/X API."""
        await self.rate_limiter.acquire()
        
        try:
            async with self.session.get(endpoint, params=params) as response:
                if response.status == 429:  # Rate limited
                    retry_after = int(response.headers.get('x-rate-limit-reset', 900))
                    await asyncio.sleep(retry_after)
                    return await self.make_request(endpoint, params)
                
                response.raise_for_status()
                return await response.json()
        except aiohttp.ClientError as e:
            logger.error(f"Twitter API request failed: {e}")
            raise TwitterAPIError(f"API request failed: {e}")
```

**Rate Limiting Best Practices**:
- Implement exponential backoff for rate limit errors
- Track rate limit headers and adjust request timing
- Use batch requests when possible to minimize API calls
- Cache responses to avoid duplicate requests

### 2. Bookmark Fetching

**Bookmark Retrieval Pattern**:
```python
class BookmarkFetcher:
    async def fetch_bookmarks(self, bookmark_url: str, max_results: int = 100) -> List[Dict[str, Any]]:
        """Fetch bookmarks from Twitter/X API or bookmark export."""
        if bookmark_url.startswith("https://api.twitter.com"):
            return await self.fetch_from_api(max_results)
        elif bookmark_url.endswith(".json"):
            return await self.fetch_from_export_file(bookmark_url)
        else:
            raise ValueError(f"Unsupported bookmark source: {bookmark_url}")
    
    async def fetch_from_api(self, max_results: int) -> List[Dict[str, Any]]:
        """Fetch bookmarks directly from Twitter/X API."""
        bookmarks = []
        pagination_token = None
        
        while len(bookmarks) < max_results:
            params = {
                "max_results": min(100, max_results - len(bookmarks)),
                "tweet.fields": "created_at,public_metrics,attachments,author_id,context_annotations",
                "user.fields": "username,name,verified",
                "media.fields": "type,url,preview_image_url,alt_text",
                "expansions": "author_id,attachments.media_keys"
            }
            
            if pagination_token:
                params["pagination_token"] = pagination_token
            
            response = await self.twitter_client.make_request(
                "https://api.twitter.com/2/users/me/bookmarks",
                params
            )
            
            # Process response and extract bookmark data
            batch_bookmarks = self.process_bookmark_response(response)
            bookmarks.extend(batch_bookmarks)
            
            # Check for pagination
            pagination_token = response.get("meta", {}).get("next_token")
            if not pagination_token:
                break
        
        return bookmarks[:max_results]
    
    async def fetch_from_export_file(self, file_url: str) -> List[Dict[str, Any]]:
        """Fetch bookmarks from exported JSON file."""
        # Download and parse bookmark export file
        async with aiohttp.ClientSession() as session:
            async with session.get(file_url) as response:
                response.raise_for_status()
                export_data = await response.json()
        
        # Transform export format to standard bookmark format
        return self.transform_export_to_bookmarks(export_data)
```

### 3. Thread Detection and Processing

**Thread Detection Pattern**:
```python
class ThreadDetector:
    async def detect_thread(self, tweet_id: str, author_id: str) -> Optional[Dict[str, Any]]:
        """Detect if a tweet is part of a thread and get thread information."""
        # Check if tweet is a reply to another tweet by the same author
        tweet_data = await self.twitter_client.get_tweet(
            tweet_id,
            expansions=["in_reply_to_user_id", "referenced_tweets.id"]
        )
        
        if not tweet_data.get("in_reply_to_user_id"):
            # Not a reply, check if it's the start of a thread
            return await self.check_thread_root(tweet_id, author_id)
        
        # If replying to same author, it's likely part of a thread
        if tweet_data["in_reply_to_user_id"] == author_id:
            return await self.build_thread_info(tweet_id, author_id)
        
        return None
    
    async def check_thread_root(self, tweet_id: str, author_id: str) -> Optional[Dict[str, Any]]:
        """Check if this tweet is the root of a thread."""
        # Look for replies to this tweet by the same author
        replies = await self.twitter_client.search_tweets(
            query=f"conversation_id:{tweet_id} from:{author_id}",
            max_results=10
        )
        
        if len(replies.get("data", [])) > 0:
            # This is the root of a thread
            thread_length = await self.calculate_thread_length(tweet_id, author_id)
            return {
                "thread_id": tweet_id,  # Use root tweet ID as thread ID
                "is_root": True,
                "position": 1,
                "length": thread_length
            }
        
        return None
    
    async def build_thread_info(self, tweet_id: str, author_id: str) -> Dict[str, Any]:
        """Build complete thread information for a tweet."""
        # Find the root tweet of the thread
        root_tweet_id = await self.find_thread_root(tweet_id, author_id)
        
        # Get all tweets in the thread
        thread_tweets = await self.get_thread_tweets(root_tweet_id, author_id)
        
        # Find position of current tweet in thread
        position = next(
            (i + 1 for i, tweet in enumerate(thread_tweets) if tweet["id"] == tweet_id),
            1
        )
        
        return {
            "thread_id": root_tweet_id,
            "is_root": tweet_id == root_tweet_id,
            "position": position,
            "length": len(thread_tweets)
        }
```

**Thread Processing Pattern**:
```python
class ThreadProcessor:
    async def process_thread_as_unit(self, thread_id: str) -> Dict[str, Any]:
        """Process an entire thread as a cohesive unit."""
        # Get all tweets in the thread
        thread_tweets = await self.content_repo.get_thread_tweets(thread_id)
        
        if not thread_tweets:
            raise ValueError(f"No tweets found for thread {thread_id}")
        
        # Combine thread content for collective analysis
        combined_content = self.combine_thread_content(thread_tweets)
        
        # Generate thread-level understanding
        backend, model, params = await self.model_router.resolve(ModelPhase.kb_generation)
        
        thread_understanding = await backend.generate_text(
            prompt=self.build_thread_understanding_prompt(combined_content),
            model=model,
            **params
        )
        
        # Update all tweets in thread with collective understanding
        for tweet in thread_tweets:
            tweet.thread_collective_understanding = thread_understanding
            tweet.has_thread_understanding = True
            await self.content_repo.update(tweet)
        
        return {
            "thread_id": thread_id,
            "tweet_count": len(thread_tweets),
            "collective_understanding": thread_understanding,
            "processing_status": "completed"
        }
    
    def combine_thread_content(self, thread_tweets: List[ContentItem]) -> Dict[str, Any]:
        """Combine thread tweets into cohesive content for analysis."""
        # Sort tweets by position in thread
        sorted_tweets = sorted(thread_tweets, key=lambda t: t.position_in_thread or 0)
        
        # Combine text content
        combined_text = "\n\n".join([
            f"Tweet {tweet.position_in_thread}: {tweet.content}"
            for tweet in sorted_tweets
        ])
        
        # Combine media content
        all_media = []
        for tweet in sorted_tweets:
            if tweet.media_content:
                all_media.extend(tweet.media_content)
        
        # Combine engagement metrics
        total_engagement = sum(tweet.total_engagement for tweet in sorted_tweets)
        
        return {
            "combined_text": combined_text,
            "media_content": all_media,
            "total_engagement": total_engagement,
            "tweet_count": len(sorted_tweets),
            "thread_span": {
                "start": sorted_tweets[0].original_tweet_created_at,
                "end": sorted_tweets[-1].original_tweet_created_at
            }
        }
```

## Media Content Processing

### 1. Media Caching and Storage

**Media Caching Pattern**:
```python
class MediaCacheService:
    async def cache_media_list(self, media_list: List[Dict[str, Any]], content_id: str) -> List[Dict[str, Any]]:
        """Cache media content and return updated media list with local references."""
        cached_media = []
        
        for media_item in media_list:
            try:
                cached_item = await self.cache_single_media(media_item, content_id)
                cached_media.append(cached_item)
            except Exception as e:
                logger.warning(f"Failed to cache media {media_item.get('id')}: {e}")
                # Keep original media item if caching fails
                cached_media.append(media_item)
        
        return cached_media
    
    async def cache_single_media(self, media_item: Dict[str, Any], content_id: str) -> Dict[str, Any]:
        """Cache a single media item and return updated metadata."""
        media_url = media_item.get("url")
        if not media_url:
            return media_item
        
        # Generate cache key and local path
        cache_key = self.generate_cache_key(media_url, content_id)
        local_path = f"media_cache/{cache_key}"
        
        # Check if already cached
        if await self.is_cached(cache_key):
            return self.update_media_item_with_cache(media_item, cache_key, local_path)
        
        # Download and cache media
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(media_url) as response:
                    response.raise_for_status()
                    media_data = await response.read()
            
            # Store in cache (database BLOB or file system)
            await self.store_cached_media(cache_key, media_data, media_item.get("type"))
            
            # Update media item with cache information
            return self.update_media_item_with_cache(media_item, cache_key, local_path)
            
        except Exception as e:
            logger.error(f"Failed to download media from {media_url}: {e}")
            raise MediaCacheError(f"Failed to cache media: {e}")
    
    def update_media_item_with_cache(self, media_item: Dict[str, Any], cache_key: str, local_path: str) -> Dict[str, Any]:
        """Update media item with cache information."""
        return {
            **media_item,
            "cached": True,
            "cache_key": cache_key,
            "local_path": local_path,
            "original_url": media_item.get("url"),
            "cached_at": datetime.utcnow().isoformat()
        }
```

### 2. Vision Model Integration

**Media Analysis Pattern**:
```python
class TwitterMediaAnalyzer:
    async def analyze_tweet_media(self, content_item: ContentItem) -> Dict[str, Any]:
        """Analyze media content in a tweet using vision models."""
        if not content_item.media_content:
            return {"has_media": False, "analysis": None}
        
        # Get vision model
        backend, model, params = await self.model_router.resolve(ModelPhase.vision)
        
        media_analyses = []
        
        for media_item in content_item.media_content:
            # Build XML prompt for media analysis
            prompt = self.build_media_analysis_prompt(media_item, content_item)
            
            try:
                analysis = await backend.generate_text(prompt, model=model, **params)
                
                media_analyses.append({
                    "media_id": media_item.get("id"),
                    "media_type": media_item.get("type"),
                    "analysis": analysis,
                    "model_used": model,
                    "analyzed_at": datetime.utcnow().isoformat()
                })
                
            except Exception as e:
                logger.error(f"Failed to analyze media {media_item.get('id')}: {e}")
                media_analyses.append({
                    "media_id": media_item.get("id"),
                    "media_type": media_item.get("type"),
                    "analysis": None,
                    "error": str(e),
                    "analyzed_at": datetime.utcnow().isoformat()
                })
        
        return {
            "has_media": True,
            "media_count": len(content_item.media_content),
            "analyses": media_analyses,
            "vision_model_used": model
        }
    
    def build_media_analysis_prompt(self, media_item: Dict[str, Any], content_item: ContentItem) -> str:
        """Build XML prompt for media analysis."""
        media_type = media_item.get("type", "unknown")
        media_url = media_item.get("local_path") or media_item.get("url")
        
        return f"""
        <task>
            <instruction>Analyze this {media_type} content from a Twitter/X post and provide detailed description</instruction>
            <context>
                <tweet_text>{content_item.content}</tweet_text>
                <author>@{content_item.author_username}</author>
                <media_type>{media_type}</media_type>
                <media_url>{media_url}</media_url>
                <alt_text>{media_item.get('alt_text', 'No alt text provided')}</alt_text>
            </context>
            <output_format>
                <visual_description>Detailed description of what is shown in the media</visual_description>
                <key_elements>
                    <element>Important visual elements, objects, people, text, etc.</element>
                </key_elements>
                <context_relevance>How the media relates to and supports the tweet text</context_relevance>
                <technical_details>Any technical information visible (code, diagrams, charts, etc.)</technical_details>
                <emotional_tone>The mood or emotional impact of the media</emotional_tone>
            </output_format>
        </task>
        """
```

## Engagement Metrics and Analytics

### 1. Engagement Tracking

**Engagement Metrics Pattern**:
```python
class EngagementTracker:
    async def update_engagement_metrics(self, content_item: ContentItem, fresh_data: Dict[str, Any]) -> bool:
        """Update engagement metrics and return True if changed."""
        public_metrics = fresh_data.get("public_metrics", {})
        
        # Extract current metrics
        new_likes = public_metrics.get("like_count", 0)
        new_retweets = public_metrics.get("retweet_count", 0)
        new_replies = public_metrics.get("reply_count", 0)
        new_quotes = public_metrics.get("quote_count", 0)
        
        # Check if metrics have changed
        metrics_changed = (
            content_item.like_count != new_likes or
            content_item.retweet_count != new_retweets or
            content_item.reply_count != new_replies or
            content_item.quote_count != new_quotes
        )
        
        if metrics_changed:
            # Update metrics
            content_item.like_count = new_likes
            content_item.retweet_count = new_retweets
            content_item.reply_count = new_replies
            content_item.quote_count = new_quotes
            
            # Calculate total engagement
            content_item.total_engagement = new_likes + new_retweets + new_replies + new_quotes
            
            # Track engagement history
            await self.record_engagement_history(content_item)
            
            return True
        
        return False
    
    async def record_engagement_history(self, content_item: ContentItem):
        """Record engagement metrics history for trend analysis."""
        engagement_record = {
            "content_id": content_item.id,
            "like_count": content_item.like_count,
            "retweet_count": content_item.retweet_count,
            "reply_count": content_item.reply_count,
            "quote_count": content_item.quote_count,
            "total_engagement": content_item.total_engagement,
            "recorded_at": datetime.utcnow()
        }
        
        await self.engagement_history_repo.create(engagement_record)
```

### 2. Engagement Analytics

**Analytics Pattern**:
```python
class EngagementAnalytics:
    async def analyze_content_performance(self, content_id: str) -> Dict[str, Any]:
        """Analyze engagement performance for a content item."""
        content_item = await self.content_repo.get(content_id)
        engagement_history = await self.engagement_history_repo.get_by_content_id(content_id)
        
        if not engagement_history:
            return {"status": "no_data", "message": "No engagement history available"}
        
        # Calculate engagement trends
        trends = self.calculate_engagement_trends(engagement_history)
        
        # Compare with similar content
        similar_content = await self.find_similar_content(content_item)
        performance_comparison = self.compare_performance(content_item, similar_content)
        
        # Generate insights
        insights = self.generate_engagement_insights(content_item, trends, performance_comparison)
        
        return {
            "content_id": content_id,
            "current_metrics": {
                "likes": content_item.like_count,
                "retweets": content_item.retweet_count,
                "replies": content_item.reply_count,
                "quotes": content_item.quote_count,
                "total": content_item.total_engagement
            },
            "trends": trends,
            "performance_comparison": performance_comparison,
            "insights": insights,
            "analyzed_at": datetime.utcnow().isoformat()
        }
    
    def calculate_engagement_trends(self, history: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Calculate engagement trends from history data."""
        if len(history) < 2:
            return {"status": "insufficient_data"}
        
        # Sort by timestamp
        sorted_history = sorted(history, key=lambda x: x["recorded_at"])
        
        # Calculate growth rates
        latest = sorted_history[-1]
        previous = sorted_history[-2]
        
        like_growth = self.calculate_growth_rate(previous["like_count"], latest["like_count"])
        retweet_growth = self.calculate_growth_rate(previous["retweet_count"], latest["retweet_count"])
        reply_growth = self.calculate_growth_rate(previous["reply_count"], latest["reply_count"])
        
        return {
            "like_growth_rate": like_growth,
            "retweet_growth_rate": retweet_growth,
            "reply_growth_rate": reply_growth,
            "trend_direction": self.determine_trend_direction([like_growth, retweet_growth, reply_growth]),
            "data_points": len(history)
        }
```

## Database Schema Patterns

### 1. Twitter/X-Specific Fields

**Content Item Schema**:
```sql
-- Twitter/X-specific fields in content_items table
ALTER TABLE content_items ADD COLUMN tweet_id VARCHAR(50) UNIQUE;
ALTER TABLE content_items ADD COLUMN author_username VARCHAR(100);
ALTER TABLE content_items ADD COLUMN author_id VARCHAR(50);
ALTER TABLE content_items ADD COLUMN tweet_url TEXT;

-- Thread information
ALTER TABLE content_items ADD COLUMN thread_id VARCHAR(50);
ALTER TABLE content_items ADD COLUMN is_thread_root BOOLEAN DEFAULT FALSE;
ALTER TABLE content_items ADD COLUMN position_in_thread INTEGER;
ALTER TABLE content_items ADD COLUMN thread_length INTEGER;

-- Engagement metrics
ALTER TABLE content_items ADD COLUMN like_count INTEGER DEFAULT 0;
ALTER TABLE content_items ADD COLUMN retweet_count INTEGER DEFAULT 0;
ALTER TABLE content_items ADD COLUMN reply_count INTEGER DEFAULT 0;
ALTER TABLE content_items ADD COLUMN quote_count INTEGER DEFAULT 0;
ALTER TABLE content_items ADD COLUMN total_engagement INTEGER GENERATED ALWAYS AS (
    COALESCE(like_count, 0) + COALESCE(retweet_count, 0) + 
    COALESCE(reply_count, 0) + COALESCE(quote_count, 0)
) STORED;

-- Sub-phase processing states
ALTER TABLE content_items ADD COLUMN bookmark_cached BOOLEAN DEFAULT FALSE;
ALTER TABLE content_items ADD COLUMN media_analyzed BOOLEAN DEFAULT FALSE;
ALTER TABLE content_items ADD COLUMN content_understood BOOLEAN DEFAULT FALSE;
ALTER TABLE content_items ADD COLUMN categorized BOOLEAN DEFAULT FALSE;

-- Media and AI analysis
ALTER TABLE content_items ADD COLUMN media_content JSONB;
ALTER TABLE content_items ADD COLUMN media_analysis_results JSONB;
ALTER TABLE content_items ADD COLUMN collective_understanding JSONB;
ALTER TABLE content_items ADD COLUMN has_media_analysis BOOLEAN DEFAULT FALSE;
ALTER TABLE content_items ADD COLUMN has_collective_understanding BOOLEAN DEFAULT FALSE;

-- Timestamps
ALTER TABLE content_items ADD COLUMN original_tweet_created_at TIMESTAMP WITH TIME ZONE;

-- Indexes for performance
CREATE INDEX idx_content_items_tweet_id ON content_items(tweet_id);
CREATE INDEX idx_content_items_author_username ON content_items(author_username);
CREATE INDEX idx_content_items_thread_id ON content_items(thread_id);
CREATE INDEX idx_content_items_processing_states ON content_items(bookmark_cached, media_analyzed, content_understood, categorized);
CREATE INDEX idx_content_items_engagement ON content_items(total_engagement DESC);
```

### 2. Repository Patterns

**Twitter/X-Specific Repository Methods**:
```python
class TwitterContentRepository(ContentRepository):
    async def get_by_tweet_id(self, db: AsyncSession, tweet_id: str) -> Optional[ContentItem]:
        """Get content item by Twitter/X tweet ID."""
        result = await db.execute(
            select(ContentItem).where(ContentItem.tweet_id == tweet_id)
        )
        return result.scalar_one_or_none()
    
    async def get_thread_tweets(self, db: AsyncSession, thread_id: str) -> List[ContentItem]:
        """Get all tweets in a specific thread, ordered by position."""
        result = await db.execute(
            select(ContentItem)
            .where(ContentItem.thread_id == thread_id)
            .order_by(ContentItem.position_in_thread.asc().nullslast())
        )
        return result.scalars().all()
    
    async def get_items_needing_media_analysis(self, db: AsyncSession) -> List[ContentItem]:
        """Get content items that need media analysis."""
        result = await db.execute(
            select(ContentItem)
            .where(
                and_(
                    ContentItem.bookmark_cached == True,
                    ContentItem.media_analyzed == False,
                    ContentItem.media_content.isnot(None)
                )
            )
            .order_by(ContentItem.created_at.asc())
        )
        return result.scalars().all()
    
    async def get_high_engagement_content(self, db: AsyncSession, min_engagement: int = 100) -> List[ContentItem]:
        """Get content with high engagement metrics."""
        result = await db.execute(
            select(ContentItem)
            .where(ContentItem.total_engagement >= min_engagement)
            .order_by(ContentItem.total_engagement.desc())
        )
        return result.scalars().all()
```

This Twitter/X integration architecture provides comprehensive support for processing Twitter/X bookmarks with proper thread detection, media analysis, engagement tracking, and database optimization.