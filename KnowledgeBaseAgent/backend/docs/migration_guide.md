# Data Migration Guide

This guide covers the data migration system for migrating from legacy data formats to the new unified model.

## Overview

The migration system provides comprehensive tools for:
- Migrating legacy data to the new unified content model
- Validating data integrity during migration
- Creating backups and rollback capabilities
- Incremental migration support for large datasets
- Comprehensive reporting and monitoring

## Migration Process

### 1. Pre-Migration Analysis

Before starting a migration, analyze your legacy data:

```bash
python -m app.cli.migration analyze --source /path/to/legacy/data --output analysis_report.json
```

This will provide:
- File count and types
- Size distribution
- Directory structure analysis
- Potential issues identification

### 2. Data Validation

Validate your data before migration:

```bash
python -m app.cli.migration validate --source /path/to/legacy/data --output validation_report.json
```

This checks for:
- Required fields presence
- Data format validity
- Content size limits
- URL format validation

### 3. Migration Execution

#### Dry Run (Recommended First)

```bash
python -m app.cli.migration migrate \
  --source /path/to/legacy/data \
  --backup /path/to/backup \
  --dry-run \
  --verbose
```

#### Actual Migration

```bash
python -m app.cli.migration migrate \
  --source /path/to/legacy/data \
  --backup /path/to/backup \
  --batch-size 100 \
  --verbose
```

### 4. Post-Migration Verification

After migration, verify the results:
- Check migration statistics
- Review error logs
- Validate data integrity
- Test application functionality

## Supported Data Formats

### JSON Files
```json
{
  "id": "unique-id",
  "title": "Content Title",
  "content": "Content body text",
  "url": "https://source.url",
  "type": "article",
  "created_at": "2024-01-01T00:00:00Z",
  "tags": ["tag1", "tag2"],
  "category": "technology",
  "metadata": {
    "additional": "data"
  }
}
```

### Markdown Files
```markdown
---
title: Content Title
url: https://source.url
category: documentation
tags: [markdown, docs]
---

# Content Title

Content body in **markdown** format.
```

### Plain Text Files
Simple text files are imported with the filename as title and content as-is.

## Migration Configuration

### Configuration Options

- `source_directory`: Path to legacy data
- `backup_directory`: Path for backups and reports
- `batch_size`: Number of files to process per batch (default: 100)
- `validate_data`: Enable data validation (default: true)
- `create_backups`: Create backups before migration (default: true)
- `preserve_timestamps`: Preserve original timestamps (default: true)
- `dry_run`: Perform dry run without actual migration (default: false)

### API Usage

```python
from app.services.migration_service import get_migration_service, MigrationConfig

migration_service = get_migration_service()

config = MigrationConfig(
    source_directory="/path/to/legacy/data",
    backup_directory="/path/to/backup",
    batch_size=50,
    validate_data=True,
    create_backups=True,
    dry_run=False
)

result = await migration_service.migrate_legacy_data(config)
```

## Data Mapping

### Legacy to New Model Mapping

| Legacy Field | New Field | Notes |
|--------------|-----------|-------|
| `id` | `metadata.legacy_id` | Preserved for reference |
| `title` | `title` | Direct mapping |
| `content` | `content` | Direct mapping |
| `url` | `source_url` | Direct mapping |
| `type` | `content_type` | Direct mapping |
| `created_at` | `metadata.legacy_created_at` | Preserved in metadata |
| `tags` | `metadata.legacy_tags` | Preserved in metadata |
| `category` | `metadata.legacy_category` | Used for categorization |

### Content Type Mapping

| Legacy Type | New Content Type |
|-------------|------------------|
| `article` | `text` |
| `blog_post` | `text` |
| `documentation` | `markdown` |
| `note` | `text` |
| `webpage` | `html` |

## Error Handling

### Common Errors

1. **Missing Required Fields**
   - Error: "Missing required field: title"
   - Solution: Ensure all files have required fields

2. **Invalid URL Format**
   - Error: "Invalid URL format: not-a-url"
   - Solution: Fix URL formats or remove invalid URLs

3. **Content Too Large**
   - Error: "Content too long: 2000000 > 1000000"
   - Solution: Split large content or increase limits

4. **File Parse Errors**
   - Error: "Could not parse file: invalid.json"
   - Solution: Fix file format or exclude from migration

### Error Recovery

- Review error logs in migration reports
- Fix data issues and re-run migration
- Use incremental migration for partial fixes
- Rollback if necessary and retry

## Rollback Procedures

### Automatic Rollback

```bash
python -m app.cli.migration rollback --rollback-file /path/to/rollback_info.json --confirm
```

### Manual Rollback

1. Stop application
2. Restore database from backup
3. Restore file system from backup
4. Restart application
5. Verify system state

## Performance Considerations

### Large Dataset Migration

For datasets with >10,000 files:
- Use smaller batch sizes (50-100)
- Enable incremental migration
- Monitor system resources
- Consider off-peak migration times

### Memory Usage

- Batch processing limits memory usage
- Large files are processed individually
- Monitor memory consumption during migration

### Database Performance

- Migration creates database load
- Consider read replicas during migration
- Monitor database connections
- Use connection pooling

## Monitoring and Reporting

### Migration Reports

Reports include:
- Total files processed
- Success/failure counts
- Processing time
- Error details
- Performance metrics

### Real-time Monitoring

- WebSocket progress updates
- API status endpoints
- Log file monitoring
- System resource monitoring

## Best Practices

### Pre-Migration

1. **Backup Everything**
   - Database backup
   - File system backup
   - Configuration backup

2. **Test Migration**
   - Use dry run mode
   - Test with sample data
   - Validate results

3. **Plan Downtime**
   - Schedule maintenance window
   - Notify users
   - Prepare rollback plan

### During Migration

1. **Monitor Progress**
   - Watch system resources
   - Monitor error rates
   - Check log files

2. **Be Prepared to Stop**
   - Have stop procedures ready
   - Monitor for critical errors
   - Be ready to rollback

### Post-Migration

1. **Verify Results**
   - Check data integrity
   - Test application functionality
   - Validate user workflows

2. **Clean Up**
   - Archive migration logs
   - Clean temporary files
   - Update documentation

## Troubleshooting

### Common Issues

1. **Migration Stuck**
   - Check system resources
   - Review error logs
   - Consider batch size reduction

2. **High Error Rate**
   - Review data validation
   - Check file formats
   - Fix data issues

3. **Performance Issues**
   - Reduce batch size
   - Check database performance
   - Monitor memory usage

### Support

For migration issues:
1. Check migration logs
2. Review error reports
3. Consult troubleshooting guide
4. Contact system administrator

## API Reference

### Migration Endpoints

- `POST /api/v1/migration/validate` - Validate migration data
- `POST /api/v1/migration/start` - Start migration
- `GET /api/v1/migration/status/{id}` - Get migration status
- `GET /api/v1/migration/history` - Get migration history
- `POST /api/v1/migration/rollback/{id}` - Rollback migration
- `DELETE /api/v1/migration/cleanup/{id}` - Cleanup migration data

### CLI Commands

- `migration analyze` - Analyze legacy data
- `migration validate` - Validate migration data
- `migration migrate` - Execute migration
- `migration rollback` - Rollback migration

## Security Considerations

### Data Protection

- Backups are encrypted
- Access controls on migration endpoints
- Audit logging for all operations
- Secure temporary file handling

### Access Control

- Admin-only migration operations
- API key authentication supported
- Role-based permissions
- Audit trail maintenance

## Compliance

### Data Retention

- Migration logs retained for audit
- Backup retention policies
- Data lineage tracking
- Compliance reporting

### Privacy

- PII handling during migration
- Data anonymization options
- GDPR compliance considerations
- Data subject rights support