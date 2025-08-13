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
from api.v1 import agent, content, chat, knowledge, system


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events."""
    # Startup
    settings = get_settings()
    logging.info("Starting AI Agent Backend API")
    
    # Initialize database
    await init_db()
    logging.info("Database initialized")
    
    yield
    
    # Shutdown
    logging.info("Shutting down AI Agent Backend API")


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