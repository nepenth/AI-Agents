#!/usr/bin/env python3
"""
Script to manually mark tweets for reprocessing through the full pipeline

This script allows you to:
1. Select specific tweets by ID or get the first N tweets
2. Reset their processing flags to trigger full reprocessing
3. Optionally reset specific phases (cache, media, categories, kb_item)
4. Provide detailed logging of what was reset

Usage:
    python scripts/mark_tweets_for_reprocessing.py --first 10
    python scripts/mark_tweets_for_reprocessing.py --tweet-ids 1878324550418714836,1867620426492653977
    python scripts/mark_tweets_for_reprocessing.py --first 5 --phases cache,media,categories,kb_item
    python scripts/mark_tweets_for_reprocessing.py --all-incomplete
"""

import sys
import argparse
from pathlib import Path
from typing import List, Optional
from datetime import datetime

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from knowledge_base_agent.models import UnifiedTweet, db
from knowledge_base_agent.config import Config
from knowledge_base_agent.web import create_app

class TweetReprocessingManager:
    def __init__(self):
        self.reset_stats = {
            'tweets_processed': 0,
            'flags_reset': 0,
            'phases_reset': {
                'cache_complete': 0,
                'media_processed': 0,
                'categories_processed': 0,
                'kb_item_created': 0,
                'processing_complete': 0
            }
        }

    def mark_tweets_for_reprocessing(self, tweet_ids: List[str], phases: List[str] = None, reason: str = "Manual reprocessing"):
        """
        Mark specific tweets for reprocessing by resetting their phase flags.
        
        Args:
            tweet_ids: List of tweet IDs to mark for reprocessing
            phases: List of phases to reset ('cache', 'media', 'categories', 'kb_item', 'all')
            reason: Reason for reprocessing (for logging)
        """
        if not phases:
            phases = ['kb_item', 'categories']  # Default to resetting KB and category phases
        
        # Map phase names to database fields
        phase_flags = {
            'cache': 'cache_complete',
            'media': 'media_processed',
            'categories': 'categories_processed',
            'kb_item': 'kb_item_created',
            'processing': 'processing_complete'
        }
        
        print(f"🔄 Marking {len(tweet_ids)} tweets for reprocessing...")
        print(f"📋 Reason: {reason}")
        print(f"🎯 Phases to reset: {', '.join(phases)}")
        print("-" * 50)
        
        for tweet_id in tweet_ids:
            try:
                tweet = db.session.query(UnifiedTweet).filter_by(tweet_id=tweet_id).first()
                
                if not tweet:
                    print(f"❌ Tweet {tweet_id} not found in database")
                    continue
                
                print(f"\n🔍 Processing tweet {tweet_id}:")
                print(f"   Current title: {tweet.kb_display_title or 'None'}")
                print(f"   Current category: {tweet.main_category} > {tweet.sub_category}")
                
                # Show current status
                current_status = {
                    'cache_complete': tweet.cache_complete,
                    'media_processed': tweet.media_processed,
                    'categories_processed': tweet.categories_processed,
                    'kb_item_created': tweet.kb_item_created,
                    'processing_complete': tweet.processing_complete
                }
                print(f"   Current flags: {current_status}")
                
                # Reset specified phases
                reset_flags = []
                for phase in phases:
                    if phase == 'all':
                        # Reset all phases
                        for flag_name in phase_flags.values():
                            if getattr(tweet, flag_name):
                                setattr(tweet, flag_name, False)
                                reset_flags.append(flag_name)
                                self.reset_stats['phases_reset'][flag_name] += 1
                    elif phase in phase_flags:
                        flag_name = phase_flags[phase]
                        if getattr(tweet, flag_name):
                            setattr(tweet, flag_name, False)
                            reset_flags.append(flag_name)
                            self.reset_stats['phases_reset'][flag_name] += 1
                
                # Always reset processing_complete if any phase is reset
                if reset_flags and tweet.processing_complete:
                    tweet.processing_complete = False
                    if 'processing_complete' not in reset_flags:
                        reset_flags.append('processing_complete')
                        self.reset_stats['phases_reset']['processing_complete'] += 1
                
                # Clear any error flags to allow reprocessing
                if hasattr(tweet, 'kbitem_error') and tweet.kbitem_error:
                    tweet.kbitem_error = None
                    reset_flags.append('kbitem_error_cleared')
                
                if hasattr(tweet, 'llm_error') and tweet.llm_error:
                    tweet.llm_error = None
                    reset_flags.append('llm_error_cleared')
                
                # Reset retry counters
                if hasattr(tweet, 'recategorization_attempts'):
                    tweet.recategorization_attempts = 0
                
                # Update timestamps
                tweet.updated_at = datetime.utcnow()
                
                if reset_flags:
                    print(f"   ✅ Reset flags: {', '.join(reset_flags)}")
                    self.reset_stats['tweets_processed'] += 1
                    self.reset_stats['flags_reset'] += len(reset_flags)
                else:
                    print(f"   ℹ️  No flags needed resetting")
                
            except Exception as e:
                print(f"❌ Error processing tweet {tweet_id}: {str(e)}")
        
        # Commit all changes
        try:
            db.session.commit()
            print(f"\n✅ Successfully committed changes to database")
        except Exception as e:
            db.session.rollback()
            print(f"\n❌ Error committing changes: {str(e)}")
            return False
        
        return True

    def get_first_n_tweets(self, n: int, filter_incomplete: bool = False) -> List[str]:
        """Get the first N tweets from the database"""
        query = db.session.query(UnifiedTweet)
        
        if filter_incomplete:
            # Only get tweets that have some processing done but aren't complete
            query = query.filter(
                UnifiedTweet.cache_complete == True,
                UnifiedTweet.processing_complete == False
            )
        
        tweets = query.order_by(UnifiedTweet.id.asc()).limit(n).all()
        return [tweet.tweet_id for tweet in tweets]

    def get_incomplete_tweets(self) -> List[str]:
        """Get all tweets that have incomplete processing"""
        tweets = db.session.query(UnifiedTweet).filter(
            UnifiedTweet.cache_complete == True,
            UnifiedTweet.processing_complete == False
        ).all()
        return [tweet.tweet_id for tweet in tweets]

    def print_summary(self):
        """Print summary of reprocessing actions"""
        print("\n" + "=" * 60)
        print("📊 REPROCESSING SUMMARY")
        print("=" * 60)
        
        print(f"📈 Tweets processed: {self.reset_stats['tweets_processed']}")
        print(f"🔧 Total flags reset: {self.reset_stats['flags_reset']}")
        
        print(f"\n🎯 Phases reset breakdown:")
        for phase, count in self.reset_stats['phases_reset'].items():
            if count > 0:
                print(f"   {phase}: {count} tweets")
        
        print(f"\n💡 Next steps:")
        print(f"   1. Run the agent to reprocess these tweets")
        print(f"   2. Monitor logs for processing progress")
        print(f"   3. Check Knowledge Base page for updated content")

def main():
    parser = argparse.ArgumentParser(description='Mark tweets for reprocessing through the full pipeline')
    
    # Tweet selection options
    tweet_group = parser.add_mutually_exclusive_group(required=True)
    tweet_group.add_argument('--first', type=int, metavar='N',
                           help='Mark the first N tweets for reprocessing')
    tweet_group.add_argument('--tweet-ids', type=str, metavar='IDS',
                           help='Comma-separated list of tweet IDs to mark for reprocessing')
    tweet_group.add_argument('--all-incomplete', action='store_true',
                           help='Mark all tweets with incomplete processing')
    
    # Phase selection options
    parser.add_argument('--phases', type=str, default='kb_item,categories',
                       help='Comma-separated list of phases to reset (cache,media,categories,kb_item,all)')
    parser.add_argument('--reason', type=str, default='Manual reprocessing for testing',
                       help='Reason for reprocessing (for logging)')
    
    # Dry run option
    parser.add_argument('--dry-run', action='store_true',
                       help='Show what would be reset without making changes')
    
    args = parser.parse_args()
    
    # Create Flask app context
    app, socketio, migrate, realtime_manager = create_app()
    
    with app.app_context():
        manager = TweetReprocessingManager()
        
        # Get tweet IDs to process
        if args.first:
            tweet_ids = manager.get_first_n_tweets(args.first)
            print(f"🎯 Selected first {len(tweet_ids)} tweets from database")
        elif args.tweet_ids:
            tweet_ids = [tid.strip() for tid in args.tweet_ids.split(',')]
            print(f"🎯 Selected {len(tweet_ids)} specific tweets")
        elif args.all_incomplete:
            tweet_ids = manager.get_incomplete_tweets()
            print(f"🎯 Selected {len(tweet_ids)} tweets with incomplete processing")
        
        if not tweet_ids:
            print("❌ No tweets found matching the criteria")
            sys.exit(1)
        
        # Parse phases
        phases = [phase.strip() for phase in args.phases.split(',')]
        
        if args.dry_run:
            print(f"\n🔍 DRY RUN - Would mark {len(tweet_ids)} tweets for reprocessing")
            print(f"📋 Phases to reset: {', '.join(phases)}")
            print(f"📝 Reason: {args.reason}")
            
            # Show first few tweet IDs
            print(f"\n📋 Tweet IDs to process:")
            for i, tweet_id in enumerate(tweet_ids[:10]):
                print(f"   {i+1}. {tweet_id}")
            if len(tweet_ids) > 10:
                print(f"   ... and {len(tweet_ids) - 10} more")
            
            print(f"\n💡 Run without --dry-run to apply changes")
            sys.exit(0)
        
        # Mark tweets for reprocessing
        success = manager.mark_tweets_for_reprocessing(tweet_ids, phases, args.reason)
        
        if success:
            manager.print_summary()
            print(f"\n✅ Successfully marked tweets for reprocessing")
            sys.exit(0)
        else:
            print(f"\n❌ Failed to mark tweets for reprocessing")
            sys.exit(1)

if __name__ == "__main__":
    main()