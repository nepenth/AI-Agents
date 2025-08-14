"""Tests for data migration system."""

import pytest
import json
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, AsyncMock
from datetime import datetime

from app.services.migration_service import (
    MigrationService, MigrationConfig, LegacyDataParser, DataValidator,
    MigrationStats, MigrationResult
)


@pytest.fixture
def migration_service():
    """Create migration service for testing."""
    return MigrationService()


@pytest.fixture
def legacy_parser():
    """Create legacy data parser for testing."""
    return LegacyDataParser()


@pytest.fixture
def data_validator():
    """Create data validator for testing."""
    return DataValidator()


@pytest.fixture
def sample_migration_config():
    """Create sample migration configuration."""
    return MigrationConfig(
        source_directory="/tmp/legacy_data",
        backup_directory="/tmp/migration_backup",
        batch_size=10,
        validate_data=True,
        create_backups=True,
        preserve_timestamps=True,
        dry_run=False
    )


@pytest.fixture
def temp_directory():
    """Create temporary directory for testing."""
    with tempfile.TemporaryDirectory() as temp_dir:
        yield Path(temp_dir)


class TestLegacyDataParser:
    """Test cases for LegacyDataParser."""
    
    def test_parse_json_content(self, legacy_parser, temp_directory):
        """Test parsing JSON content file."""
        # Create test JSON file
        json_data = {
            "id": "test-123",
            "title": "Test Article",
            "content": "This is test content",
            "url": "https://example.com/article",
            "type": "article",
            "created_at": "2024-01-01T00:00:00Z",
            "tags": ["test", "article"],
            "category": "technology"
        }
        
        json_file = temp_directory / "test.json"
        with open(json_file, 'w') as f:
            json.dump(json_data, f)
        
        result = legacy_parser.parse_content_file(json_file)
        
        assert result is not None
        assert result['title'] == "Test Article"
        assert result['content'] == "This is test content"
        assert result['source_url'] == "https://example.com/article"
        assert result['content_type'] == "article"
        assert result['metadata']['legacy_id'] == "test-123"
        assert result['metadata']['legacy_tags'] == ["test", "article"]
        assert result['metadata']['legacy_category'] == "technology"
    
    def test_parse_markdown_content(self, legacy_parser, temp_directory):
        """Test parsing Markdown content file."""
        markdown_content = """---
title: Test Markdown
url: https://example.com/markdown
category: documentation
---

# Test Markdown

This is **markdown** content with formatting.

- Item 1
- Item 2
"""
        
        md_file = temp_directory / "test.md"
        with open(md_file, 'w') as f:
            f.write(markdown_content)
        
        result = legacy_parser.parse_content_file(md_file)
        
        assert result is not None
        assert result['title'] == "Test Markdown"
        assert "This is **markdown** content" in result['content']
        assert result['source_url'] == "https://example.com/markdown"
        assert result['content_type'] == "markdown"
        assert result['metadata']['legacy_frontmatter']['category'] == "documentation"
    
    def test_parse_text_content(self, legacy_parser, temp_directory):
        """Test parsing plain text content file."""
        text_content = "This is plain text content for testing."
        
        txt_file = temp_directory / "test.txt"
        with open(txt_file, 'w') as f:
            f.write(text_content)
        
        result = legacy_parser.parse_content_file(txt_file)
        
        assert result is not None
        assert result['title'] == "test"
        assert result['content'] == text_content
        assert result['content_type'] == "text"
        assert result['metadata']['legacy_file'] == str(txt_file)
    
    def test_parse_unsupported_format(self, legacy_parser, temp_directory):
        """Test parsing unsupported file format."""
        binary_file = temp_directory / "test.bin"
        with open(binary_file, 'wb') as f:
            f.write(b"binary content")
        
        result = legacy_parser.parse_content_file(binary_file)
        assert result is None
    
    def test_parse_invalid_json(self, legacy_parser, temp_directory):
        """Test parsing invalid JSON file."""
        json_file = temp_directory / "invalid.json"
        with open(json_file, 'w') as f:
            f.write("{ invalid json content")
        
        result = legacy_parser.parse_content_file(json_file)
        assert result is None


class TestDataValidator:
    """Test cases for DataValidator."""
    
    def test_validate_content_item_valid(self, data_validator):
        """Test validation of valid content item."""
        data = {
            'title': 'Valid Title',
            'content': 'Valid content text',
            'source_url': 'https://example.com',
            'content_type': 'text'
        }
        
        is_valid, errors = data_validator.validate_content_item(data)
        
        assert is_valid is True
        assert len(errors) == 0
    
    def test_validate_content_item_missing_required(self, data_validator):
        """Test validation with missing required fields."""
        data = {
            'content': 'Content without title'
        }
        
        is_valid, errors = data_validator.validate_content_item(data)
        
        assert is_valid is False
        assert any("Missing required field: title" in error for error in errors)
    
    def test_validate_content_item_title_too_long(self, data_validator):
        """Test validation with title too long."""
        data = {
            'title': 'x' * 600,  # Exceeds max length
            'content': 'Valid content'
        }
        
        is_valid, errors = data_validator.validate_content_item(data)
        
        assert is_valid is False
        assert any("Title too long" in error for error in errors)
    
    def test_validate_content_item_invalid_url(self, data_validator):
        """Test validation with invalid URL."""
        data = {
            'title': 'Valid Title',
            'content': 'Valid content',
            'source_url': 'not-a-valid-url'
        }
        
        is_valid, errors = data_validator.validate_content_item(data)
        
        assert is_valid is False
        assert any("Invalid URL format" in error for error in errors)
    
    def test_validate_content_item_invalid_type(self, data_validator):
        """Test validation with invalid content type."""
        data = {
            'title': 'Valid Title',
            'content': 'Valid content',
            'content_type': 'invalid_type'
        }
        
        is_valid, errors = data_validator.validate_content_item(data)
        
        assert is_valid is False
        assert any("Invalid content type" in error for error in errors)
    
    def test_calculate_content_hash(self, data_validator):
        """Test content hash calculation."""
        content1 = "This is test content"
        content2 = "This is test content"
        content3 = "This is different content"
        
        hash1 = data_validator.calculate_content_hash(content1)
        hash2 = data_validator.calculate_content_hash(content2)
        hash3 = data_validator.calculate_content_hash(content3)
        
        assert hash1 == hash2  # Same content should have same hash
        assert hash1 != hash3  # Different content should have different hash
        assert len(hash1) == 64  # SHA256 hash length


class TestMigrationService:
    """Test cases for MigrationService."""
    
    @pytest.mark.asyncio
    async def test_validate_migration(self, migration_service, temp_directory):
        """Test migration validation."""
        # Create test files
        json_file = temp_directory / "test.json"
        with open(json_file, 'w') as f:
            json.dump({
                "title": "Test",
                "content": "Test content"
            }, f)
        
        invalid_file = temp_directory / "invalid.json"
        with open(invalid_file, 'w') as f:
            f.write("{ invalid json")
        
        config = MigrationConfig(
            source_directory=str(temp_directory),
            backup_directory="/tmp/backup"
        )
        
        result = await migration_service.validate_migration(config)
        
        assert result['total_files'] == 2
        assert result['valid_files'] == 1
        assert result['invalid_files'] == 1
        assert len(result['errors']) > 0
    
    @pytest.mark.asyncio
    async def test_migrate_legacy_data_dry_run(self, migration_service, temp_directory):
        """Test migration in dry run mode."""
        # Create test file
        json_file = temp_directory / "test.json"
        with open(json_file, 'w') as f:
            json.dump({
                "title": "Test Article",
                "content": "This is test content for migration"
            }, f)
        
        config = MigrationConfig(
            source_directory=str(temp_directory),
            backup_directory=str(temp_directory / "backup"),
            dry_run=True,
            create_backups=False
        )
        
        result = await migration_service.migrate_legacy_data(config)
        
        assert result.success is True
        assert result.stats.total_files == 1
        assert result.stats.successful_migrations == 1
        assert result.stats.failed_migrations == 0
    
    @pytest.mark.asyncio
    async def test_migrate_legacy_data_invalid_source(self, migration_service):
        """Test migration with invalid source directory."""
        config = MigrationConfig(
            source_directory="/nonexistent/directory",
            backup_directory="/tmp/backup"
        )
        
        result = await migration_service.migrate_legacy_data(config)
        
        assert result.success is False
        assert "does not exist" in result.message
    
    @pytest.mark.asyncio
    async def test_migrate_single_item_success(self, migration_service):
        """Test migrating a single item successfully."""
        data = {
            'title': 'Test Item',
            'content': 'Test content for migration',
            'source_url': 'https://example.com',
            'content_type': 'text',
            'metadata': {'test': 'value'}
        }
        
        with patch('app.services.migration_service.get_db_session'):
            with patch('app.services.migration_service.get_content_repository') as mock_repo:
                mock_content_repo = Mock()
                mock_repo.return_value = mock_content_repo
                mock_content_repo.get_by_hash.return_value = None  # No duplicate
                mock_content_repo.create.return_value = Mock(id="content-123")
                
                with patch('app.services.migration_service.get_knowledge_repository') as mock_knowledge_repo:
                    mock_knowledge_repo_instance = Mock()
                    mock_knowledge_repo.return_value = mock_knowledge_repo_instance
                    mock_knowledge_repo_instance.create.return_value = Mock(id="knowledge-123")
                    
                    success = await migration_service._migrate_single_item(data, Path("test.json"))
                    
                    assert success is True
                    assert "content-123" in migration_service.rollback_data['migrated_items']['content']
    
    @pytest.mark.asyncio
    async def test_migrate_single_item_duplicate(self, migration_service):
        """Test migrating a duplicate item."""
        data = {
            'title': 'Test Item',
            'content': 'Test content',
            'content_type': 'text'
        }
        
        with patch('app.services.migration_service.get_db_session'):
            with patch('app.services.migration_service.get_content_repository') as mock_repo:
                mock_content_repo = Mock()
                mock_repo.return_value = mock_content_repo
                mock_content_repo.get_by_hash.return_value = Mock(id="existing-123")  # Duplicate found
                
                success = await migration_service._migrate_single_item(data, Path("test.json"))
                
                assert success is True  # Should succeed but skip duplicate
    
    def test_discover_files(self, migration_service, temp_directory):
        """Test file discovery."""
        # Create test files
        (temp_directory / "test1.json").touch()
        (temp_directory / "test2.md").touch()
        (temp_directory / "test3.txt").touch()
        (temp_directory / "ignored.bin").touch()  # Should be ignored
        
        # Create subdirectory with files
        subdir = temp_directory / "subdir"
        subdir.mkdir()
        (subdir / "nested.json").touch()
        
        # Create hidden file (should be ignored)
        (temp_directory / ".hidden.json").touch()
        
        files = migration_service._discover_files(temp_directory)
        
        assert len(files) == 4  # Should find 4 supported files
        file_names = [f.name for f in files]
        assert "test1.json" in file_names
        assert "test2.md" in file_names
        assert "test3.txt" in file_names
        assert "nested.json" in file_names
        assert "ignored.bin" not in file_names
        assert ".hidden.json" not in file_names
    
    @pytest.mark.asyncio
    async def test_process_batch(self, migration_service, temp_directory):
        """Test processing a batch of files."""
        # Create test files
        json_file = temp_directory / "test.json"
        with open(json_file, 'w') as f:
            json.dump({"title": "Test", "content": "Content"}, f)
        
        invalid_file = temp_directory / "invalid.json"
        with open(invalid_file, 'w') as f:
            f.write("{ invalid")
        
        config = MigrationConfig(
            source_directory=str(temp_directory),
            backup_directory="/tmp/backup",
            dry_run=True
        )
        
        stats = MigrationStats()
        batch = [json_file, invalid_file]
        
        errors = await migration_service._process_batch(batch, config, stats)
        
        assert stats.processed_files == 2
        assert stats.successful_migrations == 1
        assert stats.failed_migrations == 0  # Invalid file is skipped, not failed
        assert stats.skipped_files == 1
        assert len(errors) == 0
    
    @pytest.mark.asyncio
    async def test_rollback_migration(self, migration_service):
        """Test migration rollback."""
        rollback_info = {
            'migrated_items': {
                'content': ['content-1', 'content-2'],
                'knowledge': ['knowledge-1'],
                'synthesis': []
            },
            'backup_path': '/tmp/backup.json'
        }
        
        with patch('app.services.migration_service.get_db_session'):
            with patch('app.services.migration_service.get_content_repository') as mock_content_repo:
                mock_content_repo_instance = Mock()
                mock_content_repo.return_value = mock_content_repo_instance
                mock_content_repo_instance.delete.return_value = True
                
                with patch('app.services.migration_service.get_knowledge_repository') as mock_knowledge_repo:
                    mock_knowledge_repo_instance = Mock()
                    mock_knowledge_repo.return_value = mock_knowledge_repo_instance
                    mock_knowledge_repo_instance.delete.return_value = True
                    
                    with patch.object(migration_service, '_restore_backup') as mock_restore:
                        mock_restore.return_value = None
                        
                        success = await migration_service.rollback_migration(rollback_info)
                        
                        assert success is True
                        assert mock_content_repo_instance.delete.call_count == 2
                        assert mock_knowledge_repo_instance.delete.call_count == 1
                        mock_restore.assert_called_once_with('/tmp/backup.json')


class TestMigrationStats:
    """Test cases for MigrationStats."""
    
    def test_migration_stats_to_dict(self):
        """Test converting migration stats to dictionary."""
        stats = MigrationStats(
            total_files=100,
            processed_files=95,
            successful_migrations=90,
            failed_migrations=5,
            skipped_files=5,
            validation_errors=2,
            start_time=datetime(2024, 1, 1, 12, 0, 0),
            end_time=datetime(2024, 1, 1, 12, 30, 0)
        )
        
        stats_dict = stats.to_dict()
        
        assert stats_dict['total_files'] == 100
        assert stats_dict['processed_files'] == 95
        assert stats_dict['successful_migrations'] == 90
        assert stats_dict['failed_migrations'] == 5
        assert stats_dict['skipped_files'] == 5
        assert stats_dict['validation_errors'] == 2
        assert stats_dict['start_time'] == datetime(2024, 1, 1, 12, 0, 0)
        assert stats_dict['end_time'] == datetime(2024, 1, 1, 12, 30, 0)


class TestMigrationConfig:
    """Test cases for MigrationConfig."""
    
    def test_migration_config_creation(self):
        """Test creating migration configuration."""
        config = MigrationConfig(
            source_directory="/source",
            backup_directory="/backup",
            batch_size=50,
            validate_data=False,
            create_backups=False,
            preserve_timestamps=False,
            dry_run=True,
            incremental=True,
            max_file_size=10*1024*1024,
            skip_large_files=False,
            parallel_processing=True,
            max_workers=8
        )
        
        assert config.source_directory == "/source"
        assert config.backup_directory == "/backup"
        assert config.batch_size == 50
        assert config.validate_data is False
        assert config.create_backups is False
        assert config.preserve_timestamps is False
        assert config.dry_run is True
        assert config.incremental is True
        assert config.max_file_size == 10*1024*1024
        assert config.skip_large_files is False
        assert config.parallel_processing is True
        assert config.max_workers == 8
    
    def test_migration_config_defaults(self):
        """Test migration configuration with default values."""
        config = MigrationConfig(
            source_directory="/source",
            backup_directory="/backup"
        )
        
        assert config.batch_size == 100
        assert config.validate_data is True
        assert config.create_backups is True
        assert config.preserve_timestamps is True
        assert config.dry_run is False
        assert config.incremental is False
        assert config.max_file_size == 50*1024*1024
        assert config.skip_large_files is True
        assert config.parallel_processing is False
        assert config.max_workers == 4


class TestMigrationResult:
    """Test cases for MigrationResult."""
    
    def test_migration_result_creation(self):
        """Test creating migration result."""
        stats = MigrationStats(total_files=10, successful_migrations=8, failed_migrations=2)
        errors = ["Error 1", "Error 2"]
        rollback_info = {"migrated_items": {"content": ["item-1"]}}
        
        result = MigrationResult(
            success=False,
            message="Migration completed with errors",
            stats=stats,
            errors=errors,
            rollback_info=rollback_info
        )
        
        assert result.success is False
        assert result.message == "Migration completed with errors"
        assert result.stats.total_files == 10
        assert len(result.errors) == 2
        assert result.rollback_info["migrated_items"]["content"] == ["item-1"]


class TestIncrementalMigration:
    """Test cases for incremental migration functionality."""
    
    @pytest.mark.asyncio
    async def test_filter_incremental_files_no_existing(self, migration_service, temp_directory):
        """Test filtering incremental files when no files exist in database."""
        # Create test files
        json_file = temp_directory / "new.json"
        with open(json_file, 'w') as f:
            json.dump({"title": "New", "content": "New content"}, f)
        
        files = [json_file]
        
        with patch('app.services.migration_service.get_db_session'):
            with patch('app.services.migration_service.get_content_repository') as mock_repo:
                mock_content_repo = Mock()
                mock_repo.return_value = mock_content_repo
                mock_content_repo.get_by_metadata_field.return_value = []
                mock_content_repo.get_by_hash.return_value = None
                
                filtered_files = await migration_service._filter_incremental_files(files)
                
                assert len(filtered_files) == 1
                assert filtered_files[0] == json_file
    
    @pytest.mark.asyncio
    async def test_filter_incremental_files_with_existing(self, migration_service, temp_directory):
        """Test filtering incremental files when some files already exist."""
        # Create test files
        existing_file = temp_directory / "existing.json"
        with open(existing_file, 'w') as f:
            json.dump({"title": "Existing", "content": "Existing content"}, f)
        
        new_file = temp_directory / "new.json"
        with open(new_file, 'w') as f:
            json.dump({"title": "New", "content": "New content"}, f)
        
        files = [existing_file, new_file]
        
        with patch('app.services.migration_service.get_db_session'):
            with patch('app.services.migration_service.get_content_repository') as mock_repo:
                mock_content_repo = Mock()
                mock_repo.return_value = mock_content_repo
                
                def mock_get_by_metadata(field_name, field_value):
                    if "existing.json" in field_value:
                        return [Mock(id="existing-123")]
                    return []
                
                mock_content_repo.get_by_metadata_field.side_effect = mock_get_by_metadata
                mock_content_repo.get_by_hash.return_value = None
                
                filtered_files = await migration_service._filter_incremental_files(files)
                
                assert len(filtered_files) == 1
                assert filtered_files[0] == new_file
    
    @pytest.mark.asyncio
    async def test_run_integrity_checks_success(self, migration_service):
        """Test running integrity checks with successful results."""
        # Set up rollback data
        migration_service.rollback_data = {
            'migrated_items': {
                'content': ['content-1', 'content-2'],
                'knowledge': ['knowledge-1'],
                'synthesis': []
            }
        }
        
        with patch('app.services.migration_service.get_db_session'):
            with patch('app.services.migration_service.get_content_repository') as mock_content_repo:
                with patch('app.services.migration_service.get_knowledge_repository') as mock_knowledge_repo:
                    mock_content_repo_instance = Mock()
                    mock_content_repo.return_value = mock_content_repo_instance
                    mock_content_repo_instance.count_recent_items.return_value = 2
                    mock_content_repo_instance.count_duplicate_hashes.return_value = 0
                    
                    mock_knowledge_repo_instance = Mock()
                    mock_knowledge_repo.return_value = mock_knowledge_repo_instance
                    mock_knowledge_repo_instance.get.return_value = Mock(
                        source_content_id="content-1"
                    )
                    mock_content_repo_instance.get.return_value = Mock(id="content-1")
                    
                    stats = MigrationStats()
                    result = await migration_service._run_integrity_checks(stats)
                    
                    assert result['total_checks'] == 3
                    assert result['passed_checks'] == 3
                    assert result['failed_checks'] == 0
                    assert len(result['errors']) == 0
    
    @pytest.mark.asyncio
    async def test_run_integrity_checks_with_failures(self, migration_service):
        """Test running integrity checks with some failures."""
        # Set up rollback data
        migration_service.rollback_data = {
            'migrated_items': {
                'content': ['content-1', 'content-2'],
                'knowledge': ['knowledge-1'],
                'synthesis': []
            }
        }
        
        with patch('app.services.migration_service.get_db_session'):
            with patch('app.services.migration_service.get_content_repository') as mock_content_repo:
                with patch('app.services.migration_service.get_knowledge_repository') as mock_knowledge_repo:
                    mock_content_repo_instance = Mock()
                    mock_content_repo.return_value = mock_content_repo_instance
                    mock_content_repo_instance.count_recent_items.return_value = 1  # Less than expected
                    mock_content_repo_instance.count_duplicate_hashes.return_value = 2  # Duplicates found
                    
                    mock_knowledge_repo_instance = Mock()
                    mock_knowledge_repo.return_value = mock_knowledge_repo_instance
                    mock_knowledge_repo_instance.get.return_value = Mock(
                        source_content_id="content-1"
                    )
                    mock_content_repo_instance.get.return_value = Mock(id="content-1")
                    
                    stats = MigrationStats()
                    result = await migration_service._run_integrity_checks(stats)
                    
                    assert result['total_checks'] == 3
                    assert result['passed_checks'] == 1
                    assert result['failed_checks'] == 2
                    assert len(result['errors']) == 2
                    assert any("Content count mismatch" in error for error in result['errors'])
                    assert any("duplicate content items" in error for error in result['errors'])