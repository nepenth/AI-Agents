# Modern Real-time Communication Architecture

## Overview

We have successfully implemented the recommended hybrid architecture pattern:

**✅ Durable state in Postgres + initial REST snapshot + real-time push via Socket.IO backed by Redis**

This provides:
- **Postgres**: Source of truth for task state, phase states, and historical logs
- **REST APIs**: Initial fetch and history access
- **Socket.IO + Redis**: Ephemeral real-time UX with cross-process communication
- **Workers**: Emit lightweight, structured events alongside DB writes

## Architecture Components

### 1. Storage Layer (Postgres)

**Durable State Models:**
- `CeleryTaskState`: Per-task status, start/end, progress, metadata
- `TaskLog`: Persistent log storage via PostgreSQLLogger
- `JobHistory`: Comprehensive historical tracking
- `AgentState`: Current agent execution state

**Key Features:**
- Complete task lifecycle tracking
- Cross-session state recovery
- Historical analysis and reporting
- Comprehensive error tracking

### 2. REST API Layer (Initial Snapshots)

**Enhanced Endpoints:**

```python
# Task status with comprehensive data
GET /api/v2/tasks/<task_id>/status
# Returns: task state + phase states + recent logs + Celery info

# Historical logs with sequence-based pagination  
GET /api/v2/tasks/<task_id>/logs?since_sequence=0&limit=100
# Returns: PostgreSQL logs + Redis logs (merged and deduplicated)

# Active task for frontend state restoration
GET /api/v2/agent/active
# Returns: Currently active task with full context

# Job history with filtering
GET /api/v2/jobs/history?limit=50&job_type=manual&status=SUCCESS
# Returns: Paginated job history with comprehensive metadata
```

**Frontend Integration Pattern:**
```javascript
// 1. On page load: Get initial snapshot via REST
const taskStatus = await fetch('/api/v2/tasks/abc123/status').then(r => r.json());
const initialLogs = await fetch('/api/v2/tasks/abc123/logs?limit=50').then(r => r.json());

// 2. Render initial state
renderTaskStatus(taskStatus);
populateLiveLogs(initialLogs.logs);

// 3. Subscribe to real-time updates
socket.emit('join_task', { task_id: 'abc123' });
socket.on('phase_update', handlePhaseUpdate);
socket.on('log', handleNewLog);
```

### 3. Real-time Layer (Socket.IO + Redis)

**Cross-Process Communication:**
- Web server: `SocketIO(message_queue=redis_url)` 
- Celery workers: `ModernRealtimeEmitter` with same Redis message_queue
- Task-specific rooms: `task:abc123` for targeted updates

**Standardized Event Payloads:**

```python
# Phase Update Event
{
    "task_id": "abc123",
    "phase_id": "tweet_caching", 
    "status": "active|completed|error",
    "message": "Caching 15 tweets...",
    "processed_count": 5,
    "total_count": 15,
    "error_count": 0,
    "eta_seconds": 120,
    "timestamp": "2025-01-08T12:00:00Z"
}

# Phase Complete Event  
{
    "task_id": "abc123",
    "phase_id": "tweet_caching",
    "processed_count": 15,
    "total_count": 15, 
    "error_count": 0,
    "duration_seconds": 45.2,
    "timestamp": "2025-01-08T12:00:45Z"
}

# Log Event
{
    "task_id": "abc123",
    "sequence": 42,
    "level": "INFO",
    "message": "✅ Tweet caching completed successfully",
    "component": "content_processor",
    "phase": "tweet_caching",
    "timestamp": "2025-01-08T12:00:45Z"
}

# Task Status Event
{
    "task_id": "abc123", 
    "is_running": true,
    "current_phase_message": "Processing media analysis...",
    "current_phase": "media_analysis",
    "started_at": "2025-01-08T11:59:00Z",
    "updated_at": "2025-01-08T12:00:45Z"
}
```

### 4. Worker Integration (Celery Tasks)

**Modern Real-time Emitter Usage:**

```python
from knowledge_base_agent.realtime_communication import (
    emit_phase_update, emit_phase_complete, emit_log_event, emit_task_status
)

# In Celery worker task
def process_tweets(task_id, tweets):
    # Emit phase start
    emit_phase_update(
        task_id=task_id,
        phase_id="tweet_processing", 
        status="active",
        message=f"Processing {len(tweets)} tweets...",
        total_count=len(tweets)
    )
    
    # Process items with progress updates
    for i, tweet in enumerate(tweets):
        process_single_tweet(tweet)
        
        # Emit progress
        emit_phase_update(
            task_id=task_id,
            phase_id="tweet_processing",
            status="in_progress", 
            message=f"Processed {i+1} of {len(tweets)} tweets",
            processed_count=i+1,
            total_count=len(tweets)
        )
        
        # Emit logs
        emit_log_event(
            task_id=task_id,
            level="INFO",
            message=f"✅ Processed tweet {tweet['id']}",
            component="tweet_processor"
        )
    
    # Emit completion
    emit_phase_complete(
        task_id=task_id,
        phase_id="tweet_processing",
        processed_count=len(tweets),
        total_count=len(tweets),
        duration_seconds=time.time() - start_time
    )
```

## Key Benefits

### 1. **Reliability**
- **Durable state**: Task progress survives server restarts
- **Cross-session recovery**: Frontend restores state on page load
- **Fallback graceful**: REST API works even if SocketIO fails
- **Data consistency**: Single source of truth in Postgres

### 2. **Performance** 
- **Initial snapshots**: Fast page loads with REST
- **Real-time updates**: Low-latency SocketIO push
- **Targeted events**: Task-specific rooms reduce noise
- **Event batching**: Efficient transmission via Redis

### 3. **Scalability**
- **Cross-process**: Workers emit events via Redis message_queue
- **Horizontal scaling**: Multiple workers, single web server
- **Resource efficiency**: Lightweight event payloads
- **Connection pooling**: Redis handles multiple connections

### 4. **Developer Experience**
- **Type-safe events**: Standardized event payloads with dataclasses
- **Consistent patterns**: Same event structure across all components
- **Easy debugging**: Comprehensive logging and error tracking
- **Clean separation**: Clear boundaries between layers

## Implementation Status

### ✅ Completed Components

1. **Enhanced Web Server Configuration**
   - Redis message_queue integration
   - Task-specific room management
   - Initial state restoration from database

2. **Modern Real-time Communication System**
   - `ModernRealtimeEmitter` for cross-process events
   - Standardized event payloads with dataclasses
   - Type-safe event factory methods

3. **Enhanced API Endpoints**
   - Comprehensive task status with phase details
   - Historical logs with sequence-based pagination
   - Active task detection for state recovery

4. **Worker Integration**
   - Content processor updated with real-time emitter
   - Cross-process phase completion events
   - Structured log emission

5. **Database Persistence**
   - PostgreSQL logging for durability
   - Enhanced task state management
   - Comprehensive job history tracking

### 🔄 Integration Points

The system now follows this flow:

1. **Task Creation** (REST API)
   ```
   POST /api/v2/agent/start → TaskStateManager.create_task() → Celery.delay()
   ```

2. **Task Execution** (Celery Worker)
   ```
   Worker → PostgreSQLLogger.log() + ModernRealtimeEmitter.emit() → Redis
   ```

3. **Real-time Updates** (SocketIO)
   ```
   Redis message_queue → Web Server SocketIO → Client (task:abc123 room)
   ```

4. **State Recovery** (Frontend)
   ```
   Page Load → GET /api/v2/tasks/abc123/status → Render + Subscribe to SocketIO
   ```

## Usage Examples

### Frontend Integration

```javascript
class ModernTaskManager {
    async loadTask(taskId) {
        // 1. Get initial snapshot
        const status = await this.api.get(`/v2/tasks/${taskId}/status`);
        const logs = await this.api.get(`/v2/tasks/${taskId}/logs?limit=50`);
        
        // 2. Render initial state
        this.renderTaskStatus(status);
        this.renderLogs(logs.logs);
        
        // 3. Join task room for targeted updates
        this.socket.emit('join_task', { task_id: taskId });
        
        // 4. Subscribe to real-time events
        this.socket.on('phase_update', this.handlePhaseUpdate.bind(this));
        this.socket.on('phase_complete', this.handlePhaseComplete.bind(this));
        this.socket.on('log', this.handleNewLog.bind(this));
    }
    
    handlePhaseUpdate(data) {
        if (data.task_id === this.currentTaskId) {
            this.updatePhaseProgress(data.phase_id, data);
        }
    }
    
    handleNewLog(data) {
        if (data.task_id === this.currentTaskId) {
            this.appendLog(data);
        }
    }
}
```

### Worker Implementation

```python
@celery_app.task(bind=True)
def run_agent_task(self, task_id: str, preferences: Dict[str, Any]):
    from knowledge_base_agent.realtime_communication import emit_task_status
    
    # Update task status
    emit_task_status(
        task_id=task_id,
        is_running=True,
        current_phase_message="Agent execution started"
    )
    
    # Execute phases with real-time updates
    content_processor = StreamlinedContentProcessor(
        config=config,
        task_id=task_id  # Enables real-time communication
    )
    
    # Process content (automatically emits phase updates)
    await content_processor.process_all_tweets(...)
    
    # Final status update
    emit_task_status(
        task_id=task_id,
        is_running=False,
        current_phase_message="Agent execution completed"
    )
```

## Migration Benefits

This architecture provides significant improvements over the previous system:

1. **Eliminated Race Conditions**: Durable state prevents lost progress
2. **Cross-Session Continuity**: Tasks survive browser refreshes
3. **Scalable Communication**: Redis message_queue enables multi-worker setups
4. **Type Safety**: Standardized events prevent payload mismatches
5. **Debugging Clarity**: Comprehensive logging and error tracking
6. **Performance Optimization**: Targeted updates reduce unnecessary traffic

The system now provides enterprise-grade reliability while maintaining the responsive real-time UX that users expect.