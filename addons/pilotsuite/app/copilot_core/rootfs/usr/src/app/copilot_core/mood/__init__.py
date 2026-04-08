"""
Mood Module — Context-Aware Comfort/Frugality/Joy Scoring

Provides continuous comfort/frugality/joy metrics from:
- MediaContext (music/TV playback patterns)
- Habitus (user behavior patterns and time-of-day)
- Environmental sensors (temperature, light, time)

Used to contextualize automation suggestions and improve relevance.
"""

from .service import MoodService
from .api import mood_bp, init_mood_api

__all__ = ["MoodService", "mood_bp", "init_mood_api"]
