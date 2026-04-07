"""Multi-User Preference Learning (P1-003).

Learns and applies individual user preferences for:
- Light Brightness/Color Temp
- Climate Set Temperature
- Media Genre/Volume
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

_LOGGER = logging.getLogger(__name__)

@dataclass
class UserPreference:
    """Individual user preference profile."""
    user_id: str
    zone_id: str
    domain: str # "light", "climate", "media"
    preferred_value: Any
    confidence: float = 0.5
    last_update: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

class MultiUserPreferenceEngine:
    """Learns and aggregates user preferences for multi-user scenarios."""
    
    def __init__(self):
        self._preferences: Dict[str, UserPreference] = {} # user_id:zone_id:domain -> pref

    def learn_from_override(self, user_id: str, zone_id: str, domain: str, value: Any):
        """Updates preference based on manual user override."""
        key = f"{user_id}:{zone_id}:{domain}"
        
        if key not in self._preferences:
            self._preferences[key] = UserPreference(user_id=user_id, zone_id=zone_id, domain=domain, preferred_value=value)
        else:
            prev = self._preferences[key]
            # Simple weighted update: 80% old, 20% new
            if isinstance(value, (int, float)):
                prev.preferred_value = (prev.preferred_value * 0.8) + (value * 0.2)
            else:
                prev.preferred_value = value
            prev.confidence = min(1.0, prev.confidence + 0.05)
            prev.last_update = datetime.now(timezone.utc).isoformat()
            
        _LOGGER.info("P1-003: Learned pref for %s: %s -> %s", user_id, domain, value)

    def aggregate_preferences(self, zone_id: str, domain: str, active_users: List[str]) -> Any:
        """Aggregates preferences for multiple users (e.g. average)."""
        values = []
        for uid in active_users:
            key = f"{uid}:{zone_id}:{domain}"
            if key in self._preferences:
                values.append(self._preferences[key].preferred_value)
        
        if not values:
            return None # Fallback to system default
            
        if all(isinstance(v, (int, float)) for v in values):
            return sum(values) / len(values)
        
        # Non-numeric: Return first user (priority logic simplified)
        return values[0]

# API Integration
def init_user_pref_api(bp):
    @bp.route("/users/<user_id>/preferences/<zone_id>/<domain>", methods=["GET"])
    def get_user_pref(user_id: str, zone_id: str, domain: str):
        engine = MultiUserPreferenceEngine()
        key = f"{user_id}:{zone_id}:{domain}"
        pref = engine._preferences.get(key)
        if not pref:
            return {"ok": False, "error": "not_found"}, 404
        return {"ok": True, "preference": pref.__dict__}

    @bp.route("/users/<user_id>/preferences", methods=["POST"])
    def set_user_pref(user_id: str):
        import flask
        data = flask.request.get_json() or {}
        engine = MultiUserPreferenceEngine()
        engine.learn_from_override(
            user_id=user_id, 
            zone_id=data.get("zone_id"), 
            domain=data.get("domain"), 
            value=data.get("value")
        )
        return {"ok": True}
