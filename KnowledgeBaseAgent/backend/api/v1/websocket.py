"""
WebSocket API endpoints for real-time communication.
"""

import asyncio
import logging
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException, Depends, Query
from typing import Optional, Dict, Any

from app.websocket.connection_manager import get_connection_manager
from app.websocket.pubsub import get_pubsub_manager, get_notification_service

router = APIRouter()
logger = logging.getLogger(__name__)


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """
    Main WebSocket endpoint for real-time communication.
    """
    connection_manager = get_connection_manager()
    connection_id = None
    
    try:
        # Accept connection
        connection_id = await connection_manager.connect(websocket)
        
        # Start background tasks if not already running
        await connection_manager.start_background_tasks()
        
        # Message handling loop
        while True:
            try:
                # Receive message from client
                data = await websocket.receive_text()
                
                # Handle the message
                await connection_manager.handle_message(connection_id, data)
                
            except WebSocketDisconnect:
                logger.info(f"WebSocket client disconnected: {connection_id}")
                break
            except Exception as e:
                logger.error(f"Error handling WebSocket message: {e}")
                break
    
    except Exception as e:
        logger.error(f"WebSocket connection error: {e}")
    
    finally:
        # Clean up connection
        if connection_id:
            await connection_manager.disconnect(connection_id)


@router.websocket("/ws/task/{task_id}")
async def task_websocket_endpoint(websocket: WebSocket, task_id: str):
    """
    WebSocket endpoint for monitoring a specific task.
    """
    connection_manager = get_connection_manager()
    connection_id = None
    
    try:
        # Accept connection
        connection_id = await connection_manager.connect(websocket)
        
        # Subscribe to task-specific channel
        task_channel = f"task_progress_{task_id}"
        await connection_manager.subscribe_to_channel(connection_id, task_channel)
        
        # Start background tasks if not already running
        await connection_manager.start_background_tasks()
        
        # Message handling loop
        while True:
            try:
                # Receive message from client (mostly heartbeats)
                data = await websocket.receive_text()
                await connection_manager.handle_message(connection_id, data)
                
            except WebSocketDisconnect:
                logger.info(f"Task WebSocket client disconnected: {connection_id}")
                break
            except Exception as e:
                logger.error(f"Error in task WebSocket: {e}")
                break
    
    except Exception as e:
        logger.error(f"Task WebSocket connection error: {e}")
    
    finally:
        # Clean up connection
        if connection_id:
            await connection_manager.disconnect(connection_id)


@router.get("/ws/stats")
async def get_websocket_stats():
    """
    Get WebSocket connection statistics.
    """
    try:
        connection_manager = get_connection_manager()
        stats = connection_manager.get_connection_stats()
        
        return {
            "websocket_stats": stats,
            "timestamp": asyncio.get_event_loop().time()
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get WebSocket stats: {str(e)}")


@router.post("/ws/broadcast")
async def broadcast_message(
    channel: str,
    message: str,
    message_type: str = "notification",
    data: Optional[Dict[str, Any]] = None
):
    """
    Broadcast a message to all connections on a channel.
    """
    try:
        from app.websocket.connection_manager import WebSocketMessage, MessageType
        import uuid
        
        # Create WebSocket message
        ws_message = WebSocketMessage(
            type=MessageType(message_type),
            data={
                "message": message,
                **(data or {})
            },
            timestamp=asyncio.get_event_loop().time(),
            message_id=str(uuid.uuid4())
        )
        
        # Broadcast through Redis PubSub
        pubsub_manager = get_pubsub_manager()
        await pubsub_manager.publish_message(channel, ws_message)
        
        return {
            "success": True,
            "channel": channel,
            "message": message,
            "message_id": ws_message.message_id
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to broadcast message: {str(e)}")


@router.post("/ws/notify")
async def send_notification(
    message: str,
    level: str = "info",
    user_id: Optional[str] = None
):
    """
    Send a notification through WebSocket.
    """
    try:
        notification_service = get_notification_service()
        await notification_service.send_notification(message, level, user_id)
        
        return {
            "success": True,
            "message": message,
            "level": level,
            "user_id": user_id
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to send notification: {str(e)}")


@router.post("/ws/task/{task_id}/progress")
async def update_task_progress(
    task_id: str,
    current: int,
    total: int,
    status: str,
    phase: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None
):
    """
    Update task progress and notify WebSocket clients.
    """
    try:
        progress_data = {
            "current": current,
            "total": total,
            "status": status,
            "phase": phase,
            "details": details,
            "percentage": (current / total * 100) if total > 0 else 0
        }
        
        notification_service = get_notification_service()
        await notification_service.notify_task_progress(task_id, progress_data)
        
        return {
            "success": True,
            "task_id": task_id,
            "progress": progress_data
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update task progress: {str(e)}")


@router.post("/ws/task/{task_id}/complete")
async def complete_task(
    task_id: str,
    result: Dict[str, Any],
    execution_time: Optional[float] = None
):
    """
    Mark task as complete and notify WebSocket clients.
    """
    try:
        result_data = {
            "result": result,
            "execution_time": execution_time,
            "completed_at": asyncio.get_event_loop().time()
        }
        
        notification_service = get_notification_service()
        await notification_service.notify_task_completion(task_id, result_data)
        
        return {
            "success": True,
            "task_id": task_id,
            "result": result_data
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to complete task: {str(e)}")


@router.post("/ws/task/{task_id}/fail")
async def fail_task(
    task_id: str,
    error: str,
    error_type: Optional[str] = None,
    traceback: Optional[str] = None
):
    """
    Mark task as failed and notify WebSocket clients.
    """
    try:
        error_data = {
            "error": error,
            "error_type": error_type,
            "traceback": traceback,
            "failed_at": asyncio.get_event_loop().time()
        }
        
        notification_service = get_notification_service()
        await notification_service.notify_task_failure(task_id, error_data)
        
        return {
            "success": True,
            "task_id": task_id,
            "error": error_data
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fail task: {str(e)}")


@router.post("/ws/system/status")
async def update_system_status(
    status: Dict[str, Any]
):
    """
    Update system status and notify WebSocket clients.
    """
    try:
        status_data = {
            **status,
            "updated_at": asyncio.get_event_loop().time()
        }
        
        notification_service = get_notification_service()
        await notification_service.notify_system_status(status_data)
        
        return {
            "success": True,
            "status": status_data
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update system status: {str(e)}")


@router.get("/ws/channels")
async def list_channels():
    """
    List all active WebSocket channels.
    """
    try:
        connection_manager = get_connection_manager()
        stats = connection_manager.get_connection_stats()
        
        return {
            "channels": list(stats.get("channel_stats", {}).keys()),
            "channel_stats": stats.get("channel_stats", {}),
            "total_channels": stats.get("total_channels", 0)
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list channels: {str(e)}")


@router.delete("/ws/connections/{connection_id}")
async def disconnect_client(connection_id: str):
    """
    Forcefully disconnect a WebSocket client.
    """
    try:
        connection_manager = get_connection_manager()
        await connection_manager.disconnect(connection_id)
        
        return {
            "success": True,
            "connection_id": connection_id,
            "message": "Connection disconnected"
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to disconnect client: {str(e)}")