"""Bayesian Presence Fusion (P1-001).

Implements P(present | sensor_data) using:
- PIR (Motion)
- BLE/Wi-Fi (Device Proximity)
- CO2/Humidity (Environmental)
- Acoustic (Sound)
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

_LOGGER = logging.getLogger(__name__)

@dataclass
class BayesianPrior:
    """Prior probability of presence based on time/history."""
    zone_id: str
    hour_of_day: int
    probability: float = 0.5 # Neutral prior

class BayesianPresenceEngine:
    """SOTA engine for multi-sensor presence fusion."""
    
    def __init__(self):
        self._priors: Dict[str, float] = {} # zone_id -> current_prob
        self._sensor_reliability: Dict[str, float] = {
            "pir": 0.9,      # High reliability for motion
            "ble": 0.7,      # Medium for proximity
            "co2": 0.4,      # Low but useful for long-term stay
            "acoustic": 0.6  # Medium for activity
        }

    def update_probability(self, zone_id: str, sensor_type: str, detected: bool) -> float:
        """Applies Bayesian update: P(H|E) = (P(E|H) * P(H)) / P(E)."""
        p_h = self._priors.get(zone_id, 0.5) # Current prob (Prior)
        
        # Likelihoods: P(E|H) and P(E|not H)
        reliability = self._sensor_reliability.get(sensor_type, 0.5)
        
        if detected:
            p_e_h = reliability
            p_e_not_h = 1 - reliability
        else:
            p_e_h = 1 - reliability
            p_e_not_h = reliability
            
        # Bayesian Formula (Odds ratio form)
        numerator = p_e_h * p_h
        denominator = (p_e_h * p_h) + (p_e_not_h * (1 - p_h))
        
        new_prob = numerator / max(denominator, 0.001)
        
        # Clamp and store
        new_prob = max(0.01, min(0.99, new_prob))
        self._priors[zone_id] = new_prob
        
        _LOGGER.debug("Bayesian: Zone %s -> %s via %s (prob: %.2f)", 
                      zone_id, "detected" if detected else "idle", sensor_type, new_prob)
        return new_prob

    def get_zone_presence(self, zone_id: str) -> Dict[str, Any]:
        """Returns the fused presence status."""
        prob = self._priors.get(zone_id, 0.5)
        return {
            "zone_id": zone_id,
            "probability": round(prob, 3),
            "status": "occupied" if prob > 0.75 else "uncertain" if prob > 0.25 else "clear",
            "last_update": datetime.now(timezone.utc).isoformat()
        }

# Global Instance
_bayesian_engine: Optional[BayesianPresenceEngine] = None

def get_bayesian_engine() -> BayesianPresenceEngine:
    global _bayesian_engine
    if _bayesian_engine is None:
        _bayesian_engine = BayesianPresenceEngine()
    return _bayesian_engine
