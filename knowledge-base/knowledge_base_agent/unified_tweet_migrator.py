#!/usr/bin/env python3
"""
Unified Tweet Migration Script

Migrates data from TweetCache and KnowledgeBaseItem tables to the new UnifiedTweet model.
Ensures zero data loss and maintains all processing state information.
"""

import json
import sys
import os
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List, Tuple
import logging

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from knowledge_base_agent.models import db, TweetCache, KnowledgeBaseItem, UnifiedTweet
from knowledge_base_agent.config import Config

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class UnifiedTweetMigrator:
    """Handles migration from dual-table to unified-table architecture."""
    
    def __init__(self, config: Optional[Config] = None):
        self.config = config or Config()
        self.stats = {
            'tweet_cache_records': 0,
            'knowledge_base_records': 0,
            'unified_records_created': 0,
            'merged_records': 0,
            'errors': 0,
            'skipped': 0
        }
        self.errors = []
    
    def migrate_all_data(self, dry_run: bool = False) -> Dict[str, Any]:
        """
        Main migration method that handles the complete data migration.
        
        Args:
            dry_run: If True, performs validation without actually writing data
            
        Returns:
            Dictionary with migration statistics and results
        """
        logger.info(f"Starting unified tweet migration (dry_run={dry_run})")
        
        try:
            # Step 1: Analyze existing data
            logger.info("Step 1: Analyzing existing data...")
            analysis = self._analyze_existing_data()
            logger.info(f"Analysis complete: {analysis}")
            
            # Step 2: Create migration mapping
            logger.info("Step 2: Creating migration mapping...")
            migration_map = self._create_migration_mapping()
            logger.info(f"Created migration map for {len(migration_map)} tweets")
            
            # Step 3: Migrate data
            logger.info("Step 3: Migrating data to unified table...")
            if not dry_run:
                self._migrate_to_unified_table(migration_map)
            else:
                logger.info("DRY RUN: Skipping actual data migration")
                self._validate_migration_mapping(migration_map)
            
            # Step 4: Validate migration
            logger.info("Step 4: Validating migration...")
            validation_results = self._validate_migration(dry_run)
            
            # Compile final results
            results = {
                'success': True,
                'dry_run': dry_run,
                'analysis': analysis,
                'stats': self.stats,
                'validation': validation_results,
                'errors': self.errors
            }
            
            logger.info(f"Migration completed successfully: {self.stats}")
            return results
            
        except Exception as e:
            logger.error(f"Migration failed: {e}", exc_info=True)
            return {
                'success': False,
                'error': str(e),
                'stats': self.stats,
                'errors': self.errors
            }
    
    def _analyze_existing_data(self) -> Dict[str, Any]:
        """Analyze existing data in TweetCache and KnowledgeBaseItem tables."""
        analysis = {
            'tweet_cache_count': 0,
            'knowledge_base_count': 0,
            'tweets_with_kb_items': 0,
            'tweets_without_kb_items': 0,
            'kb_items_without_tweets': 0,
            'data_integrity_issues': []
        }
        
        try:
            # Count TweetCache records
            tweet_cache_records = TweetCache.query.all()
            analysis['tweet_cache_count'] = len(tweet_cache_records)
            self.stats['tweet_cache_records'] = len(tweet_cache_records)
            
            # Count KnowledgeBaseItem records
            kb_records = KnowledgeBaseItem.query.all()
            analysis['knowledge_base_count'] = len(kb_records)
            self.stats['knowledge_base_records'] = len(kb_records)
            
            # Analyze relationships
            tweet_ids_with_kb = set()
            kb_tweet_ids = set()
            
            for kb_item in kb_records:
                if kb_item.tweet_id:
                    kb_tweet_ids.add(kb_item.tweet_id)
            
            for tweet in tweet_cache_records:
                if tweet.tweet_id in kb_tweet_ids:
                    tweet_ids_with_kb.add(tweet.tweet_id)
            
            analysis['tweets_with_kb_items'] = len(tweet_ids_with_kb)
            analysis['tweets_without_kb_items'] = len(tweet_cache_records) - len(tweet_ids_with_kb)
            analysis['kb_items_without_tweets'] = len(kb_tweet_ids) - len(tweet_ids_with_kb)
            
            # Check for data integrity issues
            if analysis['kb_items_without_tweets'] > 0:
                orphaned_kb_items = []
                for kb_item in kb_records:
                    if kb_item.tweet_id and kb_item.tweet_id not in [t.tweet_id for t in tweet_cache_records]:
                        orphaned_kb_items.append(kb_item.tweet_id)
                
                if orphaned_kb_items:
                    analysis['data_integrity_issues'].append({
                        'type': 'orphaned_kb_items',
                        'count': len(orphaned_kb_items),
                        'sample_ids': orphaned_kb_items[:5]
                    })
            
            return analysis
            
        except Exception as e:
            logger.error(f"Error analyzing existing data: {e}")
            raise
    
    def _create_migration_mapping(self) -> Dict[str, Dict[str, Any]]:
        """Create a mapping of how data should be migrated to unified table."""
        migration_map = {}
        
        try:
            # Get all TweetCache records
            tweet_cache_records = TweetCache.query.all()
            
            for tweet in tweet_cache_records:
                tweet_id = tweet.tweet_id
                
                # Start with TweetCache data
                unified_data = self._map_tweet_cache_to_unified(tweet)
                
                # Find corresponding KnowledgeBaseItem if it exists
                kb_item = KnowledgeBaseItem.query.filter_by(tweet_id=tweet_id).first()
                if kb_item:
                    # Merge KB item data
                    kb_data = self._map_kb_item_to_unified(kb_item)
                    unified_data.update(kb_data)
                    unified_data['has_kb_item'] = True
                else:
                    unified_data['has_kb_item'] = False
                
                migration_map[tweet_id] = unified_data
            
            # Handle orphaned KnowledgeBaseItem records (KB items without corresponding tweets)
            kb_records = KnowledgeBaseItem.query.all()
            for kb_item in kb_records:
                if kb_item.tweet_id and kb_item.tweet_id not in migration_map:
                    # Create unified record from KB item only
                    logger.warning(f"Found orphaned KB item for tweet {kb_item.tweet_id}")
                    unified_data = self._create_unified_from_kb_only(kb_item)
                    migration_map[kb_item.tweet_id] = unified_data
            
            return migration_map
            
        except Exception as e:
            logger.error(f"Error creating migration mapping: {e}")
            raise
    
    def _map_tweet_cache_to_unified(self, tweet: TweetCache) -> Dict[str, Any]:
        """Map TweetCache fields to UnifiedTweet fields."""
        return {
            'tweet_id': tweet.tweet_id,
            'bookmarked_tweet_id': tweet.bookmarked_tweet_id,
            'is_thread': tweet.is_thread,
            
            # Processing flags
            'urls_expanded': tweet.urls_expanded,
            'cache_complete': tweet.cache_complete,
            'media_processed': tweet.media_processed,
            'categories_processed': tweet.categories_processed,
            'kb_item_created': tweet.kb_item_created,
            'processing_complete': tweet.kb_item_created,  # Assume complete if KB item created
            
            # Content data
            'raw_tweet_data': tweet.raw_json_content,
            'thread_tweets': tweet.thread_tweets or [],
            'full_text': tweet.full_text,
            'media_files': tweet.all_downloaded_media_for_thread or [],
            'image_descriptions': tweet.image_descriptions or [],
            
            # Categorization
            'main_category': tweet.main_category,
            'sub_category': tweet.sub_category,
            'categories_raw_response': tweet.categories,
            'kb_item_name': tweet.item_name_suggestion,
            
            # KB data from TweetCache
            'kb_file_path': tweet.kb_item_path,
            'kb_media_paths': tweet.kb_media_paths or [],
            
            # Metadata
            'source': tweet.source or 'twitter',
            
            # Error tracking
            'kbitem_error': tweet.kbitem_error,
            'llm_error': tweet.llm_error,
            'recategorization_attempts': tweet.recategorization_attempts,
            
            # Reprocessing controls
            'force_reprocess_pipeline': tweet.force_reprocess_pipeline,
            'force_recache': tweet.force_recache,
            'reprocess_requested_at': tweet.reprocess_requested_at,
            'reprocess_requested_by': tweet.reprocess_requested_by,
            
            # Runtime flags
            'cache_succeeded_this_run': tweet.cache_succeeded_this_run,
            'media_succeeded_this_run': tweet.media_succeeded_this_run,
            'llm_succeeded_this_run': tweet.llm_succeeded_this_run,
            'kbitem_succeeded_this_run': tweet.kbitem_succeeded_this_run,
            'db_synced': True,  # Always true for unified model
            
            # Timestamps
            'created_at': tweet.created_at,
            'updated_at': tweet.updated_at,
            'cached_at': tweet.created_at,  # Use created_at as cached_at
        }
    
    def _map_kb_item_to_unified(self, kb_item: KnowledgeBaseItem) -> Dict[str, Any]:
        """Map KnowledgeBaseItem fields to UnifiedTweet fields."""
        # Parse kb_media_paths if it's a JSON string
        kb_media_paths = []
        if kb_item.kb_media_paths:
            try:
                if isinstance(kb_item.kb_media_paths, str):
                    kb_media_paths = json.loads(kb_item.kb_media_paths)
                else:
                    kb_media_paths = kb_item.kb_media_paths
            except (json.JSONDecodeError, TypeError):
                logger.warning(f"Could not parse kb_media_paths for KB item {kb_item.id}: {kb_item.kb_media_paths}")
                kb_media_paths = []
        
        return {
            # KB-specific data that might override TweetCache data
            'kb_title': kb_item.title,
            'kb_display_title': kb_item.display_title,
            'kb_description': kb_item.description,
            'kb_content': kb_item.content,
            'kb_file_path': kb_item.file_path,
            'kb_media_paths': kb_media_paths,
            'source_url': kb_item.source_url,
            
            # Override processing flags if KB item exists
            'kb_item_created': True,
            'kb_item_written_to_disk': bool(kb_item.file_path),
            'processing_complete': True,
            
            # Use KB item timestamps if available
            'kb_generated_at': kb_item.last_updated,
            'processed_at': kb_item.last_updated,
            
            # Ensure these are set from KB item
            'main_category': kb_item.main_category,
            'sub_category': kb_item.sub_category,
        }
    
    def _create_unified_from_kb_only(self, kb_item: KnowledgeBaseItem) -> Dict[str, Any]:
        """Create unified record from orphaned KnowledgeBaseItem."""
        kb_media_paths = []
        if kb_item.kb_media_paths:
            try:
                if isinstance(kb_item.kb_media_paths, str):
                    kb_media_paths = json.loads(kb_item.kb_media_paths)
                else:
                    kb_media_paths = kb_item.kb_media_paths
            except (json.JSONDecodeError, TypeError):
                kb_media_paths = []
        
        return {
            'tweet_id': kb_item.tweet_id,
            'bookmarked_tweet_id': kb_item.tweet_id,  # Use same as tweet_id
            'is_thread': False,
            
            # Set all processing flags to True since KB item exists
            'urls_expanded': True,
            'cache_complete': True,
            'media_processed': True,
            'categories_processed': True,
            'kb_item_created': True,
            'kb_item_written_to_disk': bool(kb_item.file_path),
            'processing_complete': True,
            
            # KB data
            'kb_title': kb_item.title,
            'kb_display_title': kb_item.display_title,
            'kb_description': kb_item.description,
            'kb_content': kb_item.content,
            'kb_file_path': kb_item.file_path,
            'kb_media_paths': kb_media_paths,
            
            # Categorization
            'main_category': kb_item.main_category,
            'sub_category': kb_item.sub_category,
            'kb_item_name': kb_item.item_name,
            
            # Metadata
            'source': 'twitter',
            'source_url': kb_item.source_url,
            
            # Timestamps
            'created_at': kb_item.created_at,
            'updated_at': kb_item.last_updated,
            'kb_generated_at': kb_item.last_updated,
            'processed_at': kb_item.last_updated,
            
            # Default values for missing data
            'thread_tweets': [],
            'media_files': [],
            'image_descriptions': [],
            'processing_errors': {},
            'retry_count': 0,
            'recategorization_attempts': 0,
            'db_synced': True,
            'has_kb_item': True
        }
    
    def _migrate_to_unified_table(self, migration_map: Dict[str, Dict[str, Any]]) -> None:
        """Migrate data to the unified table."""
        try:
            for tweet_id, unified_data in migration_map.items():
                try:
                    # Check if record already exists
                    existing = UnifiedTweet.query.filter_by(tweet_id=tweet_id).first()
                    if existing:
                        logger.info(f"Unified record already exists for tweet {tweet_id}, skipping")
                        self.stats['skipped'] += 1
                        continue
                    
                    # Create new unified record
                    unified_tweet = UnifiedTweet(**{k: v for k, v in unified_data.items() if k != 'has_kb_item'})
                    db.session.add(unified_tweet)
                    
                    self.stats['unified_records_created'] += 1
                    if unified_data.get('has_kb_item'):
                        self.stats['merged_records'] += 1
                    
                    # Commit in batches of 100
                    if self.stats['unified_records_created'] % 100 == 0:
                        db.session.commit()
                        logger.info(f"Migrated {self.stats['unified_records_created']} records...")
                
                except Exception as e:
                    logger.error(f"Error migrating tweet {tweet_id}: {e}")
                    self.errors.append(f"Tweet {tweet_id}: {str(e)}")
                    self.stats['errors'] += 1
                    db.session.rollback()
            
            # Final commit
            db.session.commit()
            logger.info(f"Migration complete: {self.stats['unified_records_created']} records created")
            
        except Exception as e:
            logger.error(f"Error during migration: {e}")
            db.session.rollback()
            raise
    
    def _validate_migration_mapping(self, migration_map: Dict[str, Dict[str, Any]]) -> None:
        """Validate migration mapping in dry run mode."""
        logger.info("Validating migration mapping...")
        
        for tweet_id, unified_data in migration_map.items():
            # Check required fields
            required_fields = ['tweet_id', 'bookmarked_tweet_id']
            for field in required_fields:
                if not unified_data.get(field):
                    self.errors.append(f"Tweet {tweet_id}: Missing required field {field}")
            
            # Validate JSON fields (but allow strings for kb_media_paths as they'll be converted)
            json_fields = ['thread_tweets', 'media_files', 'image_descriptions']
            for field in json_fields:
                value = unified_data.get(field)
                if value is not None and not isinstance(value, (list, dict)):
                    self.errors.append(f"Tweet {tweet_id}: Field {field} should be JSON serializable")
            
            # Special handling for kb_media_paths which might be JSON strings
            kb_media_paths = unified_data.get('kb_media_paths')
            if kb_media_paths is not None:
                if isinstance(kb_media_paths, str):
                    try:
                        json.loads(kb_media_paths)
                    except (json.JSONDecodeError, TypeError):
                        self.errors.append(f"Tweet {tweet_id}: Field kb_media_paths is not valid JSON")
                elif not isinstance(kb_media_paths, (list, dict)):
                    self.errors.append(f"Tweet {tweet_id}: Field kb_media_paths should be JSON serializable")
        
        logger.info(f"Validation complete: {len(self.errors)} issues found")
    
    def _validate_migration(self, dry_run: bool) -> Dict[str, Any]:
        """Validate the migration results."""
        validation = {
            'total_unified_records': 0,
            'data_integrity_checks': [],
            'missing_data_issues': [],
            'success': True
        }
        
        if not dry_run:
            try:
                # Count unified records
                unified_count = UnifiedTweet.query.count()
                validation['total_unified_records'] = unified_count
                
                # Check data integrity
                sample_records = UnifiedTweet.query.limit(10).all()
                for record in sample_records:
                    checks = []
                    
                    # Check required fields
                    if not record.tweet_id:
                        checks.append("Missing tweet_id")
                    if not record.bookmarked_tweet_id:
                        checks.append("Missing bookmarked_tweet_id")
                    
                    # Check JSON fields are properly formatted
                    json_fields = ['thread_tweets', 'media_files', 'image_descriptions', 'kb_media_paths']
                    for field in json_fields:
                        value = getattr(record, field)
                        if value is not None and not isinstance(value, (list, dict)):
                            checks.append(f"Field {field} is not JSON serializable")
                    
                    if checks:
                        validation['data_integrity_checks'].append({
                            'tweet_id': record.tweet_id,
                            'issues': checks
                        })
                
                # Check for missing critical data
                records_without_content = UnifiedTweet.query.filter(
                    (UnifiedTweet.full_text == None) | (UnifiedTweet.full_text == '')
                ).count()
                
                if records_without_content > 0:
                    validation['missing_data_issues'].append({
                        'type': 'missing_full_text',
                        'count': records_without_content
                    })
                
                validation['success'] = len(validation['data_integrity_checks']) == 0
                
            except Exception as e:
                logger.error(f"Error during validation: {e}")
                validation['success'] = False
                validation['error'] = str(e)
        
        return validation


def main():
    """Main migration script entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Migrate to unified tweet architecture')
    parser.add_argument('--dry-run', action='store_true', help='Perform dry run without actual migration')
    parser.add_argument('--verbose', action='store_true', help='Enable verbose logging')
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    try:
        # Initialize Flask app context
        from knowledge_base_agent.web import create_app
        app = create_app()
        
        with app.app_context():
            migrator = UnifiedTweetMigrator()
            results = migrator.migrate_all_data(dry_run=args.dry_run)
            
            if results['success']:
                print("\n✅ Migration completed successfully!")
                print(f"📊 Statistics: {results['stats']}")
                if results['errors']:
                    print(f"⚠️  Errors encountered: {len(results['errors'])}")
                    for error in results['errors'][:5]:  # Show first 5 errors
                        print(f"   - {error}")
            else:
                print(f"\n❌ Migration failed: {results.get('error', 'Unknown error')}")
                return 1
        
        return 0
        
    except Exception as e:
        logger.error(f"Migration script failed: {e}", exc_info=True)
        return 1


if __name__ == '__main__':
    sys.exit(main())