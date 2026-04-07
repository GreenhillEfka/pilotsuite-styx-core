"""Presence Extended Module — Stub for tests."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional
from enum import Enum


class PresenceMode(str, Enum):
    """Presence modes."""
    HOME = "home"
    AWAY = "away"
    EXTENDED_AWAY = "extended_away"
    VACATION = "vacation"


@dataclass
class PresenceState:
    """Extended presence state."""
    zone_id: str
    mode: PresenceMode = PresenceMode.AWAY
    last_seen: Optional[datetime] = None
    hold_until: Optional[datetime] = None
    confidence: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "zone_id": self.zone_id,
            "mode": self.mode.value,
            "last_seen": self.last_seen.isoformat() if self.last_seen else None,
            "hold_until": self.hold_until.isoformat() if self.hold_until else None,
            "confidence": self.confidence,
        }


class PresenceExtended:
    """Extended presence tracking."""
    
    def __init__(self):
        self._states: Dict[str, PresenceState] = {}
    
    def get_state(self, zone_id: str) -> Optional[PresenceState]:
        """Get presence state for a zone."""
        return self._states.get(zone_id)
    
    def set_state(self, state: PresenceState) -> bool:
        """Set presence state for a zone."""
        self._states[state.zone_id] = state
        return True


def create_presence_extended() -> PresenceExtended:
    """Factory function."""
    return PresenceExtended()
