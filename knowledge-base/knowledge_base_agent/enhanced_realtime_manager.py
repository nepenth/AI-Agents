"""
Enhanced Real-time Update Manager for Celery Tasks

This module provides an enhanced real-time communication system with
event validation, routing, batching, rate limiting, and connection health monitoring.
"""

import redis
import json
import logging
import threading
import time
from typing import Dict, Any, List, Optional, Callable, Set
from datetime import datetime, timedelta
from collections import defaultdict, deque
from dataclasses import dataclass, field
import queue

from flask_socketio import SocketIO
from .config import Config


@dataclass
class EventBatch:
    """Represents a batch of events for efficient transmission."""
    events: List[Dict[str, Any]] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)
    max_size: int = 10
    max_age_seconds: int = 1
    
    def add_event(self, event: Dict[str, Any]) -> bool:
        """
        Add an event to the batch.
        
        Args:
            event: The event to add
            
        Returns:
            bool: True if batch is ready to send after adding
        """
        self.events.append(event)
        return self.is_ready_to_send()
    
    def is_ready_to_send(self) -> bool:
        """Check if batch is ready to send based on size or age."""
        if len(self.events) >= self.max_size:
            return True
        
        age = datetime.now() - self.created_at
        return age.total_seconds() >= self.max_age_seconds
    
    def clear(self):
        """Clear the batch."""
        self.events.clear()
        self.created_at = datetime.now()


@dataclass
class RateLimitConfig:
    """Configuration for rate limiting."""
    max_events_per_second: int = 50
    max_events_per_minute: int = 1000
    burst_allowance: int = 10


class EventValidator:
    """Validates and sanitizes incoming Redis events."""
    
    REQUIRED_FIELDS = {
        'log_message': ['message'],  # Only message is truly required
        'phase_update': ['phase_id'],  # Only phase_id is required
        'progress_update': [],  # No strict requirements - be flexible
        'status_update': []  # No strict requirements - be flexible
    }
    
    ALLOWED_LOG_LEVELS = {'DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'}
    ALLOWED_PHASE_STATUSES = {'pending', 'active', 'in_progress', 'completed', 'error', 'skipped', 'interrupted', 'running', 'idle', 'starting', 'finishing', 'failed'}
    
    @classmethod
    def validate_event(cls, event_type: str, data: Dict[str, Any]) -> tuple[bool, Optional[str], Optional[Dict[str, Any]]]:
        """
        Validate and sanitize an event.
        
        Args:
            event_type: The type of event
            data: The event data
            
        Returns:
            tuple: (is_valid, error_message, sanitized_data)
        """
        if not isinstance(data, dict):
            return False, "Event data must be a dictionary", None
        
        # Check required fields
        required_fields = cls.REQUIRED_FIELDS.get(event_type, [])
        for field in required_fields:
            if field not in data:
                return False, f"Missing required field: {field}", None
        
        # Create sanitized copy
        sanitized = data.copy()
        
        # Type-specific validation and sanitization
        if event_type == 'log_message':
            return cls._validate_log_message(sanitized)
        elif event_type == 'phase_update':
            return cls._validate_phase_update(sanitized)
        elif event_type == 'progress_update':
            return cls._validate_progress_update(sanitized)
        elif event_type == 'status_update':
            return cls._validate_status_update(sanitized)
        
        # Default validation for unknown types
        return True, None, sanitized
    
    @classmethod
    def _validate_log_message(cls, data: Dict[str, Any]) -> tuple[bool, Optional[str], Dict[str, Any]]:
        """Validate log message event."""
        # Sanitize log level
        level = str(data.get('level', 'INFO')).upper()
        if level not in cls.ALLOWED_LOG_LEVELS:
            level = 'INFO'
        data['level'] = level
        
        # Ensure message is string
        data['message'] = str(data.get('message', ''))
        
        # Add timestamp if missing
        if 'timestamp' not in data:
            data['timestamp'] = datetime.now().isoformat()
        
        # Truncate very long messages
        if len(data['message']) > 10000:
            data['message'] = data['message'][:9997] + '...'
            data['truncated'] = True
        
        return True, None, data
    
    @classmethod
    def _validate_phase_update(cls, data: Dict[str, Any]) -> tuple[bool, Optional[str], Dict[str, Any]]:
        """Validate phase update event."""
        # Sanitize phase status - be more flexible
        status = str(data.get('status', 'pending')).lower()
        if status not in cls.ALLOWED_PHASE_STATUSES:
            # Don't reject - just use a default status
            logging.debug(f"Unknown phase status '{status}', using 'in_progress'")
            status = 'in_progress'
        data['status'] = status
        
        # Ensure phase_id is string
        data['phase_id'] = str(data.get('phase_id', 'unknown'))
        
        # Ensure message is string
        data['message'] = str(data.get('message', ''))
        
        # Validate progress data if present - be more flexible
        if 'processed_count' in data and 'total_count' in data:
            try:
                processed = int(data['processed_count'])
                total = int(data['total_count'])
                # Allow more flexible progress counts
                if processed < 0:
                    processed = 0
                if total < 0:
                    total = 0
                if processed > total and total > 0:
                    processed = total
                data['processed_count'] = processed
                data['total_count'] = total
            except (ValueError, TypeError):
                # Don't fail - just remove invalid progress data
                data.pop('processed_count', None)
                data.pop('total_count', None)
        
        return True, None, data
    
    @classmethod
    def _validate_progress_update(cls, data: Dict[str, Any]) -> tuple[bool, Optional[str], Dict[str, Any]]:
        """Validate progress update event."""
        # Make progress validation optional - not all progress events have counts
        if 'processed_count' in data and 'total_count' in data:
            try:
                processed = int(data['processed_count'])
                total = int(data['total_count'])
                
                if processed < 0 or total < 0:
                    return False, "Progress counts cannot be negative", None
                
                if total > 0 and processed > total:
                    return False, "Processed count cannot exceed total", None
                
                data['processed_count'] = processed
                data['total_count'] = total
                
                # Calculate percentage
                if total > 0:
                    data['percentage'] = int((processed / total) * 100)
                else:
                    data['percentage'] = 0
                    
            except (ValueError, TypeError):
                return False, "Progress counts must be integers", None
        else:
            # Progress update without specific counts - just pass through
            # This handles general progress messages without numeric data
            pass
        
        return True, None, data
    
    @classmethod
    def _validate_status_update(cls, data: Dict[str, Any]) -> tuple[bool, Optional[str], Dict[str, Any]]:
        """Validate status update event."""
        # Ensure required fields are strings
        data['status'] = str(data.get('status', ''))
        data['phase'] = str(data.get('phase', ''))
        
        return True, None, data


class EventRouter:
    """Routes different event types to appropriate SocketIO channels."""
    
    # Mapping of Redis channels to event types and SocketIO events
    CHANNEL_MAPPING = {
        'realtime_events': {
            'log_message': ['log', 'live_log'],
            'phase_update': ['phase_update', 'phase_status_update', 'task_progress'],
            'progress_update': ['progress_update', 'task_progress'],
            'status_update': ['agent_status_update', 'status_update'],
            'agent_status': ['agent_status', 'agent_status_update'],
            'phase_start': ['phase_update', 'phase_start'],
            'phase_complete': ['phase_update', 'phase_complete'],
            'phase_error': ['phase_update', 'phase_error']
        },
        'task_logs': {
            'log_message': ['log', 'live_log']
        },
        'task_phase_updates': {
            'phase_update': ['phase_update', 'phase_status_update']
        },
        'task_status_updates': {
            'status_update': ['agent_status_update', 'status_update']
        }
    }
    
    @classmethod
    def get_socketio_events(cls, channel: str, event_type: str) -> List[str]:
        """
        Get SocketIO event names for a Redis channel and event type.
        
        Args:
            channel: Redis channel name
            event_type: Event type from the data
            
        Returns:
            List[str]: List of SocketIO event names to emit
        """
        channel_config = cls.CHANNEL_MAPPING.get(channel, {})
        return channel_config.get(event_type, [])


class RateLimiter:
    """Rate limiter for event emission."""
    
    def __init__(self, config: RateLimitConfig):
        self.config = config
        self.event_times = deque()
        self.minute_counts = defaultdict(int)
        self.lock = threading.Lock()
    
    def is_allowed(self) -> bool:
        """
        Check if an event is allowed based on rate limits.
        
        Returns:
            bool: True if event is allowed
        """
        now = datetime.now()
        
        with self.lock:
            # Clean old entries
            self._clean_old_entries(now)
            
            # Check per-second limit
            recent_events = sum(1 for t in self.event_times if (now - t).total_seconds() <= 1)
            if recent_events >= self.config.max_events_per_second:
                return False
            
            # Check per-minute limit
            minute_key = now.strftime('%Y-%m-%d %H:%M')
            if self.minute_counts[minute_key] >= self.config.max_events_per_minute:
                return False
            
            # Record this event
            self.event_times.append(now)
            self.minute_counts[minute_key] += 1
            
            return True
    
    def _clean_old_entries(self, now: datetime):
        """Clean old entries from tracking structures."""
        # Remove events older than 1 second
        while self.event_times and (now - self.event_times[0]).total_seconds() > 1:
            self.event_times.popleft()
        
        # Remove minute counts older than 1 minute
        cutoff_minute = (now - timedelta(minutes=1)).strftime('%Y-%m-%d %H:%M')
        keys_to_remove = [k for k in self.minute_counts.keys() if k < cutoff_minute]
        for key in keys_to_remove:
            del self.minute_counts[key]


class ConnectionHealthMonitor:
    """Monitors connection health and handles reconnection with exponential backoff."""
    
    def __init__(self, redis_client: redis.Redis, reconnect_callback: Optional[Callable] = None):
        self.redis_client = redis_client
        self.reconnect_callback = reconnect_callback
        self.is_healthy = True
        self.last_health_check = datetime.now()
        self.health_check_interval = 30  # seconds
        self.consecutive_failures = 0
        self.max_consecutive_failures = 3
        
        # Exponential backoff configuration
        self.base_backoff_delay = 1.0  # Start with 1 second
        self.max_backoff_delay = 60.0  # Max 60 seconds
        self.backoff_multiplier = 2.0
        self.current_backoff_delay = self.base_backoff_delay
        self.last_reconnect_attempt = None
        self.max_reconnect_attempts = 10
        self.reconnect_attempts = 0
    
    def check_health(self) -> bool:
        """
        Check Redis connection health with exponential backoff.
        
        Returns:
            bool: True if connection is healthy
        """
        now = datetime.now()
        if (now - self.last_health_check).total_seconds() < self.health_check_interval:
            return self.is_healthy
        
        try:
            # Simple ping to check connection
            self.redis_client.ping()
            
            # Connection successful - reset backoff and counters
            if not self.is_healthy:
                logging.info("Redis connection restored after failure")
            
            self.is_healthy = True
            self.consecutive_failures = 0
            self.reconnect_attempts = 0
            self.current_backoff_delay = self.base_backoff_delay
            self.last_health_check = now
            return True
            
        except Exception as e:
            logging.warning(f"Redis health check failed: {e}")
            self.consecutive_failures += 1
            self.last_health_check = now
            
            if self.consecutive_failures >= self.max_consecutive_failures:
                self.is_healthy = False
                
                # Check if we should attempt reconnection with backoff
                if self._should_attempt_reconnection(now):
                    if self.reconnect_callback:
                        self.reconnect_callback()
                    self._update_backoff_delay()
            
            return False
    
    def reset_health(self):
        """Reset health status after successful reconnection."""
        self.is_healthy = True
        self.consecutive_failures = 0
        self.reconnect_attempts = 0
        self.current_backoff_delay = self.base_backoff_delay
        self.last_health_check = datetime.now()
    
    def _should_attempt_reconnection(self, now: datetime) -> bool:
        """
        Check if we should attempt reconnection based on exponential backoff.
        
        Args:
            now: Current datetime
            
        Returns:
            bool: True if reconnection should be attempted
        """
        # Don't exceed max attempts
        if self.reconnect_attempts >= self.max_reconnect_attempts:
            logging.warning(f"Max reconnection attempts ({self.max_reconnect_attempts}) reached")
            return False
        
        # Check if enough time has passed since last attempt
        if self.last_reconnect_attempt is None:
            return True
        
        time_since_last_attempt = (now - self.last_reconnect_attempt).total_seconds()
        return time_since_last_attempt >= self.current_backoff_delay
    
    def _update_backoff_delay(self):
        """Update the backoff delay using exponential backoff."""
        self.last_reconnect_attempt = datetime.now()
        self.reconnect_attempts += 1
        
        # Calculate next backoff delay
        self.current_backoff_delay = min(
            self.current_backoff_delay * self.backoff_multiplier,
            self.max_backoff_delay
        )
        
        logging.info(f"Reconnection attempt {self.reconnect_attempts}/{self.max_reconnect_attempts}, "
                    f"next attempt in {self.current_backoff_delay:.1f}s")
    
    def get_connection_stats(self) -> Dict[str, Any]:
        """Get connection health statistics."""
        return {
            'is_healthy': self.is_healthy,
            'consecutive_failures': self.consecutive_failures,
            'reconnect_attempts': self.reconnect_attempts,
            'max_reconnect_attempts': self.max_reconnect_attempts,
            'current_backoff_delay': self.current_backoff_delay,
            'max_backoff_delay': self.max_backoff_delay,
            'last_health_check': self.last_health_check.isoformat() if self.last_health_check else None,
            'last_reconnect_attempt': self.last_reconnect_attempt.isoformat() if self.last_reconnect_attempt else None
        }


class EnhancedRealtimeManager:
    """
    Enhanced real-time update manager with comprehensive features.
    
    Features:
    - Event validation and sanitization
    - Event routing to multiple SocketIO channels
    - Event batching for efficiency
    - Rate limiting to prevent overwhelming
    - Connection health monitoring
    - Automatic reconnection
    - Event buffering during disconnections
    """
    
    def __init__(self, socketio: SocketIO, config: Optional[Config] = None):
        """
        Initialize the Enhanced RealtimeManager.
        
        Args:
            socketio: The Flask-SocketIO instance
            config: Optional configuration object
        """
        self.socketio = socketio
        self.config = config or Config()
        
        # Redis connections: separate clients for progress and logs DBs
        self.redis_progress_client = redis.Redis.from_url(
            self.config.redis_progress_url,
            decode_responses=True,
            socket_connect_timeout=5,
            socket_timeout=5,
            retry_on_timeout=True
        )
        self.redis_logs_client = redis.Redis.from_url(
            self.config.redis_logs_url,
            decode_responses=True,
            socket_connect_timeout=5,
            socket_timeout=5,
            retry_on_timeout=True
        )
        
        # Components
        self.validator = EventValidator()
        self.router = EventRouter()
        self.rate_limiter = RateLimiter(RateLimitConfig())
        self.health_monitor_progress = ConnectionHealthMonitor(
            self.redis_progress_client,
            self._handle_reconnection_progress
        )
        self.health_monitor_logs = ConnectionHealthMonitor(
            self.redis_logs_client,
            self._handle_reconnection_logs
        )
        
        # Threading and control
        self.pubsub_thread_progress = None
        self.pubsub_thread_logs = None
        self.batch_thread = None
        self._stop_event = threading.Event()
        
        # Event batching
        self.event_batches = defaultdict(EventBatch)
        self.batch_queue = queue.Queue()
        
        # Event buffering during disconnections
        self.event_buffer = deque(maxlen=1000)
        self.buffer_enabled = False
        
        # Statistics
        self.stats = {
            'events_processed': 0,
            'events_validated': 0,
            'events_rejected': 0,
            'events_rate_limited': 0,
            'events_buffered': 0,
            'reconnections': 0
        }
    
    def start_listener(self):
        """Start the Redis pub/sub listener and batch processor."""
        if self.pubsub_thread_progress and self.pubsub_thread_progress.is_alive():
            logging.warning("EnhancedRealtimeManager listener is already running.")
            return
        
        logging.info("Starting EnhancedRealtimeManager...")
        self._stop_event.clear()
        
        # Start pub/sub listener threads for progress and logs
        self.pubsub_thread_progress = threading.Thread(
            target=self._listen_for_updates_progress,
            daemon=True,
            name="RealtimeManager-PubSub-Progress"
        )
        self.pubsub_thread_progress.start()

        self.pubsub_thread_logs = threading.Thread(
            target=self._listen_for_updates_logs,
            daemon=True,
            name="RealtimeManager-PubSub-Logs"
        )
        self.pubsub_thread_logs.start()
        
        # Start batch processor thread
        self.batch_thread = threading.Thread(
            target=self._process_batches,
            daemon=True,
            name="RealtimeManager-Batch"
        )
        self.batch_thread.start()
        
        logging.info("EnhancedRealtimeManager started successfully.")
    
    def stop_listener(self):
        """Stop the Redis pub/sub listener and batch processor."""
        if not self.pubsub_thread_progress or not self.pubsub_thread_progress.is_alive():
            logging.warning("EnhancedRealtimeManager listener is not running.")
            return
        
        logging.info("Stopping EnhancedRealtimeManager...")
        self._stop_event.set()
        
        # Wait for threads to finish
        if self.pubsub_thread_progress:
            self.pubsub_thread_progress.join(timeout=5)
        if self.pubsub_thread_logs:
            self.pubsub_thread_logs.join(timeout=5)
        if self.batch_thread:
            self.batch_thread.join(timeout=5)
        
        logging.info("EnhancedRealtimeManager stopped.")
    
    def _listen_for_updates_progress(self):
        """Listener for progress/status channels on the progress Redis DB."""
        pubsub = None
        
        try:
            pubsub = self.redis_progress_client.pubsub(ignore_subscribe_messages=True)
            
            # STANDARDIZED: Subscribe to exact channels used by TaskProgressManager
            from .task_progress import TaskProgressManager
            pubsub.subscribe(TaskProgressManager.PHASE_CHANNEL)
            pubsub.subscribe(TaskProgressManager.STATUS_CHANNEL)
            
            # Also subscribe to legacy realtime_events channel for backward compatibility
            pubsub.subscribe("realtime_events")
            
            logging.info(f"✅ EnhancedRealtimeManager subscribed (progress DB) to: {TaskProgressManager.PHASE_CHANNEL}, {TaskProgressManager.STATUS_CHANNEL}, realtime_events")
            
            while not self._stop_event.is_set():
                try:
                    # Check connection health periodically
                    if not self.health_monitor_progress.check_health():
                        logging.warning("Redis connection unhealthy, enabling event buffering")
                        self.buffer_enabled = True
                        time.sleep(5)
                        continue
                    else:
                        if self.buffer_enabled:
                            logging.info("Redis connection restored, processing buffered events")
                            self._process_buffered_events()
                            self.buffer_enabled = False
                    
                    # Get message with timeout
                    message = pubsub.get_message(timeout=1.0)
                    if message is None:
                        continue
                    
                    self._handle_redis_message(message)
                    
                except redis.exceptions.ConnectionError as e:
                    logging.error(f"Redis connection error: {e}")
                    self.buffer_enabled = True
                    time.sleep(5)
                except Exception as e:
                    logging.error(f"Error in RealtimeManager listener: {e}", exc_info=True)
                    time.sleep(1)
        
        except Exception as e:
            logging.error(f"Fatal error in RealtimeManager listener setup: {e}", exc_info=True)
        finally:
            if pubsub:
                pubsub.close()
            logging.info("Redis pub/sub connection closed.")

    def _listen_for_updates_logs(self):
        """Listener for log channels on the logs Redis DB."""
        pubsub = None
        try:
            pubsub = self.redis_logs_client.pubsub(ignore_subscribe_messages=True)
            from .task_progress import TaskProgressManager
            pubsub.subscribe(TaskProgressManager.LOG_CHANNEL)

            logging.info(f"✅ EnhancedRealtimeManager subscribed (logs DB) to: {TaskProgressManager.LOG_CHANNEL}")

            while not self._stop_event.is_set():
                try:
                    if not self.health_monitor_logs.check_health():
                        logging.warning("Logs Redis connection unhealthy, buffering logs")
                        self.buffer_enabled = True
                        time.sleep(5)
                        continue
                    else:
                        if self.buffer_enabled:
                            logging.info("Logs Redis connection restored, processing buffered events")
                            self._process_buffered_events()
                            self.buffer_enabled = False

                    message = pubsub.get_message(timeout=1.0)
                    if message is None:
                        continue
                    self._handle_redis_message(message)
                except redis.exceptions.ConnectionError as e:
                    logging.error(f"Logs Redis connection error: {e}")
                    self.buffer_enabled = True
                    time.sleep(5)
                except Exception as e:
                    logging.error(f"Error in logs listener: {e}", exc_info=True)
                    time.sleep(1)
        except Exception as e:
            logging.error(f"Fatal error in logs listener setup: {e}", exc_info=True)
        finally:
            if pubsub:
                pubsub.close()
            logging.info("Logs Redis pub/sub connection closed.")
    
    def _handle_redis_message(self, message: Dict[str, Any]):
        """Handle a message from Redis pub/sub."""
        channel = message['channel']
        data_str = message['data']
        
        try:
            data = json.loads(data_str)
        except json.JSONDecodeError:
            logging.error(f"Failed to decode JSON from Redis channel '{channel}': {data_str}")
            self.stats['events_rejected'] += 1
            return
        
        self.stats['events_processed'] += 1
        
        # Extract event type from data
        event_type = data.get('type', 'unknown')
        event_data = data.get('data', data)  # Support both nested and flat structures
        
        # Validate event
        is_valid, error_msg, sanitized_data = self.validator.validate_event(event_type, event_data)
        if not is_valid:
            logging.warning(f"Event validation failed for {event_type}: {error_msg}")
            self.stats['events_rejected'] += 1
            return
        
        self.stats['events_validated'] += 1
        
        # Check rate limiting
        if not self.rate_limiter.is_allowed():
            logging.debug(f"Event rate limited: {event_type}")
            self.stats['events_rate_limited'] += 1
            return
        
        # Route event to appropriate SocketIO channels
        socketio_events = self.router.get_socketio_events(channel, event_type)
        
        if not socketio_events:
            # Fallback routing for unknown event types
            socketio_events = self._get_fallback_events(channel, event_type)
        
        # Create event for emission
        emission_event = {
            'type': event_type,
            'data': sanitized_data,
            'timestamp': datetime.now().isoformat(),
            'channel': channel,
            'socketio_events': socketio_events
        }
        
        # Add to batch or buffer
        if self.buffer_enabled:
            self.event_buffer.append(emission_event)
            self.stats['events_buffered'] += 1
        else:
            self._add_to_batch(emission_event)
    
    def _get_fallback_events(self, channel: str, event_type: str) -> List[str]:
        """Get fallback SocketIO events for unknown types."""
        # Enhanced fallback routing with better coverage
        fallback_mapping = {
            # Channel-based fallbacks
            "task_phase_updates": ["phase_update", "phase_status_update"],
            "task_status_updates": ["agent_status_update", "status_update"],
            "task_logs": ["log", "live_log"],
            "realtime_events": ["generic_update"],
            
            # Event type-based fallbacks
            "log": ["log", "live_log"],
            "log_message": ["log", "live_log"],
            "phase": ["phase_update"],
            "status": ["agent_status_update"],
            "progress": ["progress_update"],
            "agent": ["agent_status_update"],
            "task": ["task_progress"]
        }
        
        # Try channel-based fallback first
        events = fallback_mapping.get(channel, [])
        
        # If no channel-based fallback, try event type-based
        if not events:
            # Check if event_type contains any known keywords
            for keyword, event_names in fallback_mapping.items():
                if keyword in event_type.lower():
                    events = event_names
                    break
        
        # Final fallback
        if not events:
            events = ["generic_update"]
            
        # Log fallback usage for debugging
        logging.debug(f"Using fallback routing for channel='{channel}', event_type='{event_type}' -> {events}")
        
        return events
    
    def _add_to_batch(self, event: Dict[str, Any]):
        """Add event to appropriate batch."""
        event_type = event['type']
        batch = self.event_batches[event_type]
        
        if batch.add_event(event):
            # Batch is ready, queue it for processing
            self.batch_queue.put((event_type, batch.events.copy()))
            batch.clear()
    
    def _process_batches(self):
        """Process event batches in a separate thread."""
        while not self._stop_event.is_set():
            try:
                # Check for ready batches with timeout
                try:
                    event_type, events = self.batch_queue.get(timeout=0.5)
                    self._emit_batch(events)
                    self.batch_queue.task_done()
                except queue.Empty:
                    # Check for aged batches that need to be sent
                    self._check_aged_batches()
                    continue
                
            except Exception as e:
                logging.error(f"Error processing event batch: {e}", exc_info=True)
    
    def _check_aged_batches(self):
        """Check for batches that have aged out and need to be sent."""
        for event_type, batch in list(self.event_batches.items()):
            if batch.events and batch.is_ready_to_send():
                self.batch_queue.put((event_type, batch.events.copy()))
                batch.clear()
    
    def _emit_batch(self, events: List[Dict[str, Any]]):
        """Emit a batch of events to SocketIO."""
        if not events:
            return
        
        # Group events by SocketIO event name for efficient emission
        socketio_groups = defaultdict(list)
        
        for event in events:
            for socketio_event in event['socketio_events']:
                socketio_groups[socketio_event].append(event['data'])
        
        # Emit each group
        for socketio_event, event_data_list in socketio_groups.items():
            try:
                if len(event_data_list) == 1:
                    # Single event
                    self.socketio.emit(socketio_event, event_data_list[0])
                else:
                    # Batch of events
                    self.socketio.emit(f"{socketio_event}_batch", {
                        'events': event_data_list,
                        'count': len(event_data_list),
                        'timestamp': datetime.now().isoformat()
                    })
                
                logging.debug(f"Emitted {len(event_data_list)} events to '{socketio_event}'")
                
            except Exception as e:
                logging.error(f"Failed to emit SocketIO event '{socketio_event}': {e}", exc_info=True)
    
    def _process_buffered_events(self):
        """Process events that were buffered during connection issues."""
        if not self.event_buffer:
            return
        
        logging.info(f"Processing {len(self.event_buffer)} buffered events")
        
        while self.event_buffer:
            try:
                event = self.event_buffer.popleft()
                self._add_to_batch(event)
            except IndexError:
                break
        
        # Force process any remaining batches
        self._check_aged_batches()
    
    def _handle_reconnection_progress(self):
        """Handle Redis reconnection for progress DB."""
        logging.info("Attempting Redis reconnection (progress DB)...")
        self.stats['reconnections'] += 1
        try:
            self.redis_progress_client = redis.Redis.from_url(
                self.config.redis_progress_url,
                decode_responses=True,
                socket_connect_timeout=5,
                socket_timeout=5,
                retry_on_timeout=True
            )
            self.redis_progress_client.ping()
            self.health_monitor_progress.redis_client = self.redis_progress_client
            self.health_monitor_progress.reset_health()
            logging.info("Redis reconnection successful (progress DB)")
        except Exception as e:
            logging.error(f"Redis reconnection failed (progress DB): {e}")

    def _handle_reconnection_logs(self):
        """Handle Redis reconnection for logs DB."""
        logging.info("Attempting Redis reconnection (logs DB)...")
        self.stats['reconnections'] += 1
        try:
            self.redis_logs_client = redis.Redis.from_url(
                self.config.redis_logs_url,
                decode_responses=True,
                socket_connect_timeout=5,
                socket_timeout=5,
                retry_on_timeout=True
            )
            self.redis_logs_client.ping()
            self.health_monitor_logs.redis_client = self.redis_logs_client
            self.health_monitor_logs.reset_health()
            logging.info("Redis reconnection successful (logs DB)")
        except Exception as e:
            logging.error(f"Redis reconnection failed (logs DB): {e}")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get statistics about the RealtimeManager."""
        return {
            **self.stats,
            'is_healthy_progress': self.health_monitor_progress.is_healthy,
            'is_healthy_logs': self.health_monitor_logs.is_healthy,
            'buffer_size': len(self.event_buffer),
            'buffer_enabled': self.buffer_enabled,
            'active_batches': len(self.event_batches),
            'batch_queue_size': self.batch_queue.qsize()
        }
    
    def reset_stats(self):
        """Reset statistics."""
        self.stats = {
            'events_processed': 0,
            'events_validated': 0,
            'events_rejected': 0,
            'events_rate_limited': 0,
            'events_buffered': 0,
            'reconnections': 0
        }