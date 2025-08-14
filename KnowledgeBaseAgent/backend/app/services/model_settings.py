"""
Model settings service and phase-specific model routing support types.
"""

from __future__ import annotations

import json
import logging
from enum import Enum
from pathlib import Path
from typing import Any, Dict, Optional, Tuple, List, Literal

from pydantic import BaseModel, Field

from app.services.ai_service import get_ai_service
from app.ai import get_backend_manager
from app.ai.base import ModelType
from app.config import get_settings


logger = logging.getLogger(__name__)


class ModelPhase(str, Enum):
    vision = "vision"
    kb_generation = "kb_generation"
    synthesis = "synthesis"
    chat = "chat"
    embeddings = "embeddings"
    readme_generation = "readme_generation"


class PhaseModelSelector(BaseModel):
    backend: Literal['ollama', 'localai', 'openai', 'openai_compatible']
    model: str
    params: Dict[str, Any] = Field(default_factory=dict)


class ModelSettings(BaseModel):
    per_phase: Dict[ModelPhase, Optional[PhaseModelSelector]] = Field(default_factory=dict)


class ModelSettingsService:
    """Persist and retrieve per-phase model configuration with simple JSON storage."""

    def __init__(self) -> None:
        self.settings = get_settings()
        self.storage_dir = Path(self.settings.DATA_DIR)
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.storage_file = self.storage_dir / "model_settings.json"

    async def get_config(self) -> ModelSettings:
        if not self.storage_file.exists():
            return ModelSettings()
        try:
            data = json.loads(self.storage_file.read_text(encoding="utf-8"))
            per_phase: Dict[ModelPhase, Optional[PhaseModelSelector]] = {}
            for phase_str, selector in data.get("per_phase", {}).items():
                phase = ModelPhase(phase_str)
                per_phase[phase] = PhaseModelSelector(**selector) if selector else None
            return ModelSettings(per_phase=per_phase)
        except Exception as e:
            logger.error(f"Failed to load model settings: {e}")
            return ModelSettings()

    async def set_config(self, per_phase: Dict[ModelPhase, Optional[PhaseModelSelector]]) -> ModelSettings:
        config = ModelSettings(per_phase=per_phase)
        try:
            serializable = {
                "per_phase": {
                    phase.value: selector.model_dump() if selector else None
                    for phase, selector in config.per_phase.items()
                }
            }
            self.storage_file.write_text(json.dumps(serializable, indent=2), encoding="utf-8")
        except Exception as e:
            logger.error(f"Failed to save model settings: {e}")
        return config

    async def list_available(self) -> Dict[str, Any]:
        """List models by backend with simple capability tags."""
        manager = get_backend_manager()
        if not manager:
            return {"backends": {}}
        backends: Dict[str, Any] = {}
        for backend_name in manager.factory._instances.keys():
            backend = await manager.get_backend(backend_name)
            if not backend:
                continue
            models = await backend.list_models()
            backends[backend_name] = {
                "models": [m.name for m in models],
                "capabilities": {
                    m.name: self._capabilities_for_model(m.type, getattr(m, "supports_vision", False))
                    for m in models
                }
            }
        return {"backends": backends}

    def _capabilities_for_model(self, model_type: ModelType, supports_vision: bool) -> List[str]:
        caps: List[str] = []
        if model_type == ModelType.TEXT_GENERATION:
            caps.append("text")
        if model_type == ModelType.EMBEDDING:
            caps.append("embed")
        if supports_vision or model_type == ModelType.VISION:
            caps.append("vision")
        return caps


# Global singleton
_model_settings_service: Optional[ModelSettingsService] = None


def get_model_settings_service() -> ModelSettingsService:
    global _model_settings_service
    if _model_settings_service is None:
        _model_settings_service = ModelSettingsService()
    return _model_settings_service


