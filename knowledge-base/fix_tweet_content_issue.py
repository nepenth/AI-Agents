#!/usr/bin/env python3
"""
Fix tweet content extraction issues by populating top-level full_text from thread segments
"""

import sys
import os
import json
from pathlib import Path

def main():
    # Load tweet cache to fix the data structure
    tweet_cache_path = Path("data/tweet_cache.json")
    
    if not tweet_cache_path.exists():
        print(f"❌ Tweet cache not found at {tweet_cache_path}")
        return
    
    print("=== FIXING TWEET CONTENT EXTRACTION ISSUES ===\n")
    
    try:
        with open(tweet_cache_path, 'r', encoding='utf-8') as f:
            tweet_cache = json.load(f)
    except Exception as e:
        print(f"❌ Error loading tweet cache: {e}")
        return
    
    print(f"📊 Total tweets in cache: {len(tweet_cache)}")
    
    # Find tweets that need fixing
    tweets_to_fix = []
    already_fixed = []
    
    for tweet_id, tweet_data in tweet_cache.items():
        # Check if this tweet has the content issue
        full_text = tweet_data.get('full_text', '')
        
        if full_text and 'content not available' in full_text:
            # Check if we can fix it from thread_tweets
            thread_tweets = tweet_data.get('thread_tweets', [])
            if thread_tweets:
                # Check if thread segments have content
                has_content = False
                for segment in thread_tweets:
                    segment_text = segment.get('full_text', '') or segment.get('text_content', '')
                    if segment_text and segment_text.strip() and 'content not available' not in segment_text:
                        has_content = True
                        break
                
                if has_content:
                    tweets_to_fix.append((tweet_id, tweet_data))
        elif full_text and full_text.strip() and 'content not available' not in full_text:
            already_fixed.append(tweet_id)
    
    print(f"🔍 Analysis Results:")
    print(f"  - Tweets needing fix: {len(tweets_to_fix)}")
    print(f"  - Tweets already working: {len(already_fixed)}")
    print()
    
    if not tweets_to_fix:
        print("✅ No tweets need fixing!")
        return
    
    # Fix the tweets
    print(f"🔧 FIXING {len(tweets_to_fix)} TWEETS:")
    print("=" * 60)
    
    fixed_count = 0
    
    for i, (tweet_id, tweet_data) in enumerate(tweets_to_fix, 1):
        print(f"\n{i}. Fixing Tweet ID: {tweet_id}")
        
        # Extract content from thread segments
        thread_segments = tweet_data.get('thread_tweets', [])
        all_texts = []
        
        for j, segment in enumerate(thread_segments):
            segment_text = segment.get("full_text", "") or segment.get("text_content", "")
            if segment_text and segment_text.strip():
                if len(thread_segments) > 1:
                    all_texts.append(f"Segment {j+1}: {segment_text}")
                else:
                    all_texts.append(segment_text)
        
        combined_text = "\n\n".join(all_texts)
        
        if combined_text.strip():
            # Update the full_text field
            old_text = tweet_data.get('full_text', '')
            tweet_data['full_text'] = combined_text
            
            print(f"   ✅ Fixed! Length: {len(combined_text)} characters")
            print(f"   Old: '{old_text[:50]}{'...' if len(old_text) > 50 else ''}'")
            print(f"   New: '{combined_text[:50]}{'...' if len(combined_text) > 50 else ''}'")
            
            fixed_count += 1
        else:
            print(f"   ⚠️  No usable content found in thread segments")
    
    if fixed_count > 0:
        # Save the updated cache
        print(f"\n💾 Saving updated tweet cache...")
        
        # Create backup first
        backup_path = tweet_cache_path.with_suffix('.json.backup')
        with open(backup_path, 'w', encoding='utf-8') as f:
            json.dump(tweet_cache, f, indent=2)
        print(f"   📋 Backup created: {backup_path}")
        
        # Save the fixed cache
        with open(tweet_cache_path, 'w', encoding='utf-8') as f:
            json.dump(tweet_cache, f, indent=2)
        
        print(f"   ✅ Updated tweet cache saved")
        
        print(f"\n📊 SUMMARY:")
        print(f"  - Tweets fixed: {fixed_count}")
        print(f"  - Total tweets: {len(tweet_cache)}")
        print(f"  - Success rate: {(fixed_count / len(tweets_to_fix)) * 100:.1f}%")
        
        print(f"\n💡 NEXT STEPS:")
        print(f"  1. The tweet cache has been updated with proper full_text content")
        print(f"  2. Future tweet caching will automatically populate full_text correctly")
        print(f"  3. Run the agent again to process the fixed tweets through the pipeline")
        print(f"  4. The database sync errors should be resolved")
    else:
        print(f"\n⚠️  No tweets were successfully fixed")
    
    print(f"\n✅ Fix process complete!")

if __name__ == "__main__":
    main()