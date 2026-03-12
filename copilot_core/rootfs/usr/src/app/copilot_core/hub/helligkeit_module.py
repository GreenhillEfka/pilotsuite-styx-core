"""Helligkeitsmodul — Helligkeitsverfolgung pro Zone (v1.1.0).

Verfolgt Lux-Sensoren (innen/aussen) pro Zone und berechnet
Lichtbedarf, Defizit und empfohlene Dimmung.

Architektur-Hinweis:
    Dieses Modul ist der **Sensor-Layer** fuer Helligkeitsdaten.
    ``light_intelligence.py`` ist der uebergeordnete **Intelligence-Layer**
    mit Sonnentracking, Mood-Scenes und erweiterter Analyse.
    Beide nutzen ``CloudResilientFilter`` aus ``brightness_filter.py``
    fuer die cloud-resistente Aussenbeleuchtung.

Features:
- Indoor/Outdoor Helligkeitssensoren mit Lux-Tracking
- Cloud-resistenter gleitender Durchschnitt fuer Aussenbeleuchtung
- Hysterese (12%) zur Vermeidung von Flackern bei Wolkendurchzug
- Empfohlene Dimmwerte pro Zone
- LLM-Kontext fuer Sprachsteuerung
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from copilot_core.hub.brightness_filter import CloudResilientFilter

logger = logging.getLogger(__name__)


@dataclass
class HelligkeitSensor:
    """Einzelner Helligkeitssensor."""

    entity_id: str
    zone_id: str = ""
    location: str = "indoor"  # indoor | outdoor
    last_lux: float = 0.0
    last_update: datetime = field(default_factory=lambda: datetime.now(tz=timezone.utc))


@dataclass
class ZoneHelligkeit:
    """Aggregierter Helligkeitszustand einer Zone."""

    zone_id: str
    zone_name: str = ""
    avg_indoor_lux: float = 0.0
    avg_outdoor_lux: float = 0.0
    target_lux: float = 300.0
    min_lux: float = 100.0
    needs_light: bool = False
    deficit_pct: float = 0.0
    recommended_dimming_pct: float = 0.0


@dataclass
class HelligkeitDashboard:
    """Komplettes Helligkeitsmodul-Dashboard."""

    zones: list[dict[str, Any]] = field(default_factory=list)
    global_outdoor_lux: float = 0.0
    total_sensors: int = 0
    zones_needing_light: int = 0


class HelligkeitModuleEngine:
    """Helligkeitsmodul Engine — verwaltet Lux-Sensoren pro Zone."""

    def __init__(self) -> None:
        self._sensors: dict[str, HelligkeitSensor] = {}
        self._zone_config: dict[str, dict[str, Any]] = {}
        self._zone_names: dict[str, str] = {}
        self._outdoor_filter = CloudResilientFilter(window_size=10, hysteresis_pct=12.0)

    def register_sensor(
        self, entity_id: str, zone_id: str, location: str = "indoor",
    ) -> HelligkeitSensor:
        """Registriert einen Helligkeitssensor."""
        sensor = HelligkeitSensor(
            entity_id=entity_id, zone_id=zone_id, location=location,
        )
        self._sensors[entity_id] = sensor
        logger.debug("Helligkeitsmodul: Sensor %s registriert in Zone %s (%s)", entity_id, zone_id, location)
        return sensor

    def remove_sensor(self, entity_id: str) -> bool:
        """Entfernt einen Helligkeitssensor."""
        removed = self._sensors.pop(entity_id, None)
        if removed:
            logger.debug("Helligkeitsmodul: Sensor %s entfernt", entity_id)
        return removed is not None

    def configure_zone(
        self, zone_id: str, zone_name: str = "",
        target_lux: float = 300.0, min_lux: float = 100.0,
    ) -> None:
        """Konfiguriert Helligkeitszielwerte fuer eine Zone."""
        self._zone_config[zone_id] = {
            "target_lux": target_lux,
            "min_lux": min_lux,
        }
        if zone_name:
            self._zone_names[zone_id] = zone_name
        logger.debug("Helligkeitsmodul: Zone %s konfiguriert (Ziel: %.0f lx, Min: %.0f lx)", zone_id, target_lux, min_lux)

    def update_reading(self, entity_id: str, lux: float) -> HelligkeitSensor | None:
        """Aktualisiert einen Lux-Messwert."""
        sensor = self._sensors.get(entity_id)
        if sensor is None:
            return None
        sensor.last_lux = lux
        sensor.last_update = datetime.now(tz=timezone.utc)
        if sensor.location == "outdoor":
            self._outdoor_filter.add_reading(lux)
        logger.debug("Helligkeitsmodul: %s = %.1f lx", entity_id, lux)
        return sensor

    def update_batch(self, readings: dict[str, float]) -> int:
        """Aktualisiert mehrere Sensoren gleichzeitig. Gibt Anzahl aktualisierter Sensoren zurueck."""
        count = 0
        for entity_id, lux in readings.items():
            if self.update_reading(entity_id, lux) is not None:
                count += 1
        return count

    def get_outdoor_brightness(self) -> float:
        """Berechnet cloud-resistente Aussenbeleuchtung (12% Hysterese via CloudResilientFilter)."""
        return self._outdoor_filter.get_filtered()

    def get_zone_brightness(self, zone_id: str) -> ZoneHelligkeit:
        """Berechnet den Helligkeitszustand einer Zone."""
        sensors = [s for s in self._sensors.values() if s.zone_id == zone_id]
        indoor = [s for s in sensors if s.location == "indoor"]
        outdoor = [s for s in sensors if s.location == "outdoor"]

        avg_indoor = sum(s.last_lux for s in indoor) / len(indoor) if indoor else 0.0
        avg_outdoor = sum(s.last_lux for s in outdoor) / len(outdoor) if outdoor else self.get_outdoor_brightness()

        config = self._zone_config.get(zone_id, {})
        target = config.get("target_lux", 300.0)
        min_lux = config.get("min_lux", 100.0)

        needs_light = avg_indoor < min_lux
        deficit_pct = max(0.0, (target - avg_indoor) / target * 100.0) if target > 0 else 0.0
        recommended_dimming = min(100.0, max(0.0, deficit_pct))

        return ZoneHelligkeit(
            zone_id=zone_id,
            zone_name=self._zone_names.get(zone_id, zone_id),
            avg_indoor_lux=round(avg_indoor, 1),
            avg_outdoor_lux=round(avg_outdoor, 1),
            target_lux=target,
            min_lux=min_lux,
            needs_light=needs_light,
            deficit_pct=round(deficit_pct, 1),
            recommended_dimming_pct=round(recommended_dimming, 1),
        )

    def get_dashboard(self) -> HelligkeitDashboard:
        """Erstellt das komplette Helligkeitsmodul-Dashboard."""
        zones_data: list[dict[str, Any]] = []
        zone_ids = set(s.zone_id for s in self._sensors.values() if s.zone_id)
        needing_light = 0
        for zone_id in sorted(zone_ids):
            state = self.get_zone_brightness(zone_id)
            if state.needs_light:
                needing_light += 1
            zones_data.append({
                "zone_id": zone_id, "zone_name": state.zone_name,
                "avg_indoor_lux": state.avg_indoor_lux,
                "avg_outdoor_lux": state.avg_outdoor_lux,
                "target_lux": state.target_lux,
                "min_lux": state.min_lux,
                "needs_light": state.needs_light,
                "deficit_pct": state.deficit_pct,
                "recommended_dimming_pct": state.recommended_dimming_pct,
            })
        return HelligkeitDashboard(
            zones=zones_data,
            global_outdoor_lux=round(self.get_outdoor_brightness(), 1),
            total_sensors=len(self._sensors),
            zones_needing_light=needing_light,
        )

    def get_summary(self) -> dict[str, Any]:
        """Zusammenfassung fuer API-Antworten."""
        d = self.get_dashboard()
        return {
            "total_sensors": d.total_sensors,
            "global_outdoor_lux": d.global_outdoor_lux,
            "zones_needing_light": d.zones_needing_light,
            "zones": d.zones,
        }

    def get_context_for_llm(self) -> str:
        """LLM-Kontextinjektion."""
        d = self.get_dashboard()
        if d.total_sensors == 0:
            return ""
        lines = [
            f"Helligkeitsmodul: {d.total_sensors} Sensoren, "
            f"Aussen {d.global_outdoor_lux:.0f} lx, "
            f"{d.zones_needing_light} Zonen brauchen Licht"
        ]
        for z in d.zones:
            status = "braucht Licht" if z["needs_light"] else "ausreichend"
            lines.append(
                f"  {z['zone_name']}: Innen {z['avg_indoor_lux']:.0f} lx, "
                f"Ziel {z['target_lux']:.0f} lx ({status})"
            )
        return "\n".join(lines)
