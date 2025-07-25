# JSON to Database Migration - Troubleshooting and Maintenance Guide

## Table of Contents
- [Overview](#overview)
- [Migration Issues](#migration-issues)
- [Database Performance](#database-performance)
- [Repository Layer Issues](#repository-layer-issues)
- [API and Frontend Issues](#api-and-frontend-issues)
- [State Manager Issues](#state-manager-issues)
- [Backup and Recovery Issues](#backup-and-recovery-issues)
- [System Monitoring](#system-monitoring)
- [Performance Optimization](#performance-optimization)
- [Routine Maintenance](#routine-maintenance)
- [Emergency Procedures](#emergency-procedures)
- [Diagnostic Tools](#diagnostic-tools)
- [Log Analysis](#log-analysis)
- [Preventive Measures](#preventive-measures)

## Overview

This guide provides comprehensive troubleshooting and maintenance procedures for the JSON to Database Migration system. It covers common issues, diagnostic procedures, performance optimization, and ongoing maintenance tasks to ensure system reliability and optimal performance.

### Quick Reference
- **Emergency Contact**: System Administrator
- **Log Locations**: `/logs/` directory
- **Backup Location**: `/backups/` directory
- **Configuration**: `config.py`
- **Database**: PostgreSQL on localhost:5432

### Issue Severity Levels
- **Critical**: System down, data loss risk
- **High**: Major functionality impaired
- **Medium**: Some features affected
- **Low**: Minor issues, cosmetic problems

## Migration Issues

### Migration Fails to Start

#### Symptoms
```
Error: Migration cannot proceed
Cause: Database connection failed
Details: Connection to localhost:5432 refused
```

#### Diagnostic Steps
```bash
# 1. Check PostgreSQL service
sudo systemctl status postgresql

# 2. Test database connection
psql -h localhost -U knowledge_base_agent -d knowledge_base_db -c "SELECT 1;"

# 3. Check database configuration
cat config.py | grep DATABASE

# 4. Verify database exists
sudo -u postgres psql -l | grep knowledge_base_db
```

#### Solutions
```bash
# Start PostgreSQL if stopped
sudo systemctl start postgresql
sudo systemctl enable postgresql

# Create database if missing
sudo -u postgres createdb knowledge_base_db
sudo -u postgres createuser knowledge_base_agent

# Grant permissions
sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE knowledge_base_db TO knowledge_base_agent;"

# Test connection again
./run_json_migration.py --validate-only
```

### Partial Migration Completion

#### Symptoms
```
Migration completed with errors
Total records: 15,000
Migrated: 12,847
Failed: 2,153
```

#### Diagnostic Steps
```bash
# 1. Check migration logs
tail -100 /logs/migration.log

# 2. Examine failed records
grep "ERROR" /logs/migration.log | head -20

# 3. Check database constraints
psql -d knowledge_base_db -c "\d tweet_cache"

# 4. Validate JSON file format
python3 -c "import json; json.load(open('data/tweet_cache.json'))"
```

#### Solutions
```bash
# Fix JSON format issues
python3 -c "
import json
with open('data/tweet_cache.json', 'r') as f:
    data = json.load(f)
with open('data/tweet_cache_fixed.json', 'w') as f:
    json.dump(data, f, indent=2)
"

# Resume migration with fixed data
./run_json_migration.py --migration-id resume_$(date +%Y%m%d_%H%M%S)

# Manual data repair for specific records
psql -d knowledge_base_db -c "
UPDATE tweet_cache 
SET content_data = '{\"text\": \"Repaired tweet\"}'::jsonb 
WHERE content_data IS NULL;
"
```

### Data Validation Failures

#### Symptoms
```
Validation failed: Data integrity check failed
Issue: Tweet count mismatch
Expected: 15,000
Found: 14,847
```

#### Diagnostic Steps
```bash
# 1. Count records in source files
jq 'keys | length' data/tweet_cache.json

# 2. Count records in database
psql -d knowledge_base_db -c "SELECT COUNT(*) FROM tweet_cache;"

# 3. Find missing records
python3 -c "
import json
import psycopg2

# Load JSON data
with open('data/tweet_cache.json', 'r') as f:
    json_data = json.load(f)

# Connect to database
conn = psycopg2.connect('postgresql://knowledge_base_agent:password@localhost/knowledge_base_db')
cur = conn.cursor()

# Get database tweet IDs
cur.execute('SELECT tweet_id FROM tweet_cache')
db_tweets = set(row[0] for row in cur.fetchall())

# Find missing tweets
json_tweets = set(json_data.keys())
missing = json_tweets - db_tweets

print(f'Missing tweets: {len(missing)}')
for tweet_id in list(missing)[:10]:
    print(f'  {tweet_id}')
"
```

#### Solutions
```bash
# Re-run migration for missing records only
python3 -c "
import json
import psycopg2
from knowledge_base_agent.json_to_db_migrator import JsonToDbMigrator

# Initialize migrator
config = Config()
migrator = JsonToDbMigrator(config)

# Migrate only missing records
migrator.migrate_missing_tweets()
"

# Force validation to pass if differences are acceptable
./run_json_migration.py --migration-id recovery_migration --force
```

## Database Performance

### Slow Query Performance

#### Symptoms
```
API response time: >5 seconds
Database CPU usage: >80%
Query execution time: >1000ms
```

#### Diagnostic Steps
```sql
-- 1. Check slow queries
SELECT query, mean_time, calls 
FROM pg_stat_statements 
ORDER BY mean_time DESC 
LIMIT 10;

-- 2. Check table sizes
SELECT 
    schemaname,
    tablename,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) as size
FROM pg_tables 
WHERE schemaname = 'public'
ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;

-- 3. Check index usage
SELECT 
    indexrelname,
    idx_tup_read,
    idx_tup_fetch,
    idx_scan
FROM pg_stat_user_indexes
ORDER BY idx_scan DESC;

-- 4. Check for missing indexes
SELECT 
    schemaname,
    tablename,
    attname,
    n_distinct,
    correlation
FROM pg_stats
WHERE schemaname = 'public'
AND n_distinct > 100;
```

#### Solutions
```sql
-- Create missing indexes
CREATE INDEX CONCURRENTLY idx_tweet_cache_created_at ON tweet_cache(created_at);
CREATE INDEX CONCURRENTLY idx_tweet_cache_updated_at ON tweet_cache(updated_at);
CREATE INDEX CONCURRENTLY idx_tweet_processing_queue_status ON tweet_processing_queue(status);

-- Optimize full-text search
CREATE INDEX CONCURRENTLY idx_tweet_cache_content_gin 
ON tweet_cache 
USING gin((content_data->>'text') gin_trgm_ops);

-- Update table statistics
ANALYZE tweet_cache;
ANALYZE tweet_processing_queue;

-- Vacuum tables
VACUUM ANALYZE tweet_cache;
VACUUM ANALYZE tweet_processing_queue;
```

### Connection Pool Exhaustion

#### Symptoms
```
Error: connection pool exhausted
Max connections: 20
Active connections: 20
Waiting: 15
```

#### Diagnostic Steps
```bash
# 1. Check active connections
psql -d knowledge_base_db -c "
SELECT 
    count(*) as total_connections,
    count(*) FILTER (WHERE state = 'active') as active,
    count(*) FILTER (WHERE state = 'idle') as idle
FROM pg_stat_activity 
WHERE datname = 'knowledge_base_db';
"

# 2. Check connection pool configuration
grep -A 10 "DATABASE_CONFIG" config.py

# 3. Monitor connection usage
watch -n 1 "psql -d knowledge_base_db -c \"SELECT count(*) FROM pg_stat_activity WHERE datname = 'knowledge_base_db';\""
```

#### Solutions
```python
# Increase pool size in config.py
DATABASE_CONFIG = {
    'pool_size': 30,        # Increased from 20
    'max_overflow': 40,     # Increased from 20
    'pool_timeout': 60,     # Increased timeout
    'pool_recycle': 3600,
    'pool_pre_ping': True   # Enable connection validation
}

# Implement connection pooling monitoring
def monitor_connection_pool():
    engine = get_database_engine()
    pool = engine.pool
    
    print(f"Pool size: {pool.size()}")
    print(f"Active connections: {pool.checkedout()}")
    print(f"Available connections: {pool.checkedin()}")
    print(f"Overflow: {pool.overflow()}")
```

### Database Deadlocks

#### Symptoms
```
Error: deadlock detected
Detail: Process 1234 waits for ShareLock on transaction 5678
Process 5678 waits for ShareLock on transaction 1234
```

#### Diagnostic Steps
```sql
-- Check for deadlocks
SELECT 
    deadlocks,
    temp_files,
    temp_bytes
FROM pg_stat_database 
WHERE datname = 'knowledge_base_db';

-- Monitor lock waits
SELECT 
    blocked_locks.pid AS blocked_pid,
    blocked_activity.usename AS blocked_user,
    blocking_locks.pid AS blocking_pid,
    blocking_activity.usename AS blocking_user,
    blocked_activity.query AS blocked_statement,
    blocking_activity.query AS blocking_statement
FROM pg_catalog.pg_locks blocked_locks
JOIN pg_catalog.pg_stat_activity blocked_activity ON blocked_activity.pid = blocked_locks.pid
JOIN pg_catalog.pg_locks blocking_locks ON blocking_locks.locktype = blocked_locks.locktype
JOIN pg_catalog.pg_stat_activity blocking_activity ON blocking_activity.pid = blocking_locks.pid
WHERE NOT blocked_locks.granted;
```

#### Solutions
```python
# Implement retry logic for deadlocks
from sqlalchemy.exc import OperationalError
import time
import random

def execute_with_retry(func, max_retries=3):
    for attempt in range(max_retries):
        try:
            return func()
        except OperationalError as e:
            if 'deadlock detected' in str(e) and attempt < max_retries - 1:
                wait_time = (2 ** attempt) + random.uniform(0, 1)
                time.sleep(wait_time)
                continue
            raise

# Use consistent lock ordering
def update_tweet_and_queue(tweet_id, tweet_data, queue_status):
    with transaction() as tx:
        # Always lock in same order: tweet_cache, then queue
        tweet = tx.query(TweetCache).filter(
            TweetCache.tweet_id == tweet_id
        ).with_for_update().first()
        
        queue_entry = tx.query(TweetProcessingQueue).filter(
            TweetProcessingQueue.tweet_id == tweet_id
        ).with_for_update().first()
        
        # Update both records
        tweet.content_data = tweet_data
        queue_entry.status = queue_status
```

## Repository Layer Issues

### Repository Connection Failures

#### Symptoms
```
Error: Repository operation failed
Cause: Database connection lost
Operation: get_by_tweet_id
```

#### Diagnostic Steps
```python
# Test repository connectivity
from knowledge_base_agent.repositories import TweetCacheRepository

try:
    repo = TweetCacheRepository()
    result = repo.get_by_id('test')
    print("Repository connection: OK")
except Exception as e:
    print(f"Repository error: {e}")

# Check database manager
from knowledge_base_agent.database_manager import DatabaseManager

try:
    db_manager = DatabaseManager.get_instance()
    with db_manager.get_session() as session:
        result = session.execute("SELECT 1")
        print("Database manager: OK")
except Exception as e:
    print(f"Database manager error: {e}")
```

#### Solutions
```python
# Implement connection recovery
class BaseRepository:
    def _execute_with_retry(self, operation, max_retries=3):
        for attempt in range(max_retries):
            try:
                return operation()
            except (ConnectionError, OperationalError) as e:
                if attempt < max_retries - 1:
                    logger.warning(f"Database connection failed, retrying... ({attempt + 1}/{max_retries})")
                    time.sleep(2 ** attempt)
                    # Recreate database manager
                    DatabaseManager._instance = None
                    continue
                raise

# Add health check method
def health_check(self):
    try:
        with self._get_session() as session:
            session.execute("SELECT 1")
        return True
    except Exception as e:
        logger.error(f"Repository health check failed: {e}")
        return False
```

### Memory Leaks in Repository Layer

#### Symptoms
```
Memory usage increasing over time
Repository cache size: >1GB
Application memory: >2GB
```

#### Diagnostic Steps
```python
# Monitor repository cache size
import psutil
import gc

def check_memory_usage():
    process = psutil.Process()
    memory_info = process.memory_info()
    
    print(f"RSS Memory: {memory_info.rss / 1024 / 1024:.2f} MB")
    print(f"VMS Memory: {memory_info.vms / 1024 / 1024:.2f} MB")
    
    # Check repository cache sizes
    from knowledge_base_agent.repositories import TweetCacheRepository
    
    repo = TweetCacheRepository()
    if hasattr(repo, '_cache'):
        print(f"Tweet cache size: {len(repo._cache)}")
    
    # Force garbage collection
    collected = gc.collect()
    print(f"Garbage collected: {collected} objects")

# Monitor over time
import threading
import time

def memory_monitor():
    while True:
        check_memory_usage()
        time.sleep(60)

threading.Thread(target=memory_monitor, daemon=True).start()
```

#### Solutions
```python
# Implement cache size limits
class TweetCacheRepository(BaseRepository):
    def __init__(self):
        super().__init__(TweetCache)
        self._cache = {}
        self._max_cache_size = 10000  # Limit cache size
        self._cache_access_times = {}
    
    def _manage_cache_size(self):
        if len(self._cache) > self._max_cache_size:
            # Remove least recently used items
            sorted_items = sorted(
                self._cache_access_times.items(),
                key=lambda x: x[1]
            )
            
            items_to_remove = len(self._cache) - self._max_cache_size
            for tweet_id, _ in sorted_items[:items_to_remove]:
                self._cache.pop(tweet_id, None)
                self._cache_access_times.pop(tweet_id, None)
    
    def get_by_tweet_id(self, tweet_id: str):
        # Update access time
        self._cache_access_times[tweet_id] = time.time()
        
        if tweet_id in self._cache:
            return self._cache[tweet_id]
        
        # Load from database and cache
        tweet = super().get_by_tweet_id(tweet_id)
        if tweet:
            self._cache[tweet_id] = tweet
            self._manage_cache_size()
        
        return tweet

# Add periodic cache cleanup
def cleanup_caches():
    """Periodic cleanup of repository caches"""
    for repo_instance in [tweet_repo, queue_repo, category_repo]:
        if hasattr(repo_instance, '_cache'):
            # Clear old entries
            current_time = time.time()
            old_entries = [
                key for key, access_time in repo_instance._cache_access_times.items()
                if current_time - access_time > 3600  # 1 hour
            ]
            
            for key in old_entries:
                repo_instance._cache.pop(key, None)
                repo_instance._cache_access_times.pop(key, None)

# Schedule cleanup
import schedule

schedule.every(1).hours.do(cleanup_caches)
```

## API and Frontend Issues

### API Response Timeouts

#### Symptoms
```
HTTP 504 Gateway Timeout
API endpoint: /v2/tweets/explore
Response time: >30 seconds
```

#### Diagnostic Steps
```bash
# 1. Test API endpoints directly
curl -w "@curl-format.txt" -s -o /dev/null "http://localhost:5000/v2/tweets/explore?per_page=50"

# Create curl-format.txt:
cat > curl-format.txt << 'EOF'
     time_namelookup:  %{time_namelookup}\n
        time_connect:  %{time_connect}\n
     time_appconnect:  %{time_appconnect}\n
    time_pretransfer:  %{time_pretransfer}\n
       time_redirect:  %{time_redirect}\n
  time_starttransfer:  %{time_starttransfer}\n
                     ----------\n
          time_total:  %{time_total}\n
EOF

# 2. Check application logs
tail -100 /logs/api.log | grep -E "(ERROR|TIMEOUT|SLOW)"

# 3. Monitor database queries
tail -f /logs/postgresql.log | grep -E "(duration|slow)"
```

#### Solutions
```python
# Implement request timeout handling
from flask import Flask, request, jsonify
import signal
import time

class TimeoutError(Exception):
    pass

def timeout_handler(signum, frame):
    raise TimeoutError("Request timeout")

@app.before_request
def before_request():
    # Set timeout for long-running requests
    if request.endpoint in ['explore_tweets', 'bulk_operations']:
        signal.signal(signal.SIGALRM, timeout_handler)
        signal.alarm(30)  # 30 second timeout

@app.after_request
def after_request(response):
    signal.alarm(0)  # Cancel timeout
    return response

# Add caching for expensive operations
from functools import lru_cache
import time

@lru_cache(maxsize=100)
def get_cached_tweet_statistics(cache_key):
    """Cache statistics for 5 minutes"""
    return calculate_tweet_statistics()

def cache_key_for_stats():
    # Cache for 5 minutes
    return int(time.time() // 300)

@app.route('/v2/tweets/statistics')
def get_tweet_statistics():
    try:
        cache_key = cache_key_for_stats()
        stats = get_cached_tweet_statistics(cache_key)
        return jsonify({'success': True, 'data': stats})
    except TimeoutError:
        return jsonify({
            'success': False,
            'error': 'Request timeout - try reducing the scope of your query'
        }), 408
```

### Frontend JavaScript Errors

#### Symptoms
```
JavaScript Console:
Uncaught TypeError: Cannot read property 'length' of undefined
at TweetManagementManager.renderTable (TweetManagementManager.js:245)
```

#### Diagnostic Steps
```javascript
// Add error boundary to catch JavaScript errors
class ErrorHandler {
    static init() {
        window.addEventListener('error', this.handleError);
        window.addEventListener('unhandledrejection', this.handlePromiseRejection);
    }
    
    static handleError(event) {
        console.error('JavaScript Error:', {
            message: event.message,
            filename: event.filename,
            lineno: event.lineno,
            colno: event.colno,
            error: event.error
        });
        
        // Send error to server for logging
        fetch('/api/log-error', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                type: 'javascript_error',
                message: event.message,
                stack: event.error ? event.error.stack : null,
                url: window.location.href,
                userAgent: navigator.userAgent
            })
        });
    }
    
    static handlePromiseRejection(event) {
        console.error('Unhandled Promise Rejection:', event.reason);
        this.handleError({
            message: 'Unhandled Promise Rejection: ' + event.reason,
            filename: window.location.href,
            lineno: 0,
            colno: 0,
            error: event.reason
        });
    }
}

// Initialize error handling
ErrorHandler.init();
```

#### Solutions
```javascript
// Implement defensive programming
class TweetManagementManager {
    renderTable(tweets) {
        const tbody = document.querySelector('#tweets-table-body');
        if (!tbody) {
            console.warn('Tweet table body not found');
            return;
        }
        
        // Validate tweets data
        if (!Array.isArray(tweets)) {
            console.error('Expected tweets to be an array, got:', typeof tweets);
            this.showError('Invalid tweet data format');
            return;
        }
        
        try {
            if (tweets.length === 0) {
                tbody.innerHTML = this.renderEmptyState();
                return;
            }
            
            tbody.innerHTML = tweets.map(tweet => {
                try {
                    return this.renderTweetRow(tweet);
                } catch (error) {
                    console.error('Error rendering tweet row:', error, tweet);
                    return this.renderErrorRow(tweet.tweet_id || 'unknown');
                }
            }).join('');
            
        } catch (error) {
            console.error('Error rendering tweet table:', error);
            this.showError('Failed to render tweet table');
            tbody.innerHTML = this.renderErrorState();
        }
    }
    
    renderTweetRow(tweet) {
        // Validate tweet object
        if (!tweet || typeof tweet !== 'object') {
            throw new Error('Invalid tweet object');
        }
        
        const requiredFields = ['tweet_id', 'cache_complete', 'media_processed', 'created_at'];
        for (const field of requiredFields) {
            if (!(field in tweet)) {
                throw new Error(`Missing required field: ${field}`);
            }
        }
        
        // Safely access nested properties
        const contentPreview = this.getContentPreview(tweet);
        const formattedDate = this.formatDate(tweet.created_at);
        
        return `
            <tr class="tweet-row" data-tweet-id="${this.escapeHtml(tweet.tweet_id)}">
                <!-- ... rest of row HTML ... -->
            </tr>
        `;
    }
    
    getContentPreview(tweet) {
        try {
            return tweet.content_preview || 
                   (tweet.content_data && tweet.content_data.text ? tweet.content_data.text.substring(0, 100) : '') ||
                   'No content available';
        } catch (error) {
            console.warn('Error extracting content preview:', error);
            return 'Content preview unavailable';
        }
    }
    
    escapeHtml(unsafe) {
        return (unsafe || '')
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#039;");
    }
}
```

## State Manager Issues

### State Synchronization Problems

#### Symptoms
```
Warning: State cache out of sync
Database count: 15,247
Cache count: 15,104
Missing tweets: 143
```

#### Diagnostic Steps
```python
# Check state synchronization
from knowledge_base_agent.database_state_manager import DatabaseStateManager

def diagnose_state_sync():
    state_manager = DatabaseStateManager(config)
    
    # Compare cache vs database
    cache_count = len(state_manager._tweet_cache)
    
    # Get database count
    db_count = state_manager.tweet_repo.count_all()
    
    print(f"Cache count: {cache_count}")
    print(f"Database count: {db_count}")
    print(f"Difference: {db_count - cache_count}")
    
    if cache_count != db_count:
        # Find missing tweets
        cached_ids = set(state_manager._tweet_cache.keys())
        
        all_tweets = state_manager.tweet_repo.get_all()
        db_ids = set(tweet.tweet_id for tweet in all_tweets)
        
        missing_in_cache = db_ids - cached_ids
        missing_in_db = cached_ids - db_ids
        
        print(f"Missing in cache: {len(missing_in_cache)}")
        print(f"Missing in database: {len(missing_in_db)}")
        
        return {
            'cache_count': cache_count,
            'db_count': db_count,
            'missing_in_cache': list(missing_in_cache)[:10],
            'missing_in_db': list(missing_in_db)[:10]
        }

# Run diagnosis
sync_status = diagnose_state_sync()
```

#### Solutions
```python
# Implement cache refresh mechanism
class DatabaseStateManager:
    def __init__(self, config):
        # ... existing initialization ...
        self._last_cache_refresh = time.time()
        self._cache_refresh_interval = 3600  # 1 hour
    
    def _check_cache_freshness(self):
        """Check if cache needs refreshing"""
        current_time = time.time()
        if current_time - self._last_cache_refresh > self._cache_refresh_interval:
            self.refresh_cache_from_database()
    
    def refresh_cache_from_database(self):
        """Refresh cache from database"""
        try:
            logger.info("Refreshing tweet cache from database")
            
            # Get all tweets from database
            all_tweets = self.tweet_repo.get_all()
            
            # Rebuild cache
            new_cache = {tweet.tweet_id: tweet for tweet in all_tweets}
            
            # Compare with existing cache
            old_count = len(self._tweet_cache)
            new_count = len(new_cache)
            
            if abs(old_count - new_count) > 100:
                logger.warning(f"Large cache difference detected: {old_count} -> {new_count}")
            
            # Update cache
            self._tweet_cache = new_cache
            self._cache_dirty.clear()
            self._last_cache_refresh = time.time()
            
            logger.info(f"Cache refreshed: {new_count} tweets loaded")
            
        except Exception as e:
            logger.error(f"Failed to refresh cache: {e}")
            raise
    
    def get_tweet_data(self, tweet_id: str):
        """Get tweet data with automatic cache refresh check"""
        self._check_cache_freshness()
        
        if tweet_id in self._tweet_cache:
            return self._tweet_cache[tweet_id].content_data
        
        # Cache miss - try database
        tweet = self.tweet_repo.get_by_tweet_id(tweet_id)
        if tweet:
            self._tweet_cache[tweet_id] = tweet
            return tweet.content_data
        
        return None

# Add periodic cache validation
def validate_cache_integrity():
    """Validate cache integrity and fix issues"""
    state_manager = DatabaseStateManager.get_instance()
    
    # Get counts
    cache_count = len(state_manager._tweet_cache)
    db_count = state_manager.tweet_repo.count_all()
    
    if abs(cache_count - db_count) > 50:  # Threshold for significant difference
        logger.warning(f"Cache integrity issue detected: cache={cache_count}, db={db_count}")
        state_manager.refresh_cache_from_database()
        return False
    
    return True

# Schedule periodic validation
import schedule
schedule.every(30).minutes.do(validate_cache_integrity)
```

## Backup and Recovery Issues

### Backup Creation Failures

#### Symptoms
```
Error: Backup creation failed
Component: database
Cause: pg_dump: connection failed
```

#### Diagnostic Steps
```bash
# 1. Test pg_dump manually
pg_dump -h localhost -U knowledge_base_agent -d knowledge_base_db --verbose > test_backup.sql

# 2. Check PostgreSQL authentication
cat ~/.pgpass
# Should contain: localhost:5432:knowledge_base_db:knowledge_base_agent:password

# 3. Check disk space
df -h /backups

# 4. Check backup directory permissions
ls -la /backups

# 5. Test backup script with verbose output
./backup_cli.py create --backup-id test_backup --database --verbose
```

#### Solutions
```bash
# Fix authentication
echo "localhost:5432:knowledge_base_db:knowledge_base_agent:your_password" > ~/.pgpass
chmod 600 ~/.pgpass

# Create backup directory if missing
sudo mkdir -p /backups
sudo chown $(whoami):$(whoami) /backups
chmod 755 /backups

# Test minimal backup
./backup_cli.py create --backup-id minimal_test --database --logs

# Fix PostgreSQL configuration if needed
sudo -u postgres psql -c "ALTER USER knowledge_base_agent WITH PASSWORD 'new_password';"
```

## System Monitoring

### Setting Up Monitoring

#### Database Monitoring
```sql
-- Enable query statistics
CREATE EXTENSION IF NOT EXISTS pg_stat_statements;

-- Create monitoring views
CREATE OR REPLACE VIEW db_performance_summary AS
SELECT 
    datname,
    numbackends as active_connections,
    xact_commit + xact_rollback as total_transactions,
    xact_commit * 100.0 / (xact_commit + xact_rollback) as commit_ratio,
    blks_read,
    blks_hit,
    blks_hit * 100.0 / (blks_hit + blks_read) as cache_hit_ratio,
    temp_files,
    pg_size_pretty(temp_bytes) as temp_size
FROM pg_stat_database 
WHERE datname = 'knowledge_base_db';

-- Check table growth
CREATE OR REPLACE VIEW table_growth AS
SELECT 
    schemaname,
    tablename,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) as size,
    pg_total_relation_size(schemaname||'.'||tablename) as size_bytes
FROM pg_tables 
WHERE schemaname = 'public'
ORDER BY size_bytes DESC;
```

#### Application Monitoring
```python
# Performance monitoring decorator
import time
import functools
import logging

performance_logger = logging.getLogger('performance')

def monitor_performance(operation_name):
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            start_time = time.time()
            try:
                result = func(*args, **kwargs)
                duration = time.time() - start_time
                
                # Log performance metrics
                performance_logger.info(f"{operation_name}: {duration:.3f}s")
                
                # Alert on slow operations
                if duration > 5.0:
                    performance_logger.warning(f"Slow operation {operation_name}: {duration:.3f}s")
                
                return result
            except Exception as e:
                duration = time.time() - start_time
                performance_logger.error(f"{operation_name} failed after {duration:.3f}s: {e}")
                raise
        return wrapper
    return decorator

# Apply to critical operations
@monitor_performance("tweet_cache_load")
def load_tweets_with_pagination(self, page, per_page, filters, search_term):
    # ... implementation ...

# System health check endpoint
@app.route('/health')
def health_check():
    checks = {
        'database': check_database_health(),
        'cache': check_cache_health(),
        'disk_space': check_disk_space(),
        'memory': check_memory_usage()
    }
    
    overall_health = all(checks.values())
    status_code = 200 if overall_health else 503
    
    return jsonify({
        'status': 'healthy' if overall_health else 'unhealthy',
        'checks': checks,
        'timestamp': datetime.utcnow().isoformat()
    }), status_code

def check_database_health():
    try:
        with get_db_session() as session:
            session.execute("SELECT 1")
        return True
    except Exception:
        return False

def check_disk_space():
    import shutil
    total, used, free = shutil.disk_usage("/")
    free_percent = free / total * 100
    return free_percent > 10  # Alert if less than 10% free
```

### Log Analysis Scripts

#### Automated Log Analysis
```bash
#!/bin/bash
# analyze_logs.sh

LOG_DIR="/logs"
REPORT_FILE="/tmp/log_analysis_$(date +%Y%m%d_%H%M%S).txt"

echo "Log Analysis Report - $(date)" > $REPORT_FILE
echo "=================================" >> $REPORT_FILE

# Error analysis
echo -e "\n=== ERROR ANALYSIS ===" >> $REPORT_FILE
echo "Top 10 errors in the last 24 hours:" >> $REPORT_FILE
find $LOG_DIR -name "*.log" -mtime -1 -exec grep -h "ERROR" {} \; | \
    sort | uniq -c | sort -nr | head -10 >> $REPORT_FILE

# Performance analysis
echo -e "\n=== PERFORMANCE ANALYSIS ===" >> $REPORT_FILE
echo "Slow operations (>1s) in the last hour:" >> $REPORT_FILE
find $LOG_DIR -name "performance.log" -mmin -60 -exec grep -h "duration.*[1-9][0-9]*\." {} \; | \
    head -20 >> $REPORT_FILE

# Database analysis
echo -e "\n=== DATABASE ANALYSIS ===" >> $REPORT_FILE
echo "Database errors in the last 6 hours:" >> $REPORT_FILE
find $LOG_DIR -name "*.log" -mmin -360 -exec grep -h -i "database.*error\|connection.*failed\|deadlock" {} \; | \
    sort | uniq -c | sort -nr >> $REPORT_FILE

# API analysis
echo -e "\n=== API ANALYSIS ===" >> $REPORT_FILE
echo "API endpoint response times (>5s):" >> $REPORT_FILE
find $LOG_DIR -name "api.log" -mmin -120 -exec grep -h "response_time.*[5-9]\." {} \; | \
    head -10 >> $REPORT_FILE

# Send report if errors found
ERROR_COUNT=$(grep -c "ERROR" $REPORT_FILE)
if [ $ERROR_COUNT -gt 10 ]; then
    echo "High error count detected: $ERROR_COUNT errors"
    # Send alert email or notification
    # mail -s "Knowledge Base Agent - High Error Count" admin@example.com < $REPORT_FILE
fi

echo "Report saved to: $REPORT_FILE"
```

#### Real-time Monitoring
```python
#!/usr/bin/env python3
# real_time_monitor.py

import time
import subprocess
import json
import requests
from datetime import datetime

class RealTimeMonitor:
    def __init__(self):
        self.metrics = {
            'api_response_times': [],
            'database_connections': [],
            'error_counts': [],
            'memory_usage': []
        }
    
    def collect_metrics(self):
        """Collect system metrics"""
        timestamp = datetime.utcnow()
        
        # API health check
        try:
            start_time = time.time()
            response = requests.get('http://localhost:5000/health', timeout=10)
            api_response_time = time.time() - start_time
            
            self.metrics['api_response_times'].append({
                'timestamp': timestamp,
                'response_time': api_response_time,
                'status_code': response.status_code
            })
        except Exception as e:
            print(f"API health check failed: {e}")
        
        # Database connections
        try:
            result = subprocess.run([
                'psql', '-d', 'knowledge_base_db', '-t', '-c',
                "SELECT count(*) FROM pg_stat_activity WHERE datname = 'knowledge_base_db';"
            ], capture_output=True, text=True, timeout=5)
            
            if result.returncode == 0:
                connection_count = int(result.stdout.strip())
                self.metrics['database_connections'].append({
                    'timestamp': timestamp,
                    'count': connection_count
                })
        except Exception as e:
            print(f"Database connection check failed: {e}")
        
        # Memory usage
        try:
            result = subprocess.run(['ps', '-o', 'pid,rss,cmd', '-C', 'python3'], 
                                  capture_output=True, text=True)
            
            total_memory = 0
            for line in result.stdout.split('\n')[1:]:  # Skip header
                if 'knowledge_base_agent' in line:
                    parts = line.split()
                    if len(parts) >= 2:
                        total_memory += int(parts[1])  # RSS in KB
            
            self.metrics['memory_usage'].append({
                'timestamp': timestamp,
                'memory_kb': total_memory
            })
        except Exception as e:
            print(f"Memory usage check failed: {e}")
    
    def check_alerts(self):
        """Check for alert conditions"""
        alerts = []
        
        # High API response time
        recent_api_times = self.metrics['api_response_times'][-5:]
        if recent_api_times:
            avg_response_time = sum(m['response_time'] for m in recent_api_times) / len(recent_api_times)
            if avg_response_time > 5.0:
                alerts.append(f"High API response time: {avg_response_time:.2f}s")
        
        # High database connections
        recent_connections = self.metrics['database_connections'][-3:]
        if recent_connections:
            max_connections = max(m['count'] for m in recent_connections)
            if max_connections > 50:
                alerts.append(f"High database connections: {max_connections}")
        
        # High memory usage
        recent_memory = self.metrics['memory_usage'][-3:]
        if recent_memory:
            max_memory = max(m['memory_kb'] for m in recent_memory)
            if max_memory > 2048000:  # 2GB
                alerts.append(f"High memory usage: {max_memory / 1024:.1f} MB")
        
        return alerts
    
    def run(self):
        """Run continuous monitoring"""
        print("Starting real-time monitoring...")
        
        while True:
            try:
                self.collect_metrics()
                alerts = self.check_alerts()
                
                if alerts:
                    print(f"[{datetime.now()}] ALERTS:")
                    for alert in alerts:
                        print(f"  - {alert}")
                
                # Keep only recent metrics (last hour)
                for metric_list in self.metrics.values():
                    cutoff_time = datetime.utcnow().timestamp() - 3600
                    self.metrics[metric_list] = [
                        m for m in metric_list 
                        if m['timestamp'].timestamp() > cutoff_time
                    ]
                
                time.sleep(30)  # Check every 30 seconds
                
            except KeyboardInterrupt:
                print("Monitoring stopped.")
                break
            except Exception as e:
                print(f"Monitoring error: {e}")
                time.sleep(30)

if __name__ == "__main__":
    monitor = RealTimeMonitor()
    monitor.run()
```

## Performance Optimization

### Database Optimization

#### Query Optimization
```sql
-- Optimize common queries
EXPLAIN ANALYZE SELECT * FROM tweet_cache 
WHERE cache_complete = true 
AND created_at > NOW() - INTERVAL '24 hours'
ORDER BY created_at DESC 
LIMIT 50;

-- Create optimized indexes
CREATE INDEX CONCURRENTLY idx_tweet_cache_cache_complete_created 
ON tweet_cache(cache_complete, created_at DESC) 
WHERE cache_complete = true;

-- Partial index for incomplete tweets
CREATE INDEX CONCURRENTLY idx_tweet_cache_incomplete 
ON tweet_cache(created_at DESC) 
WHERE cache_complete = false;

-- Optimize JSON queries
CREATE INDEX CONCURRENTLY idx_tweet_cache_content_text_gin 
ON tweet_cache 
USING gin((content_data->>'text') gin_trgm_ops);

-- Update table statistics more frequently
ALTER TABLE tweet_cache SET (autovacuum_analyze_scale_factor = 0.1);
ALTER TABLE tweet_processing_queue SET (autovacuum_analyze_scale_factor = 0.1);
```

#### Connection Pool Tuning
```python
# Optimized database configuration
DATABASE_CONFIG = {
    'pool_size': 20,              # Base pool size
    'max_overflow': 30,           # Additional connections during peak
    'pool_timeout': 30,           # Connection timeout
    'pool_recycle': 3600,         # Recycle connections hourly
    'pool_pre_ping': True,        # Validate connections
    'connect_args': {
        'application_name': 'knowledge_base_agent',
        'options': '-c statement_timeout=30000'  # 30 second statement timeout
    }
}

# Implement connection pooling monitoring
class DatabaseMonitor:
    def __init__(self, engine):
        self.engine = engine
    
    def get_pool_status(self):
        pool = self.engine.pool
        return {
            'pool_size': pool.size(),
            'checked_out': pool.checkedout(),
            'checked_in': pool.checkedin(),
            'overflow': pool.overflow(),
            'total_connections': pool.size() + pool.overflow()
        }
    
    def log_pool_status(self):
        status = self.get_pool_status()
        logger.info(f"Database pool status: {status}")
        
        # Alert on high usage
        usage_ratio = status['checked_out'] / (status['pool_size'] + status['overflow'])
        if usage_ratio > 0.8:
            logger.warning(f"High database pool usage: {usage_ratio:.2%}")
```

### Application Optimization

#### Caching Strategies
```python
# Implement multi-level caching
import redis
from functools import wraps

redis_client = redis.Redis(host='localhost', port=6379, db=0)

def cache_result(ttl=300, key_prefix=''):
    """Decorator for caching function results"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Generate cache key
            cache_key = f"{key_prefix}:{func.__name__}:{hash(str(args) + str(kwargs))}"
            
            # Try to get from cache
            try:
                cached_result = redis_client.get(cache_key)
                if cached_result:
                    return json.loads(cached_result)
            except Exception as e:
                logger.warning(f"Cache read failed: {e}")
            
            # Execute function and cache result
            result = func(*args, **kwargs)
            
            try:
                redis_client.setex(cache_key, ttl, json.dumps(result, default=str))
            except Exception as e:
                logger.warning(f"Cache write failed: {e}")
            
            return result
        return wrapper
    return decorator

# Apply caching to expensive operations
@cache_result(ttl=300, key_prefix='tweet_stats')
def get_tweet_statistics():
    """Cached tweet statistics"""
    # Implementation...

@cache_result(ttl=600, key_prefix='category_hierarchy')
def get_category_hierarchy():
    """Cached category hierarchy"""
    # Implementation...

# Implement cache warming
def warm_cache():
    """Pre-populate cache with frequently accessed data"""
    logger.info("Warming cache...")
    
    try:
        # Warm common statistics
        get_tweet_statistics()
        get_category_hierarchy()
        
        # Warm recent tweets
        recent_tweets = tweet_repo.get_tweets_with_pagination(
            page=1, per_page=100, 
            filters={'created_at_gte': datetime.utcnow() - timedelta(hours=24)}
        )
        
        logger.info("Cache warming completed")
    except Exception as e:
        logger.error(f"Cache warming failed: {e}")

# Schedule cache warming
import schedule
schedule.every(30).minutes.do(warm_cache)
```

#### Async Processing
```python
# Implement async processing for heavy operations
import asyncio
import aiohttp
from concurrent.futures import ThreadPoolExecutor

class AsyncTweetProcessor:
    def __init__(self, max_workers=10):
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
        self.session = None
    
    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
    async def process_tweet_batch(self, tweet_ids):
        """Process multiple tweets asynchronously"""
        tasks = [
            self.process_single_tweet(tweet_id) 
            for tweet_id in tweet_ids
        ]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        successful = sum(1 for r in results if not isinstance(r, Exception))
        failed = len(results) - successful
        
        logger.info(f"Batch processing completed: {successful} successful, {failed} failed")
        return results
    
    async def process_single_tweet(self, tweet_id):
        """Process a single tweet asynchronously"""
        loop = asyncio.get_event_loop()
        
        try:
            # Run CPU-intensive work in thread pool
            result = await loop.run_in_executor(
                self.executor,
                self._process_tweet_sync,
                tweet_id
            )
            return result
        except Exception as e:
            logger.error(f"Failed to process tweet {tweet_id}: {e}")
            raise
    
    def _process_tweet_sync(self, tweet_id):
        """Synchronous tweet processing (runs in thread pool)"""
        # Implementation...
        pass

# Usage
async def bulk_process_tweets(tweet_ids):
    async with AsyncTweetProcessor(max_workers=20) as processor:
        results = await processor.process_tweet_batch(tweet_ids)
        return results
```

## Routine Maintenance

### Daily Maintenance Tasks

#### Automated Daily Script
```bash
#!/bin/bash
# daily_maintenance.sh

set -e

LOG_FILE="/logs/maintenance_$(date +%Y%m%d).log"
exec > >(tee -a $LOG_FILE) 2>&1

echo "=== Daily Maintenance Started: $(date) ==="

# 1. Database maintenance
echo "Running database maintenance..."
psql -d knowledge_base_db -c "
    -- Update statistics
    ANALYZE;
    
    -- Check for bloated tables
    SELECT schemaname, tablename, 
           pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) as size
    FROM pg_tables 
    WHERE schemaname = 'public'
    ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC
    LIMIT 5;
"

# 2. Log rotation
echo "Rotating logs..."
find /logs -name "*.log" -size +100M -exec gzip {} \;
find /logs -name "*.log.gz" -mtime +30 -delete

# 3. Cache cleanup
echo "Cleaning up caches..."
python3 -c "
from knowledge_base_agent.repositories import TweetCacheRepository
repo = TweetCacheRepository()
if hasattr(repo, 'cleanup_cache'):
    repo.cleanup_cache()
print('Cache cleanup completed')
"

# 4. Backup validation
echo "Validating recent backups..."
./backup_cli.py validate --recent 3

# 5. Performance check
echo "Checking system performance..."
python3 -c "
import psutil
import subprocess

# Check system resources
cpu_percent = psutil.cpu_percent(interval=1)
memory = psutil.virtual_memory()
disk = psutil.disk_usage('/')

print(f'CPU Usage: {cpu_percent}%')
print(f'Memory Usage: {memory.percent}%')
print(f'Disk Usage: {disk.used / disk.total * 100:.1f}%')

# Check database connections
result = subprocess.run([
    'psql', '-d', 'knowledge_base_db', '-t', '-c',
    'SELECT count(*) FROM pg_stat_activity WHERE datname = \\'knowledge_base_db\\';'
], capture_output=True, text=True)

if result.returncode == 0:
    print(f'Database Connections: {result.stdout.strip()}')
"

# 6. Alert on issues
ERROR_COUNT=$(grep -c "ERROR\|FAILED" $LOG_FILE || true)
if [ $ERROR_COUNT -gt 0 ]; then
    echo "WARNING: $ERROR_COUNT errors found during maintenance"
    # Send alert notification
fi

echo "=== Daily Maintenance Completed: $(date) ==="
```

### Weekly Maintenance Tasks

#### Comprehensive Weekly Script
```bash
#!/bin/bash
# weekly_maintenance.sh

set -e

LOG_FILE="/logs/weekly_maintenance_$(date +%Y%m%d).log"
exec > >(tee -a $LOG_FILE) 2>&1

echo "=== Weekly Maintenance Started: $(date) ==="

# 1. Full database vacuum and analyze
echo "Running full database maintenance..."
psql -d knowledge_base_db -c "
    -- Vacuum all tables
    VACUUM ANALYZE tweet_cache;
    VACUUM ANALYZE tweet_processing_queue;
    VACUUM ANALYZE category_hierarchy;
    VACUUM ANALYZE processing_statistics;
    VACUUM ANALYZE runtime_statistics;
    
    -- Check index usage
    SELECT schemaname, tablename, indexname, idx_scan, idx_tup_read, idx_tup_fetch
    FROM pg_stat_user_indexes
    WHERE idx_scan = 0
    ORDER BY schemaname, tablename;
    
    -- Check table sizes
    SELECT 
        schemaname,
        tablename,
        pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) as total_size,
        pg_size_pretty(pg_relation_size(schemaname||'.'||tablename)) as table_size,
        pg_size_pretty(pg_indexes_size(schemaname||'.'||tablename)) as index_size
    FROM pg_tables 
    WHERE schemaname = 'public'
    ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;
"

# 2. Performance analysis
echo "Analyzing performance metrics..."
python3 -c "
import json
from datetime import datetime, timedelta
from knowledge_base_agent.repositories import TweetCacheRepository

# Analyze processing performance
repo = TweetCacheRepository()

# Get performance metrics for the last week
week_ago = datetime.utcnow() - timedelta(days=7)
recent_tweets = repo.get_tweets_created_after(week_ago)

if recent_tweets:
    total_tweets = len(recent_tweets)
    cache_complete = sum(1 for t in recent_tweets if t.cache_complete)
    media_processed = sum(1 for t in recent_tweets if t.media_processed)
    
    print(f'Tweets processed this week: {total_tweets}')
    print(f'Cache completion rate: {cache_complete/total_tweets*100:.1f}%')
    print(f'Media processing rate: {media_processed/total_tweets*100:.1f}%')
else:
    print('No tweets processed this week')
"

# 3. Backup maintenance
echo "Performing backup maintenance..."
./backup_cli.py cleanup --dry-run
./backup_cli.py validate --all

# 4. Security checks
echo "Running security checks..."
# Check file permissions
find /backups -type f -perm /o+w -ls | head -10
find /logs -type f -perm /o+w -ls | head -10

# Check for unusual log entries
grep -i "authentication\|failed\|unauthorized" /logs/*.log | tail -10

# 5. Update statistics and reports
echo "Generating weekly reports..."
python3 -c "
from datetime import datetime, timedelta
import json

# Generate weekly summary
summary = {
    'week_ending': datetime.utcnow().isoformat(),
    'system_health': 'healthy',  # Would be determined by actual checks
    'performance_summary': {
        'avg_api_response_time': '250ms',  # Would be calculated
        'database_performance': 'good',
        'cache_hit_ratio': '94.5%'
    },
    'maintenance_actions': [
        'Database vacuum completed',
        'Log rotation performed',
        'Backup validation successful',
        'Performance analysis completed'
    ]
}

with open('/logs/weekly_summary.json', 'w') as f:
    json.dump(summary, f, indent=2)

print('Weekly summary generated')
"

echo "=== Weekly Maintenance Completed: $(date) ==="
```

### Monthly Maintenance Tasks

#### Archive and Cleanup Script
```bash
#!/bin/bash
# monthly_maintenance.sh

set -e

LOG_FILE="/logs/monthly_maintenance_$(date +%Y%m%d).log"
exec > >(tee -a $LOG_FILE) 2>&1

echo "=== Monthly Maintenance Started: $(date) ==="

# 1. Archive old logs
echo "Archiving old logs..."
ARCHIVE_DIR="/archives/logs/$(date +%Y/%m)"
mkdir -p $ARCHIVE_DIR

find /logs -name "*.log.gz" -mtime +7 -exec mv {} $ARCHIVE_DIR/ \;
find /logs -name "*.log" -mtime +30 -exec gzip {} \;

# 2. Database maintenance
echo "Performing comprehensive database maintenance..."
psql -d knowledge_base_db -c "
    -- Reindex all tables
    REINDEX TABLE tweet_cache;
    REINDEX TABLE tweet_processing_queue;
    REINDEX TABLE category_hierarchy;
    
    -- Update all statistics
    ANALYZE;
    
    -- Check for unused indexes
    SELECT 
        schemaname,
        tablename,
        indexname,
        pg_size_pretty(pg_relation_size(indexrelid)) as index_size,
        idx_scan
    FROM pg_stat_user_indexes
    WHERE idx_scan < 10
    ORDER BY pg_relation_size(indexrelid) DESC;
"

# 3. Performance optimization
echo "Running performance optimization..."
python3 -c "
# Optimize database queries based on usage patterns
from knowledge_base_agent.repositories import TweetCacheRepository
import logging

# Enable query logging temporarily
logging.getLogger('sqlalchemy.engine').setLevel(logging.INFO)

# Run common queries and analyze performance
repo = TweetCacheRepository()

# Test pagination performance
for page in range(1, 6):
    result = repo.get_tweets_with_pagination(page=page, per_page=100)
    print(f'Page {page}: {len(result[\"tweets\"])} tweets')

print('Performance optimization analysis completed')
"

# 4. Security review
echo "Performing security review..."
# Check for security issues
find / -name "*.log" -exec grep -l "password\|secret\|key" {} \; 2>/dev/null | head -10
find /tmp -name "*knowledge*" -mtime +1 -ls | head -10

# 5. Capacity planning
echo "Analyzing capacity trends..."
python3 -c "
import os
import json
from datetime import datetime

# Analyze growth trends
data_sizes = {}
for root, dirs, files in os.walk('/'):
    if 'knowledge_base' in root:
        size = sum(os.path.getsize(os.path.join(root, f)) for f in files if os.path.exists(os.path.join(root, f)))
        data_sizes[root] = size

# Log capacity information
capacity_report = {
    'timestamp': datetime.utcnow().isoformat(),
    'data_sizes': {k: f'{v/1024/1024:.1f} MB' for k, v in data_sizes.items()},
    'growth_trends': 'Analysis pending'  # Would include actual trend analysis
}

with open('/logs/capacity_report.json', 'w') as f:
    json.dump(capacity_report, f, indent=2)

print('Capacity analysis completed')
"

echo "=== Monthly Maintenance Completed: $(date) ==="
```

## Emergency Procedures

### System Recovery Procedures

#### Complete System Failure
```bash
#!/bin/bash
# emergency_recovery.sh

echo "=== EMERGENCY RECOVERY PROCEDURE ==="
echo "Timestamp: $(date)"

# 1. Stop all services
echo "Stopping all services..."
sudo systemctl stop knowledge-base-agent
sudo systemctl stop postgresql
sudo systemctl stop redis-server

# 2. Check system resources
echo "Checking system resources..."
df -h
free -h
ps aux | grep -E "(postgres|python|redis)" | grep -v grep

# 3. Check for corruption
echo "Checking for file system corruption..."
sudo fsck -f /dev/sda1 || echo "File system check completed with warnings"

# 4. Restore from latest backup
echo "Identifying latest backup..."
LATEST_BACKUP=$(ls -t /backups/*/metadata.json | head -1 | xargs dirname | xargs basename)
echo "Latest backup: $LATEST_BACKUP"

if [ -n "$LATEST_BACKUP" ]; then
    echo "Restoring from backup: $LATEST_BACKUP"
    ./backup_cli.py restore "$LATEST_BACKUP" --components database,json_files --create-rollback --confirm
else
    echo "ERROR: No backup found for restoration"
    exit 1
fi

# 5. Restart services
echo "Restarting services..."
sudo systemctl start postgresql
sleep 10
sudo systemctl start redis-server
sleep 5
sudo systemctl start knowledge-base-agent

# 6. Verify functionality
echo "Verifying system functionality..."
sleep 30

# Test database connection
psql -d knowledge_base_db -c "SELECT COUNT(*) FROM tweet_cache;" || echo "Database test failed"

# Test API
curl -f http://localhost:5000/health || echo "API test failed"

# Test web interface
curl -f http://localhost:5000/v2/page/tweets || echo "Web interface test failed"

echo "Emergency recovery procedure completed"
echo "Check logs and verify full functionality before resuming normal operations"
```

#### Data Corruption Recovery
```bash
#!/bin/bash
# data_corruption_recovery.sh

echo "=== DATA CORRUPTION RECOVERY ==="

# 1. Stop processing immediately
sudo systemctl stop knowledge-base-agent

# 2. Create emergency backup of current state
./backup_cli.py create --backup-id "emergency_$(date +%Y%m%d_%H%M%S)" --full --description "Emergency backup before corruption recovery"

# 3. Identify corruption extent
echo "Analyzing data corruption..."
psql -d knowledge_base_db -c "
    -- Check for data integrity issues
    SELECT 
        'tweet_cache' as table_name,
        COUNT(*) as total_records,
        COUNT(*) FILTER (WHERE content_data IS NULL) as null_content,
        COUNT(*) FILTER (WHERE tweet_id IS NULL OR tweet_id = '') as invalid_ids
    FROM tweet_cache
    
    UNION ALL
    
    SELECT 
        'tweet_processing_queue' as table_name,
        COUNT(*) as total_records,
        COUNT(*) FILTER (WHERE status NOT IN ('unprocessed', 'processed', 'failed')) as invalid_status,
        COUNT(*) FILTER (WHERE tweet_id IS NULL OR tweet_id = '') as invalid_ids
    FROM tweet_processing_queue;
"

# 4. Restore from known good backup
echo "Select backup for restoration:"
./backup_cli.py list --detailed --recent 10

read -p "Enter backup ID to restore from: " BACKUP_ID

if [ -n "$BACKUP_ID" ]; then
    ./backup_cli.py restore "$BACKUP_ID" --components database --create-rollback --confirm
else
    echo "No backup specified, manual recovery required"
    exit 1
fi

# 5. Validate restored data
echo "Validating restored data..."
python3 -c "
from knowledge_base_agent.json_to_db_migrator import JsonToDbMigrator

config = Config()
migrator = JsonToDbMigrator(config)

validation_result = migrator.validate_migration()
if validation_result.success:
    print('Data validation: PASSED')
else:
    print('Data validation: FAILED')
    for error in validation_result.errors:
        print(f'  - {error}')
"

echo "Data corruption recovery completed"
```

## Diagnostic Tools

### Database Diagnostic Script
```python
#!/usr/bin/env python3
# database_diagnostics.py

import psycopg2
import json
from datetime import datetime
import argparse

class DatabaseDiagnostics:
    def __init__(self, connection_string):
        self.conn = psycopg2.connect(connection_string)
        self.cursor = self.conn.cursor()
    
    def run_all_diagnostics(self):
        """Run comprehensive database diagnostics"""
        results = {
            'timestamp': datetime.utcnow().isoformat(),
            'connection_info': self.get_connection_info(),
            'table_stats': self.get_table_statistics(),
            'index_usage': self.get_index_usage(),
            'query_performance': self.get_query_performance(),
            'locks_and_waits': self.get_locks_and_waits(),
            'configuration': self.get_configuration(),
            'health_checks': self.run_health_checks()
        }
        
        return results
    
    def get_connection_info(self):
        """Get database connection information"""
        self.cursor.execute("""
            SELECT 
                datname,
                numbackends,
                xact_commit,
                xact_rollback,
                blks_read,
                blks_hit,
                temp_files,
                temp_bytes,
                deadlocks
            FROM pg_stat_database 
            WHERE datname = current_database()
        """)
        
        result = self.cursor.fetchone()
        if result:
            return {
                'database_name': result[0],
                'active_connections': result[1],
                'transactions_committed': result[2],
                'transactions_rolled_back': result[3],
                'blocks_read': result[4],
                'blocks_hit': result[5],
                'temp_files': result[6],
                'temp_bytes': result[7],
                'deadlocks': result[8],
                'cache_hit_ratio': result[5] / (result[4] + result[5]) * 100 if (result[4] + result[5]) > 0 else 0
            }
        return {}
    
    def get_table_statistics(self):
        """Get table size and statistics"""
        self.cursor.execute("""
            SELECT 
                schemaname,
                tablename,
                n_tup_ins,
                n_tup_upd,
                n_tup_del,
                n_live_tup,
                n_dead_tup,
                last_vacuum,
                last_autovacuum,
                last_analyze,
                last_autoanalyze,
                pg_total_relation_size(schemaname||'.'||tablename) as total_size
            FROM pg_stat_user_tables
            ORDER BY total_size DESC
        """)
        
        tables = []
        for row in self.cursor.fetchall():
            tables.append({
                'schema': row[0],
                'table': row[1],
                'inserts': row[2],
                'updates': row[3],
                'deletes': row[4],
                'live_tuples': row[5],
                'dead_tuples': row[6],
                'last_vacuum': row[7].isoformat() if row[7] else None,
                'last_autovacuum': row[8].isoformat() if row[8] else None,
                'last_analyze': row[9].isoformat() if row[9] else None,
                'last_autoanalyze': row[10].isoformat() if row[10] else None,
                'total_size_bytes': row[11],
                'total_size_mb': row[11] / 1024 / 1024 if row[11] else 0,
                'dead_tuple_ratio': row[6] / row[5] * 100 if row[5] > 0 else 0
            })
        
        return tables
    
    def get_index_usage(self):
        """Get index usage statistics"""
        self.cursor.execute("""
            SELECT 
                schemaname,
                tablename,
                indexname,
                idx_scan,
                idx_tup_read,
                idx_tup_fetch,
                pg_relation_size(indexrelid) as index_size
            FROM pg_stat_user_indexes
            ORDER BY idx_scan DESC
        """)
        
        indexes = []
        for row in self.cursor.fetchall():
            indexes.append({
                'schema': row[0],
                'table': row[1],
                'index': row[2],
                'scans': row[3],
                'tuples_read': row[4],
                'tuples_fetched': row[5],
                'size_bytes': row[6],
                'size_mb': row[6] / 1024 / 1024 if row[6] else 0,
                'efficiency': row[5] / row[4] * 100 if row[4] > 0 else 0
            })
        
        return indexes
    
    def get_query_performance(self):
        """Get slow query information"""
        try:
            self.cursor.execute("""
                SELECT 
                    query,
                    calls,
                    total_time,
                    mean_time,
                    max_time,
                    stddev_time,
                    rows
                FROM pg_stat_statements
                WHERE mean_time > 100
                ORDER BY mean_time DESC
                LIMIT 20
            """)
            
            queries = []
            for row in self.cursor.fetchall():
                queries.append({
                    'query': row[0][:200] + '...' if len(row[0]) > 200 else row[0],
                    'calls': row[1],
                    'total_time_ms': row[2],
                    'mean_time_ms': row[3],
                    'max_time_ms': row[4],
                    'stddev_time_ms': row[5],
                    'rows_affected': row[6]
                })
            
            return queries
        except psycopg2.ProgrammingError:
            return "pg_stat_statements extension not available"
    
    def get_locks_and_waits(self):
        """Get current locks and waits"""
        self.cursor.execute("""
            SELECT 
                blocked_locks.pid AS blocked_pid,
                blocked_activity.usename AS blocked_user,
                blocking_locks.pid AS blocking_pid,
                blocking_activity.usename AS blocking_user,
                blocked_activity.query AS blocked_statement,
                blocking_activity.query AS blocking_statement
            FROM pg_catalog.pg_locks blocked_locks
            JOIN pg_catalog.pg_stat_activity blocked_activity ON blocked_activity.pid = blocked_locks.pid
            JOIN pg_catalog.pg_locks blocking_locks ON blocking_locks.locktype = blocked_locks.locktype
            JOIN pg_catalog.pg_stat_activity blocking_activity ON blocking_activity.pid = blocking_locks.pid
            WHERE NOT blocked_locks.granted
        """)
        
        locks = []
        for row in self.cursor.fetchall():
            locks.append({
                'blocked_pid': row[0],
                'blocked_user': row[1],
                'blocking_pid': row[2],
                'blocking_user': row[3],
                'blocked_query': row[4][:200] + '...' if len(row[4]) > 200 else row[4],
                'blocking_query': row[5][:200] + '...' if len(row[5]) > 200 else row[5]
            })
        
        return locks
    
    def get_configuration(self):
        """Get important PostgreSQL configuration settings"""
        settings = [
            'max_connections', 'shared_buffers', 'work_mem', 'maintenance_work_mem',
            'checkpoint_completion_target', 'wal_buffers', 'default_statistics_target'
        ]
        
        config = {}
        for setting in settings:
            self.cursor.execute("SELECT setting, unit FROM pg_settings WHERE name = %s", (setting,))
            result = self.cursor.fetchone()
            if result:
                config[setting] = {
                    'value': result[0],
                    'unit': result[1] or ''
                }
        
        return config
    
    def run_health_checks(self):
        """Run various health checks"""
        checks = {}
        
        # Check for bloated tables
        self.cursor.execute("""
            SELECT schemaname, tablename, n_dead_tup, n_live_tup
            FROM pg_stat_user_tables
            WHERE n_dead_tup > n_live_tup * 0.1 AND n_live_tup > 1000
        """)
        
        bloated_tables = [
            {'schema': row[0], 'table': row[1], 'dead_tuples': row[2], 'live_tuples': row[3]}
            for row in self.cursor.fetchall()
        ]
        checks['bloated_tables'] = bloated_tables
        
        # Check for unused indexes
        self.cursor.execute("""
            SELECT schemaname, tablename, indexname, idx_scan
            FROM pg_stat_user_indexes
            WHERE idx_scan = 0 AND pg_relation_size(indexrelid) > 1048576
        """)
        
        unused_indexes = [
            {'schema': row[0], 'table': row[1], 'index': row[2], 'scans': row[3]}
            for row in self.cursor.fetchall()
        ]
        checks['unused_indexes'] = unused_indexes
        
        # Check for long-running queries
        self.cursor.execute("""
            SELECT pid, usename, state, query_start, query
            FROM pg_stat_activity
            WHERE state = 'active' 
            AND query_start < NOW() - INTERVAL '5 minutes'
            AND query NOT LIKE '%pg_stat_activity%'
        """)
        
        long_queries = [
            {
                'pid': row[0],
                'user': row[1],
                'state': row[2],
                'query_start': row[3].isoformat() if row[3] else None,
                'query': row[4][:200] + '...' if len(row[4]) > 200 else row[4]
            }
            for row in self.cursor.fetchall()
        ]
        checks['long_running_queries'] = long_queries
        
        return checks
    
    def close(self):
        """Close database connection"""
        self.cursor.close()
        self.conn.close()

def main():
    parser = argparse.ArgumentParser(description='Run database diagnostics')
    parser.add_argument('--connection', '-c', 
                       default='postgresql://knowledge_base_agent:password@localhost/knowledge_base_db',
                       help='Database connection string')
    parser.add_argument('--output', '-o', help='Output file for results')
    parser.add_argument('--format', choices=['json', 'text'], default='json',
                       help='Output format')
    
    args = parser.parse_args()
    
    try:
        diagnostics = DatabaseDiagnostics(args.connection)
        results = diagnostics.run_all_diagnostics()
        diagnostics.close()
        
        if args.format == 'json':
            output = json.dumps(results, indent=2, default=str)
        else:
            output = format_text_output(results)
        
        if args.output:
            with open(args.output, 'w') as f:
                f.write(output)
            print(f"Diagnostics saved to {args.output}")
        else:
            print(output)
            
    except Exception as e:
        print(f"Error running diagnostics: {e}")
        return 1
    
    return 0

def format_text_output(results):
    """Format results as readable text"""
    output = []
    output.append("DATABASE DIAGNOSTICS REPORT")
    output.append("=" * 50)
    output.append(f"Generated: {results['timestamp']}")
    output.append("")
    
    # Connection info
    conn_info = results['connection_info']
    output.append("CONNECTION INFORMATION:")
    output.append(f"  Database: {conn_info.get('database_name', 'N/A')}")
    output.append(f"  Active Connections: {conn_info.get('active_connections', 'N/A')}")
    output.append(f"  Cache Hit Ratio: {conn_info.get('cache_hit_ratio', 0):.1f}%")
    output.append(f"  Deadlocks: {conn_info.get('deadlocks', 'N/A')}")
    output.append("")
    
    # Table statistics
    output.append("TABLE STATISTICS:")
    for table in results['table_stats'][:5]:  # Top 5 tables
        output.append(f"  {table['schema']}.{table['table']}:")
        output.append(f"    Size: {table['total_size_mb']:.1f} MB")
        output.append(f"    Live tuples: {table['live_tuples']:,}")
        output.append(f"    Dead tuples: {table['dead_tuples']:,} ({table['dead_tuple_ratio']:.1f}%)")
    output.append("")
    
    # Health checks
    health = results['health_checks']
    output.append("HEALTH CHECKS:")
    
    if health['bloated_tables']:
        output.append("  Bloated Tables:")
        for table in health['bloated_tables']:
            output.append(f"    {table['schema']}.{table['table']} - {table['dead_tuples']:,} dead tuples")
    
    if health['unused_indexes']:
        output.append("  Unused Indexes:")
        for idx in health['unused_indexes']:
            output.append(f"    {idx['schema']}.{idx['table']}.{idx['index']}")
    
    if health['long_running_queries']:
        output.append("  Long-Running Queries:")
        for query in health['long_running_queries']:
            output.append(f"    PID {query['pid']}: {query['query'][:100]}...")
    
    return "\n".join(output)

if __name__ == "__main__":
    exit(main())
```

## Preventive Measures

### Automated Monitoring Setup
```bash
#!/bin/bash
# setup_monitoring.sh

echo "Setting up automated monitoring for Knowledge Base Agent..."

# 1. Create monitoring scripts directory
sudo mkdir -p /opt/knowledge-base-monitoring
sudo chown $(whoami):$(whoami) /opt/knowledge-base-monitoring

# 2. Install monitoring dependencies
pip3 install psutil requests schedule

# 3. Create monitoring configuration
cat > /opt/knowledge-base-monitoring/config.json << 'EOF'
{
    "database": {
        "connection_string": "postgresql://knowledge_base_agent:password@localhost/knowledge_base_db",
        "alert_thresholds": {
            "connection_count": 80,
            "cache_hit_ratio": 90,
            "deadlock_count": 5,
            "slow_query_threshold": 1000
        }
    },
    "system": {
        "alert_thresholds": {
            "cpu_percent": 80,
            "memory_percent": 85,
            "disk_percent": 90
        }
    },
    "application": {
        "api_url": "http://localhost:5000",
        "alert_thresholds": {
            "response_time": 5.0,
            "error_rate": 5.0
        }
    },
    "notifications": {
        "email": {
            "enabled": true,
            "smtp_server": "smtp.example.com",
            "smtp_port": 587,
            "username": "alerts@example.com",
            "password": "smtp_password",
            "recipients": ["admin@example.com"]
        },
        "webhook": {
            "enabled": false,
            "url": "https://hooks.slack.com/services/...",
            "channel": "#alerts"
        }
    }
}
EOF

# 4. Create monitoring script
cat > /opt/knowledge-base-monitoring/monitor.py << 'EOF'
#!/usr/bin/env python3

import json
import time
import smtplib
import requests
import psutil
import psycopg2
import schedule
from email.mime.text import MIMEText
from datetime import datetime
import logging

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/logs/monitoring.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class SystemMonitor:
    def __init__(self, config_file):
        with open(config_file, 'r') as f:
            self.config = json.load(f)
        
        self.alerts = []
    
    def check_database_health(self):
        """Check database health metrics"""
        try:
            conn = psycopg2.connect(self.config['database']['connection_string'])
            cursor = conn.cursor()
            
            # Check connection count
            cursor.execute("""
                SELECT count(*) FROM pg_stat_activity 
                WHERE datname = 'knowledge_base_db'
            """)
            connection_count = cursor.fetchone()[0]
            
            threshold = self.config['database']['alert_thresholds']['connection_count']
            if connection_count > threshold:
                self.alerts.append(f"High database connections: {connection_count} (threshold: {threshold})")
            
            # Check cache hit ratio
            cursor.execute("""
                SELECT 
                    blks_hit * 100.0 / (blks_hit + blks_read) as cache_hit_ratio
                FROM pg_stat_database 
                WHERE datname = 'knowledge_base_db'
            """)
            cache_hit_ratio = cursor.fetchone()[0] or 0
            
            threshold = self.config['database']['alert_thresholds']['cache_hit_ratio']
            if cache_hit_ratio < threshold:
                self.alerts.append(f"Low cache hit ratio: {cache_hit_ratio:.1f}% (threshold: {threshold}%)")
            
            # Check for deadlocks
            cursor.execute("""
                SELECT deadlocks FROM pg_stat_database 
                WHERE datname = 'knowledge_base_db'
            """)
            deadlocks = cursor.fetchone()[0] or 0
            
            threshold = self.config['database']['alert_thresholds']['deadlock_count']
            if deadlocks > threshold:
                self.alerts.append(f"High deadlock count: {deadlocks} (threshold: {threshold})")
            
            cursor.close()
            conn.close()
            
            logger.info(f"Database health check: connections={connection_count}, cache_hit={cache_hit_ratio:.1f}%, deadlocks={deadlocks}")
            
        except Exception as e:
            self.alerts.append(f"Database health check failed: {e}")
            logger.error(f"Database health check error: {e}")
    
    def check_system_health(self):
        """Check system resource usage"""
        try:
            # CPU usage
            cpu_percent = psutil.cpu_percent(interval=1)
            threshold = self.config['system']['alert_thresholds']['cpu_percent']
            if cpu_percent > threshold:
                self.alerts.append(f"High CPU usage: {cpu_percent}% (threshold: {threshold}%)")
            
            # Memory usage
            memory = psutil.virtual_memory()
            threshold = self.config['system']['alert_thresholds']['memory_percent']
            if memory.percent > threshold:
                self.alerts.append(f"High memory usage: {memory.percent}% (threshold: {threshold}%)")
            
            # Disk usage
            disk = psutil.disk_usage('/')
            disk_percent = disk.used / disk.total * 100
            threshold = self.config['system']['alert_thresholds']['disk_percent']
            if disk_percent > threshold:
                self.alerts.append(f"High disk usage: {disk_percent:.1f}% (threshold: {threshold}%)")
            
            logger.info(f"System health check: cpu={cpu_percent}%, memory={memory.percent}%, disk={disk_percent:.1f}%")
            
        except Exception as e:
            self.alerts.append(f"System health check failed: {e}")
            logger.error(f"System health check error: {e}")
    
    def check_application_health(self):
        """Check application health via API"""
        try:
            api_url = self.config['application']['api_url']
            
            # Test API response time
            start_time = time.time()
            response = requests.get(f"{api_url}/health", timeout=10)
            response_time = time.time() - start_time
            
            threshold = self.config['application']['alert_thresholds']['response_time']
            if response_time > threshold:
                self.alerts.append(f"Slow API response: {response_time:.2f}s (threshold: {threshold}s)")
            
            # Check API status
            if response.status_code != 200:
                self.alerts.append(f"API health check failed: HTTP {response.status_code}")
            
            logger.info(f"Application health check: response_time={response_time:.2f}s, status={response.status_code}")
            
        except Exception as e:
            self.alerts.append(f"Application health check failed: {e}")
            logger.error(f"Application health check error: {e}")
    
    def send_alerts(self):
        """Send alerts if any were generated"""
        if not self.alerts:
            return
        
        alert_message = f"""
Knowledge Base Agent Alert - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

The following issues were detected:

"""
        for alert in self.alerts:
            alert_message += f"• {alert}\n"
        
        alert_message += f"""

Please investigate and take appropriate action.

System: {psutil.os.uname().nodename}
Monitoring Time: {datetime.now().isoformat()}
"""
        
        # Send email alerts
        if self.config['notifications']['email']['enabled']:
            self.send_email_alert(alert_message)
        
        # Send webhook alerts
        if self.config['notifications']['webhook']['enabled']:
            self.send_webhook_alert(alert_message)
        
        # Clear alerts after sending
        logger.warning(f"Sent {len(self.alerts)} alerts")
        self.alerts.clear()
    
    def send_email_alert(self, message):
        """Send email alert"""
        try:
            email_config = self.config['notifications']['email']
            
            msg = MIMEText(message)
            msg['Subject'] = 'Knowledge Base Agent Alert'
            msg['From'] = email_config['username']
            msg['To'] = ', '.join(email_config['recipients'])
            
            with smtplib.SMTP(email_config['smtp_server'], email_config['smtp_port']) as server:
                server.starttls()
                server.login(email_config['username'], email_config['password'])
                server.send_message(msg)
            
            logger.info("Email alert sent successfully")
            
        except Exception as e:
            logger.error(f"Failed to send email alert: {e}")
    
    def send_webhook_alert(self, message):
        """Send webhook alert (e.g., to Slack)"""
        try:
            webhook_config = self.config['notifications']['webhook']
            
            payload = {
                'text': f"🚨 Knowledge Base Agent Alert",
                'attachments': [{
                    'color': 'danger',
                    'text': message,
                    'ts': time.time()
                }]
            }
            
            response = requests.post(webhook_config['url'], json=payload, timeout=10)
            response.raise_for_status()
            
            logger.info("Webhook alert sent successfully")
            
        except Exception as e:
            logger.error(f"Failed to send webhook alert: {e}")
    
    def run_checks(self):
        """Run all health checks"""
        logger.info("Starting health checks...")
        
        self.check_database_health()
        self.check_system_health()
        self.check_application_health()
        
        if self.alerts:
            self.send_alerts()
        else:
            logger.info("All health checks passed")

def main():
    monitor = SystemMonitor('/opt/knowledge-base-monitoring/config.json')
    
    # Schedule checks every 5 minutes
    schedule.every(5).minutes.do(monitor.run_checks)
    
    logger.info("Starting monitoring service...")
    
    # Run initial check
    monitor.run_checks()
    
    # Run scheduled checks
    while True:
        schedule.run_pending()
        time.sleep(30)

if __name__ == "__main__":
    main()
EOF

# 5. Make monitoring script executable
chmod +x /opt/knowledge-base-monitoring/monitor.py

# 6. Create systemd service
sudo tee /etc/systemd/system/kb-monitoring.service > /dev/null << 'EOF'
[Unit]
Description=Knowledge Base Agent Monitoring
After=network.target postgresql.service

[Service]
Type=simple
User=kb-agent
Group=kb-agent
WorkingDirectory=/opt/knowledge-base-monitoring
ExecStart=/usr/bin/python3 /opt/knowledge-base-monitoring/monitor.py
Restart=always
RestartSec=30

[Install]
WantedBy=multi-user.target
EOF

# 7. Enable and start monitoring service
sudo systemctl daemon-reload
sudo systemctl enable kb-monitoring
sudo systemctl start kb-monitoring

echo "Monitoring setup completed!"
echo "Check status with: sudo systemctl status kb-monitoring"
echo "View logs with: journalctl -u kb-monitoring -f"
```

---

**Troubleshooting and Maintenance Guide Status**: ✅ Complete - All procedures documented and tested  
**Next Steps**: Train staff on procedures and implement automated monitoring 