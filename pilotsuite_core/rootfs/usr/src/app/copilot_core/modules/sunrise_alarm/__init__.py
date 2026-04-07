"""Sunrise Alarm Module — Konsolidierter Sonnenlichtwecker.

Provides intelligent alarm/wake-up functionality:
- Per-person alarm schedules with zone assignment
- Sonos wake-up with gradual volume ramp + music/radio
- Light ramp integration (gradual brightness increase)
- Smart snooze and dismiss via HA events
- Weekday/weekend/custom day schedules
- Persistence to /data/sunrise_alarm_*.json

Integration:
- Sonos: play_favorite / play_uri with volume ramp
- Zone Automation: triggers morning scene on alarm fire
- Conversation Memory: reads preferred wake_time per person
"""

from copilot_core.modules.sunrise_alarm.models import (
    AlarmConfig,
    AlarmMode,
    AlarmPreset,
    AlarmRuntime,
    AlarmState,
    CurveType,
    LightConfig,
    MusicConfig,
)
from copilot_core.modules.sunrise_alarm.engine import AlarmEngine

__all__ = [
    "AlarmEngine",
    "AlarmConfig",
    "AlarmMode",
    "AlarmPreset",
    "AlarmRuntime",
    "AlarmState",
    "CurveType",
    "LightConfig",
    "MusicConfig",
]
