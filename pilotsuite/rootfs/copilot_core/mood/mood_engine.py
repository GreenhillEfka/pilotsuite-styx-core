"""Mood Engine — 5D Mood System für SmartHome (SOTA 2026).

5 Dimensionen:
1. Energy (0-1) — Aktivitätsniveau im Haus
2. Valence (0-1) — Positiv/Negativ Stimmung
3. Arousal (0-1) — Ruhe/Aufregung
4. Dominance (0-1) — Kontrolle/Ohnmacht
5. Stability (0-1) — Stabilität/Chaos

Erfassung aus:
- Lichtverhältnissen
- Temperatur/Humidity
- Aktivitätsmustern
- Präsenz-Verteilung
- Zeit-Tags

Integration:
- Mood → Automation (stimmungsabhängige Regeln)
- Mood → Habitus (Lernen von Mood-Kontext)
- Mood → Dashboard (Visualisierung)
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional
from enum import Enum
import threading
from collections import defaultdict, deque

_LOGGER = logging.getLogger(__name__)


# =============================================================================
# MOOD DIMENSIONS
# =============================================================================

@dataclass
class MoodDimensions:
    """5D Mood Modell."""
    
    energy: float = 0.5       # 0=passive, 1=active
    valence: float = 0.5      # 0=negative, 1=positive
    arousal: float = 0.5      # 0=calm, 1=excited
    dominance: float = 0.5    # 0=submissive, 1=dominant
    stability: float = 0.5    # 0=chaotic, 1=stable
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "energy": round(self.energy, 3),
            "valence": round(self.valence, 3),
            "arousal": round(self.arousal, 3),
            "dominance": round(self.dominance, 3),
            "stability": round(self.stability, 3),
        }
    
    def to_radar_data(self) -> List[float]:
        """Daten für Radar Chart."""
        return [self.energy, self.valence, self.arousal, self.dominance, self.stability]
    
    @classmethod
    def from_dict(cls, data: Dict[str, float]) -> MoodDimensions:
        return cls(
            energy=data.get("energy", 0.5),
            valence=data.get("valence", 0.5),
            arousal=data.get("arousal", 0.5),
            dominance=data.get("dominance", 0.5),
            stability=data.get("stability", 0.5),
        }


# =============================================================================
# MOOD CALCULATOR
# =============================================================================

class MoodCalculator:
    """Berechnet Mood aus Sensor-Daten."""
    
    def __init__(self):
        self._weights = {
            "light": 0.25,
            "temperature": 0.20,
            "activity": 0.25,
            "presence": 0.15,
            "time": 0.15,
        }
    
    def calculate_mood(
        self,
        light_level: float = 0.5,
        temperature: float = 21.0,
        humidity: float = 50.0,
        activity_level: float = 0.5,
        presence_count: int = 1,
        time_of_day: str = "day",
    ) -> MoodDimensions:
        """Mood aus Sensor-Daten berechnen."""
        # Energy from activity + light
        energy = (
            activity_level * self._weights["activity"] +
            light_level * self._weights["light"] +
            self._time_energy_factor(time_of_day) * self._weights["time"]
        )
        energy = max(0.0, min(1.0, energy))
        
        # Valence from temperature + light
        temp_comfort = 1.0 - abs(temperature - 22.0) / 10.0  # Optimal 22°C
        valence = (
            temp_comfort * self._weights["temperature"] +
            light_level * self._weights["light"] +
            0.5 * self._weights["activity"]
        )
        valence = max(0.0, min(1.0, valence))
        
        # Arousal from activity + presence
        arousal = (
            activity_level * 0.5 +
            min(presence_count / 5.0, 1.0) * 0.5
        )
        arousal = max(0.0, min(1.0, arousal))
        
        # Dominance from control (inverse of chaos)
        dominance = 1.0 - arousal * 0.3  # More activity = less control
        dominance = max(0.0, min(1.0, dominance))
        
        # Stability from consistency
        stability = 1.0 - abs(activity_level - 0.5) * 0.5
        stability = max(0.0, min(1.0, stability))
        
        return MoodDimensions(
            energy=energy,
            valence=valence,
            arousal=arousal,
            dominance=dominance,
            stability=stability,
        )
    
    def _time_energy_factor(self, time_of_day: str) -> float:
        """Energy Faktor basierend auf Tageszeit."""
        factors = {
            "morning": 0.7,
            "day": 0.8,
            "evening": 0.5,
            "night": 0.2,
        }
        return factors.get(time_of_day, 0.5)


# =============================================================================
# MOOD TRACKER
# =============================================================================

class MoodTracker:
    """Trackt Mood über Zeit."""
    
    def __init__(self, max_history: int = 1000):
        self._history: Dict[str, deque] = defaultdict(lambda: deque(maxlen=max_history))
        self._current_mood: Dict[str, MoodDimensions] = {}
        self._lock = threading.Lock()
    
    def update_mood(self, zone_id: str, mood: MoodDimensions) -> None:
        """Mood updaten."""
        with self._lock:
            self._current_mood[zone_id] = mood
            self._history[zone_id].append({
                "timestamp": datetime.now(timezone.utc).isoformat(),
                **mood.to_dict(),
            })
    
    def get_current_mood(self, zone_id: str) -> Optional[MoodDimensions]:
        """Aktuellen Mood holen."""
        with self._lock:
            return self._current_mood.get(zone_id)
    
    def get_mood_history(self, zone_id: str, hours: int = 24) -> List[Dict[str, Any]]:
        """Mood History holen."""
        with self._lock:
            history = list(self._history.get(zone_id, []))
            
            # Filter last N hours
            cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
            return [
                h for h in history
                if datetime.fromisoformat(h["timestamp"]).replace(tzinfo=timezone.utc) > cutoff
            ]
    
    def get_mood_trend(self, zone_id: str) -> Dict[str, str]:
        """Mood Trend berechnen."""
        with self._lock:
            history = list(self._history.get(zone_id, []))
            
            if len(history) < 10:
                return {"energy": "unknown", "valence": "unknown", "arousal": "unknown"}
            
            # Compare first 5 vs last 5
            early = history[:5]
            late = history[-5:]
            
            def avg(data, key):
                return sum(d.get(key, 0.5) for d in data) / len(data)
            
            trends = {}
            for dim in ["energy", "valence", "arousal"]:
                diff = avg(late, dim) - avg(early, dim)
                if diff > 0.1:
                    trends[dim] = "increasing"
                elif diff < -0.1:
                    trends[dim] = "decreasing"
                else:
                    trends[dim] = "stable"
            
            return trends


# =============================================================================
# MOOD ENGINE (Main Class)
# =============================================================================

class MoodEngine:
    """Haupt-Engine für Mood System."""
    
    def __init__(self):
        self._calculator = MoodCalculator()
        self._tracker = MoodTracker()
        self._automation_hooks = []
        self._lock = threading.Lock()
        _LOGGER.info("MoodEngine initialized")
    
    def update_zone_mood(
        self,
        zone_id: str,
        sensor_data: Dict[str, Any],
    ) -> MoodDimensions:
        """Zone Mood updaten."""
        mood = self._calculator.calculate_mood(
            light_level=sensor_data.get("light_level", 0.5),
            temperature=sensor_data.get("temperature", 21.0),
            humidity=sensor_data.get("humidity", 50.0),
            activity_level=sensor_data.get("activity_level", 0.5),
            presence_count=sensor_data.get("presence_count", 1),
            time_of_day=sensor_data.get("time_of_day", "day"),
        )
        
        self._tracker.update_mood(zone_id, mood)
        
        # Notify automation hooks
        for hook in self._automation_hooks:
            try:
                hook(zone_id, mood)
            except Exception as e:
                _LOGGER.error(f"Mood hook error: {e}")
        
        return mood
    
    def get_zone_mood(self, zone_id: str) -> Optional[MoodDimensions]:
        """Zone Mood holen."""
        return self._tracker.get_current_mood(zone_id)
    
    def get_house_mood(self) -> Optional[MoodDimensions]:
        """Gesamt-Haus Mood (Durchschnitt aller Zonen)."""
        with self._lock:
            all_moods = list(self._tracker._current_mood.values())
            
            if not all_moods:
                return None
            
            avg_mood = MoodDimensions(
                energy=sum(m.energy for m in all_moods) / len(all_moods),
                valence=sum(m.valence for m in all_moods) / len(all_moods),
                arousal=sum(m.arousal for m in all_moods) / len(all_moods),
                dominance=sum(m.dominance for m in all_moods) / len(all_moods),
                stability=sum(m.stability for m in all_moods) / len(all_moods),
            )
            
            return avg_mood
    
    def get_mood_history(self, zone_id: str, hours: int = 24) -> List[Dict[str, Any]]:
        """Mood History."""
        return self._tracker.get_mood_history(zone_id, hours)
    
    def get_mood_trend(self, zone_id: str) -> Dict[str, str]:
        """Mood Trend."""
        return self._tracker.get_mood_trend(zone_id)
    
    def register_automation_hook(self, hook) -> None:
        """Hook für Mood-basierte Automation."""
        self._automation_hooks.append(hook)
    
    def get_dashboard_data(self) -> Dict[str, Any]:
        """Dashboard Daten."""
        house_mood = self.get_house_mood()
        
        zone_moods = {}
        for zone_id in self._tracker._current_mood:
            mood = self.get_zone_mood(zone_id)
            if mood:
                zone_moods[zone_id] = {
                    "current": mood.to_dict(),
                    "trend": self.get_mood_trend(zone_id),
                    "history_24h": len(self.get_mood_history(zone_id, 24)),
                }
        
        return {
            "house_mood": house_mood.to_dict() if house_mood else {},
            "zones": zone_moods,
            "total_zones": len(zone_moods),
        }
    
    @property
    def stats(self) -> Dict[str, Any]:
        return {
            "tracked_zones": len(self._tracker._current_mood),
            "total_history_entries": sum(len(h) for h in self._tracker._history.values()),
            "automation_hooks": len(self._automation_hooks),
        }


# =============================================================================
# Singleton
# =============================================================================

_engine_instance: Optional[MoodEngine] = None


def get_mood_engine() -> MoodEngine:
    """Singleton-Zugriff."""
    global _engine_instance
    
    if _engine_instance is None:
        _engine_instance = MoodEngine()
    
    return _engine_instance
