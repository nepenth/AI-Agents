"""
Redis PubSub integration for scalable WebSocket message distribution.
"""

import asyncio
import json
import logging
from typing import Dict, Any, Optional, Callable, List
import redis.asyncio as redis
from dataclasses import asdict

from app.websocket.connection_manager import WebSocketMessage, MessageType, get_connection_manager
from app.config import get_settings

logger = logging.getLogger(__name__)


class RedisPubSubManager:
    """Manages Redis PubSub for WebSocket message distribution across multiple workers."""
    
    def __init__(self):
        self.settings = get_settings()
        self.redis_client: Optional[redis.Redis] = None
        self.pubsub: Optional[redis.client.PubSub] = None
        self.subscriptions: Dict[str, Callable] = {}
        self._listen_task: Optional[asyncio.Task] = None
        self._running = False
    
    async def initialize(self):
        """Initialize Redis connection and PubSub."""
        try:
            self.redis_client = redis.from_url(
                self.settings.REDIS_URL,
                encoding="utf-8",
                decode_responses=True
            )
            
            # Test connection
            await self.redis_client.ping()
            
            self.pubsub = self.redis_client.pubsub()
            
            logger.info("Redis PubSub initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize Redis PubSub: {e}")
            raise
    
    async def start_listening(self):
        """Start listening for Redis PubSub messages."""
        if not self.pubsub:
            raise RuntimeError("PubSub not initialized")
        
        if self._running:
            logger.warning("PubSub listener already running")
            return
        
        self._running = True
        self._listen_task = asyncio.create_task(self._listen_loop())
        
        logger.info("Started Redis PubSub listener")
    
    async def stop_listening(self):
        """Stop listening for Redis PubSub messages."""
        self._running = False
        
        if self._listen_task:
            self._listen_task.cancel()
            try:
                await self._listen_task
            except asyncio.CancelledError:
                pass
            self._listen_task = None
        
        if self.pubsub:
            await self.pubsub.close()
        
        if self.redis_client:
            await self.redis_client.close()
        
        logger.info("Stopped Redis PubSub listener")
    
    async def subscribe_to_channel(self, channel: str, handler: Optional[Callable] = None):
        """
        Subscribe to a Redis channel.
        
        Args:
            channel: Channel name to subscribe to
            handler: Optional custom handler for messages
        """
        if not self.pubsub:
            raise RuntimeError("PubSub not initialized")
        
        await self.pubsub.subscribe(channel)
        
        if handler:
            self.subscriptions[channel] = handler
        else:
            self.subscriptions[channel] = self._default_message_handler
        
        logger.info(f"Subscribed to Redis channel: {channel}")
    
    async def unsubscribe_from_channel(self, channel: str):
        """
        Unsubscribe from a Redis channel.
        
        Args:
            channel: Channel name to unsubscribe from
        """
        if not self.pubsub:
            return
        
        await self.pubsub.unsubscribe(channel)
        
        if channel in self.subscriptions:
            del self.subscriptions[channel]
        
        logger.info(f"Unsubscribed from Redis channel: {channel}")
    
    async def publish_message(self, channel: str, message: WebSocketMessage):
        """
        Publish a message to a Redis channel.
        
        Args:
            channel: Channel name
            message: WebSocket message to publish
        """
        if not self.redis_client:
            raise RuntimeError("Redis client not initialized")
        
        try:
            message_data = json.dumps(message.to_dict())
            await self.redis_client.publish(channel, message_data)
            
            logger.debug(f"Published message to Redis channel {channel}")
            
        except Exception as e:
            logger.error(f"Failed to publish message to Redis channel {channel}: {e}")
            raise
    
    async def publish_task_progress(self, task_id: str, progress_data: Dict[str, Any]):
        """
        Publish task progress update.
        
        Args:
            task_id: Task ID
            progress_data: Progress information
        """
        message = WebSocketMessage(
            type=MessageType.TASK_PROGRESS,
            data={
                "task_id": task_id,
                **progress_data
            },
            timestamp=asyncio.get_event_loop().time(),
            message_id=f"task_progress_{task_id}"
        )
        
        await self.publish_message(f"task_progress_{task_id}", message)
        await self.publish_message("task_updates", message)
    
    async def publish_task_completion(self, task_id: str, result_data: Dict[str, Any]):
        """
        Publish task completion notification.
        
        Args:
            task_id: Task ID
            result_data: Task result information
        """
        message = WebSocketMessage(
            type=MessageType.TASK_COMPLETE,
            data={
                "task_id": task_id,
                **result_data
            },
            timestamp=asyncio.get_event_loop().time(),
            message_id=f"task_complete_{task_id}"
        )
        
        await self.publish_message(f"task_progress_{task_id}", message)
        await self.publish_message("task_updates", message)
    
    async def publish_task_failure(self, task_id: str, error_data: Dict[str, Any]):
        """
        Publish task failure notification.
        
        Args:
            task_id: Task ID
            error_data: Error information
        """
        message = WebSocketMessage(
            type=MessageType.TASK_FAILED,
            data={
                "task_id": task_id,
                **error_data
            },
            timestamp=asyncio.get_event_loop().time(),
            message_id=f"task_failed_{task_id}"
        )
        
        await self.publish_message(f"task_progress_{task_id}", message)
        await self.publish_message("task_updates", message)
    
    async def publish_system_status(self, status_data: Dict[str, Any]):
        """
        Publish system status update.
        
        Args:
            status_data: System status information
        """
        message = WebSocketMessage(
            type=MessageType.SYSTEM_STATUS,
            data=status_data,
            timestamp=asyncio.get_event_loop().time(),
            message_id="system_status"
        )
        
        await self.publish_message("system_status", message)
    
    async def publish_notification(self, notification_data: Dict[str, Any], channel: str = "notifications"):
        """
        Publish a general notification.
        
        Args:
            notification_data: Notification information
            channel: Channel to publish to
        """
        message = WebSocketMessage(
            type=MessageType.NOTIFICATION,
            data=notification_data,
            timestamp=asyncio.get_event_loop().time(),
            message_id=f"notification_{asyncio.get_event_loop().time()}"
        )
        
        await self.publish_message(channel, message)
    
    async def _listen_loop(self):
        """Main listening loop for Redis PubSub messages."""
        if not self.pubsub:
            return
        
        try:
            async for message in self.pubsub.listen():
                if not self._running:
                    break
                
                if message["type"] == "message":
                    await self._handle_redis_message(message)
                    
        except asyncio.CancelledError:
            logger.info("Redis PubSub listen loop cancelled")
        except Exception as e:
            logger.error(f"Error in Redis PubSub listen loop: {e}")
    
    async def _handle_redis_message(self, redis_message: Dict[str, Any]):
        """Handle incoming Redis PubSub message."""
        try:
            channel = redis_message["channel"]
            data = redis_message["data"]
            
            # Parse message data
            message_data = json.loads(data)
            
            # Get handler for channel
            handler = self.subscriptions.get(channel, self._default_message_handler)
            
            # Handle message
            await handler(channel, message_data)
            
        except Exception as e:
            logger.error(f"Error handling Redis message: {e}")
    
    async def _default_message_handler(self, channel: str, message_data: Dict[str, Any]):
        """Default handler for Redis PubSub messages."""
        try:
            # Reconstruct WebSocket message
            message = WebSocketMessage(
                type=MessageType(message_data["type"]),
                data=message_data["data"],
                timestamp=message_data["timestamp"],
                message_id=message_data["message_id"],
                channel=message_data.get("channel")
            )
            
            # Broadcast to WebSocket connections
            connection_manager = get_connection_manager()
            
            if channel.startswith("task_progress_"):
                # Task-specific channel - broadcast to subscribers
                await connection_manager.broadcast_to_channel(channel, message)
            elif channel == "task_updates":
                # General task updates - broadcast to all authenticated connections
                await connection_manager.broadcast_to_channel("task_updates", message)
            elif channel == "system_status":
                # System status - broadcast to all connections
                await connection_manager.broadcast_to_channel("system_status", message)
            elif channel == "notifications":
                # General notifications - broadcast to all authenticated connections
                await connection_manager.broadcast_to_channel("notifications", message)
            else:
                # Custom channel - broadcast to subscribers
                await connection_manager.broadcast_to_channel(channel, message)
            
            logger.debug(f"Handled Redis message on channel {channel}")
            
        except Exception as e:
            logger.error(f"Error in default message handler: {e}")


class WebSocketNotificationService:
    """Service for sending notifications through WebSocket and Redis PubSub."""
    
    def __init__(self):
        self.pubsub_manager = get_pubsub_manager()
    
    async def notify_task_progress(self, task_id: str, progress_data: Dict[str, Any]):
        """Send task progress notification."""
        await self.pubsub_manager.publish_task_progress(task_id, progress_data)
    
    async def notify_task_completion(self, task_id: str, result_data: Dict[str, Any]):
        """Send task completion notification."""
        await self.pubsub_manager.publish_task_completion(task_id, result_data)
    
    async def notify_task_failure(self, task_id: str, error_data: Dict[str, Any]):
        """Send task failure notification."""
        await self.pubsub_manager.publish_task_failure(task_id, error_data)
    
    async def notify_system_status(self, status_data: Dict[str, Any]):
        """Send system status notification."""
        await self.pubsub_manager.publish_system_status(status_data)
    
    async def send_notification(self, message: str, level: str = "info", user_id: Optional[str] = None):
        """Send a general notification."""
        notification_data = {
            "message": message,
            "level": level,
            "user_id": user_id,
            "timestamp": asyncio.get_event_loop().time()
        }
        
        if user_id:
            # Send to specific user
            connection_manager = get_connection_manager()
            ws_message = WebSocketMessage(
                type=MessageType.NOTIFICATION,
                data=notification_data,
                timestamp=asyncio.get_event_loop().time(),
                message_id=f"notification_{asyncio.get_event_loop().time()}"
            )
            await connection_manager.send_to_user(user_id, ws_message)
        else:
            # Broadcast to all
            await self.pubsub_manager.publish_notification(notification_data)


# Global instances
_pubsub_manager: Optional[RedisPubSubManager] = None
_notification_service: Optional[WebSocketNotificationService] = None


def get_pubsub_manager() -> RedisPubSubManager:
    """Get the global Redis PubSub manager."""
    global _pubsub_manager
    if _pubsub_manager is None:
        _pubsub_manager = RedisPubSubManager()
    return _pubsub_manager


def get_notification_service() -> WebSocketNotificationService:
    """Get the global WebSocket notification service."""
    global _notification_service
    if _notification_service is None:
        _notification_service = WebSocketNotificationService()
    return _notification_service