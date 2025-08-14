"""
Phase-specific model routing to select optimal backend/model/params per phase.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional, Tuple

from app.services.model_settings import (
    ModelPhase,
    PhaseModelSelector,
    get_model_settings_service,
)
from app.ai import get_backend_manager
from app.ai.base import ModelType


logger = logging.getLogger(__name__)


class ModelRouter:
    def __init__(self):
        self._settings_service = get_model_settings_service()

    async def resolve(
        self,
        phase: ModelPhase,
        override: Optional[PhaseModelSelector] = None
    ) -> Tuple[str, str, Dict[str, Any]]:
        """Resolve backend, model, and params for a given phase.

        Returns (backend_name, model_name, params_dict).
        """
        selection = override
        if not selection:
            config = await self._settings_service.get_config()
            selection = config.per_phase.get(phase)

        if selection:
            await self._validate_capability(selection, phase)
            return selection.backend, selection.model, selection.params

        # Fallback selection
        backend, model = await self._fallback_selection_for_phase(phase)
        return backend, model, {}

    async def _validate_capability(self, selector: PhaseModelSelector, phase: ModelPhase) -> None:
        manager = get_backend_manager()
        if not manager:
            raise ValueError("AI backend manager not initialized")
        backend = await manager.get_backend(selector.backend)
        if not backend:
            raise ValueError(f"Backend '{selector.backend}' not available")
        model_info = await backend.get_model_info(selector.model)
        if not model_info:
            raise ValueError(f"Model '{selector.model}' not found on backend '{selector.backend}'")

        required = self._required_model_type_for_phase(phase)
        if required == ModelType.VISION and not getattr(model_info, "supports_vision", False):
            raise ValueError(f"Model '{selector.model}' does not support vision for phase '{phase.value}'")
        if model_info.type != required and required != ModelType.VISION:
            raise ValueError(
                f"Model '{selector.model}' type {model_info.type.value} != required {required.value} for phase {phase.value}"
            )

    def _required_model_type_for_phase(self, phase: ModelPhase) -> ModelType:
        if phase == ModelPhase.embeddings:
            return ModelType.EMBEDDING
        if phase == ModelPhase.vision:
            return ModelType.VISION
        # chat, kb_generation, synthesis use text generation
        return ModelType.TEXT_GENERATION

    async def _fallback_selection_for_phase(self, phase: ModelPhase) -> Tuple[str, str]:
        manager = get_backend_manager()
        if not manager:
            raise ValueError("AI backend manager not initialized")
        required = self._required_model_type_for_phase(phase)
        for backend_name in manager.factory._instances.keys():
            backend = await manager.get_backend(backend_name)
            if not backend:
                continue
            models = await backend.list_models()
            for m in models:
                if required == ModelType.VISION and getattr(m, "supports_vision", False):
                    return backend_name, m.name
                if m.type == required:
                    return backend_name, m.name
        raise ValueError(f"No suitable model found for phase '{phase.value}'")


# Global singleton
_model_router: Optional[ModelRouter] = None


def get_model_router() -> ModelRouter:
    global _model_router
    if _model_router is None:
        _model_router = ModelRouter()
    return _model_router


