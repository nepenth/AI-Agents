#!/usr/bin/env python3
"""
Migration Script for Unified Database Data Cleanup

This script fixes data integrity issues that arose during the migration
from dual-table (TweetCache + KnowledgeBaseItem) to unified UnifiedTweet model:

1. Parses JSON strings in kb_media_paths and other JSON fields
2. Validates media file existence against filesystem
3. Generates missing display titles from content
4. Flags incomplete data for reprocessing
5. Cleans up invalid references and malformed data

Usage:
    python scripts/migrate_unified_db.py --dry-run    # Preview changes
    python scripts/migrate_unified_db.py --migrate    # Apply fixes
    python scripts/migrate_unified_db.py --validate   # Run validation only
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

class UnifiedDBMigrator:
    def __init__(self, config: Config, dry_run: bool = True):
        self.config = config
        self.dry_run = dry_run
        self.media_cache_dir = Path("data/media_cache")
        
        # Migration statistics
        self.stats = {
            'total_tweets': 0,
            'json_fields_fixed': 0,
            'display_titles_generated': 0,
            'media_references_cleaned': 0,
            'tweets_flagged_for_reprocessing': 0,
            'validation_errors_fixed': 0,
            'data_integrity_issues': 0
        }
        
        # Detailed migration log
        self.migration_log = []
        
        # Track specific fixes
        self.fixes_applied = {
            'kb_media_paths_json_parsed': [],
            'display_titles_generated': [],
            'invalid_media_removed': [],
            'flagged_for_reprocessing': [],
            'json_fields_fixed': []
        }

    def run_migration(self):
        """Main migration method"""
        print(f"🚀 Starting unified database migration {'(DRY RUN)' if self.dry_run else '(APPLYING FIXES)'}")
        print(f"📊 Media cache directory: {self.media_cache_dir.absolute()}")
        
        tweets = UnifiedTweet.query.all()
        self.stats['total_tweets'] = len(tweets)
        
        print(f"📈 Found {len(tweets)} tweets to migrate")
        
        for i, tweet in enumerate(tweets, 1):
            if i % 25 == 0:
                print(f"⏳ Processing tweet {i}/{len(tweets)}")
            
            self._migrate_tweet(tweet)
        
        if not self.dry_run:
            try:
                db.session.commit()
                print("✅ All migration changes committed to database")
            except Exception as e:
                db.session.rollback()
                print(f"❌ Error committing migration changes: {e}")
                return False
        
        self._print_migration_summary()
        return True

    def _migrate_tweet(self, tweet: UnifiedTweet):
        """Migrate a single tweet's data"""
        tweet_fixes = []
        
        # Fix 1: Parse JSON string fields
        json_fixes = self._fix_json_string_fields(tweet)
        if json_fixes:
            tweet_fixes.extend(json_fixes)
            self.stats['json_fields_fixed'] += len(json_fixes)
            self.fixes_applied['json_fields_fixed'].append({
                'tweet_id': tweet.tweet_id,
                'fixes': json_fixes
            })
        
        # Fix 2: Validate and clean media references
        media_fixes = self._validate_and_clean_media(tweet)
        if media_fixes:
            tweet_fixes.extend(media_fixes)
            self.stats['media_references_cleaned'] += 1
            self.fixes_applied['invalid_media_removed'].append({
                'tweet_id': tweet.tweet_id,
                'fixes': media_fixes
            })
        
        # Fix 3: Generate missing display titles
        if self._generate_missing_display_title(tweet):
            tweet_fixes.append("Generated display title from content")
            self.stats['display_titles_generated'] += 1
            self.fixes_applied['display_titles_generated'].append(tweet.tweet_id)
        
        # Fix 4: Validate data integrity and flag for reprocessing
        integrity_issues = self._validate_data_integrity(tweet)
        if integrity_issues:
            tweet_fixes.extend(integrity_issues)
            self.stats['tweets_flagged_for_reprocessing'] += 1
            self.stats['data_integrity_issues'] += len(integrity_issues)
            self.fixes_applied['flagged_for_reprocessing'].append({
                'tweet_id': tweet.tweet_id,
                'issues': integrity_issues
            })
        
        # Log all fixes for this tweet
        if tweet_fixes:
            self.migration_log.append({
                'tweet_id': tweet.tweet_id,
                'fixes': tweet_fixes
            })

    def _fix_json_string_fields(self, tweet: UnifiedTweet) -> List[str]:
        """Fix JSON fields that are stored as strings"""
        fixes = []
        
        # Define expected JSON fields and their types
        json_fields = {
            'thread_tweets': list,
            'media_files': list,
            'image_descriptions': list,
            'raw_tweet_data': dict,
            'categories_raw_response': dict,
            'kb_media_paths': list
        }
        
        for field_name, expected_type in json_fields.items():
            field_value = getattr(tweet, field_name)
            
            # Skip if field is None or already correct type
            if field_value is None:
                continue
            
            if isinstance(field_value, expected_type):
                continue
            
            # Try to parse string as JSON
            if isinstance(field_value, str) and field_value.strip():
                try:
                    parsed = json.loads(field_value)
                    if isinstance(parsed, expected_type):
                        setattr(tweet, field_name, parsed)
                        fixes.append(f"Parsed {field_name} from JSON string")
                    else:
                        # Wrong type after parsing, set to default
                        default_value = [] if expected_type == list else {}
                        setattr(tweet, field_name, default_value)
                        fixes.append(f"Reset {field_name} to default (wrong type after parsing)")
                except (json.JSONDecodeError, TypeError):
                    # Invalid JSON, set to default
                    default_value = [] if expected_type == list else {}
                    setattr(tweet, field_name, default_value)
                    fixes.append(f"Reset invalid JSON field {field_name} to default")
            else:
                # Non-string, non-expected type - convert to default
                default_value = [] if expected_type == list else {}
                setattr(tweet, field_name, default_value)
                fixes.append(f"Converted {field_name} from {type(field_value).__name__} to default")
        
        return fixes

    def _validate_and_clean_media(self, tweet: UnifiedTweet) -> List[str]:
        """Validate media files exist and clean invalid references"""
        fixes = []
        
        # Check media_files array
        if tweet.media_files and isinstance(tweet.media_files, list):
            original_count = len(tweet.media_files)
            valid_media = []
            
            for media_path in tweet.media_files:
                if self._media_file_exists(tweet.tweet_id, media_path):
                    valid_media.append(media_path)
                else:
                    fixes.append(f"Removed invalid media_files reference: {media_path}")
            
            if len(valid_media) != original_count:
                tweet.media_files = valid_media
                fixes.append(f"Cleaned media_files: {original_count} → {len(valid_media)} files")
        
        # Check kb_media_paths array
        if tweet.kb_media_paths and isinstance(tweet.kb_media_paths, list):
            original_count = len(tweet.kb_media_paths)
            valid_kb_media = []
            
            for media_path in tweet.kb_media_paths:
                if self._media_file_exists(tweet.tweet_id, media_path):
                    valid_kb_media.append(media_path)
                else:
                    fixes.append(f"Removed invalid kb_media_paths reference: {media_path}")
            
            if len(valid_kb_media) != original_count:
                tweet.kb_media_paths = valid_kb_media
                fixes.append(f"Cleaned kb_media_paths: {original_count} → {len(valid_kb_media)} files")
        
        return fixes

    def _media_file_exists(self, tweet_id: str, media_path: str) -> bool:
        """Check if media file actually exists on filesystem"""
        if not media_path:
            return False
        
        # Try multiple possible paths where media might be stored
        possible_paths = [
            Path(media_path),  # Absolute or relative path as-is
            self.media_cache_dir / media_path,  # Relative to media cache
            self.media_cache_dir / tweet_id / Path(media_path).name,  # In tweet-specific folder
            Path("data") / "media_cache" / tweet_id / Path(media_path).name,  # Full relative path
        ]
        
        for path in possible_paths:
            try:
                if path.exists() and path.is_file() and path.stat().st_size > 0:
                    return True
            except (OSError, PermissionError):
                continue
        
        return False

    def _generate_missing_display_title(self, tweet: UnifiedTweet) -> bool:
        """Generate display title if missing or empty"""
        if tweet.kb_display_title and tweet.kb_display_title.strip():
            return False  # Already has a title
        
        # Try to generate from kb_content first
        if tweet.kb_content:
            title = self._extract_title_from_content(tweet.kb_content)
            if title:
                tweet.kb_display_title = title
                return True
        
        # Try kb_item_name
        if tweet.kb_item_name and tweet.kb_item_name.strip():
            tweet.kb_display_title = tweet.kb_item_name[:100]
            return True
        
        # Fallback to tweet text
        if tweet.full_text:
            # Clean up tweet text for title
            title = tweet.full_text.strip()
            # Remove URLs and mentions for cleaner title
            words = title.split()
            clean_words = [w for w in words if not w.startswith(('http', '@', '#')) and len(w) > 2]
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
            
            # Skip lines that are mostly punctuation
            if len([c for c in line if c.isalnum()]) < len(line) * 0.5:
                continue
            
            # This looks like a good title candidate
            return line[:100]
        
        return None

    def _validate_data_integrity(self, tweet: UnifiedTweet) -> List[str]:
        """Validate data integrity and flag for reprocessing if needed"""
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
                if 'Main category' in missing_fields or 'Sub category' in missing_fields:
                    tweet.categories_processed = False
                
                issues.append(f"Flagged for reprocessing - missing: {', '.join(missing_fields)}")
        
        # If categories_processed is True, validate category fields
        if tweet.categories_processed:
            category_fields = ['main_category', 'sub_category', 'kb_item_name']
            missing_category_fields = []
            
            for field in category_fields:
                value = getattr(tweet, field)
                if not value or (isinstance(value, str) and not value.strip()):
                    missing_category_fields.append(field)
            
            if missing_category_fields:
                tweet.categories_processed = False
                issues.append(f"Flagged for recategorization - missing: {', '.join(missing_category_fields)}")
        
        # Validate processing sequence integrity
        if tweet.kb_item_created and not tweet.categories_processed:
            tweet.kb_item_created = False
            issues.append("Reset kb_item_created - categories not processed")
        
        if tweet.categories_processed and not tweet.media_processed:
            # This is actually OK - categories can be processed without media
            pass
        
        if tweet.processing_complete and not tweet.kb_item_created:
            tweet.processing_complete = False
            issues.append("Reset processing_complete - KB item not created")
        
        return issues

    def run_validation_only(self):
        """Run validation checks without making changes"""
        print("🔍 Running validation checks on unified database...")
        
        tweets = UnifiedTweet.query.all()
        validation_results = {
            'total_tweets': len(tweets),
            'json_string_issues': 0,
            'missing_display_titles': 0,
            'invalid_media_references': 0,
            'data_integrity_issues': 0,
            'tweets_needing_reprocessing': 0
        }
        
        issues_found = []
        
        for tweet in tweets:
            tweet_issues = []
            
            # Check for JSON string fields
            json_fields = ['thread_tweets', 'media_files', 'image_descriptions', 
                          'raw_tweet_data', 'categories_raw_response', 'kb_media_paths']
            
            for field_name in json_fields:
                field_value = getattr(tweet, field_name)
                if isinstance(field_value, str) and field_value.strip():
                    try:
                        json.loads(field_value)
                        tweet_issues.append(f"JSON string field: {field_name}")
                        validation_results['json_string_issues'] += 1
                    except (json.JSONDecodeError, TypeError):
                        tweet_issues.append(f"Invalid JSON field: {field_name}")
                        validation_results['json_string_issues'] += 1
            
            # Check for missing display titles
            if not tweet.kb_display_title or not tweet.kb_display_title.strip():
                if tweet.kb_item_created or tweet.kb_content:
                    tweet_issues.append("Missing display title")
                    validation_results['missing_display_titles'] += 1
            
            # Check media references
            media_issues = 0
            if tweet.media_files:
                for media_path in tweet.media_files:
                    if not self._media_file_exists(tweet.tweet_id, media_path):
                        media_issues += 1
            
            if tweet.kb_media_paths:
                for media_path in tweet.kb_media_paths:
                    if not self._media_file_exists(tweet.tweet_id, media_path):
                        media_issues += 1
            
            if media_issues > 0:
                tweet_issues.append(f"Invalid media references: {media_issues}")
                validation_results['invalid_media_references'] += 1
            
            # Check data integrity
            integrity_issues = self._validate_data_integrity(tweet)
            if integrity_issues:
                tweet_issues.extend(integrity_issues)
                validation_results['data_integrity_issues'] += len(integrity_issues)
                validation_results['tweets_needing_reprocessing'] += 1
            
            if tweet_issues:
                issues_found.append({
                    'tweet_id': tweet.tweet_id,
                    'issues': tweet_issues
                })
        
        # Print validation summary
        print("\n" + "="*60)
        print("📊 VALIDATION RESULTS")
        print("="*60)
        
        print(f"📈 Total tweets: {validation_results['total_tweets']}")
        print(f"🔧 JSON string issues: {validation_results['json_string_issues']}")
        print(f"📝 Missing display titles: {validation_results['missing_display_titles']}")
        print(f"🗑️  Invalid media references: {validation_results['invalid_media_references']}")
        print(f"⚠️  Data integrity issues: {validation_results['data_integrity_issues']}")
        print(f"🔄 Tweets needing reprocessing: {validation_results['tweets_needing_reprocessing']}")
        
        if issues_found:
            print(f"\n📋 ISSUES FOUND ({len(issues_found)} tweets):")
            print("-" * 40)
            
            for issue in issues_found[:10]:  # Show first 10
                print(f"Tweet {issue['tweet_id']}:")
                for problem in issue['issues']:
                    print(f"  • {problem}")
                print()
            
            if len(issues_found) > 10:
                print(f"... and {len(issues_found) - 10} more tweets with issues")
        
        print("\n" + "="*60)
        
        return validation_results

    def _print_migration_summary(self):
        """Print comprehensive migration summary"""
        print("\n" + "="*60)
        print("📊 UNIFIED DATABASE MIGRATION SUMMARY")
        print("="*60)
        
        print(f"📈 Total tweets processed: {self.stats['total_tweets']}")
        print(f"🔧 JSON fields fixed: {self.stats['json_fields_fixed']}")
        print(f"📝 Display titles generated: {self.stats['display_titles_generated']}")
        print(f"🗑️  Media references cleaned: {self.stats['media_references_cleaned']}")
        print(f"🔄 Tweets flagged for reprocessing: {self.stats['tweets_flagged_for_reprocessing']}")
        print(f"⚠️  Data integrity issues fixed: {self.stats['data_integrity_issues']}")
        
        # Show detailed fixes
        if self.fixes_applied['display_titles_generated']:
            print(f"\n📝 Display titles generated for tweets:")
            for tweet_id in self.fixes_applied['display_titles_generated'][:5]:
                print(f"  • {tweet_id}")
            if len(self.fixes_applied['display_titles_generated']) > 5:
                print(f"  ... and {len(self.fixes_applied['display_titles_generated']) - 5} more")
        
        if self.fixes_applied['flagged_for_reprocessing']:
            print(f"\n🔄 Tweets flagged for reprocessing:")
            for item in self.fixes_applied['flagged_for_reprocessing'][:5]:
                print(f"  • {item['tweet_id']}: {', '.join(item['issues'][:2])}")
            if len(self.fixes_applied['flagged_for_reprocessing']) > 5:
                print(f"  ... and {len(self.fixes_applied['flagged_for_reprocessing']) - 5} more")
        
        print("\n" + "="*60)
        
        if self.dry_run:
            print("🔍 This was a DRY RUN - no changes were applied")
            print("💡 Run with --migrate to apply these changes")
        else:
            print("✅ All migration fixes have been applied to the database")

def main():
    parser = argparse.ArgumentParser(description='Migrate and fix unified database issues')
    parser.add_argument('--dry-run', action='store_true', default=True,
                       help='Preview changes without applying them (default)')
    parser.add_argument('--migrate', action='store_true',
                       help='Apply migration fixes to the database')
    parser.add_argument('--validate', action='store_true',
                       help='Run validation checks only')
    
    args = parser.parse_args()
    
    # Create Flask app context
    app, socketio, migrate, realtime_manager = create_app()
    
    with app.app_context():
        config = Config()
        migrator = UnifiedDBMigrator(config, dry_run=not args.migrate)
        
        if args.validate:
            validation_results = migrator.run_validation_only()
            total_issues = (validation_results['json_string_issues'] + 
                          validation_results['missing_display_titles'] + 
                          validation_results['invalid_media_references'] + 
                          validation_results['data_integrity_issues'])
            
            if total_issues == 0:
                print("✅ No issues found - database is clean")
                sys.exit(0)
            else:
                print(f"⚠️  Found {total_issues} issues that need fixing")
                sys.exit(1)
        else:
            success = migrator.run_migration()
            
            if success:
                print("✅ Migration completed successfully")
                sys.exit(0)
            else:
                print("❌ Migration failed")
                sys.exit(1)

if __name__ == "__main__":
    main()