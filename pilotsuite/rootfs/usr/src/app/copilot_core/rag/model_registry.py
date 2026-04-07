"""Ollama Model Registry — Central model management for RAG + Chat.

Provides:
- Model discovery (local + cloud)
- Model metadata (capabilities, context window, embedding dim)
- Model recommendations by use case (chat, embedding, code, vision)
- Health checks + auto-fallback

Slice 151 — 168h Massive Iteration
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

import requests

_LOGGER = logging.getLogger(__name__)


class ModelCapability(str, Enum):
    """Model capability flags."""
    CHAT = "chat"
    EMBEDDING = "embedding"
    CODE = "code"
    VISION = "vision"
    FUNCTION_CALLING = "function_calling"
    LARGE_CONTEXT = "large_context"  # >32k tokens


class ModelSize(str, Enum):
    """Model size categories."""
    TINY = "tiny"       # <1B
    SMALL = "small"     # 1-7B
    MEDIUM = "medium"   # 7-20B
    LARGE = "large"     # 20-70B
    XL = "xl"           # >70B


@dataclass
class ModelMetadata:
    """Metadata for a single model."""

    model_id: str
    provider: str  # "ollama", "cloud", "ollama-cloud"
    capabilities: List[ModelCapability] = field(default_factory=list)
    size: ModelSize = ModelSize.SMALL
    context_window: int = 4096
    embedding_dim: int = 0
    language: str = "en"
    recommended_for: List[str] = field(default_factory=list)
    last_checked: float = 0.0
    healthy: bool = True
    error_message: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "model_id": self.model_id,
            "provider": self.provider,
            "capabilities": [c.value for c in self.capabilities],
            "size": self.size.value,
            "context_window": self.context_window,
            "embedding_dim": self.embedding_dim,
            "language": self.language,
            "recommended_for": self.recommended_for,
            "healthy": self.healthy,
            "last_checked": self.last_checked,
            "error": self.error_message if not self.healthy else None,
        }


# ─── Predefined Model Profiles ──────────────────────────────────────────────

MODEL_PROFILES: Dict[str, ModelMetadata] = {
    # Ollama Local Models
    "qwen3:0.6b": ModelMetadata(
        model_id="qwen3:0.6b", provider="ollama",
        capabilities=[ModelCapability.CHAT],
        size=ModelSize.TINY, context_window=32768,
        recommended_for=["fast-chat", "low-resource"],
    ),
    "qwen3:1.7b": ModelMetadata(
        model_id="qwen3:1.7b", provider="ollama",
        capabilities=[ModelCapability.CHAT],
        size=ModelSize.SMALL, context_window=32768,
        recommended_for=["chat", "general"],
    ),
    "qwen3:4b": ModelMetadata(
        model_id="qwen3:4b", provider="ollama",
        capabilities=[ModelCapability.CHAT, ModelCapability.CODE],
        size=ModelSize.SMALL, context_window=32768,
        recommended_for=["chat", "code", "general"],
    ),
    "qwen3.5:9b": ModelMetadata(
        model_id="qwen3.5:9b", provider="ollama",
        capabilities=[ModelCapability.CHAT, ModelCapability.CODE, ModelCapability.FUNCTION_CALLING],
        size=ModelSize.MEDIUM, context_window=40960,
        recommended_for=["chat", "code", "function-calling"],
    ),
    "qwen3.5:397b-cloud": ModelMetadata(
        model_id="qwen3.5:397b-cloud", provider="ollama-cloud",
        capabilities=[ModelCapability.CHAT, ModelCapability.CODE, ModelCapability.FUNCTION_CALLING, ModelCapability.LARGE_CONTEXT],
        size=ModelSize.XL, context_window=256000,
        recommended_for=["complex-reasoning", "code", "long-context"],
    ),
    "llama3.2:3b": ModelMetadata(
        model_id="llama3.2:3b", provider="ollama",
        capabilities=[ModelCapability.CHAT, ModelCapability.VISION],
        size=ModelSize.SMALL, context_window=8192,
        recommended_for=["chat", "vision"],
    ),
    "llama3.1:8b": ModelMetadata(
        model_id="llama3.1:8b", provider="ollama",
        capabilities=[ModelCapability.CHAT, ModelCapability.CODE],
        size=ModelSize.MEDIUM, context_window=8192,
        recommended_for=["chat", "code"],
    ),
    "mistral:7b": ModelMetadata(
        model_id="mistral:7b", provider="ollama",
        capabilities=[ModelCapability.CHAT, ModelCapability.CODE],
        size=ModelSize.MEDIUM, context_window=8192,
        recommended_for=["chat", "code"],
    ),
    "gemma3:4b": ModelMetadata(
        model_id="gemma3:4b", provider="ollama",
        capabilities=[ModelCapability.CHAT],
        size=ModelSize.SMALL, context_window=8192,
        recommended_for=["chat"],
    ),
    "nomic-embed-text": ModelMetadata(
        model_id="nomic-embed-text", provider="ollama",
        capabilities=[ModelCapability.EMBEDDING],
        size=ModelSize.SMALL, embedding_dim=768,
        recommended_for=["embedding", "rag"],
    ),
    "mxbai-embed-large": ModelMetadata(
        model_id="mxbai-embed-large", provider="ollama",
        capabilities=[ModelCapability.EMBEDDING],
        size=ModelSize.MEDIUM, embedding_dim=1024,
        recommended_for=["embedding", "rag"],
    ),
    # Cloud Models
    "gpt-4o-mini": ModelMetadata(
        model_id="gpt-4o-mini", provider="cloud",
        capabilities=[ModelCapability.CHAT, ModelCapability.CODE, ModelCapability.VISION, ModelCapability.FUNCTION_CALLING],
        size=ModelSize.LARGE, context_window=128000,
        recommended_for=["chat", "code", "vision"],
    ),
    "gpt-4o": ModelMetadata(
        model_id="gpt-4o", provider="cloud",
        capabilities=[ModelCapability.CHAT, ModelCapability.CODE, ModelCapability.VISION, ModelCapability.FUNCTION_CALLING],
        size=ModelSize.XL, context_window=128000,
        recommended_for=["chat", "code", "vision", "complex-tasks"],
    ),
    "gpt-oss:20b": ModelMetadata(
        model_id="gpt-oss:20b", provider="ollama-cloud",
        capabilities=[ModelCapability.CHAT, ModelCapability.CODE],
        size=ModelSize.MEDIUM, context_window=32768,
        recommended_for=["chat", "code"],
    ),
    "gpt-oss:120b": ModelMetadata(
        model_id="gpt-oss:120b", provider="ollama-cloud",
        capabilities=[ModelCapability.CHAT, ModelCapability.CODE, ModelCapability.FUNCTION_CALLING],
        size=ModelSize.XL, context_window=128000,
        recommended_for=["complex-reasoning", "code"],
    ),
    "claude-sonnet-4-5": ModelMetadata(
        model_id="claude-sonnet-4-5", provider="cloud",
        capabilities=[ModelCapability.CHAT, ModelCapability.CODE, ModelCapability.FUNCTION_CALLING, ModelCapability.LARGE_CONTEXT],
        size=ModelSize.XL, context_window=200000,
        recommended_for=["complex-reasoning", "code", "long-context"],
    ),
    "deepseek-v3": ModelMetadata(
        model_id="deepseek-v3", provider="cloud",
        capabilities=[ModelCapability.CHAT, ModelCapability.CODE],
        size=ModelSize.XL, context_window=128000,
        recommended_for=["code", "math"],
    ),
}


# ─── Model Registry ─────────────────────────────────────────────────────────


class ModelRegistry:
    """Central registry for all available models.

    Usage:
        registry = ModelRegistry(ollama_url="http://localhost:11434")
        models = registry.list_models()
        recommended = registry.get_recommended("chat")
        health = registry.check_health("qwen3:4b")
    """

    def __init__(
        self,
        ollama_url: str = "http://localhost:11434",
        cloud_api_url: str = "",
        cloud_api_key: str = "",
        cache_ttl: float = 300.0,  # 5 minutes
    ) -> None:
        self._ollama_url = ollama_url.rstrip("/")
        self._cloud_api_url = cloud_api_url
        self._cloud_api_key = cloud_api_key
        self._cache_ttl = cache_ttl
        self._cache: Dict[str, List[ModelMetadata]] = {}
        self._cache_ts: Dict[str, float] = {}
        self._session = requests.Session()

    def list_models(
        self,
        provider: Optional[str] = None,
        capability: Optional[ModelCapability] = None,
        force_refresh: bool = False,
    ) -> List[ModelMetadata]:
        """List available models with optional filters.

        Args:
            provider: Filter by provider ("ollama", "cloud", "ollama-cloud")
            capability: Filter by capability (CHAT, EMBEDDING, CODE, etc.)
            force_refresh: Force refresh from API

        Returns:
            List of ModelMetadata objects
        """
        cache_key = f"{provider or 'all'}_{capability or 'all'}"
        now = time.time()

        if not force_refresh and cache_key in self._cache:
            if now - self._cache_ts.get(cache_key, 0) < self._cache_ttl:
                return self._cache[cache_key]

        models: List[ModelMetadata] = []

        # Get from profiles
        for model_id, profile in MODEL_PROFILES.items():
            if provider and profile.provider != provider:
                continue
            if capability and capability not in profile.capabilities:
                continue
            models.append(profile)

        # Query Ollama for local models
        if not provider or provider == "ollama":
            ollama_models = self._fetch_ollama_models()
            for om in ollama_models:
                if capability and capability not in om.capabilities:
                    continue
                # Merge with profile if exists
                existing = next((m for m in models if m.model_id == om.model_id), None)
                if existing:
                    existing.healthy = om.healthy
                    existing.last_checked = om.last_checked
                else:
                    models.append(om)

        # Cache results
        self._cache[cache_key] = models
        self._cache_ts[cache_key] = now

        return models

    def get_model(self, model_id: str) -> Optional[ModelMetadata]:
        """Get metadata for a specific model."""
        # Check profiles first
        if model_id in MODEL_PROFILES:
            return MODEL_PROFILES[model_id]

        # Try to fetch from Ollama
        try:
            resp = self._session.get(
                f"{self._ollama_url}/api/show",
                json={"name": model_id},
                timeout=5,
            )
            if resp.status_code == 200:
                data = resp.json()
                return ModelMetadata(
                    model_id=model_id,
                    provider="ollama",
                    capabilities=[ModelCapability.CHAT],
                    context_window=data.get("details", {}).get("context_length", 4096),
                    healthy=True,
                    last_checked=time.time(),
                )
        except Exception:
            pass

        return None

    def get_recommended(
        self,
        use_case: str,
        provider: Optional[str] = None,
        max_count: int = 3,
    ) -> List[ModelMetadata]:
        """Get recommended models for a use case.

        Args:
            use_case: Use case ("chat", "code", "embedding", "vision", "rag")
            provider: Optional provider filter
            max_count: Maximum number of recommendations

        Returns:
            List of recommended ModelMetadata
        """
        models = self.list_models(provider=provider)

        # Score by recommendation match
        scored = []
        for m in models:
            score = 0
            if use_case in m.recommended_for:
                score += 10
            if use_case == "chat" and ModelCapability.CHAT in m.capabilities:
                score += 5
            if use_case == "code" and ModelCapability.CODE in m.capabilities:
                score += 5
            if use_case == "embedding" and ModelCapability.EMBEDDING in m.capabilities:
                score += 5
            if use_case == "vision" and ModelCapability.VISION in m.capabilities:
                score += 5
            if use_case == "rag" and ModelCapability.EMBEDDING in m.capabilities:
                score += 5
            if m.healthy:
                score += 2
            if score > 0:
                scored.append((score, m))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [m for _, m in scored[:max_count]]

    def check_health(self, model_id: str) -> bool:
        """Check if a model is healthy/available.

        Returns True if model is ready to use.
        """
        profile = MODEL_PROFILES.get(model_id)

        if not profile or profile.provider == "cloud":
            # For cloud models, just check config
            return bool(self._cloud_api_url and self._cloud_api_key)

        # For Ollama models, try a ping
        try:
            resp = self._session.get(
                f"{self._ollama_url}/api/tags",
                timeout=3,
            )
            if resp.status_code == 200:
                models = resp.json().get("models", [])
                return any(m.get("name") == model_id for m in models)
        except Exception:
            pass

        return False

    def _fetch_ollama_models(self) -> List[ModelMetadata]:
        """Fetch available models from Ollama API."""
        models: List[ModelMetadata] = []

        try:
            resp = self._session.get(
                f"{self._ollama_url}/api/tags",
                timeout=5,
            )
            if resp.status_code == 200:
                data = resp.json()
                for model in data.get("models", []):
                    name = model.get("name", "")
                    details = model.get("details", {})

                    # Infer capabilities
                    capabilities = [ModelCapability.CHAT]
                    if "embed" in name.lower():
                        capabilities.append(ModelCapability.EMBEDDING)
                    if "code" in name.lower() or "coder" in name.lower():
                        capabilities.append(ModelCapability.CODE)
                    if "vision" in name.lower() or "llava" in name.lower():
                        capabilities.append(ModelCapability.VISION)

                    # Infer size
                    size = ModelSize.SMALL
                    param_size = details.get("parameter_size", "")
                    if "70b" in param_size.lower() or "120b" in param_size.lower():
                        size = ModelSize.XL
                    elif "20b" in param_size.lower() or "30b" in param_size.lower():
                        size = ModelSize.LARGE
                    elif "7b" in param_size.lower() or "8b" in param_size.lower():
                        size = ModelSize.MEDIUM
                    elif "1b" in param_size.lower() or "0.6b" in param_size.lower():
                        size = ModelSize.TINY

                    models.append(ModelMetadata(
                        model_id=name,
                        provider="ollama",
                        capabilities=capabilities,
                        size=size,
                        context_window=details.get("context_length", 4096),
                        healthy=True,
                        last_checked=time.time(),
                    ))
        except Exception as exc:
            _LOGGER.warning("Failed to fetch Ollama models: %s", exc)

        return models

    def get_summary(self) -> Dict[str, Any]:
        """Get registry summary for dashboard."""
        all_models = self.list_models()
        by_provider: Dict[str, int] = {}
        by_capability: Dict[str, int] = {}
        healthy_count = 0

        for m in all_models:
            by_provider[m.provider] = by_provider.get(m.provider, 0) + 1
            for cap in m.capabilities:
                by_capability[cap.value] = by_capability.get(cap.value, 0) + 1
            if m.healthy:
                healthy_count += 1

        return {
            "total_models": len(all_models),
            "by_provider": by_provider,
            "by_capability": by_capability,
            "healthy_models": healthy_count,
            "unhealthy_models": len(all_models) - healthy_count,
            "cache_age_seconds": time.time() - max(self._cache_ts.values()) if self._cache_ts else 0,
        }


# ─── Global Instance ────────────────────────────────────────────────────────

_registry: Optional[ModelRegistry] = None


def get_model_registry(
    ollama_url: str = "http://localhost:11434",
    cloud_api_url: str = "",
    cloud_api_key: str = "",
) -> ModelRegistry:
    """Get or create the global model registry instance."""
    global _registry
    if _registry is None:
        _registry = ModelRegistry(
            ollama_url=ollama_url,
            cloud_api_url=cloud_api_url,
            cloud_api_key=cloud_api_key,
        )
    return _registry
