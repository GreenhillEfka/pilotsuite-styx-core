"""Pattern Learner — ML-based usage pattern detection (v1.0.0).

Lernt Nutzungsmuster aus Home Assistant Events:
- Zeitbasierte Muster (morgens Licht an, abends Jalousien)
- Wetter-basierte Muster (Sonnig → Jalousien runter)
- Geräte-spezifische Muster (Licht an/aus, Temp-Änderungen)
- Sequenz-Muster (Abläufe von Aktionen)
"""

from __future__ import annotations

import json
import logging
import os
from collections import defaultdict
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

_LOGGER = logging.getLogger(__name__)


@dataclass
class Pattern:
    """Ein gelerntes Nutzungsmuster."""
    
    pattern_id: str
    pattern_type: str  # "time_based", "weather_based", "sequence", "device"
    entity_id: str
    action: str  # "turn_on", "turn_off", "set_temperature", etc.
    
    # Zeitbasierte Features
    hour_of_day: Optional[int] = None  # 0-23
    day_of_week: Optional[int] = None  # 0-6 (Montag=0)
    time_window: Optional[Tuple[int, int]] = None  # (start_hour, end_hour)
    
    # Wetter-Features
    weather_condition: Optional[str] = None  # "sunny", "cloudy", "rainy"
    temperature_range: Optional[Tuple[float, float]] = None  # (min, max)
    solar_radiation: Optional[float] = None  # W/m²
    
    # Statistik
    occurrence_count: int = 1
    confidence: float = 0.0  # 0.0 - 1.0
    last_occurrence: Optional[datetime] = None
    first_occurrence: Optional[datetime] = None
    
    # Kontext
    related_entities: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Konvertiere zu Dictionary."""
        data = asdict(self)
        # Konvertiere datetime zu ISO-String
        if data.get("last_occurrence"):
            data["last_occurrence"] = data["last_occurrence"].isoformat()
        if data.get("first_occurrence"):
            data["first_occurrence"] = data["first_occurrence"].isoformat()
        # Konvertiere Tupel zu Listen für JSON
        if data.get("time_window"):
            data["time_window"] = list(data["time_window"])
        if data.get("temperature_range"):
            data["temperature_range"] = list(data["temperature_range"])
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> Pattern:
        """Erstelle Pattern aus Dictionary."""
        if data.get("last_occurrence"):
            data["last_occurrence"] = datetime.fromisoformat(data["last_occurrence"])
        if data.get("first_occurrence"):
            data["first_occurrence"] = datetime.fromisoformat(data["first_occurrence"])
        if data.get("time_window"):
            data["time_window"] = tuple(data["time_window"])
        if data.get("temperature_range"):
            data["temperature_range"] = tuple(data["temperature_range"])
        return cls(**data)


@dataclass
class PatternStats:
    """Statistik über gelernte Muster."""
    
    total_patterns: int = 0
    time_based_patterns: int = 0
    weather_based_patterns: int = 0
    sequence_patterns: int = 0
    device_patterns: int = 0
    avg_confidence: float = 0.0
    total_observations: int = 0


class PatternLearner:
    """ML Pattern Learning Engine.
    
    Lernt automatisch Nutzungsmuster aus Home Assistant Events
    und speichert sie für Vorhersagen.
    """
    
    def __init__(self, data_dir: str = "/data/patterns"):
        """Initialisiere Pattern Learner.
        
        Args:
            data_dir: Verzeichnis zum Speichern der gelernten Muster
        """
        self.data_dir = Path(data_dir)
        self.patterns_file = self.data_dir / "learned_patterns.json"
        self.observations_file = self.data_dir / "observations.jsonl"
        
        # Pattern-Speicher
        self.patterns: Dict[str, Pattern] = {}
        
        # Beobachtungen für inkrementelles Lernen
        self.observations: List[Dict[str, Any]] = []
        self.max_observations = 10000  # Max Beobachtungen im Speicher
        
        # Pattern-Counter für IDs
        self._pattern_counter = 0
        
        # Lade existierende Muster
        self._load_patterns()
    
    def _generate_pattern_id(self) -> str:
        """Generiere eindeutige Pattern-ID."""
        self._pattern_counter += 1
        return f"pattern_{self._pattern_counter:06d}"
    
    def _load_patterns(self):
        """Lade gespeicherte Muster von Disk."""
        if self.patterns_file.exists():
            try:
                with open(self.patterns_file, "r") as f:
                    data = json.load(f)
                    self.patterns = {
                        pid: Pattern.from_dict(pdata) 
                        for pid, pdata in data.items()
                    }
                    self._pattern_counter = len(self.patterns)
                _LOGGER.info(f"Geladen: {len(self.patterns)} Muster")
            except Exception as e:
                _LOGGER.error(f"Fehler beim Laden der Muster: {e}")
                self.patterns = {}
    
    def _save_patterns(self):
        """Speichere Muster auf Disk."""
        try:
            self.data_dir.mkdir(parents=True, exist_ok=True)
            with open(self.patterns_file, "w") as f:
                json.dump(
                    {pid: p.to_dict() for pid, p in self.patterns.items()},
                    f,
                    indent=2,
                    default=str
                )
            _LOGGER.debug(f"Gespeichert: {len(self.patterns)} Muster")
        except Exception as e:
            _LOGGER.error(f"Fehler beim Speichern der Muster: {e}")
    
    def _log_observation(self, observation: Dict[str, Any]):
        """Logge Beobachtung für inkrementelles Lernen."""
        self.observations.append(observation)
        
        # Begrenze Beobachtungen
        if len(self.observations) > self.max_observations:
            self.observations = self.observations[-self.max_observations:]
        
        # Schreibe auf Disk (append)
        try:
            self.data_dir.mkdir(parents=True, exist_ok=True)
            with open(self.observations_file, "a") as f:
                f.write(json.dumps(observation, default=str) + "\n")
        except Exception as e:
            _LOGGER.warning(f"Konnte Beobachtung nicht loggen: {e}")
    
    def observe(
        self,
        entity_id: str,
        action: str,
        timestamp: Optional[datetime] = None,
        context: Optional[Dict[str, Any]] = None
    ):
        """Registriere Beobachtung für Pattern-Learning.
        
        Args:
            entity_id: Home Assistant Entity ID (z.B. "light.wohnzimmer")
            action: Ausgeführte Aktion (z.B. "turn_on", "turn_off")
            timestamp: Zeitpunkt der Aktion (default: now)
            context: Zusätzlicher Kontext (Wetter, andere Entities, etc.)
        """
        if timestamp is None:
            timestamp = datetime.now()
        
        if context is None:
            context = {}
        
        observation = {
            "timestamp": timestamp.isoformat(),
            "entity_id": entity_id,
            "action": action,
            "hour": timestamp.hour,
            "day_of_week": timestamp.weekday(),
            "context": context
        }
        
        self._log_observation(observation)
        
        # Suche nach existierenden Mustern und aktualisiere sie
        self._update_patterns(observation)
        
        # Speichere regelmäßig
        if len(self.observations) % 100 == 0:
            self._save_patterns()
    
    def _update_patterns(self, observation: Dict[str, Any]):
        """Aktualisiere oder erstelle Patterns basierend auf Beobachtung."""
        entity_id = observation["entity_id"]
        action = observation["action"]
        hour = observation["hour"]
        day_of_week = observation["day_of_week"]
        context = observation.get("context", {})
        
        # Pattern-Schlüssel für Matching
        pattern_key = f"{entity_id}:{action}"
        
        # Suche existierendes Pattern
        existing_pattern = None
        for pid, pattern in self.patterns.items():
            if (pattern.entity_id == entity_id and 
                pattern.action == action and
                pattern.pattern_type == "time_based"):
                existing_pattern = pattern
                break
        
        if existing_pattern:
            # Aktualisiere existierendes Pattern
            existing_pattern.occurrence_count += 1
            existing_pattern.last_occurrence = datetime.fromisoformat(
                observation["timestamp"]
            )
            
            # Aktualisiere Confidence basierend auf Konsistenz
            existing_pattern.confidence = self._calculate_confidence(
                existing_pattern
            )
        else:
            # Erstelle neues Pattern
            pattern = Pattern(
                pattern_id=self._generate_pattern_id(),
                pattern_type="time_based",
                entity_id=entity_id,
                action=action,
                hour_of_day=hour,
                day_of_week=day_of_week,
                time_window=(hour, hour + 1),  # 1-Stunden-Fenster
                occurrence_count=1,
                confidence=0.3,  # Initiale Confidence
                first_occurrence=datetime.fromisoformat(observation["timestamp"]),
                last_occurrence=datetime.fromisoformat(observation["timestamp"]),
            )
            self.patterns[pattern.pattern_id] = pattern
        
        # Wetter-basierte Patterns
        if context.get("weather_condition"):
            self._update_weather_pattern(observation, context)
    
    def _update_weather_pattern(
        self, 
        observation: Dict[str, Any], 
        context: Dict[str, Any]
    ):
        """Aktualisiere wetter-basierte Patterns."""
        weather = context.get("weather_condition")
        entity_id = observation["entity_id"]
        action = observation["action"]
        
        # Pattern-Schlüssel
        pattern_key = f"{entity_id}:{action}:{weather}"
        
        existing_pattern = None
        for pid, pattern in self.patterns.items():
            if (pattern.pattern_type == "weather_based" and
                pattern.entity_id == entity_id and
                pattern.action == action and
                pattern.weather_condition == weather):
                existing_pattern = pattern
                break
        
        if existing_pattern:
            existing_pattern.occurrence_count += 1
            existing_pattern.last_occurrence = datetime.fromisoformat(
                observation["timestamp"]
            )
            existing_pattern.confidence = self._calculate_confidence(
                existing_pattern
            )
        else:
            pattern = Pattern(
                pattern_id=self._generate_pattern_id(),
                pattern_type="weather_based",
                entity_id=entity_id,
                action=action,
                weather_condition=weather,
                occurrence_count=1,
                confidence=0.3,
                first_occurrence=datetime.fromisoformat(observation["timestamp"]),
                last_occurrence=datetime.fromisoformat(observation["timestamp"]),
            )
            self.patterns[pattern.pattern_id] = pattern
    
    def _calculate_confidence(self, pattern: Pattern) -> float:
        """Berechne Confidence-Score für ein Pattern.
        
        Basierend auf:
        - Häufigkeit der Beobachtungen
        - Regelmäßigkeit
        - Recency (wie aktuell)
        - Konsistenz
        """
        if pattern.occurrence_count < 3:
            return 0.3  # Zu wenig Daten
        
        # Zeit seit letzter Beobachtung
        if pattern.last_occurrence:
            days_since_last = (
                datetime.now() - pattern.last_occurrence
            ).days
            recency_factor = max(0.0, 1.0 - (days_since_last / 30.0))
        else:
            recency_factor = 0.5
        
        # Häufigkeits-Faktor (logarithmisch)
        frequency_factor = min(1.0, np.log10(pattern.occurrence_count + 1) / 3.0)
        
        # Zeitspanne der Beobachtungen
        if pattern.first_occurrence and pattern.last_occurrence:
            total_days = (
                pattern.last_occurrence - pattern.first_occurrence
            ).days + 1
            consistency_factor = min(
                1.0, pattern.occurrence_count / max(1, total_days)
            )
        else:
            consistency_factor = 0.5
        
        # Kombiniere Faktoren
        confidence = (
            0.4 * frequency_factor +
            0.3 * recency_factor +
            0.3 * consistency_factor
        )
        
        return round(min(1.0, max(0.0, confidence)), 3)
    
    def get_patterns(
        self,
        pattern_type: Optional[str] = None,
        entity_id: Optional[str] = None,
        min_confidence: float = 0.0
    ) -> List[Pattern]:
        """Hole gelernte Muster mit Filtern.
        
        Args:
            pattern_type: Filter nach Typ ("time_based", "weather_based", etc.)
            entity_id: Filter nach Entity ID
            min_confidence: Minimale Confidence
        
        Returns:
            Liste der passenden Patterns
        """
        filtered = []
        for pattern in self.patterns.values():
            if pattern_type and pattern.pattern_type != pattern_type:
                continue
            if entity_id and pattern.entity_id != entity_id:
                continue
            if pattern.confidence < min_confidence:
                continue
            filtered.append(pattern)
        
        # Sortiere nach Confidence (absteigend)
        return sorted(filtered, key=lambda p: p.confidence, reverse=True)
    
    def get_pattern_stats(self) -> PatternStats:
        """Hole Statistik über gelernte Muster."""
        stats = PatternStats()
        stats.total_patterns = len(self.patterns)
        stats.total_observations = len(self.observations)
        
        confidences = []
        for pattern in self.patterns.values():
            if pattern.pattern_type == "time_based":
                stats.time_based_patterns += 1
            elif pattern.pattern_type == "weather_based":
                stats.weather_based_patterns += 1
            elif pattern.pattern_type == "sequence":
                stats.sequence_patterns += 1
            elif pattern.pattern_type == "device":
                stats.device_patterns += 1
            
            confidences.append(pattern.confidence)
        
        if confidences:
            stats.avg_confidence = round(
                sum(confidences) / len(confidences), 3
            )

        return stats

    @staticmethod
    def _normalize_summary_text(value: Any) -> Optional[str]:
        """Return a summary-safe string or ``None`` when no truthful text exists."""
        if not isinstance(value, str):
            return None
        normalized = value.strip()
        return normalized or None

    def _extract_summary_zone(self, pattern: Pattern) -> Optional[str]:
        """Read a truthful zone label from summary-safe metadata only."""
        metadata = pattern.metadata if isinstance(pattern.metadata, dict) else {}
        for key in ("zone", "zone_name", "area", "area_name"):
            normalized = self._normalize_summary_text(metadata.get(key))
            if normalized:
                return normalized

        context = metadata.get("context")
        if isinstance(context, dict):
            for key in ("zone", "zone_name"):
                normalized = self._normalize_summary_text(context.get(key))
                if normalized:
                    return normalized

        return None

    @staticmethod
    def _categorize_pattern(pattern: Pattern) -> str:
        """Map a learned pattern to the bounded report categories."""
        domain = pattern.entity_id.split(".", 1)[0].lower() if "." in pattern.entity_id else ""
        entity_id = pattern.entity_id.lower()

        if pattern.pattern_type == "weather_based" or domain in {"climate", "water_heater", "humidifier"}:
            return "climate"
        if domain in {"media_player", "remote"}:
            return "media"
        if domain in {"person", "device_tracker"} or "presence" in entity_id or "occupancy" in entity_id:
            return "presence"
        if domain == "sensor" and any(token in entity_id for token in ("energy", "power", "verbrauch", "solar")):
            return "energy"
        return "automation"

    @staticmethod
    def _metadata_float(metadata: Dict[str, Any], *keys: str) -> float:
        """Read a non-negative float from metadata, otherwise return ``0.0``."""
        for key in keys:
            value = metadata.get(key)
            if isinstance(value, bool):
                continue
            if isinstance(value, (int, float)):
                return round(max(0.0, float(value)), 3)
        return 0.0

    def get_pattern_summaries(
        self,
        *,
        min_confidence: float = 0.0,
        window_start: Optional[datetime] = None,
        window_end: Optional[datetime] = None,
    ) -> List[Dict[str, Any]]:
        """Return a bounded summary-friendly view over learned patterns."""
        summaries: List[Dict[str, Any]] = []

        for pattern in self.get_patterns(min_confidence=min_confidence):
            last_occurrence = pattern.last_occurrence
            if window_start and (last_occurrence is None or last_occurrence < window_start):
                continue
            if window_end and (last_occurrence is None or last_occurrence > window_end):
                continue

            metadata = pattern.metadata if isinstance(pattern.metadata, dict) else {}
            summaries.append({
                "pattern_id": pattern.pattern_id,
                "pattern_type": pattern.pattern_type,
                "category": self._categorize_pattern(pattern),
                "entity_id": pattern.entity_id,
                "action": pattern.action,
                "zone": self._extract_summary_zone(pattern),
                "confidence": round(pattern.confidence, 3),
                "occurrence_count": int(pattern.occurrence_count),
                "last_occurrence": last_occurrence.isoformat() if last_occurrence else None,
                "hour_of_day": pattern.hour_of_day,
                "day_of_week": pattern.day_of_week,
                "estimated_energy_impact_kwh": self._metadata_float(
                    metadata,
                    "estimated_energy_impact_kwh",
                    "energy_impact_kwh",
                ),
                "estimated_cost_impact_eur": self._metadata_float(
                    metadata,
                    "estimated_cost_impact_eur",
                    "cost_impact_eur",
                ),
            })

        summaries.sort(
            key=lambda item: (
                -float(item["confidence"]),
                -int(item["occurrence_count"]),
                str(item["pattern_id"]),
            )
        )
        return summaries

    def clear_patterns(self):
        """Lösche alle gelernten Muster."""
        self.patterns.clear()
        self.observations.clear()
        self._pattern_counter = 0
        self._save_patterns()
        _LOGGER.info("Alle Muster gelöscht")
    
    def export_patterns(self) -> Dict[str, Any]:
        """Exportiere alle Muster als Dictionary."""
        return {
            "patterns": [p.to_dict() for p in self.patterns.values()],
            "stats": asdict(self.get_pattern_stats()),
            "exported_at": datetime.now().isoformat()
        }
