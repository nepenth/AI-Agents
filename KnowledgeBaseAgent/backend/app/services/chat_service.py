"""
Chat service for AI-powered conversations with knowledge base integration.
"""

import asyncio
import logging
import uuid
from typing import List, Dict, Any, Optional, AsyncGenerator, Tuple
from dataclasses import dataclass
from datetime import datetime

from app.services.ai_service import get_ai_service
from app.services.model_router import get_model_router
from app.services.model_settings import ModelPhase
from app.services.vector_search import get_vector_search_service, SearchQuery, SearchType
from app.ai.base import GenerationConfig
from app.models.chat import ChatSession, ChatMessage
from app.schemas.chat import ChatSessionCreate, ChatMessageCreate
from app.repositories.chat import get_chat_repository
from app.database.connection import get_db_session

logger = logging.getLogger(__name__)


@dataclass
class ChatContext:
    """Context information for chat responses."""
    relevant_sources: List[Dict[str, Any]]
    search_query: str
    context_text: str
    source_count: int
    similarity_threshold: float


@dataclass
class ChatResponse:
    """Response from chat service."""
    message_id: str
    content: str
    context: Optional[ChatContext]
    model_used: str
    generation_time: float
    token_count: Optional[int] = None
    streaming: bool = False


class ChatService:
    """Service for managing AI-powered chat conversations."""
    
    def __init__(self):
        self.max_context_length = 4000  # tokens
        self.max_sources = 5
        self.similarity_threshold = 0.7
        self.context_window_messages = 10  # Number of recent messages to include
    
    async def create_session(
        self,
        title: Optional[str] = None,
        system_prompt: Optional[str] = None
    ) -> ChatSession:
        """
        Create a new chat session.
        
        Args:
            title: Optional session title
            system_prompt: Optional system prompt for the session
            
        Returns:
            Created chat session
        """
        try:
            chat_repo = get_chat_repository()
            
            session_create = ChatSessionCreate(
                id=str(uuid.uuid4()),
                title=title or f"Chat Session {datetime.utcnow().strftime('%Y-%m-%d %H:%M')}",
                system_prompt=system_prompt
            )
            
            async with get_db_session() as db:
                session = await chat_repo.create_session(db, session_create)
            
            logger.info(f"Created chat session: {session.id}")
            return session
            
        except Exception as e:
            logger.error(f"Failed to create chat session: {e}")
            raise
    
    async def get_session(self, session_id: str) -> Optional[ChatSession]:
        """Get a chat session by ID."""
        try:
            chat_repo = get_chat_repository()
            
            async with get_db_session() as db:
                return await chat_repo.get_session(db, session_id)
                
        except Exception as e:
            logger.error(f"Failed to get chat session {session_id}: {e}")
            return None
    
    async def list_sessions(
        self,
        limit: int = 50,
        offset: int = 0,
        include_archived: bool = False
    ) -> List[ChatSession]:
        """List chat sessions."""
        try:
            chat_repo = get_chat_repository()
            
            async with get_db_session() as db:
                return await chat_repo.list_sessions(db, limit, offset, include_archived)
                
        except Exception as e:
            logger.error(f"Failed to list chat sessions: {e}")
            return []
    
    async def update_session(
        self,
        session_id: str,
        updates: Dict[str, Any]
    ) -> Optional[ChatSession]:
        """Update a chat session."""
        try:
            chat_repo = get_chat_repository()
            
            async with get_db_session() as db:
                return await chat_repo.update_session(db, session_id, updates)
                
        except Exception as e:
            logger.error(f"Failed to update chat session {session_id}: {e}")
            return None
    
    async def delete_session(self, session_id: str) -> bool:
        """Delete a chat session."""
        try:
            chat_repo = get_chat_repository()
            
            async with get_db_session() as db:
                return await chat_repo.delete_session(db, session_id)
                
        except Exception as e:
            logger.error(f"Failed to delete chat session {session_id}: {e}")
            return False
    
    async def send_message(
        self,
        session_id: str,
        content: str,
        model_name: Optional[str] = None,
        use_knowledge_base: bool = True,
        streaming: bool = False
    ) -> ChatResponse:
        """
        Send a message and get AI response.
        
        Args:
            session_id: Chat session ID
            content: User message content
            model_name: Optional AI model to use
            use_knowledge_base: Whether to use knowledge base for context
            streaming: Whether to use streaming response
            
        Returns:
            Chat response with AI-generated content
        """
        try:
            import time
            start_time = time.time()
            
            chat_repo = get_chat_repository()
            
            async with get_db_session() as db:
                # Get session
                session = await chat_repo.get_session(db, session_id)
                if not session:
                    raise ValueError(f"Chat session {session_id} not found")
                
                # Save user message
                user_message = ChatMessageCreate(
                    id=str(uuid.uuid4()),
                    session_id=session_id,
                    role="user",
                    content=content
                )
                await chat_repo.create_message(db, user_message)
                
                # Generate AI response
                if streaming:
                    response = await self._generate_streaming_response(
                        session, content, model_name, use_knowledge_base
                    )
                else:
                    response = await self._generate_response(
                        session, content, model_name, use_knowledge_base
                    )
                
                # Save AI message
                ai_message = ChatMessageCreate(
                    id=response.message_id,
                    session_id=session_id,
                    role="assistant",
                    content=response.content,
                    model_used=response.model_used,
                    sources=response.context.relevant_sources if response.context else [],
                    context_stats={
                        "source_count": response.context.source_count if response.context else 0,
                        "similarity_threshold": response.context.similarity_threshold if response.context else 0,
                        "generation_time": response.generation_time,
                        "token_count": response.token_count
                    }
                )
                await chat_repo.create_message(db, ai_message)
                
                # Update session
                await chat_repo.update_session(db, session_id, {
                    "message_count": session.message_count + 2,  # user + assistant
                    "last_updated": datetime.utcnow()
                })
            
            response.generation_time = time.time() - start_time
            logger.info(f"Generated chat response for session {session_id} in {response.generation_time:.2f}s")
            
            return response
            
        except Exception as e:
            logger.error(f"Failed to send message in session {session_id}: {e}")
            raise
    
    async def _generate_response(
        self,
        session: ChatSession,
        user_message: str,
        model_name: Optional[str],
        use_knowledge_base: bool
    ) -> ChatResponse:
        """Generate a non-streaming AI response."""
        # Get context from knowledge base
        context = None
        if use_knowledge_base:
            context = await self._get_chat_context(user_message)
        
        # Get conversation history
        conversation_history = await self._get_conversation_history(session.id)
        
        # Build prompt
        prompt = await self._build_chat_prompt(
            user_message, context, conversation_history, session.system_prompt
        )
        
        # Generate response
        router = get_model_router()
        if model_name:
            # Respect explicit selection
            model = model_name
            backend_name = None
            config = GenerationConfig(temperature=0.7, max_tokens=800, top_p=0.9, stream=True)
        else:
            backend_name, model, params = await router.resolve(ModelPhase.chat)
            config = GenerationConfig(
                temperature=float(params.get("temperature", 0.7)),
                max_tokens=params.get("max_tokens", 800),
                top_p=float(params.get("top_p", 0.9)),
                stream=True
            )
        
        config = GenerationConfig(
            temperature=0.7,
            max_tokens=800,
            top_p=0.9
        )
        
        response_content = await ai_service.generate_text(prompt, model, config=config)
        
        return ChatResponse(
            message_id=str(uuid.uuid4()),
            content=response_content,
            context=context,
            model_used=model,
            generation_time=0.0,  # Will be set by caller
            streaming=False
        )
    
    async def _generate_streaming_response(
        self,
        session: ChatSession,
        user_message: str,
        model_name: Optional[str],
        use_knowledge_base: bool
    ) -> ChatResponse:
        """Generate a streaming AI response."""
        # Get context from knowledge base
        context = None
        if use_knowledge_base:
            context = await self._get_chat_context(user_message)
        
        # Get conversation history
        conversation_history = await self._get_conversation_history(session.id)
        
        # Build prompt
        prompt = await self._build_chat_prompt(
            user_message, context, conversation_history, session.system_prompt
        )
        
        # Generate streaming response
        ai_service = get_ai_service()
        models = await ai_service.list_models()
        text_models = [m for m in models if m.get("type") == "text_generation"]
        
        if not text_models:
            raise ValueError("No text generation models available")
        
        model = model_name or text_models[0]["name"]
        
        config = GenerationConfig(
            temperature=0.7,
            max_tokens=800,
            top_p=0.9,
            stream=True
        )
        
        # Collect streaming response
        response_chunks = []
        async for chunk in ai_service.generate_stream(prompt, model, backend_name=backend_name, config=config):
            response_chunks.append(chunk)
        
        response_content = "".join(response_chunks)
        
        return ChatResponse(
            message_id=str(uuid.uuid4()),
            content=response_content,
            context=context,
            model_used=model,
            generation_time=0.0,  # Will be set by caller
            streaming=True
        )
    
    async def _get_chat_context(self, user_message: str) -> Optional[ChatContext]:
        """Get relevant context from knowledge base."""
        try:
            search_service = get_vector_search_service()
            
            # Search for relevant content
            search_query = SearchQuery(
                query_text=user_message,
                search_type=SearchType.HYBRID,
                limit=self.max_sources,
                similarity_threshold=self.similarity_threshold,
                include_content=True
            )
            
            search_results = await search_service.search(search_query)
            
            if not search_results:
                return None
            
            # Build context from search results
            relevant_sources = []
            context_parts = []
            
            for result in search_results:
                if result.knowledge_item:
                    source_info = {
                        "id": result.knowledge_item_id,
                        "title": result.knowledge_item.display_title,
                        "summary": result.knowledge_item.summary,
                        "similarity_score": result.similarity_score,
                        "chunk_text": result.chunk_text
                    }
                    relevant_sources.append(source_info)
                    
                    # Add to context
                    context_parts.append(f"Source: {result.knowledge_item.display_title}")
                    if result.knowledge_item.summary:
                        context_parts.append(f"Summary: {result.knowledge_item.summary}")
                    context_parts.append(f"Content: {result.chunk_text}")
                    context_parts.append("---")
            
            context_text = "\n".join(context_parts)
            
            # Truncate if too long
            if len(context_text) > self.max_context_length:
                context_text = context_text[:self.max_context_length] + "..."
            
            return ChatContext(
                relevant_sources=relevant_sources,
                search_query=user_message,
                context_text=context_text,
                source_count=len(relevant_sources),
                similarity_threshold=self.similarity_threshold
            )
            
        except Exception as e:
            logger.error(f"Failed to get chat context: {e}")
            return None
    
    async def _get_conversation_history(self, session_id: str) -> List[Dict[str, str]]:
        """Get recent conversation history."""
        try:
            chat_repo = get_chat_repository()
            
            async with get_db_session() as db:
                messages = await chat_repo.get_messages(
                    db, session_id, limit=self.context_window_messages
                )
            
            # Convert to conversation format
            history = []
            for message in reversed(messages):  # Reverse to get chronological order
                history.append({
                    "role": message.role,
                    "content": message.content
                })
            
            return history
            
        except Exception as e:
            logger.error(f"Failed to get conversation history: {e}")
            return []
    
    async def _build_chat_prompt(
        self,
        user_message: str,
        context: Optional[ChatContext],
        conversation_history: List[Dict[str, str]],
        system_prompt: Optional[str]
    ) -> str:
        """Build the complete prompt for AI generation."""
        prompt_parts = []
        
        # System prompt
        if system_prompt:
            prompt_parts.append(f"System: {system_prompt}")
        else:
            prompt_parts.append("System: You are a helpful AI assistant with access to a knowledge base. Provide accurate, helpful responses based on the available information.")
        
        # Knowledge base context
        if context and context.relevant_sources:
            prompt_parts.append("\nKnowledge Base Context:")
            prompt_parts.append(context.context_text)
            prompt_parts.append("\nPlease use this context to inform your response when relevant. If you reference information from the context, mention the source.")
        
        # Conversation history
        if conversation_history:
            prompt_parts.append("\nConversation History:")
            for msg in conversation_history[-6:]:  # Last 6 messages
                prompt_parts.append(f"{msg['role'].title()}: {msg['content']}")
        
        # Current user message
        prompt_parts.append(f"\nUser: {user_message}")
        prompt_parts.append("\nAssistant:")
        
        return "\n".join(prompt_parts)
    
    async def get_messages(
        self,
        session_id: str,
        limit: int = 50,
        offset: int = 0
    ) -> List[ChatMessage]:
        """Get messages for a chat session."""
        try:
            chat_repo = get_chat_repository()
            
            async with get_db_session() as db:
                return await chat_repo.get_messages(db, session_id, limit, offset)
                
        except Exception as e:
            logger.error(f"Failed to get messages for session {session_id}: {e}")
            return []
    
    async def delete_message(self, message_id: str) -> bool:
        """Delete a chat message."""
        try:
            chat_repo = get_chat_repository()
            
            async with get_db_session() as db:
                return await chat_repo.delete_message(db, message_id)
                
        except Exception as e:
            logger.error(f"Failed to delete message {message_id}: {e}")
            return False
    
    async def regenerate_response(
        self,
        session_id: str,
        message_id: str,
        model_name: Optional[str] = None
    ) -> Optional[ChatResponse]:
        """Regenerate an AI response."""
        try:
            chat_repo = get_chat_repository()
            
            async with get_db_session() as db:
                # Get the message to regenerate
                message = await chat_repo.get_message(db, message_id)
                if not message or message.role != "assistant":
                    return None
                
                # Get the previous user message
                messages = await chat_repo.get_messages(db, session_id, limit=10)
                user_message = None
                
                for i, msg in enumerate(messages):
                    if msg.id == message_id and i > 0:
                        prev_msg = messages[i - 1]
                        if prev_msg.role == "user":
                            user_message = prev_msg.content
                        break
                
                if not user_message:
                    return None
                
                # Get session
                session = await chat_repo.get_session(db, session_id)
                if not session:
                    return None
                
                # Generate new response
                response = await self._generate_response(
                    session, user_message, model_name, True
                )
                
                # Update the existing message
                await chat_repo.update_message(db, message_id, {
                    "content": response.content,
                    "model_used": response.model_used,
                    "sources": response.context.relevant_sources if response.context else [],
                    "context_stats": {
                        "source_count": response.context.source_count if response.context else 0,
                        "generation_time": response.generation_time
                    }
                })
                
                return response
                
        except Exception as e:
            logger.error(f"Failed to regenerate response for message {message_id}: {e}")
            return None


# Global service instance
_chat_service: Optional[ChatService] = None


def get_chat_service() -> ChatService:
    """Get the global chat service instance."""
    global _chat_service
    if _chat_service is None:
        _chat_service = ChatService()
    return _chat_service