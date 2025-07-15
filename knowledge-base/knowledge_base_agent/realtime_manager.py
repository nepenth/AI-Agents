"""
Real-time Update Manager for Celery Tasks

This module manages real-time updates from Celery tasks to WebSocket clients
using a Redis pub/sub pattern, replacing the old multiprocessing queue_listener.
"""

import redis
import json
import logging
import threading
from typing import Dict, Any
import time

from flask_socketio import SocketIO
from .config import Config

class RealtimeManager:
    """
    Manages real-time updates from Celery tasks to WebSocket clients.
    
    Replaces the current queue_listener with a Redis pub/sub pattern for a
    more robust and scalable real-time communication architecture.
    """
    
    def __init__(self, socketio: SocketIO):
        """
        Initialize the RealtimeManager.
        
        Args:
            socketio: The Flask-SocketIO instance.
        """
        self.socketio = socketio
        self.config = Config()
        self.redis_client = redis.Redis.from_url(
            self.config.redis_progress_url, 
            decode_responses=True
        )
        self.pubsub_thread = None
        self._stop_event = threading.Event()

    def start_listener(self):
        """Start the Redis pub/sub listener in a background thread."""
        if self.pubsub_thread and self.pubsub_thread.is_alive():
            logging.warning("RealtimeManager listener is already running.")
            return

        logging.debug("Starting RealtimeManager Redis pub/sub listener...")
        self._stop_event.clear()
        self.pubsub_thread = threading.Thread(target=self._listen_for_updates, daemon=True)
        self.pubsub_thread.start()
        logging.debug("RealtimeManager listener started.")

    def stop_listener(self):
        """Stop the Redis pub/sub listener."""
        if not self.pubsub_thread or not self.pubsub_thread.is_alive():
            logging.warning("RealtimeManager listener is not running.")
            return
            
        logging.info("Stopping RealtimeManager listener...")
        self._stop_event.set()
        self.pubsub_thread.join(timeout=5)
        logging.info("RealtimeManager listener stopped.")

    def _listen_for_updates(self):
        """The target function for the pub/sub listener thread."""
        pubsub = self.redis_client.pubsub(ignore_subscribe_messages=True)
        
        try:
            # Subscribe to multiple channels for different update types
            pubsub.subscribe(
                "task_phase_updates",
                "task_status_updates",
                "task_logs"
            )
            logging.debug("Subscribed to Redis channels: task_phase_updates, task_status_updates, task_logs")

            while not self._stop_event.is_set():
                try:
                    message = pubsub.get_message(timeout=1.0)
                    if message is None:
                        continue

                    channel = message['channel']
                    data_str = message['data']
                    
                    try:
                        data = json.loads(data_str)
                    except json.JSONDecodeError:
                        logging.error(f"Failed to decode JSON from Redis channel '{channel}': {data_str}")
                        continue
                    
                    self._broadcast_update(channel, data)

                except redis.exceptions.ConnectionError:
                    logging.error("Redis connection lost in RealtimeManager. Attempting to reconnect...")
                    time.sleep(5)
                    # The pubsub object should handle reconnection automatically,
                    # but we can force it if needed. For now, we rely on its resilience.
                except Exception as e:
                    logging.error(f"Error in RealtimeManager listener loop: {e}", exc_info=True)
                    # Avoid tight loop on repeated errors
                    time.sleep(1)

        except Exception as e:
            logging.error(f"Catastrophic error in RealtimeManager listener setup: {e}", exc_info=True)
        finally:
            pubsub.close()
            logging.info("Redis pub/sub connection closed.")
        
    def _broadcast_update(self, channel: str, data: Dict[str, Any]):
        """
        Broadcast update to all connected clients based on the channel.
        
        Args:
            channel: The Redis channel the message was received on.
            data: The message data.
        """
        event_map = {
            "task_phase_updates": "phase_update",
            "task_status_updates": "agent_status_update",
            "task_logs": "log"
        }

        event_name = event_map.get(channel)

        if event_name:
            try:
                logging.debug(f"Broadcasting SocketIO event '{event_name}' with data: {data}")
                
                # Handle task_logs specially to normalize format
                if channel == "task_logs" and data.get("type") == "log_message":
                    log_data = data.get("data", {})
                    normalized_log = {
                        'message': log_data.get('message', ''),
                        'level': log_data.get('level', 'INFO'),
                        'timestamp': log_data.get('timestamp')
                    }
                    
                    # Emit normalized format to SocketIO (single source of truth)
                    self.socketio.emit(event_name, normalized_log)
                else:
                    # Primary event for non-log events
                    self.socketio.emit(event_name, data)

                # Back-compat aliases for older front-end handlers
                if event_name == "phase_update":
                    # Legacy names expected by older JS
                    self.socketio.emit("phase_status_update", data)
                    self.socketio.emit("task_progress", data)
            except Exception as e:
                logging.error(f"Failed to broadcast SocketIO event '{event_name}': {e}", exc_info=True)
        else:
            logging.warning(f"Unknown Redis channel for broadcast: {channel}") 