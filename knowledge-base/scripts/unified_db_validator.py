#!/usr/bin/env python3
"""
Unified Database Validation and Cleanup Script

Validates and fixes data integrity issues in the unified database:
- Parses JSON strings in kb_media_paths and converts to proper arrays
- Validates media file existence against actual filesystem
- Fixes null display_titles using intelligent content extraction
- Ensures all required fields are populated for completed phases
- Flags tweets for reprocessing if data is incomplete or invalid
- Provides comprehensive reporting of all fixes applied

Usage:
    python scripts/unified_db_validator.py --dry-run  # Preview changes
    python scripts/unified_db_validator.py --fix      # Apply fixes
"""

import json
import os
import sys
import argparse
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from knowledge_base_agent.models import UnifiedTweet, db
from knowledge_base_agent.config import Config
from knowledge_base_agent.web import create_app

class UnifiedDBValidator:
    def __init__(self, config: Config, dry_run: bool = True):
        self.config = config
        self.dry_run = dry_run
        self.media_cache_dir = Path("data/media_cache")
        
        # Validation statistics
        self.stats = {
            'total_tweets': 0,
            'fixed_kb_media_paths': 0,
            'fixed_display_titles': 0,
            'removed_invalid_media': 0,
            'flagged_for_reprocessing': 0,
            'fixed_json_parsing': 0,
            'validated_media_files': 0,
            'errors_found': 0
        }
        
        # Detailed logs for reporting
        self.detailed_logs = []

    def validate_and_fix_all(self):
        """Main validation and cleanup method"""
        print(f"🔍 Starting unified database validation {'(DRY RUN)' if self.dry_run else '(APPLYING FIXES)'}")
        print(f"📊 Media cache directory: {self.media_cache_dir.absolute()}")
        
        tweets = UnifiedTweet.query.all()
        self.stats['total_tweets'] = len(tweets)
        
        print(f"📈 Found {len(tweets)} tweets to validate")
        
        for i, tweet in enumerate(tweets, 1):
            if i % 50 == 0:
                print(f"⏳ Processing tweet {i}/{len(tweets)}")
            
            self._validate_and_fix_tweet(tweet)
        
        if not self.dry_run:
            try:
                db.session.commit()
                print("✅ All changes committed to database")
            except Exception as e:
                db.session.rollback()
                print(f"❌ Error committing changes: {e}")
                return False
        
        self._print_summary()
        return True

    def _validate_and_fix_tweet(self, tweet: UnifiedTweet):
        """Validate and fix a single tweet's data"""
        tweet_issues = []
        
        # Fix 1: Parse kb_media_paths JSON strings
        if self._fix_kb_media_paths_json(tweet):
            self.stats['fixed_kb_media_paths'] += 1
            tweet_issues.append("Fixed kb_media_paths JSON parsing")
        
        # Fix 2: Validate and clean media file references
        media_issues = self._validate_and_fix_media_files(tweet)
        if media_issues:
            tweet_issues.extend(media_issues)
        
        # Fix 3: Generate display_title from content if null/empty
        if self._fix_display_title(tweet):
            self.stats['fixed_display_titles'] += 1
            tweet_issues.append("Generated display title from content")
        
        # Fix 4: Validate required fields for completed phases
        reprocessing_issues = self._validate_phase_completion(tweet)
        if reprocessing_issues:
            tweet_issues.extend(reprocessing_issues)
            self.stats['flagged_for_reprocessing'] += 1
        
        # Fix 5: Parse other JSON string fields
        json_fixes = self._fix_json_string_fields(tweet)
        if json_fixes:
            tweet_issues.extend(json_fixes)
            self.stats['fixed_json_parsing'] += len(json_fixes)
        
        # Log issues found for this tweet
        if tweet_issues:
            self.detailed_logs.append({
                'tweet_id': tweet.tweet_id,
                'issues': tweet_issues
            })

    def _fix_kb_media_paths_json(self, tweet: UnifiedTweet) -> bool:
        """Fix kb_media_paths if it's stored as JSON string"""
        if not tweet.kb_media_paths:
            return False
            
        if isinstance(tweet.kb_media_paths, str):
            try:
                # Try to parse as JSON
                parsed = json.loads(tweet.kb_media_paths)
                if isinstance(parsed, list):
                    tweet.kb_media_paths = parsed
                    return True
                else:
                    # Not a list, convert to empty list
                    tweet.kb_media_paths = []
                    return True
            except (json.JSONDecodeError, TypeError):
                # Invalid JSON, convert to empty list
                tweet.kb_media_paths = []
                return True
        
        return False

    def _validate_and_fix_media_files(self, tweet: UnifiedTweet) -> List[str]:
        """Validate media files exist and clean invalid references"""
        issues = []
        
        # Check media_files array
        if tweet.media_files:
            original_count = len(tweet.media_files)
            valid_media = []
            
            for media_path in tweet.media_files:
                if self._media_file_exists(tweet.tweet_id, media_path):
                    valid_media.append(media_path)
                else:
                    issues.append(f"Removed invalid media reference: {media_path}")
                    self.stats['removed_invalid_media'] += 1
            
            tweet.media_files = valid_media
            self.stats['validated_media_files'] += 1
            
            if len(valid_media) != original_count:
                issues.append(f"Cleaned media_files: {original_count} → {len(valid_media)}")
        
        # Check kb_media_paths array
        if tweet.kb_media_paths:
            original_count = len(tweet.kb_media_paths)
            valid_kb_media = []
            
            for media_path in tweet.kb_media_paths:
                if self._media_file_exists(tweet.tweet_id, media_path):
                    valid_kb_media.append(media_path)
                else:
                    issues.append(f"Removed invalid KB media reference: {media_path}")
                    self.stats['removed_invalid_media'] += 1
            
            tweet.kb_media_paths = valid_kb_media
            
            if len(valid_kb_media) != original_count:
                issues.append(f"Cleaned kb_media_paths: {original_count} → {len(valid_kb_media)}")
        
        return issues

    def _media_file_exists(self, tweet_id: str, media_path: str) -> bool:
        """Check if media file actually exists on filesystem"""
        # Try multiple possible paths
        possible_paths = [
            Path(media_path),  # Absolute or relative path as-is
            self.media_cache_dir / media_path,  # Relative to media cache
            self.media_cache_dir / tweet_id / Path(media_path).name,  # In tweet folder
            Path("data") / "media_cache" / tweet_id / Path(media_path).name,  # Full relative path
        ]
        
        for path in possible_paths:
            if path.exists() and path.is_file():
                return True
        
        return False

    def _fix_display_title(self, tweet: UnifiedTweet) -> bool:
        """Generate display_title from content if null or empty"""
        if tweet.kb_display_title and tweet.kb_display_title.strip():
            return False  # Already has a title
        
        # Try to generate from kb_content first
        if tweet.kb_content:
            title = self._extract_title_from_content(tweet.kb_content)
            if title:
                tweet.kb_display_title = title
                return True
        
        # Fallback to tweet text
        if tweet.full_text:
            # Clean up tweet text for title
            title = tweet.full_text.strip()
            # Remove URLs and mentions for cleaner title
            words = title.split()
            clean_words = [w for w in words if not w.startswith(('http', '@', '#'))]
            clean_title = ' '.join(clean_words)[:100]
            
            if clean_title and len(clean_title) > 10:
                tweet.kb_display_title = clean_title
                return True
        
        # Last resort: use tweet ID
        tweet.kb_display_title = f"Tweet {tweet.tweet_id}"
        return True

    def _extract_title_from_content(self, content: str) -> Optional[str]:
        """Extract a meaningful title from KB content"""
        if not content:
            return None
        
        lines = content.strip().split('\n')
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            # Skip markdown headers
            if line.startswith('#'):
                continue
            
            # Skip very short lines
            if len(line) < 10:
                continue
            
            # Skip lines that look like metadata
            if ':' in line and len(line.split(':')) == 2:
                continue
            
            # This looks like a good title candidate
            return line[:100]
        
        return None

    def _validate_phase_completion(self, tweet: UnifiedTweet) -> List[str]:
        """Validate that completed phases have all required data"""
        issues = []
        
        # If kb_item_created is True, validate all required KB fields
        if tweet.kb_item_created:
            required_kb_fields = {
                'kb_content': 'Knowledge base content',
                'main_category': 'Main category',
                'sub_category': 'Sub category',
                'kb_item_name': 'Item name',
                'kb_display_title': 'Display title'
            }
            
            missing_fields = []
            for field, description in required_kb_fields.items():
                value = getattr(tweet, field)
                if not value or (isinstance(value, str) and not value.strip()):
                    missing_fields.append(description)
            
            if missing_fields:
                # Reset flags to trigger reprocessing
                tweet.kb_item_created = False
                if not tweet.main_category or not tweet.sub_category:
                    tweet.categories_processed = False
                
                issues.append(f"Flagged for reprocessing - missing: {', '.join(missing_fields)}")
        
        # If categories_processed is True, validate category fields
        if tweet.categories_processed:
            if not tweet.main_category or not tweet.sub_category:
                tweet.categories_processed = False
                issues.append("Flagged for recategorization - missing category data")
        
        return issues

    def _fix_json_string_fields(self, tweet: UnifiedTweet) -> List[str]:
        """Fix other JSON fields that might be stored as strings"""
        fixes = []
        
        json_fields = [
            'thread_tweets', 'media_files', 'image_descriptions',
            'raw_tweet_data', 'categories_raw_response'
        ]
        
        for field_name in json_fields:
            field_value = getattr(tweet, field_name)
            
            if isinstance(field_value, str) and field_value.strip():
                try:
                    parsed = json.loads(field_value)
                    setattr(tweet, field_name, parsed)
                    fixes.append(f"Fixed JSON parsing for {field_name}")
                except (json.JSONDecodeError, TypeError):
                    # Invalid JSON, leave as string or set to None
                    if field_name in ['media_files', 'thread_tweets', 'image_descriptions']:
                        setattr(tweet, field_name, [])
                        fixes.append(f"Reset invalid JSON field {field_name} to empty array")
        
        return fixes

    def _print_summary(self):
        """Print comprehensive validation summary"""
        print("\n" + "="*60)
        print("📊 UNIFIED DATABASE VALIDATION SUMMARY")
        print("="*60)
        
        print(f"📈 Total tweets processed: {self.stats['total_tweets']}")
        print(f"🔧 KB media paths fixed: {self.stats['fixed_kb_media_paths']}")
        print(f"📝 Display titles generated: {self.stats['fixed_display_titles']}")
        print(f"🗑️  Invalid media references removed: {self.stats['removed_invalid_media']}")
        print(f"🔄 Tweets flagged for reprocessing: {self.stats['flagged_for_reprocessing']}")
        print(f"📋 JSON parsing fixes: {self.stats['fixed_json_parsing']}")
        print(f"✅ Media files validated: {self.stats['validated_media_files']}")
        
        if self.detailed_logs:
            print(f"\n📋 DETAILED ISSUES FOUND ({len(self.detailed_logs)} tweets):")
            print("-" * 40)
            
            for log in self.detailed_logs[:10]:  # Show first 10
                print(f"Tweet {log['tweet_id']}:")
                for issue in log['issues']:
                    print(f"  • {issue}")
                print()
            
            if len(self.detailed_logs) > 10:
                print(f"... and {len(self.detailed_logs) - 10} more tweets with issues")
        
        print("\n" + "="*60)
        
        if self.dry_run:
            print("🔍 This was a DRY RUN - no changes were applied")
            print("💡 Run with --fix to apply these changes")
        else:
            print("✅ All fixes have been applied to the database")

def main():
    parser = argparse.ArgumentParser(description='Validate and fix unified database issues')
    parser.add_argument('--dry-run', action='store_true', default=True,
                       help='Preview changes without applying them (default)')
    parser.add_argument('--fix', action='store_true',
                       help='Apply fixes to the database')
    
    args = parser.parse_args()
    
    # Create Flask app context
    app, socketio, migrate, realtime_manager = create_app()
    
    with app.app_context():
        config = Config()
        validator = UnifiedDBValidator(config, dry_run=not args.fix)
        
        success = validator.validate_and_fix_all()
        
        if success:
            print("✅ Validation completed successfully")
            sys.exit(0)
        else:
            print("❌ Validation failed")
            sys.exit(1)

if __name__ == "__main__":
    main()