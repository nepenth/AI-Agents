#!/usr/bin/env python3
"""
Diagnose tweet content extraction issues
"""

import sys
import os
import json
from pathlib import Path

def main():
    # Load tweet cache to examine the data structure
    tweet_cache_path = Path("data/tweet_cache.json")
    
    if not tweet_cache_path.exists():
        print(f"❌ Tweet cache not found at {tweet_cache_path}")
        return
    
    print("=== DIAGNOSING TWEET CONTENT EXTRACTION ISSUES ===\n")
    
    try:
        with open(tweet_cache_path, 'r', encoding='utf-8') as f:
            tweet_cache = json.load(f)
    except Exception as e:
        print(f"❌ Error loading tweet cache: {e}")
        return
    
    print(f"📊 Total tweets in cache: {len(tweet_cache)}")
    
    # Find tweets that have the content issue
    problematic_tweets = []
    working_tweets = []
    
    for tweet_id, tweet_data in tweet_cache.items():
        # Check if this tweet has the content issue
        full_text = tweet_data.get('full_text', '')
        if full_text and 'content not available' in full_text:
            problematic_tweets.append((tweet_id, tweet_data))
        elif tweet_data.get('thread_tweets'):
            # Check if thread_tweets have content
            has_content = False
            for segment in tweet_data.get('thread_tweets', []):
                segment_text = segment.get('full_text', '') or segment.get('text_content', '')
                if segment_text and segment_text.strip() and 'content not available' not in segment_text:
                    has_content = True
                    break
            
            if has_content:
                working_tweets.append((tweet_id, tweet_data))
            else:
                problematic_tweets.append((tweet_id, tweet_data))
    
    print(f"🔍 Analysis Results:")
    print(f"  - Problematic tweets (no usable content): {len(problematic_tweets)}")
    print(f"  - Working tweets (have content): {len(working_tweets)}")
    print()
    
    # Examine a few problematic tweets in detail
    if problematic_tweets:
        print(f"🔍 DETAILED ANALYSIS OF PROBLEMATIC TWEETS:")
        print("=" * 60)
        
        for i, (tweet_id, tweet_data) in enumerate(problematic_tweets[:5]):  # Examine first 5
            print(f"\n{i+1}. Tweet ID: {tweet_id}")
            print(f"   Cache Complete: {tweet_data.get('cache_complete', False)}")
            print(f"   Is Thread: {tweet_data.get('is_thread', False)}")
            print(f"   URLs Expanded: {tweet_data.get('urls_expanded', False)}")
            print(f"   Media Processed: {tweet_data.get('media_processed', False)}")
            
            # Check top-level full_text
            full_text = tweet_data.get('full_text', '')
            print(f"   Top-level full_text: '{full_text[:100]}{'...' if len(full_text) > 100 else ''}'")
            
            # Check thread_tweets structure
            thread_tweets = tweet_data.get('thread_tweets', [])
            print(f"   Thread tweets count: {len(thread_tweets)}")
            
            for j, segment in enumerate(thread_tweets):
                segment_full_text = segment.get('full_text', '')
                segment_text_content = segment.get('text_content', '')
                print(f"     Segment {j+1}:")
                print(f"       full_text: '{segment_full_text[:100]}{'...' if len(segment_full_text) > 100 else ''}'")
                print(f"       text_content: '{segment_text_content[:100]}{'...' if len(segment_text_content) > 100 else ''}'")
                print(f"       author_handle: {segment.get('author_handle', 'N/A')}")
                print(f"       tweet_permalink: {segment.get('tweet_permalink', 'N/A')}")
                
                # Check if this segment has any other text fields
                other_text_fields = {}
                for key, value in segment.items():
                    if key not in ['full_text', 'text_content', 'author_handle', 'tweet_permalink', 'media_item_details', 'urls', 'expanded_urls', 'downloaded_media_paths_for_segment']:
                        if isinstance(value, str) and value.strip():
                            other_text_fields[key] = value[:50] + ('...' if len(value) > 50 else '')
                
                if other_text_fields:
                    print(f"       Other text fields: {other_text_fields}")
            
            print("   " + "-" * 50)
    
    # Examine a few working tweets for comparison
    if working_tweets:
        print(f"\n🔍 COMPARISON: WORKING TWEETS STRUCTURE:")
        print("=" * 60)
        
        for i, (tweet_id, tweet_data) in enumerate(working_tweets[:3]):  # Examine first 3
            print(f"\n{i+1}. Tweet ID: {tweet_id}")
            print(f"   Cache Complete: {tweet_data.get('cache_complete', False)}")
            print(f"   Is Thread: {tweet_data.get('is_thread', False)}")
            
            # Check thread_tweets structure
            thread_tweets = tweet_data.get('thread_tweets', [])
            print(f"   Thread tweets count: {len(thread_tweets)}")
            
            for j, segment in enumerate(thread_tweets[:2]):  # First 2 segments
                segment_full_text = segment.get('full_text', '')
                print(f"     Segment {j+1}:")
                print(f"       full_text: '{segment_full_text[:100]}{'...' if len(segment_full_text) > 100 else ''}'")
                print(f"       author_handle: {segment.get('author_handle', 'N/A')}")
            
            print("   " + "-" * 50)
    
    # Check if there's a pattern in the problematic tweets
    if problematic_tweets:
        print(f"\n🔍 PATTERN ANALYSIS:")
        print("=" * 60)
        
        cache_complete_count = sum(1 for _, data in problematic_tweets if data.get('cache_complete', False))
        thread_count = sum(1 for _, data in problematic_tweets if data.get('is_thread', False))
        urls_expanded_count = sum(1 for _, data in problematic_tweets if data.get('urls_expanded', False))
        media_processed_count = sum(1 for _, data in problematic_tweets if data.get('media_processed', False))
        
        print(f"  - Cache complete: {cache_complete_count}/{len(problematic_tweets)}")
        print(f"  - Are threads: {thread_count}/{len(problematic_tweets)}")
        print(f"  - URLs expanded: {urls_expanded_count}/{len(problematic_tweets)}")
        print(f"  - Media processed: {media_processed_count}/{len(problematic_tweets)}")
        
        # Check if there are any common patterns in the thread_tweets data
        empty_segments = 0
        total_segments = 0
        
        for _, tweet_data in problematic_tweets:
            for segment in tweet_data.get('thread_tweets', []):
                total_segments += 1
                segment_text = segment.get('full_text', '') or segment.get('text_content', '')
                if not segment_text or not segment_text.strip():
                    empty_segments += 1
        
        print(f"  - Empty segments: {empty_segments}/{total_segments}")
        
        if empty_segments > 0:
            print(f"\n⚠️  ISSUE IDENTIFIED: {empty_segments} out of {total_segments} thread segments have no text content!")
            print(f"   This suggests the playwright fetcher is not extracting tweet text properly.")
    
    # Recommendations
    print(f"\n💡 RECOMMENDATIONS:")
    print("=" * 60)
    
    if problematic_tweets:
        print(f"1. The issue appears to be in the playwright fetcher's text extraction")
        print(f"2. Check the CSS selectors used to extract tweet text")
        print(f"3. Twitter may have changed their HTML structure")
        print(f"4. Consider updating the text extraction logic in playwright_fetcher.py")
        
        if empty_segments > total_segments * 0.5:
            print(f"5. CRITICAL: Over 50% of segments have no text - this is a systematic issue")
    else:
        print(f"1. No problematic tweets found - the issue may be intermittent")
        print(f"2. Check if the issue occurs during processing rather than caching")
    
    print(f"\n✅ Diagnosis complete!")

if __name__ == "__main__":
    main()