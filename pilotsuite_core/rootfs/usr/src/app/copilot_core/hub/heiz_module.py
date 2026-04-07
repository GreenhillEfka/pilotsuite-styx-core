"""Heizmodul — Heizungs- und Klimasteuerung pro Zone (v1.0.0).

Verwaltet Temperatursensoren, Luftfeuchtigkeit und Heizkoerper pro Zone.
Berechnet Komfortindex und steuert Eco-/Komfort-Modus.

Features:
- Temperatur- und Feuchtigkeitssensoren pro Zone
- Heizkoerper-Status und Zieltemperatur-Management
- Komfortindex (0-100) basierend auf Temperatur und Luftfeuchtigkeit
- Eco-Modus mit reduzierter Zieltemperatur
- LLM-Kontext fuer Sprachsteuerung
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class TemperatureSensor:
    """Einzelner Temperatur- oder Feuchtigkeitssensor."""

    entity_id: str
    zone_id: str = ""
    sensor_type: str = "temperature"  # temperature | humidity
    value: float = 0.0
    unit: str = "°C"
    last_update: datetime = field(default_factory=lambda: datetime.now(tz=timezone.utc))


@dataclass
class HeatingEntity:
    """Einzelne Heizungsentitaet."""

    entity_id: str
    zone_id: str = ""
    friendly_name: str = ""
    hvac_mode: str = "off"
    target_temp: float = 21.0
    current_temp: float = 0.0
    is_heating: bool = False
    last_update: datetime = field(default_factory=lambda: datetime.now(tz=timezone.utc))


@dataclass
class ZoneClimate:
    """Aggregierter Klimazustand einer Zone."""

    zone_id: str
    zone_name: str = ""
    current_temp: float = 0.0
    target_temp: float = 21.0
    humidity: float = 0.0
    is_heating: bool = False
    eco_mode: bool = False
    comfort_index: int = 0
    needs_heating: bool = False
    temp_delta: float = 0.0


@dataclass
class HeizDashboard:
    """Komplettes Heizmodul-Dashboard."""

    zones: list[dict[str, Any]] = field(default_factory=list)
    avg_indoor_temp: float = 0.0
    avg_humidity: float = 0.0
    zones_heating: int = 0
    zones_eco: int = 0
    total_climate_entities: int = 0


def _compute_comfort_index(temp: float, humidity: float) -> int:
    """Berechnet den Komfortindex (0-100) basierend auf Temperatur und Luftfeuchtigkeit.

    Optimale Bereiche: Temperatur 20-22°C, Luftfeuchtigkeit 40-60%.
    """
    # Temperaturkomponente (0-50 Punkte)
    if 20.0 <= temp <= 22.0:
        temp_score = 50.0
    elif temp < 20.0:
        temp_score = max(0.0, 50.0 - (20.0 - temp) * 10.0)
    else:
        temp_score = max(0.0, 50.0 - (temp - 22.0) * 10.0)

    # Feuchtigkeitskomponente (0-50 Punkte)
    if 40.0 <= humidity <= 60.0:
        hum_score = 50.0
    elif humidity < 40.0:
        hum_score = max(0.0, 50.0 - (40.0 - humidity) * 1.5)
    else:
        hum_score = max(0.0, 50.0 - (humidity - 60.0) * 1.5)

    return int(min(100, max(0, round(temp_score + hum_score))))


class HeizModuleEngine:
    """Heizmodul Engine — verwaltet Klimaentitaeten pro Zone."""

    def __init__(self) -> None:
        self._sensors: dict[str, TemperatureSensor] = {}
        self._heaters: dict[str, HeatingEntity] = {}
        self._zone_config: dict[str, dict[str, Any]] = {}
        self._zone_names: dict[str, str] = {}

    def register_sensor(
        self, entity_id: str, zone_id: str,
        sensor_type: str = "temperature", unit: str = "°C",
    ) -> TemperatureSensor:
        """Registriert einen Temperatur- oder Feuchtigkeitssensor."""
        sensor = TemperatureSensor(
            entity_id=entity_id, zone_id=zone_id,
            sensor_type=sensor_type, unit=unit,
        )
        self._sensors[entity_id] = sensor
        logger.debug("Heizmodul: Sensor %s registriert in Zone %s (%s)", entity_id, zone_id, sensor_type)
        return sensor

    def register_heater(
        self, entity_id: str, zone_id: str, friendly_name: str = "",
    ) -> HeatingEntity:
        """Registriert eine Heizungsentitaet."""
        heater = HeatingEntity(
            entity_id=entity_id, zone_id=zone_id,
            friendly_name=friendly_name or entity_id,
        )
        self._heaters[entity_id] = heater
        logger.debug("Heizmodul: Heizung %s registriert in Zone %s", entity_id, zone_id)
        return heater

    def configure_zone(
        self, zone_id: str, zone_name: str = "",
        target_temp: float = 21.0, eco_temp: float = 17.0,
    ) -> None:
        """Konfiguriert Zieltemperaturen fuer eine Zone."""
        self._zone_config[zone_id] = {
            "target_temp": target_temp,
            "eco_temp": eco_temp,
            "eco_mode": False,
        }
        if zone_name:
            self._zone_names[zone_id] = zone_name
        logger.debug("Heizmodul: Zone %s konfiguriert (Ziel: %.1f°C, Eco: %.1f°C)", zone_id, target_temp, eco_temp)

    def set_eco_mode(self, zone_id: str, enabled: bool = True) -> bool:
        """Aktiviert oder deaktiviert den Eco-Modus fuer eine Zone."""
        config = self._zone_config.get(zone_id)
        if config is None:
            self._zone_config[zone_id] = {"target_temp": 21.0, "eco_temp": 17.0, "eco_mode": enabled}
        else:
            config["eco_mode"] = enabled
        logger.debug("Heizmodul: Eco-Modus fuer Zone %s %s", zone_id, "aktiviert" if enabled else "deaktiviert")
        return True

    def update_sensor(
        self, entity_id: str, value: float,
    ) -> TemperatureSensor | None:
        """Aktualisiert einen Sensorwert."""
        sensor = self._sensors.get(entity_id)
        if sensor is None:
            return None
        sensor.value = value
        sensor.last_update = datetime.now(tz=timezone.utc)
        logger.debug("Heizmodul: %s = %.1f %s", entity_id, value, sensor.unit)
        return sensor

    def update_heater(
        self, entity_id: str, hvac_mode: str = "",
        target_temp: float | None = None, current_temp: float | None = None,
        is_heating: bool | None = None,
    ) -> HeatingEntity | None:
        """Aktualisiert den Zustand einer Heizungsentitaet."""
        heater = self._heaters.get(entity_id)
        if heater is None:
            return None
        if hvac_mode:
            heater.hvac_mode = hvac_mode
        if target_temp is not None:
            heater.target_temp = target_temp
        if current_temp is not None:
            heater.current_temp = current_temp
        if is_heating is not None:
            heater.is_heating = is_heating
        heater.last_update = datetime.now(tz=timezone.utc)
        return heater

    def get_zone_climate(self, zone_id: str) -> ZoneClimate:
        """Berechnet den Klimazustand einer Zone."""
        temp_sensors = [s for s in self._sensors.values() if s.zone_id == zone_id and s.sensor_type == "temperature"]
        hum_sensors = [s for s in self._sensors.values() if s.zone_id == zone_id and s.sensor_type == "humidity"]
        heaters = [h for h in self._heaters.values() if h.zone_id == zone_id]

        current_temp = sum(s.value for s in temp_sensors) / len(temp_sensors) if temp_sensors else 0.0
        humidity = sum(s.value for s in hum_sensors) / len(hum_sensors) if hum_sensors else 0.0
        is_heating = any(h.is_heating for h in heaters)

        config = self._zone_config.get(zone_id, {})
        eco_mode = config.get("eco_mode", False)
        target = config.get("eco_temp", 17.0) if eco_mode else config.get("target_temp", 21.0)
        temp_delta = current_temp - target
        needs_heating = current_temp < target
        comfort = _compute_comfort_index(current_temp, humidity)

        return ZoneClimate(
            zone_id=zone_id,
            zone_name=self._zone_names.get(zone_id, zone_id),
            current_temp=round(current_temp, 1),
            target_temp=target,
            humidity=round(humidity, 1),
            is_heating=is_heating,
            eco_mode=eco_mode,
            comfort_index=comfort,
            needs_heating=needs_heating,
            temp_delta=round(temp_delta, 1),
        )

    def get_dashboard(self) -> HeizDashboard:
        """Erstellt das komplette Heizmodul-Dashboard."""
        zones_data: list[dict[str, Any]] = []
        all_zone_ids: set[str] = set()
        for s in self._sensors.values():
            if s.zone_id:
                all_zone_ids.add(s.zone_id)
        for h in self._heaters.values():
            if h.zone_id:
                all_zone_ids.add(h.zone_id)

        all_temps: list[float] = []
        all_hums: list[float] = []
        zones_heating = 0
        zones_eco = 0

        for zone_id in sorted(all_zone_ids):
            state = self.get_zone_climate(zone_id)
            if state.current_temp > 0:
                all_temps.append(state.current_temp)
            if state.humidity > 0:
                all_hums.append(state.humidity)
            if state.is_heating:
                zones_heating += 1
            if state.eco_mode:
                zones_eco += 1
            zones_data.append({
                "zone_id": zone_id, "zone_name": state.zone_name,
                "current_temp": state.current_temp, "target_temp": state.target_temp,
                "humidity": state.humidity, "is_heating": state.is_heating,
                "eco_mode": state.eco_mode, "comfort_index": state.comfort_index,
                "needs_heating": state.needs_heating, "temp_delta": state.temp_delta,
            })

        avg_temp = sum(all_temps) / len(all_temps) if all_temps else 0.0
        avg_hum = sum(all_hums) / len(all_hums) if all_hums else 0.0
        total_entities = len(self._sensors) + len(self._heaters)

        return HeizDashboard(
            zones=zones_data,
            avg_indoor_temp=round(avg_temp, 1),
            avg_humidity=round(avg_hum, 1),
            zones_heating=zones_heating,
            zones_eco=zones_eco,
            total_climate_entities=total_entities,
        )

    def get_summary(self) -> dict[str, Any]:
        """Zusammenfassung fuer API-Antworten."""
        d = self.get_dashboard()
        return {
            "total_climate_entities": d.total_climate_entities,
            "avg_indoor_temp": d.avg_indoor_temp,
            "avg_humidity": d.avg_humidity,
            "zones_heating": d.zones_heating,
            "zones_eco": d.zones_eco,
            "zones": d.zones,
        }

    def get_context_for_llm(self) -> str:
        """LLM-Kontextinjektion."""
        d = self.get_dashboard()
        if d.total_climate_entities == 0:
            return ""
        lines = [
            f"Heizmodul: {d.avg_indoor_temp:.1f}°C Durchschnitt, "
            f"{d.avg_humidity:.0f}% Feuchte, "
            f"{d.zones_heating} Zonen heizen, {d.zones_eco} Eco-Modus"
        ]
        for z in d.zones:
            mode = "Eco" if z["eco_mode"] else "Komfort"
            heat_status = "heizt" if z["is_heating"] else "aus"
            lines.append(
                f"  {z['zone_name']}: {z['current_temp']:.1f}°C "
                f"(Ziel {z['target_temp']:.1f}°C, {mode}, {heat_status}, "
                f"Komfort {z['comfort_index']})"
            )
        return "\n".join(lines)
