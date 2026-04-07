"""Bewegungsmodul — Bewegungserkennung pro Zone (v1.0.0).

Verfolgt Bewegungssensoren pro Zone mit Trigger-Zaehlung,
Zeitfenstern und Aktivitaetserkennung.

Features:
- Bewegungssensor-Tracking mit Trigger-Zaehlung
- Zeitfenster-Erkennung (5 Min, 30 Min)
- Taegliche Trigger-Statistik pro Zone
- Globale Bewegungsuebersicht
- LLM-Kontext fuer Sprachsteuerung
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class MotionSensor:
    """Einzelner Bewegungssensor."""

    entity_id: str
    zone_id: str = ""
    friendly_name: str = ""
    is_active: bool = False
    last_triggered: datetime | None = None
    trigger_count: int = 0


@dataclass
class ZoneMotion:
    """Aggregierter Bewegungszustand einer Zone."""

    zone_id: str
    zone_name: str = ""
    sensors_active: int = 0
    sensors_total: int = 0
    last_motion: datetime | None = None
    motion_in_last_5min: bool = False
    motion_in_last_30min: bool = False
    daily_triggers: int = 0


@dataclass
class BewegungDashboard:
    """Komplettes Bewegungsmodul-Dashboard."""

    zones: list[dict[str, Any]] = field(default_factory=list)
    total_sensors: int = 0
    sensors_active: int = 0
    last_global_motion: datetime | None = None
    zones_with_motion: int = 0


class BewegungModuleEngine:
    """Bewegungsmodul Engine — verwaltet Bewegungssensoren pro Zone."""

    def __init__(self) -> None:
        self._sensors: dict[str, MotionSensor] = {}
        self._zone_names: dict[str, str] = {}

    def register_sensor(
        self, entity_id: str, zone_id: str, friendly_name: str = "",
    ) -> MotionSensor:
        """Registriert einen Bewegungssensor."""
        sensor = MotionSensor(
            entity_id=entity_id, zone_id=zone_id,
            friendly_name=friendly_name or entity_id,
        )
        self._sensors[entity_id] = sensor
        logger.debug("Bewegungsmodul: Sensor %s registriert in Zone %s", entity_id, zone_id)
        return sensor

    def remove_sensor(self, entity_id: str) -> bool:
        """Entfernt einen Bewegungssensor."""
        removed = self._sensors.pop(entity_id, None)
        if removed:
            logger.debug("Bewegungsmodul: Sensor %s entfernt", entity_id)
        return removed is not None

    def configure_zone(self, zone_id: str, zone_name: str = "") -> None:
        """Konfiguriert den Zonennamen."""
        if zone_name:
            self._zone_names[zone_id] = zone_name

    def trigger_motion(self, entity_id: str) -> MotionSensor | None:
        """Loest eine Bewegungserkennung aus."""
        sensor = self._sensors.get(entity_id)
        if sensor is None:
            return None
        sensor.is_active = True
        sensor.last_triggered = datetime.now(tz=timezone.utc)
        sensor.trigger_count += 1
        logger.debug("Bewegungsmodul: Bewegung erkannt bei %s (Trigger #%d)", entity_id, sensor.trigger_count)
        return sensor

    def clear_motion(self, entity_id: str) -> MotionSensor | None:
        """Setzt einen Bewegungssensor zurueck."""
        sensor = self._sensors.get(entity_id)
        if sensor is None:
            return None
        sensor.is_active = False
        logger.debug("Bewegungsmodul: Bewegung geloescht bei %s", entity_id)
        return sensor

    def get_zone_motion(self, zone_id: str) -> ZoneMotion:
        """Berechnet den Bewegungszustand einer Zone."""
        sensors = [s for s in self._sensors.values() if s.zone_id == zone_id]
        now = datetime.now(tz=timezone.utc)
        active = [s for s in sensors if s.is_active]

        triggered_sensors = [s for s in sensors if s.last_triggered is not None]
        last_motion = max((s.last_triggered for s in triggered_sensors), default=None) if triggered_sensors else None

        motion_5min = False
        motion_30min = False
        if last_motion is not None:
            delta = now - last_motion
            motion_5min = delta <= timedelta(minutes=5)
            motion_30min = delta <= timedelta(minutes=30)

        daily_triggers = 0
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        for s in sensors:
            if s.last_triggered is not None and s.last_triggered >= today_start:
                daily_triggers += s.trigger_count

        return ZoneMotion(
            zone_id=zone_id,
            zone_name=self._zone_names.get(zone_id, zone_id),
            sensors_active=len(active),
            sensors_total=len(sensors),
            last_motion=last_motion,
            motion_in_last_5min=motion_5min,
            motion_in_last_30min=motion_30min,
            daily_triggers=daily_triggers,
        )

    def get_dashboard(self) -> BewegungDashboard:
        """Erstellt das komplette Bewegungsmodul-Dashboard."""
        zones_data: list[dict[str, Any]] = []
        zone_ids = set(s.zone_id for s in self._sensors.values() if s.zone_id)

        all_active = sum(1 for s in self._sensors.values() if s.is_active)
        triggered = [s for s in self._sensors.values() if s.last_triggered is not None]
        last_global = max((s.last_triggered for s in triggered), default=None) if triggered else None
        zones_with_motion = 0

        for zone_id in sorted(zone_ids):
            state = self.get_zone_motion(zone_id)
            if state.motion_in_last_30min:
                zones_with_motion += 1
            zones_data.append({
                "zone_id": zone_id, "zone_name": state.zone_name,
                "sensors_active": state.sensors_active,
                "sensors_total": state.sensors_total,
                "last_motion": state.last_motion.isoformat() if state.last_motion else None,
                "motion_in_last_5min": state.motion_in_last_5min,
                "motion_in_last_30min": state.motion_in_last_30min,
                "daily_triggers": state.daily_triggers,
            })

        return BewegungDashboard(
            zones=zones_data,
            total_sensors=len(self._sensors),
            sensors_active=all_active,
            last_global_motion=last_global,
            zones_with_motion=zones_with_motion,
        )

    def get_summary(self) -> dict[str, Any]:
        """Zusammenfassung fuer API-Antworten."""
        d = self.get_dashboard()
        return {
            "total_sensors": d.total_sensors,
            "sensors_active": d.sensors_active,
            "last_global_motion": d.last_global_motion.isoformat() if d.last_global_motion else None,
            "zones_with_motion": d.zones_with_motion,
            "zones": d.zones,
        }

    def get_context_for_llm(self) -> str:
        """LLM-Kontextinjektion."""
        d = self.get_dashboard()
        if d.total_sensors == 0:
            return ""
        lines = [
            f"Bewegungsmodul: {d.sensors_active}/{d.total_sensors} Sensoren aktiv, "
            f"{d.zones_with_motion} Zonen mit Bewegung"
        ]
        for z in d.zones:
            if z["motion_in_last_5min"]:
                status = "aktiv (< 5 Min)"
            elif z["motion_in_last_30min"]:
                status = "kuerzlich (< 30 Min)"
            else:
                status = "ruhig"
            lines.append(
                f"  {z['zone_name']}: {z['sensors_active']}/{z['sensors_total']} aktiv, "
                f"{status}, {z['daily_triggers']} Trigger heute"
            )
        return "\n".join(lines)
