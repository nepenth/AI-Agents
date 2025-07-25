"""
Enhanced Validation System

Provides comprehensive data integrity checks, cross-reference validation,
and health monitoring for the tweet processing pipeline with database backend.
"""

import asyncio
import logging
from typing import Dict, Any, List, Optional, Tuple, Set
from datetime import datetime, timezone, timedelta
from dataclasses import dataclass
from pathlib import Path
import json

from .config import Config
from .repositories import TweetCacheRepository, TweetProcessingQueueRepository, CategoryRepository
from .database import get_db_session_context
from .models import TweetCache, TweetProcessingQueue, CategoryHierarchy


@dataclass
class ValidationResult:
    """Result of a validation check."""
    is_valid: bool
    issue_count: int
    issues: List[str]
    fixes_applied: int
    validation_time: float
    metadata: Dict[str, Any]


@dataclass
class ValidationSummary:
    """Summary of all validation results."""
    total_validations: int
    passed_validations: int
    failed_validations: int
    total_issues: int
    total_fixes: int
    validation_duration: float
    results: Dict[str, ValidationResult]


class EnhancedValidator:
    """
    Comprehensive validation system for database-backed tweet processing.
    
    Features:
    - Deep data integrity checks
    - Cross-reference validation between database and filesystem
    - Processing phase consistency validation
    - Health monitoring and diagnostics
    - Automatic issue detection and repair
    """
    
    def __init__(self, config: Config):
        self.config = config
        self.logger = logging.getLogger(__name__)
        
        # Initialize repositories
        self.tweet_repo = TweetCacheRepository()
        self.queue_repo = TweetProcessingQueueRepository()
        self.category_repo = CategoryRepository()
    
    async def run_comprehensive_validation(self, auto_fix: bool = True) -> ValidationSummary:
        """
        Run all validation checks and return comprehensive summary.
        
        Args:
            auto_fix: Whether to automatically fix detected issues
            
        Returns:
            Comprehensive validation summary
        """
        start_time = datetime.now()
        
        self.logger.info("🔍 Starting comprehensive validation suite...")
        
        # Define all validation checks
        validation_checks = [
            ("database_integrity", self._validate_database_integrity),
            ("processing_flags_consistency", self._validate_processing_flags),
            ("queue_consistency", self._validate_queue_consistency),
            ("category_integrity", self._validate_category_integrity),
            ("filesystem_consistency", self._validate_filesystem_consistency),
            ("content_completeness", self._validate_content_completeness),
            ("retry_metadata_consistency", self._validate_retry_metadata),
            ("temporal_consistency", self._validate_temporal_consistency),
            ("cross_reference_integrity", self._validate_cross_references)
        ]
        
        results = {}
        total_issues = 0
        total_fixes = 0
        passed_count = 0
        
        # Run each validation check
        for check_name, check_function in validation_checks:
            try:
                self.logger.info(f"Running {check_name} validation...")
                result = await check_function(auto_fix)
                results[check_name] = result
                
                total_issues += result.issue_count
                total_fixes += result.fixes_applied
                
                if result.is_valid:
                    passed_count += 1
                    self.logger.info(f"✅ {check_name}: PASSED")
                else:
                    self.logger.warning(f"⚠️ {check_name}: FAILED - {result.issue_count} issues found")
                    
            except Exception as e:
                self.logger.error(f"❌ {check_name} validation failed with exception: {e}")
                results[check_name] = ValidationResult(
                    is_valid=False,
                    issue_count=1,
                    issues=[f"Validation exception: {e}"],
                    fixes_applied=0,
                    validation_time=0.0,
                    metadata={"exception": str(e)}
                )
        
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        
        summary = ValidationSummary(
            total_validations=len(validation_checks),
            passed_validations=passed_count,
            failed_validations=len(validation_checks) - passed_count,
            total_issues=total_issues,
            total_fixes=total_fixes,
            validation_duration=duration,
            results=results
        )
        
        self.logger.info(
            f"🏁 Validation complete: {passed_count}/{len(validation_checks)} passed, "
            f"{total_issues} issues found, {total_fixes} fixes applied, "
            f"duration: {duration:.2f}s"
        )
        
        return summary
    
    async def _validate_database_integrity(self, auto_fix: bool) -> ValidationResult:
        """Validate database structure and basic integrity."""
        start_time = datetime.now()
        issues = []
        fixes = 0
        tweets_count = 0
        
        try:
            # Check if methods exist (graceful handling of missing methods)
            if not hasattr(self.tweet_repo, 'get_total_count'):
                issues.append("TweetCacheRepository missing get_total_count method")
                tweets_count = 0
            else:
                tweets_count = self.tweet_repo.get_total_count()
            
            if not hasattr(self.tweet_repo, 'get_all'):
                issues.append("TweetCacheRepository missing get_all method")
                tweets = []
            else:
                tweets = self.tweet_repo.get_all()
            
            # Check for tweets without required fields
            for tweet in tweets:
                if not tweet.tweet_id:
                    issues.append(f"Tweet record {tweet.id} missing tweet_id")
                    if auto_fix:
                        # Can't fix missing tweet_id, would need to delete record
                        pass
                
                if not tweet.bookmarked_tweet_id:
                    issues.append(f"Tweet {tweet.tweet_id} missing bookmarked_tweet_id")
                    if auto_fix:
                        self.tweet_repo.update(tweet.tweet_id, {'bookmarked_tweet_id': tweet.tweet_id})
                        fixes += 1
                
                # Check for invalid boolean fields
                boolean_fields = ['is_thread', 'urls_expanded', 'media_processed', 
                                'cache_complete', 'categories_processed', 'kb_item_created', 'db_synced']
                for field in boolean_fields:
                    value = getattr(tweet, field, None)
                    if value is None:
                        issues.append(f"Tweet {tweet.tweet_id} has None value for boolean field {field}")
                        if auto_fix:
                            self.tweet_repo.update(tweet.tweet_id, {field: False})
                            fixes += 1
                
                # Check for invalid JSON fields
                json_fields = ['thread_tweets', 'all_downloaded_media_for_thread', 'categories', 'kb_media_paths']
                for field in json_fields:
                    value = getattr(tweet, field, None)
                    if value is None:
                        issues.append(f"Tweet {tweet.tweet_id} has None value for JSON field {field}")
                        if auto_fix:
                            default_value = [] if field != 'categories' else {}
                            self.tweet_repo.update(tweet.tweet_id, {field: default_value})
                            fixes += 1
            
            # Check processing queue integrity
            if hasattr(self.queue_repo, 'get_all'):
                queue_entries = self.queue_repo.get_all()
                for entry in queue_entries:
                    # Check if referenced tweet exists
                    tweet = self.tweet_repo.get_by_id(entry.tweet_id)
                    if not tweet:
                        issues.append(f"Queue entry {entry.id} references non-existent tweet {entry.tweet_id}")
                        if auto_fix:
                            self.queue_repo.delete(entry.tweet_id)
                            fixes += 1
            else:
                issues.append("TweetProcessingQueueRepository missing get_all method")
            
        except Exception as e:
            issues.append(f"Database integrity check failed: {e}")
        
        duration = (datetime.now() - start_time).total_seconds()
        
        return ValidationResult(
            is_valid=len(issues) == 0,
            issue_count=len(issues),
            issues=issues,
            fixes_applied=fixes,
            validation_time=duration,
            metadata={"tweets_checked": tweets_count}
        )
    
    async def _validate_processing_flags(self, auto_fix: bool) -> ValidationResult:
        """Validate processing flag consistency and logical progression."""
        start_time = datetime.now()
        issues = []
        fixes = 0
        
        if not hasattr(self.tweet_repo, 'get_all'):
            issues.append("TweetCacheRepository missing get_all method")
            tweets = []
        else:
            tweets = self.tweet_repo.get_all()
        
        for tweet in tweets:
            tweet_id = tweet.tweet_id
            
            # Rule 1: If media_processed is True, cache_complete should be True
            if tweet.media_processed and not tweet.cache_complete:
                issues.append(f"Tweet {tweet_id}: media_processed=True but cache_complete=False")
                if auto_fix:
                    self.tweet_repo.update(tweet_id, {'cache_complete': True})
                    fixes += 1
            
            # Rule 2: If categories_processed is True, cache_complete should be True
            if tweet.categories_processed and not tweet.cache_complete:
                issues.append(f"Tweet {tweet_id}: categories_processed=True but cache_complete=False")
                if auto_fix:
                    self.tweet_repo.update(tweet_id, {'cache_complete': True})
                    fixes += 1
            
            # Rule 3: If kb_item_created is True, all previous phases should be True
            if tweet.kb_item_created:
                required_flags = ['cache_complete', 'media_processed', 'categories_processed']
                for flag in required_flags:
                    if not getattr(tweet, flag):
                        issues.append(f"Tweet {tweet_id}: kb_item_created=True but {flag}=False")
                        if auto_fix:
                            self.tweet_repo.update(tweet_id, {flag: True})
                            fixes += 1
            
            # Rule 4: If categories_processed is True, should have category data
            if tweet.categories_processed:
                if not tweet.main_category:
                    issues.append(f"Tweet {tweet_id}: categories_processed=True but no main_category")
                if not tweet.item_name_suggestion:
                    issues.append(f"Tweet {tweet_id}: categories_processed=True but no item_name_suggestion")
            
            # Rule 5: If kb_item_created is True, should have kb_item_path
            if tweet.kb_item_created and not tweet.kb_item_path:
                issues.append(f"Tweet {tweet_id}: kb_item_created=True but no kb_item_path")
        
        duration = (datetime.now() - start_time).total_seconds()
        
        return ValidationResult(
            is_valid=len(issues) == 0,
            issue_count=len(issues),
            issues=issues,
            fixes_applied=fixes,
            validation_time=duration,
            metadata={"tweets_checked": len(tweets)}
        )
    
    async def _validate_queue_consistency(self, auto_fix: bool) -> ValidationResult:
        """Validate processing queue consistency with tweet states."""
        start_time = datetime.now()
        issues = []
        fixes = 0
        
        # Get all tweets and queue entries (with graceful fallback)
        if hasattr(self.tweet_repo, 'get_all'):
            tweets = {tweet.tweet_id: tweet for tweet in self.tweet_repo.get_all()}
        else:
            issues.append("TweetCacheRepository missing get_all method")
            tweets = {}
            
        if hasattr(self.queue_repo, 'get_all'):
            queue_entries = {entry.tweet_id: entry for entry in self.queue_repo.get_all()}
        else:
            issues.append("TweetProcessingQueueRepository missing get_all method")
            queue_entries = {}
        
        # Check for tweets that should be in processed queue but aren't
        for tweet_id, tweet in tweets.items():
            is_fully_processed = (tweet.cache_complete and tweet.media_processed and 
                                tweet.categories_processed and tweet.kb_item_created)
            
            queue_entry = queue_entries.get(tweet_id)
            
            if is_fully_processed:
                if not queue_entry or queue_entry.status != "processed":
                    issues.append(f"Tweet {tweet_id} is fully processed but not in processed queue")
                    if auto_fix:
                        if queue_entry:
                            self.queue_repo.update_status(tweet_id, "processed")
                        else:
                            self.queue_repo.create({
                                "tweet_id": tweet_id,
                                "status": "processed",
                                "processed_at": datetime.now(timezone.utc)
                            })
                        fixes += 1
            else:
                if queue_entry and queue_entry.status == "processed":
                    issues.append(f"Tweet {tweet_id} is not fully processed but marked as processed in queue")
                    if auto_fix:
                        self.queue_repo.update_status(tweet_id, "unprocessed")
                        fixes += 1
        
        # Check for queue entries without corresponding tweets
        for tweet_id, queue_entry in queue_entries.items():
            if tweet_id not in tweets:
                issues.append(f"Queue entry exists for non-existent tweet {tweet_id}")
                if auto_fix:
                    self.queue_repo.delete(tweet_id)
                    fixes += 1
        
        duration = (datetime.now() - start_time).total_seconds()
        
        return ValidationResult(
            is_valid=len(issues) == 0,
            issue_count=len(issues),
            issues=issues,
            fixes_applied=fixes,
            validation_time=duration,
            metadata={
                "tweets_checked": len(tweets),
                "queue_entries_checked": len(queue_entries)
            }
        )
    
    async def _validate_category_integrity(self, auto_fix: bool) -> ValidationResult:
        """Validate category data integrity and consistency."""
        start_time = datetime.now()
        issues = []
        fixes = 0
        
        # Get all categories and tweets with categories (with graceful fallback)
        if hasattr(self.category_repo, 'get_all'):
            categories = {f"{cat.main_category}/{cat.sub_category}": cat 
                         for cat in self.category_repo.get_all()}
        else:
            issues.append("CategoryRepository missing get_all method")
            categories = {}
            
        if hasattr(self.tweet_repo, 'get_all'):
            tweets_with_categories = [tweet for tweet in self.tweet_repo.get_all() 
                                    if tweet.main_category or tweet.sub_category]
        else:
            issues.append("TweetCacheRepository missing get_all method")
            tweets_with_categories = []
        
        for tweet in tweets_with_categories:
            if tweet.main_category and tweet.sub_category:
                category_key = f"{tweet.main_category}/{tweet.sub_category}"
                
                # Check if category exists in hierarchy
                if category_key not in categories:
                    issues.append(f"Tweet {tweet.tweet_id} uses non-existent category: {category_key}")
                    if auto_fix:
                        # Create missing category
                        self.category_repo.create({
                            "main_category": tweet.main_category,
                            "sub_category": tweet.sub_category,
                            "item_count": 1,
                            "description": f"Auto-created category for {tweet.main_category}/{tweet.sub_category}"
                        })
                        fixes += 1
        
        duration = (datetime.now() - start_time).total_seconds()
        
        return ValidationResult(
            is_valid=len(issues) == 0,
            issue_count=len(issues),
            issues=issues,
            fixes_applied=fixes,
            validation_time=duration,
            metadata={
                "categories_checked": len(categories),
                "tweets_with_categories": len(tweets_with_categories)
            }
        )
    
    async def _validate_filesystem_consistency(self, auto_fix: bool) -> ValidationResult:
        """Validate consistency between database and filesystem for KB items."""
        start_time = datetime.now()
        issues = []
        fixes = 0
        
        if hasattr(self.tweet_repo, 'get_all'):
            tweets_with_kb_items = [tweet for tweet in self.tweet_repo.get_all() 
                                  if tweet.kb_item_created and tweet.kb_item_path]
        else:
            issues.append("TweetCacheRepository missing get_all method")
            tweets_with_kb_items = []
        
        for tweet in tweets_with_kb_items:
            try:
                # Check if KB item file exists
                kb_item_path = self.config.resolve_path_from_project_root(tweet.kb_item_path)
                if not kb_item_path.exists():
                    issues.append(f"Tweet {tweet.tweet_id}: KB item file missing at {tweet.kb_item_path}")
                    if auto_fix:
                        # Mark KB item as not created since file is missing
                        self.tweet_repo.update(tweet.tweet_id, {'kb_item_created': False})
                        fixes += 1
                else:
                    # Check if file contains expected content
                    try:
                        with open(kb_item_path, 'r', encoding='utf-8') as f:
                            content = f.read(500)  # Read first 500 chars
                            if tweet.tweet_id not in content:
                                issues.append(f"Tweet {tweet.tweet_id}: KB item file doesn't contain tweet ID")
                    except Exception as e:
                        issues.append(f"Tweet {tweet.tweet_id}: Error reading KB item file: {e}")
                        
            except Exception as e:
                issues.append(f"Tweet {tweet.tweet_id}: Error validating KB item path: {e}")
        
        duration = (datetime.now() - start_time).total_seconds()
        
        return ValidationResult(
            is_valid=len(issues) == 0,
            issue_count=len(issues),
            issues=issues,
            fixes_applied=fixes,
            validation_time=duration,
            metadata={"kb_items_checked": len(tweets_with_kb_items)}
        )
    
    async def _validate_content_completeness(self, auto_fix: bool) -> ValidationResult:
        """Validate that tweets have required content fields."""
        start_time = datetime.now()
        issues = []
        fixes = 0
        
        tweets = self.tweet_repo.get_all()
        
        for tweet in tweets:
            # Check for tweets marked as cache_complete but missing content
            if tweet.cache_complete:
                if not tweet.full_text and not tweet.thread_tweets:
                    issues.append(f"Tweet {tweet.tweet_id}: cache_complete=True but no content")
                    if auto_fix:
                        # Mark as not cache complete if no content
                        self.tweet_repo.update(tweet.tweet_id, {'cache_complete': False})
                        fixes += 1
            
            # Check for tweets with categories but no item name
            if tweet.categories_processed and tweet.main_category:
                if not tweet.item_name_suggestion:
                    issues.append(f"Tweet {tweet.tweet_id}: has categories but no item_name_suggestion")
                    if auto_fix:
                        # Generate basic item name
                        item_name = f"{tweet.main_category} - {tweet.tweet_id}"
                        self.tweet_repo.update(tweet.tweet_id, {'item_name_suggestion': item_name})
                        fixes += 1
        
        duration = (datetime.now() - start_time).total_seconds()
        
        return ValidationResult(
            is_valid=len(issues) == 0,
            issue_count=len(issues),
            issues=issues,
            fixes_applied=fixes,
            validation_time=duration,
            metadata={"tweets_checked": len(tweets)}
        )
    
    async def _validate_retry_metadata(self, auto_fix: bool) -> ValidationResult:
        """Validate retry metadata consistency."""
        start_time = datetime.now()
        issues = []
        fixes = 0
        
        tweets = self.tweet_repo.get_all()
        
        for tweet in tweets:
            # Get tweet data as dict for easier access
            tweet_data = self.tweet_repo.get_by_id(tweet.tweet_id)
            if not tweet_data:
                continue
                
            # Convert to dict format
            data_dict = {
                'retry_count': getattr(tweet_data, 'retry_count', 0),
                'next_retry_after': getattr(tweet_data, 'next_retry_after', None),
                'failure_type': getattr(tweet_data, 'failure_type', None)
            }
            
            # Check for inconsistent retry metadata
            if data_dict.get('retry_count', 0) > 0:
                if not data_dict.get('failure_type'):
                    issues.append(f"Tweet {tweet.tweet_id}: has retry_count but no failure_type")
            
            # Check for outdated retry schedules
            next_retry_str = data_dict.get('next_retry_after')
            if next_retry_str:
                try:
                    next_retry_time = datetime.fromisoformat(next_retry_str.replace('Z', '+00:00'))
                    if datetime.now(timezone.utc) > next_retry_time + timedelta(days=7):
                        issues.append(f"Tweet {tweet.tweet_id}: retry scheduled over a week ago")
                        if auto_fix:
                            # Clear outdated retry metadata
                            updates = {
                                'retry_count': 0,
                                'next_retry_after': None,
                                'failure_type': None
                            }
                            self.tweet_repo.update(tweet.tweet_id, updates)
                            fixes += 1
                except (ValueError, AttributeError):
                    issues.append(f"Tweet {tweet.tweet_id}: invalid next_retry_after format")
        
        duration = (datetime.now() - start_time).total_seconds()
        
        return ValidationResult(
            is_valid=len(issues) == 0,
            issue_count=len(issues),
            issues=issues,
            fixes_applied=fixes,
            validation_time=duration,
            metadata={"tweets_checked": len(tweets)}
        )
    
    async def _validate_temporal_consistency(self, auto_fix: bool) -> ValidationResult:
        """Validate temporal consistency of timestamps."""
        start_time = datetime.now()
        issues = []
        fixes = 0
        
        if hasattr(self.tweet_repo, 'get_all'):
            tweets = self.tweet_repo.get_all()
        else:
            issues.append("TweetCacheRepository missing get_all method")
            tweets = []
        
        for tweet in tweets:
            # Check if updated_at is older than created_at
            if tweet.created_at and tweet.updated_at:
                if tweet.updated_at < tweet.created_at:
                    issues.append(f"Tweet {tweet.tweet_id}: updated_at is older than created_at")
                    if auto_fix:
                        self.tweet_repo.update(tweet.tweet_id, {'updated_at': tweet.created_at})
                        fixes += 1
            
            # Check for missing timestamps
            if not tweet.created_at:
                issues.append(f"Tweet {tweet.tweet_id}: missing created_at timestamp")
                if auto_fix:
                    self.tweet_repo.update(tweet.tweet_id, {'created_at': datetime.now(timezone.utc)})
                    fixes += 1
            
            if not tweet.updated_at:
                issues.append(f"Tweet {tweet.tweet_id}: missing updated_at timestamp")
                if auto_fix:
                    self.tweet_repo.update(tweet.tweet_id, {'updated_at': datetime.now(timezone.utc)})
                    fixes += 1
        
        duration = (datetime.now() - start_time).total_seconds()
        
        return ValidationResult(
            is_valid=len(issues) == 0,
            issue_count=len(issues),
            issues=issues,
            fixes_applied=fixes,
            validation_time=duration,
            metadata={"tweets_checked": len(tweets)}
        )
    
    async def _validate_cross_references(self, auto_fix: bool) -> ValidationResult:
        """Validate cross-references between different data stores."""
        start_time = datetime.now()
        issues = []
        fixes = 0
        
        # Get all data (with graceful fallback)
        if hasattr(self.tweet_repo, 'get_all'):
            tweets = {tweet.tweet_id: tweet for tweet in self.tweet_repo.get_all()}
        else:
            issues.append("TweetCacheRepository missing get_all method")
            tweets = {}
            
        if hasattr(self.queue_repo, 'get_all'):
            queue_entries = {entry.tweet_id: entry for entry in self.queue_repo.get_all()}
        else:
            issues.append("TweetProcessingQueueRepository missing get_all method")
            queue_entries = {}
            
        if hasattr(self.category_repo, 'get_all'):
            categories = self.category_repo.get_all()
        else:
            issues.append("CategoryRepository missing get_all method")
            categories = []
        
        # Validate tweet-queue cross-references
        for tweet_id, tweet in tweets.items():
            queue_entry = queue_entries.get(tweet_id)
            
            # Check processing status consistency
            is_fully_processed = all([
                tweet.cache_complete, tweet.media_processed,
                tweet.categories_processed, tweet.kb_item_created
            ])
            
            if is_fully_processed and (not queue_entry or queue_entry.status != "processed"):
                issues.append(f"Tweet {tweet_id}: fully processed but queue status mismatch")
                if auto_fix:
                    if queue_entry:
                        self.queue_repo.update_status(tweet_id, "processed")
                    else:
                        self.queue_repo.create({
                            "tweet_id": tweet_id,
                            "status": "processed",
                            "processed_at": datetime.now(timezone.utc)
                        })
                    fixes += 1
        
        # Validate category usage vs category hierarchy
        category_usage = {}
        for tweet in tweets.values():
            if tweet.main_category and tweet.sub_category:
                key = f"{tweet.main_category}/{tweet.sub_category}"
                category_usage[key] = category_usage.get(key, 0) + 1
        
        category_hierarchy = {f"{cat.main_category}/{cat.sub_category}": cat.item_count 
                            for cat in categories}
        
        for category_key, actual_count in category_usage.items():
            expected_count = category_hierarchy.get(category_key, 0)
            if actual_count != expected_count:
                issues.append(f"Category {category_key}: usage count mismatch (actual: {actual_count}, recorded: {expected_count})")
                if auto_fix:
                    # Update category item count
                    main_cat, sub_cat = category_key.split('/', 1)
                    self.category_repo.update_item_count(main_cat, sub_cat, actual_count)
                    fixes += 1
        
        duration = (datetime.now() - start_time).total_seconds()
        
        return ValidationResult(
            is_valid=len(issues) == 0,
            issue_count=len(issues),
            issues=issues,
            fixes_applied=fixes,
            validation_time=duration,
            metadata={
                "tweets_checked": len(tweets),
                "categories_checked": len(categories),
                "cross_references_validated": len(category_usage)
            }
        )
    
    def generate_health_report(self, validation_summary: ValidationSummary) -> Dict[str, Any]:
        """Generate a comprehensive health report based on validation results."""
        
        # Calculate health score (0-100)
        if validation_summary.total_validations == 0:
            health_score = 0
        else:
            base_score = (validation_summary.passed_validations / validation_summary.total_validations) * 100
            
            # Reduce score based on issue severity
            issue_penalty = min(validation_summary.total_issues * 2, 50)  # Max 50% penalty
            health_score = max(0, base_score - issue_penalty)
        
        # Determine health status
        if health_score >= 95:
            health_status = "EXCELLENT"
        elif health_score >= 85:
            health_status = "GOOD"
        elif health_score >= 70:
            health_status = "FAIR"
        elif health_score >= 50:
            health_status = "POOR"
        else:
            health_status = "CRITICAL"
        
        # Generate recommendations
        recommendations = []
        
        if validation_summary.total_issues > 0:
            recommendations.append("Run validation with auto_fix=True to resolve detected issues")
        
        if validation_summary.failed_validations > 0:
            failed_checks = [name for name, result in validation_summary.results.items() 
                           if not result.is_valid]
            recommendations.append(f"Focus on fixing: {', '.join(failed_checks)}")
        
        if health_score < 85:
            recommendations.append("Consider running data integrity checks more frequently")
        
        return {
            "health_score": round(health_score, 1),
            "health_status": health_status,
            "summary": {
                "total_validations": validation_summary.total_validations,
                "passed": validation_summary.passed_validations,
                "failed": validation_summary.failed_validations,
                "issues_found": validation_summary.total_issues,
                "fixes_applied": validation_summary.total_fixes,
                "duration": validation_summary.validation_duration
            },
            "critical_issues": [
                issue for result in validation_summary.results.values()
                for issue in result.issues
                if "missing" in issue.lower() or "failed" in issue.lower()
            ],
            "recommendations": recommendations,
            "detailed_results": {
                name: {
                    "status": "PASS" if result.is_valid else "FAIL",
                    "issues": result.issue_count,
                    "fixes": result.fixes_applied,
                    "duration": result.validation_time
                }
                for name, result in validation_summary.results.items()
            }
        } 