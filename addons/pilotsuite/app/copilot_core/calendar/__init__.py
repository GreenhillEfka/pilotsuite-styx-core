"""Calendar module - Smart scheduling with mood awareness.

This module provides intelligent calendar management that integrates
with the Mood Engine and Habitus system for context-aware scheduling.
"""

from .smart_scheduler import SmartScheduler, ScheduleRecommendation
from .mood_aware import MoodAwareScheduler, MoodCalendarConfig
from .suggestions import ScheduleSuggester, ScheduleSuggestion

__all__ = [
    "SmartScheduler",
    "ScheduleRecommendation",
    "MoodAwareScheduler",
    "MoodCalendarConfig",
    "ScheduleSuggester",
    "ScheduleSuggestion",
]
