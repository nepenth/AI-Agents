# JSON to Database Migration - Backup and Recovery Guide

## Table of Contents
- [Overview](#overview)
- [Backup System Architecture](#backup-system-architecture)
- [Backup Types and Components](#backup-types-and-components)
- [Creating Backups](#creating-backups)
- [Automated Backup Scheduling](#automated-backup-scheduling)
- [Backup Validation](#backup-validation)
- [Recovery Procedures](#recovery-procedures)
- [Retention Policies](#retention-policies)
- [Monitoring and Maintenance](#monitoring-and-maintenance)
- [CLI Tool Reference](#cli-tool-reference)
- [API Integration](#api-integration)
- [Troubleshooting](#troubleshooting)
- [Best Practices](#best-practices)

## Overview

The backup and recovery system provides comprehensive data protection for the Knowledge Base Agent's database and associated files. This system ensures business continuity and data integrity through automated backups, validation, and recovery capabilities.

### Key Features
- **Automated Scheduling**: Daily, weekly, and monthly backup cycles
- **Component Selection**: Granular control over what to backup
- **Validation**: Integrity checks for all backup components
- **Retention Policies**: Automatic cleanup of expired backups
- **Recovery Options**: Full or partial system restoration
- **CLI and API Access**: Multiple interfaces for backup management

### Backup Components
- **Database**: PostgreSQL dump with schema and data
- **JSON Files**: Legacy data files for rollback scenarios
- **Media Files**: Downloaded images, videos, and attachments
- **Logs**: Application and system logs
- **Configuration**: Agent configuration and settings

## Backup System Architecture

### Core Components

#### BackupManager
Central orchestrator for all backup operations:
```python
BackupManager:
├── create_backup()       # Create new backups
├── validate_backup()     # Verify backup integrity
├── restore_backup()      # Restore from backup
├── cleanup_expired()     # Remove old backups
└── schedule_automated()  # Start backup scheduler
```

#### Storage Structure
```
/backups/
├── daily_backup_20240115_120000/
│   ├── metadata.json
│   ├── database.sql
│   ├── json_files.tar.gz
│   ├── media_files.tar.gz
│   └── logs.tar.gz
├── weekly_backup_20240114_120000/
└── manual_backup_pre_migration/
```

#### Metadata Format
```json
{
  "backup_id": "daily_backup_20240115_120000",
  "backup_type": "automated",
  "created_at": "2024-01-15T12:00:00Z",
  "components": {
    "database": {
      "size": 157286400,
      "checksum": "sha256:abc123...",
      "compression": "gzip"
    },
    "json_files": {
      "size": 26214400,
      "checksum": "sha256:def456...",
      "compression": "gzip"
    }
  },
  "retention_until": "2024-02-15T12:00:00Z",
  "agent_version": "1.0.0",
  "database_version": "12.8"
}
```

## Backup Types and Components

### Backup Types

#### 1. Automated Backups
**Scheduled**: Daily, weekly, monthly
**Purpose**: Regular data protection
**Retention**: Based on retention policies
```bash
# Daily backups
daily_backup_YYYYMMDD_HHMMSS

# Weekly backups (Sundays)
weekly_backup_YYYYMMDD_HHMMSS

# Monthly backups (1st of month)
monthly_backup_YYYYMMDD_HHMMSS
```

#### 2. Manual Backups
**Triggered**: On-demand by user or system
**Purpose**: Pre-maintenance, testing, or milestone backups
**Retention**: Customizable
```bash
# User-initiated
manual_backup_description_timestamp

# Pre-migration
pre_migration_YYYYMMDD_HHMMSS

# Pre-maintenance
pre_maintenance_YYYYMMDD_HHMMSS
```

#### 3. Event-Triggered Backups
**Triggered**: Before major operations
**Purpose**: Rollback protection
**Retention**: Event-specific
```bash
# Before migration
pre_migration_backup_20240115_150000

# Before bulk operations
pre_bulk_op_backup_20240115_160000
```

### Backup Components

#### Database Component
```bash
Component: PostgreSQL Database
File: database.sql
Method: pg_dump with compression
Size: ~150MB (typical)
Contents:
- Schema definitions
- All table data
- Indexes and constraints
- Stored procedures
- User permissions
```

#### JSON Files Component
```bash
Component: Legacy JSON Files
File: json_files.tar.gz
Method: tar with gzip compression
Size: ~25MB (typical)
Contents:
- tweet_cache.json
- processed_tweets.json
- unprocessed_tweets.json
- categories.json
- processing_stats.json
- latest_run_stats.json
```

#### Media Files Component
```bash
Component: Downloaded Media
File: media_files.tar.gz
Method: tar with gzip compression
Size: Variable (1GB-10GB+)
Contents:
- Downloaded images
- Downloaded videos
- Profile pictures
- Media metadata
```

#### Logs Component
```bash
Component: Application Logs
File: logs.tar.gz
Method: tar with gzip compression
Size: ~10MB (typical)
Contents:
- Application logs
- Error logs
- Access logs
- Processing logs
```

#### Configuration Component
```bash
Component: System Configuration
File: config.tar.gz
Method: tar with gzip compression
Size: <1MB
Contents:
- config.py
- Environment files
- SSL certificates
- Service configurations
```

## Creating Backups

### Using the CLI Tool

#### Basic Backup Creation
```bash
# Create basic backup with database and JSON files
./backup_cli.py create --backup-id "manual_backup_$(date +%Y%m%d_%H%M%S)"

# Create full backup with all components
./backup_cli.py create --full --description "Complete system backup"

# Create backup with specific components
./backup_cli.py create --database --media --logs --backup-id "selective_backup"
```

#### Advanced Options
```bash
# Create backup with custom retention
./backup_cli.py create --retention-days 90 --description "Long-term backup"

# Create backup with compression level
./backup_cli.py create --compression-level 9 --backup-id "high_compression"

# Create backup to specific location
./backup_cli.py create --output-dir "/external/backups" --backup-id "external_backup"
```

### Using the API

#### Basic API Call
```python
import requests

# Create backup via API
response = requests.post('http://localhost:5000/backup/create', json={
    'backup_id': 'api_backup_20240115',
    'include_database': True,
    'include_json_files': True,
    'include_media': False,
    'include_logs': True,
    'description': 'API-created backup'
})

result = response.json()
print(f"Backup created: {result['data']['backup_id']}")
```

#### Programmatic Backup
```python
from knowledge_base_agent.backup_manager import BackupManager

# Initialize backup manager
backup_manager = BackupManager(config)

# Create backup
backup_result = backup_manager.create_backup(
    backup_id='programmatic_backup',
    include_database=True,
    include_json_files=True,
    include_media=True,
    include_logs=True,
    description='Programmatically created backup'
)

if backup_result.success:
    print(f"Backup created successfully: {backup_result.backup_id}")
    print(f"Size: {backup_result.total_size}")
    print(f"Duration: {backup_result.duration}")
else:
    print(f"Backup failed: {backup_result.error}")
```

### Pre-Migration Backup

Before running the migration, always create a comprehensive backup:

```bash
# Create pre-migration backup
./backup_cli.py create \
    --backup-id "pre_migration_$(date +%Y%m%d_%H%M%S)" \
    --full \
    --description "Backup before JSON to Database migration" \
    --retention-days 180
```

## Automated Backup Scheduling

### Configuration

#### Backup Schedule Configuration
```python
# config.py
BACKUP_CONFIG = {
    'enabled': True,
    'schedule': {
        'daily': {
            'time': '02:00',  # 2 AM
            'enabled': True,
            'components': ['database', 'json_files', 'logs']
        },
        'weekly': {
            'day': 'sunday',
            'time': '01:00',  # 1 AM on Sundays
            'enabled': True,
            'components': ['database', 'json_files', 'media', 'logs']
        },
        'monthly': {
            'day': 1,
            'time': '00:00',  # Midnight on 1st of month
            'enabled': True,
            'components': ['database', 'json_files', 'media', 'logs', 'config']
        }
    },
    'retention': {
        'daily': 30,    # Keep 30 daily backups
        'weekly': 12,   # Keep 12 weekly backups
        'monthly': 6,   # Keep 6 monthly backups
        'manual': 0     # Keep manual backups indefinitely (0 = no limit)
    }
}
```

#### Starting the Scheduler

**Via CLI:**
```bash
# Start backup scheduler
./backup_cli.py scheduler start

# Check scheduler status
./backup_cli.py scheduler status

# Stop scheduler
./backup_cli.py scheduler stop
```

**Via API:**
```bash
# Start scheduler
curl -X POST http://localhost:5000/backup/scheduler/start

# Check status
curl http://localhost:5000/backup/scheduler/status
```

**Programmatically:**
```python
from knowledge_base_agent.backup_manager import BackupManager

backup_manager = BackupManager(config)
backup_manager.schedule_automated_backups()
```

### Monitoring Scheduled Backups

#### Log Monitoring
```bash
# Monitor backup logs
tail -f /logs/backup.log

# Check for backup errors
grep -i error /logs/backup.log

# View backup schedule
./backup_cli.py scheduler status
```

#### Health Checks
```python
# Check backup system health
response = requests.get('http://localhost:5000/backup/status')
health = response.json()

print(f"Last backup: {health['data']['last_backup']}")
print(f"Failed backups (7 days): {health['data']['failed_backups_last_week']}")
print(f"Status: {health['data']['backup_system_status']}")
```

## Backup Validation

### Automatic Validation

All backups are automatically validated during creation:

```python
# Validation performed during backup creation
validation_checks = [
    'file_existence',      # Backup files exist
    'checksum_verification',  # SHA256 checksums match
    'compression_integrity',  # Archive files are valid
    'database_syntax',     # SQL dump is valid
    'metadata_consistency' # Metadata matches actual files
]
```

### Manual Validation

#### CLI Validation
```bash
# Validate specific backup
./backup_cli.py validate backup_20240115_120000

# Validate all backups
./backup_cli.py validate --all

# Deep validation (includes content checks)
./backup_cli.py validate backup_20240115_120000 --deep
```

#### API Validation
```bash
# Validate via API
curl -X POST http://localhost:5000/backup/backup_20240115_120000/validate
```

#### Validation Report
```json
{
  "backup_id": "backup_20240115_120000",
  "validation_result": {
    "is_valid": true,
    "components": {
      "database": {
        "file_exists": true,
        "checksum_valid": true,
        "sql_syntax_valid": true,
        "size_matches": true
      },
      "json_files": {
        "file_exists": true,
        "checksum_valid": true,
        "archive_valid": true,
        "content_parseable": true
      }
    },
    "validation_time": "2024-01-15T13:00:00Z",
    "validation_duration": "15 seconds"
  }
}
```

## Recovery Procedures

### Full System Recovery

#### Step 1: Identify Recovery Point
```bash
# List available backups
./backup_cli.py list --detailed

# Select appropriate backup based on:
# - Creation date
# - Validation status
# - Component completeness
```

#### Step 2: Stop Services
```bash
# Stop Knowledge Base Agent
sudo systemctl stop knowledge-base-agent

# Stop PostgreSQL (if restoring database)
sudo systemctl stop postgresql
```

#### Step 3: Execute Recovery
```bash
# Full system recovery
./backup_cli.py restore backup_20240115_120000 \
    --components database,json_files,media,logs \
    --create-rollback \
    --confirm
```

#### Step 4: Verify Recovery
```bash
# Start services
sudo systemctl start postgresql
sudo systemctl start knowledge-base-agent

# Verify system functionality
./backup_cli.py statistics
```

### Partial Recovery

#### Database-Only Recovery
```bash
# Restore only database
./backup_cli.py restore backup_20240115_120000 \
    --components database \
    --create-rollback \
    --confirm
```

#### Media Files Recovery
```bash
# Restore only media files
./backup_cli.py restore backup_20240115_120000 \
    --components media \
    --confirm
```

### Emergency Recovery

#### When Primary Backup Storage Fails
1. **Identify Alternative Backups**
   ```bash
   # Check external backup locations
   ls -la /external/backups/
   ls -la /remote/backups/
   ```

2. **Copy Backup to Primary Location**
   ```bash
   # Copy from external storage
   cp -r /external/backups/backup_20240115_120000 /backups/
   ```

3. **Validate and Restore**
   ```bash
   # Validate copied backup
   ./backup_cli.py validate backup_20240115_120000
   
   # Restore if valid
   ./backup_cli.py restore backup_20240115_120000 --confirm
   ```

### Rollback Procedures

#### Automatic Rollback Backup
When performing recovery, always create a rollback backup:
```bash
# Recovery with rollback backup creation
./backup_cli.py restore backup_20240115_120000 \
    --create-rollback \
    --rollback-id "rollback_$(date +%Y%m%d_%H%M%S)" \
    --confirm
```

#### Manual Rollback
If recovery causes issues, rollback to pre-recovery state:
```bash
# Restore from rollback backup
./backup_cli.py restore rollback_20240115_140000 --confirm
```

## Retention Policies

### Default Retention Policies

```python
DEFAULT_RETENTION = {
    'daily_backups': 30,     # 30 days
    'weekly_backups': 12,    # 12 weeks (3 months)
    'monthly_backups': 6,    # 6 months
    'manual_backups': 0,     # Indefinite (no automatic cleanup)
    'pre_migration': 180,    # 6 months
    'pre_maintenance': 90    # 3 months
}
```

### Customizing Retention

#### Via Configuration
```python
# config.py
BACKUP_RETENTION = {
    'daily': 45,      # Keep 45 daily backups
    'weekly': 24,     # Keep 24 weekly backups
    'monthly': 12,    # Keep 12 monthly backups
    'manual': 30,     # Keep manual backups for 30 days
    'critical': 0     # Keep critical backups indefinitely
}
```

#### Via CLI
```bash
# Set retention for specific backup type
./backup_cli.py retention --daily 45 --weekly 24 --monthly 12

# View current retention policies
./backup_cli.py retention --show
```

#### Via API
```bash
# Update retention policies
curl -X PUT http://localhost:5000/backup/retention-policies -H "Content-Type: application/json" -d '{
    "daily": 45,
    "weekly": 24,
    "monthly": 12
}'
```

### Manual Cleanup

#### Remove Expired Backups
```bash
# Clean up expired backups
./backup_cli.py cleanup

# Dry run (see what would be deleted)
./backup_cli.py cleanup --dry-run

# Force cleanup (skip confirmations)
./backup_cli.py cleanup --force
```

#### Remove Specific Backups
```bash
# Delete specific backup
./backup_cli.py delete backup_20240101_120000

# Delete multiple backups
./backup_cli.py delete backup_20240101_120000 backup_20240102_120000
```

## Monitoring and Maintenance

### Health Monitoring

#### Backup System Status
```bash
# Check overall backup health
./backup_cli.py status

# Detailed statistics
./backup_cli.py statistics
```

#### Key Metrics to Monitor
- **Last Successful Backup**: Should be within expected schedule
- **Failed Backup Count**: Should be zero or minimal
- **Storage Usage**: Monitor available disk space
- **Backup Size Trends**: Watch for unusual size changes
- **Validation Failures**: Check backup integrity

### Alerting

#### Configuration
```python
# config.py
BACKUP_ALERTS = {
    'enabled': True,
    'email': {
        'smtp_server': 'smtp.example.com',
        'recipients': ['admin@example.com'],
        'sender': 'backup-system@example.com'
    },
    'triggers': {
        'backup_failed': True,
        'validation_failed': True,
        'storage_low': True,          # <10% free space
        'retention_exceeded': True,   # Too many old backups
        'schedule_missed': True       # Backup didn't run on schedule
    }
}
```

#### Alert Examples
```
Subject: Backup Failed - Knowledge Base Agent
Body: The scheduled daily backup failed at 2024-01-15 02:00:00.
Error: Database connection timeout
Backup ID: daily_backup_20240115_020000
```

### Maintenance Tasks

#### Daily Maintenance
```bash
#!/bin/bash
# daily_backup_maintenance.sh

# Check backup system health
./backup_cli.py status

# Validate recent backups
./backup_cli.py validate --recent 3

# Clean up expired backups
./backup_cli.py cleanup --dry-run
```

#### Weekly Maintenance
```bash
#!/bin/bash
# weekly_backup_maintenance.sh

# Full validation of all backups
./backup_cli.py validate --all

# Storage usage report
./backup_cli.py statistics --storage

# Test restore procedure (to test environment)
./backup_cli.py restore latest_weekly --test-env --confirm
```

#### Monthly Maintenance
```bash
#!/bin/bash
# monthly_backup_maintenance.sh

# Review retention policies
./backup_cli.py retention --show

# Archive old backups to external storage
./backup_cli.py archive --older-than 90

# Performance optimization
./backup_cli.py optimize --compression --deduplication
```

## CLI Tool Reference

### backup_cli.py Commands

#### create
```bash
# Create backup
./backup_cli.py create [OPTIONS]

Options:
  --backup-id TEXT        Unique backup identifier
  --description TEXT      Backup description
  --database             Include database component
  --json-files           Include JSON files component
  --media                Include media files component
  --logs                 Include logs component
  --config               Include configuration component
  --full                 Include all components
  --output-dir PATH      Output directory for backup
  --compression-level INT Compression level (1-9)
  --retention-days INT   Custom retention period
```

#### list
```bash
# List backups
./backup_cli.py list [OPTIONS]

Options:
  --backup-type TEXT     Filter by backup type
  --detailed            Show detailed information
  --recent INT          Show only recent N backups
  --format TEXT         Output format (table, json, csv)
```

#### validate
```bash
# Validate backups
./backup_cli.py validate [BACKUP_ID] [OPTIONS]

Options:
  --all                 Validate all backups
  --recent INT          Validate recent N backups
  --deep                Perform deep validation
  --components TEXT     Validate specific components
```

#### restore
```bash
# Restore from backup
./backup_cli.py restore BACKUP_ID [OPTIONS]

Options:
  --components TEXT     Components to restore
  --create-rollback     Create rollback backup
  --rollback-id TEXT    Custom rollback backup ID
  --test-env            Restore to test environment
  --confirm             Skip confirmation prompts
```

#### delete
```bash
# Delete backups
./backup_cli.py delete BACKUP_ID [BACKUP_ID...] [OPTIONS]

Options:
  --force              Skip confirmation prompts
  --reason TEXT        Deletion reason for audit log
```

#### cleanup
```bash
# Clean up expired backups
./backup_cli.py cleanup [OPTIONS]

Options:
  --dry-run            Show what would be deleted
  --force              Skip confirmation prompts
  --older-than INT     Delete backups older than N days
```

#### statistics
```bash
# Show backup statistics
./backup_cli.py statistics [OPTIONS]

Options:
  --storage            Show storage usage details
  --performance        Show performance metrics
  --format TEXT        Output format (table, json)
```

### Exit Codes
- **0**: Success
- **1**: General error
- **2**: Backup creation failed
- **3**: Validation failed
- **4**: Restore failed
- **5**: Configuration error

## API Integration

### Backup API Endpoints

#### Create Backup
```http
POST /backup/create
Content-Type: application/json

{
  "backup_id": "api_backup_20240115",
  "include_database": true,
  "include_json_files": true,
  "include_media": false,
  "include_logs": true,
  "description": "API-created backup"
}
```

#### List Backups
```http
GET /backup/list?page=1&per_page=20&backup_type=automated
```

#### Get Backup Details
```http
GET /backup/backup_20240115_120000
```

#### Validate Backup
```http
POST /backup/backup_20240115_120000/validate
```

#### Restore Backup
```http
POST /backup/backup_20240115_120000/restore
Content-Type: application/json

{
  "components": ["database", "json_files"],
  "create_rollback_backup": true,
  "force_restore": false
}
```

#### Delete Backup
```http
DELETE /backup/backup_20240115_120000
```

#### Cleanup Expired Backups
```http
POST /backup/cleanup
Content-Type: application/json

{
  "dry_run": false,
  "force_cleanup": false
}
```

### Python Client Example
```python
import requests

class BackupAPIClient:
    def __init__(self, base_url):
        self.base_url = base_url
    
    def create_backup(self, backup_id=None, components=None, description=None):
        payload = {
            'include_database': True,
            'include_json_files': True,
            'include_media': False,
            'include_logs': True
        }
        
        if backup_id:
            payload['backup_id'] = backup_id
        if description:
            payload['description'] = description
        if components:
            for component in ['database', 'json_files', 'media', 'logs']:
                payload[f'include_{component}'] = component in components
        
        response = requests.post(f'{self.base_url}/backup/create', json=payload)
        return response.json()
    
    def list_backups(self, backup_type=None, page=1, per_page=20):
        params = {'page': page, 'per_page': per_page}
        if backup_type:
            params['backup_type'] = backup_type
        
        response = requests.get(f'{self.base_url}/backup/list', params=params)
        return response.json()
    
    def restore_backup(self, backup_id, components=None, create_rollback=True):
        payload = {
            'create_rollback_backup': create_rollback,
            'force_restore': False
        }
        
        if components:
            payload['components'] = components
        
        response = requests.post(
            f'{self.base_url}/backup/{backup_id}/restore',
            json=payload
        )
        return response.json()

# Usage
client = BackupAPIClient('http://localhost:5000')

# Create backup
result = client.create_backup(
    backup_id='api_test_backup',
    components=['database', 'json_files'],
    description='Test backup via API'
)

# List recent backups
backups = client.list_backups(backup_type='automated', per_page=10)

# Restore if needed
restore_result = client.restore_backup(
    'backup_20240115_120000',
    components=['database'],
    create_rollback=True
)
```

## Troubleshooting

### Common Issues

#### Backup Creation Fails

**Issue**: Backup creation returns error
**Symptoms**:
```
Error: Failed to create backup
Cause: Database connection timeout
```

**Solutions**:
1. Check database connectivity
2. Verify sufficient disk space
3. Check file permissions
4. Review PostgreSQL logs

```bash
# Check database connection
psql -h localhost -U knowledge_base_agent -d knowledge_base_db -c "SELECT 1;"

# Check disk space
df -h /backups

# Check permissions
ls -la /backups

# Test manual pg_dump
pg_dump -h localhost -U knowledge_base_agent knowledge_base_db > test_dump.sql
```

#### Validation Fails

**Issue**: Backup validation reports corruption
**Symptoms**:
```
Validation failed: Checksum mismatch
Component: database
Expected: abc123...
Actual: def456...
```

**Solutions**:
1. Re-create the backup
2. Check storage device integrity
3. Verify backup process logs
4. Test backup creation in different location

```bash
# Re-create backup
./backup_cli.py create --backup-id "replacement_backup" --full

# Check filesystem
fsck /dev/sdb1

# Test backup to different location
./backup_cli.py create --output-dir "/tmp/test_backup" --full
```

#### Restore Fails

**Issue**: Restore operation fails partway through
**Symptoms**:
```
Restore failed: PostgreSQL restore error
Error: relation "tweet_cache" already exists
```

**Solutions**:
1. Stop all services before restore
2. Drop database before restore
3. Use force restore option
4. Restore to test environment first

```bash
# Stop services
sudo systemctl stop knowledge-base-agent

# Drop and recreate database
sudo -u postgres dropdb knowledge_base_db
sudo -u postgres createdb knowledge_base_db

# Retry restore
./backup_cli.py restore backup_20240115_120000 --confirm
```

#### Storage Issues

**Issue**: Insufficient storage space
**Symptoms**:
```
Error: No space left on device
Failed to create backup archive
```

**Solutions**:
1. Clean up old backups
2. Move backups to external storage
3. Increase storage capacity
4. Adjust retention policies

```bash
# Clean up expired backups
./backup_cli.py cleanup --force

# Move old backups
mv /backups/old_backup_* /external/archive/

# Check storage usage
./backup_cli.py statistics --storage

# Reduce retention
./backup_cli.py retention --daily 14 --weekly 8 --monthly 3
```

### Performance Issues

#### Slow Backup Creation

**Possible Causes**:
- Large database size
- Slow storage device
- Network issues (if using remote storage)
- High system load

**Solutions**:
```bash
# Monitor backup progress
tail -f /logs/backup.log

# Check system resources
top
iostat 1

# Use lower compression for speed
./backup_cli.py create --compression-level 1

# Schedule during off-peak hours
crontab -e
# 0 2 * * * /path/to/backup_cli.py create --full
```

#### Slow Restore Operations

**Possible Causes**:
- Large backup size
- Slow decompression
- Database import bottlenecks

**Solutions**:
```bash
# Monitor restore progress
tail -f /logs/restore.log

# Use parallel restore for PostgreSQL
pg_restore --jobs 4 --dbname knowledge_base_db backup.sql

# Restore to faster storage first
./backup_cli.py restore backup_id --output-dir "/tmp/fast_storage"
```

### Monitoring and Alerts

#### Log Analysis
```bash
# Check backup logs for errors
grep -i error /logs/backup.log

# Monitor backup timing
grep "Backup completed" /logs/backup.log | tail -20

# Check validation results
grep "Validation" /logs/backup.log
```

#### Health Checks
```bash
# Daily health check script
#!/bin/bash
HEALTH=$(./backup_cli.py status --json)
LAST_BACKUP=$(echo $HEALTH | jq -r '.last_backup')
FAILED_COUNT=$(echo $HEALTH | jq -r '.failed_backups_last_week')

if [ "$FAILED_COUNT" -gt 0 ]; then
    echo "WARNING: $FAILED_COUNT failed backups in last week"
fi

# Check if last backup is too old (>25 hours)
LAST_BACKUP_EPOCH=$(date -d "$LAST_BACKUP" +%s)
NOW_EPOCH=$(date +%s)
HOURS_SINCE=$((($NOW_EPOCH - $LAST_BACKUP_EPOCH) / 3600))

if [ "$HOURS_SINCE" -gt 25 ]; then
    echo "WARNING: Last backup was $HOURS_SINCE hours ago"
fi
```

## Best Practices

### Backup Strategy

#### 3-2-1 Rule
- **3 copies** of important data
- **2 different** storage media types
- **1 offsite** backup copy

```bash
# Local backup
./backup_cli.py create --full --output-dir "/backups/local"

# Network attached storage
./backup_cli.py create --full --output-dir "/mnt/nas/backups"

# Cloud/offsite backup
./backup_cli.py create --full --output-dir "/remote/cloud/backups"
```

#### Testing Backups

**Regular Testing Schedule**:
- **Weekly**: Validate all recent backups
- **Monthly**: Test database restore to staging environment
- **Quarterly**: Full disaster recovery test

```bash
# Weekly validation
./backup_cli.py validate --recent 7

# Monthly staging restore
./backup_cli.py restore latest_monthly --test-env --confirm

# Quarterly DR test
./backup_cli.py restore backup_20240101_000000 --full-dr-test
```

### Security Considerations

#### Backup Encryption
```bash
# Encrypt backups at rest
./backup_cli.py create --encrypt --key-file "/secure/backup.key"

# Use encrypted storage
mount -t ext4 -o encryption=aes256 /dev/sdb1 /backups
```

#### Access Control
```bash
# Restrict backup directory permissions
chmod 700 /backups
chown backup-user:backup-group /backups

# Use dedicated backup user
sudo useradd -m -s /bin/bash backup-user
sudo usermod -aG sudo backup-user
```

### Automation Best Practices

#### Monitoring Integration
```python
# Integration with monitoring systems
import requests

def send_backup_metrics(backup_result):
    metrics = {
        'backup_success': 1 if backup_result.success else 0,
        'backup_duration': backup_result.duration,
        'backup_size': backup_result.total_size
    }
    
    # Send to monitoring system (Prometheus, InfluxDB, etc.)
    requests.post('http://monitoring:9090/metrics', json=metrics)
```

#### Documentation
- **Maintain runbooks** for recovery procedures
- **Document custom retention policies** and reasons
- **Keep inventory** of backup locations and access methods
- **Update procedures** when system changes occur

#### Change Management
- **Test backup procedures** before implementing changes
- **Version control** backup scripts and configurations
- **Coordinate with application deployments**
- **Maintain rollback procedures** for backup system changes

---

**Backup and Recovery Guide Status**: ✅ Complete - All procedures documented and tested
**Next Steps**: Implement monitoring integration and staff training 