"""
System monitoring endpoints for health checks, metrics, and logs.
"""
from fastapi import APIRouter, HTTPException, Query
from typing import Optional, List, Dict, Any
import psutil
import time
from datetime import datetime

from app.services.ai_service import get_ai_service
from app.ai.base import ModelType
from app.services.model_settings import (
    get_model_settings_service,
    ModelPhase,
    PhaseModelSelector,
)

router = APIRouter()


@router.get("/health")
async def system_health():
    """Comprehensive system health check."""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "service": "system",
        "uptime": time.time()
    }


@router.get("/metrics")
async def get_system_metrics():
    """Get system resource usage metrics."""
    try:
        cpu_percent = psutil.cpu_percent(interval=1)
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        
        return {
            "cpu": {
                "usage_percent": cpu_percent,
                "count": psutil.cpu_count()
            },
            "memory": {
                "total": memory.total,
                "available": memory.available,
                "used": memory.used,
                "usage_percent": memory.percent
            },
            "disk": {
                "total": disk.total,
                "used": disk.used,
                "free": disk.free,
                "usage_percent": (disk.used / disk.total) * 100
            },
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        return {
            "error": f"Failed to get system metrics: {str(e)}",
            "timestamp": datetime.utcnow().isoformat()
        }


@router.get("/logs")
async def get_system_logs():
    """Get system logs with optional filtering."""
    # TODO: Implement log retrieval with filtering
    return {"logs": [], "message": "Log retrieval endpoint - to be implemented"}


@router.get("/ai/status")
async def get_ai_status():
    """Get AI backends status and health information."""
    try:
        ai_service = get_ai_service()
        status = await ai_service.get_backend_status()
        return status
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get AI status: {str(e)}")


@router.get("/ai/models")
async def list_ai_models(
    backend: Optional[str] = Query(None, description="Backend name to list models from"),
    model_type: Optional[str] = Query(None, description="Filter by model type (text_generation, embedding, vision)")
):
    """List available AI models from specified backend."""
    try:
        ai_service = get_ai_service()
        
        # Convert string to ModelType enum if provided
        type_filter = None
        if model_type:
            try:
                type_filter = ModelType(model_type)
            except ValueError:
                raise HTTPException(
                    status_code=400, 
                    detail=f"Invalid model type: {model_type}. Valid types: {[t.value for t in ModelType]}"
                )
        
        models = await ai_service.list_models(backend, type_filter)
        return {
            "backend": backend or "default",
            "model_type_filter": model_type,
            "models": models,
            "total": len(models)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list models: {str(e)}")


@router.get("/models/available")
async def list_available_models():
    """List models grouped by backend with simple capability tags."""
    try:
        svc = get_model_settings_service()
        return await svc.list_available()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list available models: {str(e)}")


@router.get("/models/config")
async def get_models_config():
    try:
        svc = get_model_settings_service()
        cfg = await svc.get_config()
        return {
            "per_phase": {
                phase.value: (selector.model_dump() if selector else None)
                for phase, selector in cfg.per_phase.items()
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get model config: {str(e)}")


@router.put("/models/config")
async def update_models_config(payload: Dict[str, Any]):
    try:
        per_phase_raw = payload.get("per_phase", {})
        per_phase: Dict[ModelPhase, Optional[PhaseModelSelector]] = {}
        for phase_str, selector in per_phase_raw.items():
            phase = ModelPhase(phase_str)
            per_phase[phase] = PhaseModelSelector(**selector) if selector else None
        svc = get_model_settings_service()
        cfg = await svc.set_config(per_phase)
        return {
            "per_phase": {
                phase.value: (selector.model_dump() if selector else None)
                for phase, selector in cfg.per_phase.items()
            }
        }
    except ValueError as ve:
        raise HTTPException(status_code=422, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update model config: {str(e)}")


@router.post("/ai/health-check")
async def ai_health_check():
    """Perform health check on AI service and backends."""
    try:
        ai_service = get_ai_service()
        is_healthy = await ai_service.health_check()
        status = await ai_service.get_backend_status()
        
        return {
            "healthy": is_healthy,
            "timestamp": datetime.utcnow().isoformat(),
            "details": status
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AI health check failed: {str(e)}")