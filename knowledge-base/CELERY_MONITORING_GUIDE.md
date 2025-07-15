# Celery Task Monitoring and Management Guide

This guide provides comprehensive instructions for monitoring and managing Celery tasks in the knowledge base agent system, including detecting stuck jobs and flushing old tasks.

## Quick Start

### 1. Check Current Status
```bash
# Check overall stats
python celery_monitor.py stats

# List active tasks
python celery_monitor.py active-tasks

# Check for stuck tasks
python celery_monitor.py stuck-tasks
```

### 2. Clean Up Old Tasks
```bash
# Clear tasks older than 24 hours (dry run first)
python celery_monitor.py clear-old-tasks --dry-run

# Actually clear them
python celery_monitor.py clear-old-tasks

# Clear failed tasks older than 12 hours
python celery_monitor.py clear-old-tasks --older-than 12 --status FAILURE
```

### 3. Emergency Cleanup
```bash
# Revoke all active tasks
python celery_monitor.py revoke-tasks --all-active

# Flush all Redis data
python celery_monitor.py flush-redis

# Reset agent state
python celery_monitor.py reset-agent-state
```

## Detailed Commands

### Monitor Active Tasks

```bash
# List all currently running tasks
python celery_monitor.py active-tasks
```

This shows:
- Worker name
- Task ID
- Task name
- Start time
- Arguments

### Check for Stuck Tasks

```bash
# Find tasks running longer than 3 hours
python celery_monitor.py stuck-tasks
```

This identifies tasks that may be stuck in a loop or hanging.

### View Statistics

```bash
# Show comprehensive task statistics
python celery_monitor.py stats
```

Displays:
- Database task counts by status
- Celery worker statistics
- Currently active task count

### Clear Old Tasks

```bash
# Clear tasks older than 24 hours (default)
python celery_monitor.py clear-old-tasks

# Clear tasks older than 12 hours
python celery_monitor.py clear-old-tasks --older-than 12

# Clear only failed tasks
python celery_monitor.py clear-old-tasks --status FAILURE

# Clear multiple statuses
python celery_monitor.py clear-old-tasks --status FAILURE --status SUCCESS

# Dry run to see what would be deleted
python celery_monitor.py clear-old-tasks --dry-run
```

### Revoke Running Tasks

```bash
# Revoke a specific task
python celery_monitor.py revoke-tasks --task-id YOUR_TASK_ID

# Revoke all active tasks
python celery_monitor.py revoke-tasks --all-active
```

### Flush Redis Data

```bash
# Clear all task progress and logs from Redis
python celery_monitor.py flush-redis
```

⚠️ **Warning**: This clears ALL task data from Redis including progress and logs.

### Reset Agent State

```bash
# Reset the agent database state to idle
python celery_monitor.py reset-agent-state
```

### Purge Message Queues

```bash
# Purge all queues
python celery_monitor.py purge-queues

# Purge specific queue
python celery_monitor.py purge-queues --queue agent
```

## Using Built-in Celery Commands

### Celery CLI Commands

```bash
# Monitor tasks with Flower (web dashboard)
python -m knowledge_base_agent.cli monitor

# Start worker
python -m knowledge_base_agent.cli worker

# Check worker status
celery -A knowledge_base_agent.celery_app status

# Get detailed worker statistics
celery -A knowledge_base_agent.celery_app inspect stats

# List active tasks
celery -A knowledge_base_agent.celery_app inspect active

# List scheduled tasks
celery -A knowledge_base_agent.celery_app inspect scheduled

# Revoke task
celery -A knowledge_base_agent.celery_app control revoke TASK_ID

# Shutdown worker
celery -A knowledge_base_agent.celery_app control shutdown
```

### Flower Dashboard

Start the Flower monitoring dashboard:

```bash
python -m knowledge_base_agent.cli monitor --port 5555
```

Then visit http://localhost:5555 to see:
- Real-time task monitoring
- Worker status
- Task history
- Task details and logs

## Redis Commands

### Direct Redis Access

```bash
# Connect to Redis
redis-cli -p 6379

# List all keys
KEYS *

# List progress keys
KEYS progress:*

# List log keys  
KEYS logs:*

# Get task progress
HGETALL progress:YOUR_TASK_ID

# Get task logs
LRANGE logs:YOUR_TASK_ID 0 -1

# Clear specific task data
DEL progress:YOUR_TASK_ID
DEL logs:YOUR_TASK_ID

# Clear all task data
DEL progress:*
DEL logs:*
```

### Redis Database Layout

Your system uses three Redis databases:
- **DB 0**: Celery broker and result backend
- **DB 1**: Task progress tracking
- **DB 2**: Task logs

## Common Troubleshooting Scenarios

### 1. Tasks Stuck in Loop

**Symptoms**: Tasks running for hours without progress

**Solution**:
```bash
# Check stuck tasks
python celery_monitor.py stuck-tasks

# Revoke stuck tasks
python celery_monitor.py revoke-tasks --all-active

# Clear old task data
python celery_monitor.py clear-old-tasks --older-than 3
```

### 2. Queue Buildup

**Symptoms**: Many pending tasks, slow processing

**Solution**:
```bash
# Check stats
python celery_monitor.py stats

# Purge queues if needed
python celery_monitor.py purge-queues

# Start more workers
python -m knowledge_base_agent.cli worker --concurrency 4
```

### 3. Memory Issues

**Symptoms**: Workers consuming too much memory

**Solution**:
```bash
# Shutdown workers
celery -A knowledge_base_agent.celery_app control shutdown

# Clear all data
python celery_monitor.py flush-redis
python celery_monitor.py clear-old-tasks --older-than 1

# Restart workers
python -m knowledge_base_agent.cli worker
```

### 4. Database Inconsistencies

**Symptoms**: UI shows running but no active tasks

**Solution**:
```bash
# Reset agent state
python celery_monitor.py reset-agent-state

# Check for orphaned tasks
python celery_monitor.py stuck-tasks

# Clear inconsistent data
python celery_monitor.py clear-old-tasks --status PROGRESS
```

## Monitoring Best Practices

### Regular Maintenance

1. **Daily**: Check for stuck tasks
   ```bash
   python celery_monitor.py stuck-tasks
   ```

2. **Weekly**: Clear old completed tasks
   ```bash
   python celery_monitor.py clear-old-tasks --older-than 168 --status SUCCESS
   ```

3. **Monthly**: Full cleanup
   ```bash
   python celery_monitor.py clear-old-tasks --older-than 720
   python celery_monitor.py flush-redis
   ```

### Monitoring Alerts

Set up alerts for:
- Tasks running longer than 4 hours
- More than 10 pending tasks
- Worker memory usage > 80%
- Redis memory usage > 1GB

### Performance Tuning

```bash
# Increase worker concurrency
python -m knowledge_base_agent.cli worker --concurrency 8

# Monitor with Flower
python -m knowledge_base_agent.cli monitor

# Adjust prefetch multiplier in config
export CELERY_WORKER_PREFETCH_MULTIPLIER=4
```

## Configuration

### Environment Variables

```bash
# Celery Configuration
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/0
CELERY_TASK_TIME_LIMIT=7200  # 2 hours

# Redis Configuration
REDIS_PROGRESS_URL=redis://localhost:6379/1
REDIS_LOGS_URL=redis://localhost:6379/2
```

### Task Limits

The system has the following limits:
- **Task time limit**: 2 hours (7200 seconds)
- **Worker prefetch**: 1 task per worker
- **Result expiry**: 1 hour
- **Max tasks per worker**: 1000

## Emergency Procedures

### Complete Reset

If the system is completely stuck:

```bash
# 1. Stop all workers
celery -A knowledge_base_agent.celery_app control shutdown

# 2. Revoke all tasks
python celery_monitor.py revoke-tasks --all-active

# 3. Clear all data
python celery_monitor.py flush-redis
python celery_monitor.py clear-old-tasks --older-than 0

# 4. Reset agent state
python celery_monitor.py reset-agent-state

# 5. Restart workers
python -m knowledge_base_agent.cli worker
```

### Partial Reset

For less severe issues:

```bash
# Clear only old/stuck tasks
python celery_monitor.py clear-old-tasks --older-than 3
python celery_monitor.py revoke-tasks --all-active
python celery_monitor.py reset-agent-state
```

## Logs and Debugging

### View Logs

```bash
# System logs
tail -f logs/agent.log

# Celery worker logs
celery -A knowledge_base_agent.celery_app worker --loglevel=debug

# Task-specific logs (via Redis)
redis-cli -p 6379 -n 2 LRANGE logs:YOUR_TASK_ID 0 -1
```

### Debug Mode

Run workers in debug mode:

```bash
celery -A knowledge_base_agent.celery_app worker --loglevel=debug --concurrency=1
```

This provides detailed output for troubleshooting. 