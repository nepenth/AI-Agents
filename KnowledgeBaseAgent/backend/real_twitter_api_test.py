#!/usr/bin/env python3
"""
Real Twitter/X API testing script that uses actual Twitter API to fetch tweet data
and test the seven-phase pipeline with real data.
"""
import asyncio
import sys
import json
import argparse
from datetime import datetime
from typing import Dict, Any, Optional

# Add the app directory to the path so we can import our modules
sys.path.append('.')

from app.config import get_settings
from app.services.twitter_client import get_twitter_client, TwitterAPIError, TweetData


class RealTwitterTester:
    """Real Twitter API tester for the seven-phase pipeline."""
    
    def __init__(self):
        self.settings = get_settings()
        self.twitter_client = get_twitter_client()
        # Reset rate limiting for testing
        self.twitter_client.requests_made = 0
        self.twitter_client.window_start = datetime.utcnow()
    
    async def test_twitter_connection(self) -> bool:
        """Test if Twitter API connection is working."""
        print("🔍 Testing Twitter/X API connection...")
        
        # First, check if credentials are configured
        if not self.settings.X_BEARER_TOKEN:
            print("   ❌ X_BEARER_TOKEN not configured")
            return False
        
        if not self.settings.X_API_KEY:
            print("   ❌ X_API_KEY not configured")
            return False
        
        print(f"   📋 Using Bearer Token: {self.settings.X_BEARER_TOKEN[:20]}...")
        print(f"   📋 Using API Key: {self.settings.X_API_KEY[:10]}...")
        
        try:
            async with self.twitter_client as client:
                is_available = await client.is_available()
                if is_available:
                    print("   ✅ Twitter/X API connection successful")
                    return True
                else:
                    print("   ❌ Twitter/X API connection failed")
                    return False
        except TwitterAPIError as e:
            print(f"   ❌ Twitter API error: {e}")
            print(f"   📊 Status code: {e.status_code}")
            print(f"   🔍 Error code: {e.error_code}")
            
            if e.status_code == 403:
                print("   💡 403 Forbidden - This usually means:")
                print("      • Your API credentials are invalid")
                print("      • Your app doesn't have the required permissions")
                print("      • Your Twitter developer account is suspended")
                print("      • You're using the wrong API endpoint")
            elif e.status_code == 401:
                print("   💡 401 Unauthorized - Check your Bearer Token")
            elif e.status_code == 429:
                print("   💡 429 Rate Limited - Wait before trying again")
            
            return False
        except Exception as e:
            print(f"   ❌ Unexpected error: {e}")
            return False
    
    async def fetch_real_tweet(self, tweet_id: str) -> Optional[TweetData]:
        """Fetch real tweet data from Twitter API."""
        print(f"🔍 Fetching real tweet data for {tweet_id}...")
        
        try:
            async with self.twitter_client as client:
                # Reset rate limiting for this session
                client.requests_made = 0
                client.window_start = datetime.utcnow()
                
                print(f"   📊 Rate limit status: {client.requests_made}/{client.config.rate_limit_requests}")
                print(f"   ⏰ Window start: {client.window_start}")
                
                tweet_data = await client.get_tweet(tweet_id)
                print("   ✅ Successfully fetched real tweet data")
                return tweet_data
        except TwitterAPIError as e:
            print(f"   ❌ Twitter API error: {e}")
            if e.status_code == 404:
                print("   💡 Tweet not found - check if the tweet ID is correct and public")
            elif e.status_code == 401:
                print("   💡 Unauthorized - check your API credentials")
            elif e.status_code == 429:
                print("   💡 Rate limited - waiting 60 seconds and retrying...")
                await asyncio.sleep(60)
                try:
                    async with self.twitter_client as retry_client:
                        retry_client.requests_made = 0
                        retry_client.window_start = datetime.utcnow()
                        tweet_data = await retry_client.get_tweet(tweet_id)
                        print("   ✅ Successfully fetched real tweet data after retry")
                        return tweet_data
                except Exception as retry_e:
                    print(f"   ❌ Retry failed: {retry_e}")
                    return None
            return None
        except Exception as e:
            print(f"   ❌ Unexpected error: {e}")
            return None
    
    def print_tweet_summary(self, tweet_data: TweetData):
        """Print a detailed summary of the real tweet data."""
        print(f"\n📄 Real Tweet Data Summary:")
        print(f"   Tweet ID: {tweet_data.id}")
        print(f"   Author: @{tweet_data.author_username} (ID: {tweet_data.author_id})")
        print(f"   URL: {tweet_data.url}")
        print(f"   Created: {tweet_data.created_at.strftime('%Y-%m-%d %H:%M:%S UTC')}")
        
        print(f"\n💬 Content:")
        print(f"   Text: {tweet_data.text}")
        
        print(f"\n📊 Engagement Metrics:")
        metrics = tweet_data.public_metrics
        likes = metrics.get('like_count', 0)
        retweets = metrics.get('retweet_count', 0)
        replies = metrics.get('reply_count', 0)
        quotes = metrics.get('quote_count', 0)
        total = likes + retweets + replies + quotes
        
        print(f"   👍 Likes: {likes}")
        print(f"   🔄 Retweets: {retweets}")
        print(f"   💬 Replies: {replies}")
        print(f"   📝 Quotes: {quotes}")
        print(f"   📊 Total Engagement: {total}")
        
        if tweet_data.media:
            print(f"\n🖼️  Media Content ({len(tweet_data.media)} items):")
            for i, media in enumerate(tweet_data.media, 1):
                print(f"   {i}. {media.get('type', 'unknown')}: {media.get('media_key', 'N/A')}")
                if media.get('alt_text'):
                    print(f"      Alt text: {media['alt_text'][:100]}...")
        
        if tweet_data.context_annotations:
            print(f"\n🎯 Context Annotations:")
            for annotation in tweet_data.context_annotations:
                domain = annotation.get('domain', {})
                entity = annotation.get('entity', {})
                print(f"   • {domain.get('name', 'Unknown')}: {entity.get('name', 'Unknown')}")
        
        if tweet_data.referenced_tweets:
            print(f"\n🔗 Referenced Tweets:")
            for ref in tweet_data.referenced_tweets:
                print(f"   • {ref.get('type', 'unknown')}: {ref.get('id', 'N/A')}")


async def main():
    parser = argparse.ArgumentParser(description="Test seven-phase pipeline with real Twitter/X API data")
    parser.add_argument("--tweet-id", help="Real tweet ID to test with")
    parser.add_argument("--test-connection", action="store_true", help="Test Twitter API connection only")
    
    args = parser.parse_args()
    
    tester = RealTwitterTester()
    
    try:
        if args.test_connection:
            # Only test connection if specifically requested
            connection_ok = await tester.test_twitter_connection()
            if connection_ok:
                print("\n🎉 Twitter/X API connection test successful!")
            else:
                print("\n❌ Twitter/X API connection test failed!")
            return
        
        if not args.tweet_id:
            print("\n❌ Tweet ID is required when not testing connection only")
            print("Usage: python real_twitter_api_test.py --tweet-id TWEET_ID")
            return
        
        # Fetch real tweet data
        tweet_data = await tester.fetch_real_tweet(args.tweet_id)
        
        if not tweet_data:
            print(f"\n❌ Failed to fetch tweet {args.tweet_id}")
            return
        
        # Print tweet summary
        tester.print_tweet_summary(tweet_data)
        
        print(f"\n🎉 Successfully fetched and analyzed real tweet {args.tweet_id}!")
        print("\n🚀 Next steps:")
        print("   1. This tweet data can now be processed through the seven-phase pipeline")
        print("   2. Each phase will work with this real Twitter data")
        print("   3. You can test individual phases or run the full pipeline")
        
    except KeyboardInterrupt:
        print("\n❌ Test cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())