#!/usr/bin/env python3
"""
Simple Twitter API test that bypasses rate limiting for testing.
"""
import asyncio
import sys
import aiohttp
from datetime import datetime

# Add the app directory to the path
sys.path.append('.')

from app.config import get_settings


async def simple_twitter_test(tweet_id: str):
    """Simple Twitter API test without rate limiting."""
    settings = get_settings()
    
    print(f"🔍 Testing Twitter API with tweet {tweet_id}...")
    print(f"   📋 Bearer Token: {settings.X_BEARER_TOKEN[:20]}...")
    
    url = f"https://api.twitter.com/2/tweets/{tweet_id}"
    headers = {
        'Authorization': f'Bearer {settings.X_BEARER_TOKEN}',
        'Content-Type': 'application/json'
    }
    params = {
        'expansions': 'author_id,attachments.media_keys',
        'tweet.fields': 'created_at,public_metrics,context_annotations',
        'user.fields': 'username,name,verified',
        'media.fields': 'type,url,alt_text'
    }
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers, params=params) as response:
                print(f"   📊 Response status: {response.status}")
                
                if response.status == 200:
                    data = await response.json()
                    print("   ✅ Successfully fetched tweet data!")
                    
                    tweet_data = data.get('data', {})
                    includes = data.get('includes', {})
                    
                    print(f"\n📄 Tweet Data:")
                    print(f"   ID: {tweet_data.get('id')}")
                    print(f"   Text: {tweet_data.get('text', '')[:100]}...")
                    print(f"   Created: {tweet_data.get('created_at')}")
                    
                    # Author info
                    users = {user['id']: user for user in includes.get('users', [])}
                    author = users.get(tweet_data.get('author_id', ''), {})
                    if author:
                        print(f"   Author: @{author.get('username')} ({author.get('name')})")
                    
                    # Metrics
                    metrics = tweet_data.get('public_metrics', {})
                    if metrics:
                        print(f"   Engagement: {metrics.get('like_count', 0)} likes, {metrics.get('retweet_count', 0)} retweets")
                    
                    # Media
                    media_list = includes.get('media', [])
                    if media_list:
                        print(f"   Media: {len(media_list)} items")
                        for media in media_list:
                            print(f"      - {media.get('type')}: {media.get('media_key')}")
                    
                    return True
                    
                else:
                    error_text = await response.text()
                    print(f"   ❌ Error {response.status}: {error_text}")
                    return False
                    
    except Exception as e:
        print(f"   ❌ Exception: {e}")
        return False


async def main():
    if len(sys.argv) != 2:
        print("Usage: python simple_twitter_test.py <tweet_id>")
        sys.exit(1)
    
    tweet_id = sys.argv[1]
    success = await simple_twitter_test(tweet_id)
    
    if success:
        print("\n🎉 Twitter API test successful!")
    else:
        print("\n❌ Twitter API test failed!")


if __name__ == "__main__":
    asyncio.run(main())