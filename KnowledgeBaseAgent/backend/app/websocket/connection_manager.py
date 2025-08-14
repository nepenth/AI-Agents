"""
WebSocket connection manager for real-time communication.
"""

import asyncio
import json
import logging
import time
from typing import Dict, List, Set, Optional, Any
from dataclasses import dataclass, asdict
from enum import Enum
from fastapi import WebSocket, WebSocketDisconnect
import uuid

logger = logging.getLogger(__name__)


class MessageType(str, Enum):
    """WebSocket message types."""
    TASK_PROGRESS = "task_progress"
    TASK_COMPLETE = "task_complete"
    TASK_FAILED = "task_failed"
    SYSTEM_STATUS = "system_status"
    NOTIFICATION = "notification"
    HEARTBEAT = "heartbeat"
    AUTH_REQUEST = "auth_request"
    AUTH_SUCCESS = "auth_success"
    AUTH_FAILED = "auth_failed"
    SUBSCRIBE = "subscribe"
    UNSUBSCRIBE = "unsubscribe"
    ERROR = "error"


@dataclass
class WebSocketMessage:
    """WebSocket message structure."""
    type: MessageType
    data: Dict[str, Any]
    timestamp: float
    message_id: str
    channel: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)
    
    def to_json(self) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict())


@dataclass
class ConnectionInfo:
    """Information about a WebSocket connection."""
    connection_id: str
    websocket: WebSocket
    user_id: Optional[str] = None
    authenticated: bool = False
    connected_at: float = 0.0
    last_heartbeat: float = 0.0
    subscriptions: Set[str] = None
    
    def __post_init__(self):
        if self.subscriptions is None:
            self.subscriptions = set()
        if self.connected_at == 0.0:
            self.connected_at = time.time()
        if self.last_heartbeat == 0.0:
            self.last_heartbeat = time.time()


class WebSocketConnectionManager:
    """Manages WebSocket connections and message broadcasting."""
    
    def __init__(self):
        self.connections: Dict[str, ConnectionInfo] = {}
        self.user_connections: Dict[str, Set[str]] = {}  # user_id -> connection_ids
        self.channel_subscriptions: Dict[str, Set[str]] = {}  # channel -> connection_ids
        self.heartbeat_interval = 30  # seconds
        self.connection_timeout = 300  # 5 minutes
        self._heartbeat_task: Optional[asyncio.Task] = None
        self._cleanup_task: Optional[asyncio.Task] = None
    
    async def start_background_tasks(self):
        """Start background tasks for heartbeat and cleanup."""
        if not self._heartbeat_task:
            self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())
        if not self._cleanup_task:
            self._cleanup_task = asyncio.create_task(self._cleanup_loop())
    
    async def stop_background_tasks(self):
        """Stop background tasks."""
        if self._heartbeat_task:
            self._heartbeat_task.cancel()
            try:
                await self._heartbeat_task
            except asyncio.CancelledError:
                pass
            self._heartbeat_task = None
        
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
            self._cleanup_task = None
    
    async def connect(self, websocket: WebSocket) -> str:
        """
        Accept a new WebSocket connection.
        
        Args:
            websocket: The WebSocket connection
            
        Returns:
            Connection ID
        """
        await websocket.accept()
        
        connection_id = str(uuid.uuid4())
        connection_info = ConnectionInfo(
            connection_id=connection_id,
            websocket=websocket
        )
        
        self.connections[connection_id] = connection_info
        
        logger.info(f"WebSocket connection established: {connection_id}")
        
        # Send welcome message
        welcome_message = WebSocketMessage(
            type=MessageType.NOTIFICATION,
            data={
                "message": "Connected to AI Agent WebSocket",
                "connection_id": connection_id
            },
            timestamp=time.time(),
            message_id=str(uuid.uuid4())
        )
        
        await self._send_to_connection(connection_id, welcome_message)
        
        return connection_id
    
    async def disconnect(self, connection_id: str):
        """
        Disconnect a WebSocket connection.
        
        Args:
            connection_id: The connection ID to disconnect
        """
        if connection_id not in self.connections:
            return
        
        connection_info = self.connections[connection_id]
        
        # Remove from user connections
        if connection_info.user_id and connection_info.user_id in self.user_connections:
            self.user_connections[connection_info.user_id].discard(connection_id)
            if not self.user_connections[connection_info.user_id]:
                del self.user_connections[connection_info.user_id]
        
        # Remove from channel subscriptions
        for channel in connection_info.subscriptions:
            if channel in self.channel_subscriptions:
                self.channel_subscriptions[channel].discard(connection_id)
                if not self.channel_subscriptions[channel]:
                    del self.channel_subscriptions[channel]
        
        # Remove connection
        del self.connections[connection_id]
        
        logger.info(f"WebSocket connection disconnected: {connection_id}")
    
    async def authenticate_connection(self, connection_id: str, user_id: str) -> bool:
        """
        Authenticate a WebSocket connection.
        
        Args:
            connection_id: The connection ID
            user_id: The user ID
            
        Returns:
            True if authentication successful
        """
        if connection_id not in self.connections:
            return False
        
        connection_info = self.connections[connection_id]
        connection_info.user_id = user_id
        connection_info.authenticated = True
        
        # Add to user connections
        if user_id not in self.user_connections:
            self.user_connections[user_id] = set()
        self.user_connections[user_id].add(connection_id)
        
        # Send authentication success
        auth_message = WebSocketMessage(
            type=MessageType.AUTH_SUCCESS,
            data={"user_id": user_id},
            timestamp=time.time(),
            message_id=str(uuid.uuid4())
        )
        
        await self._send_to_connection(connection_id, auth_message)
        
        logger.info(f"WebSocket connection authenticated: {connection_id} for user {user_id}")
        return True
    
    async def subscribe_to_channel(self, connection_id: str, channel: str):
        """
        Subscribe a connection to a channel.
        
        Args:
            connection_id: The connection ID
            channel: The channel name
        """
        if connection_id not in self.connections:
            return
        
        connection_info = self.connections[connection_id]
        connection_info.subscriptions.add(channel)
        
        # Add to channel subscriptions
        if channel not in self.channel_subscriptions:
            self.channel_subscriptions[channel] = set()
        self.channel_subscriptions[channel].add(connection_id)
        
        logger.debug(f"Connection {connection_id} subscribed to channel {channel}")
    
    async def unsubscribe_from_channel(self, connection_id: str, channel: str):
        """
        Unsubscribe a connection from a channel.
        
        Args:
            connection_id: The connection ID
            channel: The channel name
        """
        if connection_id not in self.connections:
            return
        
        connection_info = self.connections[connection_id]
        connection_info.subscriptions.discard(channel)
        
        # Remove from channel subscriptions
        if channel in self.channel_subscriptions:
            self.channel_subscriptions[channel].discard(connection_id)
            if not self.channel_subscriptions[channel]:
                del self.channel_subscriptions[channel]
        
        logger.debug(f"Connection {connection_id} unsubscribed from channel {channel}")
    
    async def broadcast_to_channel(self, channel: str, message: WebSocketMessage):
        """
        Broadcast a message to all connections subscribed to a channel.
        
        Args:
            channel: The channel name
            message: The message to broadcast
        """
        if channel not in self.channel_subscriptions:
            logger.debug(f"No subscribers for channel {channel}")
            return
        
        message.channel = channel
        connection_ids = self.channel_subscriptions[channel].copy()
        
        # Send to all subscribers
        tasks = []
        for connection_id in connection_ids:
            task = asyncio.create_task(self._send_to_connection(connection_id, message))
            tasks.append(task)
        
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        
        logger.debug(f"Broadcasted message to {len(connection_ids)} connections on channel {channel}")
    
    async def send_to_user(self, user_id: str, message: WebSocketMessage):
        """
        Send a message to all connections for a specific user.
        
        Args:
            user_id: The user ID
            message: The message to send
        """
        if user_id not in self.user_connections:
            logger.debug(f"No connections for user {user_id}")
            return
        
        connection_ids = self.user_connections[user_id].copy()
        
        # Send to all user connections
        tasks = []
        for connection_id in connection_ids:
            task = asyncio.create_task(self._send_to_connection(connection_id, message))
            tasks.append(task)
        
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        
        logger.debug(f"Sent message to {len(connection_ids)} connections for user {user_id}")
    
    async def send_to_connection(self, connection_id: str, message: WebSocketMessage):
        """
        Send a message to a specific connection.
        
        Args:
            connection_id: The connection ID
            message: The message to send
        """
        await self._send_to_connection(connection_id, message)
    
    async def _send_to_connection(self, connection_id: str, message: WebSocketMessage):
        """Internal method to send message to connection."""
        if connection_id not in self.connections:
            return
        
        connection_info = self.connections[connection_id]
        
        try:
            await connection_info.websocket.send_text(message.to_json())
        except Exception as e:
            logger.error(f"Failed to send message to connection {connection_id}: {e}")
            # Remove broken connection
            await self.disconnect(connection_id)
    
    async def handle_message(self, connection_id: str, message_data: str):
        """
        Handle incoming message from a WebSocket connection.
        
        Args:
            connection_id: The connection ID
            message_data: The raw message data
        """
        try:
            data = json.loads(message_data)
            message_type = MessageType(data.get("type"))
            
            if message_type == MessageType.HEARTBEAT:
                await self._handle_heartbeat(connection_id)
            elif message_type == MessageType.AUTH_REQUEST:
                await self._handle_auth_request(connection_id, data.get("data", {}))
            elif message_type == MessageType.SUBSCRIBE:
                await self._handle_subscribe(connection_id, data.get("data", {}))
            elif message_type == MessageType.UNSUBSCRIBE:
                await self._handle_unsubscribe(connection_id, data.get("data", {}))
            else:
                logger.warning(f"Unhandled message type: {message_type}")
                
        except Exception as e:
            logger.error(f"Error handling message from {connection_id}: {e}")
            error_message = WebSocketMessage(
                type=MessageType.ERROR,
                data={"error": "Invalid message format"},
                timestamp=time.time(),
                message_id=str(uuid.uuid4())
            )
            await self._send_to_connection(connection_id, error_message)
    
    async def _handle_heartbeat(self, connection_id: str):
        """Handle heartbeat message."""
        if connection_id in self.connections:
            self.connections[connection_id].last_heartbeat = time.time()
    
    async def _handle_auth_request(self, connection_id: str, data: Dict[str, Any]):
        """Handle authentication request."""
        # This would integrate with your authentication system
        # For now, we'll do a simple mock authentication
        user_id = data.get("user_id")
        token = data.get("token")
        
        if user_id and token:
            # Mock authentication - in production, validate the token
            await self.authenticate_connection(connection_id, user_id)
        else:
            auth_failed_message = WebSocketMessage(
                type=MessageType.AUTH_FAILED,
                data={"error": "Invalid credentials"},
                timestamp=time.time(),
                message_id=str(uuid.uuid4())
            )
            await self._send_to_connection(connection_id, auth_failed_message)
    
    async def _handle_subscribe(self, connection_id: str, data: Dict[str, Any]):
        """Handle channel subscription request."""
        channel = data.get("channel")
        if channel:
            await self.subscribe_to_channel(connection_id, channel)
    
    async def _handle_unsubscribe(self, connection_id: str, data: Dict[str, Any]):
        """Handle channel unsubscription request."""
        channel = data.get("channel")
        if channel:
            await self.unsubscribe_from_channel(connection_id, channel)
    
    async def _heartbeat_loop(self):
        """Background task to send heartbeat messages."""
        while True:
            try:
                await asyncio.sleep(self.heartbeat_interval)
                
                heartbeat_message = WebSocketMessage(
                    type=MessageType.HEARTBEAT,
                    data={"timestamp": time.time()},
                    timestamp=time.time(),
                    message_id=str(uuid.uuid4())
                )
                
                # Send heartbeat to all connections
                connection_ids = list(self.connections.keys())
                tasks = []
                for connection_id in connection_ids:
                    task = asyncio.create_task(self._send_to_connection(connection_id, heartbeat_message))
                    tasks.append(task)
                
                if tasks:
                    await asyncio.gather(*tasks, return_exceptions=True)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in heartbeat loop: {e}")
    
    async def _cleanup_loop(self):
        """Background task to cleanup stale connections."""
        while True:
            try:
                await asyncio.sleep(60)  # Check every minute
                
                current_time = time.time()
                stale_connections = []
                
                for connection_id, connection_info in self.connections.items():
                    if current_time - connection_info.last_heartbeat > self.connection_timeout:
                        stale_connections.append(connection_id)
                
                # Remove stale connections
                for connection_id in stale_connections:
                    logger.info(f"Removing stale connection: {connection_id}")
                    await self.disconnect(connection_id)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in cleanup loop: {e}")
    
    def get_connection_stats(self) -> Dict[str, Any]:
        """Get connection statistics."""
        return {
            "total_connections": len(self.connections),
            "authenticated_connections": sum(1 for conn in self.connections.values() if conn.authenticated),
            "total_users": len(self.user_connections),
            "total_channels": len(self.channel_subscriptions),
            "channel_stats": {
                channel: len(connections) 
                for channel, connections in self.channel_subscriptions.items()
            }
        }


# Global connection manager instance
_connection_manager: Optional[WebSocketConnectionManager] = None


def get_connection_manager() -> WebSocketConnectionManager:
    """Get the global WebSocket connection manager."""
    global _connection_manager
    if _connection_manager is None:
        _connection_manager = WebSocketConnectionManager()
    return _connection_manager