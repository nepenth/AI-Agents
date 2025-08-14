# Data Migration System

This document describes the comprehensive data migration system for migrating legacy data to the new unified AI Agent Backend architecture.

## Overview

The migration system provides a robust, scalable solution for migrating data from legacy systems to the new unified database model. It supports various data formats, provides comprehensive validation, and includes rollback capabilities.

## Features

### Core Features
- **Multi-format Support**: JSON, Markdown, plain text, and CSV files
- **Data Validation**: Comprehensive validation with configurable rules
- **Batch Processing**: Efficient processing of large datasets
- **Backup & Rollback**: Automatic backups with rollback capabilities
- **Progress Tracking**: Real-time progress monitoring
- **Error Handling**: Detailed error reporting and recovery

### Advanced Features
- **Incremental Migration**: Skip already migrated files
- **Large File Handling**: Configurable file size limits
- **Parallel Processing**: Multi-threaded processing for performance
- **Data Integrity Checks**: Post-migration validation
- **Comprehensive Reporting**: Detailed migration reports

## Architecture

### Components

1. **MigrationService**: Core service handling migration logic
2. **LegacyDataParser**: Parses various legacy data formats
3. **DataValidator**: Validates data integrity and format
4. **Migration API**: REST endpoints for migration operations
5. **Migration CLI**: Command-line interface for migrations
6. **Migration Models**: Database models for tracking migrations

### Database Schema

The migration system uses several tables to track migration progress:

- `migration_runs`: Tracks individual migration executions
- `migration_items`: Tracks individual migrated items
- `data_integrity_checks`: Records integrity check results
- `legacy_mappings`: Maps legacy IDs to new IDs
- `migration_backups`: Tracks backup files

## Usage

### API Usage

#### Start Migration
```bash
POST /api/v1/migration/start
{
  "source_directory": "/path/to/legacy/data",
  "backup_directory": "/path/to/backups",
  "batch_size": 100,
  "validate_data": true,
  "create_backups": true,
  "dry_run": false,
  "incremental": false,
  "max_file_size": 52428800,
  "skip_large_files": true,
  "parallel_processing": false,
  "max_workers": 4
}
```

#### Check Migration Status
```bash
GET /api/v1/migration/status/{migration_id}
```

#### Validate Migration Data
```bash
POST /api/v1/migration/validate
{
  "source_directory": "/path/to/legacy/data",
  "backup_directory": "/path/to/backups"
}
```

#### Rollback Migration
```bash
POST /api/v1/migration/rollback/{migration_id}
```

### CLI Usage

#### Basic Migration
```bash
python -m app.cli.migration migrate \
  --source /path/to/legacy/data \
  --backup /path/to/backups \
  --batch-size 100 \
  --verbose
```

#### Incremental Migration
```bash
python -m app.cli.migration migrate \
  --source /path/to/legacy/data \
  --backup /path/to/backups \
  --incremental \
  --verbose
```

#### Validate Data
```bash
python -m app.cli.migration validate \
  --source /path/to/legacy/data \
  --output validation_report.json \
  --verbose
```

#### Check Incremental Status
```bash
python -m app.cli.migration check-incremental \
  --source /path/to/legacy/data \
  --verbose
```

#### Analyze Legacy Data
```bash
python -m app.cli.migration analyze \
  --source /path/to/legacy/data \
  --output analysis_report.json
```

#### Rollback Migration
```bash
python -m app.cli.migration rollback \
  --rollback-file /path/to/rollback_info.json \
  --confirm
```

## Configuration Options

### MigrationConfig Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `source_directory` | str | Required | Source directory containing legacy data |
| `backup_directory` | str | Required | Directory for backups and reports |
| `batch_size` | int | 100 | Number of files to process in each batch |
| `validate_data` | bool | true | Whether to validate data before migration |
| `create_backups` | bool | true | Whether to create backups |
| `preserve_timestamps` | bool | true | Whether to preserve original timestamps |
| `dry_run` | bool | false | Whether to perform a dry run |
| `incremental` | bool | false | Whether to perform incremental migration |
| `max_file_size` | int | 50MB | Maximum file size to process |
| `skip_large_files` | bool | true | Whether to skip files larger than max_file_size |
| `parallel_processing` | bool | false | Whether to use parallel processing |
| `max_workers` | int | 4 | Maximum number of worker threads |

## Data Formats

### Supported Input Formats

#### JSON Format
```json
{
  "id": "legacy-123",
  "title": "Article Title",
  "content": "Article content...",
  "url": "https://example.com/article",
  "type": "article",
  "created_at": "2024-01-01T00:00:00Z",
  "tags": ["tag1", "tag2"],
  "category": "technology",
  "metadata": {
    "author": "John Doe",
    "source": "blog"
  }
}
```

#### Markdown Format
```markdown
---
title: Article Title
url: https://example.com/article
category: technology
tags: [tag1, tag2]
---

# Article Title

Article content with **markdown** formatting.

- List item 1
- List item 2
```

#### Plain Text Format
```
Simple plain text content that will be migrated
with the filename as the title.
```

### Output Format

All migrated data is stored in the unified database schema:

- **ContentItem**: Main content storage
- **KnowledgeItem**: Knowledge base entries (for substantial content)
- **Embeddings**: Vector embeddings for search

## Migration Process

### Phase 1: Validation
1. Validate source directory exists
2. Check file permissions
3. Analyze file formats and sizes
4. Estimate migration time and resources

### Phase 2: Backup
1. Create backup directory
2. Export existing database content
3. Generate backup checksums
4. Store rollback information

### Phase 3: Processing
1. Discover files to migrate
2. Filter for incremental migration (if enabled)
3. Process files in batches
4. Parse and validate each file
5. Create database entries
6. Track migration progress

### Phase 4: Integrity Checks
1. Verify migrated item counts
2. Check for duplicate content
3. Validate relationships
4. Generate integrity report

### Phase 5: Reporting
1. Generate migration statistics
2. Create detailed error reports
3. Save rollback information
4. Generate human-readable summary

## Error Handling

### Error Types

1. **Validation Errors**: Invalid data format or content
2. **Processing Errors**: File access or parsing issues
3. **Database Errors**: Database connection or constraint violations
4. **System Errors**: Disk space, memory, or permission issues

### Error Recovery

- **Automatic Retry**: Transient errors are automatically retried
- **Batch Isolation**: Errors in one batch don't affect others
- **Detailed Logging**: All errors are logged with context
- **Rollback Support**: Failed migrations can be rolled back

## Performance Considerations

### Optimization Strategies

1. **Batch Processing**: Process files in configurable batches
2. **Memory Management**: Regular garbage collection between batches
3. **Parallel Processing**: Multi-threaded processing for large datasets
4. **Incremental Migration**: Skip already processed files
5. **File Size Limits**: Skip or handle large files separately

### Performance Metrics

- **Throughput**: Files processed per minute
- **Memory Usage**: Peak memory consumption
- **Database Performance**: Query execution times
- **Error Rate**: Percentage of failed migrations

## Monitoring and Observability

### Metrics Collected

- Migration progress percentage
- Files processed vs. total files
- Success/failure rates
- Processing speed (files/minute)
- Memory and CPU usage
- Database connection pool status

### Logging

All migration activities are logged with structured logging:

```python
logger.info("Migration started", extra={
    "migration_id": migration_id,
    "source_directory": config.source_directory,
    "total_files": stats.total_files
})
```

### Real-time Updates

Migration progress is broadcast via WebSocket for real-time monitoring in the frontend.

## Security Considerations

### Data Protection

1. **Backup Encryption**: Backups can be encrypted
2. **Access Control**: Admin-only migration operations
3. **Audit Logging**: All migration activities are audited
4. **Data Validation**: Input sanitization and validation

### Best Practices

1. **Test Migrations**: Always test with a subset of data first
2. **Backup Verification**: Verify backups before starting migration
3. **Rollback Planning**: Have rollback procedures ready
4. **Resource Monitoring**: Monitor system resources during migration

## Troubleshooting

### Common Issues

#### Migration Fails to Start
- Check source directory permissions
- Verify backup directory is writable
- Ensure database connectivity

#### High Memory Usage
- Reduce batch size
- Disable parallel processing
- Enable large file skipping

#### Slow Performance
- Enable parallel processing
- Increase batch size
- Check database performance

#### Validation Errors
- Review error logs for specific issues
- Use validation-only mode to identify problems
- Fix data format issues before migration

### Debug Commands

```bash
# Check what files would be migrated
python -m app.cli.migration check-incremental --source /path/to/data --verbose

# Validate data without migration
python -m app.cli.migration validate --source /path/to/data --verbose

# Analyze data structure
python -m app.cli.migration analyze --source /path/to/data --verbose

# Dry run migration
python -m app.cli.migration migrate --source /path/to/data --backup /tmp --dry-run --verbose
```

## API Reference

### Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/migration/validate` | Validate migration data |
| POST | `/api/v1/migration/start` | Start migration process |
| GET | `/api/v1/migration/status/{id}` | Get migration status |
| GET | `/api/v1/migration/history` | Get migration history |
| POST | `/api/v1/migration/rollback/{id}` | Rollback migration |
| DELETE | `/api/v1/migration/cleanup/{id}` | Cleanup migration data |
| GET | `/api/v1/migration/stats` | Get migration statistics |
| GET | `/api/v1/migration/export` | Export current data |
| POST | `/api/v1/migration/import` | Import data from backup |

### Response Formats

All API responses follow a consistent format:

```json
{
  "success": true,
  "message": "Operation completed successfully",
  "data": {
    // Response-specific data
  },
  "timestamp": "2024-01-01T12:00:00Z"
}
```

Error responses:

```json
{
  "success": false,
  "error": "validation_error",
  "message": "Invalid request data",
  "details": {
    "field_errors": {
      "source_directory": ["Field is required"]
    }
  },
  "timestamp": "2024-01-01T12:00:00Z"
}
```

## Examples

### Complete Migration Workflow

1. **Analyze Legacy Data**
```bash
python -m app.cli.migration analyze --source /legacy/data --output analysis.json
```

2. **Validate Data**
```bash
python -m app.cli.migration validate --source /legacy/data --output validation.json
```

3. **Dry Run Migration**
```bash
python -m app.cli.migration migrate --source /legacy/data --backup /backups --dry-run --verbose
```

4. **Actual Migration**
```bash
python -m app.cli.migration migrate --source /legacy/data --backup /backups --verbose
```

5. **Check Results**
```bash
# View migration report
cat /backups/migration_summary.txt

# Check database
curl -H "Authorization: Bearer $TOKEN" http://localhost:8000/api/v1/content/items
```

### Incremental Migration

```bash
# Initial migration
python -m app.cli.migration migrate --source /legacy/data --backup /backups

# Later, migrate only new files
python -m app.cli.migration migrate --source /legacy/data --backup /backups --incremental
```

This migration system provides a comprehensive, robust solution for migrating legacy data while maintaining data integrity and providing full observability throughout the process.