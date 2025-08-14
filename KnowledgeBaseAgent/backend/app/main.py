"""
FastAPI application initialization and configuration.
"""
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import logging

from app.config import get_settings
from app.middleware import setup_middleware
from app.database import init_db
from app.logging_config import setup_logging
from app.services.ai_service import initialize_ai_service, cleanup_ai_service
from app.websocket.pubsub import get_pubsub_manager
from api.v1 import agent, content, chat, knowledge, system, search, websocket, auth, migration, readme, pipeline


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events."""
    # Startup
    setup_logging()
    settings = get_settings()
    logging.info("Starting AI Agent Backend API")
    
    # Database initialization is handled by Alembic migrations
    # await init_db()
    logging.info("Database connection ready")
    
    # Initialize AI service
    try:
        await initialize_ai_service()
        logging.info("AI service initialized")
    except Exception as e:
        logging.error(f"Failed to initialize AI service: {e}")
        # Continue startup even if AI service fails - it can be retried later
    
    # Initialize WebSocket PubSub
    try:
        pubsub_manager = get_pubsub_manager()
        await pubsub_manager.initialize()
        await pubsub_manager.start_listening()
        
        # Subscribe to common channels
        await pubsub_manager.subscribe_to_channel("task_updates")
        await pubsub_manager.subscribe_to_channel("system_status")
        await pubsub_manager.subscribe_to_channel("notifications")
        
        logging.info("WebSocket PubSub initialized")
    except Exception as e:
        logging.error(f"Failed to initialize WebSocket PubSub: {e}")
        # Continue startup even if PubSub fails
    
    yield
    
    # Shutdown
    logging.info("Shutting down AI Agent Backend API")
    
    # Cleanup AI service
    try:
        await cleanup_ai_service()
        logging.info("AI service cleaned up")
    except Exception as e:
        logging.error(f"Error during AI service cleanup: {e}")
    
    # Cleanup WebSocket PubSub
    try:
        pubsub_manager = get_pubsub_manager()
        await pubsub_manager.stop_listening()
        logging.info("WebSocket PubSub cleaned up")
    except Exception as e:
        logging.error(f"Error during WebSocket PubSub cleanup: {e}")


def create_app() -> FastAPI:
    """Create and configure FastAPI application."""
    settings = get_settings()
    
    app = FastAPI(
        title="AI Agent Backend API",
        description="Backend API service for the Knowledge Base AI Agent system",
        version="1.0.0",
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan
    )
    
    # Setup middleware
    setup_middleware(app)
    
    # Add CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.ALLOWED_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # Include API routers
    app.include_router(agent.router, prefix="/api/v1/agent", tags=["agent"])
    app.include_router(content.router, prefix="/api/v1/content", tags=["content"])
    app.include_router(chat.router, prefix="/api/v1/chat", tags=["chat"])
    app.include_router(knowledge.router, prefix="/api/v1/knowledge", tags=["knowledge"])
    app.include_router(system.router, prefix="/api/v1/system", tags=["system"])
    app.include_router(search.router, prefix="/api/v1/search", tags=["search"])
    app.include_router(websocket.router, prefix="/api/v1", tags=["websocket"])
    app.include_router(auth.router, prefix="/api/v1/auth", tags=["authentication"])
    app.include_router(migration.router, prefix="/api/v1/migration", tags=["migration"])
    app.include_router(readme.router, prefix="/api/v1", tags=["readme"])
    app.include_router(pipeline.router, prefix="/api/v1", tags=["pipeline"])
    
    return app


app = create_app()


@app.get("/health")
async def health_check():
    """Basic health check endpoint."""
    return {
        "status": "healthy",
        "service": "ai-agent-backend",
        "version": "1.0.0"
    }