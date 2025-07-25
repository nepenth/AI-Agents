"""
Comprehensive Backup and Recovery System

This module provides automated backup creation, validation, and recovery capabilities
for the Knowledge Base Agent's database and file systems.
"""

import os
import shutil
import gzip
import hashlib
import json
import logging
import subprocess
import threading
import time
from datetime import datetime, timedelta
from dataclasses import dataclass
from typing import Dict, List, Optional, Union, Any
from pathlib import Path
from sqlalchemy.exc import SQLAlchemyError

from .config import Config
from .database import get_db_session_context


@dataclass
class BackupMetadata:
    """Metadata for backup tracking and management."""
    backup_id: str
    backup_type: str  # 'daily', 'weekly', 'manual', 'pre_migration'
    created_at: datetime
    size_bytes: int
    checksum: str
    description: str
    retention_date: datetime
    components: List[str]  # ['database', 'json_files', 'media', 'logs']
    validation_status: str  # 'pending', 'valid', 'invalid', 'failed'
    restore_tested: bool
    file_paths: Dict[str, str]  # component -> file_path mapping


@dataclass
class BackupValidationResult:
    """Result of backup validation process."""
    is_valid: bool
    checksum_verified: bool
    content_verified: bool
    restore_tested: bool
    errors: List[str]
    warnings: List[str]
    validation_time: datetime


@dataclass
class RestoreResult:
    """Result of backup restoration process."""
    success: bool
    backup_id: str
    components_restored: List[str]
    errors: List[str]
    warnings: List[str]
    restore_time: datetime
    rollback_available: bool


class BackupManager:
    """
    Comprehensive backup and recovery manager.
    
    Handles automated backup creation, validation, restoration, and cleanup
    with configurable retention policies and monitoring capabilities.
    """

    def __init__(self, config: Optional[Config] = None):
        self.config = config or Config()
        self.logger = logging.getLogger(__name__)
        
        # Backup configuration
        self.backup_base_dir = Path(self.config.backup_directory) if hasattr(self.config, 'backup_directory') else Path("backups")
        self.retention_policies = {
            'daily': timedelta(days=7),
            'weekly': timedelta(weeks=2),
            'monthly': timedelta(days=90),
            'manual': timedelta(days=30),
            'pre_migration': timedelta(days=90)
        }
        
        # Ensure backup directories exist
        self.backup_base_dir.mkdir(parents=True, exist_ok=True)
        (self.backup_base_dir / "metadata").mkdir(exist_ok=True)
        (self.backup_base_dir / "database").mkdir(exist_ok=True)
        (self.backup_base_dir / "files").mkdir(exist_ok=True)
        (self.backup_base_dir / "logs").mkdir(exist_ok=True)
        
        # Monitoring and alerts
        self.alert_handlers = []
        self.backup_running = False
        self.last_backup_time = None
        self.backup_stats = {
            'total_backups': 0,
            'successful_backups': 0,
            'failed_backups': 0,
            'average_backup_time': 0,
            'total_backup_size': 0
        }

    def create_backup(self, backup_type: str = 'manual', description: str = '', 
                     components: Optional[List[str]] = None) -> str:
        """
        Create a comprehensive backup with specified type and components.
        
        Args:
            backup_type: Type of backup ('daily', 'weekly', 'manual', 'pre_migration')
            description: Human-readable description of the backup
            components: List of components to backup ['database', 'json_files', 'media', 'logs']
        
        Returns:
            backup_id: Unique identifier for the created backup
        """
        if self.backup_running:
            raise RuntimeError("Backup operation already in progress")
        
        backup_id = f"{backup_type}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        start_time = datetime.now()
        
        if components is None:
            components = ['database', 'json_files', 'media', 'logs']
        
        self.logger.info(f"Starting {backup_type} backup: {backup_id}")
        self.backup_running = True
        
        try:
            backup_paths = {}
            total_size = 0
            
            # Create backup directory
            backup_dir = self.backup_base_dir / backup_id
            backup_dir.mkdir(parents=True, exist_ok=True)
            
            # Backup database
            if 'database' in components:
                db_backup_path = self._backup_database(backup_dir, backup_id)
                backup_paths['database'] = str(db_backup_path)
                total_size += db_backup_path.stat().st_size
                self.logger.info(f"Database backup completed: {db_backup_path}")
            
            # Backup JSON files
            if 'json_files' in components:
                json_backup_path = self._backup_json_files(backup_dir, backup_id)
                backup_paths['json_files'] = str(json_backup_path)
                total_size += json_backup_path.stat().st_size
                self.logger.info(f"JSON files backup completed: {json_backup_path}")
            
            # Backup media files
            if 'media' in components:
                media_backup_path = self._backup_media_files(backup_dir, backup_id)
                if media_backup_path and media_backup_path.exists():
                    backup_paths['media'] = str(media_backup_path)
                    total_size += media_backup_path.stat().st_size
                    self.logger.info(f"Media files backup completed: {media_backup_path}")
            
            # Backup logs
            if 'logs' in components:
                logs_backup_path = self._backup_logs(backup_dir, backup_id)
                if logs_backup_path and logs_backup_path.exists():
                    backup_paths['logs'] = str(logs_backup_path)
                    total_size += logs_backup_path.stat().st_size
                    self.logger.info(f"Logs backup completed: {logs_backup_path}")
            
            # Calculate backup checksum
            backup_checksum = self._calculate_backup_checksum(backup_paths)
            
            # Create backup metadata
            metadata = BackupMetadata(
                backup_id=backup_id,
                backup_type=backup_type,
                created_at=start_time,
                size_bytes=total_size,
                checksum=backup_checksum,
                description=description or f"{backup_type.title()} backup",
                retention_date=start_time + self.retention_policies[backup_type],
                components=components,
                validation_status='pending',
                restore_tested=False,
                file_paths=backup_paths
            )
            
            # Save metadata
            self._save_backup_metadata(metadata)
            
            # Update statistics
            self._update_backup_stats(True, datetime.now() - start_time, total_size)
            
            self.logger.info(f"Backup {backup_id} completed successfully. Size: {total_size:,} bytes")
            self.last_backup_time = datetime.now()
            
            # Schedule background validation
            self._schedule_backup_validation(backup_id)
            
            return backup_id
            
        except Exception as e:
            self.logger.error(f"Backup {backup_id} failed: {e}", exc_info=True)
            self._update_backup_stats(False, datetime.now() - start_time, 0)
            self._send_alert(f"Backup failed: {backup_id}", str(e), 'error')
            raise
        
        finally:
            self.backup_running = False

    def validate_backup(self, backup_id: str) -> BackupValidationResult:
        """
        Validate backup integrity and content.
        
        Args:
            backup_id: Unique identifier of the backup to validate
        
        Returns:
            BackupValidationResult: Detailed validation results
        """
        validation_start = datetime.now()
        errors = []
        warnings = []
        
        try:
            # Load backup metadata
            metadata = self._load_backup_metadata(backup_id)
            if not metadata:
                errors.append(f"Backup metadata not found for {backup_id}")
                return BackupValidationResult(
                    is_valid=False, checksum_verified=False, content_verified=False,
                    restore_tested=False, errors=errors, warnings=warnings,
                    validation_time=validation_start
                )
            
            self.logger.info(f"Validating backup: {backup_id}")
            
            # Verify checksum
            current_checksum = self._calculate_backup_checksum(metadata.file_paths)
            checksum_verified = current_checksum == metadata.checksum
            
            if not checksum_verified:
                errors.append(f"Checksum mismatch: expected {metadata.checksum}, got {current_checksum}")
            
            # Verify content integrity
            content_verified = True
            for component, file_path in metadata.file_paths.items():
                if not Path(file_path).exists():
                    errors.append(f"Backup file missing: {file_path}")
                    content_verified = False
                    continue
                
                # Verify component-specific integrity
                if component == 'database':
                    if not self._verify_database_backup(file_path):
                        errors.append(f"Database backup corruption detected: {file_path}")
                        content_verified = False
                elif component == 'json_files':
                    if not self._verify_json_backup(file_path):
                        errors.append(f"JSON backup corruption detected: {file_path}")
                        content_verified = False
            
            # Test restore (optional, resource-intensive)
            restore_tested = False
            if hasattr(self.config, 'enable_restore_testing') and self.config.enable_restore_testing:
                restore_tested = self._test_restore(backup_id)
                if not restore_tested:
                    warnings.append("Restore test failed or skipped")
            
            # Determine overall validation status
            is_valid = checksum_verified and content_verified and not errors
            
            # Update metadata with validation results
            metadata.validation_status = 'valid' if is_valid else 'invalid'
            metadata.restore_tested = restore_tested
            self._save_backup_metadata(metadata)
            
            result = BackupValidationResult(
                is_valid=is_valid,
                checksum_verified=checksum_verified,
                content_verified=content_verified,
                restore_tested=restore_tested,
                errors=errors,
                warnings=warnings,
                validation_time=validation_start
            )
            
            self.logger.info(f"Backup validation completed: {backup_id}, valid: {is_valid}")
            
            if not is_valid:
                self._send_alert(f"Backup validation failed: {backup_id}", 
                               f"Errors: {', '.join(errors)}", 'error')
            
            return result
            
        except Exception as e:
            self.logger.error(f"Backup validation error for {backup_id}: {e}", exc_info=True)
            errors.append(f"Validation error: {str(e)}")
            return BackupValidationResult(
                is_valid=False, checksum_verified=False, content_verified=False,
                restore_tested=False, errors=errors, warnings=warnings,
                validation_time=validation_start
            )

    def restore_backup(self, backup_id: str, components: Optional[List[str]] = None, 
                      target_directory: Optional[str] = None, 
                      create_rollback: bool = True) -> RestoreResult:
        """
        Restore data from a backup.
        
        Args:
            backup_id: Unique identifier of the backup to restore
            components: List of components to restore (None = all)
            target_directory: Custom target directory for restoration
            create_rollback: Whether to create a rollback backup before restoration
        
        Returns:
            RestoreResult: Detailed restoration results
        """
        restore_start = datetime.now()
        errors = []
        warnings = []
        components_restored = []
        rollback_backup_id = None
        
        try:
            # Load backup metadata
            metadata = self._load_backup_metadata(backup_id)
            if not metadata:
                errors.append(f"Backup metadata not found for {backup_id}")
                return RestoreResult(
                    success=False, backup_id=backup_id, components_restored=[],
                    errors=errors, warnings=warnings, restore_time=restore_start,
                    rollback_available=False
                )
            
            # Validate backup before restoration
            validation_result = self.validate_backup(backup_id)
            if not validation_result.is_valid:
                errors.append("Backup validation failed")
                errors.extend(validation_result.errors)
                return RestoreResult(
                    success=False, backup_id=backup_id, components_restored=[],
                    errors=errors, warnings=warnings, restore_time=restore_start,
                    rollback_available=False
                )
            
            self.logger.info(f"Starting restoration from backup: {backup_id}")
            
            # Create rollback backup if requested
            if create_rollback:
                try:
                    rollback_backup_id = self.create_backup(
                        backup_type='pre_migration',
                        description=f"Pre-restore rollback for {backup_id}",
                        components=components or metadata.components
                    )
                    self.logger.info(f"Rollback backup created: {rollback_backup_id}")
                except Exception as e:
                    warnings.append(f"Failed to create rollback backup: {str(e)}")
            
            # Determine components to restore
            restore_components = components or metadata.components
            
            # Restore each component
            for component in restore_components:
                if component not in metadata.file_paths:
                    warnings.append(f"Component {component} not available in backup")
                    continue
                
                try:
                    if component == 'database':
                        self._restore_database(metadata.file_paths[component], target_directory)
                        components_restored.append(component)
                    elif component == 'json_files':
                        self._restore_json_files(metadata.file_paths[component], target_directory)
                        components_restored.append(component)
                    elif component == 'media':
                        self._restore_media_files(metadata.file_paths[component], target_directory)
                        components_restored.append(component)
                    elif component == 'logs':
                        self._restore_logs(metadata.file_paths[component], target_directory)
                        components_restored.append(component)
                    
                    self.logger.info(f"Component {component} restored successfully")
                    
                except Exception as e:
                    error_msg = f"Failed to restore component {component}: {str(e)}"
                    errors.append(error_msg)
                    self.logger.error(error_msg, exc_info=True)
            
            success = len(components_restored) > 0 and len(errors) == 0
            
            result = RestoreResult(
                success=success,
                backup_id=backup_id,
                components_restored=components_restored,
                errors=errors,
                warnings=warnings,
                restore_time=restore_start,
                rollback_available=rollback_backup_id is not None
            )
            
            if success:
                self.logger.info(f"Restoration completed successfully: {backup_id}")
            else:
                self.logger.error(f"Restoration failed: {backup_id}")
                self._send_alert(f"Restore failed: {backup_id}", 
                               f"Errors: {', '.join(errors)}", 'error')
            
            return result
            
        except Exception as e:
            self.logger.error(f"Restoration error for {backup_id}: {e}", exc_info=True)
            errors.append(f"Restoration error: {str(e)}")
            return RestoreResult(
                success=False, backup_id=backup_id, components_restored=components_restored,
                errors=errors, warnings=warnings, restore_time=restore_start,
                rollback_available=rollback_backup_id is not None
            )

    def cleanup_expired_backups(self) -> Dict[str, int]:
        """
        Remove expired backups based on retention policies.
        
        Returns:
            Dict with cleanup statistics
        """
        cleanup_stats = {
            'total_checked': 0,
            'expired_found': 0,
            'successfully_deleted': 0,
            'failed_deletions': 0,
            'space_freed_bytes': 0
        }
        
        current_time = datetime.now()
        
        try:
            # Get all backup metadata
            backups = self.list_backups()
            cleanup_stats['total_checked'] = len(backups)
            
            for backup_id in backups:
                metadata = self._load_backup_metadata(backup_id)
                if not metadata:
                    continue
                
                # Check if backup is expired
                if current_time > metadata.retention_date:
                    cleanup_stats['expired_found'] += 1
                    
                    try:
                        # Delete backup files
                        backup_dir = self.backup_base_dir / backup_id
                        if backup_dir.exists():
                            space_freed = sum(f.stat().st_size for f in backup_dir.rglob('*') if f.is_file())
                            shutil.rmtree(backup_dir)
                            cleanup_stats['space_freed_bytes'] += space_freed
                        
                        # Delete metadata
                        metadata_file = self.backup_base_dir / "metadata" / f"{backup_id}.json"
                        if metadata_file.exists():
                            metadata_file.unlink()
                        
                        cleanup_stats['successfully_deleted'] += 1
                        self.logger.info(f"Deleted expired backup: {backup_id}")
                        
                    except Exception as e:
                        cleanup_stats['failed_deletions'] += 1
                        self.logger.error(f"Failed to delete backup {backup_id}: {e}")
            
            self.logger.info(f"Backup cleanup completed. Deleted {cleanup_stats['successfully_deleted']} backups, "
                           f"freed {cleanup_stats['space_freed_bytes']:,} bytes")
            
            return cleanup_stats
            
        except Exception as e:
            self.logger.error(f"Backup cleanup error: {e}", exc_info=True)
            return cleanup_stats

    def list_backups(self) -> List[str]:
        """Get list of all available backup IDs."""
        metadata_dir = self.backup_base_dir / "metadata"
        if not metadata_dir.exists():
            return []
        
        backup_ids = []
        for metadata_file in metadata_dir.glob("*.json"):
            backup_ids.append(metadata_file.stem)
        
        return sorted(backup_ids, reverse=True)  # Most recent first

    def get_backup_info(self, backup_id: str) -> Optional[BackupMetadata]:
        """Get detailed information about a specific backup."""
        return self._load_backup_metadata(backup_id)

    def get_backup_statistics(self) -> Dict[str, Any]:
        """Get comprehensive backup statistics and metrics."""
        stats = self.backup_stats.copy()
        
        # Add current backup information
        backups = self.list_backups()
        stats['total_backups_on_disk'] = len(backups)
        
        # Calculate storage usage
        total_storage = 0
        backup_types = {}
        
        for backup_id in backups:
            metadata = self._load_backup_metadata(backup_id)
            if metadata:
                total_storage += metadata.size_bytes
                backup_types[metadata.backup_type] = backup_types.get(metadata.backup_type, 0) + 1
        
        stats['total_storage_bytes'] = total_storage
        stats['storage_by_type'] = backup_types
        stats['last_backup_time'] = self.last_backup_time.isoformat() if self.last_backup_time else None
        
        return stats

    def schedule_automated_backups(self):
        """Start automated backup scheduling in background thread."""
        def backup_scheduler():
            while True:
                try:
                    current_time = datetime.now()
                    
                    # Check for daily backup (run at 2 AM)
                    if current_time.hour == 2 and current_time.minute < 5:
                        if not self.backup_running:
                            self.create_backup('daily', 'Automated daily backup')
                        time.sleep(300)  # Sleep 5 minutes to avoid duplicate runs
                    
                    # Check for weekly backup (run on Sunday at 3 AM)
                    elif current_time.weekday() == 6 and current_time.hour == 3 and current_time.minute < 5:
                        if not self.backup_running:
                            self.create_backup('weekly', 'Automated weekly backup')
                        time.sleep(300)
                    
                    # Run cleanup daily at 4 AM
                    elif current_time.hour == 4 and current_time.minute < 5:
                        self.cleanup_expired_backups()
                        time.sleep(300)
                    
                    time.sleep(60)  # Check every minute
                    
                except Exception as e:
                    self.logger.error(f"Backup scheduler error: {e}", exc_info=True)
                    time.sleep(300)  # Wait 5 minutes before retrying
        
        scheduler_thread = threading.Thread(target=backup_scheduler, daemon=True)
        scheduler_thread.start()
        self.logger.info("Automated backup scheduler started")

    def add_alert_handler(self, handler_func):
        """Add a custom alert handler function."""
        self.alert_handlers.append(handler_func)

    def _backup_database(self, backup_dir: Path, backup_id: str) -> Path:
        """Create database backup using pg_dump."""
        db_backup_file = backup_dir / f"database_{backup_id}.sql.gz"
        
        # Build pg_dump command
        cmd = [
            'pg_dump',
            '--host', getattr(self.config, 'db_host', 'localhost'),
            '--port', str(getattr(self.config, 'db_port', 5432)),
            '--username', getattr(self.config, 'db_user', 'postgres'),
            '--dbname', getattr(self.config, 'db_name', 'knowledge_base'),
            '--verbose',
            '--clean',
            '--if-exists',
            '--create'
        ]
        
        # Set password via environment variable
        env = os.environ.copy()
        if hasattr(self.config, 'db_password'):
            env['PGPASSWORD'] = self.config.db_password
        
        try:
            # Run pg_dump and compress output
            with gzip.open(db_backup_file, 'wt') as f:
                result = subprocess.run(cmd, stdout=f, stderr=subprocess.PIPE, 
                                      env=env, text=True, check=True)
            
            return db_backup_file
            
        except subprocess.CalledProcessError as e:
            self.logger.error(f"Database backup failed: {e.stderr}")
            raise RuntimeError(f"Database backup failed: {e.stderr}")

    def _backup_json_files(self, backup_dir: Path, backup_id: str) -> Path:
        """Create backup of JSON data files."""
        json_backup_file = backup_dir / f"json_files_{backup_id}.tar.gz"
        
        data_dir = Path(getattr(self.config, 'data_directory', 'data'))
        if not data_dir.exists():
            self.logger.warning(f"Data directory not found: {data_dir}")
            # Create empty archive
            subprocess.run(['tar', '-czf', str(json_backup_file), '-T', '/dev/null'], check=True)
            return json_backup_file
        
        # Create compressed archive of JSON files
        cmd = ['tar', '-czf', str(json_backup_file), '-C', str(data_dir.parent), str(data_dir.name)]
        subprocess.run(cmd, check=True)
        
        return json_backup_file

    def _backup_media_files(self, backup_dir: Path, backup_id: str) -> Optional[Path]:
        """Create backup of media files."""
        media_backup_file = backup_dir / f"media_{backup_id}.tar.gz"
        
        media_dir = Path(getattr(self.config, 'media_directory', 'media'))
        if not media_dir.exists():
            self.logger.info(f"Media directory not found, skipping: {media_dir}")
            return None
        
        # Create compressed archive of media files
        cmd = ['tar', '-czf', str(media_backup_file), '-C', str(media_dir.parent), str(media_dir.name)]
        subprocess.run(cmd, check=True)
        
        return media_backup_file

    def _backup_logs(self, backup_dir: Path, backup_id: str) -> Optional[Path]:
        """Create backup of log files."""
        logs_backup_file = backup_dir / f"logs_{backup_id}.tar.gz"
        
        logs_dir = Path(getattr(self.config, 'log_directory', 'logs'))
        if not logs_dir.exists():
            self.logger.info(f"Logs directory not found, skipping: {logs_dir}")
            return None
        
        # Create compressed archive of recent log files (last 30 days)
        recent_logs = []
        cutoff_date = datetime.now() - timedelta(days=30)
        
        for log_file in logs_dir.glob("*.log*"):
            if log_file.stat().st_mtime > cutoff_date.timestamp():
                recent_logs.append(str(log_file.relative_to(logs_dir.parent)))
        
        if recent_logs:
            cmd = ['tar', '-czf', str(logs_backup_file), '-C', str(logs_dir.parent)] + recent_logs
            subprocess.run(cmd, check=True)
            return logs_backup_file
        
        return None

    def _calculate_backup_checksum(self, file_paths: Dict[str, str]) -> str:
        """Calculate SHA256 checksum of all backup files."""
        hasher = hashlib.sha256()
        
        for component in sorted(file_paths.keys()):
            file_path = Path(file_paths[component])
            if file_path.exists():
                with open(file_path, 'rb') as f:
                    for chunk in iter(lambda: f.read(4096), b""):
                        hasher.update(chunk)
        
        return hasher.hexdigest()

    def _save_backup_metadata(self, metadata: BackupMetadata):
        """Save backup metadata to JSON file."""
        metadata_file = self.backup_base_dir / "metadata" / f"{metadata.backup_id}.json"
        
        metadata_dict = {
            'backup_id': metadata.backup_id,
            'backup_type': metadata.backup_type,
            'created_at': metadata.created_at.isoformat(),
            'size_bytes': metadata.size_bytes,
            'checksum': metadata.checksum,
            'description': metadata.description,
            'retention_date': metadata.retention_date.isoformat(),
            'components': metadata.components,
            'validation_status': metadata.validation_status,
            'restore_tested': metadata.restore_tested,
            'file_paths': metadata.file_paths
        }
        
        with open(metadata_file, 'w') as f:
            json.dump(metadata_dict, f, indent=2)

    def _load_backup_metadata(self, backup_id: str) -> Optional[BackupMetadata]:
        """Load backup metadata from JSON file."""
        metadata_file = self.backup_base_dir / "metadata" / f"{backup_id}.json"
        
        if not metadata_file.exists():
            return None
        
        try:
            with open(metadata_file, 'r') as f:
                data = json.load(f)
            
            return BackupMetadata(
                backup_id=data['backup_id'],
                backup_type=data['backup_type'],
                created_at=datetime.fromisoformat(data['created_at']),
                size_bytes=data['size_bytes'],
                checksum=data['checksum'],
                description=data['description'],
                retention_date=datetime.fromisoformat(data['retention_date']),
                components=data['components'],
                validation_status=data['validation_status'],
                restore_tested=data['restore_tested'],
                file_paths=data['file_paths']
            )
        except Exception as e:
            self.logger.error(f"Failed to load backup metadata {backup_id}: {e}")
            return None

    def _verify_database_backup(self, backup_file: str) -> bool:
        """Verify database backup integrity."""
        try:
            # Test if the gzipped SQL file can be read
            with gzip.open(backup_file, 'rt') as f:
                # Read first few lines to verify it's a valid SQL dump
                header = f.read(1000)
                return 'PostgreSQL database dump' in header or 'CREATE DATABASE' in header
        except Exception:
            return False

    def _verify_json_backup(self, backup_file: str) -> bool:
        """Verify JSON backup integrity."""
        try:
            # Test if the tar.gz file can be read
            result = subprocess.run(['tar', '-tzf', backup_file], 
                                  capture_output=True, check=True)
            return len(result.stdout) > 0
        except Exception:
            return False

    def _test_restore(self, backup_id: str) -> bool:
        """Test backup restoration in a temporary environment."""
        # This is a placeholder for restore testing
        # In a full implementation, this would restore to a test database
        self.logger.info(f"Restore test for {backup_id} skipped (not implemented)")
        return False

    def _restore_database(self, backup_file: str, target_directory: Optional[str]):
        """Restore database from backup."""
        self.logger.info(f"Starting database restoration from {backup_file}")
        
        # Build psql command for restoration
        cmd = [
            'psql',
            '--host', getattr(self.config, 'db_host', 'localhost'),
            '--port', str(getattr(self.config, 'db_port', 5432)),
            '--username', getattr(self.config, 'db_user', 'postgres'),
            '--dbname', getattr(self.config, 'db_name', 'knowledge_base')
        ]
        
        env = os.environ.copy()
        if hasattr(self.config, 'db_password'):
            env['PGPASSWORD'] = self.config.db_password
        
        try:
            with gzip.open(backup_file, 'rt') as f:
                result = subprocess.run(cmd, stdin=f, stderr=subprocess.PIPE,
                                      env=env, text=True, check=True)
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"Database restoration failed: {e.stderr}")

    def _restore_json_files(self, backup_file: str, target_directory: Optional[str]):
        """Restore JSON files from backup."""
        target_dir = target_directory or getattr(self.config, 'data_directory', 'data')
        self.logger.info(f"Restoring JSON files to {target_dir}")
        
        cmd = ['tar', '-xzf', backup_file, '-C', str(Path(target_dir).parent)]
        subprocess.run(cmd, check=True)

    def _restore_media_files(self, backup_file: str, target_directory: Optional[str]):
        """Restore media files from backup."""
        target_dir = target_directory or getattr(self.config, 'media_directory', 'media')
        self.logger.info(f"Restoring media files to {target_dir}")
        
        cmd = ['tar', '-xzf', backup_file, '-C', str(Path(target_dir).parent)]
        subprocess.run(cmd, check=True)

    def _restore_logs(self, backup_file: str, target_directory: Optional[str]):
        """Restore log files from backup."""
        target_dir = target_directory or getattr(self.config, 'log_directory', 'logs')
        self.logger.info(f"Restoring logs to {target_dir}")
        
        cmd = ['tar', '-xzf', backup_file, '-C', str(Path(target_dir).parent)]
        subprocess.run(cmd, check=True)

    def _schedule_backup_validation(self, backup_id: str):
        """Schedule background validation of a backup."""
        def validate_in_background():
            time.sleep(60)  # Wait 1 minute before validating
            try:
                self.validate_backup(backup_id)
            except Exception as e:
                self.logger.error(f"Background validation failed for {backup_id}: {e}")
        
        validation_thread = threading.Thread(target=validate_in_background, daemon=True)
        validation_thread.start()

    def _update_backup_stats(self, success: bool, duration: timedelta, size_bytes: int):
        """Update backup statistics."""
        self.backup_stats['total_backups'] += 1
        if success:
            self.backup_stats['successful_backups'] += 1
            self.backup_stats['total_backup_size'] += size_bytes
            
            # Update average backup time
            current_avg = self.backup_stats['average_backup_time']
            new_avg = (current_avg + duration.total_seconds()) / 2
            self.backup_stats['average_backup_time'] = new_avg
        else:
            self.backup_stats['failed_backups'] += 1

    def _send_alert(self, title: str, message: str, severity: str):
        """Send alert to configured handlers."""
        alert_data = {
            'title': title,
            'message': message,
            'severity': severity,
            'timestamp': datetime.now().isoformat(),
            'component': 'BackupManager'
        }
        
        for handler in self.alert_handlers:
            try:
                handler(alert_data)
            except Exception as e:
                self.logger.error(f"Alert handler failed: {e}") 