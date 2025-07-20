#!/usr/bin/env python3
"""
Log Cleanup Utility

This script cleans up old and test logs from Redis to keep the Live Logs clean.
"""

import redis
import json
import sys
import os
from datetime import datetime, timedelta

# Add the project root to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from knowledge_base_agent.config import Config


def cleanup_logs():
    """Clean up old and test logs from Redis."""
    config = Config.from_env()
    redis_logs = redis.Redis.from_url(config.redis_logs_url, decode_responses=True)
    redis_progress = redis.Redis.from_url(config.redis_progress_url, decode_responses=True)
    
    print("🧹 Starting log cleanup...")
    
    # Get all log keys
    log_keys = redis_logs.keys('logs:*')
    progress_keys = redis_progress.keys('progress:*')
    
    print(f"Found {len(log_keys)} log keys and {len(progress_keys)} progress keys")
    
    # Cleanup criteria
    test_patterns = [
        'Test log message at',
        'Testing structured logging',
        'Phase started: test_phase',
        'Frontend compatibility test',
        'Validation test',
        'test_operation'
    ]
    
    error_patterns = [
        '--- Logging error ---',
        'UNIFIED_LOGGER_ERROR',
        'Failed to emit event',
        'circular logging'
    ]
    
    # Clean up test logs
    test_logs_cleaned = 0
    for key in log_keys:
        try:
            logs = redis_logs.lrange(key, 0, -1)
            is_test_log = False
            
            for log in logs:
                try:
                    log_data = json.loads(log)
                    message = log_data.get('message', '')
                    
                    # Check for test patterns
                    if any(pattern in message for pattern in test_patterns):
                        is_test_log = True
                        break
                        
                except json.JSONDecodeError:
                    continue
            
            if is_test_log:
                redis_logs.delete(key)
                test_logs_cleaned += 1
                print(f"  ✅ Cleaned test log: {key}")
                
        except Exception as e:
            print(f"  ❌ Error processing {key}: {e}")
    
    # Clean up error-heavy logs
    error_logs_cleaned = 0
    remaining_keys = redis_logs.keys('logs:*')
    
    for key in remaining_keys:
        try:
            logs = redis_logs.lrange(key, 0, -1)
            error_count = 0
            total_count = len(logs)
            
            if total_count == 0:
                continue
                
            for log in logs:
                try:
                    log_data = json.loads(log)
                    message = log_data.get('message', '')
                    level = log_data.get('level', '')
                    
                    # Count error patterns
                    if any(pattern in message for pattern in error_patterns) or level == 'ERROR':
                        error_count += 1
                        
                except json.JSONDecodeError:
                    continue
            
            # If more than 80% of logs are errors, clean it up
            if total_count > 5 and (error_count / total_count) > 0.8:
                redis_logs.delete(key)
                error_logs_cleaned += 1
                print(f"  ✅ Cleaned error-heavy log: {key} ({error_count}/{total_count} errors)")
                
        except Exception as e:
            print(f"  ❌ Error processing {key}: {e}")
    
    # Clean up old progress keys (older than 24 hours)
    old_progress_cleaned = 0
    cutoff_time = datetime.now() - timedelta(hours=24)
    
    for key in progress_keys:
        try:
            progress_data = redis_progress.hgetall(key)
            if progress_data and 'last_update' in progress_data:
                try:
                    last_update = datetime.fromisoformat(progress_data['last_update'].replace('Z', '+00:00'))
                    if last_update < cutoff_time:
                        redis_progress.delete(key)
                        old_progress_cleaned += 1
                        print(f"  ✅ Cleaned old progress: {key}")
                except ValueError:
                    # Invalid timestamp, clean it up
                    redis_progress.delete(key)
                    old_progress_cleaned += 1
                    print(f"  ✅ Cleaned invalid progress: {key}")
                    
        except Exception as e:
            print(f"  ❌ Error processing progress {key}: {e}")
    
    print(f"\n📊 Cleanup Summary:")
    print(f"  • Test logs cleaned: {test_logs_cleaned}")
    print(f"  • Error-heavy logs cleaned: {error_logs_cleaned}")
    print(f"  • Old progress keys cleaned: {old_progress_cleaned}")
    
    # Show remaining logs
    remaining_log_keys = redis_logs.keys('logs:*')
    remaining_progress_keys = redis_progress.keys('progress:*')
    
    print(f"  • Remaining log keys: {len(remaining_log_keys)}")
    print(f"  • Remaining progress keys: {len(remaining_progress_keys)}")
    
    if remaining_log_keys:
        print(f"\n📋 Remaining logs:")
        for key in remaining_log_keys[:3]:  # Show first 3
            try:
                logs = redis_logs.lrange(key, 0, 2)  # Get first 3 logs
                print(f"  {key}:")
                for log in logs:
                    try:
                        log_data = json.loads(log)
                        timestamp = log_data.get('timestamp', '')[:19]
                        level = log_data.get('level', '')
                        message = log_data.get('message', '')[:60]
                        print(f"    {timestamp} {level:7} {message}")
                    except:
                        print(f"    {log[:60]}...")
            except Exception as e:
                print(f"    Error reading {key}: {e}")
    
    print(f"\n✅ Log cleanup completed!")


if __name__ == "__main__":
    cleanup_logs()