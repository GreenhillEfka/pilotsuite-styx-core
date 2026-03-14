"""
Mood Module — Context-Aware Comfort/Frugality/Joy Scoring

Provides continuous comfort/frugality/joy metrics from:
- MediaContext (music/TV playback patterns)
- Habitus (user behavior patterns and time-of-day)
- Environmental sensors (temperature, light, time)

Used to contextualize automation suggestions and improve relevance.
"""

from .service import MoodService
from .live_engine import (
    LiveMoodEngine,
    LiveMoodState,
    MoodScore3D,
    MoodDimension,
    MoodTransition,
    get_live_mood_engine
)

__all__ = [
    "MoodService",
    "LiveMoodEngine",
    "LiveMoodState",
    "MoodScore3D",
    "MoodDimension",
    "MoodTransition",
    "get_live_mood_engine"
]
