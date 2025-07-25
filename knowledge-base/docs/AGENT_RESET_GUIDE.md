# Agent Reset Guide

## Overview

The Knowledge Base Agent now has enhanced reset functionality to handle stuck jobs and orphaned tasks. This guide explains the different reset options available and when to use them.

## The Problem

Sometimes agent tasks can get stuck in a "running" state in the database while the actual Celery worker process has finished or been terminated. This creates orphaned database records that prevent new agent runs from starting.

Common symptoms:
- Frontend shows agent as "running" but no actual processing is happening
- Cannot start new agent runs due to "Another agent task is already running" error
- Tasks stuck in PROGRESS status for hours or days
- Celery shows 0 active tasks but database shows running tasks

## Enhanced Reset Solutions

### 1. Frontend Reset Button (Recommended)

The **Reset Agent State** button in the web interface now performs comprehensive cleanup:

**Location**: Agent Control Panel → System Utilities → Reset Agent State

**What it does**:
- ✅ Stops any running Celery tasks
- ✅ Clears stuck database records
- ✅ Clears Redis progress data
- ✅ Resets agent to idle state
- ✅ Provides detailed feedback on what was cleaned

**How to use**:
1. Click the "Reset Agent State" button
2. Confirm the comprehensive cleanup operation
3. Wait for success message showing how many stuck tasks were cleaned
4. Page will automatically refresh to show clean state

### 2. Command Line Tools

#### Quick Reset Script
```bash
# Simple utility for emergency cleanup
python3 clear_stuck_tasks.py

# Dry run to see what would be cleaned
python3 clear_stuck_tasks.py --dry-run

# Force cleanup without confirmation
python3 clear_stuck_tasks.py --force
```

#### Celery Monitor Commands
```bash
# Check for stuck tasks
python3 celery_monitor.py stuck-tasks

# View current statistics
python3 celery_monitor.py stats

# Comprehensive reset (recommended)
python3 celery_monitor.py comprehensive-reset

# Dry run to see what would be cleaned
python3 celery_monitor.py comprehensive-reset --dry-run

# Force reset without confirmation
python3 celery_monitor.py comprehensive-reset --force

# Basic agent state reset (less comprehensive)
python3 celery_monitor.py reset-agent-state
```

## What Gets Cleaned Up

### Database Records
- Tasks stuck in PENDING, PROGRESS, or STARTED status
- Marks them as REVOKED with completion timestamp
- Sets is_active=False to prevent conflicts
- Resets AgentState to idle

### Celery Tasks
- Revokes any active Celery tasks with SIGTERM
- Revokes tasks by both custom task_id and Celery task_id
- Handles cases where Celery tasks are already terminated

### Redis Data
- Clears progress tracking data for stuck tasks
- Clears log data for stuck tasks
- Prevents memory leaks from orphaned data

### Agent State
- Sets is_running=False
- Clears current_task_id
- Resets phase message to "Idle"
- Updates last_update timestamp

## When to Use Each Method

### Use Frontend Reset When:
- ✅ You have web access
- ✅ You want detailed feedback
- ✅ You prefer a user-friendly interface
- ✅ You want automatic page refresh

### Use Command Line When:
- ✅ You're debugging or developing
- ✅ Web interface is not accessible
- ✅ You want to script the reset process
- ✅ You need to check what would be cleaned first (dry-run)

## Troubleshooting

### If Reset Doesn't Work
1. Check if Celery workers are running:
   ```bash
   python3 celery_monitor.py stats
   ```

2. Manually clear Redis if needed:
   ```bash
   python3 celery_monitor.py flush-redis
   ```

3. Check for database connection issues in logs

4. Restart Celery workers if necessary:
   ```bash
   python3 celery_monitor.py restart-workers
   ```

### If Tasks Keep Getting Stuck
1. Check the root cause in synthesis generation or other phases
2. Review timeout settings in configuration
3. Monitor system resources (CPU, memory, GPU)
4. Check for network connectivity issues with external services

## Prevention

To prevent tasks from getting stuck:

1. **Monitor Long-Running Operations**: Keep an eye on synthesis generation which can take 10+ minutes
2. **Check System Resources**: Ensure adequate CPU, memory, and GPU resources
3. **Review Logs**: Look for timeout errors or resource exhaustion
4. **Update Timeouts**: Increase timeouts for operations that legitimately take longer
5. **Regular Cleanup**: Periodically clean up old completed tasks

## Technical Details

The enhanced reset function performs these operations in order:

1. **Discovery**: Find all tasks in non-terminal states (PENDING, PROGRESS, STARTED)
2. **Celery Cleanup**: Revoke active Celery tasks and stuck task IDs
3. **Redis Cleanup**: Clear progress and log data for each stuck task
4. **Database Update**: Mark stuck tasks as REVOKED with completion timestamps
5. **State Reset**: Reset AgentState to idle with clean status
6. **Verification**: Ensure all active flags are cleared

This comprehensive approach ensures that all aspects of the task lifecycle are properly cleaned up, preventing future conflicts and ensuring a clean slate for new agent runs.

## API Reference

### REST Endpoint
```
POST /api/agent/reset-state
```

**Response**:
```json
{
  "success": true,
  "message": "Agent state reset with comprehensive cleanup. Cleaned up 5 stuck tasks.",
  "stuck_tasks_cleaned": 5,
  "previous_active_task": {...}
}
```

### JavaScript API
```javascript
// Frontend usage
const result = await window.api.resetAgentState();

// Task state manager usage
await window.taskStateManager.resetAgentState();
```

This enhanced reset functionality ensures that stuck jobs are properly cleaned up and the agent can return to a healthy state for new operations.