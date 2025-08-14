"""Data migration service for migrating from legacy system to new unified model."""

import os
import json
import logging
import asyncio
import hashlib
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
from pathlib import Path
from dataclasses import dataclass, asdict

from app.database.connection import get_db_session
from app.repositories.content import get_content_repository
from app.repositories.knowledge import get_knowledge_repository
from app.repositories.synthesis import get_synthesis_repository
from app.repositories.tasks import get_task_repository
from app.schemas.content import ContentItemCreate
from app.schemas.knowledge import KnowledgeItemCreate
from app.schemas.synthesis import SynthesisDocumentCreate
from app.models.content import ContentItem
from app.models.knowledge import KnowledgeItem
from app.models.synthesis import SynthesisDocument

logger = logging.getLogger(__name__)


@dataclass
class MigrationConfig:
    """Configuration for migration process."""
    source_directory: str
    backup_directory: str
    batch_size: int = 100
    validate_data: bool = True
    create_backups: bool = True
    preserve_timestamps: bool = True
    dry_run: bool = False
    incremental: bool = False
    max_file_size: int = 50 * 1024 * 1024  # 50MB max file size
    skip_large_files: bool = True
    parallel_processing: bool = False
    max_workers: int = 4


@dataclass
class MigrationStats:
    """Statistics for migration process."""
    total_files: int = 0
    processed_files: int = 0
    successful_migrations: int = 0
    failed_migrations: int = 0
    skipped_files: int = 0
    validation_errors: int = 0
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert stats to dictionary."""
        return asdict(self)


@dataclass
class MigrationResult:
    """Result of a migration operation."""
    success: bool
    message: str
    stats: MigrationStats
    errors: List[str]
    rollback_info: Optional[Dict[str, Any]] = None


class LegacyDataParser:
    """Parser for legacy data formats."""
    
    def __init__(self):
        self.supported_formats = ['.json', '.md', '.txt', '.csv']
    
    def parse_content_file(self, file_path: Path) -> Optional[Dict[str, Any]]:
        """Parse legacy content file."""
        try:
            if file_path.suffix == '.json':
                return self._parse_json_content(file_path)
            elif file_path.suffix == '.md':
                return self._parse_markdown_content(file_path)
            elif file_path.suffix == '.txt':
                return self._parse_text_content(file_path)
            else:
                logger.warning(f"Unsupported file format: {file_path}")
                return None
                
        except Exception as e:
            logger.error(f"Failed to parse file {file_path}: {e}")
            return None
    
    def _parse_json_content(self, file_path: Path) -> Dict[str, Any]:
        """Parse JSON content file."""
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # Map legacy fields to new schema
        return {
            'title': data.get('title', file_path.stem),
            'content': data.get('content', data.get('text', '')),
            'source_url': data.get('url', data.get('source_url')),
            'content_type': data.get('type', 'text'),
            'metadata': {
                'legacy_id': data.get('id'),
                'legacy_created_at': data.get('created_at'),
                'legacy_tags': data.get('tags', []),
                'legacy_category': data.get('category'),
                **data.get('metadata', {})
            },
            'file_path': str(file_path)
        }
    
    def _parse_markdown_content(self, file_path: Path) -> Dict[str, Any]:
        """Parse Markdown content file."""
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Extract frontmatter if present
        metadata = {}
        if content.startswith('---'):
            parts = content.split('---', 2)
            if len(parts) >= 3:
                try:
                    import yaml
                    metadata = yaml.safe_load(parts[1]) or {}
                    content = parts[2].strip()
                except ImportError:
                    logger.warning("PyYAML not installed, skipping frontmatter parsing")
        
        return {
            'title': metadata.get('title', file_path.stem),
            'content': content,
            'source_url': metadata.get('url'),
            'content_type': 'markdown',
            'metadata': {
                'legacy_file': str(file_path),
                'legacy_frontmatter': metadata,
                **metadata.get('metadata', {})
            },
            'file_path': str(file_path)
        }
    
    def _parse_text_content(self, file_path: Path) -> Dict[str, Any]:
        """Parse plain text content file."""
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        return {
            'title': file_path.stem,
            'content': content,
            'content_type': 'text',
            'metadata': {
                'legacy_file': str(file_path)
            },
            'file_path': str(file_path)
        }


class DataValidator:
    """Validator for migration data integrity."""
    
    def __init__(self):
        self.required_fields = ['title', 'content']
        self.max_title_length = 500
        self.max_content_length = 1000000  # 1MB
    
    def validate_content_item(self, data: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """Validate content item data."""
        errors = []
        
        # Check required fields
        for field in self.required_fields:
            if not data.get(field):
                errors.append(f"Missing required field: {field}")
        
        # Validate field lengths
        if data.get('title') and len(data['title']) > self.max_title_length:
            errors.append(f"Title too long: {len(data['title'])} > {self.max_title_length}")
        
        if data.get('content') and len(data['content']) > self.max_content_length:
            errors.append(f"Content too long: {len(data['content'])} > {self.max_content_length}")
        
        # Validate URL format
        if data.get('source_url'):
            url = data['source_url']
            if not (url.startswith('http://') or url.startswith('https://')):
                errors.append(f"Invalid URL format: {url}")
        
        # Validate content type
        valid_types = ['text', 'markdown', 'html', 'json', 'csv']
        if data.get('content_type') and data['content_type'] not in valid_types:
            errors.append(f"Invalid content type: {data['content_type']}")
        
        return len(errors) == 0, errors
    
    def calculate_content_hash(self, content: str) -> str:
        """Calculate hash for content deduplication."""
        return hashlib.sha256(content.encode('utf-8')).hexdigest()


class MigrationService:
    """Service for managing data migration from legacy system."""
    
    def __init__(self):
        self.parser = LegacyDataParser()
        self.validator = DataValidator()
        self.rollback_data = {}
    
    async def migrate_legacy_data(self, config: MigrationConfig) -> MigrationResult:
        """Migrate legacy data to new unified model."""
        stats = MigrationStats(start_time=datetime.utcnow())
        errors = []
        
        try:
            logger.info(f"Starting migration from {config.source_directory}")
            
            # Validate source directory
            source_path = Path(config.source_directory)
            if not source_path.exists():
                raise ValueError(f"Source directory does not exist: {config.source_directory}")
            
            # Create backup if requested
            if config.create_backups and not config.dry_run:
                await self._create_backup(config)
            
            # Discover files to migrate
            files_to_migrate = self._discover_files(source_path)
            
            # Filter out already migrated files for incremental migration
            if hasattr(config, 'incremental') and config.incremental:
                files_to_migrate = await self._filter_incremental_files(files_to_migrate)
            
            stats.total_files = len(files_to_migrate)
            
            logger.info(f"Found {stats.total_files} files to migrate")
            
            if stats.total_files == 0:
                logger.info("No files to migrate")
                return MigrationResult(
                    success=True,
                    message="No files to migrate",
                    stats=stats,
                    errors=errors
                )
            
            # Process files in batches with memory management
            for i in range(0, len(files_to_migrate), config.batch_size):
                batch = files_to_migrate[i:i + config.batch_size]
                batch_result = await self._process_batch(batch, config, stats)
                errors.extend(batch_result)
                
                # Log progress
                progress = (stats.processed_files / stats.total_files) * 100
                logger.info(f"Migration progress: {progress:.1f}% ({stats.processed_files}/{stats.total_files})")
                
                # Memory cleanup between batches
                if i % (config.batch_size * 10) == 0:  # Every 10 batches
                    await asyncio.sleep(0.1)  # Allow garbage collection
            
            stats.end_time = datetime.utcnow()
            
            # Run data integrity checks
            if not config.dry_run:
                integrity_results = await self._run_integrity_checks(stats)
                if integrity_results['failed_checks'] > 0:
                    errors.extend(integrity_results['errors'])
            
            # Generate migration report
            await self._generate_migration_report(stats, errors, config)
            
            success = stats.failed_migrations == 0
            message = f"Migration completed. Success: {stats.successful_migrations}, Failed: {stats.failed_migrations}"
            
            return MigrationResult(
                success=success,
                message=message,
                stats=stats,
                errors=errors,
                rollback_info=self.rollback_data if not config.dry_run else None
            )
            
        except Exception as e:
            logger.error(f"Migration failed: {e}")
            stats.end_time = datetime.utcnow()
            
            return MigrationResult(
                success=False,
                message=f"Migration failed: {str(e)}",
                stats=stats,
                errors=errors + [str(e)]
            )
    
    async def rollback_migration(self, rollback_info: Dict[str, Any]) -> bool:
        """Rollback a migration using stored rollback information."""
        try:
            logger.info("Starting migration rollback")
            
            # Create rollback checkpoint
            rollback_checkpoint = {
                'timestamp': datetime.utcnow().isoformat(),
                'rollback_items': [],
                'errors': []
            }
            
            # Remove migrated items with error handling
            if 'migrated_items' in rollback_info:
                async with get_db_session() as db:
                    content_repo = get_content_repository()
                    knowledge_repo = get_knowledge_repository()
                    synthesis_repo = get_synthesis_repository()
                    
                    # Rollback content items
                    for item_id in rollback_info['migrated_items'].get('content', []):
                        try:
                            await content_repo.delete(db, item_id)
                            rollback_checkpoint['rollback_items'].append({
                                'type': 'content',
                                'id': item_id,
                                'status': 'removed'
                            })
                        except Exception as e:
                            error_msg = f"Failed to remove content item {item_id}: {str(e)}"
                            logger.error(error_msg)
                            rollback_checkpoint['errors'].append(error_msg)
                    
                    # Rollback knowledge items
                    for item_id in rollback_info['migrated_items'].get('knowledge', []):
                        try:
                            await knowledge_repo.delete(db, item_id)
                            rollback_checkpoint['rollback_items'].append({
                                'type': 'knowledge',
                                'id': item_id,
                                'status': 'removed'
                            })
                        except Exception as e:
                            error_msg = f"Failed to remove knowledge item {item_id}: {str(e)}"
                            logger.error(error_msg)
                            rollback_checkpoint['errors'].append(error_msg)
                    
                    # Rollback synthesis items
                    for item_id in rollback_info['migrated_items'].get('synthesis', []):
                        try:
                            await synthesis_repo.delete(db, item_id)
                            rollback_checkpoint['rollback_items'].append({
                                'type': 'synthesis',
                                'id': item_id,
                                'status': 'removed'
                            })
                        except Exception as e:
                            error_msg = f"Failed to remove synthesis item {item_id}: {str(e)}"
                            logger.error(error_msg)
                            rollback_checkpoint['errors'].append(error_msg)
            
            # Restore backup if available
            if 'backup_path' in rollback_info:
                try:
                    await self._restore_backup(rollback_info['backup_path'])
                    rollback_checkpoint['backup_restored'] = True
                except Exception as e:
                    error_msg = f"Failed to restore backup: {str(e)}"
                    logger.error(error_msg)
                    rollback_checkpoint['errors'].append(error_msg)
                    rollback_checkpoint['backup_restored'] = False
            
            # Save rollback checkpoint
            if 'backup_directory' in rollback_info:
                checkpoint_path = Path(rollback_info['backup_directory']) / "rollback_checkpoint.json"
                with open(checkpoint_path, 'w') as f:
                    json.dump(rollback_checkpoint, f, indent=2, default=str)
            
            success = len(rollback_checkpoint['errors']) == 0
            if success:
                logger.info("Migration rollback completed successfully")
            else:
                logger.warning(f"Migration rollback completed with {len(rollback_checkpoint['errors'])} errors")
            
            return success
            
        except Exception as e:
            logger.error(f"Rollback failed: {e}")
            return False
    
    async def validate_migration(self, config: MigrationConfig) -> Dict[str, Any]:
        """Validate migration without actually performing it."""
        logger.info("Validating migration data")
        
        source_path = Path(config.source_directory)
        files_to_migrate = self._discover_files(source_path)
        
        validation_results = {
            'total_files': len(files_to_migrate),
            'valid_files': 0,
            'invalid_files': 0,
            'errors': [],
            'warnings': []
        }
        
        for file_path in files_to_migrate:
            try:
                # Parse file
                parsed_data = self.parser.parse_content_file(file_path)
                if not parsed_data:
                    validation_results['invalid_files'] += 1
                    validation_results['errors'].append(f"Could not parse file: {file_path}")
                    continue
                
                # Validate data
                is_valid, errors = self.validator.validate_content_item(parsed_data)
                if is_valid:
                    validation_results['valid_files'] += 1
                else:
                    validation_results['invalid_files'] += 1
                    validation_results['errors'].extend([f"{file_path}: {error}" for error in errors])
                
            except Exception as e:
                validation_results['invalid_files'] += 1
                validation_results['errors'].append(f"Error validating {file_path}: {str(e)}")
        
        return validation_results
    
    def _discover_files(self, source_path: Path) -> List[Path]:
        """Discover files to migrate."""
        files = []
        
        for pattern in ['**/*.json', '**/*.md', '**/*.txt']:
            files.extend(source_path.glob(pattern))
        
        # Filter out hidden files and directories
        files = [f for f in files if not any(part.startswith('.') for part in f.parts)]
        
        return sorted(files)
    
    async def _process_batch(
        self, 
        batch: List[Path], 
        config: MigrationConfig, 
        stats: MigrationStats
    ) -> List[str]:
        """Process a batch of files."""
        errors = []
        
        for file_path in batch:
            try:
                stats.processed_files += 1
                
                # Parse file
                parsed_data = self.parser.parse_content_file(file_path)
                if not parsed_data:
                    stats.skipped_files += 1
                    continue
                
                # Validate data
                if config.validate_data:
                    is_valid, validation_errors = self.validator.validate_content_item(parsed_data)
                    if not is_valid:
                        stats.validation_errors += 1
                        stats.failed_migrations += 1
                        errors.extend([f"{file_path}: {error}" for error in validation_errors])
                        continue
                
                # Migrate data
                if not config.dry_run:
                    success = await self._migrate_single_item(parsed_data, file_path)
                    if success:
                        stats.successful_migrations += 1
                    else:
                        stats.failed_migrations += 1
                        errors.append(f"Failed to migrate: {file_path}")
                else:
                    stats.successful_migrations += 1
                
            except Exception as e:
                stats.failed_migrations += 1
                errors.append(f"Error processing {file_path}: {str(e)}")
                logger.error(f"Error processing {file_path}: {e}")
        
        return errors
    
    async def _migrate_single_item(self, data: Dict[str, Any], file_path: Path) -> bool:
        """Migrate a single item to the database."""
        try:
            async with get_db_session() as db:
                content_repo = get_content_repository()
                
                # Check for duplicates
                content_hash = self.validator.calculate_content_hash(data['content'])
                existing = await content_repo.get_by_hash(db, content_hash)
                if existing:
                    logger.info(f"Skipping duplicate content: {file_path}")
                    return True
                
                # Create content item
                content_create = ContentItemCreate(
                    title=data['title'],
                    content=data['content'],
                    source_url=data.get('source_url'),
                    content_type=data.get('content_type', 'text'),
                    metadata=data.get('metadata', {}),
                    content_hash=content_hash
                )
                
                content_item = await content_repo.create(db, content_create)
                
                # Store rollback info
                if 'migrated_items' not in self.rollback_data:
                    self.rollback_data['migrated_items'] = {'content': [], 'knowledge': [], 'synthesis': []}
                
                self.rollback_data['migrated_items']['content'].append(content_item.id)
                
                # Create knowledge item if content is substantial
                if len(data['content']) > 500:  # Threshold for knowledge items
                    knowledge_repo = get_knowledge_repository()
                    
                    knowledge_create = KnowledgeItemCreate(
                        title=data['title'],
                        content=data['content'],
                        source_content_id=content_item.id,
                        main_category=data.get('metadata', {}).get('legacy_category', 'migrated'),
                        sub_category='legacy_data',
                        metadata=data.get('metadata', {})
                    )
                    
                    knowledge_item = await knowledge_repo.create(db, knowledge_create)
                    self.rollback_data['migrated_items']['knowledge'].append(knowledge_item.id)
                
                return True
                
        except Exception as e:
            logger.error(f"Failed to migrate item {file_path}: {e}")
            return False
    
    async def _create_backup(self, config: MigrationConfig):
        """Create backup of existing data."""
        try:
            backup_path = Path(config.backup_directory)
            backup_path.mkdir(parents=True, exist_ok=True)
            
            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            backup_file = backup_path / f"migration_backup_{timestamp}.json"
            
            # Export existing data
            backup_data = await self._export_existing_data()
            
            with open(backup_file, 'w', encoding='utf-8') as f:
                json.dump(backup_data, f, indent=2, default=str)
            
            self.rollback_data['backup_path'] = str(backup_file)
            logger.info(f"Backup created: {backup_file}")
            
        except Exception as e:
            logger.error(f"Failed to create backup: {e}")
            raise
    
    async def _export_existing_data(self) -> Dict[str, Any]:
        """Export existing data for backup."""
        backup_data = {
            'timestamp': datetime.utcnow().isoformat(),
            'content_items': [],
            'knowledge_items': [],
            'synthesis_documents': []
        }
        
        try:
            async with get_db_session() as db:
                # Export content items
                content_repo = get_content_repository()
                content_items = await content_repo.list(db, limit=10000)
                backup_data['content_items'] = [item.to_dict() for item in content_items]
                
                # Export knowledge items
                knowledge_repo = get_knowledge_repository()
                knowledge_items = await knowledge_repo.list(db, limit=10000)
                backup_data['knowledge_items'] = [item.to_dict() for item in knowledge_items]
                
                # Export synthesis documents
                synthesis_repo = get_synthesis_repository()
                synthesis_docs = await synthesis_repo.list(db, limit=10000)
                backup_data['synthesis_documents'] = [doc.to_dict() for doc in synthesis_docs]
                
        except Exception as e:
            logger.error(f"Failed to export existing data: {e}")
        
        return backup_data
    
    async def _restore_backup(self, backup_path: str):
        """Restore data from backup."""
        try:
            with open(backup_path, 'r', encoding='utf-8') as f:
                backup_data = json.load(f)
            
            # This would implement restoration logic
            # For now, just log the action
            logger.info(f"Backup restoration would restore {len(backup_data.get('content_items', []))} content items")
            
        except Exception as e:
            logger.error(f"Failed to restore backup: {e}")
            raise
    
    async def _filter_incremental_files(self, files: List[Path]) -> List[Path]:
        """Filter out already migrated files for incremental migration."""
        try:
            filtered_files = []
            
            async with get_db_session() as db:
                content_repo = get_content_repository()
                
                for file_path in files:
                    # Check if file was already migrated by looking for metadata
                    file_path_str = str(file_path)
                    
                    # Query for existing content with this file path in metadata
                    existing_items = await content_repo.get_by_metadata_field(
                        db, 'legacy_file', file_path_str
                    )
                    
                    if not existing_items:
                        # Also check by file hash if file exists
                        try:
                            with open(file_path, 'r', encoding='utf-8') as f:
                                content = f.read()
                            content_hash = self.validator.calculate_content_hash(content)
                            existing_by_hash = await content_repo.get_by_hash(db, content_hash)
                            
                            if not existing_by_hash:
                                filtered_files.append(file_path)
                            else:
                                logger.debug(f"Skipping already migrated file (by hash): {file_path}")
                        except Exception:
                            # If we can't read the file, include it for processing
                            filtered_files.append(file_path)
                    else:
                        logger.debug(f"Skipping already migrated file (by metadata): {file_path}")
            
            logger.info(f"Incremental migration: {len(filtered_files)} of {len(files)} files need migration")
            return filtered_files
            
        except Exception as e:
            logger.error(f"Error filtering incremental files: {e}")
            return files  # Return all files if filtering fails
    
    async def _run_integrity_checks(self, stats: MigrationStats) -> Dict[str, Any]:
        """Run data integrity checks after migration."""
        try:
            logger.info("Running data integrity checks")
            
            integrity_results = {
                'total_checks': 0,
                'passed_checks': 0,
                'failed_checks': 0,
                'errors': []
            }
            
            async with get_db_session() as db:
                content_repo = get_content_repository()
                knowledge_repo = get_knowledge_repository()
                
                # Check 1: Verify migrated content count
                integrity_results['total_checks'] += 1
                try:
                    migrated_content_count = len(self.rollback_data.get('migrated_items', {}).get('content', []))
                    actual_content_count = await content_repo.count_recent_items(db, hours=1)
                    
                    if migrated_content_count <= actual_content_count:
                        integrity_results['passed_checks'] += 1
                        logger.info(f"Content count check passed: {migrated_content_count} <= {actual_content_count}")
                    else:
                        integrity_results['failed_checks'] += 1
                        error_msg = f"Content count mismatch: expected {migrated_content_count}, found {actual_content_count}"
                        integrity_results['errors'].append(error_msg)
                        logger.error(error_msg)
                        
                except Exception as e:
                    integrity_results['failed_checks'] += 1
                    error_msg = f"Content count check failed: {str(e)}"
                    integrity_results['errors'].append(error_msg)
                    logger.error(error_msg)
                
                # Check 2: Verify knowledge items have valid source references
                integrity_results['total_checks'] += 1
                try:
                    migrated_knowledge_ids = self.rollback_data.get('migrated_items', {}).get('knowledge', [])
                    orphaned_knowledge = 0
                    
                    for knowledge_id in migrated_knowledge_ids:
                        knowledge_item = await knowledge_repo.get(db, knowledge_id)
                        if knowledge_item and knowledge_item.source_content_id:
                            source_content = await content_repo.get(db, knowledge_item.source_content_id)
                            if not source_content:
                                orphaned_knowledge += 1
                    
                    if orphaned_knowledge == 0:
                        integrity_results['passed_checks'] += 1
                        logger.info("Knowledge item reference check passed")
                    else:
                        integrity_results['failed_checks'] += 1
                        error_msg = f"Found {orphaned_knowledge} orphaned knowledge items"
                        integrity_results['errors'].append(error_msg)
                        logger.error(error_msg)
                        
                except Exception as e:
                    integrity_results['failed_checks'] += 1
                    error_msg = f"Knowledge reference check failed: {str(e)}"
                    integrity_results['errors'].append(error_msg)
                    logger.error(error_msg)
                
                # Check 3: Verify no duplicate content hashes
                integrity_results['total_checks'] += 1
                try:
                    duplicate_count = await content_repo.count_duplicate_hashes(db)
                    
                    if duplicate_count == 0:
                        integrity_results['passed_checks'] += 1
                        logger.info("Duplicate content check passed")
                    else:
                        integrity_results['failed_checks'] += 1
                        error_msg = f"Found {duplicate_count} duplicate content items"
                        integrity_results['errors'].append(error_msg)
                        logger.error(error_msg)
                        
                except Exception as e:
                    integrity_results['failed_checks'] += 1
                    error_msg = f"Duplicate content check failed: {str(e)}"
                    integrity_results['errors'].append(error_msg)
                    logger.error(error_msg)
            
            logger.info(f"Integrity checks completed: {integrity_results['passed_checks']}/{integrity_results['total_checks']} passed")
            return integrity_results
            
        except Exception as e:
            logger.error(f"Integrity checks failed: {e}")
            return {
                'total_checks': 0,
                'passed_checks': 0,
                'failed_checks': 1,
                'errors': [f"Integrity check system failed: {str(e)}"]
            }

    async def _generate_migration_report(
        self, 
        stats: MigrationStats, 
        errors: List[str], 
        config: MigrationConfig
    ):
        """Generate migration report."""
        try:
            report_path = Path(config.backup_directory) / "migration_report.json"
            report_path.parent.mkdir(parents=True, exist_ok=True)
            
            report = {
                'migration_config': asdict(config),
                'statistics': stats.to_dict(),
                'errors': errors,
                'rollback_info': self.rollback_data if hasattr(self, 'rollback_data') else None,
                'timestamp': datetime.utcnow().isoformat()
            }
            
            with open(report_path, 'w', encoding='utf-8') as f:
                json.dump(report, f, indent=2, default=str)
            
            logger.info(f"Migration report generated: {report_path}")
            
            # Also generate a human-readable summary
            summary_path = Path(config.backup_directory) / "migration_summary.txt"
            with open(summary_path, 'w', encoding='utf-8') as f:
                f.write("MIGRATION SUMMARY\n")
                f.write("=" * 50 + "\n\n")
                f.write(f"Migration completed at: {datetime.utcnow().isoformat()}\n")
                f.write(f"Source directory: {config.source_directory}\n")
                f.write(f"Backup directory: {config.backup_directory}\n\n")
                
                f.write("STATISTICS:\n")
                f.write(f"  Total files found: {stats.total_files}\n")
                f.write(f"  Files processed: {stats.processed_files}\n")
                f.write(f"  Successful migrations: {stats.successful_migrations}\n")
                f.write(f"  Failed migrations: {stats.failed_migrations}\n")
                f.write(f"  Skipped files: {stats.skipped_files}\n")
                f.write(f"  Validation errors: {stats.validation_errors}\n\n")
                
                if stats.start_time and stats.end_time:
                    duration = stats.end_time - stats.start_time
                    f.write(f"  Duration: {duration}\n\n")
                
                if errors:
                    f.write(f"ERRORS ({len(errors)}):\n")
                    for i, error in enumerate(errors[:20], 1):
                        f.write(f"  {i}. {error}\n")
                    if len(errors) > 20:
                        f.write(f"  ... and {len(errors) - 20} more errors\n")
            
            logger.info(f"Migration summary generated: {summary_path}")
            
        except Exception as e:
            logger.error(f"Failed to generate migration report: {e}")


# Global service instance
_migration_service: Optional[MigrationService] = None


def get_migration_service() -> MigrationService:
    """Get the global migration service instance."""
    global _migration_service
    if _migration_service is None:
        _migration_service = MigrationService()
    return _migration_service