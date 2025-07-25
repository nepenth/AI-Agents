"""
JSON to Database Migration Engine

This module provides comprehensive migration functionality to transfer data
from JSON files to the database-backed system while ensuring data integrity,
providing backup capabilities, and supporting rollback operations.
"""

import json
import logging
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, timezone, timedelta
from pathlib import Path
import shutil
import hashlib
from dataclasses import dataclass
from enum import Enum

from .config import Config
from .database import get_db_session_context
from .models import (
    TweetCache, TweetProcessingQueue, CategoryHierarchy, 
    ProcessingStatistics, RuntimeStatistics, db
)
from .repositories import (
    TweetCacheRepository, TweetProcessingQueueRepository,
    CategoryRepository, ProcessingStatisticsRepository, RuntimeStatisticsRepository
)

logger = logging.getLogger(__name__)


class MigrationStatus(Enum):
    """Migration status enumeration."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"


@dataclass
class MigrationResult:
    """Result of a single migration operation."""
    operation: str
    status: MigrationStatus
    items_processed: int
    items_failed: int
    duration_seconds: float
    error_message: Optional[str] = None
    warnings: List[str] = None
    backup_path: Optional[str] = None
    
    def __post_init__(self):
        if self.warnings is None:
            self.warnings = []


@dataclass
class ValidationResult:
    """Result of data validation operation."""
    is_valid: bool
    total_items: int
    valid_items: int
    invalid_items: int
    errors: List[str]
    warnings: List[str]
    
    def __post_init__(self):
        if self.errors is None:
            self.errors = []
        if self.warnings is None:
            self.warnings = []


@dataclass
class MigrationReport:
    """Comprehensive migration report."""
    migration_id: str
    start_time: datetime
    end_time: Optional[datetime]
    status: MigrationStatus
    results: List[MigrationResult]
    validation_results: List[ValidationResult]
    total_items_migrated: int
    total_errors: int
    backup_location: Optional[str] = None
    
    def __post_init__(self):
        if self.results is None:
            self.results = []
        if self.validation_results is None:
            self.validation_results = []


class BackupManager:
    """Manages backup creation and restoration for migration operations."""
    
    def __init__(self, config: Config):
        self.config = config
        self.backup_base_dir = Path(config.project_root) / "backups" / "migration"
        self.backup_base_dir.mkdir(parents=True, exist_ok=True)
    
    def create_pre_migration_backup(self, migration_id: str) -> str:
        """
        Create comprehensive backup before migration.
        
        Args:
            migration_id: Unique migration identifier
            
        Returns:
            Path to created backup directory
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_dir = self.backup_base_dir / f"pre_migration_{migration_id}_{timestamp}"
        backup_dir.mkdir(exist_ok=True)
        
        try:
            # Backup JSON files
            data_dir = Path(self.config.project_root) / "data"
            json_files = [
                "tweet_cache.json",
                "processed_tweets.json", 
                "unprocessed_tweets.json",
                "categories.json",
                "processing_stats.json",
                "latest_run_stats.json"
            ]
            
            json_backup_dir = backup_dir / "json_files"
            json_backup_dir.mkdir(exist_ok=True)
            
            for filename in json_files:
                source_path = data_dir / filename
                if source_path.exists():
                    dest_path = json_backup_dir / filename
                    shutil.copy2(source_path, dest_path)
                    logger.info(f"Backed up {filename} to {dest_path}")
            
            # Create database backup (if exists)
            self._create_database_backup(backup_dir)
            
            # Create manifest
            self._create_backup_manifest(backup_dir, migration_id)
            
            logger.info(f"Created pre-migration backup at {backup_dir}")
            return str(backup_dir)
            
        except Exception as e:
            logger.error(f"Failed to create backup: {e}")
            # Clean up partial backup
            if backup_dir.exists():
                shutil.rmtree(backup_dir)
            raise
    
    def _create_database_backup(self, backup_dir: Path):
        """Create database backup using pg_dump."""
        try:
            import subprocess
            
            # Get database configuration
            db_config = self.config.get_database_config()
            
            dump_file = backup_dir / "database_backup.sql"
            
            cmd = [
                "pg_dump",
                f"--host={db_config.get('host', 'localhost')}",
                f"--port={db_config.get('port', 5432)}",
                f"--username={db_config.get('username', 'postgres')}",
                f"--dbname={db_config.get('database', 'knowledge_base')}",
                f"--file={dump_file}",
                "--verbose",
                "--no-password"
            ]
            
            # Set PGPASSWORD environment variable if password exists
            env = {}
            if 'password' in db_config:
                env['PGPASSWORD'] = db_config['password']
            
            result = subprocess.run(cmd, env=env, capture_output=True, text=True)
            
            if result.returncode == 0:
                logger.info(f"Database backup created at {dump_file}")
            else:
                logger.warning(f"Database backup failed: {result.stderr}")
                
        except Exception as e:
            logger.warning(f"Could not create database backup: {e}")
    
    def _create_backup_manifest(self, backup_dir: Path, migration_id: str):
        """Create backup manifest with metadata."""
        manifest = {
            "migration_id": migration_id,
            "backup_created": datetime.now(timezone.utc).isoformat(),
            "files": [],
            "checksums": {}
        }
        
        # Add file information and checksums
        for file_path in backup_dir.rglob("*"):
            if file_path.is_file() and file_path.name != "manifest.json":
                relative_path = file_path.relative_to(backup_dir)
                manifest["files"].append(str(relative_path))
                
                # Calculate checksum
                with open(file_path, 'rb') as f:
                    content = f.read()
                    checksum = hashlib.sha256(content).hexdigest()
                    manifest["checksums"][str(relative_path)] = checksum
        
        manifest_path = backup_dir / "manifest.json"
        with open(manifest_path, 'w') as f:
            json.dump(manifest, f, indent=2)
    
    def validate_backup(self, backup_path: str) -> bool:
        """
        Validate backup integrity using checksums.
        
        Args:
            backup_path: Path to backup directory
            
        Returns:
            True if backup is valid
        """
        try:
            backup_dir = Path(backup_path)
            manifest_path = backup_dir / "manifest.json"
            
            if not manifest_path.exists():
                logger.error("Backup manifest not found")
                return False
            
            with open(manifest_path, 'r') as f:
                manifest = json.load(f)
            
            # Validate each file
            for filename, expected_checksum in manifest["checksums"].items():
                file_path = backup_dir / filename
                
                if not file_path.exists():
                    logger.error(f"Backup file missing: {filename}")
                    return False
                
                with open(file_path, 'rb') as f:
                    content = f.read()
                    actual_checksum = hashlib.sha256(content).hexdigest()
                
                if actual_checksum != expected_checksum:
                    logger.error(f"Checksum mismatch for {filename}")
                    return False
            
            logger.info(f"Backup validation successful: {backup_path}")
            return True
            
        except Exception as e:
            logger.error(f"Backup validation failed: {e}")
            return False


class DataValidator:
    """Validates data integrity during migration."""
    
    def validate_tweet_cache_data(self, tweet_data: Dict[str, Any]) -> ValidationResult:
        """
        Validate tweet cache data structure.
        
        Args:
            tweet_data: Dictionary of tweet cache data
            
        Returns:
            ValidationResult with validation details
        """
        errors = []
        warnings = []
        valid_items = 0
        invalid_items = 0
        
        total_items = len(tweet_data)
        
        for tweet_id, tweet_info in tweet_data.items():
            try:
                # Validate required fields
                if not isinstance(tweet_info, dict):
                    errors.append(f"Tweet {tweet_id}: Data is not a dictionary")
                    invalid_items += 1
                    continue
                
                # Check essential fields
                required_fields = ["tweet_id", "bookmarked_tweet_id"]
                for field in required_fields:
                    if field not in tweet_info:
                        errors.append(f"Tweet {tweet_id}: Missing required field '{field}'")
                        invalid_items += 1
                        continue
                
                # Validate data types
                if "is_thread" in tweet_info and not isinstance(tweet_info["is_thread"], bool):
                    warnings.append(f"Tweet {tweet_id}: 'is_thread' should be boolean")
                
                if "thread_tweets" in tweet_info and not isinstance(tweet_info["thread_tweets"], list):
                    warnings.append(f"Tweet {tweet_id}: 'thread_tweets' should be list")
                
                # Validate processing flags
                boolean_flags = [
                    "urls_expanded", "media_processed", "cache_complete",
                    "categories_processed", "kb_item_created"
                ]
                for flag in boolean_flags:
                    if flag in tweet_info and not isinstance(tweet_info[flag], bool):
                        warnings.append(f"Tweet {tweet_id}: '{flag}' should be boolean")
                
                valid_items += 1
                
            except Exception as e:
                errors.append(f"Tweet {tweet_id}: Validation error - {e}")
                invalid_items += 1
        
        return ValidationResult(
            is_valid=(invalid_items == 0),
            total_items=total_items,
            valid_items=valid_items,
            invalid_items=invalid_items,
            errors=errors,
            warnings=warnings
        )
    
    def validate_categories_data(self, categories_data: Dict[str, List[str]]) -> ValidationResult:
        """
        Validate categories data structure.
        
        Args:
            categories_data: Dictionary of categories data
            
        Returns:
            ValidationResult with validation details
        """
        errors = []
        warnings = []
        valid_items = 0
        invalid_items = 0
        
        total_items = sum(len(subcats) for subcats in categories_data.values())
        
        for main_category, sub_categories in categories_data.items():
            try:
                if not isinstance(sub_categories, list):
                    errors.append(f"Main category '{main_category}': Sub-categories should be a list")
                    invalid_items += len(sub_categories) if hasattr(sub_categories, '__len__') else 1
                    continue
                
                for sub_category in sub_categories:
                    if not isinstance(sub_category, str):
                        errors.append(f"Category '{main_category}/{sub_category}': Sub-category should be string")
                        invalid_items += 1
                    else:
                        valid_items += 1
                        
            except Exception as e:
                errors.append(f"Main category '{main_category}': Validation error - {e}")
                invalid_items += len(sub_categories) if hasattr(sub_categories, '__len__') else 1
        
        return ValidationResult(
            is_valid=(invalid_items == 0),
            total_items=total_items,
            valid_items=valid_items,
            invalid_items=invalid_items,
            errors=errors,
            warnings=warnings
        )


class JsonToDbMigrator:
    """
    Main migration orchestrator for JSON to Database migration.
    
    Handles the complete migration process including backup creation,
    data validation, transformation, and rollback capabilities.
    """
    
    def __init__(self, config: Config):
        self.config = config
        self.data_dir = Path(config.project_root) / "data"
        self.backup_manager = BackupManager(config)
        self.validator = DataValidator()
        
        # Initialize repositories
        self.tweet_repo = TweetCacheRepository()
        self.queue_repo = TweetProcessingQueueRepository()
        self.category_repo = CategoryRepository()
        self.processing_stats_repo = ProcessingStatisticsRepository()
        self.runtime_stats_repo = RuntimeStatisticsRepository()
    
    def migrate_all_data(self, migration_id: Optional[str] = None) -> MigrationReport:
        """
        Migrate all JSON data to database.
        
        Args:
            migration_id: Optional migration identifier
            
        Returns:
            Comprehensive migration report
        """
        if migration_id is None:
            migration_id = f"migration_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        report = MigrationReport(
            migration_id=migration_id,
            start_time=datetime.now(timezone.utc),
            end_time=None,
            status=MigrationStatus.IN_PROGRESS,
            results=[],
            validation_results=[],
            total_items_migrated=0,
            total_errors=0
        )
        
        try:
            logger.info(f"Starting migration {migration_id}")
            
            # Create pre-migration backup
            backup_path = self.backup_manager.create_pre_migration_backup(migration_id)
            report.backup_location = backup_path
            
            # Validate backup
            if not self.backup_manager.validate_backup(backup_path):
                raise Exception("Backup validation failed")
            
            # Migrate each data type
            migration_steps = [
                ("categories", self.migrate_categories),
                ("tweet_cache", self.migrate_tweet_cache),
                ("processing_queues", self.migrate_processing_queues),
                ("processing_statistics", self.migrate_processing_statistics),
                ("runtime_statistics", self.migrate_runtime_statistics)
            ]
            
            for step_name, migration_func in migration_steps:
                try:
                    logger.info(f"Starting migration step: {step_name}")
                    result = migration_func()
                    report.results.append(result)
                    
                    if result.status == MigrationStatus.FAILED:
                        logger.error(f"Migration step {step_name} failed: {result.error_message}")
                        report.total_errors += result.items_failed
                    else:
                        report.total_items_migrated += result.items_processed
                        
                except Exception as e:
                    error_result = MigrationResult(
                        operation=step_name,
                        status=MigrationStatus.FAILED,
                        items_processed=0,
                        items_failed=0,
                        duration_seconds=0,
                        error_message=str(e)
                    )
                    report.results.append(error_result)
                    report.total_errors += 1
                    logger.error(f"Migration step {step_name} failed with exception: {e}")
            
            # Validate migrated data
            validation_result = self.validate_migration()
            report.validation_results.append(validation_result)
            
            # Determine final status
            if report.total_errors == 0 and validation_result.is_valid:
                report.status = MigrationStatus.COMPLETED
                logger.info(f"Migration {migration_id} completed successfully")
            else:
                report.status = MigrationStatus.FAILED
                logger.error(f"Migration {migration_id} failed with {report.total_errors} errors")
            
        except Exception as e:
            report.status = MigrationStatus.FAILED
            logger.error(f"Migration {migration_id} failed: {e}")
            
        finally:
            report.end_time = datetime.now(timezone.utc)
            
        return report
    
    def migrate_tweet_cache(self) -> MigrationResult:
        """
        Migrate tweet_cache.json to TweetCache table.
        
        Returns:
            MigrationResult with operation details
        """
        start_time = datetime.now()
        
        try:
            # Load tweet cache data
            tweet_cache_path = self.data_dir / "tweet_cache.json"
            if not tweet_cache_path.exists():
                return MigrationResult(
                    operation="tweet_cache",
                    status=MigrationStatus.COMPLETED,
                    items_processed=0,
                    items_failed=0,
                    duration_seconds=0,
                    warnings=["tweet_cache.json not found, skipping migration"]
                )
            
            with open(tweet_cache_path, 'r') as f:
                tweet_data = json.load(f)
            
            # Validate data
            validation_result = self.validator.validate_tweet_cache_data(tweet_data)
            
            items_processed = 0
            items_failed = 0
            warnings = validation_result.warnings.copy()
            
            # Migrate each tweet
            for tweet_id, tweet_info in tweet_data.items():
                try:
                    # Transform data to database format
                    db_data = self._transform_tweet_cache_data(tweet_id, tweet_info)
                    
                    # Save to database
                    self.tweet_repo.create(db_data)
                    items_processed += 1
                    
                except Exception as e:
                    logger.error(f"Failed to migrate tweet {tweet_id}: {e}")
                    items_failed += 1
                    warnings.append(f"Failed to migrate tweet {tweet_id}: {e}")
            
            duration = (datetime.now() - start_time).total_seconds()
            
            status = MigrationStatus.COMPLETED if items_failed == 0 else MigrationStatus.FAILED
            
            return MigrationResult(
                operation="tweet_cache",
                status=status,
                items_processed=items_processed,
                items_failed=items_failed,
                duration_seconds=duration,
                warnings=warnings
            )
            
        except Exception as e:
            duration = (datetime.now() - start_time).total_seconds()
            return MigrationResult(
                operation="tweet_cache",
                status=MigrationStatus.FAILED,
                items_processed=0,
                items_failed=0,
                duration_seconds=duration,
                error_message=str(e)
            )
    
    def _transform_tweet_cache_data(self, tweet_id: str, tweet_info: Dict[str, Any]) -> Dict[str, Any]:
        """Transform tweet cache data to database format."""
        
        # Extract basic fields
        db_data = {
            "tweet_id": tweet_id,
            "bookmarked_tweet_id": tweet_info.get("bookmarked_tweet_id", tweet_id),
            "is_thread": tweet_info.get("is_thread", False),
            "thread_tweets": tweet_info.get("thread_tweets", []),
            "all_downloaded_media_for_thread": tweet_info.get("all_downloaded_media_for_thread", []),
        }
        
        # Processing flags
        db_data.update({
            "urls_expanded": tweet_info.get("urls_expanded", False),
            "media_processed": tweet_info.get("media_processed", False),
            "cache_complete": tweet_info.get("cache_complete", False),
            "categories_processed": tweet_info.get("categories_processed", False),
            "kb_item_created": tweet_info.get("kb_item_created", False),
        })
        
        # Categorization data
        db_data.update({
            "main_category": tweet_info.get("main_category"),
            "sub_category": tweet_info.get("sub_category"),
            "item_name_suggestion": tweet_info.get("item_name_suggestion"),
            "categories": tweet_info.get("categories", {}),
        })
        
        # Knowledge base integration
        db_data.update({
            "kb_item_path": tweet_info.get("kb_item_path"),
            "kb_media_paths": tweet_info.get("kb_media_paths", []),
        })
        
        # Content and metadata
        db_data.update({
            "raw_json_content": tweet_info.get("raw_json_content"),
            "display_title": tweet_info.get("display_title"),
            "source": tweet_info.get("source", "unknown"),
            "image_descriptions": tweet_info.get("image_descriptions", []),
        })
        
        # Processing metadata
        db_data.update({
            "recategorization_attempts": tweet_info.get("recategorization_attempts", 0),
            "db_synced": tweet_info.get("db_synced", False),
        })
        
        # Extract full text for search
        full_text_parts = []
        if "thread_tweets" in tweet_info:
            for thread_tweet in tweet_info["thread_tweets"]:
                if "full_text" in thread_tweet:
                    full_text_parts.append(thread_tweet["full_text"])
        
        db_data["full_text"] = " ".join(full_text_parts)
        
        return db_data
    
    def migrate_processing_queues(self) -> MigrationResult:
        """
        Migrate processed_tweets.json and unprocessed_tweets.json to TweetProcessingQueue table.
        
        Returns:
            MigrationResult with operation details
        """
        start_time = datetime.now()
        
        try:
            items_processed = 0
            items_failed = 0
            warnings = []
            
            # Migrate processed tweets
            processed_path = self.data_dir / "processed_tweets.json"
            if processed_path.exists():
                with open(processed_path, 'r') as f:
                    processed_tweets = json.load(f)
                
                for tweet_id, processed_time in processed_tweets.items():
                    try:
                        queue_data = {
                            "tweet_id": tweet_id,
                            "status": "processed",
                            "processed_at": datetime.fromisoformat(processed_time.replace('Z', '+00:00'))
                        }
                        self.queue_repo.create(queue_data)
                        items_processed += 1
                    except Exception as e:
                        logger.error(f"Failed to migrate processed tweet {tweet_id}: {e}")
                        items_failed += 1
                        warnings.append(f"Failed to migrate processed tweet {tweet_id}: {e}")
            
            # Migrate unprocessed tweets
            unprocessed_path = self.data_dir / "unprocessed_tweets.json"
            if unprocessed_path.exists():
                with open(unprocessed_path, 'r') as f:
                    unprocessed_tweets = json.load(f)
                
                for tweet_id in unprocessed_tweets:
                    try:
                        queue_data = {
                            "tweet_id": tweet_id,
                            "status": "unprocessed"
                        }
                        self.queue_repo.create(queue_data)
                        items_processed += 1
                    except Exception as e:
                        logger.error(f"Failed to migrate unprocessed tweet {tweet_id}: {e}")
                        items_failed += 1
                        warnings.append(f"Failed to migrate unprocessed tweet {tweet_id}: {e}")
            
            duration = (datetime.now() - start_time).total_seconds()
            
            status = MigrationStatus.COMPLETED if items_failed == 0 else MigrationStatus.FAILED
            
            return MigrationResult(
                operation="processing_queues",
                status=status,
                items_processed=items_processed,
                items_failed=items_failed,
                duration_seconds=duration,
                warnings=warnings
            )
            
        except Exception as e:
            duration = (datetime.now() - start_time).total_seconds()
            return MigrationResult(
                operation="processing_queues",
                status=MigrationStatus.FAILED,
                items_processed=0,
                items_failed=0,
                duration_seconds=duration,
                error_message=str(e)
            )
    
    def migrate_categories(self) -> MigrationResult:
        """
        Migrate categories.json to CategoryHierarchy table.
        
        Returns:
            MigrationResult with operation details
        """
        start_time = datetime.now()
        
        try:
            # Load categories data
            categories_path = self.data_dir / "categories.json"
            if not categories_path.exists():
                return MigrationResult(
                    operation="categories",
                    status=MigrationStatus.COMPLETED,
                    items_processed=0,
                    items_failed=0,
                    duration_seconds=0,
                    warnings=["categories.json not found, skipping migration"]
                )
            
            with open(categories_path, 'r') as f:
                categories_data = json.load(f)
            
            # Validate data
            validation_result = self.validator.validate_categories_data(categories_data)
            
            items_processed = 0
            items_failed = 0
            warnings = validation_result.warnings.copy()
            sort_order = 0
            
            # Migrate each category
            for main_category, sub_categories in categories_data.items():
                for sub_category in sub_categories:
                    try:
                        category_data = {
                            "main_category": main_category,
                            "sub_category": sub_category,
                            "display_name": f"{main_category} - {sub_category}",
                            "sort_order": sort_order,
                            "is_active": True,
                            "item_count": 0  # Will be updated later
                        }
                        
                        self.category_repo.create(category_data)
                        items_processed += 1
                        sort_order += 1
                        
                    except Exception as e:
                        logger.error(f"Failed to migrate category {main_category}/{sub_category}: {e}")
                        items_failed += 1
                        warnings.append(f"Failed to migrate category {main_category}/{sub_category}: {e}")
            
            duration = (datetime.now() - start_time).total_seconds()
            
            status = MigrationStatus.COMPLETED if items_failed == 0 else MigrationStatus.FAILED
            
            return MigrationResult(
                operation="categories",
                status=status,
                items_processed=items_processed,
                items_failed=items_failed,
                duration_seconds=duration,
                warnings=warnings
            )
            
        except Exception as e:
            duration = (datetime.now() - start_time).total_seconds()
            return MigrationResult(
                operation="categories",
                status=MigrationStatus.FAILED,
                items_processed=0,
                items_failed=0,
                duration_seconds=duration,
                error_message=str(e)
            )
    
    def migrate_processing_statistics(self) -> MigrationResult:
        """
        Migrate processing_stats.json to ProcessingStatistics table.
        
        Returns:
            MigrationResult with operation details
        """
        start_time = datetime.now()
        
        try:
            # Load processing statistics data
            stats_path = self.data_dir / "processing_stats.json"
            if not stats_path.exists():
                return MigrationResult(
                    operation="processing_statistics",
                    status=MigrationStatus.COMPLETED,
                    items_processed=0,
                    items_failed=0,
                    duration_seconds=0,
                    warnings=["processing_stats.json not found, skipping migration"]
                )
            
            with open(stats_path, 'r') as f:
                stats_data = json.load(f)
            
            items_processed = 0
            items_failed = 0
            warnings = []
            
            # Migrate phase statistics
            if "phases" in stats_data:
                for phase_name, phase_stats in stats_data["phases"].items():
                    try:
                        # Create entries for each metric
                        metrics = [
                            ("total_items_processed", phase_stats.get("total_items_processed", 0), "items"),
                            ("total_duration_seconds", phase_stats.get("total_duration_seconds", 0), "seconds"),
                            ("avg_time_per_item_seconds", phase_stats.get("avg_time_per_item_seconds", 0), "seconds")
                        ]
                        
                        for metric_name, metric_value, metric_unit in metrics:
                            stats_entry = {
                                "phase_name": phase_name,
                                "metric_name": metric_name,
                                "metric_value": metric_value,
                                "metric_unit": metric_unit,
                                "total_items_processed": phase_stats.get("total_items_processed", 0),
                                "total_duration_seconds": phase_stats.get("total_duration_seconds", 0),
                                "avg_time_per_item_seconds": phase_stats.get("avg_time_per_item_seconds", 0),
                                "run_id": "historical_migration"
                            }
                            
                            self.processing_stats_repo.create(stats_entry)
                            items_processed += 1
                            
                    except Exception as e:
                        logger.error(f"Failed to migrate processing stats for {phase_name}: {e}")
                        items_failed += 1
                        warnings.append(f"Failed to migrate processing stats for {phase_name}: {e}")
            
            duration = (datetime.now() - start_time).total_seconds()
            
            status = MigrationStatus.COMPLETED if items_failed == 0 else MigrationStatus.FAILED
            
            return MigrationResult(
                operation="processing_statistics",
                status=status,
                items_processed=items_processed,
                items_failed=items_failed,
                duration_seconds=duration,
                warnings=warnings
            )
            
        except Exception as e:
            duration = (datetime.now() - start_time).total_seconds()
            return MigrationResult(
                operation="processing_statistics",
                status=MigrationStatus.FAILED,
                items_processed=0,
                items_failed=0,
                duration_seconds=duration,
                error_message=str(e)
            )
    
    def migrate_runtime_statistics(self) -> MigrationResult:
        """
        Migrate latest_run_stats.json to RuntimeStatistics table.
        
        Returns:
            MigrationResult with operation details
        """
        start_time = datetime.now()
        
        try:
            # Load runtime statistics data
            stats_path = self.data_dir / "latest_run_stats.json"
            if not stats_path.exists():
                return MigrationResult(
                    operation="runtime_statistics",
                    status=MigrationStatus.COMPLETED,
                    items_processed=0,
                    items_failed=0,
                    duration_seconds=0,
                    warnings=["latest_run_stats.json not found, skipping migration"]
                )
            
            with open(stats_path, 'r') as f:
                stats_data = json.load(f)
            
            # Transform data
            runtime_data = {
                "run_id": "historical_migration_run",
                "processed_count": stats_data.get("processed_count", 0),
                "success_count": stats_data.get("success_count", 0),
                "error_count": stats_data.get("error_count", 0),
                "skipped_count": stats_data.get("skipped_count", 0),
                "media_processed": stats_data.get("media_processed", 0),
                "cache_hits": stats_data.get("cache_hits", 0),
                "cache_misses": stats_data.get("cache_misses", 0),
                "network_errors": stats_data.get("network_errors", 0),
                "retry_count": stats_data.get("retry_count", 0)
            }
            
            # Parse start time and duration
            if "start_time" in stats_data:
                try:
                    runtime_data["start_time"] = datetime.fromisoformat(stats_data["start_time"])
                except:
                    logger.warning("Could not parse start_time from runtime stats")
            
            if "duration" in stats_data:
                try:
                    # Parse duration string like "0:00:00.010229"
                    duration_str = stats_data["duration"]
                    time_parts = duration_str.split(":")
                    if len(time_parts) == 3:
                        hours = int(time_parts[0])
                        minutes = int(time_parts[1])
                        seconds = float(time_parts[2])
                        runtime_data["duration"] = timedelta(hours=hours, minutes=minutes, seconds=seconds)
                        
                        if runtime_data.get("start_time"):
                            runtime_data["end_time"] = runtime_data["start_time"] + runtime_data["duration"]
                except:
                    logger.warning("Could not parse duration from runtime stats")
            
            # Create runtime statistics entry
            self.runtime_stats_repo.create(runtime_data)
            
            duration = (datetime.now() - start_time).total_seconds()
            
            return MigrationResult(
                operation="runtime_statistics",
                status=MigrationStatus.COMPLETED,
                items_processed=1,
                items_failed=0,
                duration_seconds=duration
            )
            
        except Exception as e:
            duration = (datetime.now() - start_time).total_seconds()
            return MigrationResult(
                operation="runtime_statistics",
                status=MigrationStatus.FAILED,
                items_processed=0,
                items_failed=1,
                duration_seconds=duration,
                error_message=str(e)
            )
    
    def validate_migration(self) -> ValidationResult:
        """
        Validate migrated data integrity.
        
        Returns:
            ValidationResult with comprehensive validation details
        """
        errors = []
        warnings = []
        
        try:
            with get_db_session_context() as session:
                # Count migrated data
                tweet_count = session.query(TweetCache).count()
                queue_count = session.query(TweetProcessingQueue).count()
                category_count = session.query(CategoryHierarchy).count()
                stats_count = session.query(ProcessingStatistics).count()
                runtime_count = session.query(RuntimeStatistics).count()
                
                # Check for basic data presence
                if tweet_count == 0:
                    warnings.append("No tweets found in database after migration")
                
                if category_count == 0:
                    warnings.append("No categories found in database after migration")
                
                # Validate foreign key relationships
                orphaned_queues = session.query(TweetProcessingQueue).outerjoin(
                    TweetCache, TweetProcessingQueue.tweet_id == TweetCache.tweet_id
                ).filter(TweetCache.tweet_id.is_(None)).count()
                
                if orphaned_queues > 0:
                    errors.append(f"Found {orphaned_queues} processing queue entries with no corresponding tweet")
                
                # Check for data consistency
                tweets_with_categories = session.query(TweetCache).filter(
                    TweetCache.main_category.isnot(None)
                ).count()
                
                if tweets_with_categories > 0 and category_count == 0:
                    warnings.append("Tweets have categories but no category hierarchy exists")
                
                logger.info(f"Migration validation: {tweet_count} tweets, {queue_count} queue entries, "
                          f"{category_count} categories, {stats_count} stats, {runtime_count} runtime stats")
                
                return ValidationResult(
                    is_valid=(len(errors) == 0),
                    total_items=tweet_count + queue_count + category_count + stats_count + runtime_count,
                    valid_items=tweet_count + queue_count + category_count + stats_count + runtime_count - len(errors),
                    invalid_items=len(errors),
                    errors=errors,
                    warnings=warnings
                )
                
        except Exception as e:
            errors.append(f"Validation failed with exception: {e}")
            return ValidationResult(
                is_valid=False,
                total_items=0,
                valid_items=0,
                invalid_items=1,
                errors=errors,
                warnings=warnings
            )
    
    def rollback_migration(self, backup_path: str) -> bool:
        """
        Rollback migration using backup.
        
        Args:
            backup_path: Path to backup directory
            
        Returns:
            True if rollback successful
        """
        try:
            logger.info(f"Starting migration rollback from {backup_path}")
            
            # Validate backup first
            if not self.backup_manager.validate_backup(backup_path):
                logger.error("Backup validation failed, cannot rollback")
                return False
            
            backup_dir = Path(backup_path)
            
            # Clear database tables
            with get_db_session_context() as session:
                # Delete in reverse dependency order
                session.query(TweetProcessingQueue).delete()
                session.query(ProcessingStatistics).delete()
                session.query(RuntimeStatistics).delete()
                session.query(CategoryHierarchy).delete()
                session.query(TweetCache).delete()
                session.commit()
                logger.info("Cleared database tables for rollback")
            
            # Restore JSON files
            json_backup_dir = backup_dir / "json_files"
            if json_backup_dir.exists():
                for json_file in json_backup_dir.iterdir():
                    if json_file.is_file():
                        dest_path = self.data_dir / json_file.name
                        shutil.copy2(json_file, dest_path)
                        logger.info(f"Restored {json_file.name}")
            
            logger.info("Migration rollback completed successfully")
            return True
            
        except Exception as e:
            logger.error(f"Migration rollback failed: {e}")
            return False 