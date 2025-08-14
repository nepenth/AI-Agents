"""
Chat endpoints for AI-powered conversations with knowledge base integration.
"""
from fastapi import APIRouter, HTTPException, Query, Depends
from fastapi.responses import StreamingResponse
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
import json
import asyncio

from app.services.chat_service import get_chat_service, ChatResponse
from app.models.chat import ChatSession, ChatMessage

router = APIRouter()


class CreateSessionRequest(BaseModel):
    """Request model for creating a chat session."""
    title: Optional[str] = Field(default=None, description="Session title")
    system_prompt: Optional[str] = Field(default=None, description="System prompt for the session")


class SendMessageRequest(BaseModel):
    """Request model for sending a chat message."""
    content: str = Field(..., description="Message content")
    model_name: Optional[str] = Field(default=None, description="AI model to use")
    use_knowledge_base: bool = Field(default=True, description="Whether to use knowledge base for context")
    streaming: bool = Field(default=False, description="Whether to use streaming response")


class UpdateSessionRequest(BaseModel):
    """Request model for updating a chat session."""
    title: Optional[str] = Field(default=None, description="New session title")
    system_prompt: Optional[str] = Field(default=None, description="New system prompt")
    is_archived: Optional[bool] = Field(default=None, description="Archive status")


class ChatSessionResponse(BaseModel):
    """Response model for chat session."""
    id: str
    title: str
    message_count: int
    is_archived: bool
    created_at: str
    last_updated: str
    system_prompt: Optional[str] = None


class ChatMessageResponse(BaseModel):
    """Response model for chat message."""
    id: str
    session_id: str
    role: str
    content: str
    model_used: Optional[str] = None
    sources: List[Dict[str, Any]] = []
    context_stats: Optional[Dict[str, Any]] = None
    created_at: str


class ChatResponseModel(BaseModel):
    """Response model for chat AI response."""
    message_id: str
    content: str
    model_used: str
    generation_time: float
    context: Optional[Dict[str, Any]] = None
    streaming: bool = False


@router.get("/health")
async def chat_health():
    """Check chat service health."""
    return {"status": "healthy", "service": "chat"}


@router.get("/sessions", response_model=List[ChatSessionResponse])
async def list_chat_sessions(
    limit: int = Query(default=50, ge=1, le=100, description="Maximum number of sessions"),
    offset: int = Query(default=0, ge=0, description="Offset for pagination"),
    include_archived: bool = Query(default=False, description="Include archived sessions")
):
    """List chat sessions."""
    try:
        chat_service = get_chat_service()
        sessions = await chat_service.list_sessions(limit, offset, include_archived)
        
        return [
            ChatSessionResponse(
                id=session.id,
                title=session.title,
                message_count=session.message_count,
                is_archived=session.is_archived,
                created_at=session.created_at.isoformat(),
                last_updated=session.last_updated.isoformat(),
                system_prompt=session.system_prompt
            )
            for session in sessions
        ]
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list chat sessions: {str(e)}")


@router.post("/sessions", response_model=ChatSessionResponse)
async def create_chat_session(request: CreateSessionRequest):
    """Create a new chat session."""
    try:
        chat_service = get_chat_service()
        session = await chat_service.create_session(request.title, request.system_prompt)
        
        return ChatSessionResponse(
            id=session.id,
            title=session.title,
            message_count=session.message_count,
            is_archived=session.is_archived,
            created_at=session.created_at.isoformat(),
            last_updated=session.last_updated.isoformat(),
            system_prompt=session.system_prompt
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create chat session: {str(e)}")


@router.get("/sessions/{session_id}", response_model=ChatSessionResponse)
async def get_chat_session(session_id: str):
    """Get a specific chat session."""
    try:
        chat_service = get_chat_service()
        session = await chat_service.get_session(session_id)
        
        if not session:
            raise HTTPException(status_code=404, detail="Chat session not found")
        
        return ChatSessionResponse(
            id=session.id,
            title=session.title,
            message_count=session.message_count,
            is_archived=session.is_archived,
            created_at=session.created_at.isoformat(),
            last_updated=session.last_updated.isoformat(),
            system_prompt=session.system_prompt
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get chat session: {str(e)}")


@router.put("/sessions/{session_id}", response_model=ChatSessionResponse)
async def update_chat_session(session_id: str, request: UpdateSessionRequest):
    """Update a chat session."""
    try:
        chat_service = get_chat_service()
        
        # Build updates dict
        updates = {}
        if request.title is not None:
            updates["title"] = request.title
        if request.system_prompt is not None:
            updates["system_prompt"] = request.system_prompt
        if request.is_archived is not None:
            updates["is_archived"] = request.is_archived
        
        if not updates:
            raise HTTPException(status_code=400, detail="No updates provided")
        
        session = await chat_service.update_session(session_id, updates)
        
        if not session:
            raise HTTPException(status_code=404, detail="Chat session not found")
        
        return ChatSessionResponse(
            id=session.id,
            title=session.title,
            message_count=session.message_count,
            is_archived=session.is_archived,
            created_at=session.created_at.isoformat(),
            last_updated=session.last_updated.isoformat(),
            system_prompt=session.system_prompt
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update chat session: {str(e)}")


@router.delete("/sessions/{session_id}")
async def delete_chat_session(session_id: str):
    """Delete a chat session."""
    try:
        chat_service = get_chat_service()
        success = await chat_service.delete_session(session_id)
        
        if not success:
            raise HTTPException(status_code=404, detail="Chat session not found")
        
        return {"success": True, "message": "Chat session deleted"}
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete chat session: {str(e)}")


@router.get("/sessions/{session_id}/messages", response_model=List[ChatMessageResponse])
async def get_chat_messages(
    session_id: str,
    limit: int = Query(default=50, ge=1, le=100, description="Maximum number of messages"),
    offset: int = Query(default=0, ge=0, description="Offset for pagination")
):
    """Get messages for a chat session."""
    try:
        chat_service = get_chat_service()
        
        # Verify session exists
        session = await chat_service.get_session(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Chat session not found")
        
        messages = await chat_service.get_messages(session_id, limit, offset)
        
        return [
            ChatMessageResponse(
                id=message.id,
                session_id=message.session_id,
                role=message.role,
                content=message.content,
                model_used=message.model_used,
                sources=message.sources or [],
                context_stats=message.context_stats,
                created_at=message.created_at.isoformat()
            )
            for message in messages
        ]
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get chat messages: {str(e)}")


@router.post("/sessions/{session_id}/messages", response_model=ChatResponseModel)
async def send_chat_message(session_id: str, request: SendMessageRequest):
    """Send a message in a chat session and get AI response."""
    try:
        chat_service = get_chat_service()
        
        # Verify session exists
        session = await chat_service.get_session(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Chat session not found")
        
        # Send message and get response
        response = await chat_service.send_message(
            session_id=session_id,
            content=request.content,
            model_name=request.model_name,
            use_knowledge_base=request.use_knowledge_base,
            streaming=request.streaming
        )
        
        # Format context for response
        context_data = None
        if response.context:
            context_data = {
                "source_count": response.context.source_count,
                "similarity_threshold": response.context.similarity_threshold,
                "relevant_sources": response.context.relevant_sources
            }
        
        return ChatResponseModel(
            message_id=response.message_id,
            content=response.content,
            model_used=response.model_used,
            generation_time=response.generation_time,
            context=context_data,
            streaming=response.streaming
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to send chat message: {str(e)}")


@router.post("/sessions/{session_id}/messages/stream")
async def send_chat_message_stream(session_id: str, request: SendMessageRequest):
    """Send a message with streaming response."""
    try:
        chat_service = get_chat_service()
        
        # Verify session exists
        session = await chat_service.get_session(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Chat session not found")
        
        # Force streaming mode
        request.streaming = True
        
        async def generate_stream():
            try:
                response = await chat_service.send_message(
                    session_id=session_id,
                    content=request.content,
                    model_name=request.model_name,
                    use_knowledge_base=request.use_knowledge_base,
                    streaming=True
                )
                
                # Send response in chunks
                words = response.content.split()
                for i, word in enumerate(words):
                    chunk_data = {
                        "type": "content",
                        "data": word + " ",
                        "index": i,
                        "total": len(words)
                    }
                    yield f"data: {json.dumps(chunk_data)}\n\n"
                    await asyncio.sleep(0.05)  # Small delay for streaming effect
                
                # Send completion message
                completion_data = {
                    "type": "complete",
                    "data": {
                        "message_id": response.message_id,
                        "model_used": response.model_used,
                        "generation_time": response.generation_time,
                        "context": {
                            "source_count": response.context.source_count if response.context else 0,
                            "relevant_sources": response.context.relevant_sources if response.context else []
                        }
                    }
                }
                yield f"data: {json.dumps(completion_data)}\n\n"
                
            except Exception as e:
                error_data = {
                    "type": "error",
                    "data": {"error": str(e)}
                }
                yield f"data: {json.dumps(error_data)}\n\n"
        
        return StreamingResponse(
            generate_stream(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "Access-Control-Allow-Origin": "*",
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to send streaming message: {str(e)}")


@router.delete("/messages/{message_id}")
async def delete_chat_message(message_id: str):
    """Delete a chat message."""
    try:
        chat_service = get_chat_service()
        success = await chat_service.delete_message(message_id)
        
        if not success:
            raise HTTPException(status_code=404, detail="Chat message not found")
        
        return {"success": True, "message": "Chat message deleted"}
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete chat message: {str(e)}")


@router.post("/messages/{message_id}/regenerate", response_model=ChatResponseModel)
async def regenerate_chat_response(
    message_id: str,
    session_id: str = Query(..., description="Session ID for the message"),
    model_name: Optional[str] = Query(default=None, description="AI model to use for regeneration")
):
    """Regenerate an AI response."""
    try:
        chat_service = get_chat_service()
        
        response = await chat_service.regenerate_response(session_id, message_id, model_name)
        
        if not response:
            raise HTTPException(status_code=404, detail="Message not found or cannot be regenerated")
        
        # Format context for response
        context_data = None
        if response.context:
            context_data = {
                "source_count": response.context.source_count,
                "similarity_threshold": response.context.similarity_threshold,
                "relevant_sources": response.context.relevant_sources
            }
        
        return ChatResponseModel(
            message_id=response.message_id,
            content=response.content,
            model_used=response.model_used,
            generation_time=response.generation_time,
            context=context_data,
            streaming=response.streaming
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to regenerate response: {str(e)}")


@router.get("/sessions/{session_id}/context")
async def get_session_context(session_id: str, query: str = Query(..., description="Query to get context for")):
    """Get knowledge base context for a query in the session."""
    try:
        chat_service = get_chat_service()
        
        # Verify session exists
        session = await chat_service.get_session(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Chat session not found")
        
        # Get context (this would need to be exposed from the chat service)
        context = await chat_service._get_chat_context(query)
        
        if not context:
            return {"sources": [], "context_text": "", "source_count": 0}
        
        return {
            "sources": context.relevant_sources,
            "context_text": context.context_text,
            "source_count": context.source_count,
            "similarity_threshold": context.similarity_threshold
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get session context: {str(e)}")