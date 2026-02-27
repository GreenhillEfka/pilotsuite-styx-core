"""Mood Module v3.0 — Unified Mood Inference + Persistence.

Provides:
- Discrete mood states (away/night/relax/focus/active/neutral) via Softmax
- Continuous dimensions (comfort/frugality/joy/energy/stress)
- Per-zone mood profiles with entity dependency tracking
- SQLite persistence with 30-day rolling history
- REST API for HA integration consumption

Architecture:
    models.py      → Data types (MoodState, MoodDimensions, ZoneMoodProfile, ...)
    engine.py      → UnifiedMoodEngine (inference: sensors → mood profile)
    service.py     → MoodService (persistence + query layer)
    scoring.py     → MoodScorer (event-based sentiment scoring)
    orchestrator.py → MoodOrchestrator (mood → HA service calls)
    actions.py     → ActionEngine (service call generation)
    api.py         → Flask Blueprint (REST endpoints)
"""

from .models import (
    EntityDependency,
    EntityRole,
    MoodDimensions,
    MoodDimensionName,
    MoodState,
    MoodSystemConfig,
    MoodTransition,
    ZoneConfig,
    ZoneMoodProfile,
)
from .engine import UnifiedMoodEngine
from .service import MoodService
from .api import mood_bp, init_mood_api

__all__ = [
    # Models
    "EntityDependency",
    "EntityRole",
    "MoodDimensions",
    "MoodDimensionName",
    "MoodState",
    "MoodSystemConfig",
    "MoodTransition",
    "ZoneConfig",
    "ZoneMoodProfile",
    # Engine
    "UnifiedMoodEngine",
    # Service
    "MoodService",
    # API
    "mood_bp",
    "init_mood_api",
]
